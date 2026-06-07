"""
Drug intelligence researcher LangGraph pipeline.

Graph topology (linear — no conditional branches needed):
  load_drug → research_domains → extract_benchmarks → extract_timeline

Each node can fail independently; errors are accumulated in state.errors
rather than raising. The graph always runs to completion.
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END

from .state import DrugIntelPipelineState
from .nodes import load_drug, research_domains, extract_benchmarks, extract_timeline


def _route_after_load(state: DrugIntelPipelineState):
    """Skip all LLM nodes if drug lookup failed."""
    return "research_domains" if state.ok else END


def build_drug_intel_graph():
    """Build and compile the drug intelligence LangGraph application."""
    g = StateGraph(DrugIntelPipelineState)

    g.add_node("load_drug",          load_drug.run)
    g.add_node("research_domains",   research_domains.run)
    g.add_node("extract_benchmarks", extract_benchmarks.run)
    g.add_node("extract_timeline",   extract_timeline.run)

    g.set_entry_point("load_drug")
    g.add_conditional_edges("load_drug", _route_after_load,
                            {"research_domains": "research_domains", END: END})
    g.add_edge("research_domains",   "extract_benchmarks")
    g.add_edge("extract_benchmarks", "extract_timeline")
    g.add_edge("extract_timeline",   END)

    return g.compile()
