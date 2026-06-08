"""
Nightly news-extraction LangGraph pipeline (intelligence/research.py phases 1-5).

Graph topology
──────────────
  START
    │
  fetch_feeds
    │
  filter_relevant ──[no relevant articles]───────────────► END
    │
  dedup ────────────[no new articles]─────────────────────► END
    │
  enrich_full_text
    │
  extract_intel
    │
  write_intel
    │
   END

Conditional routing replaces the original `if not relevant: ... else: ...`
nesting with explicit early-exit edges — each skip is now visible in the
compiled graph topology (and in app.get_graph().draw_mermaid()).
"""
from __future__ import annotations

import os
import sys
from typing import Literal

_HERE    = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(os.path.dirname(_HERE))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from langgraph.graph import END, START, StateGraph  # noqa: E402

from .state import ResearchNewsState  # noqa: E402
from .nodes import (  # noqa: E402
    fetch_feeds,
    filter_relevant,
    dedup,
    enrich_full_text,
    extract_intel,
    write_intel,
)


# ── Routing conditions ────────────────────────────────────────────────────────

def _route_after_filter(state: ResearchNewsState) -> Literal["dedup", "__end__"]:
    if not state.relevant:
        from _common import log
        log("No relevant articles found — done.")
        return END
    return "dedup"


def _route_after_dedup(state: ResearchNewsState) -> Literal["enrich_full_text", "__end__"]:
    return "enrich_full_text" if state.new_articles else END


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_research_news_graph(checkpointing: bool = False):
    """Build and compile the nightly news-extraction LangGraph application."""
    g = StateGraph(ResearchNewsState)

    g.add_node("fetch_feeds",       fetch_feeds.run)
    g.add_node("filter_relevant",   filter_relevant.run)
    g.add_node("dedup",             dedup.run)
    g.add_node("enrich_full_text",  enrich_full_text.run)
    g.add_node("extract_intel",     extract_intel.run)
    g.add_node("write_intel",       write_intel.run)

    g.add_edge(START, "fetch_feeds")
    g.add_edge("fetch_feeds", "filter_relevant")
    g.add_conditional_edges("filter_relevant", _route_after_filter,
                            {"dedup": "dedup", END: END})
    g.add_conditional_edges("dedup", _route_after_dedup,
                            {"enrich_full_text": "enrich_full_text", END: END})
    g.add_edge("enrich_full_text", "extract_intel")
    g.add_edge("extract_intel",    "write_intel")
    g.add_edge("write_intel",      END)

    if checkpointing:
        from langgraph.checkpoint.memory import MemorySaver
        return g.compile(checkpointer=MemorySaver())

    return g.compile()
