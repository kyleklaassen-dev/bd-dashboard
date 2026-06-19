#!/usr/bin/env python3
"""
coverage_scoring.py — pure coverage sub-score functions + weights (§3 split).

The dimension constants and the ten score_* functions (+ compute_overall,
build_recommendations). Pure: each takes already-indexed data and returns
scores; no I/O. Extracted verbatim from compute_coverage.py.
"""
import datetime


STALE_DAYS = 30          # profiles older than this score below 70
VERY_STALE_DAYS = 60     # profiles older than this score below 30
CLINICAL_STAGES = {"Phase 1", "Phase 1/2", "Phase 2", "Phase 2/3", "Phase 3",
                   "Phase 3/4", "BLA/NDA", "Approved", "Pre-BLA"}
# Approved drugs have completed their development catalysts — exclude from
# catalyst_coverage denominator so they don't artificially inflate the gap.
ACTIVE_STAGES = CLINICAL_STAGES - {"Approved"}

# Dimension weights for overall_score
WEIGHTS = {
    "profile_completeness_score":   2.0,
    "source_coverage_score":        2.0,
    "enrichment_recency_score":     1.5,
    "target_mapping_score":         1.0,
    "ownership_coverage_score":     1.0,
    "confidence_coverage_score":    1.0,
    "molecule_intelligence_score":  1.0,
    "catalyst_coverage_score":      1.0,
    "deal_linkage_score":           0.5,
}

# ── Supabase helpers ──────────────────────────────────────────────────────────


def score_target_mapping(drugs_in_scope, idx):
    if not drugs_in_scope:
        return 100.0, [], []
    mapped = [d for d in drugs_in_scope if d in idx["drugs_with_targets"]]
    unmapped = [d for d in drugs_in_scope if d not in idx["drugs_with_targets"]]
    score = len(mapped) / len(drugs_in_scope) * 100
    return round(score, 1), unmapped, []


def score_ownership_coverage(company_id, area_id, drugs_in_scope, data, idx):
    """% of licensed-in drugs (has partner_company) with ownership_edges."""
    licensed_drugs = [
        d for d in drugs_in_scope
        if data["drugs"].get(d, {}).get("partner_company")
    ]
    if not licensed_drugs:
        return 100.0, [], []  # No licensed drugs → no gap

    covered = [
        d for d in licensed_drugs
        if idx["drug_ownership_predicates"].get(d)
    ]
    missing = [d for d in licensed_drugs if d not in covered]
    score = len(covered) / len(licensed_drugs) * 100
    return round(score, 1), missing, []


def score_source_coverage(drugs_in_scope, area_id, idx):
    """% of sourced drug_area_scores rows, denominated on confirmed+supported only.

    Semantic rationale:
      - 'confirmed' rows are claims backed by primary sources — source_url required (E6)
      - 'supported' rows have corroborating evidence — source_url strongly expected
      - 'inferred' rows represent model-inferred classifications, not sourced claims
      - 'null' rows are legacy data with unassigned confidence
    Only confirmed+supported rows count against the denominator. Having source_url
    on inferred/null rows is a bonus (data quality) but should not penalise the score.
    """
    relevant = [
        idx["das_by_drug_area"][(d, area_id)]
        for d in drugs_in_scope
        if (d, area_id) in idx["das_by_drug_area"]
    ]
    if not relevant:
        return 50.0, [], ["No drug_area_scores rows found"]  # unknown state

    # Denominator: only rows that are expected to have a source
    SOURCED_CONFIDENCE = {"confirmed", "supported"}
    scored_rows = [r for r in relevant if (r.get("confidence_level") or "") in SOURCED_CONFIDENCE]

    if not scored_rows:
        # All rows are inferred/null — not a gap, return neutral
        return 80.0, [], []

    with_source = [r for r in scored_rows if r.get("source_url")]
    e6_violations = [
        r["drug_id"] for r in scored_rows
        if r.get("confidence_level") == "confirmed" and not r.get("source_url")
    ]
    score = len(with_source) / len(scored_rows) * 100
    # Penalise E6 violations (should never occur — enforced by enrichment invariant)
    if e6_violations:
        score = max(0, score - len(e6_violations) * 10)
    missing = [r["drug_id"] for r in scored_rows if not r.get("source_url")]
    return round(score, 1), missing, [f"E6 violation: {d}" for d in e6_violations]


def score_confidence_coverage(drugs_in_scope, area_id, idx):
    """% of drug_area_scores with non-null confidence_level."""
    relevant = [
        idx["das_by_drug_area"][(d, area_id)]
        for d in drugs_in_scope
        if (d, area_id) in idx["das_by_drug_area"]
    ]
    if not relevant:
        return 50.0, [], []
    with_conf = [r for r in relevant if r.get("confidence_level")]
    score = len(with_conf) / len(relevant) * 100
    missing = [r["drug_id"] for r in relevant if not r.get("confidence_level")]
    return round(score, 1), missing, []


