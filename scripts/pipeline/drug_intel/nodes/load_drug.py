"""Node 1: load_drug — fetch drug record + company name from Supabase."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from ..state import DrugIntelPipelineState


def run(state: DrugIntelPipelineState) -> DrugIntelPipelineState:
    from enrichment.drug_intelligence_researcher import load_drug

    try:
        state.drug = load_drug(state.drug_id)
        state.mark_complete("load_drug")
    except SystemExit as e:
        state.add_error("load_drug", str(e))
    return state
