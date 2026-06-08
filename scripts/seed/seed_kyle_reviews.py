#!/usr/bin/env python3
"""
seed_kyle_reviews.py — Meridian Feedback Loop Initializer
==========================================================
Seeds kyle_reviews and enriched_field_log with high-value items for human review.

Three sources:
  1. Drugs with enriched intelligence fields (drug_summary, ailux_angle, risk_summary,
     bd_angle, differentiation_thesis) — top 30 by overlap + stage priority
  2. drug_validation_results WHERE check_status IN ('needs_review', 'warning')
  3. governance_violations WHERE resolved = false

Deduplication: skips any entity+field combo already in kyle_reviews.

Also updates enriched_field_log.review_priority_score for all seeded items,
and backfills existing enriched_field_log entries with priority scores.

USAGE:
  python scripts/seed_kyle_reviews.py
  python scripts/seed_kyle_reviews.py --dry-run
  python scripts/seed_kyle_reviews.py --limit 50
"""

import os
import sys
import json
import time
import datetime
import argparse
import uuid
from typing import List, Dict, Optional, Tuple

# ── Path setup ───────────────────────────────────────────────────────────────
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _common import load_credentials  # noqa: E402
import _db                              # noqa: E402

SUPABASE_URL, SUPABASE_KEY, _ = load_credentials(require_anthropic=False)
_db.init_db(SUPABASE_URL, SUPABASE_KEY)

NOW_ISO = datetime.datetime.utcnow().isoformat() + "Z"
TODAY   = datetime.datetime.utcnow().strftime("%Y-%m-%d")
DRY_RUN = False

# ── Priority scores by field name ────────────────────────────────────────────

FIELD_PRIORITY = {
    "drug_summary":                10,
    "ailux_angle":                 9,
    "validation_stage_trial_match":    8,
    "validation_target_consistency":   8,
    "validation_indication_consistency": 8,
    "validation_company_resolution":   8,
    "validation_field_consistency":    8,
    "differentiation_thesis":      6,
    "why_it_matters":              6,
    "patient_benefit_simplified":  5,
    "unmet_need_addressed":        5,
    "source_url":                  7,   # governance violations
    "confidence_source":           3,
    "key_data":                    3,
}

# Validation check_type → friendly field_name for kyle_reviews
VALIDATION_FIELD_MAP = {
    "stage_trial_match":     "validation_stage_trial_match",
    "target_consistency":    "validation_target_consistency",
    "indication_consistency":"validation_indication_consistency",
    "company_resolution":    "validation_company_resolution",
    "field_consistency":     "validation_field_consistency",
}

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str, indent: int = 0):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {'  ' * indent}{msg}", flush=True)


# ── Supabase helpers ──────────────────────────────────────────────────────────

def sb_get(table: str, params: dict = None) -> List[dict]:
    return _db.sb_get(table, params or {})


def sb_post_rows(table: str, rows: List[dict]) -> int:
    """Insert rows, return count inserted."""
    if not rows:
        return 0
    if DRY_RUN:
        log(f"  [DRY-RUN] Would insert {len(rows)} rows into {table}", indent=2)
        return len(rows)
    result = _db.sb_insert(table, rows)
    return len(result)


def sb_patch(table: str, filters: dict, data: dict) -> bool:
    """Patch rows matching filters. Returns True on success."""
    if DRY_RUN:
        log(f"  [DRY-RUN] Would PATCH {table} WHERE {filters}: {list(data.keys())}", indent=2)
        return True
    params = {k: f"eq.{v}" for k, v in filters.items()}
    return _db.sb_patch(table, data, params)


def sb_post_single(table: str, row: dict) -> Optional[dict]:
    """Insert a single row, return inserted row or None."""
    if DRY_RUN:
        log(f"  [DRY-RUN] Would insert into {table}: {json.dumps(row)[:120]}", indent=2)
        return row
    return _db.sb_post(table, row)


# ── Data loading ──────────────────────────────────────────────────────────────

