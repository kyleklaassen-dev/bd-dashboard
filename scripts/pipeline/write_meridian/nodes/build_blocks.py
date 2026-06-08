"""
Node: build_blocks
Phase A — assembles every formatted prompt block shared by both LLM passes
from the fetched Supabase context (intelligence.write_meridian.build_content_blocks).
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
    state.blocks = wm.build_content_blocks(
        state.intel, state.deals, state.catalysts, state.drugs, state.companies,
        state.ailux_positions, state.recent_issues, state.company_signals, state.trials,
        graph_active_in=state.graph_active_in,
        graph_targets=state.graph_targets,
        graph_competes=state.graph_competes,
        catalyst_calendar_events=state.catalyst_calendar_events,
        bd_priority_data=state.bd_priority_data,
    )
    state.mark_complete("build_blocks")
    return state
