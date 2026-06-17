#!/usr/bin/env python3
"""
BD Recommendations Engine — Meridian / Ailux Biotherapeutics
=============================================================
Scores all tracked companies on 5 BD-relevant dimensions, calls Claude
Haiku to generate deal framing for each top company, and writes a ranked
call list to the bd_recommendations table.

USAGE:
  python scripts/bd_recommender.py           # full run, writes top 20
  python scripts/bd_recommender.py --dry-run # score + frame but skip DB write
  python scripts/bd_recommender.py --top 5   # print top N in full detail

SCORING (0–100 total):
  Strategic Value  (30) — companies.strategic_value_score normalised to 0-30
  Pipeline Urgency (25) — competitor catalyst within 12 months: +8/readout, +5/completed Ph2
  Deal Appetite    (20) — recent deals (18 mo): +5/deal, +10 if upfront >$500M
  Partnership Fit  (15) — company_strategic_views.view_type mapping
  Coverage Gap     (10) — 10 × (1 − coverage_score/100)

GOVERNANCE CONSTRAINTS (applied at ranking time):
  - AbbVie blocked from TL1A bispecific until after ABBV-701 Ph1 readout (Oct 2026)
    → downgraded to call_urgency='watch', note appended to deal_framing
"""

import os
import sys
import json
import time
import datetime
import argparse
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Any

# ── Paths ─────────────────────────────────────────────────────────────────────
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT    = os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPTS_DIR)))


# ── Credentials ───────────────────────────────────────────────────────────────
def _cred(env_var: str, filename: str) -> str:
    val = os.environ.get(env_var, "")
    if val:
        return val.strip()
    for base in [_REPO_ROOT, _SCRIPTS_DIR]:
        path = os.path.join(base, filename)
        if os.path.exists(path):
            return open(path).read().strip()
    return ""


SUPABASE_URL      = _cred("SUPABASE_URL", ".supabase_url") or "https://tghntyofptvfhmtchwcv.supabase.co"
SUPABASE_KEY      = _cred("SUPABASE_SERVICE_KEY", ".supabase_service_key")
ANON_KEY          = _cred("SUPABASE_ANON_KEY", ".supabase_anon_key")
SUPABASE_PAT      = _cred("SUPABASE_PAT", ".supabase_pat")
ANTHROPIC_API_KEY = _cred("ANTHROPIC_API_KEY", ".anthropic_api_key")

PROJECT_REF = "tghntyofptvfhmtchwcv"
MGMT_URL    = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

_READ_KEY  = SUPABASE_KEY or ANON_KEY
_WRITE_KEY = SUPABASE_KEY or ANON_KEY

TODAY = datetime.date.today().isoformat()
NOW   = datetime.datetime.utcnow().isoformat()

AILUX_CONTEXT = (
    "Ailux Biotherapeutics is developing ALX001 (TL1A×IL-23p19 bispecific for IBD, IND 2027), "
    "ALX002 (CD19×BCMA bispecific for I&I autoimmune), and ALX005 (FcRn×Albumin for autoantibody-driven diseases). "
    "Ailux is a pre-IND biotech with a differentiated bispecific platform and is actively seeking "
    "licensing, co-development, or option deal partners."
)

ABBVIE_CONSTRAINT_NOTE = (
    "[TIMING NOTE: AbbVie has an active TL1A asset (ABBV-701) with Ph1 readout expected Oct 2026. "
    "Per deal sequencing governance, do not approach AbbVie for TL1A bispecific partnership until "
    "after that readout. Downgraded to 'watch' urgency.]"
)


# ── HTTP helpers ──────────────────────────────────────────────────────────────
def _sb_headers(key: str, write: bool = False) -> dict:
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if write:
        h["Prefer"] = "resolution=merge-duplicates,return=representation"
    return h


