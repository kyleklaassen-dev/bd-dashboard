"""
Node 5: log_run
Writes an enrichment_runs row for observability / model comparison.
"""
from __future__ import annotations

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import enrichment._db as _db
from ..state import DrugPipelineState


def run(state: DrugPipelineState, elapsed: float = 0.0) -> DrugPipelineState:
    from enrichment.drug_enrichment import (
        _MODEL_COMPARISON_AVAILABLE,
        patch_enrichment_run,
    )

    if state.enrichment_run_id and _MODEL_COMPARISON_AVAILABLE:
        patch_enrichment_run(state.enrichment_run_id, {
            "status":            "success" if state.ok else "error",
            "schema_valid":      state.ok,
            "records_processed": state.fields_written,
            "run_duration_seconds": round(elapsed, 2),
            "model_version":     "claude-sonnet-4-6",
        })
    else:
        try:
            _db.sb_post("enrichment_runs", {
                "entity_id":            state.drug_id,
                "entity_type":          "drug",
                "skill_name":           "drug_enrich",
                "script_name":          "drug_enrichment.py",
                "model_name":           "claude-sonnet-4-6",
                "model_version":        "claude-sonnet-4-6",
                "run_type":             "weekend_sprint",
                "status":               "success" if state.ok else "error",
                "schema_valid":         state.ok,
                "records_processed":    state.fields_written,
                "run_duration_seconds": round(elapsed, 2),
                "run_date":             _db.now_iso(),
            })
        except Exception:
            pass

    state.mark_complete("log_run")
    return state
