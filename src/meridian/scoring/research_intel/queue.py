#!/usr/bin/env python3
"""Priority scoring + research-queue upsert (§3 research_intelligence split)."""

from __future__ import annotations

import json

import requests

from meridian.scoring.research_intel.common import _now_iso, _sb_patch


# ──────────────────────────────────────────────────────────────────────────────
# STEP 4 — PRIORITY SCORE
# ──────────────────────────────────────────────────────────────────────────────

def calculate_priority_score(
    ctx: dict,
    score_result: dict,
    triggers: list[str],
) -> tuple[int, str]:
    """
    Return (priority_score: int 0–200, reason: str).

    Base score = (100 - completeness_score).
    Adjustments:
      +30  strategic entity (cls = direct / 1st gen)
      +20  has active triggers
      +10  per trigger beyond the first (capped at +40 total)
      +15  thin tier
      +10  stale profile trigger
      +10  catalyst date passed trigger
      -10  strong tier with no triggers
      Min 0, max 200.
    """
    base = 100 - score_result.get("completeness_score", 50)
    adjustments: list[str] = []

    company = ctx.get("company") or {}
    cls_field = (company.get("cls") or "").lower()
    is_strategic = "direct" in cls_field or "1st gen" in cls_field

    if is_strategic:
        base += 30
        adjustments.append("+30 strategic entity")

    if triggers:
        base += 20
        adjustments.append(f"+20 has {len(triggers)} trigger(s)")
        extra = min(40, (len(triggers) - 1) * 10)
        if extra:
            base += extra
            adjustments.append(f"+{extra} additional triggers")

    if score_result.get("completeness_tier") == "thin":
        base += 15
        adjustments.append("+15 thin tier")

    if "profile_stale" in triggers:
        base += 10
        adjustments.append("+10 stale profile")

    if "catalyst_date_passed_unresolved" in triggers:
        base += 10
        adjustments.append("+10 passed catalyst")

    if score_result.get("completeness_tier") == "strong" and not triggers:
        base -= 10
        adjustments.append("-10 strong + no triggers")

    priority_score = max(0, min(200, base))
    reason = "; ".join(adjustments) if adjustments else "baseline"

    return priority_score, reason


# ──────────────────────────────────────────────────────────────────────────────
# STEP 5 — UPSERT RESEARCH QUEUE + STAMP DRUGS
# ──────────────────────────────────────────────────────────────────────────────

def upsert_research_queue(
    ctx: dict,
    score_result: dict,
    triggers: list[str],
    next_action: str,
    priority_score: int,
    reason: str,
    dry_run: bool,
    sb_url: str,
    sb_key: str,
) -> None:
    """
    Write the enriched entity state to:
      1. research_queue (upsert on entity_id + area_id)
      2. drugs rows (patch completeness_score, tier, missing_fields, etc.)
    """
    entity_id = ctx["entity_id"]
    area_id = ctx["area_id"]
    drugs = ctx.get("drugs", [])
    company_id = drugs[0].get("company_id") if drugs else None
    entity_name = (
        (drugs[0].get("drug_name") if drugs else None)
        or (ctx.get("company") or {}).get("company_name")
        or entity_id
    )

    # Determine strategic importance from cls
    company = ctx.get("company") or {}
    cls_field = (company.get("cls") or "").lower()
    if "direct" in cls_field or "1st gen" in cls_field:
        strategic_importance = "high"
    elif "adjacent" in cls_field or "2nd gen" in cls_field:
        strategic_importance = "medium"
    else:
        strategic_importance = "low"

    queue_row = {
        "entity_id": entity_id,
        "entity_name": entity_name,
        "company_id": company_id,
        "area_id": area_id,
        "priority_score": priority_score,
        "reason": reason,
        "next_best_action": next_action,
        "missing_stage": score_result["missing_stages"][0] if score_result["missing_stages"] else None,
        "missing_fields": score_result["missing_fields"],
        "strategic_importance": strategic_importance,
        "completeness_score": score_result["completeness_score"],
        "completeness_tier": score_result["completeness_tier"],
        "trigger_events": triggers,
        "last_updated": _now_iso(),
        # NOTE: assigned_status intentionally excluded from this payload.
        # merge-duplicates would overwrite user-set 'in_progress'/'done' statuses on
        # every nightly pipeline run. New rows get DEFAULT 'pending' from the schema.
        # To change status: use the dashboard toggle or update research_queue directly.
    }

    drug_patch = {
        "completeness_score": score_result["completeness_score"],
        "completeness_tier": score_result["completeness_tier"],
        "missing_fields": score_result["missing_fields"],
        "missing_stages": score_result["missing_stages"],
        "next_best_action": next_action,
        "last_scored_at": score_result["last_scored_at"],
        "priority_score": priority_score,
        "trigger_flags": triggers,
    }

    if dry_run:
        print(f"    [dry-run] research_queue upsert: {json.dumps(queue_row, default=str)[:200]}…")
        print(f"    [dry-run] drugs patch ({len(drugs)} rows): {json.dumps(drug_patch, default=str)[:200]}…")
        return

    # Write research_queue — use explicit on_conflict target because the table's PK is
    # a generated UUID; without this, PostgREST conflicts on PK and 409s on the
    # UNIQUE(entity_id, area_id) constraint instead of updating the existing row.
    rq_headers = {
        "apikey": sb_key,
        "Authorization": f"Bearer {sb_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    rq_resp = requests.post(
        f"{sb_url}/rest/v1/research_queue",
        headers=rq_headers,
        params={"on_conflict": "entity_id,area_id"},
        json=[queue_row],
        timeout=30,
    )
    rq_resp.raise_for_status()

    # Stamp each drug row
    for drug in drugs:
        _sb_patch(sb_url, sb_key, "drugs", {"id": drug["id"]}, drug_patch)
