"""
Daily Meridian Issue writer LangGraph pipeline (intelligence/write_meridian.py).

Graph topology
──────────────
  START
    │
  load_context
    │
  build_blocks ──[no intel]────────► placeholder ──┐
    │                                              │
  generate_plan                                    │
    │                                              │
  generate_draft                                   │
    │                                              │
    └──────────────────► publish ◄─────────────────┘
                            │
                          wrapup
                            │
                           END

`build_blocks` replaces the original `if not intel: <placeholder> else: generate_html(...)`
branch with an explicit conditional edge — both paths converge on `publish` so the
Issue is always saved + deployed before the best-effort wrap-up steps run.
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

from .state import MeridianState  # noqa: E402
from .nodes import (  # noqa: E402
    load_context,
    build_blocks,
    placeholder,
    generate_plan,
    generate_draft,
    publish,
    wrapup,
)


# ── Routing conditions ────────────────────────────────────────────────────────

def _route_after_blocks(state: MeridianState) -> Literal["generate_plan", "placeholder"]:
    return "generate_plan" if state.intel else "placeholder"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_write_meridian_graph(checkpointing: bool = False):
    """Build and compile the daily Meridian Issue writer LangGraph application."""
    g = StateGraph(MeridianState)

    g.add_node("load_context",   load_context.run)
    g.add_node("build_blocks",   build_blocks.run)
    g.add_node("placeholder",    placeholder.run)
    g.add_node("generate_plan",  generate_plan.run)
    g.add_node("generate_draft", generate_draft.run)
    g.add_node("publish",        publish.run)
    g.add_node("wrapup",         wrapup.run)

    g.add_edge(START, "load_context")
    g.add_edge("load_context", "build_blocks")
    g.add_conditional_edges("build_blocks", _route_after_blocks,
                            {"generate_plan": "generate_plan", "placeholder": "placeholder"})
    g.add_edge("generate_plan",  "generate_draft")
    g.add_edge("generate_draft", "publish")
    g.add_edge("placeholder",    "publish")
    g.add_edge("publish", "wrapup")
    g.add_edge("wrapup",  END)

    if checkpointing:
        from langgraph.checkpoint.memory import MemorySaver
        return g.compile(checkpointer=MemorySaver())

    return g.compile()
