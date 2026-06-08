#!/usr/bin/env python3
"""
Ailux BD Platform — Company Freshness Refresh
==============================================
Automatically sets last_verified on company records that are null or stale,
without overwriting any curated field.

NEVER TOUCHES: company_type, geography, hq_city, hq_country, ta_focus_1,
ta_focus_2, ownership_type, parent_company_id, coverage_status, name,
ticker, status, acquired_by (or anything in company_aliases).

VERIFICATION TIERS (applied in order per company):

  Tier 1 — enrichment_pipeline_bootstrap
    last_verified is null or stale AND last_enriched_at is within FRESH_DAYS.
    Sets last_verified = last_enriched_at::date.
    Rationale: the enrichment pipeline explicitly reviewed the company's data.

  Tier 2 — reference_entity_auto_verify
    last_verified is null or stale AND coverage_status is reference, planned,
    or orphan AND no recent last_enriched_at.
    Sets last_verified = today.
    Rationale: these are static reference/attribution entities. Their structure
    was validated in the company governance session (2026-05-25). Future runs
    confirm they still exist in the DB unchanged.

  Tier 3 — skip (needs_manual_review)
    Active company with no recent enrichment and no reference-entity status.
    Does NOT update last_verified. Writes a drug_validation_results flag.

OUTPUTS:
  companies.last_verified      — updated where a tier 1 or 2 source exists
  drug_validation_results      — one row per company with check_type=
                                 'company_freshness_refreshed' (pass) or
                                 'company_freshness_needs_review' (skip)
  stdout                       — per-company log + summary table
  logs/company_refresh_<ts>.jsonl — JSONL log of every action (one line/company)

USAGE:
  python scripts/refresh_company_verified.py            # all stale/null companies
  python scripts/refresh_company_verified.py --dry-run  # no DB writes
  python scripts/refresh_company_verified.py --company ailux
  python scripts/refresh_company_verified.py --all      # all 101, not just stale

ENVIRONMENT:
  SUPABASE_URL         — https://tghntyofptvfhmtchwcv.supabase.co
  SUPABASE_SERVICE_KEY — service role key
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

# NOTE: dirname(dirname(__file__)) resolved to scripts/, not the repo root,
# after the scripts/ reorg moved this file into scripts/sync/ —
# load_credentials locates the repo root correctly regardless of subfolder depth.
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _common import load_credentials  # noqa: E402
import _db                              # noqa: E402

# ── Config ──────────────────────────────────────────────────────────────────

SUPABASE_URL, SUPABASE_KEY, _ = load_credentials(require_anthropic=False)
_db.init_db(SUPABASE_URL, SUPABASE_KEY)

# Company is "stale" if last_verified is older than this many days
STALE_DAYS = 90

# last_enriched_at is considered "fresh" if within this many days
FRESH_DAYS = 90

# coverage_status values eligible for tier-2 auto-verify
REFERENCE_STATUSES = {"reference", "planned", "orphan"}

# Fields that must NEVER be modified by this script
PROTECTED_FIELDS = {
    "company_type", "geography", "hq_city", "hq_country",
    "ta_focus_1", "ta_focus_2", "ownership_type", "parent_company_id",
    "coverage_status", "name", "ticker", "status", "acquired_by",
    "id", "created_at",
}

TODAY = date.today().isoformat()
NOW = datetime.now(timezone.utc)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None) -> list[dict]:
    return _db.sb_get(path, params or {})


def _patch_company(company_id: str, payload: dict) -> bool:
    """Update ONLY last_verified on a company. Refuses to touch protected fields."""
    safe = {k: v for k, v in payload.items() if k not in PROTECTED_FIELDS}
    if not safe:
        return False
    return _db.sb_patch("companies", safe, {"id": f"eq.{company_id}"})


def _write_validation(company_id: str, check_type: str, severity: str, details: dict) -> None:
    row = {
        "drug_id": company_id,
        "check_type": check_type,
        "check_status": "pass" if "refreshed" in check_type else "needs_review",
        "severity": severity,
        "details": json.dumps(details),
        "checked_at": NOW.isoformat(),
        "created_by": "refresh_company_verified",
        "updated_at": NOW.isoformat(),
    }
    _db.sb_upsert("drug_validation_results", row)


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date()
    except (ValueError, TypeError):
        return None


def _days_ago(d: date | None) -> int | None:
    if d is None:
        return None
    return (date.today() - d).days


def _ensure_log_dir() -> Path:
    script_dir = Path(__file__).parent
    log_dir = script_dir.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir


# ── Core logic ───────────────────────────────────────────────────────────────

def determine_action(company: dict) -> dict:
    """
    Decide what to do for a single company.
    Returns: {action, new_last_verified, method, source, reason, skip_reason}
    """
    cid = company["id"]
    coverage = (company.get("coverage_status") or "active").lower()
    last_verified = _parse_date(company.get("last_verified"))
    last_enriched_at = _parse_date(company.get("last_enriched_at"))
    lv_days = _days_ago(last_verified)
    le_days = _days_ago(last_enriched_at)

    is_stale = (last_verified is None) or (lv_days is not None and lv_days > STALE_DAYS)

    if not is_stale:
        return {
            "action": "skip_current",
            "new_last_verified": None,
            "method": None,
            "source": None,
            "reason": f"last_verified is current ({lv_days}d ago, threshold {STALE_DAYS}d)",
            "skip_reason": None,
        }

    # Tier 1: recent last_enriched_at
    if le_days is not None and le_days <= FRESH_DAYS:
        return {
            "action": "update",
            "new_last_verified": last_enriched_at.isoformat(),
            "method": "enrichment_pipeline_bootstrap",
            "source": "last_enriched_at",
            "reason": f"last_enriched_at is {le_days}d ago — within {FRESH_DAYS}d fresh window",
            "skip_reason": None,
        }

    # Tier 2: reference/planned/orphan with no recent enrichment
    if coverage in REFERENCE_STATUSES:
        return {
            "action": "update",
            "new_last_verified": TODAY,
            "method": "reference_entity_auto_verify",
            "source": "coverage_status=" + coverage,
            "reason": f"Static reference entity; structure validated in company governance session",
            "skip_reason": None,
        }

    # Tier 3: active company, no recent enrichment — skip
    return {
        "action": "skip_needs_review",
        "new_last_verified": None,
        "method": None,
        "source": None,
        "reason": None,
        "skip_reason": (
            f"Active company; last_verified={'null' if last_verified is None else lv_days}d ago; "
            f"last_enriched_at={'null' if last_enriched_at is None else str(le_days) + 'd ago'}. "
            "Needs manual verification or enrichment pipeline run."
        ),
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Refresh company last_verified")
    parser.add_argument("--dry-run", action="store_true", help="No DB writes; show what would happen")
    parser.add_argument("--company", help="Refresh a single company by ID")
    parser.add_argument("--all", dest="all_companies", action="store_true",
                        help="Process all companies, not just stale/null ones")
    args = parser.parse_args()

    dry_run = args.dry_run
    if dry_run:
        print("DRY RUN — no database writes\n")

    # ── Load ────────────────────────────────────────────────────────────────

    print("Loading companies...", end=" ", flush=True)
    if args.company:
        companies = _get("companies", {"id": f"eq.{args.company}"})
    else:
        companies = _get("companies", {"limit": 1000})
    print(f"{len(companies)} loaded")

    # ── Process ─────────────────────────────────────────────────────────────

    log_dir = _ensure_log_dir()
    ts = NOW.strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"company_refresh_{ts}.jsonl"

    results = {
        "updated": [],
        "skip_current": [],
        "skip_needs_review": [],
        "error": [],
    }

    print(f"\n{'Company':<35} {'Coverage':<12} {'LV Age':>8}  {'Action'}")
    print(f"{'-'*35} {'-'*12} {'-'*8}  {'-'*40}")

    for company in sorted(companies, key=lambda x: x["name"]):
        cid = company["id"]
        name = company.get("name", cid)
        coverage = (company.get("coverage_status") or "active").lower()
        lv_date = _parse_date(company.get("last_verified"))
        lv_days = _days_ago(lv_date)
        lv_age_str = f"{lv_days}d" if lv_days is not None else "null"

        decision = determine_action(company)
        action = decision["action"]

        log_entry = {
            "company_id": cid,
            "company_name": name,
            "coverage_status": coverage,
            "previous_last_verified": company.get("last_verified"),
            "last_enriched_at": company.get("last_enriched_at"),
            "action": action,
            "new_last_verified": decision["new_last_verified"],
            "method": decision["method"],
            "source": decision["source"],
            "reason": decision.get("reason") or decision.get("skip_reason"),
            "timestamp": NOW.isoformat(),
            "dry_run": dry_run,
        }

        if action == "skip_current":
            results["skip_current"].append(cid)
            if args.all_companies:
                print(f"  {name[:35]:<35} {coverage:<12} {lv_age_str:>8}  CURRENT")
            # Don't log current-skip unless --all
            continue

        elif action == "update":
            action_label = f"→ {decision['new_last_verified']} [{decision['method']}]"
            print(f"  {name[:35]:<35} {coverage:<12} {lv_age_str:>8}  UPDATE {action_label}")

            if not dry_run:
                ok = _patch_company(cid, {
                    "last_verified": decision["new_last_verified"],
                    "updated_at": NOW.isoformat(),
                })
                if ok:
                    results["updated"].append(cid)
                    _write_validation(cid, "company_freshness_refreshed", "low", {
                        "company_id": cid,
                        "previous_last_verified": company.get("last_verified"),
                        "new_last_verified": decision["new_last_verified"],
                        "method": decision["method"],
                        "source": decision["source"],
                    })
                else:
                    results["error"].append(cid)
                    print(f"    [ERROR] patch failed for {cid}")
                    log_entry["action"] = "error"
            else:
                results["updated"].append(cid)

        elif action == "skip_needs_review":
            print(f"  {name[:35]:<35} {coverage:<12} {lv_age_str:>8}  SKIP — {decision['skip_reason'][:60]}")
            results["skip_needs_review"].append(cid)

            if not dry_run:
                _write_validation(cid, "company_freshness_needs_review", "medium", {
                    "company_id": cid,
                    "last_verified": company.get("last_verified"),
                    "last_enriched_at": company.get("last_enriched_at"),
                    "skip_reason": decision["skip_reason"],
                })

        # Write log entry
        if not dry_run or action != "skip_current":
            with open(log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")

    # ── Summary ─────────────────────────────────────────────────────────────

    print()
    print("=" * 70)
    print("REFRESH SUMMARY")
    print("=" * 70)
    print(f"  Updated (last_verified set)    : {len(results['updated'])}")
    print(f"  Skipped (already current)      : {len(results['skip_current'])}")
    print(f"  Skipped (needs manual review)  : {len(results['skip_needs_review'])}")
    if results["error"]:
        print(f"  Errors                         : {len(results['error'])}")

    if results["skip_needs_review"]:
        print()
        print("  Companies needing manual verification:")
        for cid in results["skip_needs_review"]:
            co = next(c for c in companies if c["id"] == cid)
            print(f"    [{cid}] {co.get('name')} — run enrichment pipeline or verify manually")

    status_line = "DRY RUN — no changes written" if dry_run else f"Log: {log_path}"
    print()
    print(f"  {status_line}")


if __name__ == "__main__":
    main()
