"""
Node: score_completeness
Computes the post-enrichment completeness score and patches company_profiles.
"""
from __future__ import annotations

import datetime
import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_PIPELINE = os.path.dirname(_HERE)
_SCRIPTS  = os.path.dirname(_PIPELINE)
_ENRICH   = os.path.join(_SCRIPTS, "enrichment")
for _p in (_SCRIPTS, _ENRICH):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _common import log          # noqa: E402
from _db import sb_patch         # noqa: E402
from pipeline.state import PipelineState  # noqa: E402


def _ce():
    import company_enrichment  # noqa: PLC0415
    return company_enrichment


def score_completeness(state: PipelineState) -> PipelineState:
    """
    Merges newly-written data with pre-enrichment context to compute a
    completeness score (0–100) and tier, without an extra DB round-trip.

    Patches company_profiles with:
      completeness_score, missing_fields, completeness_checked_at

    Populates state.completeness_score, .completeness_tier, .completeness_missing.
    """
    ce = _ce()
    cs = ce._score_company_completeness(
        state.company_id,
        state.area_id,
        state.validated_data,
        state.ctx.as_dict(),
    )
    state.completeness_score   = cs["score"]
    state.completeness_tier    = cs["tier"]
    state.completeness_missing = cs["missing"]

    if not state.dry_run:
        ok = sb_patch(
            "company_profiles",
            {
                "completeness_score":      state.completeness_score,
                "missing_fields":          state.completeness_missing,
                "completeness_checked_at": datetime.datetime.utcnow().isoformat(),
            },
            {
                "company_id": f"eq.{state.company_id}",
                "area_id":    f"eq.{state.area_id}",
            },
        )
        if not ok:
            log("  ⚠ completeness score patch failed — profile row may not exist yet", indent=1)

    state.mark_complete("score_completeness")
    return state
