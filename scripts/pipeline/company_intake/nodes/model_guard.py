"""
Node: model_guard
Blocks live writes when INTAKE_MODEL is set to a Haiku-tier model — Haiku
hallucinates company pipelines and fabricated drug names must not reach
discovery_queue. --dry-run is exempt (fast structural validation only).
"""
from __future__ import annotations

import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_NODES    = os.path.dirname(_HERE)
_PIPELINE = os.path.dirname(_NODES)
_SCRIPTS  = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from pipeline.company_intake.state import IntakeState  # noqa: E402

INTAKE_MODEL_ENV_DEFAULT = "claude-sonnet-4-6"


def active_model() -> str:
    return os.environ.get("INTAKE_MODEL", INTAKE_MODEL_ENV_DEFAULT)


def model_guard_node(state: IntakeState) -> IntakeState:
    """
    Aborts the run when a Haiku-tier INTAKE_MODEL is configured for a live
    (non-dry-run) write. Message wording mirrors the original per-mode text.
    """
    _active_model = active_model()
    if not state.dry_run and "haiku" in _active_model.lower():
        if state.mode == "reaudit":
            print(f"  ❌ Model tier error: INTAKE_MODEL='{_active_model}' cannot be used for live writes.")
            print(f"     Set INTAKE_MODEL=claude-sonnet-4-6 for re-audit live runs.")
        else:
            print(f"\n  ❌ Model tier error: INTAKE_MODEL='{_active_model}' cannot be used for live writes.")
            print(f"     Haiku hallucinates company pipelines — fabricated drug names may enter discovery_queue.")
            print(f"     Set INTAKE_MODEL=claude-sonnet-4-6 (or unset INTAKE_MODEL) for live runs.")
            print(f"     Use --dry-run with Haiku for fast structural validation only.")
        state.abort("haiku_model_blocked")

    state.mark_complete("model_guard")
    return state
