"""
Node: fetch_feeds
Phase 1 — pulls articles from the RSS feed list (last `state.hours_back` hours).
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
    state.articles = r.fetch_feeds(hours_back=state.hours_back)
    state.mark_complete("fetch_feeds")
    return state
