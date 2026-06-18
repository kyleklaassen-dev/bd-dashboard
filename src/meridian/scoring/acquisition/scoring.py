#!/usr/bin/env python3
"""Five-dimension acquisition-target scoring (§3 acquisition_scorer split)."""

from datetime import date

from meridian.scoring.acquisition.common import (
    ABBVIE_CONSTRAINT_UNTIL, ABBVIE_CONSTRAINT_NOTE, EXCLUDE_COMPANY_IDS, FORCE_HOLD_STATUSES, TODAY,
)


# ---------------------------------------------------------------------------
# Step 3: Scoring helpers
# ---------------------------------------------------------------------------

# Normalized overlap values
DIRECT_OVERLAPS = {"direct", "Direct"}
ADJACENT_OVERLAPS = {"adjacent", "Adjacent"}
SAME_SPACE_OVERLAPS = {"same-space", "Same-Space"}

# Bispecific indicators
BISPECIFIC_KEYWORDS = {"bispecific", "bsab", "bispecific_vhh", "bispecific mab"}

# Approved stage values
APPROVED_STAGES = {
    "approved", "Approved", "approved_us", "approved_eu", "approved_us_eu",
    "approved_partial", "approved_china", "bla_under_review"
}

# Large pharma company types (harder deal, regulatory scrutiny)
LARGE_PHARMA_TYPES = {"large_pharma", "big_pharma", "large_cap"}
MID_PHARMA_TYPES = {"mid_pharma", "mid_cap", "pharma"}
BIOTECH_TYPES = {"biotech", "small_cap", "Biotech", "big_biotech", "innovative"}
PRIVATE_TYPES = {"private"}


def _days_until(date_str):
    """Days until a future date. Negative = past."""
    if not date_str:
        return 9999
    try:
        d = date.fromisoformat(str(date_str)[:10])
        return (d - TODAY).days
    except Exception:
        return 9999


def _is_bispecific(drug):
    fmt = (drug.get("drug_format") or "").lower()
    modality = (drug.get("modality") or "").lower()
    cls = (drug.get("cls") or "").lower()
    name = (drug.get("name") or "").lower()
    return (
        any(k in fmt for k in BISPECIFIC_KEYWORDS)
        or any(k in modality for k in BISPECIFIC_KEYWORDS)
        or any(k in cls for k in BISPECIFIC_KEYWORDS)
        or "×" in name or " x " in name
    )


# ---------------------------------------------------------------------------
# Dimension 1: Strategic Overlap (0-20)
# ---------------------------------------------------------------------------

def score_dim1_overlap(company, idx):
    """
    D1: Does this company have drugs that directly compete with Ailux assets?
    Uses drug-level overlap field + competitive_relevance from drug_competitive_scores.
    """
    cid = company["id"]
    company_drugs = idx["company_drugs"].get(cid, [])
    company_overlap = (company.get("overlap") or "").strip()
    comp_rel = idx["company_comp_relevance"].get(cid, "none")

    # Best drug-level overlap
    best_overlap = "none"
    best_stage = ""
    for d in company_drugs:
        ov = (d.get("overlap") or "").strip()
        st = (d.get("stage") or "").strip()
        if ov in DIRECT_OVERLAPS:
            # Prefer clinical-stage direct overlaps
            if best_overlap not in DIRECT_OVERLAPS or st in ("Phase 2", "Phase 3", "Phase 2/3"):
                best_overlap = ov
                best_stage = st
        elif ov in ADJACENT_OVERLAPS and best_overlap not in DIRECT_OVERLAPS:
            best_overlap = ov
            best_stage = st
        elif ov in SAME_SPACE_OVERLAPS and best_overlap not in DIRECT_OVERLAPS | ADJACENT_OVERLAPS:
            best_overlap = ov
            best_stage = st

    # Fall back to company-level overlap
    if best_overlap == "none" and company_overlap in DIRECT_OVERLAPS:
        best_overlap = company_overlap

    # Score by overlap + stage combo
    if best_overlap in DIRECT_OVERLAPS:
        if best_stage in ("Phase 2", "Phase 3", "Phase 2/3", "Phase 3 complete"):
            pts = 20
            reason = f"Direct overlap — clinical stage ({best_stage})"
        elif best_stage in ("Phase 1", "Phase 1/2"):
            pts = 15
            reason = f"Direct overlap — Phase 1"
        elif best_stage == "Preclinical" or best_stage == "IND Enabling":
            pts = 10
            reason = "Direct overlap — preclinical"
        elif best_stage in APPROVED_STAGES:
            pts = 12
            reason = "Direct overlap — approved asset"
        else:
            pts = 8
            reason = "Direct overlap — stage unknown"
    elif best_overlap in ADJACENT_OVERLAPS:
        pts = 8
        reason = "Adjacent overlap"
    elif best_overlap in SAME_SPACE_OVERLAPS:
        pts = 5
        reason = "Same-Space overlap"
    else:
        # Check competitive scores as fallback
        if comp_rel == "very_high":
            pts = 12
            reason = "Very high competitive relevance score (no direct overlap tag)"
        elif comp_rel == "high":
            pts = 8
            reason = "High competitive relevance score"
        else:
            pts = 0
            reason = "No relevant overlap"

    return pts, reason


