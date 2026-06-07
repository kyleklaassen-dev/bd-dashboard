"""
Static descriptions of the weekend GitHub Actions pipelines, one module per
workflow. Each module exports a `PIPELINE` dict; this package re-exports them
under names that match the workflow.
"""
from .abstract_fetcher import PIPELINE as ABSTRACT_FETCHER
from .evidence_collectors import PIPELINE as EVIDENCE_COLLECTORS

PIPELINES = {
    ABSTRACT_FETCHER["key"]: ABSTRACT_FETCHER,
    EVIDENCE_COLLECTORS["key"]: EVIDENCE_COLLECTORS,
}
