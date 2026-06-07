"""
Node 4: write
Patches drugs table, logs field changes to enriched_field_log, and upserts coverage_scores.
Populates state.fields_written, state.coverage_after.
"""
from __future__ import annotations

import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from enrichment._common import log
import enrichment._db as _db
from ..state import DrugPipelineState


def run(state: DrugPipelineState) -> DrugPipelineState:
    from enrichment.drug_enrichment import (
        compute_coverage,
        log_field_change,
        _MODEL_COMPARISON_AVAILABLE,
        patch_enrichment_run,
    )

    if not state.fields_to_write:
        log(f"  No fields to write — skipping", indent=2)
        state.mark_complete("write")
        return state

    if state.dry_run:
        log(f"  [DRY-RUN] Would patch drug {state.drug_id}: {list(state.fields_to_write.keys())}", indent=2)
        state.fields_written = len(state.fields_to_write)
        state.mark_complete("write")
        return state

    now_iso = datetime.datetime.utcnow().isoformat()
    write_payload = {
        **state.fields_to_write,
        "last_enriched_model": "claude-sonnet-4-6",
        "updated_at": "now()",
    }
    if state.enrichment_run_id:
        write_payload["last_enrichment_run_id"] = state.enrichment_run_id

    ok = _db.sb_patch("drugs", write_payload, {"id": f"eq.{state.drug_id}"})
    if not ok:
        state.add_error("write", f"Patch failed for drug {state.drug_id}")
        return state

    log(f"  Drug '{state.drug_name}': patched {len(state.fields_to_write)} fields", indent=2)
    state.fields_written = len(state.fields_to_write)

    # Log each field change with provenance
    source_url = state.validated_data.get("source_url")
    drug = state.ctx.get("drug", {})
    for field_name, new_val in state.fields_to_write.items():
        old_val = drug.get(field_name)
        log_field_change(
            state.drug_id, field_name, old_val, new_val,
            enrichment_run_id=state.enrichment_run_id,
            source_url=source_url if field_name == "source_url" else None,
        )

    # Update coverage score
    updated_drug = {**drug, **state.fields_to_write}
    state.coverage_after = compute_coverage(updated_drug)
    _db.sb_post("coverage_scores", {
        "entity_id":      state.drug_id,
        "entity_type":    "drug",
        "coverage_score": state.coverage_after,
        "computed_at":    now_iso,
    })
    log(f"  Coverage: {state.coverage_before}% → {state.coverage_after}%", indent=2)

    state.mark_complete("write")
    return state
