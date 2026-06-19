#!/usr/bin/env python3
"""
human_queue_builder.py — builds the human review queue (weekend_sprint Phase F4).

Orchestrator after the §3 split: the load/build/write/promote pipeline + run(),
over the dry-run-gated Supabase layer and scoring helpers in human_queue_base.
Stays the entrypoint weekend_sprint loads + calls run().

USAGE (standalone):
  python scripts/human_queue_builder.py
  python scripts/human_queue_builder.py --dry-run
"""
import os
import sys
import json
import time
import datetime
import argparse
from typing import Optional, List, Dict, Tuple
import requests

# weekend_sprint loads this via spec_from_file_location (Phase F4), which does NOT put
# scripts/ on sys.path — bootstrap so the sibling import below resolves in both paths.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from human_queue_base import (
    sb_get, sb_post, sb_patch, sb_upsert, table_exists, log,
    normalize_stage, is_clinical, days_since, compute_priority_score,
    HIGH_VALUE_FIELDS, CATALYST_HORIZON_DAYS, NOW_DT, NOW_ISO, TODAY, RUN_ID,
    set_dry_run, is_dry_run,
)
# ── Data loading ──────────────────────────────────────────────────────────────

def load_pending_entries(limit: int = 500) -> List[Dict]:
    """Load pending enriched_field_log entries."""
    if not table_exists("enriched_field_log"):
        log("  enriched_field_log not found", indent=2)
        return []
    try:
        entries = sb_get("enriched_field_log", {
            "select": (
                "id,entity_id,entity_type,field_name,enriched_value,old_value,"
                "field_label,model_confidence,confidence_score,was_changed,enriched_at,"
                "model_name"
            ),
            "field_label": "eq.pending",
            "limit": str(limit),
            "order": "enriched_at.desc",
        })
        log(f"  Pending enriched_field_log entries: {len(entries)}", indent=2)
        return entries
    except Exception as e:
        log(f"  enriched_field_log query failed: {e}", indent=2)
        return []


def load_drug_context() -> Dict[str, Dict]:
    """Load drug overlap, stage for priority scoring."""
    try:
        drugs = sb_get("drugs", {
            "select": "id,name,stage,overlap",
            "limit": "1000",
        })
        return {str(d["id"]): d for d in drugs}
    except Exception as e:
        log(f"  Drug context load failed: {e}", indent=2)
        return {}


def load_upcoming_catalyst_drug_ids() -> set:
    """Load drug IDs with catalyst events in the next CATALYST_HORIZON_DAYS."""
    if not table_exists("catalyst_calendar"):
        return set()
    horizon_date = (NOW_DT + datetime.timedelta(days=CATALYST_HORIZON_DAYS)).strftime("%Y-%m-%d")
    try:
        cats = sb_get("catalyst_calendar", {
            "select": "catalyst_drug_id,drug_id,expected_date",
            "expected_date": f"lte.{horizon_date}",
            "expected_date.gte": TODAY,
            "limit": "200",
        })
        drug_ids: set = set()
        for cat in cats:
            for f in ["catalyst_drug_id", "drug_id"]:
                val = cat.get(f)
                if val:
                    drug_ids.add(str(val))
        return drug_ids
    except Exception as e:
        # Supabase may not support compound filter syntax in params like this
        # Try simpler query and filter in Python
        try:
            cats = sb_get("catalyst_calendar", {
                "select": "catalyst_drug_id,drug_id,expected_date",
                "limit": "300",
            })
            drug_ids = set()
            for cat in cats:
                exp_date = cat.get("expected_date") or ""
                if exp_date and TODAY <= exp_date <= horizon_date:
                    for f in ["catalyst_drug_id", "drug_id"]:
                        val = cat.get(f)
                        if val:
                            drug_ids.add(str(val))
            return drug_ids
        except Exception:
            return set()


# ── Priority assignment and queue building ────────────────────────────────────

def build_queue(
    entries: List[Dict],
    drug_map: Dict[str, Dict],
    catalyst_ids: set,
) -> List[Dict]:
    """
    Score each entry, sort descending, assign queue positions.
    Returns sorted list with score and position added.
    """
    scored: List[Tuple[int, Dict]] = []

    for entry in entries:
        score = compute_priority_score(entry, drug_map, catalyst_ids)
        scored.append((score, entry))

    # Sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)

    result = []
    for position, (score, entry) in enumerate(scored, start=1):
        result.append({
            **entry,
            "review_priority_score":    score,
            "review_queue_position":    position,
        })

    return result


