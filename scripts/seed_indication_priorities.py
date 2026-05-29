#!/usr/bin/env python3
"""
seed_indication_priorities.py
Creates and seeds the indication_priority_scores table in Supabase.

Scoring model:
  ailux_fit_score (1-10):
    10 = direct Ailux program (UC, CD, gMG, CIDP)
    7-9 = strong mechanistic fit (TL1A area, FcRn area, IBD)
    4-6 = adjacent (IL-23, Atopy/IL-4Ra, TSLP, Graves, TED, RA)
    1-3 = exploratory/watch

  competitive_white_space (1-10):
    10 = no approved bispecific, only monospecifics in Phase 1
    7-9 = some Phase 2 bispecifics, no Phase 3 readout <12 months
    4-6 = Phase 3 bispecifics underway
    1-3 = bispecific already approved or imminent

  indication_priority_rank: composite score rank
    formula = (unmet_need_score * 0.3) + (ailux_fit_score * 0.3)
              + (competitive_white_space * 0.2)
              + (biologic_failure_rate_pct / 10 * 0.2)

Run: python3 scripts/seed_indication_priorities.py
"""

import os
import json
import requests
import sys

BASE_URL = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"

def get_key():
    key_path = os.path.join(os.path.dirname(__file__), '..', '.supabase_service_key')
    with open(key_path) as f:
        return f.read().strip()

SERVICE_KEY = get_key()

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# ── Indication data ───────────────────────────────────────────────────────────
# Source: indication_patient_intelligence table + clinical knowledge
# All numeric scoring fields are author-assigned with rationale below.

