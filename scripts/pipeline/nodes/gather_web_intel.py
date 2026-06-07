"""
Node: gather_web_intel
Phase A of Step 5 — runs 4 live web searches via Claude to collect clinical data,
financing, BD activity, and catalyst timing for the company.
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


def gather_web_intel(state: PipelineState) -> PipelineState:
    """
    Calls gather_web_intelligence() to produce a structured text block
    that is injected into the Phase B synthesis prompt.
    Returns empty string on any failure — Phase B continues without it.
    Populates state.web_intel.
    """
    ce = _ce()
    co = state.ctx.company
    state.web_intel = ce.gather_web_intelligence(
        company_name=co.get("name", state.company_id),
        area_id=state.area_id,
        drugs=state.ctx.drugs,
        ticker=co.get("ticker", ""),
    )
    state.mark_complete("gather_web_intel")
    return state
