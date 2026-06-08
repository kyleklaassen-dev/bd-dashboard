"""
Node: publish
Saves the Issue to Supabase, then deploys it to GitHub Pages — in that order,
matching the original script. Deploy must run even if later wrap-up steps
would fail (root cause of the 2026-06-03+ Writer outage: a post-save step
crashed before deploy, so meridian_today.html never published).
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

    wm.save_to_supabase(
        state.html, state.intel, state.today,
        plan=state.plan,
        company_ids=state.plan_company_ids,
        content_fingerprint=state.content_fingerprint,
    )
    wm.deploy_to_github(state.html)

    state.mark_complete("publish")
    return state
