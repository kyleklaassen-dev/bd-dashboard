#!/usr/bin/env python3
"""
compute_strategic_value.py
--------------------------
Computes strategic_value_score (0-100) for all tracked companies and
populates company_platform_views with inferred platform capabilities.

Scoring formula -- "how much should Kyle at Ailux care about this company?"
  Pipeline relevance  (0-40 pts): overlap tier x drug count
  Deal activity       (0-20 pts): recency + deal size
  Coverage score      (0-20 pts): approximated via coverage_status
  Strategic context   (0-20 pts): company_type + overlap tier

company_platform_views schema (actual):
  company_id, platform_type, platform_description,
  relevance_to_ailux, partnership_potential, confidence_source

Run:
  python3 scripts/compute_strategic_value.py [--dry-run]
"""

import json
import os
import sys
import argparse
from datetime import datetime, date
import urllib.request
import urllib.error
import base64

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SUPA_URL = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_key(filename):
    path = os.path.join(WORKSPACE, filename)
    with open(path) as f:
        return f.read().strip()


SUPA_KEY = _read_key(".supabase_service_key")
GITHUB_TOKEN = _read_key(".github_token")

RUN_ID = f"svs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
TODAY = date.today().isoformat()

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
            if raw.strip():
                return json.loads(raw)
            return []
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        print(f"  HTTP {e.code} {method} /{endpoint.split('?')[0]}: {body_err[:200]}", file=sys.stderr)
        return None


def get(endpoint):
    return _request("GET", endpoint)


def patch(endpoint, data):
    return _request("PATCH", endpoint, data)


def post(endpoint, data, prefer=None):
    hdrs = {"Prefer": prefer} if prefer else {}
    return _request("POST", endpoint, data, hdrs)


def delete(endpoint):
    return _request("DELETE", endpoint)


# ---------------------------------------------------------------------------
# Step 1: Fetch all data
# ---------------------------------------------------------------------------

def fetch_companies():
    rows = get("companies?select=id,name,status,overlap,company_type,coverage_status,"
               "hq_country,market_cap_display,r_and_d_spend,ta_focus_1,ta_focus_2"
               "&limit=300") or []
    print(f"  Fetched {len(rows)} companies")
    return rows


def fetch_drugs():
    rows = get("drugs?select=id,name,company_id,stage,cls,target,brand_name,modality&limit=500") or []
    print(f"  Fetched {len(rows)} drugs")
    return rows


def fetch_drug_competitive_scores():
    rows = get("drug_competitive_scores?select=drug_id,context_id,overlap,total_competition_score&limit=1000") or []
    print(f"  Fetched {len(rows)} drug_competitive_scores")
    return rows


def fetch_deals():
    rows = get("deals?select=id,company_id,deal_date,upfront_usd_m,total_usd_m,deal_type&limit=500") or []
    print(f"  Fetched {len(rows)} deals")
    return rows


def fetch_partnerships():
    rows = get("company_partnerships?select=company_id,partner_company_id,deal_type,partnership_verified&limit=500") or []
    print(f"  Fetched {len(rows)} partnerships")
    return rows


# ---------------------------------------------------------------------------
# Step 2: Index data
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Step 4: Update companies
# ---------------------------------------------------------------------------

def update_company_scores(companies, scores, dry_run=False):
    updated = 0
    for company in companies:
        cid = company["id"]
        score, rationale = scores.get(cid, (0, "not computed"))
        if dry_run:
            continue
        patch(
            f"companies?id=eq.{cid}",
            {
                "strategic_value_score": score,
                "strategic_value_rationale": rationale,
                "strategic_value_updated_at": datetime.utcnow().isoformat(),
                # strategic_value_run_id is UUID type — omit free-text run ID
            }
        )
        updated += 1
    if not dry_run:
        print(f"  Updated {updated} companies")
    return updated


# ---------------------------------------------------------------------------
# Step 5: Build company_platform_views
# ---------------------------------------------------------------------------

