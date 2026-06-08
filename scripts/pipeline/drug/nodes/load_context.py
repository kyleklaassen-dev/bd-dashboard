"""
Node 1: load_context
Fetches drug record + company + targets + indications + trials from Supabase.
Populates state.ctx, state.drug_name, state.coverage, state.missing_fields.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from _common import log
import _db
from ..state import DrugPipelineState


def run(state: DrugPipelineState) -> DrugPipelineState:
    from enrichment.drug_enrichment import (
        fetch_drug_context,
        compute_coverage,
        fields_to_enrich,
    )

    ctx = fetch_drug_context(state.drug_id)
    if not ctx:
        state.add_error("load_context", f"Drug '{state.drug_id}' not found in Supabase")
        return state

    drug = ctx["drug"]
    state.ctx = ctx
    state.drug_name = drug.get("name") or state.drug_id
    state.coverage = compute_coverage(drug)
    state.coverage_before = state.coverage
    state.missing_fields = fields_to_enrich(drug)

    log(f"  Drug: {state.drug_name} | Stage: {drug.get('stage')} | "
        f"Coverage: {state.coverage}% | Missing: {state.missing_fields}", indent=1)

    state.mark_complete("load_context")
    return state