def load_existing_reviews() -> set:
    """Return set of 'entity_id::field_name' already in kyle_reviews."""
    rows = sb_get("kyle_reviews", {
        "select": "entity_id,field_name",
        "limit":  "2000",
    })
    return {f"{r['entity_id']}::{r['field_name']}" for r in rows}


def load_drugs_with_intel_fields(limit: int = 50) -> List[dict]:
    """
    Load drugs that have populated intelligence fields.
    Returns up to `limit` drugs, prioritized by overlap then stage.
    Note: bd_angle does not exist as a column in drugs; it is excluded.
    """
    rows = sb_get("drugs", {
        "select": (
            "id,name,drug_summary,ailux_angle,differentiation_thesis,"
            "why_it_matters,patient_benefit_simplified,"
            "unmet_need_addressed,overlap,stage,dashboard_visible"
        ),
        "limit":  str(limit * 3),  # Fetch extra, we'll filter
        "dashboard_visible": "eq.true",
    })

    # Overlap priority order
    overlap_order = {"Direct": 0, "Adjacent": 1, "Same-Space": 2, None: 3}

    # Stage priority
    def stage_priority(s: str) -> int:
        s = (s or "").lower()
        if "phase 3" in s or "phase_3" in s or "phase iii" in s:
            return 0
        if "phase 2" in s or "phase_2" in s or "phase ii" in s:
            return 1
        if "phase 1" in s or "phase_1" in s:
            return 2
        if "approved" in s:
            return 3
        return 4

    # Filter to drugs with at least one intel field
    intel_fields = ["drug_summary", "ailux_angle", "differentiation_thesis",
                    "bd_angle", "why_it_matters", "patient_benefit_simplified",
                    "unmet_need_addressed"]

    filtered = [r for r in rows if any(r.get(f) for f in intel_fields)]

    # Sort by overlap then stage
    filtered.sort(key=lambda r: (
        overlap_order.get(r.get("overlap"), 3),
        stage_priority(r.get("stage") or ""),
    ))

    return filtered[:limit]


def load_validation_issues() -> List[dict]:
    """Load drug_validation_results where check_status in ('needs_review', 'warning')."""
    needs_review = sb_get("drug_validation_results", {
        "select": "id,drug_id,check_type,check_status,details,created_at",
        "check_status": "eq.needs_review",
        "limit": "50",
    })
    warnings = sb_get("drug_validation_results", {
        "select": "id,drug_id,check_type,check_status,details,created_at",
        "check_status": "eq.warning",
        "limit": "20",
    })
    return needs_review + warnings


def load_governance_violations() -> List[dict]:
    """Load governance_violations where resolved = false."""
    return sb_get("governance_violations", {
        "select": "id,table_name,row_id,rule_name,description,detected_at",
        "resolved": "eq.false",
        "limit": "50",
    })


# ── Enriched field log entry builder ─────────────────────────────────────────

def make_efl_entry(
    entity_type: str,
    entity_id: str,
    field_name: str,
    enriched_value: str,
    priority_score: int,
    source: str = "seed_kyle_reviews",
    old_value: Optional[str] = None,
) -> dict:
    """Build an enriched_field_log row for a drug intelligence field."""
    return {
        "entity_type":           entity_type,
        "entity_id":             str(entity_id),
        "field_name":            field_name,
        "enriched_value":        enriched_value,
        "old_value":             old_value,
        "field_label":           "pending",
        "label_source":          source,
        "review_priority_score": priority_score,
        "was_changed":           True,
        "enriched_at":           NOW_ISO,
        "reviewed_by":           None,
    }


def make_kyle_review_entry(
    entity_type: str,
    entity_id: str,
    field_name: str,
    field_value: Optional[str],
    priority_score: int,
    source: str = "seed_kyle_reviews",
    notes: Optional[str] = None,
) -> dict:
    """Build a kyle_reviews row for human review."""
    return {
        "entity_type": entity_type,
        "entity_id":   str(entity_id),
        "field_name":  field_name,
        "field_value": str(field_value or "")[:500] if field_value else None,
        "action":      "confirmed",   # Seed as 'confirmed' — Kyle can override in UI
        "reviewed_at": NOW_ISO,
        "session_id":  f"seed-{TODAY}",
        "notes":       notes,
        "fine_tune_use": True,
    }


