#!/usr/bin/env python3
"""
seed_strategic_views.py
========================
GAP 2 FIX: company_strategic_views has 0 rows and no writer.

Seeds company_strategic_views with one row per company for each of their
primary TA areas. Uses:
  - company_areas for TA coverage
  - coverage_scores for enrichment quality signal
  - drugs + company_partnerships for pipeline depth
  - companies for strategic_importance

view_type logic (from schema check constraint):
  'competitive'          — company has a direct/adjacent competitor drug to Ailux
  'partnership'          — company has partnership history (licensing/co-dev)
  'acquisition_target'   — small biotech with clinical-stage asset, no large parent
  'licensing_candidate'  — preclinical/early-stage asset that Ailux could license in

Run:
  python scripts/seed_strategic_views.py
  python scripts/seed_strategic_views.py --dry-run
"""

import os, sys, json, requests, argparse, datetime

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _read(f):
    for base in [_REPO, os.path.dirname(os.path.abspath(__file__))]:
        p = os.path.join(base, f)
        if os.path.exists(p):
            return open(p).read().strip()
    return ""

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://tghntyofptvfhmtchwcv.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or _read(".supabase_service_key")

if not SUPABASE_KEY:
    print("ERROR: No SUPABASE_SERVICE_KEY"); sys.exit(1)

REST = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

def sb_get(table, params=None):
    r = requests.get(f"{REST}/{table}", headers=HEADERS, params=params or {}, timeout=20)
    if r.status_code == 200:
        return r.json()
    print(f"  GET {table}: {r.status_code} {r.text[:200]}")
    return []

def sb_insert(table, payload):
    h = {**HEADERS, "Prefer": "resolution=ignore-duplicates,return=minimal"}
    r = requests.post(f"{REST}/{table}", headers=h, json=payload, timeout=15)
    return r.status_code in (200, 201, 204)


# ─── Classify view_type ───────────────────────────────────────────────────────

# Companies known to be large pharma / strategic competitors
LARGE_PHARMA = {
    "abbvie", "roche", "lilly", "astrazeneca", "jnj", "janssen", "sanofi",
    "pfizer", "novartis", "merck", "amgen", "bms", "bristol", "gsk",
    "boehringer", "takeda", "regeneron", "biogen", "gilead", "ucb",
    "argenx", "teva",
}

# Companies with notable partnership history in these areas
PARTNERSHIP_HEAVY = {
    "futuregen", "simcere", "candid", "zymeworks", "merus", "lanova",
    "epimab", "vignette", "aprinoia", "xencor",
}

# Stage-to-view_type mapping for smaller biotechs
def infer_view_type(company_id: str, max_stage: str, has_partnership: bool) -> str:
    """
    Classify company into view_type for company_strategic_views.
    Follows schema constraint: competitive | partnership | acquisition_target | licensing_candidate
    """
    cid = company_id.lower()

    if cid in LARGE_PHARMA:
        return "competitive"

    if has_partnership or cid in PARTNERSHIP_HEAVY:
        return "partnership"

    stage_lower = (max_stage or "").lower()
    if any(s in stage_lower for s in ["phase 2", "phase 3", "approved", "bla", "nda"]):
        return "acquisition_target"

    # Preclinical or Phase 1 small biotechs
    return "licensing_candidate"


