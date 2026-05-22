"""
research_intelligence.py — BD Platform Intelligence Layer
==========================================================

PURPOSE
-------
This module turns the BD platform from a passive database into a guided
research system. For every Strategic Competitive Entity it answers:
  • What do we know?          → score_entity_completeness()
  • What is missing?          → missing_fields / missing_stages in score result
  • What changed?             → check_research_triggers()
  • What should happen next?  → get_next_best_action()
  • Why does this matter?     → priority_score + strategic_importance

ARCHITECTURE
------------
  load_entity_context()          — pull all data for one entity from Supabase
                                    (trials + deals fetched by drug_id AND canonical_drug_id)
  _group_drugs_by_canonical()    — group drug rows by canonical_drug_id for unified scoring
  _merge_drug_rows()             — merge sibling drug rows into one best-values representative
  score_entity_completeness()    — 0–100 score across 6 weighted research stages
                                    (Stages 2 + 3 score per canonical program, not per DB row)
  get_next_best_action()         — priority-ordered decision tree → plain-English action
  check_research_triggers()      — detect conditions that require downstream updates
  calculate_priority_score()     — urgency integer (0–200) with human reason
  upsert_research_queue()        — write result to research_queue + stamp drugs rows
  run_intelligence_audit()       — main entry point; loops all entities for an area

STAGE WEIGHTS (must sum to 100)
  Stage 1 — Entity Discovery          10
  Stage 2 — Drug Mapping              15
  Stage 3 — Trial Intelligence        20
  Stage 4 — Catalyst Engine           15
  Stage 5 — Strategic Positioning     25
  Stage 6 — Deal Intelligence         15

COMPLETENESS TIERS
  thin    → score <  40  (entity barely started)
  partial → score 40–69  (entity in progress)
  strong  → score >= 70  (entity well-researched)

USAGE
-----
  python scripts/research_intelligence.py --area tl1a
  python scripts/research_intelligence.py --area tl1a --entity ailux
  python scripts/research_intelligence.py --area all
  python scripts/research_intelligence.py --area tl1a --dry-run

DEPENDENCIES
------------
  pip install requests
  Env:  SUPABASE_URL, SUPABASE_SERVICE_KEY
  OR:   .supabase_service_key file in working directory (runtime fallback)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import requests


# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

STAGE_WEIGHTS: dict[str, int] = {
    "stage1_entity_discovery":   10,
    "stage2_drug_mapping":       15,
    "stage3_trial_intelligence": 20,
    "stage4_catalyst_engine":    15,
    "stage5_strategic_position": 25,
    "stage6_deal_intelligence":  15,
}

TIER_THRESHOLDS = {"thin": 40, "partial": 70}  # <40 thin, 40–69 partial, >=70 strong

TRIGGER_TYPES = {
    "trial_phase_ahead_of_drug_stage":    "Trial phase is more advanced than the mapped drug stage",
    "trial_pcd_without_catalyst":         "Trial has a primary completion date but no catalyst generated",
    "completed_trial_without_results":    "Trial status is completed but no results text on associated drug",
    "catalyst_date_passed_unresolved":    "Catalyst expected date has passed with no resolution/outcome",
    "profile_stale":                      "Company profile not enriched in >30 days",
    "new_deal_since_enrichment":          "A new deal exists with a created_at newer than company's last enrichment",
    "strategic_entity_missing_vs_ailux":  "Entity is strategic but vs_ailux field is empty on company profile",
}

# Drug stage → numeric rank for phase comparison
DRUG_STAGE_RANK: dict[str, int] = {
    "preclinical": 1,
    "phase 1": 2, "phase1": 2,
    "phase 1/2": 3, "phase1/2": 3,
    "phase 2": 4, "phase2": 4,
    "phase 2/3": 5, "phase2/3": 5,
    "phase 3": 6, "phase3": 6,
    "approved": 7,
}

TRIAL_PHASE_RANK: dict[str, int] = {
    "phase 1": 2, "phase1": 2,
    "phase 1/phase 2": 3,
    "phase 2": 4, "phase2": 4,
    "phase 2/phase 3": 5,
    "phase 3": 6, "phase3": 6,
    "phase 4": 7,
}

ALL_AREAS = ["tl1a", "tslp", "il4ra", "fcrn", "igf1r", "tcell"]


# ──────────────────────────────────────────────────────────────────────────────
# SUPABASE CLIENT
# ──────────────────────────────────────────────────────────────────────────────

def _get_supabase_creds() -> tuple[str, str]:
    """Return (url, service_key) from env or .supabase_service_key file."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not key:
        try:
            with open(".supabase_service_key") as f:
                key = f.read().strip()
        except FileNotFoundError:
            pass
    if not url or not key:
        raise RuntimeError(
            "Supabase credentials not found. Set SUPABASE_URL + SUPABASE_SERVICE_KEY "
            "or provide .supabase_service_key file."
        )
    return url, key


