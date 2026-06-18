#!/usr/bin/env python3
"""
Characterization tests for the pure functions exposed by the §3 module splits.

These are the FIRST tests to cash in the testability the splits unlocked: small,
fast, no DB / no network / no LLM. They lock in current behavior so future edits to
the split modules can't silently regress it. Run: `python tests/unit/test_pure_functions.py`
(exits non-zero on any failure, so CI can gate on it).

NOTE: several modules still read credentials at import time (os.environ[...]), so we
set dummy env BEFORE importing them. That import-time coupling is itself a testability
debt (see ROADMAP §B) — lazy credential reads would remove the need for this shim.
"""
import os
import sys
import datetime

# dummy env so import-time credential reads don't crash (pure logic doesn't use them)
os.environ.setdefault("ANTHROPIC_API_KEY", "test-dummy")
os.environ.setdefault("SUPABASE_URL", "https://test.dummy")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from meridian.enrichment.company.common import normalize_area_id
from meridian.ingestion.ctgov.map import parse_ct_study
from meridian.scoring.acquisition.scoring import _bd_rating, _days_until


def test_normalize_area_id():
    assert normalize_area_id("tl1a") == "tl1a"
    assert normalize_area_id("TL1A") == "tl1a"          # case-fold
    assert normalize_area_id("tll1a") == "tl1a"         # known typo alias
    assert normalize_area_id("il-4ra") == "il4ra"       # punctuation alias
    assert normalize_area_id("t-cell") == "tcell"
    assert normalize_area_id("bogus") == ""             # unknown → empty (rejected)


def test_bd_rating_bands():
    assert _bd_rating(95) == "CALL NOW"
    assert _bd_rating(80) == "PRIORITY"
    assert _bd_rating(60) == "WATCH"
    assert _bd_rating(40) == "MONITOR"
    assert _bd_rating(10) == "HOLD"


def test_days_until():
    fut = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    assert 28 <= _days_until(fut) <= 31           # ~30 days out (clock-of-day tolerant)
    assert _days_until("not-a-date") == 9999      # unparseable → far-future sentinel


def test_parse_ct_study_maps_status_and_phase():
    study = {"protocolSection": {
        "identificationModule": {"nctId": "NCT12345678", "briefTitle": "Test Study"},
        "statusModule": {"overallStatus": "RECRUITING"},
        "designModule": {"phases": ["PHASE2"]},
    }}
    rec = parse_ct_study(study, "testdrug")
    assert rec["id"] == "NCT12345678"
    assert rec["status"] == "Recruiting"          # CT_STATUS_MAP
    assert rec["phase"] == "Phase 2"              # CT_PHASE_MAP


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    print("Pure-function characterization suite:")
    for t in tests:
        try:
            t()
            print(f"  ok  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    sys.exit(1 if _run() else 0)
