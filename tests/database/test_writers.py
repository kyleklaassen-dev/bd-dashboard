#!/usr/bin/env python3
"""Regression tests for CompanyWriter + EdgeWriter (read-only / dry-run)."""
import sys, pathlib
_BASE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BASE / "src" / "meridian" / "database"))
sys.path.insert(0, str(_BASE / "src" / "meridian" / "identity"))
from company_writer import CompanyWriter
from edge_writer import EdgeWriter
from catalyst_writer import CatalystWriter

PASS, FAIL = [], []
def check(n, c): (PASS if c else FAIL).append(n); print(("  ok  " if c else "  FAIL ") + n)


def test_company_identity():
    r = CompanyWriter(dry_run=True).upsert({"name": "Shattuck Labs, Inc."})
    check("Shattuck resolves to existing (no dup)", r["company_id"] == "shattucklabs" and r["action"] == "update")

def test_company_acquired_needs_parent():
    r = CompanyWriter(dry_run=True).upsert({"name": "ZzNewCo", "status": "acquired"})
    check("acquired without parent rejected", any("parent_company_id" in e for e in r["errors"]))

def test_edge_valid():
    r = EdgeWriter(dry_run=True).write({"subject_type": "drug", "subject_id": "sl325", "predicate": "TARGETS",
                                        "object_type": "target", "object_id": "dr3"})
    check("valid edge accepted", r["would_write"] == 1 and not r["rejected"])

def test_edge_bad_predicate():
    r = EdgeWriter(dry_run=True).write({"subject_type": "drug", "subject_id": "sl325", "predicate": "FOO",
                                        "object_type": "target", "object_id": "dr3"})
    check("bad predicate rejected", len(r["rejected"]) == 1)

def test_edge_missing_endpoint():
    r = EdgeWriter(dry_run=True).write({"subject_type": "drug", "subject_id": "nope999", "predicate": "TARGETS",
                                        "object_type": "target", "object_id": "dr3"})
    check("missing endpoint rejected", len(r["rejected"]) == 1)


def test_catalyst_valid():
    r = CatalystWriter(dry_run=True).upsert({"drug_id": "sl325", "label": "Ph2b readout", "catalyst_date": "2028-06-30"})
    check("valid catalyst accepted", not r["errors"])

def test_catalyst_needs_anchor():
    r = CatalystWriter(dry_run=True).upsert({"label": "orphan", "catalyst_date": "2027-01-01"})
    check("catalyst without an anchor rejected", any("anchor" in e for e in r["errors"]))

def test_catalyst_needs_date():
    r = CatalystWriter(dry_run=True).upsert({"drug_id": "sl325", "label": "no date"})
    check("catalyst without date rejected", any("date" in e for e in r["errors"]))


if __name__ == "__main__":
    print("Writer regression suite (read-only / dry-run):")
    for fn in [test_company_identity, test_company_acquired_needs_parent, test_edge_valid,
               test_edge_bad_predicate, test_edge_missing_endpoint,
               test_catalyst_valid, test_catalyst_needs_anchor, test_catalyst_needs_date]:
        try: fn()
        except Exception as e: FAIL.append(fn.__name__); print(f"  ERROR {fn.__name__}: {e}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
