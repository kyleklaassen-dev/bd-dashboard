"""
LangGraph-based enrichment pipeline graph.

Provides the same business logic as orchestrator.run_company_pipeline() but
runs under the LangGraph framework, which adds:

  • Conditional routing  — synthesis failure exits early without running
                           write/score/deals; skip_web_search bypasses the
                           web-search node entirely.

  • Checkpointing        — MemorySaver (in-memory) or any LangGraph
                           CheckpointSaver keeps state at each node boundary
                           so a failed run can be resumed from the last
                           successful node.

  • Graph visualization  — call app.get_graph().draw_mermaid() to get a
                           Mermaid diagram of the pipeline.

Graph topology
──────────────
  START
    │
  load_context
    │
  generate_catalysts
    │
    ├─[skip_web_search=True]─────────────────────┐
    │                                             │
  gather_web_intel                           (skipped)
    │                                             │
    └──────────── synthesize_enrichment ──────────┘
                        │
         ┌──[synth ok?]─┘
         │  yes                  no
  validate_enrichment           END
         │
  write_enrichment
         │
  score_completeness
         │
  generate_deals
         │
        END

Usage
─────
    from pipeline.graph import build_enrichment_graph
    from pipeline.state import PipelineState

    app = build_enrichment_graph()

    state = PipelineState(area_id="tl1a", company_id="abbvie", ...)
    result = app.invoke(state)
    success = not result.get("errors")

    # With checkpointing (resume failed runs):
    app_ckpt = build_enrichment_graph(checkpointing=True)
    config = {"configurable": {"thread_id": "abbvie_tl1a_20260607"}}
    result = app_ckpt.invoke(state, config=config)

    # Mermaid diagram:
    print(app.get_graph().draw_mermaid())
"""
from __future__ import annotations

import os
import sys

_HERE    = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
_ENRICH  = os.path.join(_SCRIPTS, "enrichment")
for _p in (_SCRIPTS, _ENRICH):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from langgraph.graph import END, START, StateGraph  # noqa: E402

from pipeline.state import PipelineState  # noqa: E402


# ── Routing conditions ────────────────────────────────────────────────────────

def _route_web_intel(state: PipelineState) -> str:
    """Skip web search when the flag is set — go straight to synthesis."""
    return "synthesize_enrichment" if state.skip_web_search else "gather_web_intel"


def _route_after_synthesis(state: PipelineState) -> str:
    """Abort the pipeline if Claude synthesis failed."""
    return "validate_enrichment" if state.ok else END


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_enrichment_graph(checkpointing: bool = False):
    """
    Build and compile the LangGraph enrichment pipeline.

    Args:
        checkpointing: When True, attaches a MemorySaver so runs can be
                       resumed from the last successful node by passing the
                       same ``config["configurable"]["thread_id"]``.

    Returns:
        A compiled ``CompiledStateGraph`` that accepts ``PipelineState`` as
        input via ``app.invoke(state)`` or ``app.stream(state)``.
    """
    # Lazy imports so this module can be loaded without anthropic installed.
    from pipeline.nodes.load_context          import load_context
    from pipeline.nodes.generate_catalysts    import generate_catalysts
    from pipeline.nodes.gather_web_intel      import gather_web_intel
    from pipeline.nodes.synthesize_enrichment import synthesize_enrichment
    from pipeline.nodes.validate_enrichment   import validate_enrichment
    from pipeline.nodes.write_enrichment      import write_enrichment
    from pipeline.nodes.score_completeness    import score_completeness
    from pipeline.nodes.generate_deals        import generate_deals

    graph = StateGraph(PipelineState)

    # ── Register nodes ────────────────────────────────────────────────────
    graph.add_node("load_context",          load_context)
    graph.add_node("generate_catalysts",    generate_catalysts)
    graph.add_node("gather_web_intel",      gather_web_intel)
    graph.add_node("synthesize_enrichment", synthesize_enrichment)
    graph.add_node("validate_enrichment",   validate_enrichment)
    graph.add_node("write_enrichment",      write_enrichment)
    graph.add_node("score_completeness",    score_completeness)
    graph.add_node("generate_deals",        generate_deals)

    # ── Edges ─────────────────────────────────────────────────────────────
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "generate_catalysts")

    # Conditional: skip web search OR run it
    graph.add_conditional_edges(
        "generate_catalysts",
        _route_web_intel,
        {
            "gather_web_intel":      "gather_web_intel",
            "synthesize_enrichment": "synthesize_enrichment",
        },
    )

    # Both paths converge at synthesis
    graph.add_edge("gather_web_intel", "synthesize_enrichment")

    # Conditional: abort if synthesis failed
    graph.add_conditional_edges(
        "synthesize_enrichment",
        _route_after_synthesis,
        {
            "validate_enrichment": "validate_enrichment",
            END: END,
        },
    )

    # Sequential tail
    graph.add_edge("validate_enrichment", "write_enrichment")
    graph.add_edge("write_enrichment",    "score_completeness")
    graph.add_edge("score_completeness",  "generate_deals")
    graph.add_edge("generate_deals",      END)

    # ── Compile ───────────────────────────────────────────────────────────
    if checkpointing:
        from langgraph.checkpoint.memory import MemorySaver
        return graph.compile(checkpointer=MemorySaver())

    return graph.compile()
