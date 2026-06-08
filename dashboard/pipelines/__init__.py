"""
Static descriptions of the weekend GitHub Actions pipelines, one module per
workflow. Each module exports a `PIPELINE` dict; this package re-exports them
under names that match the workflow.
"""
from .abstract_fetcher import PIPELINE as ABSTRACT_FETCHER
from .evidence_collectors import PIPELINE as EVIDENCE_COLLECTORS
from .weekend_sprint import PIPELINE as WEEKEND_SPRINT
from .school_week_sprint import PIPELINE as SCHOOL_WEEK_SPRINT
from .flywheel_phase2 import PIPELINE as FLYWHEEL_PHASE2

PIPELINES = {
    ABSTRACT_FETCHER["key"]: ABSTRACT_FETCHER,
    EVIDENCE_COLLECTORS["key"]: EVIDENCE_COLLECTORS,
    WEEKEND_SPRINT["key"]: WEEKEND_SPRINT,
    SCHOOL_WEEK_SPRINT["key"]: SCHOOL_WEEK_SPRINT,
    FLYWHEEL_PHASE2["key"]: FLYWHEEL_PHASE2,
}
