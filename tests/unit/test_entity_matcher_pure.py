#!/usr/bin/env python3
"""
Characterization tests for entity_matcher's PURE logic (no DB / no network).

entity_matcher is THE shared resolver — every knowledge-graph builder links
entities through it, so a regression in its normalization mis-attributes facts
across the whole platform. These lock in the current behavior of the suffix
stripper and the curated-alias / stop-word data so a careless edit can't silently
change how names resolve. Run: `python tests/unit/test_entity_matcher_pure.py`
(exits non-zero on any failure, so CI can gate on it).

The DB-backed Registry.resolve() is covered separately by the live writer/edge
suites; this file is the fast, deterministic floor.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from meridian.identity.entity_matcher import _SUFFIX_RE, STOP, CURATED


def _strip(name):
    """One application of the corporate-suffix stripper (as used at build time)."""
    return _SUFFIX_RE.sub("", name)


def test_suffix_stripper_drops_one_trailing_corporate_suffix():
    # captured 2026-06-19 — current behavior is a SINGLE trailing-suffix strip
    assert _strip("Roche Pharmaceuticals") == "Roche"
    assert _strip("Protagonist Therapeutics") == "Protagonist"
    assert _strip("Arena Pharmaceuticals") == "Arena"
    assert _strip("Acme Biosciences") == "Acme"
    assert _strip("Pfizer Inc.") == "Pfizer"
    # comma-suffix form: strips ", Inc." but not the inner token (single pass)
    assert _strip("Shattuck Labs, Inc.") == "Shattuck Labs"


def test_suffix_stripper_leaves_unknown_suffix_untouched():
    # "SE" is not in the suffix list → name unchanged
    assert _strip("argenx SE") == "argenx SE"
    # no suffix at all → unchanged
    assert _strip("Roivant") == "Roivant"


def test_stop_words_block_generic_tokens():
    assert isinstance(STOP, set)
    # generic biotech/clinical words must stay excluded from auto-matching
    for tok in ("phase", "trial", "pharma", "company", "therapeutics", "placebo"):
        assert tok in STOP, f"{tok!r} dropped from STOP — generic token would match"


def test_curated_aliases_pin_known_entities():
    assert CURATED["bms"] == ("company", "bms")
    assert CURATED["bristol myers squibb"] == ("company", "bms")
    assert CURATED["j&j"] == ("company", "jnj")
    assert CURATED["janssen"] == ("company", "jnj")
    # brand -> generic drug id
    assert CURATED["skyrizi"] == ("drug", "risankizumab")
    assert CURATED["rinvoq"] == ("drug", "upadacitinib")


def test_curated_structure_is_well_formed():
    """Every curated value must be (etype, id) with a valid etype — guards typos."""
    for surface, val in CURATED.items():
        assert isinstance(val, tuple) and len(val) == 2, f"{surface!r}: bad shape {val!r}"
        etype, eid = val
        assert etype in ("company", "drug"), f"{surface!r}: bad etype {etype!r}"
        assert isinstance(eid, str) and eid, f"{surface!r}: bad id {eid!r}"
        assert surface == surface.lower(), f"{surface!r}: curated keys must be lowercase"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ok   {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