INDICATIONS = [
    # ── Core Ailux Direct Indications ──
    {
        "indication_id": "uc",
        "indication_name": "Ulcerative Colitis",
        "patient_count_us": 900000,
        "market_size_usd_bn": 8.0,
        "unmet_need_score": 8,
        "biologic_failure_rate_pct": 40.0,
        "remission_rate_soc_pct": 25.0,
        "ailux_fit_score": 10,
        "competitive_white_space": 7,
        # Rationale: No bispecific approved in UC. Spyre SPY002 in Phase 2,
        # AbbVie ABBV-201 (TL1A+IL-23) now in development. White space
        # narrowing but no Phase 3 readout within 12 months for bispecifics.
        "priority_rationale": "Direct ALX001 target. 40% biologic failure rate with only 25% SoC remission — among the worst in I&I. No approved bispecific; Spyre/Sanofi SPY002 in Phase 2 is closest competitor. Deep remission gap is Ailux's clinical window.",
        "alx_programs": ["alx001"],
    },
    {
        "indication_id": "cd",
        "indication_name": "Crohn's Disease",
        "patient_count_us": 780000,
        "market_size_usd_bn": 7.0,
        "unmet_need_score": 9,
        "biologic_failure_rate_pct": 45.0,
        "remission_rate_soc_pct": 20.0,
        "ailux_fit_score": 10,
        "competitive_white_space": 7,
        # Rationale: No bispecific approved in CD. Higher failure + lower
        # remission than UC = more urgent. Bispecific white space = 7 because
        # pipeline is more active than UC (Spyre, Prometheus data available).
        "priority_rationale": "Direct ALX001 target. Worst remission rate of any indication tracked (20% SoC). 45% biologic failure = large inadequate responder pool. Fibrotic CD has essentially no good option. TL1A×IL-23 combo is mechanistically ideal for the fibroinflammatory phenotype.",
        "alx_programs": ["alx001"],
    },
    {
        "indication_id": "gmg",
        "indication_name": "Generalized Myasthenia Gravis",
        "patient_count_us": 90000,
        "market_size_usd_bn": 3.0,
        "unmet_need_score": 8,
        "biologic_failure_rate_pct": 30.0,
        "remission_rate_soc_pct": 50.0,
        "ailux_fit_score": 10,
        "competitive_white_space": 8,
        # Rationale: FcRn blockers (rozanolixizumab, efgartigimod) approved,
        # but no bispecific combining FcRn + another target is approved. FcRn
        # monospecifics are SoC — bispecific white space remains open.
        "priority_rationale": "Direct ALX005 target (FcRn×Albumin). FcRn monospecifics now approved (rozanolixizumab, efgartigimod) but bispecific combining extended half-life with second mechanism has open white space. AChR+ and MuSK+ subgroups have different needs = Ailux differentiation opportunity.",
        "alx_programs": ["alx005"],
    },
    {
        "indication_id": "cidp",
        "indication_name": "CIDP",
        "patient_count_us": 40000,
        "market_size_usd_bn": 1.5,
        "unmet_need_score": 8,
        "biologic_failure_rate_pct": 35.0,
        "remission_rate_soc_pct": 60.0,
        "ailux_fit_score": 10,
        "competitive_white_space": 9,
        # Rationale: efgartigimod alfa approved 2023, but only FcRn mono.
        # No bispecific in the space. Less competitive than gMG. Small patient
        # pool limits commercial ceiling but white space is high.
        "priority_rationale": "Direct ALX005 target. Efgartigimod approved but bispecific white space is essentially unchallenged. Smaller patient population ($1.5B market) is a ceiling constraint, but high fit + high white space justifies top-5 priority. Maintenance convenience is a key clinical differentiator.",
        "alx_programs": ["alx005"],
    },
    # ── ALX002 Targets ──
    {
        "indication_id": "sle",
        "indication_name": "Systemic Lupus Erythematosus",
        "patient_count_us": 200000,
        "market_size_usd_bn": 4.0,
        "unmet_need_score": 9,
        "biologic_failure_rate_pct": 50.0,
        "remission_rate_soc_pct": 15.0,
        "ailux_fit_score": 9,
        "competitive_white_space": 8,
        # Rationale: CD19×BCMA bispecific directly addresses plasma cell/B cell
        # pathology in SLE. No bispecific approved in SLE. Very high unmet need
        # (15% remission SoC). Several CD19×BCMA programs in early trials.
        "priority_rationale": "Direct ALX002 target (CD19×BCMA). SLE has among the worst SoC remission rates tracked. The B-cell + plasma cell dual depletion strategy is mechanistically compelling and differentiated from belimumab (BLyS only) or anifrolumab (IFN). No approved bispecific in class — high white space.",
        "alx_programs": ["alx002"],
    },
    {
        "indication_id": "sjogrens",
        "indication_name": "Sjogren's Syndrome",
        "patient_count_us": 400000,
        "market_size_usd_bn": 2.0,
        "unmet_need_score": 9,
        "biologic_failure_rate_pct": 60.0,
        "remission_rate_soc_pct": 10.0,
        "ailux_fit_score": 9,
        "competitive_white_space": 9,
        # Rationale: No approved biologic for Sjogren's systemic disease.
        # CD19×BCMA could address glandular B cell/plasma cell infiltration.
        # Nearly unchallenged white space — iscalimab in Phase 3 but different
        # mechanism.
        "priority_rationale": "Direct ALX002 target. Nearly no approved pharmacotherapy for systemic Sjogren's — highest white space of any indication tracked. B cell/plasma cell pathology is core disease driver = strong CD19×BCMA mechanistic fit. Small but severely underserved patient population.",
        "alx_programs": ["alx002"],
    },
    # ── TL1A Mechanism Area ──
    {
        "indication_id": "tl1a",
        "indication_name": "TL1A Mechanism Area",
        "patient_count_us": 2500000,
        "market_size_usd_bn": 15.0,
        "unmet_need_score": 9,
        "biologic_failure_rate_pct": 42.0,
        "remission_rate_soc_pct": 18.0,
        "ailux_fit_score": 10,
        "competitive_white_space": 7,
        # Rationale: TL1A monospecifics (tulisokibart, etc.) are advancing to
        # Ph3. Bispecific white space is high but narrowing. This is the
        # broadest competitive monitoring view — includes UC/CD and fibrosis.
        "priority_rationale": "Broadest view of ALX001 competitive landscape. TL1A space is rapidly maturing — monospecifics entering Phase 3, but TL1A bispecifics (pairing with IL-23) are only entering Ph1/2. Competitive window for differentiation is 2025-2027 before monospecifics own the positioning.",
        "alx_programs": ["alx001"],
    },
    # ── FcRn Mechanism Area ──
    {
        "indication_id": "fcrn",
        "indication_name": "FcRn Target Area",
        "patient_count_us": 800000,
        "market_size_usd_bn": 6.0,
        "unmet_need_score": 8,
        "biologic_failure_rate_pct": 35.0,
        "remission_rate_soc_pct": 40.0,
        "ailux_fit_score": 9,
        "competitive_white_space": 7,
        # Rationale: FcRn monospecifics approved (rozanolixizumab, efgartigimod,
        # nipocalimab). Bispecific with FcRn + second arm is next frontier.
        # Immunovant veligrotug, Argenx pipeline expanding scope.
        "priority_rationale": "ALX005 mechanism monitoring view. FcRn monospecific era is now established — approved drugs exist. Competitive window for bispecific is the next gen. Bispecific + extended half-life profile could redefine dosing standards across gMG, CIDP, pemphigus, ITP.",
        "alx_programs": ["alx005"],
    },
    # ── Adjacent but Moderate Fit ──
    {
        "indication_id": "ibd",
        "indication_name": "IBD (Inflammatory Bowel Disease)",
        "patient_count_us": 1680000,
        "market_size_usd_bn": 15.0,
        "unmet_need_score": 8,
        "biologic_failure_rate_pct": 42.0,
        "remission_rate_soc_pct": 22.0,
        "ailux_fit_score": 9,
        "competitive_white_space": 6,
        # Rationale: IBD = UC+CD combined view. Fit is high (ALX001 directly).
        # White space = 6 because the combined view includes both indications
        # and the competitive crowd in IBD is significant (vedolizumab, upadacitinib,
        # risankizumab, mirikizumab all approved). Bispecific white space remains
        # open, but the approved drug density lowers the score.
        "priority_rationale": "Combined UC+CD view for ALX001. More competitive than individual indication views because of the breadth of approved drugs in IBD overall. Bispecific white space is real but the crowding in the monospecific space sets a high differentiation bar.",
        "alx_programs": ["alx001"],
    },
    {
        "indication_id": "il23",
        "indication_name": "IL-23 / IL-23p19 Target Area",
        "patient_count_us": 3000000,
        "market_size_usd_bn": 20.0,
        "unmet_need_score": 7,
        "biologic_failure_rate_pct": 38.0,
        "remission_rate_soc_pct": 30.0,
        "ailux_fit_score": 8,
        "competitive_white_space": 5,
        # Rationale: IL-23p19 monospecifics fully approved (risankizumab,
        # mirikizumab, guselkumab). Bispecific pairing IL-23 with TL1A is the
        # ALX001 thesis. White space = 5 because IL-23p19 monos are so
        # well-established that the bispecific must prove additive value.
        "priority_rationale": "Second arm of ALX001. IL-23p19 monotherapy is already standard of care in UC/CD/psoriasis — bispecific must prove additive benefit over adding drugs sequentially. The differentiation story is convenience + synergy, not mechanism novelty alone.",
        "alx_programs": ["alx001"],
    },
    {
        "indication_id": "ted",
        "indication_name": "Thyroid Eye Disease",
        "patient_count_us": 50000,
        "market_size_usd_bn": 2.0,
        "unmet_need_score": 9,
        "biologic_failure_rate_pct": 35.0,
        "remission_rate_soc_pct": 45.0,
        "ailux_fit_score": 4,
        "competitive_white_space": 6,
        # Rationale: IGF-1R×TSHR bispecific is the next-gen play in TED.
        # Not a direct Ailux program but worth monitoring. Tepezza approved
        # but relapse rate problem creates opening. Ailux fit = low (4) —
        # IGF-1R is not in Ailux portfolio, but competitive monitoring value
        # is high.
        "priority_rationale": "Competitive monitoring area — not direct Ailux. IGF-1R×TSHR bispecific approach is being pioneered here (veligrotug, lonigutamab). Tepezza relapse problem + SC route preference = clinical gap. Relevant to understand bispecific differentiation playbook even outside Ailux mechanisms.",
        "alx_programs": [],
    },
    {
        "indication_id": "atopy",
        "indication_name": "Atopic Dermatitis",
        "patient_count_us": 18000000,
        "market_size_usd_bn": 12.0,
        "unmet_need_score": 7,
        "biologic_failure_rate_pct": 25.0,
        "remission_rate_soc_pct": 30.0,
        "ailux_fit_score": 3,
        "competitive_white_space": 3,
        # Rationale: Dupilumab, lebrikizumab, tralokinumab all approved.
        # Space is very crowded with effective biologics. Not Ailux mechanism.
        # Low fit, low white space.
        "priority_rationale": "Watch area. Dupilumab dominates with strong efficacy. IL-4Ra/TSLP/IL-13 monospecifics all approved or late-stage. Bispecific white space nearly closed by competitive density. Low Ailux relevance — useful for understanding IL-4Ra/TSLP positioning benchmarks.",
        "alx_programs": [],
    },
    {
        "indication_id": "mg",
        "indication_name": "Myasthenia Gravis (Broad)",
        "patient_count_us": 36000,
        "market_size_usd_bn": 2.5,
        "unmet_need_score": 8,
        "biologic_failure_rate_pct": 30.0,
        "remission_rate_soc_pct": 50.0,
        "ailux_fit_score": 8,
        "competitive_white_space": 8,
        # Similar to gMG but broader view including ocular/thymoma subtypes.
        "priority_rationale": "Broad MG view overlapping with direct ALX005 target (gMG). Relevant for FcRn competitive monitoring. eculizumab, rituximab, efgartigimod all active. Bispecific opportunity mirrors gMG analysis.",
        "alx_programs": ["alx005"],
    },
    {
        "indication_id": "graves",
        "indication_name": "Graves' Disease",
        "patient_count_us": 150000,
        "market_size_usd_bn": 1.0,
        "unmet_need_score": 7,
        "biologic_failure_rate_pct": 30.0,
        "remission_rate_soc_pct": 55.0,
        "ailux_fit_score": 3,
        "competitive_white_space": 8,
        # Adjacent to TED. Not direct Ailux.
        "priority_rationale": "Adjacent to TED — same IGF-1R/TSHR biology. Iscalimab (anti-CD40L) in Phase 3. No approved biologic for Graves hyperthyroidism itself. High white space but low Ailux fit. Monitor as part of IGF-1R competitive landscape.",
        "alx_programs": [],
    },
    {
        "indication_id": "ra",
        "indication_name": "Rheumatoid Arthritis",
        "patient_count_us": 1500000,
        "market_size_usd_bn": 22.0,
        "unmet_need_score": 6,
        "biologic_failure_rate_pct": 35.0,
        "remission_rate_soc_pct": 30.0,
        "ailux_fit_score": 3,
        "competitive_white_space": 2,
        # RA has TNF, IL-6, JAK, CD80/86, CD20 all approved.
        # Bispecifics starting to enter but enormous competition.
        "priority_rationale": "Low-priority watch area. RA market is enormous ($22B) but mechanistically saturated — TNFi, JAKi, IL-6i, abatacept all approved + generic/biosimilar pressure. No Ailux mechanism directly relevant. Bispecific white space closing (faricimab-class approach not yet applied in RA).",
        "alx_programs": [],
    },
    {
        "indication_id": "autoimmune_broad",
        "indication_name": "Autoimmune Diseases (Broad)",
        "patient_count_us": 25000000,
        "market_size_usd_bn": 30.0,
        "unmet_need_score": 7,
        "biologic_failure_rate_pct": 35.0,
        "remission_rate_soc_pct": 25.0,
        "ailux_fit_score": 5,
        "competitive_white_space": 4,
        "priority_rationale": "Broad strategic view — useful for partner positioning analysis across ALX001/ALX002/ALX005 mechanisms. Too wide for actionable competitive scoring but relevant for tracking company portfolios that span multiple autoimmune indications.",
        "alx_programs": ["alx001", "alx002", "alx005"],
    },
    {
        "indication_id": "respiratory_broad",
        "indication_name": "Respiratory Diseases (Broad)",
        "patient_count_us": 40000000,
        "market_size_usd_bn": 15.0,
        "unmet_need_score": 7,
        "biologic_failure_rate_pct": 30.0,
        "remission_rate_soc_pct": 25.0,
        "ailux_fit_score": 2,
        "competitive_white_space": 4,
        "priority_rationale": "Low Ailux relevance. TSLP/IL-4Ra/IL-5 biologics dominating respiratory (tezepelumab, dupilumab, mepolizumab). Useful for TSLP competitive monitoring but not directly relevant to ALX001/002/005 programs.",
        "alx_programs": [],
    },
]


