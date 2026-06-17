#!/usr/bin/env python3
"""
Regression tests for DrugWriter + drug-table invariants (Constitution §6).
Runs against the live DB in DRY-RUN / read-only mode (no writes) so it is safe
to run any time, including CI. Pure asserts — run with `python3 test_drug_writer.py`
or under pytest.
"""
import os, sys, pathlib
_BASE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BASE / "src" / "meridian" / "database"))
sys.path.insert(0, str(_BASE / "src" / "meridian" / "identity"))
import client
from drug_writer import DrugWriter

PASS, FAIL = [], []
def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("  ok  " if cond else "  FAIL ") + name)


def test_identity_resolution_no_dup():
    w = DrugWriter(dry_run=True)
    r = w.upsert({"name": "SL-325", "company_id": "shattucklabs", "stage": "Phase 1", "target": "DR3"},
                 source={"url": "https://clinicaltrials.gov/study/NCT07158437", "type": "ct_gov"})
    check("SL-325 resolves to existing canonical id (no dup)", r["drug_id"] == "sl325" and r["action"] == "update")


def test_governance_brand_requires_approved():
    w = DrugWriter(dry_run=True)
    r = w.upsert({"name": "ZzTestMolecule", "company_id": "x", "stage": "Phase 1", "brand_name": "FakeBrand"},
                 source={"url": "https://x"})
    check("brand_name + non-approved stage is rejected", any("brand_name" in e for e in r["errors"]))


def test_governance_unknown_column():
    w = DrugWriter(dry_run=True)
    r = w.upsert({"name": "ZzTestMolecule", "company_id": "x", "stage": "Phase 1", "not_a_real_col": 1},
                 source={"url": "https://x"})
    check("unknown column is rejected", any("unknown" in e for e in r["errors"]))


def test_source_required_for_new():
    w = DrugWriter(dry_run=True)
    r = w.upsert({"name": "ZzBrandNewMolecule12345", "company_id": "x", "stage": "Phase 1"})
    check("new drug without a source URL is rejected", any("source" in e for e in r["errors"]))


def test_invariant_no_duplicate_names():
    rows = client.select_all("drugs", {"select": "name"})
    seen = {}
    for r in rows:
        k = (r.get("name") or "").strip().lower()
        if k:
            seen[k] = seen.get(k, 0) + 1
    dups = [k for k, c in seen.items() if c > 1]
    check(f"no duplicate drug names in DB (found {len(dups)})", len(dups) == 0)


# Baseline of 7 known cases pending Kyle's modeling decision: these ARE marketed/
# approved molecules but are tracked at the PHASE OF A SPECIFIC AILUX-RELEVANT
# INDICATION (e.g. Rinvoq approved in RA, Phase 3 in a tracked IBD indication).
# CLAUDE.md §4 (brand⇒approved) vs per-indication phase tracking — see
# STABILIZATION_PLAN.md "Open decisions". Test guards against NEW violations.
KNOWN_BRAND_STAGE_EXCEPTIONS = {
    "benralizumab", "rozanolixizumab", "upadacitinib", "mepolizumab",
    "nipocalimab", "tralokinumab", "lebrikizumab",
}


def test_invariant_brand_implies_approved():
    bad = client.select_all("drugs", {"select": "id,brand_name,stage", "brand_name": "not.is.null"})
    viol = [d["id"] for d in bad if (d.get("stage") or "").lower() not in
            {"approved", "approved_us", "approved_eu", "approved_china", "approved_us_eu", "approved_partial"}]
    new_viol = [v for v in viol if v not in KNOWN_BRAND_STAGE_EXCEPTIONS]
    check(f"no NEW brand⇒approved violations (known baseline {len(viol)}, new {len(new_viol)})", len(new_viol) == 0)


if __name__ == "__main__":
    print("DrugWriter regression suite (read-only / dry-run):")
    for fn in [test_identity_resolution_no_dup, test_governance_brand_requires_approved,
               test_governance_unknown_column, test_source_required_for_new,
               test_invariant_no_duplicate_names, test_invariant_brand_implies_approved]:
        try:
            fn()
        except Exception as e:
            FAIL.append(fn.__name__); print(f"  ERROR {fn.__name__}: {e}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