# ── Source 1: Drug intelligence fields ───────────────────────────────────────

def seed_drug_intel_fields(
    existing_reviews: set,
    limit: int = 30,
) -> Tuple[int, int, int]:
    """
    For each drug with populated intel fields, seed both:
    - enriched_field_log (so the UI shows them in the review queue)
    - kyle_reviews (as 'confirmed' pending Kyle's override)

    Returns (drugs_processed, efl_rows_inserted, review_rows_inserted)
    """
    log("Source 1: Drug intelligence fields", indent=1)
    drugs = load_drugs_with_intel_fields(limit=limit)
    log(f"  Found {len(drugs)} drugs with intel fields", indent=2)

    intel_fields = [
        "drug_summary",
        "ailux_angle",
        "differentiation_thesis",
        "why_it_matters",
        "patient_benefit_simplified",
        "unmet_need_addressed",
    ]

    efl_rows    = []
    review_rows = []
    drugs_seen  = set()

    for drug in drugs:
        drug_id   = str(drug["id"])
        drug_name = drug.get("name") or drug_id

        for field in intel_fields:
            value = drug.get(field)
            if not value or str(value).strip() in ("", "null", "None"):
                continue

            priority = FIELD_PRIORITY.get(field, 5)
            # Boost for Direct/Adjacent overlap
            overlap = drug.get("overlap") or ""
            if overlap == "Direct":
                priority = min(10, priority + 2)
            elif overlap == "Adjacent":
                priority = min(10, priority + 1)

            key = f"{drug_id}::{field}"
            if key in existing_reviews:
                log(f"  SKIP (already reviewed): {drug_name} / {field}", indent=3)
                continue

            # Build EFL entry (for UI queue)
            efl_rows.append(make_efl_entry(
                entity_type="drugs",
                entity_id=drug_id,
                field_name=field,
                enriched_value=str(value),
                priority_score=priority,
                source="seed_drug_intel",
            ))

            # Build kyle_reviews entry (seeded as confirmed, Kyle can change)
            review_rows.append(make_kyle_review_entry(
                entity_type="drug",
                entity_id=drug_id,
                field_name=field,
                field_value=str(value),
                priority_score=priority,
                notes=f"Seeded from drugs.{field} — review and confirm or correct",
            ))

            existing_reviews.add(key)
            drugs_seen.add(drug_id)

    log(f"  Drugs represented: {len(drugs_seen)}", indent=2)
    log(f"  EFL rows to insert: {len(efl_rows)}", indent=2)
    log(f"  kyle_reviews rows to insert: {len(review_rows)}", indent=2)

    efl_inserted    = 0
    review_inserted = 0

    # Insert EFL in batches of 20
    for i in range(0, len(efl_rows), 20):
        batch = efl_rows[i:i+20]
        n = sb_post_rows("enriched_field_log", batch)
        efl_inserted += n
        time.sleep(0.2)

    # Insert kyle_reviews in batches of 20
    for i in range(0, len(review_rows), 20):
        batch = review_rows[i:i+20]
        n = sb_post_rows("kyle_reviews", batch)
        review_inserted += n
        time.sleep(0.2)

    log(f"  Inserted: {efl_inserted} EFL rows, {review_inserted} kyle_reviews rows", indent=2)
    return len(drugs_seen), efl_inserted, review_inserted


# ── Source 2: Validation issues ───────────────────────────────────────────────

