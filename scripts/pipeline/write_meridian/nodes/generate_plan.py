"""
Node: generate_plan
Pass 1 — editorial plan (intelligence.write_meridian.generate_editorial_plan,
routed through ai_client.run_json). Persists the plan's intel/company ids and
content fingerprint before Pass 2 runs, so editorial judgments are never lost
even if the draft pass fails.
"""
from __future__ import annotations

import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_PIPELINE = os.path.dirname(os.path.dirname(_HERE))
_SCRIPTS  = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from ..state import MeridianState  # noqa: E402


def _wm():
    import intelligence.write_meridian as write_meridian  # noqa: PLC0415
    return write_meridian


def run(state: MeridianState) -> MeridianState:
    wm = _wm()
    blocks = state.blocks

    plan = wm.generate_editorial_plan(
        blocks["date_long"], blocks["intel_block"], blocks["deals_block"],
        blocks["ailux_block"], blocks["prior_block"], blocks["signals_block"],
        graph_block=blocks["graph_block"],
        patient_context_block=blocks["patient_context_block"],
        patient_stats_block=blocks["patient_stats_block"],
        catalyst_calendar_block=blocks["catalyst_calendar_block"],
        bd_priority_block=blocks["bd_priority_block"],
    )
    state.plan       = plan
    state.plan_block = wm.format_plan_block(plan)

    # ── Persist Pass 1 plan before Pass 2 so it is never lost ────────────────
    plan_intel_ids = [it["id"] for it in state.intel if it.get("id")]
    state.plan_company_ids    = wm._extract_company_ids_from_plan(plan, state.intel)
    state.content_fingerprint = wm._compute_content_fingerprint(plan_intel_ids, state.plan_company_ids)
    wm.log(f"Pass 1 plan persisted: {len(state.plan_company_ids)} companies · "
           f"fingerprint={state.content_fingerprint[:12]}…")

    state.mark_complete("generate_plan")
    return state
