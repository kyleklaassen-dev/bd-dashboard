"""Node 2: score — compute completeness score (0–100) across 6 research stages."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from enrichment.research_intelligence import score_entity_completeness
from ..state import ResearchPipelineState


def run(state: ResearchPipelineState) -> ResearchPipelineState:
    state.score_result = score_entity_completeness(state.ctx)
    state.mark_complete("score")
    return state
