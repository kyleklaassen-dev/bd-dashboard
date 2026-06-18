#!/usr/bin/env python3
"""
Characterization tests for the pure functions exposed by the §3 module splits.

These are the FIRST tests to cash in the testability the splits unlocked: small,
fast, no DB / no network / no LLM. They lock in current behavior so future edits to
the split modules can't silently regress it. Run: `python tests/unit/test_pure_functions.py`
(exits non-zero on any failure, so CI can gate on it).

NOTE: the split common.py modules now read credentials fail-soft (env → repo-root file
→ "", never raises — ROADMAP §B), so these imports no longer need a dummy-env shim. A
pure function imports clean with no secrets, which is the whole point.
"""
import os
import sys
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from meridian.enrichment.company.common import normalize_area_id
from meridian.enrichment.company.prompts import build_step5_prompt
from meridian.enrichment.company.resolve import resolve_company_id
from meridian.enrichment.company.catalysts import _parse_sort_date
from meridian.enrichment.company.deals import _deal_signature
from meridian.ingestion.ctgov.map import parse_ct_study, _format_date_label, score_search_match
from meridian.ingestion.ctgov.validate import validate_drug_field_consistency
from meridian.products.narrative.common import recipe_hash
from meridian.scoring.acquisition.scoring import _bd_rating, _days_until, _is_bispecific
from meridian.scoring.research_intel.scoring import score_entity_completeness


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


def test_format_date_label():
    assert _format_date_label("2026-04") == "Apr 2026"      # year-month
    assert _format_date_label("2026-01-15") == "Jan 2026"   # full date → month-year
    assert _format_date_label("") == ""                     # empty → empty


def test_build_step5_prompt_shape():
    ctx = {"company": {"name": "Spyre", "ticker": "SYRE"}, "profile": {}, "ailux_pos": {},
           "drugs": [], "trials": [], "catalysts": [], "deals": [], "recent_intel": []}
    p = build_step5_prompt("spyre", "tl1a", ctx)
    assert isinstance(p, str)
    assert "Spyre" in p                  # company name interpolated
    assert "company_profile" in p        # the required output schema is present


def test_score_entity_completeness_returns_tier():
    ctx = {"entity": {"name": "X"}, "company": {}, "trials": [], "catalysts": [], "deals": [],
           "drugs": [{"id": "d1", "mechanism": "m", "stage": "Phase 2", "drug_summary": "s"}]}
    r = score_entity_completeness(ctx)
    assert "completeness_score" in r and isinstance(r["completeness_score"], (int, float))
    assert r["completeness_tier"] in ("thin", "partial", "strong")


def test_resolve_company_id():
    cmap = {"eli lilly": "lilly", "roche": "roche", "spyre therapeutics": "spyre"}
    assert resolve_company_id("Roche", cmap) == "roche"                       # exact (case-fold)
    assert resolve_company_id("Spyre Therapeutics (TL1A mono)", cmap) == "spyre"  # parenthetical strip
    assert resolve_company_id("Nonexistent Biotech XYZ", cmap) is None        # no ghost match


def test_parse_sort_date():
    assert _parse_sort_date("2026-05-15") == "2026-05-15"   # ISO prefix
    assert _parse_sort_date("Apr 2026") == "2026-04-01"     # Mon YYYY → 1st
    assert _parse_sort_date("Q3 2026") == "2026-07-01"      # quarter → quarter-start
    assert _parse_sort_date("2026") == "2026-06-01"         # bare year → mid-year
    assert _parse_sort_date("sometime") is None             # unparseable → None


def test_deal_signature_normalizes():
    # case / punctuation / whitespace variants collapse to one dedupe key
    a = _deal_signature("AbbVie licenses TL1A from FutureGen")
    b = _deal_signature("abbvie  LICENSES tl1a from futuregen!")
    assert a == b and a != ""


def test_recipe_hash_order_independent():
    assert recipe_hash({"a": 1, "b": 2}) == recipe_hash({"b": 2, "a": 1})     # key order irrelevant
    assert recipe_hash({"a": 1}) != recipe_hash({"a": 2})                     # content-sensitive


