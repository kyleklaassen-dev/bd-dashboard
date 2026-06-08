"""
Node: filter_relevant
Phase 2 — keeps articles matching focus-area keywords (or direct-source passthrough).
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
    state.relevant = r.filter_relevant(state.articles)
    state.mark_complete("filter_relevant")
    return state
