"""Node 3: triggers — detect conditions that require downstream updates."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from enrichment.research_intelligence import check_research_triggers
from ..state import ResearchPipelineState


def run(state: ResearchPipelineState) -> ResearchPipelineState:
    state.triggers = check_research_triggers(state.ctx)
    state.mark_complete("triggers")
    return state