def _study(title="", interventions=(), status="RECRUITING", conditions=(), sponsor="", phases=None):
    """Build a minimal CT.gov v2 protocolSection for the match/parse functions."""
    proto = {
        "identificationModule": {"nctId": "NCT00000000", "briefTitle": title},
        "statusModule": {"overallStatus": status},
        "conditionsModule": {"conditions": list(conditions)},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": sponsor}},
        "armsInterventionsModule": {"interventions": [{"name": n} for n in interventions]},
    }
    if phases is not None:
        proto["designModule"] = {"phases": phases}
    return {"protocolSection": proto}


def test_score_search_match_hard_gate():
    # The verekitug/APG777 governance lesson: a trial that names a DIFFERENT compound
    # must hard-zero, never accumulate partial credit from sponsor/indication overlap.
    study = _study(title="A study of someotherdrug in colitis",
                   interventions=["someotherdrug"], sponsor="ourdrug pharma",
                   conditions=["ulcerative colitis"])
    assert score_search_match(study, "d1", "ourdrug", "ulcerative colitis") == 0


def test_score_search_match_strong_match():
    # Drug named in BOTH title and interventions → +50 +30 = 80, recruiting (no penalty).
    study = _study(title="Phase 2 study of ourdrug", interventions=["ourdrug"])
    assert score_search_match(study, "d1", "ourdrug") == 80


def test_score_search_match_terminated_penalty():
    # Same strong match but TERMINATED → −20 penalty applied to the 80.
    study = _study(title="Phase 2 study of ourdrug", interventions=["ourdrug"],
                   status="TERMINATED")
    assert score_search_match(study, "d1", "ourdrug") == 60


def test_parse_ct_study_multiphase_combine():
    rec = parse_ct_study(_study(title="t", phases=["PHASE1", "PHASE2"]), "d1")
    assert rec["phase"] == "Phase 1/Phase 2"          # mapped parts joined on "/"


def test_parse_ct_study_no_phase_is_na():
    rec = parse_ct_study(_study(title="t", phases=[]), "d1")
    assert rec["phase"] == "N/A"                       # empty phases → N/A sentinel


def test_is_bispecific():
    assert _is_bispecific({"drug_format": "bispecific antibody"}) is True
    assert _is_bispecific({"name": "TL1A × IL-23 bispecific", "drug_format": ""}) is True   # × in name
    assert _is_bispecific({"drug_format": "mAb", "modality": "antibody"}) is False           # plain monospecific


def test_validate_field_consistency_clean_bispecific():
    # consistent: bispecific target + bispecific format → no warnings
    d = {"id": "ailux", "target": "TL1A × IL-23", "drug_format": "bispecific", "mechanism": "TL1A×IL-23 bispecific"}
    assert validate_drug_field_consistency(d) == []


def test_validate_field_consistency_flags_target_format_conflict():
    # target implies bispecific (×) but format says mAb (monospecific) → exactly one conflict
    d = {"id": "x", "target": "TL1A × IL-23", "drug_format": "mAb", "mechanism": ""}
    w = validate_drug_field_consistency(d)
    assert len(w) == 1 and "field_conflict" in w[0] and "monospecific" in w[0]


def test_validate_field_consistency_flags_format_without_separator():
    # format says bispecific but target has no separator → flagged as possibly-incomplete target
    d = {"id": "x", "target": "TL1A", "drug_format": "bispecific", "mechanism": ""}
    w = validate_drug_field_consistency(d)
    assert any("no bispecific separator" in s for s in w)


def test_validate_field_consistency_combo_is_exempt():
    # combination drugs intentionally mix fields → early-return, no warnings
    d = {"id": "x", "target": "TL1A × IL-23", "drug_format": "mAb", "is_combo": True}
    assert validate_drug_field_consistency(d) == []


def test_validate_field_consistency_separator_variants():
    # the validator recognizes ×, /, spaced " x ", and compact AxB as bispecific separators
    for tgt in ["CD19xCD3", "CD5 x CD3", "IL-4Ra/TSLP", "TL1A × IL-23"]:
        d = {"id": "x", "target": tgt, "drug_format": "bispecific", "mechanism": ""}
        assert validate_drug_field_consistency(d) == [], f"{tgt!r} should read as bispecific (no conflict)"


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
