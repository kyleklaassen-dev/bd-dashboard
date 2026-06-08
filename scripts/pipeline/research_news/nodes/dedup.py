"""
Node: dedup
Phase 3 — drops articles whose source_url already exists in `intel` (last 7 days).
"""
from __future__ import annotations

import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_PIPELINE = os.path.dirname(os.path.dirname(_HERE))
_SCRIPTS  = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _common import log  # noqa: E402
from ..state import ResearchNewsState  # noqa: E402


def _research():
    import intelligence.research as research  # noqa: PLC0415
    return research


def run(state: ResearchNewsState) -> ResearchNewsState:
    r = _research()
    state.existing_urls = r.get_existing_urls()
    state.new_articles = [a for a in state.relevant if a["url"] not in state.existing_urls]
    log(f"New (not in Supabase): {len(state.new_articles)} articles")
    state.mark_complete("dedup")
    return state