def compute_composite_score(ind):
    """Composite priority formula as specified in the task."""
    unmet = ind["unmet_need_score"]
    fit = ind["ailux_fit_score"]
    wspace = ind["competitive_white_space"]
    bfr = ind["biologic_failure_rate_pct"]
    return (unmet * 0.3) + (fit * 0.3) + (wspace * 0.2) + (bfr / 10 * 0.2)


def rank_indications(indications):
    """Sort by composite score descending, assign rank."""
    scored = [(ind, compute_composite_score(ind)) for ind in indications]
    scored.sort(key=lambda x: x[1], reverse=True)
    ranked = []
    for rank, (ind, score) in enumerate(scored, start=1):
        ind_copy = dict(ind)
        ind_copy["indication_priority_rank"] = rank
        ind_copy["_composite_score"] = round(score, 3)
        ranked.append(ind_copy)
    return ranked


def create_table(service_key):
    """Attempt to create table via Supabase SQL API (requires service key)."""
    sql = """
    CREATE TABLE IF NOT EXISTS indication_priority_scores (
        indication_id TEXT PRIMARY KEY,
        indication_name TEXT NOT NULL,
        patient_count_us INTEGER,
        market_size_usd_bn NUMERIC,
        unmet_need_score INTEGER CHECK (unmet_need_score BETWEEN 1 AND 10),
        biologic_failure_rate_pct NUMERIC,
        remission_rate_soc_pct NUMERIC,
        ailux_fit_score INTEGER CHECK (ailux_fit_score BETWEEN 1 AND 10),
        competitive_white_space INTEGER CHECK (competitive_white_space BETWEEN 1 AND 10),
        indication_priority_rank INTEGER,
        priority_rationale TEXT,
        alx_programs TEXT[],
        last_computed TIMESTAMPTZ DEFAULT NOW()
    );
    """
    resp = requests.post(
        "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1/rpc/exec_sql",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        },
        json={"query": sql},
        timeout=15,
    )
    return resp.status_code, resp.text


