#!/usr/bin/env python3
"""
bd_recommender_scoring.py — company scoring + Claude deal-framing (§3 split).

score_company() (deterministic BD scoring) + generate_deal_framing() (Claude Haiku
opener via the Anthropic REST API). Extracted verbatim from bd_recommender.py. Has
its own minimal cred read so it stays a leaf (imports nothing from the orchestrator).
"""
import os
import json
import datetime
import urllib.request
import urllib.parse
from typing import Any, Dict

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT   = os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPTS_DIR)))

def _cred(env_var: str, filename: str) -> str:
    val = os.environ.get(env_var, "")
    if val:
        return val.strip()
    for base in [_REPO_ROOT, _SCRIPTS_DIR]:
        path = os.path.join(base, filename)
        if os.path.exists(path):
            return open(path).read().strip()
    return ""

ANTHROPIC_API_KEY = _cred("ANTHROPIC_API_KEY", ".anthropic_api_key")

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
