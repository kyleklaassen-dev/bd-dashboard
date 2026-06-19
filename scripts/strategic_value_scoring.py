#!/usr/bin/env python3
"""
strategic_value_scoring.py — pure scoring layer for compute_strategic_value.py (§3 split).

Index builders + the strategic-value score computation, extracted verbatim.
All functions here are pure (data in → data out); no network, no module-level
write state. compute_strategic_value.py imports build_*_index + compute_score.
"""
from datetime import date


def build_drug_index(drugs):
    idx = {}
    for d in drugs:
        cid = d.get("company_id")
        if cid:
            idx.setdefault(cid, []).append(d)
    return idx


def build_dcs_index(dcs_rows, drugs):
    drug_to_company = {d["id"]: d["company_id"] for d in drugs
                       if d.get("id") and d.get("company_id")}
    idx = {}
    for row in dcs_rows:
        drug_id = row.get("drug_id")
        overlap = row.get("overlap")
        cid = drug_to_company.get(drug_id)
        if not cid or not overlap:
            continue
        bucket = idx.setdefault(cid, {"Direct": 0, "Adjacent": 0,
                                       "Same-Space": 0, "Watch": 0, "total": 0})
        if overlap in bucket:
            bucket[overlap] += 1
        bucket["total"] += 1
    return idx


def build_deal_index(deals):
    idx = {}
    for d in deals:
        cid = d.get("company_id")
        if cid:
            idx.setdefault(cid, []).append(d)
    return idx


# ---------------------------------------------------------------------------
# Step 3: Score computation
# ---------------------------------------------------------------------------

OVERLAP_TIER_POINTS = {"Direct": 30, "Adjacent": 15, "Same-Space": 5, "Watch": 2}

COMPANY_TYPE_BONUS = {
    "large_pharma": 20, "big_pharma": 20, "mid_cap": 15,
    "biotech": 12, "small_biotech": 8, "cro": 2, "academic": 2, "platform": 5,
}


def _parse_deal_value(row):
    for field in ("total_usd_m", "upfront_usd_m"):
        v = row.get(field)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return 0.0


def _days_since(date_str):
    if not date_str:
        return 9999
    try:
        d = date.fromisoformat(str(date_str)[:10])
        return (date.today() - d).days
    except Exception:
        return 9999


def compute_score(company, dcs_idx, deal_idx):
    cid = company["id"]
    score = 0
    rationale_parts = []

    # Pipeline relevance (0-40 pts)
    tier_data = dcs_idx.get(cid, {})
    company_overlap = company.get("overlap") or ""

    if tier_data.get("Direct", 0) > 0:
        base_tier_pts = 30
        rationale_parts.append(f"Direct overlap x{tier_data['Direct']}")
    elif tier_data.get("Adjacent", 0) > 0:
        base_tier_pts = 15
        rationale_parts.append(f"Adjacent overlap x{tier_data['Adjacent']}")
    elif tier_data.get("Same-Space", 0) > 0:
        base_tier_pts = 5
        rationale_parts.append(f"Same-Space x{tier_data['Same-Space']}")
    elif company_overlap == "Direct":
        base_tier_pts = 30
        rationale_parts.append("Direct (company-level)")
    elif company_overlap == "Adjacent":
        base_tier_pts = 15
        rationale_parts.append("Adjacent (company-level)")
    else:
        base_tier_pts = 0

    count_bonus = min(tier_data.get("total", 0) * 2, 10)
    score += min(base_tier_pts + count_bonus, 40)

    # Deal activity (0-20 pts)
    company_deals = deal_idx.get(cid, [])
    deal_pts = 0
    recent_deal = False
    max_value = 0.0
    for deal in company_deals:
        if _days_since(deal.get("deal_date")) <= 365:
            recent_deal = True
        v = _parse_deal_value(deal)
        if v > max_value:
            max_value = v
    if recent_deal:
        deal_pts += 10
        rationale_parts.append("Deal <12mo")
    if max_value >= 1000:
        deal_pts += 10
        rationale_parts.append(f"Deal >$1B (${max_value:.0f}M)")
    elif max_value >= 500:
        deal_pts += 5
        rationale_parts.append(f"Deal >$500M (${max_value:.0f}M)")
    score += min(deal_pts, 20)

    # Coverage completeness (0-20 pts)
    cov = company.get("coverage_status") or ""
    score += 20 if cov == "enriched" else (12 if cov == "active" else 5)

    # Strategic context (0-20 pts)
    ctype = company.get("company_type") or ""
    score += COMPANY_TYPE_BONUS.get(ctype, 8)

    score = min(int(score), 100)
    rationale = "; ".join(rationale_parts) if rationale_parts else "No direct overlap detected"
    return score, rationale
