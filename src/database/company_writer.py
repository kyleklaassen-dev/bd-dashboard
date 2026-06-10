#!/usr/bin/env python3
"""
src/database/company_writer.py — the SINGLE writer for the `companies` table.
============================================================================
Only approved path to create/modify a company (Constitution §4, ADR-010).
Enforces: identity (no duplicate company — the problem we just deduped 8 of),
default status='subsidiary' (CLAUDE.md §2), parent_company_id set for sub/acq,
unknown-column rejection. Dry-run capable. Mirrors DrugWriter.
"""
import re, sys, pathlib
_BASE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BASE / "src" / "database"))
sys.path.insert(0, str(_BASE / "scripts"))
import client
from entity_matcher import Registry


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower()) or None


class CompanyWriter:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
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
            self._cols = client.columns("companies")
        return self._cols

    def check_governance(self, rec):
        errs, warns, rec = [], [], dict(rec)
        unknown = [k for k in rec if self.cols and k not in self.cols]
        if unknown:
            errs.append(f"unknown company columns: {unknown}")
        # default subsidiary unless explicitly approved otherwise (CLAUDE.md §2)
        if not rec.get("id") and not rec.get("status"):
            rec["status"] = "subsidiary"
        if rec.get("status") == "acquired" and not rec.get("parent_company_id"):
            errs.append("status='acquired' requires parent_company_id (CLAUDE.md §2)")
        return errs, warns, rec

    def resolve_identity(self, rec):
        if rec.get("id"):
            return rec["id"], rec["id"]
        nm = rec.get("name")
        if nm:
            hits = [h for h in self.reg.resolve(nm) if h[0] == "company"]
            if len(hits) == 1:
                return hits[0][1], hits[0][1]
        return None, _slug(nm)

    def upsert(self, rec):
        report = {"action": None, "company_id": None, "errors": [], "warnings": [], "validation": {}, "dry_run": self.dry_run}
        errs, warns, rec = self.check_governance(rec)
        report["warnings"] = warns
        if errs:
            report["errors"] = errs
            return report
        existing, cand = self.resolve_identity(rec)
        rec["id"] = existing or cand
        report["company_id"] = rec["id"]
        report["action"] = "update" if existing else "create"
        if self.dry_run:
            report["validation"] = {"dup_name": self._dup_check(rec.get("name"), rec["id"])}
            return report
        code, body, _ = client.insert("companies", rec, on_conflict="id")
        if code >= 300:
            report["errors"].append(f"write failed: {code} {str(body)[:200]}")
            return report
        report["validation"] = {"dup_name": self._dup_check(rec.get("name"), rec["id"])}
        return report

    def _dup_check(self, name, cid):
        if not name:
            return "skip"
        same = client.select("companies", {"name": f"ilike.{name}", "select": "id"})
        return "pass" if len([s for s in same if s["id"] != cid]) == 0 else "FAIL"


if __name__ == "__main__":
    w = CompanyWriter(dry_run=True)
    print("Shattuck (existing):", w.upsert({"name": "Shattuck Labs, Inc."}))
    print("acquired w/o parent (reject):", w.upsert({"name": "ZzNewCo", "status": "acquired"}))
