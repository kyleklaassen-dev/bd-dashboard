"""
LangGraph-based company intake pipeline graph.

Both supported workflows — research-and-queue ("intake") and pipeline-diff
("reaudit") — share identity resolution, the model-tier guard, and the
open-ended Claude research call, then diverge. state.mode selects the path.

Graph topology
──────────────
  START
    │
  resolve_identity ──[aborted]──────────────────────────────────► END
    │
    ├─[mode=="reaudit"]──► load_db_drugs ──[aborted]────────────► END
    │                            │
    │                       model_guard ◄─────────────────────────┐
    │                            │                                 │
    └─[mode=="intake"]──────────►┘                                │
                                 │                                 │
                            [aborted]──────────────────────────► END
                                 │
                          research_company
                                 │
                            [aborted]──────────────────────────► END
                                 │
              ┌──[mode=="reaudit"]──► diff_pipeline ──[no new_drugs]──► END
              │                              │
              │                         write_gaps ─────────────────► END
              │
              └──[mode=="intake"]───► score_areas ──[no relevant_areas]──► END
                                             │
                                       write_queue ──────────────────► END

Usage
─────
    from pipeline.company_intake.graph import build_intake_graph
    from pipeline.company_intake.state import IntakeState

    app = build_intake_graph()
    state = IntakeState(company_name="Akeso", mode="intake",
                        supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY,
                        run_id=run_id, dry_run=dry_run, verbose=verbose, force=force)
    result = app.invoke(state)
"""
from __future__ import annotations

import os
import sys

_HERE    = os.path.dirname(os.path.abspath(__file__))
_PIPELINE = os.path.dirname(_HERE)
_SCRIPTS = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from langgraph.graph import END, START, StateGraph  # noqa: E402

from pipeline.company_intake.state import IntakeState  # noqa: E402


# ── Routing conditions ────────────────────────────────────────────────────────

def _route_after_resolve(state: IntakeState) -> str:
    if state.aborted:
        return END
    return "load_db_drugs" if state.mode == "reaudit" else "model_guard"


def _route_after_load_db_drugs(state: IntakeState) -> str:
    return END if state.aborted else "model_guard"


def _route_after_model_guard(state: IntakeState) -> str:
    return END if state.aborted else "research_company"


def _route_after_research(state: IntakeState) -> str:
    if state.aborted:
        return END
    return "diff_pipeline" if state.mode == "reaudit" else "score_areas"


def _route_after_diff(state: IntakeState) -> str:
    return "write_gaps" if state.new_drugs else END


def _route_after_score(state: IntakeState) -> str:
    return "write_queue" if state.relevant_areas else END


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_intake_graph(checkpointing: bool = False):
    """
    Build and compile the LangGraph company-intake pipeline.

    Args:
        checkpointing: When True, attaches a MemorySaver so runs can be
                       resumed from the last successful node.

    Returns:
        A compiled ``CompiledStateGraph`` accepting ``IntakeState`` via
        ``app.invoke(state)``.
    """
    from pipeline.company_intake.nodes.resolve_identity  import resolve_identity_node
    from pipeline.company_intake.nodes.model_guard       import model_guard_node
    from pipeline.company_intake.nodes.research_company  import research_company_node
    from pipeline.company_intake.nodes.score_areas       import score_areas_node
    from pipeline.company_intake.nodes.write_queue       import write_queue_node
    from pipeline.company_intake.nodes.load_db_drugs     import load_db_drugs_node
    from pipeline.company_intake.nodes.diff_pipeline     import diff_pipeline_node
    from pipeline.company_intake.nodes.write_gaps        import write_gaps_node

    graph = StateGraph(IntakeState)

    # ── Register nodes ────────────────────────────────────────────────────
    graph.add_node("resolve_identity",  resolve_identity_node)
    graph.add_node("load_db_drugs",     load_db_drugs_node)
    graph.add_node("model_guard",       model_guard_node)
    graph.add_node("research_company",  research_company_node)
    graph.add_node("score_areas",       score_areas_node)
    graph.add_node("write_queue",       write_queue_node)
    graph.add_node("diff_pipeline",     diff_pipeline_node)
    graph.add_node("write_gaps",        write_gaps_node)

    # ── Edges ─────────────────────────────────────────────────────────────
    graph.add_edge(START, "resolve_identity")

    graph.add_conditional_edges(
        "resolve_identity",
        _route_after_resolve,
        {"load_db_drugs": "load_db_drugs", "model_guard": "model_guard", END: END},
    )
    graph.add_conditional_edges(
        "load_db_drugs",
        _route_after_load_db_drugs,
        {"model_guard": "model_guard", END: END},
    )
    graph.add_conditional_edges(
        "model_guard",
        _route_after_model_guard,
        {"research_company": "research_company", END: END},
    )
    graph.add_conditional_edges(
        "research_company",
        _route_after_research,
        {"diff_pipeline": "diff_pipeline", "score_areas": "score_areas", END: END},
    )
    graph.add_conditional_edges(
        "diff_pipeline",
        _route_after_diff,
        {"write_gaps": "write_gaps", END: END},
    )
    graph.add_conditional_edges(
        "score_areas",
        _route_after_score,
        {"write_queue": "write_queue", END: END},
    )
    graph.add_edge("write_queue", END)
    graph.add_edge("write_gaps",  END)

    # ── Compile ───────────────────────────────────────────────────────────
    if checkpointing:
        from langgraph.checkpoint.memory import MemorySaver
        return graph.compile(checkpointer=MemorySaver())

    return graph.compile()
