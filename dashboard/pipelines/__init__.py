"""
Static descriptions of the GitHub Actions pipelines, one module per workflow.
Each module exports a `PIPELINE` dict; this package re-exports them and builds
the `PIPELINES` registry (keyed by each pipeline's `key`) that the app routes on.

Grouped by cadence to match the landing page sections:
  • weekend / weekly sprints  • nightly publishing chain (chain-01..07)
  • daily jobs  • weekly jobs  • manual (workflow_dispatch) jobs
"""
# --- Sprints / standalone -------------------------------------------------
from .abstract_fetcher import PIPELINE as ABSTRACT_FETCHER
from .evidence_collectors import PIPELINE as EVIDENCE_COLLECTORS
from .weekend_sprint import PIPELINE as WEEKEND_SPRINT
from .school_week_sprint import PIPELINE as SCHOOL_WEEK_SPRINT
from .flywheel_phase2 import PIPELINE as FLYWHEEL_PHASE2
from .trial_audit import PIPELINE as TRIAL_AUDIT

# --- Nightly publishing chain (chain-01 → chain-07) -----------------------
from .chain_01_research import PIPELINE as CHAIN_RESEARCH
from .chain_02_source_verifier import PIPELINE as CHAIN_SOURCE_VERIFIER
from .chain_03_content_verifier import PIPELINE as CHAIN_CONTENT_VERIFIER
from .chain_04_landscape_scores import PIPELINE as CHAIN_LANDSCAPE_SCORES
from .chain_05_writer import PIPELINE as CHAIN_WRITER
from .chain_06_morning_summary import PIPELINE as CHAIN_MORNING_SUMMARY
from .chain_07_homepage_news import PIPELINE as CHAIN_HOMEPAGE_NEWS

# --- Daily jobs -----------------------------------------------------------
from .daily_company_enrichment import PIPELINE as DAILY_COMPANY_ENRICHMENT
from .daily_completeness_scoring import PIPELINE as DAILY_COMPLETENESS_SCORING
from .daily_execute_intel_actions import PIPELINE as DAILY_EXECUTE_INTEL_ACTIONS
from .daily_pipeline_health import PIPELINE as DAILY_PIPELINE_HEALTH
from .daily_pipeline_monitor import PIPELINE as DAILY_PIPELINE_MONITOR
from .daily_queue_processor import PIPELINE as DAILY_QUEUE_PROCESSOR
from .daily_ranking_snapshots import PIPELINE as DAILY_RANKING_SNAPSHOTS
from .daily_review_submitted_intel import PIPELINE as DAILY_REVIEW_SUBMITTED_INTEL
from .daily_run_validation_tests import PIPELINE as DAILY_RUN_VALIDATION_TESTS
from .daily_signal_monitor import PIPELINE as DAILY_SIGNAL_MONITOR
from .daily_stock_prices import PIPELINE as DAILY_STOCK_PRICES
from .daily_structural_edges import PIPELINE as DAILY_STRUCTURAL_EDGES
from .daily_verify_edges import PIPELINE as DAILY_VERIFY_EDGES

# --- Weekly jobs ----------------------------------------------------------
from .weekly_audit_retention import PIPELINE as WEEKLY_AUDIT_RETENTION
from .weekly_bd_recommender import PIPELINE as WEEKLY_BD_RECOMMENDER
from .weekly_deal_edges import PIPELINE as WEEKLY_DEAL_EDGES
from .weekly_landscape_briefing import PIPELINE as WEEKLY_LANDSCAPE_BRIEFING
from .weekly_narrative_generation import PIPELINE as WEEKLY_NARRATIVE_GENERATION
from .weekly_patient_briefs import PIPELINE as WEEKLY_PATIENT_BRIEFS
from .weekly_refresh_company_verified import PIPELINE as WEEKLY_REFRESH_COMPANY_VERIFIED
from .weekly_validation_research import PIPELINE as WEEKLY_VALIDATION_RESEARCH

# --- Manual (workflow_dispatch) jobs --------------------------------------
from .manual_apply_migration import PIPELINE as MANUAL_APPLY_MIGRATION
from .manual_backfill_ailux_angle import PIPELINE as MANUAL_BACKFILL_AILUX_ANGLE
from .manual_backfill_bd_angle import PIPELINE as MANUAL_BACKFILL_BD_ANGLE


# Ordered groups — drives the landing-page card layout in app.py.
SPRINT_PIPELINES = [
    ABSTRACT_FETCHER,
    EVIDENCE_COLLECTORS,
    WEEKEND_SPRINT,
    SCHOOL_WEEK_SPRINT,
    FLYWHEEL_PHASE2,
    TRIAL_AUDIT,
]

CHAIN_PIPELINES = [
    CHAIN_RESEARCH,
    CHAIN_SOURCE_VERIFIER,
    CHAIN_CONTENT_VERIFIER,
    CHAIN_LANDSCAPE_SCORES,
    CHAIN_WRITER,
    CHAIN_MORNING_SUMMARY,
    CHAIN_HOMEPAGE_NEWS,
]

DAILY_PIPELINES = [
    DAILY_COMPANY_ENRICHMENT,
    DAILY_COMPLETENESS_SCORING,
    DAILY_RANKING_SNAPSHOTS,
    DAILY_STOCK_PRICES,
    DAILY_STRUCTURAL_EDGES,
    DAILY_VERIFY_EDGES,
    DAILY_QUEUE_PROCESSOR,
    DAILY_EXECUTE_INTEL_ACTIONS,
    DAILY_REVIEW_SUBMITTED_INTEL,
    DAILY_RUN_VALIDATION_TESTS,
    DAILY_SIGNAL_MONITOR,
    DAILY_PIPELINE_MONITOR,
    DAILY_PIPELINE_HEALTH,
]

WEEKLY_PIPELINES = [
    WEEKLY_BD_RECOMMENDER,
    WEEKLY_LANDSCAPE_BRIEFING,
    WEEKLY_NARRATIVE_GENERATION,
    WEEKLY_PATIENT_BRIEFS,
    WEEKLY_DEAL_EDGES,
    WEEKLY_REFRESH_COMPANY_VERIFIED,
    WEEKLY_VALIDATION_RESEARCH,
    WEEKLY_AUDIT_RETENTION,
]

MANUAL_PIPELINES = [
    MANUAL_APPLY_MIGRATION,
    MANUAL_BACKFILL_BD_ANGLE,
    MANUAL_BACKFILL_AILUX_ANGLE,
]

PIPELINE_GROUPS = [
    ("Sprints", SPRINT_PIPELINES),
    ("Nightly publishing chain", CHAIN_PIPELINES),
    ("Daily", DAILY_PIPELINES),
    ("Weekly", WEEKLY_PIPELINES),
    ("Manual", MANUAL_PIPELINES),
]

# Flat registry the router looks pipelines up in, keyed by each pipeline's key.
PIPELINES = {
    p["key"]: p
    for _label, group in PIPELINE_GROUPS
    for p in group
}
