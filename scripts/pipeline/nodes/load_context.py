"""
Node: load_context
Fetches all Supabase data for a company × area and populates state.ctx.
"""
from __future__ import annotations

import os
import sys

# Ensure scripts/ and scripts/enrichment/ are on the path for standalone testing.
_HERE        = os.path.dirname(os.path.abspath(__file__))
_PIPELINE    = os.path.dirname(_HERE)
_SCRIPTS     = os.path.dirname(_PIPELINE)
_ENRICH      = os.path.join(_SCRIPTS, "enrichment")
for _p in (_SCRIPTS, _ENRICH):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pipeline.state import CompanyContext, PipelineState  # noqa: E402


def _ce():
    """Lazy import of company_enrichment to avoid circular deps at module load."""
    import company_enrichment  # noqa: PLC0415
    return company_enrichment


def load_context(state: PipelineState) -> PipelineState:
    """
    Fetch company, profile, drugs, trials, catalysts, deals, and recent intel
    from Supabase.  Optionally pre-syncs missing trials from CT.gov unless
    state.skip_trial_refresh is set.
    """
    ce = _ce()
    raw = ce.fetch_company_context(
        state.company_id,
        state.area_id,
        skip_trial_refresh=state.skip_trial_refresh,
    )
    state.ctx = CompanyContext(
        company=raw.get("company", {}),
        profile=raw.get("profile", {}),
        drugs=raw.get("drugs", []),
        trials=raw.get("trials", []),
        catalysts=raw.get("catalysts", []),
        deals=raw.get("deals", []),
        recent_intel=raw.get("recent_intel", []),
        ailux_pos=raw.get("ailux_pos", {}),
    )
    state.mark_complete("load_context")
    return state
