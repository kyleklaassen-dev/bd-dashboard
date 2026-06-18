#!/usr/bin/env python3
"""Next-best-action + research triggers (§3 research_intelligence split)."""

from __future__ import annotations

from datetime import datetime, timezone

from meridian.scoring.research_intel.common import _nonempty, DRUG_STAGE_RANK, TRIAL_PHASE_RANK


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