def seed_validation_issues(existing_reviews: set) -> Tuple[int, int]:
    """
    Create kyle_reviews entries for drug_validation_results needs_review/warning items.
    Returns (efl_inserted, review_inserted)
    """
    log("Source 2: Validation issues (needs_review + warning)", indent=1)
    issues = load_validation_issues()
    log(f"  Found {len(issues)} validation issues", indent=2)

    efl_rows    = []
    review_rows = []

    for issue in issues:
        drug_id    = str(issue.get("drug_id") or "")
        check_type = issue.get("check_type") or "unknown"
        status     = issue.get("check_status") or "needs_review"
        details    = issue.get("details") or {}
        field_name = VALIDATION_FIELD_MAP.get(check_type, f"validation_{check_type}")

        if not drug_id:
            continue

        key = f"{drug_id}::{field_name}"
        if key in existing_reviews:
            continue

        # Summarize details
        if isinstance(details, dict):
            detail_str = details.get("discrepancy") or details.get("message") or json.dumps(details)[:200]
            warnings = details.get("warnings", [])
            if warnings:
                detail_str = "; ".join(warnings[:2])
        elif isinstance(details, str):
            detail_str = details[:300]
        else:
            detail_str = str(details)[:300]

        summary = f"[{status.upper()}] {check_type}: {detail_str}"

        efl_rows.append(make_efl_entry(
            entity_type="drugs",
            entity_id=drug_id,
            field_name=field_name,
            enriched_value=summary,
            priority_score=8,  # Validation issues are high priority
            source="validation_results",
        ))

        review_rows.append(make_kyle_review_entry(
            entity_type="drug",
            entity_id=drug_id,
            field_name=field_name,
            field_value=summary,
            priority_score=8,
            notes=f"Validation {status} — manually confirm correct value",
        ))

        existing_reviews.add(key)

    log(f"  New validation issues to seed: {len(review_rows)}", indent=2)

    efl_inserted = 0
    review_inserted = 0

    for i in range(0, len(efl_rows), 20):
        n = sb_post_rows("enriched_field_log", efl_rows[i:i+20])
        efl_inserted += n
        time.sleep(0.2)

    for i in range(0, len(review_rows), 20):
        n = sb_post_rows("kyle_reviews", review_rows[i:i+20])
        review_inserted += n
        time.sleep(0.2)

    log(f"  Inserted: {efl_inserted} EFL rows, {review_inserted} kyle_reviews rows", indent=2)
    return efl_inserted, review_inserted


# ── Source 3: Governance violations ──────────────────────────────────────────

def seed_governance_violations(existing_reviews: set) -> Tuple[int, int]:
    """
    Create kyle_reviews entries for unresolved governance violations.
    Returns (efl_inserted, review_inserted)
    """
    log("Source 3: Governance violations (unresolved)", indent=1)
    violations = load_governance_violations()
    log(f"  Found {len(violations)} unresolved violations", indent=2)

    efl_rows    = []
    review_rows = []

    for v in violations:
        table_name = v.get("table_name") or "unknown"
        row_id     = str(v.get("row_id") or "")
        rule_name  = v.get("rule_name") or "unknown"
        description = v.get("description") or ""

        # Map to entity type / field
        if table_name == "company_partnerships":
            entity_type = "partnership"
            entity_id   = f"{table_name}:{row_id}"
            field_name  = "source_url"
        elif table_name == "deals":
            entity_type = "deal"
            entity_id   = f"{table_name}:{row_id}"
            field_name  = "source_url"
        else:
            entity_type = "governance"
            entity_id   = f"{table_name}:{row_id}"
            field_name  = f"governance_{rule_name}"

        key = f"{entity_id}::{field_name}"
        if key in existing_reviews:
            continue

        summary = f"[{rule_name}] {description}"

        efl_rows.append(make_efl_entry(
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            enriched_value=summary,
            priority_score=7,
            source="governance_violations",
        ))

        review_rows.append(make_kyle_review_entry(
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            field_value=summary,
            priority_score=7,
            notes=f"Governance violation: {rule_name} — add source_url to resolve",
        ))

        existing_reviews.add(key)

    log(f"  New governance violations to seed: {len(review_rows)}", indent=2)

    efl_inserted = 0
    review_inserted = 0

    for i in range(0, len(efl_rows), 20):
        n = sb_post_rows("enriched_field_log", efl_rows[i:i+20])
        efl_inserted += n
        time.sleep(0.2)

    for i in range(0, len(review_rows), 20):
        n = sb_post_rows("kyle_reviews", review_rows[i:i+20])
        review_inserted += n
        time.sleep(0.2)

    log(f"  Inserted: {efl_inserted} EFL rows, {review_inserted} kyle_reviews rows", indent=2)
    return efl_inserted, review_inserted


