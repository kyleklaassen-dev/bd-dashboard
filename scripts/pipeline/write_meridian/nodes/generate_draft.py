"""
Node: generate_draft
Pass 2 — full draft (intelligence.write_meridian.generate_draft, routed
through ai_client.run_text since the response is raw HTML, not JSON — see
the _parse_json object-vs-array convention documented in source_verify.py).
Includes all post-draft processing (fence stripping, first-mention links,
fact-check audit, feedback widget injection).
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
    state.html = wm.generate_draft(state.blocks, state.plan_block, state.drugs, state.companies)
    state.mark_complete("generate_draft")
    return state
