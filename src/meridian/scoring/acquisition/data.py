#!/usr/bin/env python3
"""Data fetch + index build (§3 acquisition_scorer split)."""

from collections import defaultdict

from meridian.scoring.acquisition.common import get


def fetch_all_data():
    print("[1/6] Fetching data from Supabase...")

    companies = get(
        "companies?select=id,name,status,company_type,market_cap,"
        "strategic_value_score,overlap,ta_focus_1,ta_focus_2,ailux_angle&limit=300"
    )
    print(f"  {len(companies)} companies")

    drugs = get(
        "drugs?select=id,name,company_id,stage,overlap,drug_format,modality,"
        "catalog_category,target,cls&limit=500"
    )
    print(f"  {len(drugs)} drugs")

    competitive_scores = get(
        "drug_competitive_scores?select=drug_id,context_id,competitive_relevance,"
        "total_competition_score&limit=1000"
    )
    print(f"  {len(competitive_scores)} drug_competitive_scores rows")

    catalysts = get(
        "catalyst_calendar?select=drug_id,company_id,event_type,expected_date,"
        "expected_quarter,confidence,is_past&limit=300"
    )
    print(f"  {len(catalysts)} catalyst_calendar rows")

    partnerships = get(
        "company_partnerships?select=company_id,lead_company_id,partner_company_id,"
        "deal_type,partnership_type,start_date&limit=500"
    )
    print(f"  {len(partnerships)} company_partnerships rows")

    deals = get(
        "deals?select=company_id,deal_date,deal_type,upfront_usd_m,"
        "total_usd_m,from_company,to_company&limit=500"
    )
    print(f"  {len(deals)} deals rows")

    strategic_views = get(
        "company_strategic_views?select=company_id,view_type,strategic_score,"
        "ailux_relevance&limit=300"
    )
    print(f"  {len(strategic_views)} company_strategic_views rows")

    return {
        "companies": companies,
        "drugs": drugs,
        "competitive_scores": competitive_scores,
        "catalysts": catalysts,
        "partnerships": partnerships,
        "deals": deals,
        "strategic_views": strategic_views,
    }


# ---------------------------------------------------------------------------
# Step 2: Build indexes
# ---------------------------------------------------------------------------


def build_indexes(data):
    print("[2/6] Building indexes...")

    companies = data["companies"]
    drugs = data["drugs"]
    competitive_scores = data["competitive_scores"]
    catalysts = data["catalysts"]
    partnerships = data["partnerships"]
    deals = data["deals"]

    # drug_id → company_id
    drug_to_company = {
        d["id"]: d["company_id"]
        for d in drugs
        if d.get("id") and d.get("company_id")
    }

    # company_id → list of drugs
    company_drugs = defaultdict(list)
    for d in drugs:
        cid = d.get("company_id")
        if cid:
            company_drugs[cid].append(d)

    # company_id → best competitive relevance from drug_competitive_scores
    # competitive_relevance: very_high, high, medium, low, none
    RELEVANCE_ORDER = {"very_high": 5, "high": 4, "medium": 3, "low": 2, "none": 1}
    company_comp_relevance = {}
    company_comp_scores = defaultdict(list)
    for row in competitive_scores:
        drug_id = row.get("drug_id")
        cid = drug_to_company.get(drug_id)
        if not cid:
            continue
        rel = row.get("competitive_relevance") or "none"
        score = row.get("total_competition_score") or 0
        company_comp_scores[cid].append(score)
        existing = company_comp_relevance.get(cid, "none")
        if RELEVANCE_ORDER.get(rel, 0) > RELEVANCE_ORDER.get(existing, 0):
            company_comp_relevance[cid] = rel

    # company_id → upcoming catalysts
    company_catalysts = defaultdict(list)
    for cat in catalysts:
        cid = cat.get("company_id")
        is_past = cat.get("is_past", False)
        if cid and not is_past:
            company_catalysts[cid].append(cat)

    # company_id → partnerships (to detect competitor partnerships)
    company_partnerships = defaultdict(list)
    for p in partnerships:
        cid = p.get("company_id")
        if cid:
            company_partnerships[cid].append(p)

    # company_id → deals (for BD acquirer track record)
    company_deals = defaultdict(list)
    for d in deals:
        cid = d.get("company_id")
        if cid:
            company_deals[cid].append(d)

    # Identify known BD acquirers (companies with acquisition deals in the DB)
    ACQUISITION_DEAL_TYPES = {"acquisition", "Acquisition", "license", "License",
                               "licensing", "option", "collab", "partnership"}
    bd_acquirers = set()
    for cid, dlist in company_deals.items():
        for deal in dlist:
            if deal.get("deal_type") in ACQUISITION_DEAL_TYPES:
                bd_acquirers.add(cid)

    print(f"  Identified {len(bd_acquirers)} companies with BD deal history")
    print(f"  Companies with upcoming catalysts: {len(company_catalysts)}")

    return {
        "drug_to_company": drug_to_company,
        "company_drugs": company_drugs,
        "company_comp_relevance": company_comp_relevance,
        "company_comp_scores": company_comp_scores,
        "company_catalysts": company_catalysts,
        "company_partnerships": company_partnerships,
        "company_deals": company_deals,
        "bd_acquirers": bd_acquirers,
    }