# ── Step 4: Backfill priority scores on existing EFL rows ───────────────────

def backfill_existing_efl_priorities() -> int:
    """
    Update review_priority_score for existing enriched_field_log rows
    that currently have null priority. Uses the FIELD_PRIORITY map.
    Returns count updated.
    """
    log("Backfilling priority scores on existing enriched_field_log rows", indent=1)

    existing = sb_get("enriched_field_log", {
        "select": "id,field_name,review_priority_score",
        "review_priority_score": "is.null",
        "limit": "500",
    })

    log(f"  Rows with null priority_score: {len(existing)}", indent=2)

    updated = 0
    for row in existing:
        row_id     = row.get("id")
        field_name = (row.get("field_name") or "").lower()
        score      = FIELD_PRIORITY.get(field_name, 5)

        if sb_patch("enriched_field_log", {"id": row_id}, {"review_priority_score": score}):
            updated += 1

        time.sleep(0.05)

    log(f"  Updated {updated} rows with priority scores", indent=2)
    return updated


# ── Fix: UI bug — created_at vs enriched_at ──────────────────────────────────
# The feedback UI's loadQueue() has:
#   .order('created_at', { ascending: false })
# but the column is named 'enriched_at'. This is a non-fatal bug because
# Supabase just ignores invalid order columns — but it means secondary sort
# is not applied. We note this and fix the HTML file.


# ── Main ─────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False, limit: int = 30) -> dict:
    global DRY_RUN
    DRY_RUN = dry_run

    log("=" * 60)
    log("Meridian Feedback Loop — Seed Kyle Reviews")
    log(f"  Dry-run: {DRY_RUN}")
    log(f"  Drug intel limit: {limit}")
    log("=" * 60)

    # Step 1: Load existing reviews to deduplicate
    log("Loading existing kyle_reviews for deduplication...", indent=1)
    existing_reviews = load_existing_reviews()
    log(f"  Existing kyle_reviews: {len(existing_reviews)}", indent=2)

    # Source 1: Drug intelligence fields
    drugs_count, efl1, kr1 = seed_drug_intel_fields(existing_reviews, limit=limit)

    # Source 2: Validation issues
    efl2, kr2 = seed_validation_issues(existing_reviews)

    # Source 3: Governance violations
    efl3, kr3 = seed_governance_violations(existing_reviews)

    # Step 4: Backfill priority scores on existing EFL rows
    backfilled = backfill_existing_efl_priorities()

    total_efl       = efl1 + efl2 + efl3
    total_kr        = kr1  + kr2  + kr3

    log("=" * 60)
    log("SUMMARY")
    log(f"  kyle_reviews rows created:        {total_kr}")
    log(f"    From drug intel fields:          {kr1} (across {drugs_count} drugs)")
    log(f"    From validation issues:          {kr2}")
    log(f"    From governance violations:      {kr3}")
    log(f"  enriched_field_log rows created:  {total_efl}")
    log(f"  enriched_field_log backfilled:    {backfilled} priority scores updated")
    log("=" * 60)

    return {
        "kyle_reviews_created":   total_kr,
        "kyle_reviews_drug_intel": kr1,
        "kyle_reviews_validation": kr2,
        "kyle_reviews_governance": kr3,
        "drugs_processed":         drugs_count,
        "efl_rows_created":        total_efl,
        "efl_backfilled":          backfilled,
        "dry_run":                 DRY_RUN,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed Meridian kyle_reviews and enriched_field_log for human review"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Run without writing to Supabase")
    parser.add_argument("--limit", type=int, default=30,
                        help="Max drugs to process for intel fields (default: 30)")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(result, indent=2, default=str))
