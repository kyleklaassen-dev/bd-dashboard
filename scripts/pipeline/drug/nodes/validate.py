"""
Node 3: validate
Validates and sanitizes LLM output (overlap enum, catalog_category, source_url, text lengths).
Populates state.validated_data and state.fields_to_write.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from enrichment._common import log
from ..state import DrugPipelineState


def run(state: DrugPipelineState) -> DrugPipelineState:
    from enrichment.drug_enrichment import validate_output

    drug = state.ctx.get("drug", {})
    drug_name = state.drug_name

    validated = validate_output(state.llm_raw, drug_name)
    if not validated:
        state.add_error("validate", "No valid fields after validation")
        return state

    # Only write fields that are actually missing on the drug record
    state.validated_data = validated
    state.fields_to_write = {
        k: v for k, v in validated.items()
        if k in state.missing_fields or (k == "source_url" and not drug.get("source_url"))
    }

    log(f"  Fields to write: {list(state.fields_to_write.keys())}", indent=2)

    state.mark_complete("validate")
    return state
