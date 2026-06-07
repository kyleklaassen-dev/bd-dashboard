"""
Node: generate_catalysts
Auto-creates catalyst records from CT.gov trial primary completion dates (Step 4).
"""
from __future__ import annotations

import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_PIPELINE = os.path.dirname(_HERE)
_SCRIPTS  = os.path.dirname(_PIPELINE)
_ENRICH   = os.path.join(_SCRIPTS, "enrichment")
for _p in (_SCRIPTS, _ENRICH):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pipeline.state import PipelineState  # noqa: E402


def _ce():
    import company_enrichment  # noqa: PLC0415
    return company_enrichment


def generate_catalysts(state: PipelineState) -> PipelineState:
    """
    For each trial with a future primary_completion_date, creates an upcoming
    catalyst record.  Idempotent — skips duplicates by drug × date.
    Populates state.catalysts_generated.
    """
    ce = _ce()
    state.catalysts_generated = ce.step4_generate_catalysts_from_trials(
        state.company_id,
        state.area_id,
        state.ctx.as_dict(),
        state.dry_run,
    )
    state.mark_complete("generate_catalysts")
    return state