def sb_get(path: str, params: dict = None) -> List[dict]:
    qs = ("?" + urllib.parse.urlencode(params)) if params else ""
    url = f"{SUPABASE_URL}/rest/v1/{path}{qs}"
    req = urllib.request.Request(url, headers=_sb_headers(_READ_KEY))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"GET {path} → HTTP {e.code}: {body[:200]}")


def sb_post(table: str, rows: List[dict], dry_run: bool = False) -> None:
    if dry_run:
        print(f"  [DRY-RUN] Would insert {len(rows)} rows into {table}")
        return
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    data = json.dumps(rows).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers=_sb_headers(_WRITE_KEY, write=True)
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"POST {table} → HTTP {e.code}: {body[:300]}")


def sb_delete(table: str, params: dict, dry_run: bool = False) -> None:
    """Delete rows matching params."""
    if dry_run:
        print(f"  [DRY-RUN] Would DELETE from {table} WHERE {params}")
        return
    qs = "?" + urllib.parse.urlencode(params)
    url = f"{SUPABASE_URL}/rest/v1/{table}{qs}"
    req = urllib.request.Request(url, method="DELETE", headers=_sb_headers(_WRITE_KEY))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"DELETE {table} → HTTP {e.code}: {body[:200]}")


# ── Data pull ─────────────────────────────────────────────────────────────────
def pull_all_data() -> Dict[str, Any]:
    """Pull all source tables needed for scoring."""
    print("Pulling data from Supabase...")

    # Companies with strategic_value_score
    companies = sb_get(
        "companies",
        {
            "strategic_value_score": "not.is.null",
            "select": "id,name,strategic_value_score,coverage_status,strategic_value_rationale,ailux_angle,overlap,status",
            "limit": "200",
        }
    )
    print(f"  Companies with SVS: {len(companies)}")

    # Strategic views (partnership fit + context)
    views_raw = sb_get(
        "company_strategic_views",
        {"select": "company_id,view_type,strategic_score,summary,ailux_relevance", "limit": "400"}
    )
    # Index by company_id; keep best view_type per company (licensing > partnership > acquisition > competitive)
    VIEW_PRIORITY = {
        "licensing_candidate": 4,
        "partnership": 3,
        "acquisition_target": 2,
        "competitive": 1,
    }
    views: Dict[str, dict] = {}
    for v in views_raw:
        cid = v["company_id"]
        if cid not in views:
            views[cid] = v
        else:
            if VIEW_PRIORITY.get(v["view_type"], 0) > VIEW_PRIORITY.get(views[cid]["view_type"], 0):
                views[cid] = v
    print(f"  Strategic views (unique companies): {len(views)}")

    # Deals last 18 months (for deal appetite)
    eighteen_months_ago = (datetime.date.today() - datetime.timedelta(days=548)).isoformat()
    deals = sb_get(
        "deals",
        {
            "deal_date": f"gt.{eighteen_months_ago}",
            "select": "company_id,deal_type,upfront_usd_m,total_usd_m,from_company,to_company,deal_date,headline,ailux_signal",
            "limit": "300",
        }
    )
    print(f"  Deals (18 mo): {len(deals)}")

    # Catalyst calendar next 12 months (pipeline urgency)
    twelve_months_out = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
    # Supabase: use 'and' filter to get date range on same column
    catalysts = sb_get(
        "catalyst_calendar",
        {
            "and": f"(expected_date.gt.{TODAY},expected_date.lt.{twelve_months_out})",
            "select": "drug_id,company_id,event_type,expected_date,event_name,strategic_significance,ailux_impact",
            "order": "expected_date.asc",
            "limit": "200",
        }
    )
    print(f"  Catalysts (next 12 mo): {len(catalysts)}")

    # Direct overlap drugs (for deal framing context)
    drugs = sb_get(
        "drugs",
        {
            "overlap": "eq.Direct",
            "select": "id,display_name,company_id,stage,target,ailux_angle",
            "limit": "150",
        }
    )
    print(f"  Direct overlap drugs: {len(drugs)}")

    return {
        "companies": companies,
        "views": views,
        "deals": deals,
        "catalysts": catalysts,
        "drugs": drugs,
    }


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_company(company: dict, data: Dict[str, Any]) -> Dict[str, Any]:
    """Score one company across 5 dimensions. Returns score dict."""
    cid = company["id"]
    svs = company.get("strategic_value_score") or 0

    # ── 1. Strategic Value (0–30) ─────────────────────────────────────────────
    strategic_value_pts = round(min(svs / 100 * 30, 30), 2)

    # ── 2. Pipeline Urgency (0–25) ────────────────────────────────────────────
    pipeline_urgency_pts = 0.0
    key_catalyst = None
    company_cats = [c for c in data["catalysts"] if c.get("company_id") == cid]
    # Also check drugs owned by this company that have catalysts
    company_drug_ids = {d["id"] for d in data["drugs"] if d.get("company_id") == cid}
    drug_cats = [c for c in data["catalysts"] if c.get("drug_id") in company_drug_ids]
    all_cats = company_cats + [c for c in drug_cats if c not in company_cats]
    for cat in all_cats:
        sig = cat.get("strategic_significance", "") or ""
        etype = (cat.get("event_type") or "").lower()
        days_out = (
            datetime.date.fromisoformat(cat["expected_date"]) - datetime.date.today()
        ).days if cat.get("expected_date") else 999
        if days_out <= 365:
            pts = 0
            if "trial_readout" in etype or "readout" in etype or "topline" in etype.lower():
                pts = 8
            elif "pdufa" in etype or "approval" in etype or "fda" in etype:
                pts = 8
            elif "phase_start" in etype or "fih" in etype:
                pts = 4
            else:
                pts = 5  # general
            # P0 significance gets max boost
            if sig == "P0":
                pts = min(pts + 2, 10)
            pipeline_urgency_pts += pts
            if key_catalyst is None:
                key_catalyst = f"{cat.get('event_name','?')[:80]} ({cat['expected_date']})"
    pipeline_urgency_pts = round(min(pipeline_urgency_pts, 25), 2)

    # ── 3. Deal Appetite (0–20) ───────────────────────────────────────────────
    deal_appetite_pts = 0.0
    company_deals = [
        d for d in data["deals"]
        if d.get("company_id") == cid
        or d.get("from_company") == company["name"]
        or d.get("to_company") == company["name"]
    ]
    for deal in company_deals:
        upfront = deal.get("upfront_usd_m") or 0
        try:
            upfront = float(upfront)
        except (TypeError, ValueError):
            upfront = 0.0
        if upfront > 500:
            deal_appetite_pts += 10
        else:
            deal_appetite_pts += 5
    deal_appetite_pts = round(min(deal_appetite_pts, 20), 2)

    # ── 4. Partnership Fit (0–15) ─────────────────────────────────────────────
    VIEW_SCORE = {
        "licensing_candidate": 15,
        "partnership":         12,
        "acquisition_target":  10,
        "competitive":          3,
    }
    view = data["views"].get(cid, {})
    view_type = view.get("view_type", "competitive")
    partnership_fit_pts = float(VIEW_SCORE.get(view_type, 3))

    # ── 5. Coverage Gap (0–10) ────────────────────────────────────────────────
    # Use coverage_status as proxy if coverage_score not available
    # (coverage_scores table exists separately; use status heuristic)
    cov_status = company.get("coverage_status") or "unknown"
    cov_heuristic = {
        "complete": 100,
        "partial": 60,
        "minimal": 30,
        "unknown": 15,
        "none": 5,
    }.get(cov_status.lower(), 50)
    coverage_gap_pts = round(10 * (1 - cov_heuristic / 100), 2)

    total = round(
        strategic_value_pts
        + pipeline_urgency_pts
        + deal_appetite_pts
        + partnership_fit_pts
        + coverage_gap_pts,
        2,
    )

    # ── Call urgency ──────────────────────────────────────────────────────────
    if total >= 60:
        call_urgency = "this_week"
    elif total >= 45:
        call_urgency = "this_month"
    elif total >= 30:
        call_urgency = "this_quarter"
    else:
        call_urgency = "watch"

    # ── Governance: AbbVie constraint ─────────────────────────────────────────
    abbvie_blocked = False
    if cid == "abbvie":
        call_urgency = "watch"
        abbvie_blocked = True

    return {
        "company_id": cid,
        "company_name": company["name"],
        "total_score": total,
        "strategic_value_pts": strategic_value_pts,
        "pipeline_urgency_pts": pipeline_urgency_pts,
        "deal_appetite_pts": deal_appetite_pts,
        "partnership_fit_pts": partnership_fit_pts,
        "coverage_gap_pts": coverage_gap_pts,
        "call_urgency": call_urgency,
        "key_catalyst": key_catalyst,
        "view_type": view_type,
        "view_summary": (view.get("summary") or "")[:500],
        "ailux_relevance": (view.get("ailux_relevance") or "")[:300],
        "ailux_angle": (company.get("ailux_angle") or "")[:300],
        "company_drugs": [
            d for d in data["drugs"] if d.get("company_id") == cid
        ],
        "abbvie_blocked": abbvie_blocked,
    }


