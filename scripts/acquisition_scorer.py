#!/usr/bin/env python3
"""
acquisition_scorer.py
---------------------
Phase 3 Predictive Intelligence Layer for the Meridian BD Platform.

Computes an acquisition probability score (0-100) and BD priority rating
for every tracked company, answering: "Should Ailux be in active conversations
with this company RIGHT NOW?"

Five scoring dimensions (20 pts each):
  D1 Strategic Overlap   — how directly does their pipeline compete with Ailux?
  D2 BD Timing Urgency   — upcoming catalysts creating deal pressure
  D3 Platform Value      — engineering / modality capabilities Ailux could acquire
  D4 Deal Feasibility    — size + structure that makes a deal achievable
  D5 Ailux Window        — differentiation + constraint logic (AbbVie rule etc.)

BD Priority Ratings:
  85-100 → CALL NOW
  70-84  → PRIORITY
  55-69  → WATCH
  40-54  → MONITOR
  <40    → HOLD

Hard constraints:
  - AbbVie: capped at WATCH until ABBV-701 Phase 1 readout (Oct 2026)
  - Any company with status='acquired': forced to HOLD
  - Ailux itself: excluded from scoring

Run:
  python3 scripts/acquisition_scorer.py [--dry-run] [--top N]

Outputs:
  - Console: top 20 ranked companies with full dimension breakdown
  - Supabase: upserts to company_strategic_views (view_type='acquisition_target')
  - Local JSON: outputs/acquisition_probability_scores.json
  - GitHub: commits this script to kyleklaassen-dev/bd-dashboard
"""

