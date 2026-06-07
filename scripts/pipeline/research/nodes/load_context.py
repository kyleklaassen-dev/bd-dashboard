"""Node 1: load_context — fetch all entity data from Supabase."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from enrichment.research_intelligence import load_entity_context
from ..state import ResearchPipelineState


def run(state: ResearchPipelineState) -> ResearchPipelineState:
    ctx = load_entity_context(state.entity_id, state.area_id)
    if not ctx or not ctx.get("drugs"):
        state.add_error("load_context", f"No drugs found for entity '{state.entity_id}'")
        return state
    state.ctx = ctx
    state.mark_complete("load_context")
    return state