def check_efl_has_priority_columns() -> bool:
    """Check if enriched_field_log has the review_priority_score column."""
    try:
        # Try a PATCH with the new columns on a non-existent ID to test schema
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/enriched_field_log",
            headers=SB_HEADERS,
            params={"id": "eq.0"},  # ID 0 won't exist
            json={"review_priority_score": 0, "review_queue_position": 0},
            timeout=10,
        )
        # 404-style schema error = column doesn't exist
        if r.status_code == 400:
            body = r.json() if r.content else {}
            if "review_priority_score" in str(body):
                return False
        return True
    except Exception:
        return True  # Assume exists; real errors will surface at write time


def write_queue_to_db(queue: List[Dict], batch_size: int = 50) -> int:
    """
    Write review_priority_score and review_queue_position back to enriched_field_log.
    Gracefully skips if columns don't exist yet (DDL migration pending).
    Batches PATCH calls for efficiency.
    """
    if not queue:
        return 0

    # Check if columns exist first
    has_cols = check_efl_has_priority_columns()
    if not has_cols:
        log(
            "  enriched_field_log missing review_priority_score column. "
            "Apply DDL migration (see source_verifier.py EFL_ALTER_SQL) then re-run.",
            indent=2
        )
        log("  Logging queue to stdout only (no DB write)", indent=2)
        for entry in queue[:20]:
            log(
                f"  [Q{entry['review_queue_position']}] "
                f"entity={entry.get('entity_id')} "
                f"field={entry.get('field_name')} "
                f"score={entry['review_priority_score']}",
                indent=3
            )
        return 0

    updated = 0
    for i in range(0, len(queue), batch_size):
        batch = queue[i:i + batch_size]
        for entry in batch:
            entry_id = entry.get("id")
            if not entry_id:
                continue
            try:
                sb_patch(
                    "enriched_field_log",
                    {"id": entry_id},
                    {
                        "review_priority_score": entry["review_priority_score"],
                        "review_queue_position": entry["review_queue_position"],
                    }
                )
                updated += 1
            except Exception as e:
                log(f"  PATCH failed for entry {entry_id}: {e}", indent=3)

        log(f"  Written batch {i // batch_size + 1}: {len(batch)} entries", indent=2)
        time.sleep(0.2)

    return updated


# ── Auto-promote stale pending labels ────────────────────────────────────────

def auto_promote_stale_pending(drug_map: Dict[str, Dict]) -> Dict:
    """
    Positive label promotion:
    - Enriched fields where field_label = 'pending'
    - enriched_at < NOW() - 14 days
    - entity has overlap IN ('Direct', 'Adjacent', 'Same-Space')
    → Auto-promote to 'confirmed'
    → Write to kyle_reviews with action='confirmed', label_source='auto_promoted'
    """
    log("Auto-promote: stale pending labels for tracked overlap drugs", indent=1)
    results = {"checked": 0, "promoted": 0}

    if not table_exists("enriched_field_log"):
        return results

    cutoff_14d = (NOW_DT - datetime.timedelta(days=14)).isoformat()

    try:
        stale_pending = sb_get("enriched_field_log", {
            "select": "id,entity_id,entity_type,field_name,enriched_value,enriched_at",
            "field_label": "eq.pending",
            "limit": "200",
        })

        promote_ids = []
        for entry in stale_pending:
            results["checked"] += 1
            entity_id = str(entry.get("entity_id") or "")
            entity_type = (entry.get("entity_type") or "").lower()

            # Check age (enriched_at column)
            ts = entry.get("enriched_at") or ""
            if not ts:
                continue
            age_days = days_since(ts)
            if age_days < 14:
                continue  # Not old enough

            # Check overlap for drugs
            if entity_type == "drug":
                drug = drug_map.get(entity_id, {})
                overlap = drug.get("overlap") or ""
                if overlap not in ("Direct", "Adjacent", "Same-Space"):
                    continue  # Only promote tracked overlap drugs
            elif entity_type in ("company", "company_profile"):
                # Allow company entries that are old enough
                pass
            else:
                continue  # Skip other entity types

            promote_ids.append(entry)

        log(f"  Eligible for auto-promote: {len(promote_ids)}", indent=2)

        for entry in promote_ids:
            # Update field_label to confirmed
            try:
                sb_patch(
                    "enriched_field_log",
                    {"id": entry["id"]},
                    {"field_label": "confirmed"}
                )
            except Exception as e:
                log(f"  Promote patch failed for {entry['id']}: {e}", indent=3)
                continue

            # Write to kyle_reviews if table exists
            if table_exists("kyle_reviews"):
                try:
                    sb_post("kyle_reviews", {
                        "entity_id":    str(entry.get("entity_id")),
                        "entity_type":  entry.get("entity_type"),
                        "field_name":   entry.get("field_name"),
                        "field_value":  str(entry.get("enriched_value") or "")[:500],
                        "action":       "confirmed",
                        "label_source": "auto_promoted",
                        "reviewed_at":  NOW_ISO,
                        "run_id":       RUN_ID,
                        "notes": (
                            f"Auto-promoted after {days_since(entry.get('enriched_at')):.0f} "
                            f"days in pending state for tracked overlap drug"
                        ),
                    })
                except Exception as e:
                    log(f"  kyle_reviews write failed: {e}", indent=3)

            results["promoted"] += 1
            log(
                f"  Promoted: entity={entry.get('entity_id')} "
                f"field={entry.get('field_name')}",
                indent=2
            )

    except Exception as e:
        log(f"  Auto-promote check failed: {e}", indent=2)

    log(f"  Promoted {results['promoted']} / {results['checked']} entries", indent=2)
    return results


