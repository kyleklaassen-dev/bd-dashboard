"""Node 4: action — determine the priority-ordered next best action."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from enrichment.research_intelligence import get_next_best_action
from ..state import ResearchPipelineState


def run(state: ResearchPipelineState) -> ResearchPipelineState:
    state.next_action = get_next_best_action(state.ctx, state.score_result)
    state.mark_complete("action")
    return state
