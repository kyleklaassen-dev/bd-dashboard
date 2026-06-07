#!/usr/bin/env python3
"""
Ailux BD Platform — Company Profile Completeness Validator
===========================================================
Checks every company record against completeness rules and writes results
to drug_validation_results (reusing the validation infrastructure with
check_type='company_*'). Also computes a Company Health Score (0-100)
for each company across six dimensions.

COVERAGE STATUS AWARENESS:
  Companies have a coverage_status field that controls validator behavior:
  - active    : has pipeline drugs (or expected to). All checks apply.
  - reference : strategic landscape reference (BMS, Biogen, etc.). P1
                no_drugs_linked check is waived.
  - planned   : pipeline ingestion planned. P1 no_drugs_linked is waived.
  - orphan    : no drugs, no strategic purpose. All checks apply.
                Candidates for removal.

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
                             (waived for: CRO, technology, platform types)
  alias_missing            — company has zero rows in company_aliases
  ownership_incomplete     — has parent_company_id but ownership_type is null
  acquired_parent_missing  — acquired_by is set but parent_company_id is null
  no_drugs_linked          — no drugs linked AND coverage_status is
                             'active' or 'orphan' (waived for reference/planned)

  P2 — Enrichment (severity: low)
  ────────────────────────────────
  ticker_missing           — ticker is null (waived for private, acquired,
                             CRO/platform, reference companies)
  tagline_missing          — tagline/insight_text is null
  last_verified_stale      — last_verified null or > 90 days ago

HEALTH SCORE (0–100):
  Six dimensions, each 0–100, equal weight (1/6 each):
  1. identity_score    — company_type + status set (50 each)
  2. geo_score         — geography (50) + hq_city|hq_country (50)
  3. alias_score       — has ≥1 alias (100); 0 otherwise
  4. ownership_score   — N/A for standalone (100); has parent→type set (100);
                         has parent→type missing (0); orphan (50)
  5. pipeline_score    — has drugs linked (100); reference/planned (70);
                         active/orphan with no drugs (0)
  6. freshness_score   — last_verified within 30d (100), 90d (70), 180d (40),
                         never/older (0)

OUTPUTS:
  drug_validation_results  — one row per (company_id, check_type)
  stdout                   — summary table + health score leaderboard

USAGE:
  python scripts/company_validator.py               # all companies
  python scripts/company_validator.py --company ailux
  python scripts/company_validator.py --dry-run     # no DB writes
  python scripts/company_validator.py --p0-only     # blocking checks only
  python scripts/company_validator.py --summary     # counts + scores only
  python scripts/company_validator.py --scores      # health scores only

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

# coverage_status values that waive the no_drugs_linked check
WAIVE_NO_DRUGS = {"reference", "planned"}

# company_type values that waive ta_focus and ticker checks
CRO_TYPES = {"cro", "technology", "platform", "ai", "contract_research",
             "tool", "service", "cdmo", "distribution", "state_owned", "tcm"}

# coverage_status values that waive the ticker check
REFERENCE_TYPES_FOR_TICKER = {"reference"}

SEVERITY = {
    "company_type_missing":    "high",
    "status_missing":          "high",
    "hq_missing":              "high",
    "geography_missing":       "high",
    "ta_focus_missing":        "medium",
    "alias_missing":           "medium",
    "ownership_incomplete":    "medium",
    "acquired_parent_missing": "medium",
    "no_drugs_linked":         "medium",
    "ticker_missing":          "low",
    "tagline_missing":         "low",
    "last_verified_stale":     "low",
}

PRIORITY = {"high": 1, "medium": 2, "low": 3}


# ── Supabase helpers ─────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None) -> list[dict]:
    r = requests.get(f"{BASE}/{path}", headers=HEADERS, params=params or {})
    r.raise_for_status()
    return r.json()


def _patch_validation(company_id: str, check_type: str, payload: dict) -> None:
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
        print(f"  [WARN] DB write failed ({company_id}, {check_type}): {r.status_code} {r.text[:200]}")


def _clear_resolved(company_id: str, check_type: str) -> None:
    requests.patch(
        f"{BASE}/drug_validation_results",
        headers={**HEADERS, "Prefer": "return=minimal"},
        params={"drug_id": f"eq.{company_id}", "check_type": f"eq.{check_type}"},
        json={"check_status": "resolved", "updated_at": datetime.now(timezone.utc).isoformat()},
    )


# ── Health score ─────────────────────────────────────────────────────────────

def compute_health_score(company: dict, has_aliases: bool, drug_count: int) -> dict:
    """
    Returns dict with per-dimension scores (0-100) and total (0-100).
    Six equal-weight dimensions.
    """
    ctype = (company.get("company_type") or "").lower()
    status = (company.get("status") or "").lower()
    coverage = (company.get("coverage_status") or "active").lower()
    is_acquired = status == "acquired"

    # 1. Identity score — company_type (50) + status (50)
    identity = 0
    if ctype:
        identity += 50
    if status:
        identity += 50

    # 2. Geography score — geography (50) + hq_city|hq_country (50)
    geo = 0
    if company.get("geography"):
        geo += 50
    if company.get("hq_city") or company.get("hq_country"):
        geo += 50

    # 3. Alias score — 100 if any alias, 0 otherwise
    alias = 100 if has_aliases else 0

    # 4. Ownership score
    parent = company.get("parent_company_id")
    ownership_type = company.get("ownership_type")
    if not parent:
        # Standalone company — no ownership metadata needed
        ownership = 100
    elif parent and ownership_type:
        ownership = 100
    else:
        # Has parent but missing ownership_type
        ownership = 0

    # 5. Pipeline linkage score
    if drug_count > 0:
        pipeline = 100
    elif coverage in WAIVE_NO_DRUGS:
        # reference/planned — intentionally empty, partial credit
        pipeline = 70
    else:
        pipeline = 0

    # 6. Freshness score
    last_verified_str = company.get("last_verified") or ""
    if not last_verified_str:
        freshness = 0
    else:
        try:
            lv = datetime.fromisoformat(last_verified_str.replace("Z", "+00:00"))
            if lv.tzinfo is None:
                lv = lv.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - lv).days
            if age <= 30:
                freshness = 100
            elif age <= 90:
                freshness = 70
            elif age <= 180:
                freshness = 40
            else:
                freshness = 10
        except ValueError:
            freshness = 0

    dimensions = {
        "identity": identity,
        "geography": geo,
        "aliases": alias,
        "ownership": ownership,
        "pipeline": pipeline,
        "freshness": freshness,
    }
    total = round(sum(dimensions.values()) / len(dimensions))
    return {"dimensions": dimensions, "total": total}


# ── Check functions ──────────────────────────────────────────────────────────

def check_company(company: dict, aliases_by_company: dict, drug_counts: dict) -> list[dict]:
    cid = company["id"]
    ctype = (company.get("company_type") or "").lower().strip()
    status = (company.get("status") or "").lower().strip()
    coverage = (company.get("coverage_status") or "active").lower()
    is_acquired = status == "acquired"
    is_cro_type = ctype in CRO_TYPES
    is_reference = coverage in REFERENCE_TYPES_FOR_TICKER

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

    if not company.get("hq_city") and not company.get("hq_country"):
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
             {"company_id": cid, "name": company.get("name"), "company_type": ctype})

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

    # no_drugs_linked: only flag for active/orphan (not reference/planned)
    if coverage not in WAIVE_NO_DRUGS and not is_acquired:
        drug_count = drug_counts.get(cid, 0)
        if drug_count == 0:
            flag("no_drugs_linked",
                 f"No drugs linked (coverage_status={coverage})",
                 {"company_id": cid, "name": company.get("name"),
                  "coverage_status": coverage,
                  "note": "If intentional, set coverage_status to 'reference' or 'planned'"})

    # ── P2: Enrichment ───────────────────────────────────────────────────────

    ticker = company.get("ticker") or ""
    if not ticker and not is_acquired and not is_cro_type and not is_reference:
        flag("ticker_missing", "ticker is null",
             {"company_id": cid, "name": company.get("name"),
              "note": "Waived for private, acquired, CRO/platform, reference companies"})

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
            lv = datetime.fromisoformat(last_verified_str.replace("Z", "+00:00"))
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


# ── Reporting helpers ────────────────────────────────────────────────────────

def print_health_scores(scored: list[tuple]) -> None:
    """scored: list of (company_id, name, coverage_status, score_dict)"""
    print("=" * 72)
    print("COMPANY HEALTH SCORES")
    print("=" * 72)
    print(f"  {'Company':<30} {'Status':<10} {'Score':>5}  {'ID':<25} {'IDENT':>5} {'GEO':>4} {'ALIAS':>5} {'OWN':>4} {'PIPE':>4} {'FRESH':>5}")
    print(f"  {'-'*30} {'-'*10} {'-'*5}  {'-'*25} {'-'*5} {'-'*4} {'-'*5} {'-'*4} {'-'*4} {'-'*5}")

    # Grade bands
    def grade(score):
        if score >= 85: return "A"
        if score >= 70: return "B"
        if score >= 50: return "C"
        if score >= 30: return "D"
        return "F"

    for cid, name, cov_status, score_dict in sorted(scored, key=lambda x: -x[3]["total"]):
        total = score_dict["total"]
        d = score_dict["dimensions"]
        g = grade(total)
        print(f"  {name[:30]:<30} {cov_status:<10} {total:>3}({g})  {cid:<25} {d['identity']:>5} {d['geography']:>4} {d['aliases']:>5} {d['ownership']:>4} {d['pipeline']:>4} {d['freshness']:>5}")

    # Summary
    totals = [s[3]["total"] for s in scored]
    avg = round(sum(totals) / len(totals)) if totals else 0
    a_count = sum(1 for t in totals if t >= 85)
    b_count = sum(1 for t in totals if 70 <= t < 85)
    c_count = sum(1 for t in totals if 50 <= t < 70)
    d_count = sum(1 for t in totals if 30 <= t < 50)
    f_count = sum(1 for t in totals if t < 30)
    print()
    print(f"  Fleet average: {avg}/100  |  A:{a_count}  B:{b_count}  C:{c_count}  D:{d_count}  F:{f_count}")
    print()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Company profile completeness validator")
    parser.add_argument("--company", help="Validate a single company by ID")
    parser.add_argument("--dry-run", action="store_true", help="Detect only, no DB writes")
    parser.add_argument("--p0-only", action="store_true", help="Show only P0 (high severity) failures")
    parser.add_argument("--summary", action="store_true", help="Print counts + scores only, no row detail")
    parser.add_argument("--scores", action="store_true", help="Print health score table only")
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

    # ── Compute health scores ─────────────────────────────────────────────────

    scored = []
    for company in companies:
        cid = company["id"]
        has_aliases = cid in aliases_by_company
        dc = drug_counts.get(cid, 0)
        score = compute_health_score(company, has_aliases, dc)
        scored.append((cid, company.get("name", cid), company.get("coverage_status", "active"), score))

    if args.scores:
        print_health_scores(scored)
        return

    # ── Run checks ───────────────────────────────────────────────────────────

    all_issues: list[dict] = []

    for company in companies:
        cid = company["id"]
        issues = check_company(company, aliases_by_company, drug_counts)

        if args.p0_only:
            issues = [i for i in issues if i["severity"] == "high"]

        for issue in issues:
            all_issues.append({
                "company_id": cid,
                "company_name": company.get("name", cid),
                "coverage_status": company.get("coverage_status", "active"),
                **issue,
            })

        if not dry_run:
            failed_checks = {i["check_type"] for i in issues}
            for ct in set(SEVERITY.keys()) - failed_checks:
                _clear_resolved(cid, ct)
            for issue in issues:
                _patch_validation(cid, issue["check_type"], {
                    "company_id": cid,
                    "company_name": company.get("name"),
                    "coverage_status": company.get("coverage_status", "active"),
                    "message": issue["message"],
                    **issue["details"],
                })

    # ── Report ───────────────────────────────────────────────────────────────

    all_issues.sort(key=lambda x: (PRIORITY[x["severity"]], x["company_id"]))

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

    if by_check:
        print("─" * 70)
        print("BREAKDOWN BY CHECK TYPE")
        print("─" * 70)
        for ct, count in sorted(by_check.items(), key=lambda x: (PRIORITY[SEVERITY[x[0]]], -x[1])):
            sev_label = SEVERITY[ct].upper().ljust(8)
            print(f"  [{sev_label}] {ct:35s}  {count:3d} companies")
        print()

    print()
    print_health_scores(scored)

    if args.summary:
        status_line = "DRY RUN (no DB writes)" if dry_run else "Results written to drug_validation_results"
        print(f"Status: {status_line}")
        return

    if not all_issues:
        print("✓ All companies pass all active checks.")
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
        cov = issue.get("coverage_status", "")
        print(f"\n  [{cid}] {cname} ({cov})")
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
