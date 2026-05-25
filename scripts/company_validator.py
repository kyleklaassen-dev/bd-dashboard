#!/usr/bin/env python3
"""
Ailux BD Platform — Company Profile Completeness Validator
===========================================================
Checks every company record against a set of completeness rules and writes
results to drug_validation_results (reusing the validation infrastructure
with check_type='company_*') so they appear in the existing review queue.

DESIGN PRINCIPLE:
  A company is "production-ready" when all P0 checks pass.
  P1 checks are quality improvements. P2 checks are optional enrichment.

CHECKS:

  P0 — Blocking (severity: high)
  ──────────────────────────────
  company_type_missing     — company_type is null or empty
  status_missing           — status is null or empty
  hq_missing               — both hq_city and hq_country are null
  geography_missing        — geography is null

  P1 — Quality (severity: medium)
  ────────────────────────────────
  ta_focus_missing         — neither ta_focus_1 nor ta_focus_2 is set
                             (waived for: CRO, technology, platform company types)
  alias_missing            — company has zero rows in company_aliases
  ownership_incomplete     — has parent_company_id but ownership_type is null
  acquired_parent_missing  — acquired_by is set but parent_company_id is null
  no_drugs_linked          — no drugs have company_id = this company
                             (waived for: acquired companies — drugs folded into parent)

  P2 — Enrichment (severity: low)
  ────────────────────────────────
  ticker_missing           — ticker is null (waived for private companies,
                             partnerships, acquired companies)
  tagline_missing          — tagline/insight_text is null
  last_verified_stale      — last_verified is null or > 90 days ago

OUTPUTS:
  drug_validation_results  — one row per (company_id, check_type) stored as
                             drug_id=company_id so the existing review UI sees them
  stdout                   — summary table, P0 failures first

USAGE:
  python scripts/company_validator.py               # all companies
  python scripts/company_validator.py --company ailux
  python scripts/company_validator.py --dry-run     # no DB writes
  python scripts/company_validator.py --p0-only     # blocking checks only
  python scripts/company_validator.py --summary     # counts only, no row detail

ENVIRONMENT:
  SUPABASE_URL         — https://tghntyofptvfhmtchwcv.supabase.co
  SUPABASE_SERVICE_KEY — service role key (falls back to anon key)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any

import requests

# ── Config ──────────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
SUPABASE_KEY = os.environ.get(
    "SUPABASE_SERVICE_KEY",
    os.environ.get("SUPABASE_ANON_KEY", ""),
)

# Fallback: read from workspace files
if not SUPABASE_KEY:
    _key_paths = [
        os.path.join(os.path.dirname(__file__), "..", ".supabase_service_key"),
        os.path.join(os.path.dirname(__file__), "..", ".supabase_anon_key"),
    ]
    for _p in _key_paths:
        _p = os.path.abspath(_p)
        if os.path.exists(_p):
            with open(_p) as _f:
                SUPABASE_KEY = _f.read().strip()
            break

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

STALE_DAYS = 90

# company_type values that don't need ta_focus or ticker
CRO_TYPES = {"cro", "technology", "platform", "ai", "contract_research", "tool", "service"}

# Severity by check_type
SEVERITY = {
    "company_type_missing":       "high",
    "status_missing":             "high",
    "hq_missing":                 "high",
    "geography_missing":          "high",
    "ta_focus_missing":           "medium",
    "alias_missing":              "medium",
    "ownership_incomplete":       "medium",
    "acquired_parent_missing":    "medium",
    "no_drugs_linked":            "medium",
    "ticker_missing":             "low",
    "tagline_missing":            "low",
    "last_verified_stale":        "low",
}

PRIORITY = {"high": 1, "medium": 2, "low": 3}


# ── Supabase helpers ─────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None) -> list[dict]:
    r = requests.get(f"{BASE}/{path}", headers=HEADERS, params=params or {})
    r.raise_for_status()
    return r.json()


def _patch_validation(company_id: str, check_type: str, payload: dict) -> None:
    """Upsert a row into drug_validation_results (drug_id=company_id)."""
    row = {
        "drug_id": company_id,
        "check_type": check_type,
        "check_status": "needs_review",
        "severity": SEVERITY.get(check_type, "medium"),
        "details": json.dumps(payload),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "company_validator",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    r = requests.post(
        f"{BASE}/drug_validation_results",
        headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
        json=row,
    )
    if r.status_code not in (200, 201, 204):
        print(f"  [WARN] DB write failed for ({company_id}, {check_type}): {r.status_code} {r.text[:200]}")


def _clear_resolved(company_id: str, check_type: str) -> None:
    """Mark a previously flagged issue as resolved."""
    r = requests.patch(
        f"{BASE}/drug_validation_results",
        headers={**HEADERS, "Prefer": "return=minimal"},
        params={"drug_id": f"eq.{company_id}", "check_type": f"eq.{check_type}"},
        json={"check_status": "resolved", "updated_at": datetime.now(timezone.utc).isoformat()},
    )
    # 204 or 200 = fine; 404 = no row existed = also fine


# ── Check functions ──────────────────────────────────────────────────────────

def check_company(company: dict, aliases_by_company: dict, drug_counts: dict) -> list[dict]:
    """
    Run all checks for a single company. Returns list of conflict dicts.
    Each dict: {check_type, severity, message, details}
    """
    cid = company["id"]
    ctype = (company.get("company_type") or "").lower().strip()
    status = (company.get("status") or "").lower().strip()
    is_acquired = status == "acquired"
    is_cro_type = ctype in CRO_TYPES

    issues = []

    def flag(check_type: str, message: str, details: dict | None = None):
        issues.append({
            "check_type": check_type,
            "severity": SEVERITY[check_type],
            "message": message,
            "details": details or {},
        })

    # ── P0: Blocking ────────────────────────────────────────────────────────

    if not ctype:
        flag("company_type_missing", "company_type is null or empty",
             {"company_id": cid, "name": company.get("name")})

    if not status:
        flag("status_missing", "status is null or empty",
             {"company_id": cid, "name": company.get("name")})

    hq_city = company.get("hq_city") or ""
    hq_country = company.get("hq_country") or ""
    if not hq_city and not hq_country:
        flag("hq_missing", "Both hq_city and hq_country are null",
             {"company_id": cid, "name": company.get("name")})

    if not company.get("geography"):
        flag("geography_missing", "geography is null",
             {"company_id": cid, "name": company.get("name")})

    # ── P1: Quality ──────────────────────────────────────────────────────────

    ta1 = company.get("ta_focus_1") or ""
    ta2 = company.get("ta_focus_2") or ""
    if not ta1 and not ta2 and not is_cro_type:
        flag("ta_focus_missing", "Neither ta_focus_1 nor ta_focus_2 is set",
             {"company_id": cid, "name": company.get("name"), "company_type": ctype,
              "note": "Waived for CRO/technology/platform types"})

    company_aliases = aliases_by_company.get(cid, [])
    if not company_aliases:
        flag("alias_missing", "No rows in company_aliases for this company",
             {"company_id": cid, "name": company.get("name"),
              "suggested_action": "Add at least one alias (primary name preferred)"})

    parent_id = company.get("parent_company_id")
    ownership_type = company.get("ownership_type")
    if parent_id and not ownership_type:
        flag("ownership_incomplete", "parent_company_id set but ownership_type is null",
             {"company_id": cid, "name": company.get("name"),
              "parent_company_id": parent_id,
              "suggested_action": "Set ownership_type: subsidiary|majority-owned|minority-invested|partnership|division"})

    acquired_by = company.get("acquired_by")
    if acquired_by and not parent_id:
        flag("acquired_parent_missing", "acquired_by is set but parent_company_id is null",
             {"company_id": cid, "name": company.get("name"),
              "acquired_by": acquired_by,
              "suggested_action": "Set parent_company_id = " + acquired_by})

    # Only flag no_drugs_linked for active (non-acquired) companies
    if not is_acquired:
        drug_count = drug_counts.get(cid, 0)
        if drug_count == 0:
            flag("no_drugs_linked",
                 "No drugs have company_id = this company (active company with empty pipeline)",
                 {"company_id": cid, "name": company.get("name"), "status": status,
                  "note": "May be intentional for new/CRO companies; review if therapeutics type"})

    # ── P2: Enrichment ───────────────────────────────────────────────────────

    ticker = company.get("ticker") or ""
    if not ticker and not is_acquired and not is_cro_type:
        flag("ticker_missing", "ticker is null (expected for public/large-cap companies)",
             {"company_id": cid, "name": company.get("name"),
              "note": "Waived for private, acquired, CRO/platform companies"})

    tagline = company.get("tagline") or company.get("insight_text") or ""
    if not tagline:
        flag("tagline_missing", "tagline and insight_text are both null",
             {"company_id": cid, "name": company.get("name")})

    last_verified_str = company.get("last_verified") or ""
    if not last_verified_str:
        flag("last_verified_stale", "last_verified is null (never verified)",
             {"company_id": cid, "name": company.get("name")})
    else:
        try:
            lv_str = last_verified_str.replace("Z", "+00:00")
            lv = datetime.fromisoformat(lv_str)
            if lv.tzinfo is None:
                lv = lv.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - lv).days
            if age > STALE_DAYS:
                flag("last_verified_stale",
                     f"last_verified is {age} days ago (threshold: {STALE_DAYS})",
                     {"company_id": cid, "name": company.get("name"),
                      "last_verified": last_verified_str, "age_days": age})
        except ValueError:
            pass

    return issues


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Company profile completeness validator")
    parser.add_argument("--company", help="Validate a single company by ID")
    parser.add_argument("--dry-run", action="store_true", help="Detect only, no DB writes")
    parser.add_argument("--p0-only", action="store_true", help="Show only P0 (high severity) failures")
    parser.add_argument("--summary", action="store_true", help="Print counts only, no row detail")
    args = parser.parse_args()

    dry_run = args.dry_run
    if dry_run:
        print("DRY RUN — no database writes\n")

    # ── Load data ────────────────────────────────────────────────────────────

    print("Loading companies...", end=" ", flush=True)
    if args.company:
        companies = _get("companies", {"id": f"eq.{args.company}"})
    else:
        companies = _get("companies", {"limit": 1000})
    print(f"{len(companies)} loaded")

    print("Loading aliases...", end=" ", flush=True)
    aliases = _get("company_aliases", {"limit": 5000, "select": "company_id,alias_name,alias_type"})
    aliases_by_company: dict[str, list] = {}
    for a in aliases:
        aliases_by_company.setdefault(a["company_id"], []).append(a)
    print(f"{len(aliases)} loaded")

    print("Loading drug company_id counts...", end=" ", flush=True)
    drugs = _get("drugs", {"limit": 2000, "select": "id,company_id"})
    drug_counts: dict[str, int] = {}
    for d in drugs:
        cid = d.get("company_id")
        if cid:
            drug_counts[cid] = drug_counts.get(cid, 0) + 1
    print(f"{len(drugs)} drugs across {len(drug_counts)} companies\n")

    # ── Run checks ───────────────────────────────────────────────────────────

    all_issues: list[dict] = []  # {company_id, company_name, check_type, severity, message, details}

    for company in companies:
        cid = company["id"]
        issues = check_company(company, aliases_by_company, drug_counts)

        if args.p0_only:
            issues = [i for i in issues if i["severity"] == "high"]

        for issue in issues:
            all_issues.append({
                "company_id": cid,
                "company_name": company.get("name", cid),
                **issue,
            })

        # Write passing check_types as resolved; write failures as needs_review
        if not dry_run:
            failed_checks = {i["check_type"] for i in issues}
            all_checks = set(SEVERITY.keys())
            for ct in all_checks - failed_checks:
                _clear_resolved(cid, ct)
            for issue in issues:
                _patch_validation(cid, issue["check_type"], {
                    "company_id": cid,
                    "company_name": company.get("name"),
                    "message": issue["message"],
                    **issue["details"],
                })

    # ── Report ───────────────────────────────────────────────────────────────

    if not all_issues:
        print("✓ All companies pass all checks.")
        return

    # Sort by severity priority, then company_id
    all_issues.sort(key=lambda x: (PRIORITY[x["severity"]], x["company_id"]))

    # Summary counts
    by_sev = {"high": 0, "medium": 0, "low": 0}
    by_check: dict[str, int] = {}
    for i in all_issues:
        by_sev[i["severity"]] += 1
        by_check[i["check_type"]] = by_check.get(i["check_type"], 0) + 1

    print("=" * 70)
    print("COMPANY VALIDATOR RESULTS")
    print("=" * 70)
    print(f"  HIGH (P0 blocking):   {by_sev['high']:3d} issues")
    print(f"  MEDIUM (P1 quality):  {by_sev['medium']:3d} issues")
    print(f"  LOW (P2 enrichment):  {by_sev['low']:3d} issues")
    print(f"  TOTAL:                {len(all_issues):3d} issues across {len(companies)} companies")
    print()

    print("─" * 70)
    print("BREAKDOWN BY CHECK TYPE")
    print("─" * 70)
    for ct, count in sorted(by_check.items(), key=lambda x: (PRIORITY[SEVERITY[x[0]]], -x[1])):
        sev_label = SEVERITY[ct].upper().ljust(8)
        print(f"  [{sev_label}] {ct:35s}  {count:3d} companies")
    print()

    if args.summary:
        return

    print("─" * 70)
    print("ISSUE DETAIL")
    print("─" * 70)

    current_sev = None
    for issue in all_issues:
        sev = issue["severity"]
        if sev != current_sev:
            current_sev = sev
            label = {"high": "P0 — BLOCKING", "medium": "P1 — QUALITY", "low": "P2 — ENRICHMENT"}[sev]
            print(f"\n{'═' * 60}")
            print(f"  {label}")
            print(f"{'═' * 60}")

        cid = issue["company_id"]
        cname = issue["company_name"]
        ct = issue["check_type"]
        msg = issue["message"]
        print(f"\n  [{cid}] {cname}")
        print(f"    check : {ct}")
        print(f"    msg   : {msg}")
        details = issue.get("details", {})
        suggested = details.get("suggested_action")
        if suggested:
            print(f"    fix   : {suggested}")

    print()
    status_line = "DRY RUN (no DB writes)" if dry_run else "Results written to drug_validation_results"
    print(f"Status: {status_line}")


if __name__ == "__main__":
    main()