# ---------------------------------------------------------------------------
# Dimension 2: BD Timing Urgency (0-20)
# ---------------------------------------------------------------------------

def score_dim2_timing(company, idx):
    """
    D2: Is there a readout / regulatory event coming that creates time pressure?
    """
    cid = company["id"]
    company_drugs = idx["company_drugs"].get(cid, [])
    upcoming = idx["company_catalysts"].get(cid, [])

    # Check if company has approved drugs (closing deal window)
    all_approved = all(
        (d.get("stage") or "") in APPROVED_STAGES
        for d in company_drugs
        if company_drugs
    )
    has_approved = any((d.get("stage") or "") in APPROVED_STAGES for d in company_drugs)

    if not upcoming:
        if has_approved:
            return 3, "Already approved — deal window may be closing"
        return 5, "No upcoming catalysts — stable baseline"

    # Find the soonest relevant readout
    best_days = 9999
    best_cat = None
    for cat in upcoming:
        days = _days_until(cat.get("expected_date"))
        if 0 < days < best_days:
            best_days = days
            best_cat = cat

    if best_cat is None:
        return 5, "No future-dated catalysts"

    drug_id = best_cat.get("drug_id", "")
    quarter = best_cat.get("expected_quarter", "")

    # Find drug stage for this catalyst
    drug_stage = "unknown"
    for d in company_drugs:
        if d["id"] == drug_id:
            drug_stage = d.get("stage") or "unknown"
            break

    if best_days <= 365:
        if drug_stage in ("Phase 2", "Phase 3", "Phase 2/3", "Phase 3 complete"):
            pts = 20
            reason = f"Ph2/3 readout within 12mo ({quarter}) — maximum timing urgency"
        elif drug_stage in ("Phase 1", "Phase 1/2"):
            pts = 15
            reason = f"Ph1 readout within 12mo ({quarter})"
        elif drug_stage in APPROVED_STAGES:
            pts = 8
            reason = f"Regulatory decision within 12mo ({quarter})"
        else:
            pts = 10
            reason = f"Catalyst within 12mo ({quarter})"
    elif best_days <= 730:
        pts = 10
        reason = f"Readout in 13-24mo ({quarter})"
    else:
        pts = 5
        reason = f"Readout >24mo out ({quarter})"

    return pts, reason


# ---------------------------------------------------------------------------
# Dimension 3: Platform Value (0-20)
# ---------------------------------------------------------------------------

def score_dim3_platform(company, idx):
    """
    D3: Does this company have platform capabilities Ailux could leverage or acquire?
    """
    cid = company["id"]
    company_drugs = idx["company_drugs"].get(cid, [])

    bispecific_drugs = [d for d in company_drugs if _is_bispecific(d)]
    bispecific_clinical = [
        d for d in bispecific_drugs
        if (d.get("stage") or "") not in ("Preclinical", "IND Enabling", "")
    ]

    # FcRn / half-life extension detection
    fcrn_drugs = [
        d for d in company_drugs
        if "fcrn" in (d.get("target") or "").lower()
        or "fcrn" in (d.get("cls") or "").lower()
        or "half-life" in (d.get("drug_format") or "").lower()
        or "albumin" in (d.get("target") or "").lower()
    ]

    # Check target field for bispecific format indicators
    has_unique_engineering = any(
        any(kw in (d.get("target") or "").lower() for kw in ["×", " x ", "bispecific"])
        for d in company_drugs
    )

    if len(bispecific_drugs) >= 2 and len(bispecific_clinical) >= 1:
        pts = 20
        reason = f"Bispecific platform — {len(bispecific_drugs)} programs ({len(bispecific_clinical)} clinical)"
    elif len(bispecific_drugs) >= 2:
        pts = 17
        reason = f"Bispecific platform — {len(bispecific_drugs)} programs (preclinical)"
    elif len(fcrn_drugs) >= 1:
        pts = 15
        reason = f"FcRn/half-life engineering capability ({len(fcrn_drugs)} assets)"
    elif len(bispecific_drugs) == 1:
        pts = 12
        reason = f"Single bispecific program — emerging platform"
    elif has_unique_engineering:
        pts = 10
        reason = "Unique engineering capability detected"
    else:
        # Check company type for context
        ctype = (company.get("company_type") or "").lower()
        if ctype in ("large_pharma", "big_pharma"):
            pts = 10
            reason = "Large pharma — monospecific platform in target class"
        elif ctype in ("biotech", "small_cap", "innovative"):
            pts = 6
            reason = "Biotech — platform details limited in DB"
        else:
            pts = 0
            reason = "No bispecific/FcRn platform detected"

    return pts, reason