def _sb_get(url: str, key: str, table: str, params: dict) -> list[dict]:
    """GET rows from a Supabase table via PostgREST."""
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    resp = requests.get(f"{url}/rest/v1/{table}", headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _sb_upsert(url: str, key: str, table: str, data: dict | list) -> None:
    """Upsert one or more rows into a Supabase table."""
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    payload = data if isinstance(data, list) else [data]
    resp = requests.post(
        f"{url}/rest/v1/{table}", headers=headers, json=payload, timeout=30
    )
    resp.raise_for_status()


def _sb_patch(url: str, key: str, table: str, match: dict, data: dict) -> None:
    """PATCH rows matching `match` with `data`."""
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    params = {k: f"eq.{v}" for k, v in match.items()}
    resp = requests.patch(
        f"{url}/rest/v1/{table}", headers=headers, params=params, json=data, timeout=30
    )
    resp.raise_for_status()


# ──────────────────────────────────────────────────────────────────────────────
# HELPER
# ──────────────────────────────────────────────────────────────────────────────

def _nonempty(val: Any) -> bool:
    """Return True if val is meaningfully populated (not None, '', [], {})."""
    if val is None:
        return False
    if isinstance(val, str):
        return val.strip() != ""
    if isinstance(val, (list, dict)):
        return len(val) > 0
    return True  # numbers, booleans, etc.


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────────────────
# CANONICAL GROUPING HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _group_drugs_by_canonical(drugs: list[dict]) -> list[list[dict]]:
    """
    Group drug rows by canonical_drug_id.
    Drugs without a canonical_drug_id each form their own single-item group.
    Returns a list of groups (each group = list of drug rows sharing one canonical).
    """
    canon_groups: dict[str, list[dict]] = {}
    ungrouped: list[list[dict]] = []
    for d in drugs:
        cid = d.get("canonical_drug_id")
        if cid:
            canon_groups.setdefault(cid, []).append(d)
        else:
            ungrouped.append([d])
    return list(canon_groups.values()) + ungrouped


def _merge_drug_rows(rows: list[dict]) -> dict:
    """
    Merge multiple drug rows sharing the same canonical_drug_id into one
    representative row, using the most-populated value for each text field.

    Attaches:
      _all_drug_ids  — list of all constituent drug.id values (for trial/catalyst lookups)
    """
    if len(rows) == 1:
        merged = dict(rows[0])
        merged["_all_drug_ids"] = [rows[0]["id"]]
        return merged

    merged = dict(rows[0])
    TEXT_FIELDS = [
        "mechanism", "target", "stage", "differentiation_thesis",
        "results_summary", "vs_competitor", "drug_class", "name",
    ]
    for field in TEXT_FIELDS:
        best = max((r.get(field) or "" for r in rows), key=len)
        if best:
            merged[field] = best

    # Numeric: take max confidence score across all rows
    merged["confidence_score"] = max((r.get("confidence_score") or 0) for r in rows)

    # canonical_drug_id: take any populated value (all rows should share it)
    merged["canonical_drug_id"] = next(
        (r.get("canonical_drug_id") for r in rows if r.get("canonical_drug_id")), None
    )

    # trial_data_status: 'missing' only if EVERY row explicitly says 'missing'
    # (None/unset rows are treated as non-missing, so [None, "missing"] → not missing)
    statuses = [r.get("trial_data_status") for r in rows]
    if statuses and all(s == "missing" for s in statuses):
        merged["trial_data_status"] = "missing"
    else:
        merged["trial_data_status"] = next(
            (s for s in statuses if s and s != "missing"),
            statuses[0] if statuses else None,
        )

    # Keep all constituent IDs for downstream trial/catalyst lookups
    merged["_all_drug_ids"] = [r["id"] for r in rows]
    return merged


# ──────────────────────────────────────────────────────────────────────────────
# STEP 0 — LOAD ENTITY CONTEXT
# ──────────────────────────────────────────────────────────────────────────────

def load_entity_context(
    entity_id: str,
    area_id: str,
    sb_url: str,
    sb_key: str,
) -> dict:
    """
    Load all research data for one entity from Supabase.

    Returns a context dict with keys:
      entity_id, area_id,
      drugs          — list of drug rows (drug_id, drug_name, stage, mechanism,
                        target, discovery_status, confidence_score,
                        differentiation_thesis, trial_data_status, vs_competitor,
                        results_summary, aliases, completeness_score, ...)
      trials         — list of trial rows joined through drugs
      catalysts      — list of catalyst rows for drugs in this entity
      company        — single company row (company_id, company_name, ...)
      profile        — single company_profiles row
      deals          — list of deal rows for this entity
    """
    ctx: dict = {
        "entity_id": entity_id,
        "area_id": area_id,
        "drugs": [],
        "trials": [],
        "catalysts": [],
        "company": None,
        "profile": None,
        "deals": [],
    }

    # -- Drugs for this entity (area_id is in drug_areas junction, not on drugs directly)
    drugs = _sb_get(sb_url, sb_key, "drugs", {
        "entity_id": f"eq.{entity_id}",
        "select": "*",
    })
    ctx["drugs"] = drugs

    if not drugs:
        # Try to find by company + area even if entity_id not set yet
        return ctx

    drug_ids = [d["id"] for d in drugs]
    drug_ids_filter = "in.(" + ",".join(drug_ids) + ")"

    # Collect canonical_drug_ids for this entity's drugs — used to broaden
    # trial/deal lookups so cross-drug-row records are captured correctly.
    canonical_ids: list[str] = list({
        d["canonical_drug_id"] for d in drugs if d.get("canonical_drug_id")
    })

    # -- Trials linked to these drugs (by drug_id)
    trials = _sb_get(sb_url, sb_key, "trials", {
        "drug_id": drug_ids_filter,
        "select": "*",
    })
    # Also fetch trials by canonical_drug_id to catch records written by
    # ct_gov_sync that reference a different drug row sharing the same canonical.
    if canonical_ids:
        canon_filter = "in.(" + ",".join(canonical_ids) + ")"
        canon_trials = _sb_get(sb_url, sb_key, "trials", {
            "canonical_drug_id": canon_filter,
            "select": "*",
        })
        seen_trial_ids = {t["id"] for t in trials}
        for t in canon_trials:
            if t["id"] not in seen_trial_ids:
                trials.append(t)
                seen_trial_ids.add(t["id"])
    ctx["trials"] = trials

    # -- Catalysts for these drugs
    catalysts = _sb_get(sb_url, sb_key, "catalysts", {
        "drug_id": drug_ids_filter,
        "select": "*",
    })
    ctx["catalysts"] = catalysts

    # -- Company from first drug
    company_id = drugs[0].get("company_id") if drugs else None
    if company_id:
        companies = _sb_get(sb_url, sb_key, "companies", {
            "id": f"eq.{company_id}",   # companies PK is 'id', not 'company_id'
            "select": "*",
            "limit": "1",
        })
        ctx["company"] = companies[0] if companies else None

        profiles = _sb_get(sb_url, sb_key, "company_profiles", {
            "company_id": f"eq.{company_id}",
            "select": "*",
            "limit": "1",
        })
        ctx["profile"] = profiles[0] if profiles else None

    # -- Deals for this entity (by entity_id)
    deals: list[dict] = []
    if entity_id:
        deals = _sb_get(sb_url, sb_key, "deals", {
            "entity_id": f"eq.{entity_id}",
            "select": "*",
        })
    # Also fetch deals by canonical_drug_id to capture deals written by
    # company_enrichment that may reference the canonical program directly.
    if canonical_ids:
        canon_filter = "in.(" + ",".join(canonical_ids) + ")"
        canon_deals = _sb_get(sb_url, sb_key, "deals", {
            "canonical_drug_id": canon_filter,
            "select": "*",
        })
        seen_deal_ids = {d["id"] for d in deals}
        for d in canon_deals:
            if d["id"] not in seen_deal_ids:
                deals.append(d)
                seen_deal_ids.add(d["id"])
    ctx["deals"] = deals

    return ctx


# ──────────────────────────────────────────────────────────────────────────────
# STEP 1 — COMPLETENESS SCORING
# ──────────────────────────────────────────────────────────────────────────────

def score_entity_completeness(ctx: dict) -> dict:
    """
    Score an entity 0–100 across 6 research stages.

    Scoring logic per stage:
      Stage 1 (Entity Discovery, weight=10):
        Full credit if: entity_id present, drugs list non-empty,
                        at least one drug has a company_id.
      Stage 2 (Drug Mapping, weight=15):
        Per drug: mechanism, target, stage, differentiation_thesis (25 pts each).
        Averaged across all drugs; credit for aliases is a bonus.
      Stage 3 (Trial Intelligence, weight=20):
        Per drug: has trials (50%), arms/endpoints populated (25%),
                  confidence_score >= 80 (25%).
        Averaged across drugs; penalised if trial_data_status == 'missing'.
      Stage 4 (Catalyst Engine, weight=15):
        Has at least one catalyst (50%); catalyst has expected_date + title (50%).
      Stage 5 (Strategic Positioning, weight=25):
        Company profile exists (20%); competitive_position (20%);
        vs_ailux on profile OR drug (40%); key_differentiators (20%).
      Stage 6 (Deal Intelligence, weight=15):
        Has deals (60%); deals have economics_royalties + strategic_signal (40%).

    Returns dict:
      completeness_score  — int 0–100
      completeness_tier   — 'thin' | 'partial' | 'strong'
      stage_scores        — {stage_name: raw_score_0_to_1}
      missing_fields      — [field_names ...]
      missing_stages      — [stage_names ...]
      populated_fields    — [field_names ...]
      last_scored_at      — ISO timestamp
    """
    drugs = ctx.get("drugs", [])
    trials = ctx.get("trials", [])
    catalysts = ctx.get("catalysts", [])
    profile = ctx.get("profile") or {}
    deals = ctx.get("deals", [])

    stage_scores: dict[str, float] = {}
    missing_fields: list[str] = []
    populated_fields: list[str] = []

    def _check(condition: bool, field: str) -> float:
        if condition:
            populated_fields.append(field)
            return 1.0
        else:
            missing_fields.append(field)
            return 0.0

    # ── Stage 1: Entity Discovery ────────────────────────────────────────────
    s1 = 0.0
    s1 += _check(bool(ctx.get("entity_id")), "entity_id")
    s1 += _check(len(drugs) > 0, "drugs_list")
    s1 += _check(any(_nonempty(d.get("company_id")) for d in drugs), "company_id")
    stage_scores["stage1_entity_discovery"] = s1 / 3

    # ── Stage 2: Drug Mapping ────────────────────────────────────────────────
    # Group by canonical_drug_id so multi-row programs score as one program.
    # _merge_drug_rows() picks the best-populated value across all sibling rows,
    # so two rows sharing a canonical both contribute to a single score rather
    # than two separate averaged scores.
    if drugs:
        canonical_groups = _group_drugs_by_canonical(drugs)
        drug_scores = []
        for group in canonical_groups:
            d = _merge_drug_rows(group)
            label = d["id"]  # use first/primary drug.id as the field label key
            ds = 0.0
            ds += _check(_nonempty(d.get("mechanism")), f"drug:{label}:mechanism")
            ds += _check(_nonempty(d.get("target")), f"drug:{label}:target")
            ds += _check(_nonempty(d.get("stage")), f"drug:{label}:stage")
            ds += _check(_nonempty(d.get("differentiation_thesis")), f"drug:{label}:differentiation_thesis")
            # canonical_drug_id: identity spine — full credit if any sibling has it
            ds += _check(_nonempty(d.get("canonical_drug_id")), f"drug:{label}:canonical_drug_id")
            drug_scores.append(ds / 5)
        stage_scores["stage2_drug_mapping"] = sum(drug_scores) / len(drug_scores)
    else:
        missing_fields.append("drugs_list")
        stage_scores["stage2_drug_mapping"] = 0.0

    # ── Stage 3: Trial Intelligence ──────────────────────────────────────────
    # Score per canonical program (not per DB row) so a program with 3 drug
    # rows and 6 trials doesn't inflate or deflate the average.
    # Trials are looked up by both drug_id AND canonical_drug_id.
    if drugs:
        canonical_groups = _group_drugs_by_canonical(drugs)
        drug_trial_scores = []

        # Build trial lookup maps
        drug_trial_map: dict[str, list] = {}
        canon_trial_map: dict[str, list] = {}
        for t in trials:
            if t.get("drug_id"):
                drug_trial_map.setdefault(t["drug_id"], []).append(t)
            if t.get("canonical_drug_id"):
                canon_trial_map.setdefault(t["canonical_drug_id"], []).append(t)

        for group in canonical_groups:
            d = _merge_drug_rows(group)
            all_drug_ids = d.get("_all_drug_ids", [d["id"]])
            canonical_id = d.get("canonical_drug_id")
            label = all_drug_ids[0]  # field label key

            # Union trials from all constituent drug_ids + canonical_drug_id,
            # deduplicated by trial id to avoid double-counting.
            group_trials: list[dict] = []
            seen_trial_ids: set = set()
            for did in all_drug_ids:
                for t in drug_trial_map.get(did, []):
                    if t["id"] not in seen_trial_ids:
                        group_trials.append(t)
                        seen_trial_ids.add(t["id"])
            if canonical_id:
                for t in canon_trial_map.get(canonical_id, []):
                    if t["id"] not in seen_trial_ids:
                        group_trials.append(t)
                        seen_trial_ids.add(t["id"])

            ds = 0.0
            has_trials = len(group_trials) > 0
            ds += _check(has_trials, f"drug:{label}:has_trials")

            if has_trials:
                has_detail = any(
                    _nonempty(t.get("arms")) or _nonempty(t.get("primary_endpoint"))
                    for t in group_trials
                )
                ds += _check(has_detail, f"drug:{label}:trial_detail")

                high_conf = any(
                    (t.get("confidence_score") or 0) >= 80 for t in group_trials
                )
                ds += _check(high_conf, f"drug:{label}:trial_confidence")

                # canonical_drug_id stamped on at least one trial — identity spine intact
                has_canonical = any(
                    _nonempty(t.get("canonical_drug_id")) for t in group_trials
                )
                ds += _check(has_canonical, f"drug:{label}:trial_canonical_linked")
            else:
                missing_fields.extend([
                    f"drug:{label}:trial_detail",
                    f"drug:{label}:trial_confidence",
                    f"drug:{label}:trial_canonical_linked",
                ])

            # Penalise if merged row says trial data is explicitly absent
            if d.get("trial_data_status") == "missing":
                ds = max(0.0, ds - 0.5)

            drug_trial_scores.append(ds / 4)

        stage_scores["stage3_trial_intelligence"] = (
            sum(drug_trial_scores) / len(drug_trial_scores)
        )
    else:
        stage_scores["stage3_trial_intelligence"] = 0.0

    # ── Stage 4: Catalyst Engine ─────────────────────────────────────────────
    if catalysts:
        populated_fields.append("catalysts_list")
        # Catalysts table uses sort_date and label (not expected_date / title)
        s4_detail = any(
            _nonempty(c.get("sort_date")) and _nonempty(c.get("label"))
            for c in catalysts
        )
        s4 = 0.5 + (0.5 if s4_detail else 0.0)
        if not s4_detail:
            missing_fields.append("catalyst_sort_date_and_label")
    else:
        missing_fields.append("catalysts_list")
        s4 = 0.0
    stage_scores["stage4_catalyst_engine"] = s4

    # ── Stage 5: Strategic Positioning ──────────────────────────────────────
    s5 = 0.0
    has_profile = bool(profile)
    s5 += _check(has_profile, "company_profile_exists")

    if has_profile:
        s5 += _check(
            _nonempty(profile.get("competitive_position")),
            "competitive_position"
        )
        vs_ailux_ok = _nonempty(profile.get("vs_ailux")) or any(
            _nonempty(d.get("vs_competitor")) for d in drugs
        )
        s5 += 2 * _check(vs_ailux_ok, "vs_ailux")  # double weight
        s5 += _check(
            _nonempty(profile.get("key_differentiators")),
            "key_differentiators"
        )
    else:
        missing_fields.extend([
            "competitive_position", "vs_ailux", "key_differentiators"
        ])

    stage_scores["stage5_strategic_position"] = min(1.0, s5 / 5)

    # ── Stage 6: Deal Intelligence ───────────────────────────────────────────
    if deals:
        populated_fields.append("deals_list")
        has_deal_detail = any(
            _nonempty(d.get("economics_royalties")) or _nonempty(d.get("strategic_signal"))
            for d in deals
        )
        s6 = 0.6 + (0.4 if has_deal_detail else 0.0)
        if not has_deal_detail:
            missing_fields.append("deal_economics_or_signal")
    else:
        missing_fields.append("deals_list")
        s6 = 0.0
    stage_scores["stage6_deal_intelligence"] = s6

    # ── Final Score ──────────────────────────────────────────────────────────
    total = sum(
        stage_scores[stage] * weight
        for stage, weight in STAGE_WEIGHTS.items()
    )
    completeness_score = round(total)

    if completeness_score < TIER_THRESHOLDS["thin"]:
        tier = "thin"
    elif completeness_score < TIER_THRESHOLDS["partial"]:
        tier = "partial"
    else:
        tier = "strong"

    missing_stages = [
        stage for stage, score in stage_scores.items()
        if score < 0.5
    ]

    return {
        "completeness_score": completeness_score,
        "completeness_tier": tier,
        "stage_scores": {k: round(v * 100) for k, v in stage_scores.items()},
        "missing_fields": list(dict.fromkeys(missing_fields)),   # deduplicated, ordered
        "missing_stages": missing_stages,
        "populated_fields": list(dict.fromkeys(populated_fields)),
        "last_scored_at": _now_iso(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# STEP 2 — NEXT BEST ACTION ENGINE
# ──────────────────────────────────────────────────────────────────────────────

def get_next_best_action(ctx: dict, score_result: dict) -> str:
    """
    Return a single plain-English recommended next action for this entity.

    Decision priority order (first match wins):
      1. No drugs mapped                          → "Map drugs/programs for this entity"
      2. Any drug missing mechanism or target     → "Run drug mapping to fill mechanism + target"
      3. Any drug missing trials                  → "Run CT.gov search to find clinical trials"
      4. Trial has PCD but no catalyst            → "Generate catalyst from primary completion date"
      5. Catalyst date passed with no resolution  → "Search for trial results — catalyst date has passed"
      6. Company profile missing vs_ailux         → "Run strategic enrichment to assess vs. Ailux"
      7. No deals for a strategic entity          → "Search deal history for partnership/licensing activity"
      8. Profile stale (>30 days)                 → "Re-run company enrichment — profile is stale"
      9. Completeness ≥ 70 (strong)               → "Entity well-researched — verify data quality"
     10. Default                                  → "Continue enrichment across remaining gaps"
    """
    drugs = ctx.get("drugs", [])
    trials = ctx.get("trials", [])
    catalysts = ctx.get("catalysts", [])
    profile = ctx.get("profile") or {}
    deals = ctx.get("deals", [])
    score = score_result.get("completeness_score", 0)

    # 1. No drugs
    if not drugs:
        return "Map drugs/programs for this entity"

    # 2. Any drug missing mechanism or target
    if any(
        not _nonempty(d.get("mechanism")) or not _nonempty(d.get("target"))
        for d in drugs
    ):
        return "Run drug mapping to fill mechanism + target fields"

    # 2b. Any drug missing canonical identity — identity spine broken
    if any(not _nonempty(d.get("canonical_drug_id")) for d in drugs):
        return "Run identity resolver to link drug to canonical_drug_id (one_time_migration.py)"

    # 3. Any drug with no associated trials
    drug_ids_with_trials = {t["drug_id"] for t in trials}
    if any(d["id"] not in drug_ids_with_trials for d in drugs):
        return "Run CT.gov search to find clinical trials for unmapped drugs"

    # 4. Trial has primary_completion_date but no catalyst
    today = datetime.now(timezone.utc).date()
    trial_pcd_set = {
        t["drug_id"] for t in trials
        if _nonempty(t.get("primary_completion_date"))
    }
    cat_drug_ids = {c["drug_id"] for c in catalysts}
    if trial_pcd_set - cat_drug_ids:
        return "Generate catalyst from trial primary completion date"

    # 5. Catalyst date passed unresolved
    for c in catalysts:
        exp_date = c.get("sort_date")   # was expected_date — catalysts table uses sort_date
        resolved = _nonempty(c.get("outcome")) or _nonempty(c.get("results_url"))
        if exp_date and not resolved:
            try:
                cd = datetime.fromisoformat(exp_date.replace("Z", "+00:00")).date()
                if cd < today:
                    return f"Search for results — catalyst '{c.get('label', 'unknown')}' date has passed"
            except (ValueError, AttributeError):
                pass

    # 6. vs_ailux missing on profile or drug
    vs_ailux_ok = _nonempty(profile.get("vs_ailux")) or any(
        _nonempty(d.get("vs_competitor")) for d in drugs
    )
    if not vs_ailux_ok:
        return "Run strategic enrichment to fill vs. Ailux competitive assessment"

    # 7. No deals for this entity
    if not deals:
        company_name = (ctx.get("company") or {}).get("company_name", "this company")
        return f"Search deal history for {company_name} — no partnerships or licensing found"

    # 8. Profile stale
    enriched_at = profile.get("enriched_at") or profile.get("last_enriched_at")
    if enriched_at:
        try:
            ea = datetime.fromisoformat(enriched_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - ea).days
            if age_days > 30:
                return f"Re-run company enrichment — profile is {age_days} days old"
        except (ValueError, AttributeError):
            pass

    # 9. Strong entity
    if score >= 70:
        return "Entity well-researched — verify data quality and freshness"

    # 10. Default
    missing = score_result.get("missing_stages", [])
    if missing:
        return f"Continue enrichment — gaps in {', '.join(missing[:2])}"
    return "Continue enrichment across remaining research gaps"


# ──────────────────────────────────────────────────────────────────────────────
# STEP 3 — TRIGGER ENGINE
# ──────────────────────────────────────────────────────────────────────────────

def check_research_triggers(ctx: dict) -> list[str]:
    """
    Detect conditions that require downstream pipeline updates.

    Returns list of trigger type strings (subset of TRIGGER_TYPES keys).

    Trigger definitions:
      trial_phase_ahead_of_drug_stage
        → any trial's phase rank > its drug's stage rank

      trial_pcd_without_catalyst
        → any trial has primary_completion_date but drug has no catalyst

      completed_trial_without_results
        → any trial status is 'completed' but associated drug has no results_summary

      catalyst_date_passed_unresolved
        → any catalyst expected_date < today with no outcome + no results_url

      profile_stale
        → company profile enriched_at > 30 days ago

      new_deal_since_enrichment
        → any deal created_at > company profile's enriched_at / last_enriched_at

      strategic_entity_missing_vs_ailux
        → company cls field starts with 'direct' or strategic_importance='high'
          AND vs_ailux is empty on both profile and drugs
    """
    triggers: list[str] = []
    drugs = ctx.get("drugs", [])
    trials = ctx.get("trials", [])
    catalysts = ctx.get("catalysts", [])
    profile = ctx.get("profile") or {}
    company = ctx.get("company") or {}
    deals = ctx.get("deals", [])
    today = datetime.now(timezone.utc).date()

    # Build lookup maps
    drug_map = {d["id"]: d for d in drugs}
    drug_trials: dict[str, list] = {}
    for t in trials:
        drug_trials.setdefault(t["drug_id"], []).append(t)
    drug_catalysts: dict[str, list] = {}
    for c in catalysts:
        drug_catalysts.setdefault(c["drug_id"], []).append(c)

    # ── T1: trial phase ahead of drug stage ─────────────────────────────────
    for t in trials:
        drug = drug_map.get(t["drug_id"])
        if not drug:
            continue
        trial_phase = (t.get("phase") or "").lower().strip()
        drug_stage = (drug.get("stage") or "").lower().strip()
        tp_rank = TRIAL_PHASE_RANK.get(trial_phase, 0)
        ds_rank = DRUG_STAGE_RANK.get(drug_stage, 0)
        if tp_rank > 0 and ds_rank > 0 and tp_rank > ds_rank:
            triggers.append("trial_phase_ahead_of_drug_stage")
            break

    # ── T2: trial PCD without catalyst ──────────────────────────────────────
    for t in trials:
        if _nonempty(t.get("primary_completion_date")):
            drug_id = t["drug_id"]
            if not drug_catalysts.get(drug_id):
                triggers.append("trial_pcd_without_catalyst")
                break

    # ── T3: completed trial without results ─────────────────────────────────
    for t in trials:
        status = (t.get("overall_status") or "").lower()
        if "complet" in status:
            drug = drug_map.get(t["drug_id"])
            if drug and not _nonempty(drug.get("results_summary")):
                triggers.append("completed_trial_without_results")
                break

    # ── T4: catalyst date passed unresolved ─────────────────────────────────
    for c in catalysts:
        exp_date = c.get("sort_date")   # was expected_date — catalysts table uses sort_date
        if not exp_date:
            continue
        resolved = _nonempty(c.get("outcome")) or _nonempty(c.get("results_url"))
        if not resolved:
            try:
                cd = datetime.fromisoformat(exp_date.replace("Z", "+00:00")).date()
                if cd < today:
                    triggers.append("catalyst_date_passed_unresolved")
                    break
            except (ValueError, AttributeError):
                pass

    # ── T5: profile stale ────────────────────────────────────────────────────
    enriched_at = profile.get("enriched_at") or profile.get("last_enriched_at")
    if enriched_at:
        try:
            ea = datetime.fromisoformat(enriched_at.replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - ea).days > 30:
                triggers.append("profile_stale")
        except (ValueError, AttributeError):
            pass
    elif profile:
        # Profile exists but no enriched_at — treat as stale
        triggers.append("profile_stale")

    # ── T6: new deal since enrichment ────────────────────────────────────────
    enriched_at = profile.get("enriched_at") or profile.get("last_enriched_at")
    if enriched_at and deals:
        try:
            ea = datetime.fromisoformat(enriched_at.replace("Z", "+00:00"))
            for deal in deals:
                deal_created = deal.get("created_at") or deal.get("announced_date")
                if deal_created:
                    dc = datetime.fromisoformat(deal_created.replace("Z", "+00:00"))
                    if dc > ea:
                        triggers.append("new_deal_since_enrichment")
                        break
        except (ValueError, AttributeError):
            pass

    # ── T7: strategic entity missing vs_ailux ───────────────────────────────
    cls_field = (company.get("cls") or "").lower()
    is_strategic = "direct" in cls_field or "1st gen" in cls_field
    vs_ailux_ok = _nonempty(profile.get("vs_ailux")) or any(
        _nonempty(d.get("vs_competitor")) for d in drugs
    )
    if is_strategic and not vs_ailux_ok:
        triggers.append("strategic_entity_missing_vs_ailux")

    return list(dict.fromkeys(triggers))  # deduplicate, preserve order


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
        drugs[0].get("drug_name")
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


# ──────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

def run_intelligence_audit(
    area_id: str,
    entity_filter: str | None = None,
    dry_run: bool = False,
) -> None:
    """
    Run the full intelligence audit for one area.

    For each entity in the area:
      1. Load context from Supabase
      2. Score completeness
      3. Detect triggers
      4. Determine next best action
      5. Calculate priority score
      6. Upsert research_queue + stamp drugs

    Prints a summary table on completion.
    """
    sb_url, sb_key = _get_supabase_creds()

    print(f"\n{'═'*60}")
    print(f"  Intelligence Audit — area: {area_id}")
    if dry_run:
        print("  DRY RUN — no writes to Supabase")
    print(f"{'═'*60}")

    # Discover all drug_ids for this area via the drug_areas junction table
    area_rows = _sb_get(sb_url, sb_key, "drug_areas", {
        "area_id": f"eq.{area_id}",
        "select": "drug_id",
    })
    if not area_rows:
        print("  No drug_areas rows found for this area.")
        return

    area_drug_ids = [r["drug_id"] for r in area_rows]
    drug_id_filter = "in.(" + ",".join(area_drug_ids) + ")"

    params: dict = {
        "id": drug_id_filter,
        "select": "entity_id,id,name,company_id",
    }
    if entity_filter:
        params["entity_id"] = f"ilike.%{entity_filter}%"

    all_drugs = _sb_get(sb_url, sb_key, "drugs", params)

    # Group by entity_id; entities without entity_id get a fallback key
    entity_map: dict[str, list] = {}
    for d in all_drugs:
        # drugs table uses 'id' as primary key, not 'drug_id'
        eid = d.get("entity_id") or f"__no_entity__{d['id']}"
        entity_map.setdefault(eid, []).append(d)

    if not entity_map:
        print("  No entities found for this area.")
        return

    print(f"  Entities to audit: {len(entity_map)}\n")

    results = []
    for entity_id, entity_drugs in entity_map.items():
        real_entity_id = entity_id if not entity_id.startswith("__no_entity__") else entity_drugs[0]["id"]
        drug_names = ", ".join(d.get("name", "?") for d in entity_drugs[:2])
        print(f"  ── {real_entity_id} ({drug_names})")

        try:
            ctx = load_entity_context(real_entity_id, area_id, sb_url, sb_key)

            score_result = score_entity_completeness(ctx)
            triggers = check_research_triggers(ctx)
            next_action = get_next_best_action(ctx, score_result)
            priority_score, reason = calculate_priority_score(ctx, score_result, triggers)

            upsert_research_queue(
                ctx=ctx,
                score_result=score_result,
                triggers=triggers,
                next_action=next_action,
                priority_score=priority_score,
                reason=reason,
                dry_run=dry_run,
                sb_url=sb_url,
                sb_key=sb_key,
            )

            results.append({
                "entity_id": real_entity_id,
                "score": score_result["completeness_score"],
                "tier": score_result["completeness_tier"],
                "priority": priority_score,
                "triggers": len(triggers),
                "action": next_action[:60],
            })

            print(
                f"     score={score_result['completeness_score']:3d} "
                f"tier={score_result['completeness_tier']:<8s} "
                f"priority={priority_score:3d} "
                f"triggers={len(triggers)} "
                f"→ {next_action[:55]}"
            )

        except Exception as e:
            print(f"     ERROR: {e}")
            results.append({"entity_id": real_entity_id, "error": str(e)})

    # Summary
    scored = [r for r in results if "score" in r]
    print(f"\n{'─'*60}")
    print(f"  Audit complete. {len(scored)}/{len(results)} entities scored.")
    if scored:
        avg = sum(r["score"] for r in scored) / len(scored)
        top = sorted(scored, key=lambda r: r["priority"], reverse=True)[:3]
        print(f"  Average completeness: {avg:.1f}")
        print(f"  Top priorities:")
        for r in top:
            print(f"    [{r['priority']:3d}] {r['entity_id']} — {r['action']}")
    print(f"{'═'*60}\n")


def rescore_molecule(
    drug_id: str,
    area_id: str,
    dry_run: bool = False,
) -> None:
    """
    Re-score completeness for the company that owns drug_id in area_id.

    Called after manual curation of molecule_intelligence to ensure:
      - company_profiles.completeness_score reflects the updated molecule data
      - company_profiles.missing_fields drops any molecule fields now populated
      - research_queue entry is updated (priority_score + next_best_action)

    Does NOT re-run Claude enrichment. Only re-reads the current DB state
    and recalculates scores.
    """
    sb_url, sb_key = _get_supabase_creds()

    print(f"\n{'═'*60}")
    print(f"  Rescore Molecule — drug: {drug_id} / area: {area_id}")
    if dry_run:
        print("  DRY RUN — no writes to Supabase")
    print(f"{'═'*60}")

    # 1. Find which company owns this drug in this area
    drug_rows = _sb_get(sb_url, sb_key, "drugs", {
        "id": f"eq.{drug_id}",
        "select": "id,name,company_id,entity_id,stage,canonical_drug_id",
    })
    if not drug_rows:
        print(f"  ✗ Drug '{drug_id}' not found in drugs table.")
        return
    drug = drug_rows[0]
    company_id = drug.get("company_id") or drug.get("entity_id") or drug_id
    entity_id  = drug.get("entity_id") or company_id
    print(f"  Drug: {drug['name']} | Company: {company_id} | Entity: {entity_id}")

    # 2. Load full entity context (same as run_intelligence_audit)
    ctx = load_entity_context(
        entity_id=entity_id,
        area_id=area_id,
        sb_url=sb_url,
        sb_key=sb_key,
    )
    if not ctx:
        print(f"  ✗ Could not load context for entity '{entity_id}'")
        return

    # 3. Load current molecule_intelligence for this drug (post-curation state)
    mol_rows = _sb_get(sb_url, sb_key, "molecule_intelligence", {
        "drug_id": f"eq.{drug_id}",
        "select": "*",
    })
    mol = mol_rows[0] if mol_rows else {}

    # Inject current molecule data into ctx so scoring sees it
    # Build a synthetic molecule_updates entry from the current DB row
    if mol:
        ctx["molecule_intelligence"] = mol
        print(f"  Molecule row found: format={mol.get('format')} "
              f"modality={mol.get('modality')} "
              f"field_status={mol.get('field_status')}")
    else:
        print(f"  No molecule_intelligence row found for {drug_id}")

    # 4. Score completeness using existing scoring infrastructure
    score_result = score_entity_completeness(ctx)
    completeness_score = score_result.get("completeness_score", 0)
    completeness_tier  = score_result.get("completeness_tier", "thin")
    missing_fields     = score_result.get("missing_fields") or []
    next_action        = get_next_best_action(ctx, score_result)

    # Add molecule-specific missing fields to the list
    MOL_REQUIRED = ["format", "modality", "differentiation_claim"]
    MOL_DESIRED  = ["epitope", "affinity_kd", "fc_engineering", "lowest_active_dose"]
    field_status = mol.get("field_status") or {}
    for field in MOL_REQUIRED:
        val = mol.get(field) or ""
        if not val or not str(val).strip():
            mf = f"molecule_intelligence.{field}[{drug_id}]"
            if mf not in missing_fields:
                missing_fields.append(mf)
    for field in MOL_DESIRED:
        if field_status.get(field) == "unknown" or (field not in field_status and not mol.get(field)):
            mf = f"molecule_intelligence.{field}[{drug_id}]"
            if mf not in missing_fields:
                missing_fields.append(mf)

    print(f"  Score: {completeness_score}/100 ({completeness_tier}) | "
          f"{len(missing_fields)} missing field(s)")
    if missing_fields:
        mol_missing = [f for f in missing_fields if "molecule_intelligence" in f]
        other_missing = [f for f in missing_fields if "molecule_intelligence" not in f]
        if mol_missing:
            print(f"  Molecule gaps: {mol_missing}")
        if other_missing:
            print(f"  Other gaps:   {other_missing[:5]}")
    print(f"  Next action: {next_action}")

    if dry_run:
        print("  [dry-run] No writes.")
        return

    # 5. Patch company_profiles
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    profile_patch = {
        "completeness_score":      completeness_score,
        "missing_fields":          missing_fields,
        "completeness_checked_at": now_iso,
    }
    # Find the company_profiles row for this entity × area
    cp_rows = _sb_get(sb_url, sb_key, "company_profiles", {
        "company_id": f"eq.{company_id}",
        "area_id":    f"eq.{area_id}",
        "select":     "company_id",
    })
    if cp_rows:
        _sb_patch(sb_url, sb_key, "company_profiles",
                  {"company_id": company_id, "area_id": area_id},
                  profile_patch)
        print(f"  ✓ company_profiles updated: score={completeness_score} "
              f"missing={len(missing_fields)}")
    else:
        print(f"  ⚠ No company_profiles row for {company_id}/{area_id} — skipping patch")

    # 6. Update research_queue
    priority_score = int(completeness_score * 0.6 + (
        30 if completeness_tier == "thin" else (20 if completeness_tier == "partial" else 10)
    ))
    rq_rows = _sb_get(sb_url, sb_key, "research_queue", {
        "entity_id": f"eq.{entity_id}",
        "area_id":   f"eq.{area_id}",
        "select":    "entity_id",
    })
    rq_patch = {
        "priority_score":        priority_score,
        "completeness_score":    completeness_score,
        "completeness_tier":     completeness_tier,
        "next_best_action":      next_action,
        "missing_fields":        missing_fields,
    }
    if rq_rows:
        _sb_patch(sb_url, sb_key, "research_queue",
                  {"entity_id": entity_id, "area_id": area_id},
                  rq_patch)
        print(f"  ✓ research_queue updated: priority={priority_score}")
    else:
        print(f"  ⚠ No research_queue row for {entity_id}/{area_id} — not updated")

    print(f"{'═'*60}\n")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="BD Platform — Research Intelligence Audit"
    )
    parser.add_argument(
        "--area",
        default="",
        help="Disease area to audit (tl1a | tslp | il4ra | fcrn | igf1r | tcell | all). "
             "Required for audit mode; optional for --rescore-molecule if area can be inferred.",
    )
    parser.add_argument(
        "--entity",
        default="",
        help="Optional: filter by entity_id substring",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and score but do not write to Supabase",
    )
    parser.add_argument(
        "--rescore-molecule",
        default="",
        metavar="DRUG_ID",
        help="Re-score completeness for the company owning DRUG_ID after manual curation. "
             "Updates company_profiles.completeness_score and research_queue. "
             "Requires --area. Example: --rescore-molecule tulisokibart --area tl1a",
    )
    args = parser.parse_args()

    if args.rescore_molecule:
        # Rescore a single molecule after manual curation
        if not args.area:
            print("ERROR: --area is required with --rescore-molecule")
            sys.exit(1)
        rescore_molecule(
            drug_id=args.rescore_molecule,
            area_id=args.area,
            dry_run=args.dry_run,
        )
    else:
        # Standard intelligence audit
        if not args.area:
            print("ERROR: --area is required for audit mode")
            sys.exit(1)
        areas = ALL_AREAS if args.area == "all" else [args.area]
        for area in areas:
            run_intelligence_audit(
                area_id=area,
                entity_filter=args.entity or None,
                dry_run=args.dry_run,
            )

    sys.exit(0)
