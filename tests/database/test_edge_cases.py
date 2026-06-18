#!/usr/bin/env python3
"""Edge-case regression tests (§A.5) — real identity/governance scenarios from
Meridian's history. Read-only against the live DB. These lock in CORRECT behavior
for the cases that have bitten the platform before.

Run:  PYTHONPATH=src python3 tests/database/test_edge_cases.py
"""
import sys, pathlib
_BASE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BASE / "src" / "meridian" / "database"))
import client  # noqa: E402

PASS, FAIL = [], []
def check(n, c):
    (PASS if c else FAIL).append(n)
    print(("  ok   " if c else "  FAIL ") + n)


def test_tulisokibart_canonical_identity():
    """tulisokibart = MK-7240 (Merck code) = PRA-023 (Prometheus code): ONE drug, not three.
    Originator is Prometheus — company_id must be the ORIGINATOR, never Merck (the acquirer)."""
    rows = client.select("drugs", {"id": "eq.tulisokibart", "select": "id,company_id,aliases"})
    check("tulisokibart exists as one canonical drug", len(rows) == 1)
    if rows:
        d = rows[0]
        aliases = [str(a).lower() for a in (d.get("aliases") or [])]
        check("  └ aliases include MK-7240 (Merck code) — not a separate record",
              any("mk-7240" in a for a in aliases))
        check("  └ company_id = prometheus (ORIGINATOR, not Merck the acquirer)",
              d.get("company_id") == "prometheus")
    dup = client.select("drugs", {"id": "eq.mk-7240", "select": "id"})
    check("no separate 'mk-7240' drug row (it is an alias, not a duplicate)", len(dup) == 0)


def test_vtx002_identity():
    """VTX002 (Ventyx S1P modulator) — clean canonical record, correct originator."""
    rows = client.select("drugs", {"id": "eq.vtx002", "select": "id,company_id,target"})
    check("VTX002 exists and is owned by Ventyx",
          len(rows) == 1 and rows[0].get("company_id") == "ventyx")


def test_telavant_roche_acquisition():
    """Roche acquired Telavant (TL1A asset, 2023). Telavant must be modeled as
    status='acquired' (provably dissolved) — NOT deleted, NOT relabeled as Roche.
    Roche remains a separate, active company. (company_id=originator rule.)"""
    tel = client.select("companies", {"id": "eq.telavant", "select": "id,status"})
    roche = client.select("companies", {"id": "eq.roche", "select": "id,status"})
    check("Telavant modeled as status=acquired (acquisition captured, not deleted)",
          bool(tel) and tel[0].get("status") == "acquired")
    check("Roche exists as a separate active company (acquirer != originator)",
          bool(roche) and roche[0].get("status") == "active")


def test_lbl053_tl1a_bispecific_competitor():
    """LBL-053 (Nanjing Leads) — a TL1A × IL-23 bispecific, a DIRECT Ailux competitor.
    Must be captured with the bispecific target and the right originator."""
    rows = client.select("drugs", {"id": "eq.lbl053", "select": "id,company_id,target"})
    check("LBL-053 exists and is owned by Leads", len(rows) == 1 and rows[0].get("company_id") == "leads")
    if rows:
        tgt = (rows[0].get("target") or "").lower()
        check("  └ target reflects a TL1A bispecific (TL1A + IL-23)",
              "tl1a" in tgt and ("23" in tgt))


if __name__ == "__main__":
    print("Edge-case regression suite (read-only, live DB):")
    for t in (test_tulisokibart_canonical_identity, test_vtx002_identity,
              test_telavant_roche_acquisition, test_lbl053_tl1a_bispecific_competitor):
        try:
            t()
        except Exception as e:
            FAIL.append(t.__name__)
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
