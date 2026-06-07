"""Node 5: priority — calculate urgency integer (0–200) with human reason."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from enrichment.research_intelligence import calculate_priority_score
from ..state import ResearchPipelineState


def run(state: ResearchPipelineState) -> ResearchPipelineState:
    score, reason = calculate_priority_score(state.ctx, state.score_result, state.triggers)
    state.priority_score = score
    state.priority_reason = reason
    state.mark_complete("priority")
    return state
