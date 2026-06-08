"""
Node: write_intel
Phase 5b — writes extracted intel/deal/catalyst records to Supabase.
"""
from __future__ import annotations

import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_PIPELINE = os.path.dirname(os.path.dirname(_HERE))
_SCRIPTS  = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from ..state import ResearchNewsState  # noqa: E402


def _research():
    import intelligence.research as research  # noqa: PLC0415
    return research


def run(state: ResearchNewsState) -> ResearchNewsState:
    r = _research()
    r.write_to_supabase(state.intel, company_map=state.company_map, resolver=state.resolver)
    state.mark_complete("write_intel")
    return state