PLATFORM_CONFIG = {
    "bispecific": {
        "target_kw": ["x ", " x", "×", "bispecific"],
        "cls_kw": ["bispecific", "bsab"],
        "modality_kw": ["bispecific"],
        "desc": "{name} has bispecific antibody platform capability ({count} clinical/approved assets)",
        "relevance": "Direct format competitor to ALX001 (TL1A×IL-23p19) and ALX002 (CD19×BCMA)",
        "partnership": "high",
    },
    "FcRn_engineering": {
        "target_kw": ["fcrn", "neonatal fc"],
        "cls_kw": ["fcrn"],
        "modality_kw": ["fcrn", "half-life extended"],
        "desc": "{name} has FcRn-targeting or half-life engineering capability ({count} clinical/approved assets)",
        "relevance": "Direct mechanism competitor to ALX005 (FcRn×Albumin)",
        "partnership": "medium",
    },
    "ADC": {
        "target_kw": [],
        "cls_kw": ["adc", "antibody-drug conjugate"],
        "modality_kw": ["adc", "antibody-drug"],
        "desc": "{name} has antibody-drug conjugate (ADC) platform ({count} clinical/approved assets)",
        "relevance": "Tangential — ADC expertise relevant to next-gen bispecific linker/payload chemistry",
        "partnership": "low",
    },
    "TCE": {
        "target_kw": ["cd3", "t-cell engager"],
        "cls_kw": ["tce", "t-cell engager"],
        "modality_kw": ["t-cell engager", "bispecific t-cell"],
        "desc": "{name} has T-cell engager (TCE) platform ({count} clinical/approved assets)",
        "relevance": "Adjacent to ALX002 (CD19×BCMA) — TCE expertise relevant to bispecific I&I strategy",
        "partnership": "medium",
    },
    "mAb_platform": {
        "target_kw": [],
        "cls_kw": ["mab", "1st gen", "2nd gen"],
        "modality_kw": ["monoclonal antibody", "antibody"],
        "min_approved": 3,
        "desc": "{name} has established monoclonal antibody platform ({count} approved mAbs)",
        "relevance": "Adjacent — established mAb infrastructure positions for bispecific expansion",
        "partnership": "medium",
    },
    "small_molecule": {
        "target_kw": [],
        "cls_kw": ["smi", "small molecule"],
        "modality_kw": ["small molecule", "oral"],
        "desc": "{name} has small molecule platform ({count} clinical/approved assets)",
        "relevance": "Same-space — small molecule competitors in same indications; different modality",
        "partnership": "low",
    },
    "cell_therapy": {
        "target_kw": ["car-t", "car t"],
        "cls_kw": ["car-t", "cell therapy"],
        "modality_kw": ["car-t", "cell therapy"],
        "desc": "{name} has cell therapy platform ({count} clinical/approved assets)",
        "relevance": "Adjacent to ALX002 (CD19×BCMA) — cell therapy targets same antigens, different modality",
        "partnership": "medium",
    },
}


def _drug_matches(drug, config):
    t = (drug.get("target") or "").lower()
    c = (drug.get("cls") or "").lower()
    m = (drug.get("modality") or "").lower()
    for kw in config.get("target_kw", []):
        if kw.lower() in t:
            return True
    for kw in config.get("cls_kw", []):
        if kw.lower() in c:
            return True
    for kw in config.get("modality_kw", []):
        if kw.lower() in m:
            return True
    return False


APPROVED_STAGES = {"approved", "approved_us", "approved_eu", "approved_us_eu",
                   "approved_partial", "approved_china"}


def build_platform_views(companies, drug_idx, scores, dry_run=False):
    if not dry_run:
        result = delete("company_platform_views?id=gt.0")
        print("  Cleared existing company_platform_views rows")

    rows_created = 0
    cap_counts = {k: 0 for k in PLATFORM_CONFIG}

    high_relevance = [(c, scores.get(c["id"], (0, ""))[0])
                      for c in companies
                      if scores.get(c["id"], (0, ""))[0] > 40]
    high_relevance.sort(key=lambda x: x[1], reverse=True)
    print(f"  Building platform views for {len(high_relevance)} companies (score > 40)")

    for company, svs in high_relevance:
        cid = company["id"]
        cname = company["name"]
        company_drugs = drug_idx.get(cid, [])

        for pkey, config in PLATFORM_CONFIG.items():
            matching = [d for d in company_drugs if _drug_matches(d, config)]

            if pkey == "mAb_platform":
                approved = [d for d in matching
                            if (d.get("stage") or "").lower() in APPROVED_STAGES]
                if len(approved) < config.get("min_approved", 3):
                    continue
                count = len(approved)
            else:
                count = len(matching)
                if count == 0:
                    continue

            row = {
                "company_id": cid,
                "platform_type": pkey,
                "platform_description": config["desc"].format(name=cname, count=count),
                "relevance_to_ailux": config["relevance"],
                "partnership_potential": config["partnership"],
                "confidence_source": "model",
            }

            if dry_run:
                print(f"  [DRY] {cname:<30} | {pkey:<20} | {count} drugs")
            else:
                post("company_platform_views", row, prefer="return=minimal")
            rows_created += 1
            cap_counts[pkey] += 1

    print(f"  Created {rows_created} platform view rows")
    return rows_created, cap_counts


