#!/usr/bin/env python3
"""Coverage / evidence-tier / strategic-value scoring + combo checks (§3 drug_intake split)."""

from datetime import datetime, timezone

import requests

from meridian.ingestion.drugintake.common import _sb_headers, SUPABASE_URL, SUPABASE_KEY


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — COVERAGE SCORE (Completeness Audit)
# ══════════════════════════════════════════════════════════════════════════════

def compute_coverage_score(
    resolution: dict,
    graph_state: dict,
    research: dict,
) -> dict:
    """
    Score each coverage dimension 0 / 50 / 100.
    Returns dict with per-dimension scores + overall coverage_score (int, average of scored dims).
    """
    dims = {}
    drug_row = graph_state.get("drug") or {}
    mi       = graph_state.get("molecule_intelligence")
    trials   = graph_state.get("trials") or []
    catalysts = graph_state.get("catalysts") or []
    signals  = graph_state.get("signals") or []
    deals    = graph_state.get("deals") or []

    # 1. Identity
    rtype = resolution.get("resolution_type", "candidate_new")
    if rtype == "existing_drug":
        dims["identity"] = 100
    elif rtype == "fuzzy_match":
        dims["identity"] = 75
    else:
        dims["identity"] = 0

    # 2. Company
    company_id = drug_row.get("company_id") or resolution.get("company_id_hint")
    if company_id:
        dims["company"] = 100
    elif research.get("drug", {}).get("company_id_hint"):
        dims["company"] = 50
    else:
        dims["company"] = 0

    # 3. Target
    target = drug_row.get("target") or research.get("drug", {}).get("target")
    if target and len(target) > 3 and target.lower() not in ("unknown", "n/a", "tbd"):
        dims["target"] = 100
    elif target:
        dims["target"] = 50
    else:
        dims["target"] = 0

    # 4. Trials
    active_trials = [t for t in trials if t.get("status") not in ("Completed", "Withdrawn", "Terminated")]
    all_trials    = trials
    if len(all_trials) >= 2:
        dims["trials"] = 100
    elif len(all_trials) == 1:
        dims["trials"] = 50
    else:
        # Check if research found any
        nct_ids = research.get("drug", {}).get("nct_ids") or []
        dims["trials"] = 25 if nct_ids else 0

    # 5. Catalysts
    if len(catalysts) >= 3:
        dims["catalysts"] = 100
    elif len(catalysts) >= 1:
        dims["catalysts"] = 50
    else:
        # Check if research found upcoming catalysts
        upcoming = research.get("upcoming_catalysts") or []
        dims["catalysts"] = 25 if upcoming else 0

    # 6. Molecule Intelligence
    if mi:
        # Count non-null non-trivial fields
        mi_fields = ["format", "valency", "igg_subclass", "fc_engineering", "epitope",
                     "affinity_kd", "differentiation_claim"]
        filled = sum(1 for f in mi_fields if mi.get(f) and mi[f] not in ("unknown", "not publicly disclosed", "none known", "null"))
        if filled >= 4:
            dims["molecule_intel"] = 100
        elif filled >= 2:
            dims["molecule_intel"] = 50
        else:
            dims["molecule_intel"] = 25
    else:
        # Research may have molecule intel fields
        mi_research = research.get("molecule_intelligence") or {}
        filled_r = sum(1 for v in mi_research.values() if v and v != "null")
        dims["molecule_intel"] = 25 if filled_r >= 2 else 0

    # 7. Conference Intelligence
    conf_signals = [s for s in signals if s.get("signal_type") in ("conference", "abstract", "presentation")]
    if conf_signals:
        dims["conference_intel"] = 100
    elif signals:
        dims["conference_intel"] = 50
    else:
        dims["conference_intel"] = 0

    # 8. Deals (N/A for genuinely new drugs with no company anchor)
    company_known = drug_row.get("company_id") or research.get("drug", {}).get("company_id_hint")
    if not company_known:
        dims["deals"] = None  # N/A
    elif len(deals) >= 2:
        dims["deals"] = 100
    elif len(deals) == 1:
        dims["deals"] = 50
    else:
        dims["deals"] = 0

    # Overall: average of scored (non-None) dimensions
    scored = [v for v in dims.values() if v is not None]
    overall = int(sum(scored) / len(scored)) if scored else 0

    return {
        "dimensions": dims,
        "coverage_score": overall,
        "active_trials_count": len(active_trials),
        "total_trials_count":  len(all_trials),
        "catalysts_count":     len(catalysts),
        "mi_exists":           mi is not None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# EVIDENCE TIER — explicit confidence for preclinical/emerging programs
# ══════════════════════════════════════════════════════════════════════════════

_CLINICAL_STAGES = {"Phase 1", "Phase 2", "Phase 3", "Approved", "Phase 1/2", "Phase 2/3"}
_PRECLINICAL_STAGES = {"Preclinical", "IND-enabling", "IND Enabling"}
_DISCOVERY_STAGES = {"Discovery", "Undisclosed", "Unknown", ""}

def compute_evidence_tier(research: dict) -> dict:
    """
    Assign an evidence tier to characterise how much we can trust this drug's data.

    Tiers:
      Confirmed  — Named molecule + company source + clinical stage (Phase 1–Approved).
                   High data quality. Can be promoted directly.
      Likely     — Named molecule + company source + preclinical/IND-enabling stage,
                   OR medium data quality with a clinical stage.
                   Promote with standard review.
      Emerging   — Low data quality OR stage Discovery/Undisclosed with some evidence.
                   Promote only after manual verification.
      Hypothesis — No named molecule OR no company anchor.
                   Do NOT create a production drug row without manual approval.

    Returns dict: { tier, rationale, can_auto_promote, review_note }
    """
    drug_info    = research.get("drug", {})
    data_quality = (drug_info.get("data_quality") or "low").lower()
    stage        = drug_info.get("stage") or ""
    has_name     = bool((drug_info.get("canonical_name") or "").strip())
    has_company  = bool((drug_info.get("company") or drug_info.get("company_id_hint") or "").strip())
    has_target   = bool((drug_info.get("target") or "").strip())
    source_note  = drug_info.get("source_note") or ""

    # Hypothesis: no named molecule or no company anchor
    if not has_name or not has_company:
        return {
            "tier":             "Hypothesis",
            "rationale":        "No named molecule or no company anchor — strategic inference only.",
            "can_auto_promote": False,
            "review_note":      "⚠️  Do NOT create a production drug row without manual approval. "
                                "Keep as signal or hypothesis until evidence is confirmed.",
        }

    # Confirmed: high data quality + clinical stage
    if data_quality == "high" and stage in _CLINICAL_STAGES:
        return {
            "tier":             "Confirmed",
            "rationale":        f"Named molecule + company source + {stage}. High data quality.",
            "can_auto_promote": True,
            "review_note":      "✅ Standard review. Evidence quality is high.",
        }

    # Likely: high quality preclinical OR medium quality clinical
    if (data_quality == "high" and stage in _PRECLINICAL_STAGES) or \
       (data_quality == "medium" and stage in _CLINICAL_STAGES):
        tier_rationale = (
            f"Named molecule + company source + {stage}." if stage in _PRECLINICAL_STAGES
            else f"{stage} stage with medium data quality."
        )
        return {
            "tier":             "Likely",
            "rationale":        tier_rationale,
            "can_auto_promote": True,
            "review_note":      "Standard review. Cross-check company pipeline page before promoting.",
        }

    # Emerging: low data quality OR discovery stage but mechanism known
    if has_target and (data_quality == "low" or stage in _DISCOVERY_STAGES):
        return {
            "tier":             "Emerging",
            "rationale":        f"Mechanism known ({drug_info.get('target')}) but data quality={data_quality}, stage={stage or 'unknown'}.",
            "can_auto_promote": False,
            "review_note":      "⚠️  Manual verification required before promotion. "
                                "Confirm molecule name + company source from primary evidence.",
        }

    # Default: Emerging
    return {
        "tier":             "Emerging",
        "rationale":        f"data_quality={data_quality}, stage={stage or 'unknown'}.",
        "can_auto_promote": False,
        "review_note":      "⚠️  Manual verification required. Check primary source before promoting.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGIC VALUE SCORE — BD importance, orthogonal to coverage + evidence tier
# ══════════════════════════════════════════════════════════════════════════════

# Core areas for Ailux's bispecific program — overlap here is highest priority
_CORE_AREAS = {"tl1a", "tslp", "il4ra"}

# Major pharma / active BD companies (Meridian company_ids)
_MAJOR_PHARMA = {
    "astrazeneca", "abbvie", "roche", "pfizer", "jnj", "lilly", "merck",
    "sanofi", "novartis", "gsk", "amgen", "bms", "boehringer", "gilead",
    "regeneron", "biogen", "takeda", "astellas", "astellas", "vertex",
}


def compute_strategic_value_score(
    overlap:       str,
    area_id:       str,
    stage:         str | None,
    catalysts:     list,
    deals:         list,
    evidence_tier: dict | None,
    company_id:    str | None,
) -> int:
    """
    Score BD importance 0–10.

    Scoring model (max ~10 before rounding):
      Overlap × Area Primacy   0–4.0   Direct in core area = 4; Watch = 0.5
      Stage Maturity           0–2.0   Phase 3 / Approved = 2; Discovery = 0
      Catalyst Proximity       0–1.5   Catalyst within 90 days = 1.5
      Evidence Confidence      0–1.0   Confirmed = 1; Hypothesis = 0.1
      Deal Activity            0–0.75  Has deals = 0.75
      Company Importance       0–0.5   Major pharma = 0.5

    Principle: a 30%-coverage Direct competitor in a core area scores higher than
    a 95%-coverage Watch drug. Coverage = how complete; strategic_value = how important.
    """
    score = 0.0
    stage_str    = (stage or "").strip()
    is_core      = area_id in _CORE_AREAS

    # ── 1. Overlap × Area Primacy (0–4) ──────────────────────────────────────
    _overlap_base = {
        "Direct":       4.0 if is_core else 3.5,
        "Adjacent":     3.0 if is_core else 2.0,
        "Same-Space":   1.5,
        "Same-patient": 1.5,
        "Watch":        0.5,
        "Watchlist":    0.5,
    }
    score += _overlap_base.get(overlap, 0.5)

    # ── 2. Stage Maturity (0–2) ──────────────────────────────────────────────
    _stage_score = {
        "Approved":      2.0,
        "Phase 3":       2.0,
        "Phase 2/3":     1.75,
        "Phase 2":       1.5,
        "Phase 1/2":     1.0,
        "Phase 1":       1.0,
        "IND-enabling":  0.5,
        "IND Enabling":  0.5,
        "Preclinical":   0.25,
        "Discovery":     0.0,
        "Undisclosed":   0.0,
    }
    score += _stage_score.get(stage_str, 0.5)

    # ── 3. Catalyst Proximity (0–1.5) ────────────────────────────────────────
    # catalysts are already filtered to future dates in fetch_graph_state
    if catalysts:
        nearest_days: int | None = None
        for c in catalysts:
            date_str = c.get("catalyst_date") or c.get("sort_date")
            if date_str:
                try:
                    from datetime import datetime, timezone
                    cd = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                    # Ensure aware datetime for comparison
                    if cd.tzinfo is None:
                        cd = cd.replace(tzinfo=timezone.utc)
                    days = (cd - datetime.now(timezone.utc)).days
                    if nearest_days is None or days < nearest_days:
                        nearest_days = days
                except Exception:
                    pass
        if nearest_days is not None:
            if nearest_days <= 90:
                score += 1.5
            elif nearest_days <= 180:
                score += 1.0
            elif nearest_days <= 365:
                score += 0.5
        else:
            score += 0.25  # catalysts exist but no parseable date

    # ── 4. Evidence Confidence (0–1) ─────────────────────────────────────────
    tier_name = (evidence_tier or {}).get("tier", "Emerging")
    _tier_score = {"Confirmed": 1.0, "Likely": 0.8, "Emerging": 0.4, "Hypothesis": 0.1}
    score += _tier_score.get(tier_name, 0.4)

    # ── 5. Deal Activity (0–0.75) ────────────────────────────────────────────
    if deals:
        score += 0.75

    # ── 6. Company Importance (0–0.5) ────────────────────────────────────────
    if company_id and company_id.lower() in _MAJOR_PHARMA:
        score += 0.5
    elif company_id:
        score += 0.25

    return min(10, max(0, int(score + 0.5)))  # standard rounding (not banker's)


# ══════════════════════════════════════════════════════════════════════════════
# COMBO COMPONENT VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def check_combo_components(
    drug_id:    str | None,
    drug_name:  str,
    drug_row:   dict,
    area_ids:   list[str],
    all_drugs_cache: list[dict] | None = None,
    verbose: bool = False,
) -> list[dict]:
    """
    If this drug is a combination, verify each component drug has area links
    for every area the combination is linked to.

    Rule: if guselkumab-golimumab is in drug_areas.tl1a, then both guselkumab
    and golimumab should also be in drug_areas.tl1a.

    Detects combinations via:
      1. drug.target containing '×', '+', or '/'
      2. drug.name or drug.id containing ' + ' or being in form drugA-drugB
         where each part matches a known drug

    Returns list of warning dicts: { component, area_id, issue, suggestion }
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []

    target   = drug_row.get("target") or ""
    name_raw = drug_row.get("name") or drug_name or ""
    drug_id  = drug_id or ""

    # Quick exit: if target has no multi-target indicators and name has no combo markers
    is_likely_combo = (
        any(sep in target for sep in ("×", "+", "/"))
        or " + " in name_raw
        or " + " in drug_id
    )

    # Also check for dash-joined drug names (e.g. guselkumab-golimumab)
    # Only trigger if each dash-separated part fuzzy-matches a known drug name
    candidate_components: list[str] = []

    if not is_likely_combo and "-" in drug_id:
        # Try to split by dash and see if each part is a known drug
        parts = drug_id.split("-")
        if len(parts) >= 2:
            # Fetch all drug ids for matching
            try:
                resp = requests.get(
                    f"{SUPABASE_URL}/rest/v1/drugs",
                    headers={**_sb_headers, "Prefer": ""},
                    params={"select": "id,name", "limit": "2000"},
                    timeout=10,
                )
                known = {d["id"]: d["name"] for d in (resp.json() if resp.status_code == 200 else [])}
            except Exception:
                known = {}

            matched_parts = [p for p in parts if p in known]
            if len(matched_parts) >= 2:
                candidate_components = matched_parts
                is_likely_combo = True

    if not is_likely_combo:
        return []

    # Parse components from name / target
    if not candidate_components:
        if " + " in name_raw:
            candidate_components = [p.strip().lower().replace(" ", "-") for p in name_raw.split("+")]
        elif any(sep in target for sep in ("×", "+")):
            sep = "×" if "×" in target else "+"
            candidate_components = [p.strip().lower().replace(" ", "-") for p in target.split(sep)]

    if not candidate_components:
        return []

    # For each component, check drug_areas for each area_id
    warnings = []

    for component in candidate_components:
        # Try both the raw component and without trailing modifiers
        component_clean = component.strip().split("(")[0].strip()

        for area_id in area_ids:
            try:
                resp = requests.get(
                    f"{SUPABASE_URL}/rest/v1/drug_areas",
                    headers={**_sb_headers, "Prefer": ""},
                    params={"drug_id": f"eq.{component_clean}", "area_id": f"eq.{area_id}", "select": "drug_id"},
                    timeout=8,
                )
                rows = resp.json() if resp.status_code == 200 else []
            except Exception:
                rows = []

            if not rows:
                # Check if component drug even exists
                try:
                    drug_exists = requests.get(
                        f"{SUPABASE_URL}/rest/v1/drugs",
                        headers={**_sb_headers, "Prefer": ""},
                        params={"id": f"eq.{component_clean}", "select": "id,name,stage"},
                        timeout=8,
                    )
                    exists_rows = drug_exists.json() if drug_exists.status_code == 200 else []
                except Exception:
                    exists_rows = []

                if not exists_rows:
                    warnings.append({
                        "component":  component_clean,
                        "area_id":    area_id,
                        "issue":      "component_drug_missing",
                        "suggestion": f"Add drug row for '{component_clean}' — component of '{drug_name}'",
                    })
                else:
                    warnings.append({
                        "component":  component_clean,
                        "area_id":    area_id,
                        "issue":      "component_missing_area_link",
                        "suggestion": f"Add drug_areas + drug_area_scores for '{component_clean}' in '{area_id}' — component of '{drug_name}'",
                    })

    return warnings


# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT A — ROUTING DECISION
# ══════════════════════════════════════════════════════════════════════════════