# ---------------------------------------------------------------------------
# Dimension 4: Deal Feasibility (0-20)
# ---------------------------------------------------------------------------

def score_dim4_feasibility(company, idx):
    """
    D4: How feasible is a deal with this company given size, structure, history?
    """
    cid = company["id"]
    ctype = (company.get("company_type") or "").lower()
    status = (company.get("status") or "").lower()
    deals = idx["company_deals"].get(cid, [])

    # Market cap heuristic from company_type
    if ctype in LARGE_PHARMA_TYPES:
        base_pts = 5
        size_reason = "Large pharma ($20B+) — harder deal, regulatory scrutiny"
    elif ctype in MID_PHARMA_TYPES:
        base_pts = 12
        size_reason = "Mid-cap pharma — BD track record likely"
    elif ctype in BIOTECH_TYPES:
        base_pts = 18
        size_reason = "Biotech — optimal deal target"
    elif ctype in PRIVATE_TYPES or status == "private":
        base_pts = 15
        size_reason = "Private company — flexible deal structure"
    elif status == "subsidiary":
        base_pts = 18
        size_reason = "Subsidiary with independent pipeline — high deal flexibility"
    elif ctype in ("innovative", "tcm", "state_owned"):
        base_pts = 10
        size_reason = "Specialty/regional company"
    else:
        base_pts = 8
        size_reason = "Company type unknown — moderate feasibility"

    # BD track record bonus
    bd_deal_count = len([d for d in deals if d.get("deal_type") in
                         {"acquisition", "Acquisition", "license", "License",
                          "licensing", "option", "collab", "partnership"}])
    if bd_deal_count >= 3:
        track_bonus = 2
        track_reason = f"Active BD history ({bd_deal_count} recorded deals)"
    elif bd_deal_count >= 1:
        track_bonus = 1
        track_reason = f"BD history present ({bd_deal_count} deals)"
    else:
        track_bonus = 0
        track_reason = "No recorded BD deals"

    pts = min(base_pts + track_bonus, 20)
    reason = f"{size_reason}; {track_reason}"

    return pts, reason


# ---------------------------------------------------------------------------
# Dimension 5: Ailux Competitive Window (0-20)
# ---------------------------------------------------------------------------

KNOWN_COMPETITORS_TO_AILUX = {
    # Companies with established TL1A programs competing directly with ALX001
    "sanofi",       # duvakitug Ph3 TL1A
    "merck",        # tulisokibart Ph3 TL1A
    "roche",        # afimkibart Ph3 TL1A + bispecific RO7837195
    "spyre",        # SPY002/SPY072 Ph2 TL1A
    "abbvie",       # ABBV-701 Ph1 TL1A (via FutureGen) — constrained
    "mirador",      # MDR-018 Ph2 + MT-251 Ph1 bispecific
    "xencor",       # XmAb942 Ph2 + XmAb412 bispecific
    "viridian",     # veligrotug BLA TED FcRn
    "immunovant",   # veligrotug BLA FcRn
}

CONSTRAINT_COMPANIES = {
    "abbvie": {
        "until": ABBVIE_CONSTRAINT_UNTIL,
        "note": ABBVIE_CONSTRAINT_NOTE,
    }
}


