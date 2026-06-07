"""
Node: generate_deals
Discovers and logs new deal records from recent intel (Step 6).

Delegates to step6_deal_intelligence() in company_enrichment.py via a lazy
import.  step6 is kept in company_enrichment.py for now.
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


def generate_deals(state: PipelineState) -> PipelineState:
    """
    Scans state.ctx.recent_intel for new financing, partnering, or BD events
    and creates deal records in Supabase.  Idempotent — skips duplicates by
    headline signature.

    Populates state.deals_created.
    """
    ce = _ce()
    state.deals_created = ce.step6_deal_intelligence(
        state.company_id,
        state.area_id,
        state.ctx.as_dict(),
        state.company_map,
        state.dry_run,
        resolver=state.resolver,
    )
    state.mark_complete("generate_deals")
    return state
