"""
Node: validate_enrichment
Applies Pydantic field validation to drug_updates from the synthesis response
and records trajectory metadata on the enrichment_runs row.
"""
from __future__ import annotations

import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_PIPELINE = os.path.dirname(_HERE)
_SCRIPTS  = os.path.dirname(_PIPELINE)
_ENRICH   = os.path.join(_SCRIPTS, "enrichment")
for _p in (_SCRIPTS, _ENRICH):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ai.validators.drug_fields import validate_drug_updates  # noqa: E402
from ai import run_log                                        # noqa: E402
from _common import log                                       # noqa: E402
from pipeline.state import PipelineState                      # noqa: E402


def validate_enrichment(state: PipelineState) -> PipelineState:
    """
    1. Patches enrichment_runs with the raw LLM response (trajectory v59).
    2. Validates drug_updates via Pydantic — invalid rows are dropped, corrected
       values are logged.
    3. Writes the validated data to state.validated_data (with drug_updates
       replaced by the clean list) so write_enrichment sees correct records.
    4. Patches enrichment_runs again with field-level tracking stats.

    Populates state.validated_data and state.validation_stats.
    """
    # ── Trajectory: raw LLM response ─────────────────────────────────────
    if state.enrichment_run_id and not state.dry_run:
        try:
            run_log.patch_enrichment_run(state.enrichment_run_id, {
                "raw_llm_response": (state.synth_raw_text or "")[:8000],
                "entity_id":        state.company_id,
                "skill_name":       "company_enrich",
            })
        except Exception as e:
            log(f"  [trajectory] raw_llm_response patch failed (non-fatal): {e}", indent=2)

    # ── Pydantic validation ───────────────────────────────────────────────
    ctx_drug_map = {d["id"]: d for d in state.ctx.drugs}
    val = validate_drug_updates(
        state.synth_data.get("drug_updates") or [],
        ctx_drug_map,
    )
    val.stats.log(indent=1)

    state.validated_data = dict(state.synth_data)
    state.validated_data["drug_updates"] = val.valid_updates
    state.validation_stats = val.stats

    # ── Trajectory: field-level tracking ─────────────────────────────────
    if state.enrichment_run_id and not state.dry_run:
        try:
            st = val.stats
            patch: dict = {"fine_tune_eligible": True}
            if st.attempted:               patch["fields_attempted"]  = st.attempted
            if st.changed:                 patch["fields_changed"]    = st.changed
            if st.confirmed:               patch["fields_confirmed"]  = st.confirmed
            if st.failed:                  patch["fields_failed"]     = st.failed
            if st.schema_valid is not None: patch["schema_valid"]     = st.schema_valid
            if st.corrections:             patch["correction_count"]  = st.corrections
            run_log.patch_enrichment_run(state.enrichment_run_id, patch)
        except Exception as e:
            log(f"  [trajectory] field-tracking patch failed (non-fatal): {e}", indent=2)

    state.mark_complete("validate_enrichment")
    return state