def main(dry_run: bool = False):
    NOW_ISO = datetime.datetime.utcnow().isoformat()

    print("Loading company_areas...")
    ca_rows = sb_get("company_areas", {"select": "company_id,area_id", "limit": "500"})
    from collections import defaultdict, Counter
    # company_id → Counter of area_ids
    company_areas_map = defaultdict(Counter)
    for r in ca_rows:
        company_areas_map[r["company_id"]][r["area_id"]] += 1

    print(f"  {len(company_areas_map)} companies with area coverage")

    # Load drugs per company for pipeline depth
    print("Loading drugs...")
    drugs = sb_get("drugs", {"select": "id,company_id,stage", "limit": "500"})
    company_drugs = defaultdict(list)
    for d in drugs:
        if d.get("company_id"):
            company_drugs[d["company_id"]].append(d)

    # Load partnerships per company (for has_partnership flag)
    print("Loading partnerships...")
    partnerships = sb_get("company_partnerships", {"select": "company_id,deal_type", "limit": "500"})
    company_has_partnership = set(p["company_id"] for p in partnerships)

    # Load companies basic info
    print("Loading companies...")
    companies = sb_get("companies", {
        "select": "id,name,strategic_importance,status",
        "status": "not.eq.acquired",
        "limit": "300",
    })
    company_info = {c["id"]: c for c in companies}

    print(f"  {len(company_info)} active companies\n")

    inserted = 0
    skipped = 0

    for company_id, areas_counter in sorted(company_areas_map.items()):
        cinfo = company_info.get(company_id, {})
        company_name = cinfo.get("name", company_id)
        strategic_importance = cinfo.get("strategic_importance", "")

        # Primary TA = most common area
        primary_ta = areas_counter.most_common(1)[0][0]
        all_areas = list(areas_counter.keys())
        pipeline_depth = len(company_drugs.get(company_id, []))

        # Best stage across all company drugs
        drug_stages = [d.get("stage", "") for d in company_drugs.get(company_id, [])]
        STAGE_ORDER = {
            "approved": 10, "approved_us": 10, "approved_eu": 10,
            "bla/nda": 9, "nda": 9, "bla": 9, "pre-bla": 8,
            "phase 3": 7, "phase 2/3": 6, "phase 2": 5, "phase 1/2": 4,
            "phase 1": 3, "ind-enabling": 2, "preclinical": 1,
        }
        max_stage = max(drug_stages, key=lambda s: STAGE_ORDER.get(s.lower(), 0), default="")

        has_partnership = company_id in company_has_partnership
        view_type = infer_view_type(company_id, max_stage, has_partnership)

        # Strategic score (rough: based on pipeline depth + stage)
        stage_score = STAGE_ORDER.get((max_stage or "").lower(), 0)
        strategic_score = min(100, pipeline_depth * 5 + stage_score * 7)

        # Key assets
        key_assets = [d["id"] for d in company_drugs.get(company_id, [])
                      if d.get("stage", "") and "terminated" not in d.get("stage", "").lower()][:5]

        summary = (
            f"{company_name} — primary TA: {primary_ta.upper()}, "
            f"pipeline depth: {pipeline_depth} drug(s), "
            f"best stage: {max_stage or 'unknown'}, "
            f"areas covered: {', '.join(all_areas)}."
        )
        if strategic_importance:
            summary += f" Strategic importance: {strategic_importance}."

        ailux_relevance = f"Covers {primary_ta.upper()} area — watch for {view_type.replace('_', ' ')} dynamics."

        rec = {
            "company_id":       company_id,
            "view_type":        view_type,
            "summary":          summary[:500],
            "key_assets":       key_assets,
            "ailux_relevance":  ailux_relevance[:300],
            "strategic_score":  strategic_score,
            "confidence_source": "model",
        }

        if dry_run:
            print(f"[DRY RUN] {company_id}: {view_type} | TA={primary_ta} | depth={pipeline_depth} | score={strategic_score}")
            skipped += 1
        else:
            ok = sb_insert("company_strategic_views", rec)
            status = "✓" if ok else "✗"
            print(f"{status} {company_id}: {view_type} | TA={primary_ta} | depth={pipeline_depth} | score={strategic_score}")
            if ok:
                inserted += 1
            else:
                skipped += 1

    action = "Would insert" if dry_run else "Inserted"
    print(f"\nDone: {action} {inserted + (skipped if dry_run else 0)}/{len(company_areas_map)} rows, {skipped} skipped/failed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print without writing")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
