"""
Node: write_enrichment
Writes the validated enrichment data to Supabase (Step 5 write phase).

Delegates to write_step5() in company_enrichment.py via a lazy import.
write_step5 is ~930 lines covering 15 tables — it is intentionally kept in
company_enrichment.py until a dedicated refactor can safely extract it.
"""
from __future__ import annotations

import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_PIPELINE = os.path.dirname(_HERE)
_SCRIPTS  = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from pipeline.state import PipelineState  # noqa: E402


def _ce():
    import company_enrichment  # noqa: PLC0415
    return company_enrichment


def write_enrichment(state: PipelineState) -> PipelineState:
    """
    Calls write_step5() with the validated enrichment data.

    Writes to: company_profiles, drugs, catalysts, deals, company_areas,
    drug_areas, drug_indications, drug_targets, and related tables.
    """
    ce = _ce()
    ce.write_step5(
        state.company_id,
        state.area_id,
        state.validated_data,
        state.ctx.as_dict(),
        state.dry_run,
        enrichment_run_id=state.enrichment_run_id,
    )
    state.mark_complete("write_enrichment")
    return state
