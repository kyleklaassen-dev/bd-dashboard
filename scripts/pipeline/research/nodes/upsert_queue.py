"""Node 6: upsert_queue — write research_queue + stamp drug rows."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from enrichment.research_intelligence import upsert_research_queue
from ..state import ResearchPipelineState


def run(state: ResearchPipelineState) -> ResearchPipelineState:
    upsert_research_queue(
        ctx=state.ctx,
        score_result=state.score_result,
        triggers=state.triggers,
        next_action=state.next_action,
        priority_score=state.priority_score,
        reason=state.priority_reason,
        dry_run=state.dry_run,
    )
    state.mark_complete("upsert_queue")
    return state
