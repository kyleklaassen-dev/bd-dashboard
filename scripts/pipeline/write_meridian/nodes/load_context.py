"""
Node: load_context
Fetches every data source the Issue depends on, and augments the writer's
module-level SYSTEM_PROMPT with verification cautions + reader feedback —
mirroring the original __main__ mutation so generate_editorial_plan/generate_draft
(which read SYSTEM_PROMPT as a module global) pick up the augmented version.
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

    wm.SYSTEM_PROMPT = wm.SYSTEM_PROMPT + wm.build_verification_cautions()
    wm.SYSTEM_PROMPT = wm.SYSTEM_PROMPT + wm.build_reader_feedback_block()

    state.intel                    = wm.fetch_recent_intel(hours_back=48)
    state.deals                    = wm.fetch_recent_deals(days_back=7)
    state.catalysts                = wm.fetch_upcoming_catalysts()
    state.catalyst_calendar_events = wm.fetch_catalyst_calendar(days_ahead=365)
    state.bd_priority_data         = wm.fetch_bd_priority_companies()
    state.drugs, state.companies   = wm.fetch_drug_context()
    state.ailux_positions          = wm.fetch_ailux_position()
    state.recent_issues            = wm.fetch_recent_meridian_issues(n=7)
    state.company_signals          = wm.fetch_company_signals()
    state.trials                   = wm.fetch_recent_trials()
    (state.graph_active_in,
     state.graph_targets,
     state.graph_competes)         = wm.fetch_graph_context()

    wm.log(
        f"Data assembled: {len(state.intel)} intel · {len(state.deals)} deals · "
        f"{len(state.catalysts)} catalysts · {len(state.catalyst_calendar_events)} cal events · "
        f"{len(state.bd_priority_data.get('scores', []))} very_high scores · "
        f"{len(state.bd_priority_data.get('views', []))} strategic views · "
        f"{len(state.company_signals)} signals · {len(state.trials)} trials · "
        f"{len(state.recent_issues)} prior issues · "
        f"graph: {sum(len(v) for v in state.graph_active_in.values())} ACTIVE_IN / "
        f"{len(state.graph_targets)} TARGETS / {len(state.graph_competes)} COMPETES_WITH"
    )

    state.mark_complete("load_context")
    return state
