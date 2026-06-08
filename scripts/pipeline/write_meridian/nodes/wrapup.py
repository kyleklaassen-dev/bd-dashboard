"""
Node: wrapup
Best-effort post-publish steps — editorial priority bump, catalyst outcome
sync, system_status stamp, and the pre-publish fact-check report. None of
these may fail the run; the Issue is already published by this point.
"""
from __future__ import annotations

import datetime
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

    try:
        if state.plan_company_ids:
            wm.bump_editorial_priority(state.plan_company_ids)
    except Exception as e:
        wm.log(f"bump_editorial_priority failed (non-fatal): {e}")

    try:
        wm.sync_catalyst_outcomes(state.plan, state.intel)
    except Exception as e:
        wm.log(f"sync_catalyst_outcomes failed (non-fatal): {e}")

    try:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        wm.requests.patch(
            f"{wm.SUPABASE_URL}/rest/v1/system_status",
            headers={**wm.SB_HEADERS, "Prefer": "return=minimal"},
            params={"id": "eq.1"},
            json={"last_meridian_at": now_iso, "updated_at": now_iso,
                  "last_pipeline_label": "meridian_write",
                  "note": "New Meridian Issue published"},
            timeout=15)
        wm.log("system_status stamped (meridian_write)")
    except Exception as e:
        wm.log(f"system_status stamp failed (non-fatal): {e}")

    wm.fact_check_report()

    state.mark_complete("wrapup")
    return state