def score_enrichment_recency(company_id, area_id, idx):
    """Score based on how recently company_profiles was enriched."""
    profile = idx["profiles"].get((company_id, area_id)) or idx["profiles"].get((company_id, None))
    if not profile:
        return 0.0, ["No company_profiles row"], []

    last = profile.get("last_enriched_at")
    if not last:
        return 10.0, ["last_enriched_at is null"], []

    try:
        dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 10.0, ["Could not parse last_enriched_at"], []

    if age_days < 7:
        return 100.0, [], []
    elif age_days < 14:
        return 90.0, [], []
    elif age_days < STALE_DAYS:
        return 70.0, [], []
    elif age_days < VERY_STALE_DAYS:
        return 40.0, [f"Profile {age_days}d old (stale >30d)"], []
    else:
        return 10.0, [f"Profile {age_days}d old (very stale >60d)"], []


def score_deal_linkage(company_id, idx):
    """% of transactional ownership_edges (LICENSED_IN, ACQUIRED, SPUN_OUT_FROM) with deal_id.
    ORIGINATED_BY and CONTROLLED_BY are provenance facts, not deal events — excluded from denominator."""
    TRANSACTIONAL_PREDICATES = {"LICENSED_IN", "ACQUIRED", "SPUN_OUT_FROM", "LICENSED_FROM"}
    all_edges = idx["company_acquisition_edges"].get(company_id, [])
    edges = [e for e in all_edges if e.get("predicate") in TRANSACTIONAL_PREDICATES]
    if not edges:
        return 100.0, [], []  # No transactional deals → nothing to link
    with_deal = [e for e in edges if e.get("deal_id")]
    missing = [e["subject_id"] + "→" + e["object_id"] for e in edges if not e.get("deal_id")]
    score = len(with_deal) / len(edges) * 100
    return round(score, 1), missing, []


def score_molecule_intelligence(drugs_in_scope, idx):
    """% of drugs with molecule_intelligence rows."""
    if not drugs_in_scope:
        return 100.0, [], []
    with_mi = [d for d in drugs_in_scope if d in idx["drugs_with_mi"]]
    missing = [d for d in drugs_in_scope if d not in idx["drugs_with_mi"]]
    score = len(with_mi) / len(drugs_in_scope) * 100
    return round(score, 1), missing, []


def score_catalyst_coverage(drugs_in_scope, area_id, data, idx):
    """% of active clinical-stage drugs with ≥1 unresolved future catalyst.
    Denominator uses ACTIVE_STAGES (excludes 'Approved') — approved drugs have
    completed their development lifecycle and should not count as gaps.
    """
    clinical_drugs = [
        d for d in drugs_in_scope
        if data["drugs"].get(d, {}).get("stage", "") in ACTIVE_STAGES
    ]
    if not clinical_drugs:
        return 100.0, [], []  # No clinical drugs → nothing expected

    with_catalyst = [d for d in clinical_drugs if (d, area_id) in idx["drugs_with_catalyst"]]
    missing = [d for d in clinical_drugs if (d, area_id) not in idx["drugs_with_catalyst"]]
    score = len(with_catalyst) / len(clinical_drugs) * 100
    return round(score, 1), missing, []


def score_profile_completeness(company_id, area_id, idx):
    """% of expected company_profiles fields present."""
    profile = idx["profiles"].get((company_id, area_id)) or idx["profiles"].get((company_id, None))
    if not profile:
        return 0.0, ["No company_profiles row — run company_enrichment.py"], []

    expected_fields = [
        "platform_summary", "bd_summary", "key_risk",
        "risk_summary", "bd_angle", "vs_ailux"
    ]
    present = [f for f in expected_fields if profile.get(f)]
    missing = [f for f in expected_fields if not profile.get(f)]
    score = len(present) / len(expected_fields) * 100
    return round(score, 1), missing, []


# ── Overall score ─────────────────────────────────────────────────────────────

def compute_overall(scores_dict):
    total_weight = 0.0
    weighted_sum = 0.0
    for dim, weight in WEIGHTS.items():
        val = scores_dict.get(dim)
        if val is not None:
            weighted_sum += val * weight
            total_weight += weight
    if total_weight == 0:
        return None
    return round(weighted_sum / total_weight, 1)


# ── Recommended actions ───────────────────────────────────────────────────────

def build_recommendations(scores, missing):
    actions = []
    thresholds = {
        "profile_completeness_score": (60, "Run company_enrichment.py to fill missing profile fields"),
        "enrichment_recency_score":   (60, "Re-enrich company profile — data is stale (>30 days)"),
        "source_coverage_score":      (70, "Add source_url to drug_area_scores rows missing citations"),
        "confidence_coverage_score":  (70, "Set confidence_level on drug_area_scores rows"),
        "target_mapping_score":       (80, "Add drug_targets rows for unmapped drugs"),
        "molecule_intelligence_score":(70, "Run molecule_enrichment for drugs missing MI"),
        "catalyst_coverage_score":    (60, "Add catalyst entries for clinical-stage drugs"),
        "ownership_coverage_score":   (70, "Add ownership_edges for licensed-in drugs"),
        "deal_linkage_score":         (70, "Link ownership_edges to deals table via deal_id"),
    }
    for dim, (threshold, action) in thresholds.items():
        val = scores.get(dim)
        if val is not None and val < threshold:
            count = len(missing.get(dim, []))
            suffix = f" ({count} items)" if count else ""
            actions.append(action + suffix)
    return actions
