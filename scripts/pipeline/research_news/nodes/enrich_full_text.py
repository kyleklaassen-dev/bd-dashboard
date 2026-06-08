"""
Node: enrich_full_text
Phase 4 — fetches full article body text for high-priority new articles
(mutates state.new_articles entries in place, tagging them with 'full_text').
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
    r.enrich_with_full_text(state.new_articles, max_fetches=15)
    state.mark_complete("enrich_full_text")
    return state
