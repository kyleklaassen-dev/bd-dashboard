#!/usr/bin/env python3
"""
src/database/catalyst_writer.py — the SINGLE writer for the `catalysts` table.
=============================================================================
Only approved path to create/modify a catalyst (Constitution §4, ADR-010).
Enforces: must link to a drug or company; a date is present; dedup on
(drug_id|company_id, label, catalyst_date); unknown-column rejection. Dry-run
capable. Mirrors DrugWriter/CompanyWriter.
"""
import sys, pathlib
_BASE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BASE / "src" / "database"))
import client


class CatalystWriter:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self._cols = None

    @property
    def cols(self):
        if self._cols is None:
            self._cols = client.columns("catalysts")
        return self._cols

    def check_governance(self, rec):
        errs, rec = [], dict(rec)
        unknown = [k for k in rec if self.cols and k not in self.cols]
        if unknown:
            errs.append(f"unknown catalyst columns: {unknown}")
        if not rec.get("drug_id") and not rec.get("company_id") and not rec.get("id"):
            errs.append("catalyst must link to a drug_id or company_id (Governance Table)")
        if not rec.get("catalyst_date") and not rec.get("sort_date") and not rec.get("id"):
            errs.append("catalyst requires a date (catalyst_date/sort_date)")
        return errs, rec

    def _find_existing(self, rec):
        """Dedup on (anchor, label, date)."""
        anchor_col = "drug_id" if rec.get("drug_id") else "company_id" if rec.get("company_id") else None
        if not anchor_col or not rec.get("label"):
            return None
        params = {anchor_col: f"eq.{rec[anchor_col]}", "label": f"eq.{rec['label']}", "select": "id"}
        if rec.get("catalyst_date"):
            params["catalyst_date"] = f"eq.{rec['catalyst_date']}"
        hits = client.select("catalysts", params)
        return hits[0]["id"] if hits else None

    def upsert(self, rec):
        report = {"action": None, "catalyst_id": None, "errors": [], "dry_run": self.dry_run}
        errs, rec = self.check_governance(rec)
        if errs:
            report["errors"] = errs
            return report
        existing = rec.get("id") or self._find_existing(rec)
        report["action"] = "update" if existing else "create"
        if existing:
            rec["id"] = existing
        if self.dry_run:
            report["catalyst_id"] = existing or "(new)"
            return report
        if existing:
            code, body, _ = client.update("catalysts", f"id=eq.{existing}", {k: v for k, v in rec.items() if k != "id"})
            report["catalyst_id"] = existing
        else:
            code, body, _ = client.insert("catalysts", rec, return_rep=True)
            if code < 300 and isinstance(body, list) and body:
                report["catalyst_id"] = body[0].get("id")
        if code >= 300:
            report["errors"].append(f"write failed: {code} {str(body)[:160]}")
        return report


if __name__ == "__main__":
    w = CatalystWriter(dry_run=True)
    print("valid:", w.upsert({"drug_id": "sl325", "label": "RECEPTIVE-CD1 Ph2b readout", "catalyst_date": "2028-06-30"}))
    print("no anchor (reject):", w.upsert({"label": "orphan catalyst", "catalyst_date": "2027-01-01"}))
    print("no date (reject):", w.upsert({"drug_id": "sl325", "label": "no date"}))
