#!/usr/bin/env python3
"""
src/database/drug_writer.py — the SINGLE writer for the `drugs` table.
=====================================================================
The only approved path to create or modify a drug record (Constitution §4,
Governance Table, ADR-010). Collectors/enrichers/intake call this; they never
write `drugs` directly.

On every write it:
  1. RESOLVES IDENTITY via the shared entity_matcher (no duplicate molecules).
  2. APPLIES GOVERNANCE (brand_name⇒approved; company_id present/originator;
     target molecular-only; "—" brand cleared; unknown columns rejected).
  3. REQUIRES A SOURCE (Constitution §2) — records it to drug_sources.
  4. WRITES (upsert on id), then runs a VALIDATION query and returns a report.

Use `dry_run=True` to see what would happen with no writes. Returns a structured
result so callers (and tests) can assert on it.

    from src.database.drug_writer import DrugWriter
    w = DrugWriter()
    res = w.upsert({"name":"SL-325","company_id":"shattucklabs","stage":"Phase 1",
                    "target":"DR3"}, source={"url":"https://...","type":"press_release"})
"""
import os, re, sys, pathlib

_BASE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BASE / "src" / "database"))
sys.path.insert(0, str(_BASE / "scripts"))  # entity_matcher currently lives here (Phase 3 moves it)
import client
from entity_matcher import Registry

APPROVED_STAGES = {"approved", "approved_us", "approved_eu", "approved_china",
                   "approved_us_eu", "approved_partial"}


def _slug(name):
    s = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    return s or None


class GovernanceError(Exception):
    pass


