"""
Runtime flags for the weekend sprint — in ONE place so every module reads the
LIVE value rather than a stale import-time copy.

Why this exists: `DRY_RUN` is set once at startup from `--dry-run`. When phases
live in separate modules, `from weekend_sprint import DRY_RUN` would capture the
value at import time (always False) and silently turn a dry-run into a real run.
Reading `runtime.DRY_RUN` (a module attribute) always reflects the current value.

Usage:
    from weekend import runtime
    runtime.set_dry_run(args.dry_run)   # once, at startup
    if not runtime.DRY_RUN:             # in any module/phase
        ...write...
"""

# Default False = real run, preserving the original module-global default exactly.
DRY_RUN = False


def set_dry_run(value: bool) -> None:
    """Set the global dry-run flag once at startup."""
    global DRY_RUN
    DRY_RUN = bool(value)


def is_dry_run() -> bool:
    return DRY_RUN


# Sprint identifier — defaults to a startup timestamp, overridable via --sprint-id.
# Mutable shared state like DRY_RUN: read as runtime.SPRINT_ID so every module sees
# the live value.
import datetime as _dt

SPRINT_ID = f"sprint_{_dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"


def set_sprint_id(value: str) -> None:
    global SPRINT_ID
    SPRINT_ID = value
