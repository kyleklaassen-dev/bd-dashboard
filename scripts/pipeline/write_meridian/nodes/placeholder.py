"""
Node: placeholder
Taken when no intel was collected in the lookback window — writes a minimal
"check back tomorrow" Issue instead of running the two LLM passes.
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
    wm.log("No intel found — writing placeholder issue.")

    state.html = (
        "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>The Meridian</title></head>"
        "<body><h1 style='color:#1a3f8f;font-family:Georgia,serif'>The Meridian</h1>"
        f"<p style='font-family:Georgia,serif'>No significant biopharma intelligence collected in the last 48 hours "
        f"for today, {datetime.datetime.utcnow().strftime('%B %-d, %Y')}. "
        "Check back tomorrow.</p></body></html>"
    )
    state.plan                = None
    state.plan_company_ids    = []
    state.content_fingerprint = None

    state.mark_complete("placeholder")
    return state
