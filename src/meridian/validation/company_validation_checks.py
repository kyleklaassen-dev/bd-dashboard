#!/usr/bin/env python3
"""company_validation_checks.py — pure validation config + checks (§3 split).

The severity/priority/threshold tables + compute_health_score + check_company
(company dict -> health score / failure rows). Pure: no I/O. Imported by
company_validator.py (which owns the Supabase IO + orchestration)."""
from datetime import datetime, timezone, timedelta

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