class DrugWriter:
    def __init__(self, dry_run=False, source_required=True):
        self.dry_run = dry_run
        self.source_required = source_required
        self._reg = None
        self._cols = None

    @property
    def reg(self):
        if self._reg is None:
            self._reg = Registry(client.SUPABASE_URL, client._headers())
        return self._reg

    @property
    def cols(self):
        if self._cols is None:
            self._cols = client.columns("drugs")
        return self._cols

    # ---- governance ----------------------------------------------------
    def check_governance(self, rec):
        errs, warns, rec = [], [], dict(rec)
        # unknown columns
        unknown = [k for k in rec if self.cols and k not in self.cols]
        if unknown:
            errs.append(f"unknown drug columns: {unknown}")
        # brand "—" -> null
        if rec.get("brand_name") in ("—", "-", ""):
            rec["brand_name"] = None
        # brand implies approved
        if rec.get("brand_name") and (rec.get("stage") or "").lower() not in APPROVED_STAGES:
            errs.append(f"brand_name set but stage '{rec.get('stage')}' not approved (CLAUDE.md §4)")
        # company_id required (originator)
        if not rec.get("company_id") and not rec.get("id"):
            errs.append("company_id required on new drug (originator; CLAUDE.md §1)")
        # target molecular-only (warn, don't block)
        tgt = rec.get("target") or ""
        if re.search(r"\b(inc|ltd|pharma|therapeutics|biosciences)\b", tgt, re.I):
            warns.append(f"target '{tgt}' looks like it contains a company name (should be molecular only)")
        return errs, warns, rec

    # ---- identity ------------------------------------------------------
    def resolve_identity(self, rec):
        """Return (existing_id_or_None, candidate_id). Never create a duplicate."""
        if rec.get("id"):
            return rec["id"], rec["id"]
        # match by name / dev_code / inn against the canonical registry
        for field in ("name", "dev_code", "inn_name"):
            v = rec.get(field)
            if not v:
                continue
            hits = [h for h in self.reg.resolve(v) if h[0] == "drug"]
            if len(hits) == 1:
                return hits[0][1], hits[0][1]
        return None, _slug(rec.get("name"))

    # ---- write ---------------------------------------------------------
    def upsert(self, rec, source=None):
        report = {"action": None, "drug_id": None, "errors": [], "warnings": [],
                  "validation": {}, "dry_run": self.dry_run}
        errs, warns, rec = self.check_governance(rec)
        report["warnings"] = warns
        if self.source_required and not (source and source.get("url")) and not rec.get("id"):
            errs.append("source with a real URL required for a new drug (Constitution §2)")
        if errs:
            report["errors"] = errs
            return report
        existing, cand_id = self.resolve_identity(rec)
        rec["id"] = existing or cand_id
        report["drug_id"] = rec["id"]
        report["action"] = "update" if existing else "create"
        if self.dry_run:
            report["validation"] = self.validate(rec["id"], preview=rec)
            return report
        code, body, _ = client.insert("drugs", rec, on_conflict="id")
        if code >= 300:
            report["errors"].append(f"write failed: {code} {str(body)[:200]}")
            return report
        if source and source.get("url"):
            self._record_source(rec, source)
        report["validation"] = self.validate(rec["id"])
        return report

    def _record_source(self, rec, source):
        client.insert("drug_sources", {
            "drug_id": rec["id"], "drug_name": rec.get("name"),
            "claim_type": source.get("claim_type", "drug_record"),
            "claim_value": source.get("claim_value", f"{rec.get('name')} record write"),
            "source_url": source["url"], "source_type": source.get("type", "other"),
            "content_confirms_claim": True, "confidence": source.get("confidence", "confirmed"),
            "added_by": source.get("added_by", "DrugWriter"),
            "session_label": source.get("session_label", "DrugWriter"),
        }, return_rep=False)

    # ---- in-place field update (no identity resolution; drug must exist) ----
    def update_fields(self, drug_id, fields):
        """Governance-checked partial update of an EXISTING drug. Lighter than
        upsert (no entity_matcher build) — for field patches like canonical_drug_id."""
        report = {"action": "update", "drug_id": drug_id, "errors": [], "warnings": [], "dry_run": self.dry_run}
        errs, warns, merged = self.check_governance({**fields, "id": drug_id})
        report["warnings"] = warns
        merged.pop("id", None)
        if errs:
            report["errors"] = errs
            return report
        if self.dry_run:
            return report
        code, body, _ = client.update("drugs", f"id=eq.{drug_id}", merged)
        if code >= 300:
            report["errors"].append(f"update failed: {code} {str(body)[:160]}")
        return report

    # ---- validation (Constitution §6) ----------------------------------
    def validate(self, drug_id, preview=None):
        v = {}
        # duplicate identity by name
        nm = (preview or {}).get("name")
        if not nm and not self.dry_run:
            rows = client.select("drugs", {"id": f"eq.{drug_id}", "select": "name,brand_name,stage"})
            nm = rows[0]["name"] if rows else None
        if nm:
            same = client.select("drugs", {"name": f"ilike.{nm}", "select": "id"})
            v["dup_name"] = "pass" if len([s for s in same if s["id"] != drug_id]) == 0 else "FAIL"
        # brand implies approved
        row = preview or (client.select("drugs", {"id": f"eq.{drug_id}", "select": "brand_name,stage"}) or [{}])[0]
        if row.get("brand_name") and (row.get("stage") or "").lower() not in APPROVED_STAGES:
            v["brand_implies_approved"] = "FAIL"
        else:
            v["brand_implies_approved"] = "pass"
        return v


if __name__ == "__main__":
    # smoke test (dry run, no writes)
    w = DrugWriter(dry_run=True)
    print("dry-run upsert SL-325:", w.upsert(
        {"name": "SL-325", "company_id": "shattucklabs", "stage": "Phase 1", "target": "DR3"},
        source={"url": "https://clinicaltrials.gov/study/NCT07158437", "type": "ct_gov"}))
    print("governance reject (brand+phase1):", w.upsert(
        {"name": "FakeDrug", "company_id": "x", "stage": "Phase 1", "brand_name": "Madeup"},
        source={"url": "https://x"}))