# ── Main entry point ──────────────────────────────────────────────────────────

def run(dry_run: bool = False, limit: int = 500) -> Dict:
    set_dry_run(dry_run)

    log("Human Queue Builder — Tier 5 Meta Agent")
    log(f"Run ID: {RUN_ID}")
    log(f"Dry-run: {is_dry_run()}")

    # 1. Load data
    log("Step 1: Loading context data", indent=1)
    drug_map = load_drug_context()
    log(f"  Loaded {len(drug_map)} drugs", indent=2)

    catalyst_ids = load_upcoming_catalyst_drug_ids()
    log(f"  Loaded {len(catalyst_ids)} drugs with upcoming catalysts (<{CATALYST_HORIZON_DAYS}d)", indent=2)

    # 2. Load pending entries
    log("Step 2: Loading pending enriched_field_log entries", indent=1)
    entries = load_pending_entries(limit=limit)

    if not entries:
        log("  No pending entries found", indent=1)
        return {
            "total_pending": 0,
            "queued_for_review": 0,
            "avg_priority_score": 0,
        }

    # 3. Score and sort
    log("Step 3: Computing priority scores", indent=1)
    queue = build_queue(entries, drug_map, catalyst_ids)

    avg_score = sum(e["review_priority_score"] for e in queue) / len(queue) if queue else 0
    top_10 = queue[:10]

    log(f"  Entries scored: {len(queue)}", indent=2)
    log(f"  Average priority score: {avg_score:.1f}", indent=2)
    log(f"  Top-10 queue items:", indent=2)
    for e in top_10:
        log(
            f"    [{e['review_queue_position']}] "
            f"entity={e.get('entity_id')} "
            f"field={e.get('field_name')} "
            f"score={e['review_priority_score']}",
            indent=3
        )

    # 4. Write back to DB
    log("Step 4: Writing priority scores to enriched_field_log", indent=1)
    updated = write_queue_to_db(queue)
    log(f"  Updated {updated} entries", indent=2)

    # 5. Auto-promote stale pending labels
    log("Step 5: Auto-promoting stale pending labels", indent=1)
    promote_results = auto_promote_stale_pending(drug_map)

    # 6. Build summary
    summary = {
        "total_pending":        len(entries),
        "queued_for_review":    updated,
        "avg_priority_score":   round(avg_score, 1),
        "auto_promoted":        promote_results.get("promoted", 0),
        "top_priority_entity":  top_10[0].get("entity_id") if top_10 else None,
        "top_priority_field":   top_10[0].get("field_name") if top_10 else None,
        "top_priority_score":   top_10[0].get("review_priority_score") if top_10 else None,
    }

    log("=" * 60)
    log("Human Queue Builder Complete")
    log(f"  Total pending:       {summary['total_pending']}")
    log(f"  Queued for review:   {summary['queued_for_review']}")
    log(f"  Avg priority score:  {summary['avg_priority_score']}")
    log(f"  Auto-promoted:       {summary['auto_promoted']}")

    return summary


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Meridian Human Queue Builder — build Kyle's prioritized review queue"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Run without writing to Supabase")
    parser.add_argument("--limit", type=int, default=500,
                        help="Max enriched_field_log entries to process (default: 500)")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(result, indent=2, default=str))