# ── Claude deal framing ───────────────────────────────────────────────────────

def generate_deal_framing(scored: dict) -> str:
    """Call Claude Haiku to generate a 3-sentence deal opener."""
    if not ANTHROPIC_API_KEY:
        return "[No Anthropic API key — framing skipped]"

    drugs = scored["company_drugs"]
    drug_list = "; ".join(
        f"{d.get('display_name') or d['id']} ({d.get('stage','?')}, {d.get('target','?')})"
        for d in drugs[:5]
    ) or "No direct overlap drugs tracked"

    summary = scored["view_summary"] or scored["ailux_relevance"] or scored["ailux_angle"] or "No context available."

    prompt = f"""You are a BD advisor at Ailux Biotherapeutics. {AILUX_CONTEXT}

Generate a 3-sentence deal conversation opener for approaching {scored['company_name']}:
- Sentence 1: Why Ailux is approaching them specifically (their pipeline situation and what makes them a fit right now)
- Sentence 2: What Ailux offers (bispecific platform, TL1A×IL-23p19 mechanism, IND 2027 timing, differentiation)
- Sentence 3: The specific partnership ask (licensing, co-development, or option deal — be concrete)

Company context: {summary}
Their tracked assets: {drug_list}
Partnership type assessment: {scored['view_type']}
Key upcoming catalyst: {scored['key_catalyst'] or 'None in next 12 months'}

Be specific, data-driven, and BD-grade professional. No generic filler phrases. Each sentence must contain at least one concrete data point or mechanism detail."""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 400,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        method="POST",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        text = resp["content"][0]["text"].strip()
        if scored["abbvie_blocked"]:
            text += f"\n\n{ABBVIE_CONSTRAINT_NOTE}"
        return text
    except Exception as e:
        return f"[Framing generation failed: {e}]"


