"""
Drug enrichment LangGraph pipeline.

Graph topology:
  load_context → [skip if coverage ≥ 80%] → synthesize → validate → write → log_run

Conditional skip: if the drug is already well-enriched (coverage ≥ 80),
the pipeline exits after load_context without calling Claude.
"""
from __future__ import annotations

import time
from typing import Literal

from langgraph.graph import StateGraph, END

from .state import DrugPipelineState
from .nodes import load_context, synthesize, validate, write, log_run

_COVERAGE_THRESHOLD = 80


def _route_after_load(state: DrugPipelineState) -> Literal["synthesize", "__end__"]:
    """Skip Claude if drug is already well-enriched."""
    if not state.ok:
        return END
    if state.coverage >= _COVERAGE_THRESHOLD:
        from _common import log
        log(f"  Already well-enriched (coverage={state.coverage}%) — skipping", indent=1)
        return END
    return "synthesize"


def _route_after_synth(state: DrugPipelineState) -> Literal["validate", "__end__"]:
    """Abort if LLM call failed."""
    return "validate" if state.ok else END


def _timed_load(state: DrugPipelineState) -> DrugPipelineState:
    return load_context.run(state)


def _timed_synth(state: DrugPipelineState) -> DrugPipelineState:
    return synthesize.run(state)


def _timed_validate(state: DrugPipelineState) -> DrugPipelineState:
    return validate.run(state)


def _timed_write(state: DrugPipelineState) -> DrugPipelineState:
    return write.run(state)


def _timed_log(state: DrugPipelineState) -> DrugPipelineState:
    return log_run.run(state)


def build_drug_graph():
    """Build and compile the drug enrichment LangGraph application."""
    g = StateGraph(DrugPipelineState)

    g.add_node("load_context",  _timed_load)
    g.add_node("synthesize",    _timed_synth)
    g.add_node("validate",      _timed_validate)
    g.add_node("write",         _timed_write)
    g.add_node("log_run",       _timed_log)

    g.set_entry_point("load_context")
    g.add_conditional_edges("load_context", _route_after_load,
                            {"synthesize": "synthesize", END: END})
    g.add_conditional_edges("synthesize",   _route_after_synth,
                            {"validate": "validate", END: END})
    g.add_edge("validate", "write")
    g.add_edge("write",    "log_run")
    g.add_edge("log_run",  END)

    return g.compile()
