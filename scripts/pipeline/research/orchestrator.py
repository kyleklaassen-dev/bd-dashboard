"""
Research intelligence pipeline orchestrator.

Sequential runner — no LangGraph graph since there are no LLM calls or
conditional branches. Each node passes state to the next in order.

Pipeline:
  load_context → score → triggers → action → priority → upsert_queue
"""
from __future__ import annotations

from .state import ResearchPipelineState
from .nodes import load_context, score, triggers, action, priority, upsert_queue


def run_entity_pipeline(
    entity_id: str,
    area_id: str,
    dry_run: bool = False,
) -> ResearchPipelineState:
    """
    Run the full intelligence audit pipeline for one entity × area.
    Returns the final state (inspect .ok, .errors, .priority_score, etc.)
    """
    state = ResearchPipelineState(entity_id=entity_id, area_id=area_id, dry_run=dry_run)

    state = load_context.run(state)
    if not state.ok:
        return state

    state = score.run(state)
    state = triggers.run(state)
    state = action.run(state)
    state = priority.run(state)
    state = upsert_queue.run(state)

    return state