def upsert_rows(ranked, service_key):
    """Upsert all rows into indication_priority_scores."""
    rows = []
    for ind in ranked:
        row = {k: v for k, v in ind.items() if not k.startswith("_")}
        row["last_computed"] = "now()"
        rows.append(row)

    resp = requests.post(
        f"{BASE_URL}/indication_priority_scores",
        headers={
            **HEADERS,
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
        json=rows,
        timeout=20,
    )
    return resp.status_code, resp.text


def write_json_fallback(ranked):
    """Write scores to a JSON file for manual inspection."""
    out_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'indication_priority_scores.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(ranked, f, indent=2)
    print(f"[fallback] Written to {out_path}")
    return out_path


def print_ranking(ranked):
    print("\n=== INDICATION PRIORITY RANKINGS ===")
    print(f"{'Rank':<5} {'Score':<7} {'Indication':<40} {'Fit':<5} {'WSpace':<8} {'Unmet':<7} {'BFR%':<7} Programs")
    print("-" * 100)
    for ind in ranked:
        progs = ",".join(ind.get("alx_programs", [])) or "—"
        print(
            f"{ind['indication_priority_rank']:<5} "
            f"{ind['_composite_score']:<7} "
            f"{ind['indication_name']:<40} "
            f"{ind['ailux_fit_score']:<5} "
            f"{ind['competitive_white_space']:<8} "
            f"{ind['unmet_need_score']:<7} "
            f"{ind['biologic_failure_rate_pct']:<7} "
            f"{progs}"
        )


def main():
    service_key = get_key()
    ranked = rank_indications(INDICATIONS)
    print_ranking(ranked)

    # Try to create table (may fail if DDL blocked)
    print("\n[table] Attempting to create indication_priority_scores table...")
    status, body = create_table(service_key)
    print(f"  create attempt: HTTP {status} — {body[:120]}")

    # Try upsert
    print("[upsert] Upserting rows...")
    u_status, u_body = upsert_rows(ranked, service_key)
    print(f"  upsert: HTTP {u_status}")
    if u_status not in (200, 201):
        print(f"  error body: {u_body[:300]}")
        print("[fallback] Writing to JSON instead...")
        out = write_json_fallback(ranked)
        print(f"  JSON written: {out}")
    else:
        print(f"  success — {len(ranked)} rows upserted")


if __name__ == "__main__":
    main()