# ── Table creation ────────────────────────────────────────────────────────────

BD_REC_DDL = """
CREATE TABLE IF NOT EXISTS bd_recommendations (
    id                   SERIAL PRIMARY KEY,
    company_id           TEXT NOT NULL,
    recommendation_date  DATE NOT NULL,
    total_score          NUMERIC,
    strategic_value_pts  NUMERIC,
    pipeline_urgency_pts NUMERIC,
    deal_appetite_pts    NUMERIC,
    partnership_fit_pts  NUMERIC,
    coverage_gap_pts     NUMERIC,
    rank                 INTEGER,
    deal_framing         TEXT,
    call_urgency         TEXT,
    key_catalyst         TEXT,
    created_at           TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bd_rec_date    ON bd_recommendations(recommendation_date);
CREATE INDEX IF NOT EXISTS idx_bd_rec_company ON bd_recommendations(company_id);
CREATE INDEX IF NOT EXISTS idx_bd_rec_urgency ON bd_recommendations(call_urgency);
"""


def ensure_table(dry_run: bool = False) -> bool:
    """Create bd_recommendations table if it doesn't exist. Returns True if confident."""
    if dry_run:
        print("  [DRY-RUN] Would ensure bd_recommendations table exists")
        return True
    # Probe first
    try:
        sb_get("bd_recommendations", {"limit": "1"})
        return True  # table already exists
    except RuntimeError as e:
        if "404" not in str(e) and "does not exist" not in str(e).lower():
            raise  # unexpected error

    # Create via Supabase Management API (PAT required)
    if not SUPABASE_PAT:
        print("  WARNING: No .supabase_pat — cannot create bd_recommendations table. "
              "Run DDL manually:\n" + BD_REC_DDL)
        return False

    mgmt_headers = {
        "Authorization": f"Bearer {SUPABASE_PAT}",
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0.1",
    }
    for label, sql in [
        ("table", "CREATE TABLE IF NOT EXISTS bd_recommendations (id SERIAL PRIMARY KEY, company_id TEXT NOT NULL, recommendation_date DATE NOT NULL, total_score NUMERIC, strategic_value_pts NUMERIC, pipeline_urgency_pts NUMERIC, deal_appetite_pts NUMERIC, partnership_fit_pts NUMERIC, coverage_gap_pts NUMERIC, rank INTEGER, deal_framing TEXT, call_urgency TEXT, key_catalyst TEXT, created_at TIMESTAMP DEFAULT NOW())"),
        ("idx_date",    "CREATE INDEX IF NOT EXISTS idx_bd_rec_date ON bd_recommendations(recommendation_date)"),
        ("idx_company", "CREATE INDEX IF NOT EXISTS idx_bd_rec_company ON bd_recommendations(company_id)"),
        ("idx_urgency", "CREATE INDEX IF NOT EXISTS idx_bd_rec_urgency ON bd_recommendations(call_urgency)"),
    ]:
        try:
            payload = json.dumps({"query": sql}).encode()
            req = urllib.request.Request(MGMT_URL, data=payload, method="POST", headers=mgmt_headers)
            with urllib.request.urlopen(req, timeout=20) as r:
                r.read()
            print(f"  {label}: OK")
        except Exception as e:
            print(f"  WARNING: Could not create {label}: {e}")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main(dry_run: bool = False, top_n: int = 20, print_top: int = 10) -> List[dict]:
    """
    Full BD recommendations run.
    Returns list of scored+framed records (top_n).
    """
    print(f"\n{'='*60}")
    print(f"Meridian BD Recommendations Engine — {TODAY}")
    print(f"{'='*60}\n")

    if not _READ_KEY:
        print("ERROR: No Supabase key available. Check .supabase_service_key or .supabase_anon_key")
        sys.exit(1)

    # 1. Pull data
    data = pull_all_data()

    # 2. Score every company
    print("\nScoring companies...")
    scored_list: List[dict] = []
    for company in data["companies"]:
        try:
            s = score_company(company, data)
            scored_list.append(s)
        except Exception as e:
            print(f"  WARNING: Skipped {company.get('name','?')}: {e}")

    # 3. Rank
    scored_list.sort(key=lambda x: x["total_score"], reverse=True)
    top = scored_list[:top_n]
    for i, s in enumerate(top, 1):
        s["rank"] = i

    # 4. Generate deal framings — parallel (4 workers) for speed
    print(f"\nGenerating deal framings for top {top_n} companies (Claude Haiku, parallel)...")

    def _frame_one(s):
        framing = generate_deal_framing(s)
        return s["rank"], framing

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_frame_one, s): s for s in top}
        for future in as_completed(futures):
            rank, framing = future.result()
            scored_by_rank = {s["rank"]: s for s in top}
            scored_by_rank[rank]["deal_framing"] = framing
            print(f"  [{rank:02d}] done", flush=True)

    # 5. Ensure table + write to Supabase
    ensure_table(dry_run=dry_run)

    # Clear today's existing recommendations before re-inserting
    if not dry_run:
        try:
            sb_delete("bd_recommendations", {"recommendation_date": f"eq.{TODAY}"})
            print(f"  Cleared existing {TODAY} recommendations")
        except Exception as e:
            print(f"  WARNING: Could not clear old rows: {e}")

    rows = []
    for s in top:
        rows.append({
            "company_id":           s["company_id"],
            "recommendation_date":  TODAY,
            "total_score":          s["total_score"],
            "strategic_value_pts":  s["strategic_value_pts"],
            "pipeline_urgency_pts": s["pipeline_urgency_pts"],
            "deal_appetite_pts":    s["deal_appetite_pts"],
            "partnership_fit_pts":  s["partnership_fit_pts"],
            "coverage_gap_pts":     s["coverage_gap_pts"],
            "rank":                 s["rank"],
            "deal_framing":         s["deal_framing"],
            "call_urgency":         s["call_urgency"],
            "key_catalyst":         s["key_catalyst"],
        })

    try:
        sb_post("bd_recommendations", rows, dry_run=dry_run)
        print(f"\n  Wrote {len(rows)} recommendations to bd_recommendations")
    except RuntimeError as e:
        print(f"\n  WARNING: Could not write to bd_recommendations: {e}")
        print("  (Table may not exist yet — run DDL manually in Supabase SQL editor)")

    # 6. Print report
    print(f"\n{'='*60}")
    print(f"TOP {print_top} BD RECOMMENDATIONS — {TODAY}")
    print(f"{'='*60}")

    urgency_map = {
        "this_week":    "CALL THIS WEEK",
        "this_month":   "call this month",
        "this_quarter": "call this quarter",
        "watch":        "watch",
    }

    for s in top[:print_top]:
        urg = urgency_map.get(s["call_urgency"], s["call_urgency"])
        print(f"\n[#{s['rank']}] {s['company_name'].upper()} — Score: {s['total_score']}/100  [{urg.upper()}]")
        print(f"  Strategic Value: {s['strategic_value_pts']:.1f}/30  |  "
              f"Pipeline Urgency: {s['pipeline_urgency_pts']:.1f}/25  |  "
              f"Deal Appetite: {s['deal_appetite_pts']:.1f}/20  |  "
              f"Partnership Fit: {s['partnership_fit_pts']:.1f}/15  |  "
              f"Coverage Gap: {s['coverage_gap_pts']:.1f}/10")
        if s["key_catalyst"]:
            print(f"  KEY CATALYST: {s['key_catalyst']}")
        print(f"  DEAL FRAMING:")
        for line in s["deal_framing"].split("\n"):
            if line.strip():
                print(f"    {line}")

    print(f"\n{'='*60}")
    this_week = [s for s in top if s["call_urgency"] == "this_week"]
    this_month = [s for s in top if s["call_urgency"] == "this_month"]
    print(f"CALL THIS WEEK ({len(this_week)}): {', '.join(s['company_name'] for s in this_week)}")
    print(f"CALL THIS MONTH ({len(this_month)}): {', '.join(s['company_name'] for s in this_month)}")
    print(f"{'='*60}\n")

    return top


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Meridian BD Recommendations Engine")
    parser.add_argument("--dry-run", action="store_true", help="Score + frame but skip DB writes")
    parser.add_argument("--top", type=int, default=20, help="Number of companies to score + frame (default 20)")
    parser.add_argument("--print-top", type=int, default=10, help="Number to print in detail (default 10)")
    args = parser.parse_args()
    main(dry_run=args.dry_run, top_n=args.top, print_top=args.print_top)