# ---------------------------------------------------------------------------
# Step 6: GitHub commit
# ---------------------------------------------------------------------------

def commit_to_github(dry_run=False):
    if dry_run:
        print("  [DRY] Skipping GitHub commit")
        return

    token = GITHUB_TOKEN
    repo = "kyleklaassen-dev/bd-dashboard"
    path = "scripts/compute_strategic_value.py"
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"

    with open(os.path.abspath(__file__), "rb") as f:
        content = f.read()
    encoded = base64.b64encode(content).decode()

    # Get existing SHA
    sha = None
    req_get = urllib.request.Request(
        api_url,
        headers={"Authorization": f"token {token}",
                 "Accept": "application/vnd.github.v3+json"}
    )
    try:
        with urllib.request.urlopen(req_get) as resp:
            sha = json.loads(resp.read()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"  GitHub GET warning: {e.code}", file=sys.stderr)

    payload = {
        "message": f"feat: compute_strategic_value.py — SVS scores for 121 companies [{RUN_ID}]",
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
        method="PUT"
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

def print_report(companies, scores, cap_counts):
    ranked = sorted(companies,
                    key=lambda c: scores.get(c["id"], (0, ""))[0], reverse=True)

    print("\n" + "=" * 72)
    print("TOP 20 COMPANIES BY STRATEGIC VALUE SCORE")
    print("=" * 72)
    print(f"{'Rank':<5} {'Name':<36} {'SVS':<6} {'Overlap':<12} {'Type'}")
    print("-" * 72)
    for i, c in enumerate(ranked[:20], 1):
        svs = scores.get(c["id"], (0, ""))[0]
        print(f"{i:<5} {c['name']:<36} {svs:<6} {(c.get('overlap') or 'N/A'):<12} {c.get('company_type') or ''}")

    print("\n" + "=" * 72)
    print("BOTTOM 20 COMPANIES BY STRATEGIC VALUE SCORE")
    print("=" * 72)
    print(f"{'Rank':<5} {'Name':<36} {'SVS':<6} {'Overlap':<12} {'Type'}")
    print("-" * 72)
    for i, c in enumerate(ranked[-20:], len(ranked) - 19):
        svs = scores.get(c["id"], (0, ""))[0]
        print(f"{i:<5} {c['name']:<36} {svs:<6} {(c.get('overlap') or 'N/A'):<12} {c.get('company_type') or ''}")

    print("\n" + "=" * 72)
    print("PLATFORM CAPABILITY COVERAGE")
    print("=" * 72)
    for cap, cnt in sorted(cap_counts.items(), key=lambda x: x[1], reverse=True):
        if cnt > 0:
            bar = "#" * cnt
            print(f"  {cap:<25} {bar} ({cnt})")

    print("\n" + "=" * 72)
    print("SCORE DISTRIBUTION")
    print("=" * 72)
    all_scores = [scores.get(c["id"], (0, ""))[0] for c in companies]
    for label, lo, hi in [("80-100", 80, 101), ("60-79", 60, 80),
                           ("40-59", 40, 60), ("20-39", 20, 40), ("0-19", 0, 20)]:
        cnt = sum(1 for s in all_scores if lo <= s < hi)
        bar = "#" * cnt
        print(f"  {label:<10} {bar} ({cnt})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    dry_run = args.dry_run

    print(f"compute_strategic_value.py  |  Run: {RUN_ID}")
    if dry_run:
        print("=== DRY RUN — no DB writes ===")

    print("\n[1/6] Fetching data...")
    companies = fetch_companies()
    drugs = fetch_drugs()
    dcs_rows = fetch_drug_competitive_scores()
    deals = fetch_deals()
    fetch_partnerships()

    print("\n[2/6] Building indexes...")
    drug_idx = build_drug_index(drugs)
    dcs_idx = build_dcs_index(dcs_rows, drugs)
    deal_idx = build_deal_index(deals)

    print("\n[3/6] Computing scores...")
    scores = {}
    for company in companies:
        scores[company["id"]] = compute_score(company, dcs_idx, deal_idx)
    print(f"  Scored {len(scores)} companies")

    print("\n[4/6] Updating companies.strategic_value_score...")
    update_company_scores(companies, scores, dry_run=dry_run)

    print("\n[5/6] Building company_platform_views...")
    rows_created, cap_counts = build_platform_views(companies, drug_idx, scores, dry_run=dry_run)

    print("\n[6/6] Committing script to GitHub...")
    commit_to_github(dry_run=dry_run)

    print_report(companies, scores, cap_counts)
    print(f"\nComplete. Run ID: {RUN_ID}")


if __name__ == "__main__":
    main()