def score_dim5_window(company, idx):
    """
    D5: Does Ailux have a clear differentiation window? Constraints applied here.
    """
    cid = company["id"]
    company_drugs = idx["company_drugs"].get(cid, [])
    partnerships = idx["company_partnerships"].get(cid, [])
    bd_acquirers = idx["bd_acquirers"]

    # Hard constraint check first
    if cid in CONSTRAINT_COMPANIES:
        constraint = CONSTRAINT_COMPANIES[cid]
        if TODAY < constraint["until"]:
            return 0, f"CONSTRAINT ACTIVE: {constraint['note']}"

    pts = 0
    reasons = []

    # Ailux bispecific differentiation
    has_bispecific = any(_is_bispecific(d) for d in company_drugs)
    direct_drug_count = sum(
        1 for d in company_drugs
        if (d.get("overlap") or "") in DIRECT_OVERLAPS
    )

    # Does Ailux's bispecific format directly differentiate vs this company's monospecific?
    monospecific_only = company_drugs and not has_bispecific and direct_drug_count > 0
    if monospecific_only:
        pts += 20
        reasons.append("ALX001 bispecific directly differentiated vs monospecific TL1A program")
    elif has_bispecific and direct_drug_count > 0:
        pts += 8
        reasons.append("Both have bispecific — differentiation via dose/schedule/target combo")
    elif direct_drug_count > 0:
        pts += 12
        reasons.append("Direct overlap — Ailux bispecific may offer differentiation")

    # Partnership constraints that delay competitor development
    competitor_partnerships = [
        p for p in partnerships
        if p.get("partner_company_id") in KNOWN_COMPETITORS_TO_AILUX
        or p.get("deal_type") in ("licensing", "co-development", "option")
    ]
    if competitor_partnerships:
        pts = max(0, pts - 5)
        reasons.append("Existing competitor partnership may create exclusivity constraints")

    # Known BD acquirer — they WANT to do deals (positive signal)
    if cid in bd_acquirers:
        pts = min(pts + 5, 20)
        reasons.append("Known BD acquirer — receptive to external deals")

    # Already fully partnered with a known competitor → negative
    competitor_partner_ids = {
        p.get("partner_company_id") for p in partnerships
    } | {p.get("lead_company_id") for p in partnerships}
    if competitor_partner_ids & KNOWN_COMPETITORS_TO_AILUX:
        pts = max(0, pts - 10)
        reasons.append("Partnered with known Ailux competitor — BD window may be closed")

    if not reasons:
        pts = 5
        reasons.append("Baseline window — no direct overlap or constraint detected")

    pts = max(0, min(pts, 20))
    return pts, "; ".join(reasons)


# ---------------------------------------------------------------------------
# BD Priority rating
# ---------------------------------------------------------------------------

BD_RATING_SCALE = [
    (85, "CALL NOW"),
    (70, "PRIORITY"),
    (55, "WATCH"),
    (40, "MONITOR"),
    (0,  "HOLD"),
]


def _bd_rating(score):
    for threshold, label in BD_RATING_SCALE:
        if score >= threshold:
            return label
    return "HOLD"


# ---------------------------------------------------------------------------
# Step 3: Full scoring for one company
# ---------------------------------------------------------------------------


def score_company(company, idx):
    cid = company["id"]
    name = company.get("name", cid)

    # Exclusions
    if cid in EXCLUDE_COMPANY_IDS:
        return None

    # Acquired companies → HOLD regardless
    status = (company.get("status") or "").lower()
    if status in FORCE_HOLD_STATUSES:
        return {
            "company_id": cid,
            "company_name": name,
            "dim1_overlap": 0,
            "dim2_timing": 0,
            "dim3_platform": 0,
            "dim4_feasibility": 0,
            "dim5_window": 0,
            "total_score": 0,
            "bd_priority": "HOLD",
            "dim1_reason": "Acquired — absorbed into parent",
            "dim2_reason": "N/A",
            "dim3_reason": "N/A",
            "dim4_reason": "N/A",
            "dim5_reason": "N/A",
            "constraint_note": f"Status=acquired — company absorbed, not a BD target",
            "strategic_value_score": company.get("strategic_value_score"),
        }

    # AbbVie special constraint — cap at WATCH regardless of score
    abbvie_constrained = (
        cid == "abbvie" and TODAY < ABBVIE_CONSTRAINT_UNTIL
    )

    d1_pts, d1_reason = score_dim1_overlap(company, idx)
    d2_pts, d2_reason = score_dim2_timing(company, idx)
    d3_pts, d3_reason = score_dim3_platform(company, idx)
    d4_pts, d4_reason = score_dim4_feasibility(company, idx)
    d5_pts, d5_reason = score_dim5_window(company, idx)

    total = d1_pts + d2_pts + d3_pts + d4_pts + d5_pts
    total = min(total, 100)

    bd_priority = _bd_rating(total)

    constraint_note = None
    if abbvie_constrained:
        # Cap at WATCH
        if bd_priority in ("CALL NOW", "PRIORITY"):
            bd_priority = "WATCH"
        constraint_note = ABBVIE_CONSTRAINT_NOTE

    return {
        "company_id": cid,
        "company_name": name,
        "dim1_overlap": d1_pts,
        "dim2_timing": d2_pts,
        "dim3_platform": d3_pts,
        "dim4_feasibility": d4_pts,
        "dim5_window": d5_pts,
        "total_score": total,
        "bd_priority": bd_priority,
        "dim1_reason": d1_reason,
        "dim2_reason": d2_reason,
        "dim3_reason": d3_reason,
        "dim4_reason": d4_reason,
        "dim5_reason": d5_reason,
        "constraint_note": constraint_note,
        "strategic_value_score": company.get("strategic_value_score"),
    }


# ---------------------------------------------------------------------------
# Step 4: Write scores to Supabase (company_strategic_views)
# ---------------------------------------------------------------------------
