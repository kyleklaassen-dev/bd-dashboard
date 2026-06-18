#!/usr/bin/env python3
"""Completeness scoring (§3 research_intelligence split)."""

from __future__ import annotations

from meridian.scoring.research_intel.common import (
    _group_drugs_by_canonical, _merge_drug_rows, _nonempty, _now_iso,
    STAGE_WEIGHTS, TIER_THRESHOLDS,
)


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