import json
import os
import sys
import argparse
import base64
import urllib.request
import urllib.error
from datetime import datetime, date
from collections import defaultdict

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SUPA_URL = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS_DIR = os.path.join(WORKSPACE, "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

RUN_ID = f"aps_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
TODAY = date.today()
TODAY_STR = TODAY.isoformat()


def _read_key(filename):
    path = os.path.join(WORKSPACE, filename)
    with open(path) as f:
        return f.read().strip()


SUPA_KEY = _read_key(".supabase_service_key")
GITHUB_TOKEN = _read_key(".github_token")
REPO = "kyleklaassen-dev/bd-dashboard"

# ---------------------------------------------------------------------------
# Hard constraints (governance rules)
# ---------------------------------------------------------------------------

# AbbVie cannot be targeted for TL1A bispecific until after ABBV-701 Ph1 readout
ABBVIE_CONSTRAINT_UNTIL = date(2026, 10, 1)
ABBVIE_CONSTRAINT_NOTE = (
    "AbbVie cap: ABBV-701 (FutureGen-licensed TL1A mAb) Phase 1 readout expected "
    "Oct 2026. Cannot target AbbVie for TL1A bispecific BD until after readout. "
    "Governance rule: deal_sequencing / CLAUDE.md."
)

# Companies to exclude from scoring entirely
EXCLUDE_COMPANY_IDS = {"ailux"}

# Companies that should be forced to HOLD regardless of score
FORCE_HOLD_STATUSES = {"acquired"}

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _request(method, endpoint, data=None, extra_headers=None):
    url = f"{SUPA_URL}/{endpoint}"
    body = json.dumps(data).encode() if data is not None else None
    hdrs = {
        "apikey": SUPA_KEY,
        "Authorization": f"Bearer {SUPA_KEY}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        print(f"  HTTP {e.code} {method} /{endpoint.split('?')[0]}: {body_err[:200]}", file=sys.stderr)
        return None


def get(endpoint):
    return _request("GET", endpoint) or []


def post(endpoint, data, prefer=None):
    hdrs = {"Prefer": prefer} if prefer else {}
    return _request("POST", endpoint, data, hdrs)


def patch(endpoint, data):
    return _request("PATCH", endpoint, data)


def upsert(endpoint, data):
    hdrs = {"Prefer": "resolution=merge-duplicates,return=minimal"}
    return _request("POST", endpoint, data, hdrs)


# ---------------------------------------------------------------------------
# Step 1: Fetch data from Supabase
# ---------------------------------------------------------------------------


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


def _delete_acquisition_target_rows():
    """Delete all existing acquisition_target rows so we can insert fresh ones."""
    return _request(
        "DELETE",
        "company_strategic_views?view_type=eq.acquisition_target",
    )


def write_to_supabase(results, dry_run=False):
    print("[4/6] Writing scores to Supabase (company_strategic_views)...")

    if dry_run:
        print(f"  [DRY RUN] Would write {len([r for r in results if r])} rows")
        return 0

    # Delete existing acquisition_target rows, then insert fresh set
    _delete_acquisition_target_rows()
    print("  Cleared existing acquisition_target rows")

    rows_to_insert = []
    for r in results:
        if r is None:
            continue

        cid = r["company_id"]
        priority = r["bd_priority"]
        total = r["total_score"]

        # Build a clean summary string
        summary_parts = [
            f"D1 Overlap: {r['dim1_overlap']}/20 — {r['dim1_reason']}",
            f"D2 Timing: {r['dim2_timing']}/20 — {r['dim2_reason']}",
            f"D3 Platform: {r['dim3_platform']}/20 — {r['dim3_reason']}",
            f"D4 Feasibility: {r['dim4_feasibility']}/20 — {r['dim4_reason']}",
            f"D5 Window: {r['dim5_window']}/20 — {r['dim5_reason']}",
        ]
        if r.get("constraint_note"):
            summary_parts.append(f"CONSTRAINT: {r['constraint_note']}")

        summary = " | ".join(summary_parts)

        rows_to_insert.append({
            "company_id": cid,
            "view_type": "acquisition_target",
            "summary": summary[:2000],  # safety trim
            "strategic_score": total,
            "ailux_relevance": (
                f"BD Priority: {priority} (score {total}/100). "
                f"D1={r['dim1_overlap']} D2={r['dim2_timing']} "
                f"D3={r['dim3_platform']} D4={r['dim4_feasibility']} "
                f"D5={r['dim5_window']}"
            ),
            "enrichment_run_id": None,
            "confidence_source": "model",
            "updated_at": datetime.utcnow().isoformat(),
        })

    # Batch insert in chunks of 50
    written = 0
    chunk_size = 50
    for i in range(0, len(rows_to_insert), chunk_size):
        chunk = rows_to_insert[i:i + chunk_size]
        post("company_strategic_views", chunk, prefer="return=minimal")
        written += len(chunk)

    print(f"  Wrote {written} acquisition_target rows to company_strategic_views")
    return written


# ---------------------------------------------------------------------------
# Step 5: Write to local JSON
# ---------------------------------------------------------------------------


def write_json(results):
    output_path = os.path.join(OUTPUTS_DIR, "acquisition_probability_scores.json")
    clean = [r for r in results if r is not None]
    payload = {
        "run_id": RUN_ID,
        "generated_at": datetime.utcnow().isoformat(),
        "total_companies_scored": len(clean),
        "scoring_date": TODAY_STR,
        "scores": clean,
    }
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[5/6] JSON written: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Step 6: GitHub commit
# ---------------------------------------------------------------------------


def commit_to_github(dry_run=False):
    if dry_run:
        print("[6/6] [DRY RUN] Skipping GitHub commit")
        return

    print("[6/6] Committing to GitHub...")
    token = GITHUB_TOKEN
    api_url = f"https://api.github.com/repos/{REPO}/contents/scripts/acquisition_scorer.py"

    with open(os.path.abspath(__file__), "rb") as f:
        content = f.read()
    encoded = base64.b64encode(content).decode()

    # Get existing SHA
    sha = None
    req_get = urllib.request.Request(
        api_url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
    )
    try:
        with urllib.request.urlopen(req_get) as resp:
            sha = json.loads(resp.read()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"  GitHub GET warning: {e.code}", file=sys.stderr)

    payload = {
        "message": (
            f"feat: acquisition_scorer.py — Phase 3 BD probability scores "
            f"for 121 companies [{RUN_ID}]"
        ),
        "content": encoded,
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha

    req_put = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req_put) as resp:
            result = json.loads(resp.read())
            sha_short = result.get("commit", {}).get("sha", "")[:12]
            print(f"  GitHub: committed {sha_short}...")
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  GitHub commit failed: {e.code} — {err[:200]}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def print_report(results, top_n=20):
    clean = [r for r in results if r is not None]
    ranked = sorted(clean, key=lambda r: r["total_score"], reverse=True)

    call_now = [r for r in ranked if r["bd_priority"] == "CALL NOW"]
    priority = [r for r in ranked if r["bd_priority"] == "PRIORITY"]
    watch = [r for r in ranked if r["bd_priority"] == "WATCH"]
    monitor = [r for r in ranked if r["bd_priority"] == "MONITOR"]
    hold = [r for r in ranked if r["bd_priority"] == "HOLD"]

    W = 120
    print("\n" + "=" * W)
    print("MERIDIAN BD PLATFORM — ACQUISITION PROBABILITY SCORES")
    print(f"Phase 3 Predictive Intelligence Layer  |  Run: {RUN_ID}  |  Date: {TODAY_STR}")
    print("=" * W)

    print(f"\n{'RATING':<12} {'COMPANY':<32} {'TOTAL':<7} {'D1':<5} {'D2':<5} {'D3':<5} {'D4':<5} {'D5':<5}")
    print("-" * W)

    for i, r in enumerate(ranked[:top_n], 1):
        constraint = " [CONSTRAINED]" if r.get("constraint_note") else ""
        print(
            f"[{r['bd_priority']:<9}] "
            f"{r['company_name']:<32} "
            f"{r['total_score']:<7} "
            f"{r['dim1_overlap']:<5} "
            f"{r['dim2_timing']:<5} "
            f"{r['dim3_platform']:<5} "
            f"{r['dim4_feasibility']:<5} "
            f"{r['dim5_window']:<5}"
            f"{constraint}"
        )

    # CALL NOW detail section
    if call_now:
        print("\n" + "=" * W)
        print(f"CALL NOW COMPANIES ({len(call_now)} companies) — detailed reasoning")
        print("=" * W)
        for r in call_now:
            print(f"\n  {r['company_name'].upper()} (score: {r['total_score']}/100)")
            print(f"    D1 Overlap    [{r['dim1_overlap']:>2}/20]: {r['dim1_reason']}")
            print(f"    D2 Timing     [{r['dim2_timing']:>2}/20]: {r['dim2_reason']}")
            print(f"    D3 Platform   [{r['dim3_platform']:>2}/20]: {r['dim3_reason']}")
            print(f"    D4 Feasibility[{r['dim4_feasibility']:>2}/20]: {r['dim4_reason']}")
            print(f"    D5 Window     [{r['dim5_window']:>2}/20]: {r['dim5_reason']}")
            if r.get("constraint_note"):
                print(f"    CONSTRAINT: {r['constraint_note']}")
    else:
        print("\n  No companies reached CALL NOW threshold.")

    # PRIORITY detail section
    if priority:
        print("\n" + "=" * W)
        print(f"PRIORITY COMPANIES ({len(priority)} companies)")
        print("=" * W)
        for r in priority:
            print(f"  {r['company_name']:<32} score={r['total_score']}  "
                  f"D1={r['dim1_overlap']} D2={r['dim2_timing']} "
                  f"D3={r['dim3_platform']} D4={r['dim4_feasibility']} D5={r['dim5_window']}")

    # Constraints applied
    constrained = [r for r in clean if r.get("constraint_note")]
    if constrained:
        print("\n" + "=" * W)
        print(f"TIMING CONSTRAINTS APPLIED ({len(constrained)} companies)")
        print("=" * W)
        for r in constrained:
            print(f"  {r['company_name']}: {r['constraint_note'][:120]}")

    # Distribution
    print("\n" + "=" * W)
    print("BD PRIORITY DISTRIBUTION")
    print("=" * W)
    dist = [
        ("CALL NOW", call_now),
        ("PRIORITY", priority),
        ("WATCH", watch),
        ("MONITOR", monitor),
        ("HOLD", hold),
    ]
    for label, group in dist:
        bar = "#" * len(group)
        names = ", ".join(r["company_name"] for r in group[:5])
        if len(group) > 5:
            names += f", +{len(group)-5} more"
        print(f"  {label:<10} {bar:<30} ({len(group):>3}) — {names}")

    print(f"\nTotal scored: {len(clean)}  |  Excluded (Ailux): {len([r for r in results if r is None])}")
    print(f"Run ID: {RUN_ID}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Meridian Phase 3: Acquisition Probability Scorer"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute scores but do not write to Supabase or GitHub")
    parser.add_argument("--top", type=int, default=20,
                        help="How many companies to show in the report (default: 20)")
    args = parser.parse_args()

    data = fetch_all_data()
    idx = build_indexes(data)

    print("[3/6] Computing acquisition probability scores...")
    results = []
    for company in data["companies"]:
        result = score_company(company, idx)
        results.append(result)

    scored = [r for r in results if r is not None]
    print(f"  Scored {len(scored)} companies ({len(results)-len(scored)} excluded)")

    if not args.dry_run:
        write_to_supabase(results, dry_run=False)
    else:
        print("[4/6] [DRY RUN] Skipping Supabase write")

    write_json(results)

    if not args.dry_run:
        commit_to_github()
    else:
        print("[6/6] [DRY RUN] Skipping GitHub commit")

    print_report(results, top_n=args.top)


if __name__ == "__main__":
    main()
