#!/usr/bin/env python3
"""
drug_intake.py — Drug-First Discovery Engine (Task #93)

CLI tool: python scripts/drug_intake.py --drug "Tozorakimab"

PURPOSE
-------
Entry point into the Meridian entity graph from a drug anchor.

Given a drug name, this script:
  1. Resolves drug identity against the Meridian drugs table
  2. Fetches the current graph state (what Meridian already knows)
  3. Researches the drug open-endedly via Claude Sonnet
  4. Produces two outputs:
       Output A — Routing Decision: which areas does this drug belong in, at what overlap tier?
       Output B — Completeness Audit: what does the graph still need for this drug?
  5. Writes a discovery_queue row with source='drug_intake', coverage_score,
     completeness_gaps, promotion_payload, and evidence_tier for human review

MODEL TIER RULE
---------------
Live writes require Claude Sonnet. Haiku is blocked for live writes.
Use --dry-run with INTAKE_MODEL=claude-haiku-4-5-20251001 for fast structural validation.

EVIDENCE TIER
-------------
All drugs route through the same pipeline regardless of stage. The evidence_tier field
makes the confidence level explicit so reviewers can calibrate accordingly.

  Confirmed  — Named molecule + named company + clinical stage (Phase 1–Approved)
               High data quality. Can be promoted directly.
  Likely     — Named molecule + company source + preclinical/IND-enabling, OR
               medium data quality with clinical stage.
               Promote with standard review.
  Emerging   — Mechanism known, molecule partially named or stage=Discovery/Undisclosed.
               Low data quality. Promote only after manual verification.
  Hypothesis — Strategic inference only. No named molecule or no company anchor.
               Do NOT create a production drug row without manual approval.
               Keep as signal unless evidence is subsequently confirmed.

COMBO COMPONENT RULE
--------------------
If a combination drug (e.g. guselkumab-golimumab) is linked to an area,
each component drug is checked for: existence in drugs, drug_areas, drug_area_scores.
Missing component area links are surfaced as warnings (graph completeness gaps).

USAGE
-----
  python scripts/drug_intake.py --drug "Tozorakimab"
  python scripts/drug_intake.py --drug "Amlitelimab" --area il4ra
  python scripts/drug_intake.py --drug "QX031N" --company "Qyuns" --dry-run
  python scripts/drug_intake.py --drug "Tozorakimab" --dry-run --verbose

ENVIRONMENT
-----------
  ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
  INTAKE_MODEL  (optional) — model override; defaults to claude-sonnet-4-6
                             Haiku blocked for live writes.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    import requests
except ImportError:
    import urllib.request as _ur, urllib.parse as _up, urllib.error as _ue, json as _rjson
    class _Resp:
        def __init__(self, code, body):
            self.status_code = code
            self._body = body
        def json(self):     return _rjson.loads(self._body)
        @property
        def text(self):     return self._body.decode() if isinstance(self._body, bytes) else self._body
    class _Requests:
        @staticmethod
        def _call(method, url, headers=None, params=None, json=None, **kw):
            if params: url += '?' + _up.urlencode(params)
            data = _rjson.dumps(json).encode() if json else None
            req  = _ur.Request(url, data=data, headers=headers or {}, method=method)
            try:
                with _ur.urlopen(req) as r: return _Resp(r.status, r.read())
            except _ue.HTTPError as e:      return _Resp(e.code,   e.read())
        def get(self,  url, **kw): return self._call('GET',  url, **kw)
        def post(self, url, **kw): return self._call('POST', url, **kw)
        def patch(self,url, **kw): return self._call('PATCH',url, **kw)
    requests = _Requests()

import anthropic

# ── Credential helpers (reuse company_intake pattern) ────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from meridian.identity.company_identity_resolver import get_credentials
except ImportError:
    def get_credentials():
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            # Try workspace files
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            try:
                with open(os.path.join(base, ".supabase_config")) as f:
                    for line in f:
                        if line.startswith("SUPABASE_URL="):
                            url = line.split("=", 1)[1].strip()
            except FileNotFoundError:
                pass
            try:
                with open(os.path.join(base, ".supabase_service_key")) as f:
                    key = f.read().strip()
            except FileNotFoundError:
                pass
        return url, key

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SUPABASE_URL, SUPABASE_KEY = get_credentials()

_sb_headers = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}

_ai: anthropic.Anthropic | None = None

def _get_ai() -> anthropic.Anthropic:
    global _ai
    if _ai is None:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise SystemExit(
                "ERROR: ANTHROPIC_API_KEY not set.\n"
                "export ANTHROPIC_API_KEY=sk-ant-..."
            )
        _ai = anthropic.Anthropic(api_key=key)
    return _ai


# ── Active Meridian areas ─────────────────────────────────────────────────────

ACTIVE_AREAS = {
    "tl1a":  {"label": "TL1A × IBD",                     "keywords": ["TL1A", "TNFSF15", "DR3", "IBD", "Crohn", "ulcerative colitis", "UC", "CD"]},
    "tslp":  {"label": "TSLP × Respiratory",              "keywords": ["TSLP", "thymic stromal lymphopoietin", "IL-33", "ST2", "asthma", "COPD", "atopic", "eosinophil"]},
    "il4ra": {"label": "IL-4Rα × Atopy",                  "keywords": ["IL-4R", "IL-4Rα", "IL-13", "atopic dermatitis", "AD", "asthma", "OX40L", "CRSwNP"]},
    "fcrn":  {"label": "FcRn × Autoimmune",               "keywords": ["FcRn", "neonatal Fc receptor", "IgG", "gMG", "ITP", "pemphigus", "HDFN", "nipocalimab", "rozanolixizumab"]},
    "igf1r": {"label": "IGF-1R × Thyroid Eye",            "keywords": ["IGF-1R", "IGF1R", "TSH receptor", "TSHR", "thyroid eye disease", "TED", "Graves", "teprotumumab"]},
    "tcell": {"label": "T-cell Engineering × Autoimmune", "keywords": ["CAR-T", "T cell", "TCR", "BCMA", "CD19", "autoimmune", "cell therapy", "CAR-Treg"]},
}

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — DRUG IDENTITY RESOLUTION
# ══════════════════════════════════════════════════════════════════════════════

def resolve_drug_identity(drug_name: str, company_hint: str | None = None) -> dict:
    """
    Resolve drug name against the Meridian drugs table.

    Resolution types:
      existing_drug    — exact or strong fuzzy match, drug_id returned
      candidate_new    — no match found, treat as new drug
      ambiguous        — multiple fuzzy matches, pause for clarification

    Returns dict with keys: resolution_type, drug_id, drug_row (or None), match_score, candidates
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"resolution_type": "candidate_new", "drug_id": None, "drug_row": None, "match_score": 0.0, "candidates": []}

    # Fetch all drugs for resolution (id, name, display_name, brand_name, aliases, company_id)
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/drugs",
            headers={**_sb_headers, "Prefer": ""},
            params={
                "select": "id,name,display_name,brand_name,aliases,company_id,target,stage,modality,cls,overlap,catalog_category",
                "limit":  "2000",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return {"resolution_type": "candidate_new", "drug_id": None, "drug_row": None, "match_score": 0.0, "candidates": []}
        all_drugs = resp.json()
    except Exception:
        return {"resolution_type": "candidate_new", "drug_id": None, "drug_row": None, "match_score": 0.0, "candidates": []}

    drug_name_lower = drug_name.lower().strip()

    # Build list of (drug_row, all_name_variants) for matching
    def _names(d: dict) -> list[str]:
        ns = []
        for field in ("name", "display_name", "brand_name"):
            v = d.get(field)
            if v:
                ns.append(v.lower().strip())
        aliases = d.get("aliases") or []
        if isinstance(aliases, list):
            ns.extend(a.lower().strip() for a in aliases if a)
        elif isinstance(aliases, str):
            try:
                parsed = json.loads(aliases)
                ns.extend(a.lower().strip() for a in parsed if a)
            except Exception:
                pass
        return ns

    # Exact match first
    for d in all_drugs:
        if drug_name_lower in _names(d):
            return {
                "resolution_type": "existing_drug",
                "drug_id":    d["id"],
                "drug_row":   d,
                "match_score": 1.0,
                "candidates": [],
            }

    # Fuzzy match — score each drug by best name variant match
    scored = []
    for d in all_drugs:
        best = max(
            difflib.SequenceMatcher(None, drug_name_lower, n).ratio()
            for n in _names(d)
        ) if _names(d) else 0.0
        if best >= 0.7:
            scored.append((best, d))

    scored.sort(key=lambda x: -x[0])

    if not scored:
        return {"resolution_type": "candidate_new", "drug_id": None, "drug_row": None, "match_score": 0.0, "candidates": []}

    best_score, best_drug = scored[0]

    if best_score >= 0.90:
        # Strong fuzzy — treat as existing
        return {
            "resolution_type": "existing_drug",
            "drug_id":    best_drug["id"],
            "drug_row":   best_drug,
            "match_score": best_score,
            "candidates": [],
        }

    if best_score >= 0.70:
        # Moderate fuzzy — could be ambiguous
        top_candidates = [d for _, d in scored[:3]]
        if len(scored) == 1 or scored[0][0] - scored[1][0] > 0.10:
            # Single clear best match — flag for confirmation but don't block
            return {
                "resolution_type": "fuzzy_match",
                "drug_id":    best_drug["id"],
                "drug_row":   best_drug,
                "match_score": best_score,
                "candidates": top_candidates,
            }
        return {
            "resolution_type": "ambiguous",
            "drug_id":    None,
            "drug_row":   None,
            "match_score": best_score,
            "candidates": top_candidates,
        }

    return {"resolution_type": "candidate_new", "drug_id": None, "drug_row": None, "match_score": 0.0, "candidates": []}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — FETCH CURRENT GRAPH STATE
# ══════════════════════════════════════════════════════════════════════════════

def fetch_graph_state(drug_id: str | None, company_id: str | None) -> dict:
    """
    Fetch everything Meridian currently knows about this drug.
    Returns a dict with keys: drug, molecule_intelligence, trials, drug_area_scores,
                               catalysts, signals, deals
    """
    state = {
        "drug":                 None,
        "molecule_intelligence": None,
        "trials":               [],
        "drug_area_scores":     [],
        "catalysts":            [],
        "signals":              [],
        "deals":                [],
    }

    if not SUPABASE_URL or not SUPABASE_KEY:
        return state

    def _get(table: str, params: dict) -> list:
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/{table}",
                headers={**_sb_headers, "Prefer": ""},
                params={**params, "limit": "200"},
                timeout=10,
            )
            return r.json() if r.status_code == 200 else []
        except Exception:
            return []

    if drug_id:
        # Drug row
        rows = _get("drugs", {"id": f"eq.{drug_id}", "select": "*"})
        state["drug"] = rows[0] if rows else None

        # Molecule intelligence
        mi_rows = _get("molecule_intelligence", {"drug_id": f"eq.{drug_id}", "select": "*"})
        state["molecule_intelligence"] = mi_rows[0] if mi_rows else None

        # Trials
        state["trials"] = _get("trials", {
            "drug_id": f"eq.{drug_id}",
            "select":  "id,phase,indication,status,readout_date,trial_name",
        })

        # Drug area scores
        state["drug_area_scores"] = _get("drug_area_scores", {
            "drug_id": f"eq.{drug_id}",
            "select":  "area_id,overlap,cls,overlap_rationale,vs_ailux_positioning,area_fit",
        })

    if company_id:
        # Catalysts for this company (active areas)
        area_ids = ",".join(ACTIVE_AREAS.keys())
        cutoff_future = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        state["catalysts"] = _get("catalysts", {
            "company_id":    f"eq.{company_id}",
            "catalyst_date": f"gte.{cutoff_future}",
            "select":        "id,catalyst_date,label,area_id,catalyst_type,significance",
        })

        # Signals last 90 days
        cutoff_past = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
        state["signals"] = _get("signals", {
            "company_id": f"eq.{company_id}",
            "event_date": f"gte.{cutoff_past}",
            "select":     "signal_type,headline,event_date,area_id,relevance_score",
        })

        # Deals
        state["deals"] = _get("deals", {
            "company_id": f"eq.{company_id}",
            "select":     "id,deal_date,deal_type,from_company,to_company,headline,upfront_usd_m,total_usd_m",
        })

    return state


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — DRUG RESEARCH (Sonnet only for live writes)
# ══════════════════════════════════════════════════════════════════════════════

DRUG_RESEARCH_PROMPT = """You are a pharmaceutical competitive intelligence analyst.

Research the drug: **{drug_name}**{company_context}

Your task is OPEN-ENDED DISCOVERY across all Meridian therapeutic areas.
Research this drug comprehensively: mechanism, target, clinical development, company, competitive positioning.

Return a JSON object with this exact structure:

{{
  "drug": {{
    "canonical_name": "string — INN or WHO-approved name",
    "display_name": "string — common display name (may include brand if Phase 3+)",
    "brand_name": "string or null — approved brand name if any",
    "aliases": ["string"] — code names, former names, trial identifiers (e.g. MEDI3506, AZD0471),
    "company": "string — developing company full name",
    "company_id_hint": "string or null — suggest Meridian company_id if known (e.g. astrazeneca, abbvie, jnj)",
    "target": "string — molecular target(s), specific (e.g. IL-33 (anti-ST2), not just 'cytokine')",
    "mechanism": "string — mechanism of action",
    "modality": "string — mAb|bispecific|small molecule|ADC|cell therapy|fusion protein|etc.",
    "stage": "string — Preclinical|Phase 1|Phase 2|Phase 3|Approved|Terminated",
    "primary_indication": "string — lead indication",
    "other_indications": ["string"],
    "nct_ids": ["string"] — DO NOT fabricate. Only include if you have verified trial IDs.,
    "data_quality": "string — high|medium|low — how much verified public information is available",
    "source_note": "string — brief citation or evidence summary supporting key facts"
  }},
  "area_assessment": {{
    "tl1a":  {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "tslp":  {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "il4ra": {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "fcrn":  {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "igf1r": {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "tcell": {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}}
  }},
  "upcoming_catalysts": [
    {{
      "event_type": "string — phase_readout|conference|regulatory|pdufa|trial_start|partnership",
      "description": "string — what the event is",
      "expected_date": "string — YYYY-MM or YYYY or 'H1 YYYY'",
      "significance": "string — high|medium|low"
    }}
  ],
  "molecule_intelligence": {{
    "format": "string or null — monospecific|bispecific|trispecific|etc.",
    "valency": "string or null",
    "igg_subclass": "string or null — IgG1|IgG2|IgG4|etc.",
    "fc_engineering": "string or null",
    "epitope": "string or null — binding site / blocking mechanism",
    "half_life": "string or null",
    "differentiation_claim": "string or null — key differentiator vs. class"
  }},
  "competitive_context": "string — 2-3 sentences on where this drug fits in the competitive landscape",
  "bd_angle": "string or null — what BD opportunity or risk does this drug represent for an analyst tracking TL1A/FcRn/IL-4Rα/TSLP/IGF-1R?"
}}

Area definitions for scoring:
- TL1A/IBD: TL1A inhibitors, IL-23 inhibitors in IBD, JAK inhibitors in IBD, integrin inhibitors in IBD
- TSLP/Respiratory: TSLP inhibitors, IL-33/ST2 pathway, anti-IL-33 mAbs, Type 2 inflammation in asthma/COPD
- IL-4Rα/Atopy: IL-4Rα inhibitors, IL-13, OX40L, atopic dermatitis, asthma, CRSwNP
- FcRn/Autoimmune: FcRn inhibitors for IgG-mediated diseases (gMG, ITP, pemphigus, HDFN, SLE, MN)
- IGF-1R/Thyroid Eye: IGF-1R inhibitors or TSH receptor antibodies in TED or Graves disease
- T-cell/Autoimmune Cell Therapy: CAR-T, TCR-T, CAR-Treg, or related cell therapies for autoimmune indications

Confidence: 0.9–1.0 = direct mechanism in area + clinical data; 0.6–0.9 = preclinical or platform; 0.3–0.6 = indication overlap only; <0.3 = speculative

CRITICAL RULES:
- Do NOT fabricate NCT IDs — leave nct_ids as empty list if unknown
- Do NOT fabricate drug names or trial IDs not publicly associated with this drug
- If you have limited information, set data_quality to 'low' and be conservative in scoring
- Return ONLY the JSON object, no prose before or after

Drug to research: {drug_name}
"""


def research_drug(
    drug_name: str,
    company_name: str | None = None,
    verbose: bool = False,
) -> dict | None:
    """
    Call Claude to research the drug open-endedly across all active areas.
    Returns parsed JSON dict or None on failure.
    """
    company_context = f" (developed by {company_name})" if company_name else ""
    prompt = DRUG_RESEARCH_PROMPT.format(
        drug_name=drug_name,
        company_context=company_context,
    )

    _model = os.environ.get("INTAKE_MODEL", "claude-sonnet-4-6")

    if verbose:
        print(f"  → Calling Claude ({_model}) for drug research on '{drug_name}'...")

    try:
        _max_tokens = int(os.environ.get("INTAKE_MAX_TOKENS", "8192"))
        resp = _get_ai().messages.create(
            model=_model,
            max_tokens=_max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()

        # Strip code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)
        if verbose:
            drug_info = data.get("drug", {})
            print(f"  → Research complete. Target: {drug_info.get('target', '?')} | "
                  f"Stage: {drug_info.get('stage', '?')} | "
                  f"Company: {drug_info.get('company', '?')}")
        return data

    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON parse error: {e}")
        print(f"  Raw response (first 500 chars): {raw[:500]}")
        return None
    except Exception as e:
        print(f"  ❌ Research call failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — AREA RELEVANCE SCORING
# ══════════════════════════════════════════════════════════════════════════════

_RELEVANCE_INCLUDE          = {"Direct", "Adjacent", "Same-patient"}
_WATCHLIST_MIN_CONFIDENCE   = 0.65
_MIN_CONFIDENCE             = 0.50


def get_relevant_areas(research: dict, area_filter: str | None = None) -> list[dict]:
    """
    Extract areas that meet minimum evidence + confidence thresholds.
    If area_filter is set, only return that area (if it meets the threshold).
    """
    assessment = research.get("area_assessment", {})
    result = []

    for area_id, area_info in assessment.items():
        if area_id not in ACTIVE_AREAS:
            continue
        if area_filter and area_id != area_filter:
            continue

        relevance  = area_info.get("relevance", "Not relevant")
        confidence = float(area_info.get("confidence", 0))
        rationale  = area_info.get("rationale", "")
        evidence   = area_info.get("evidence", "")

        if relevance == "Not relevant":
            continue
        if relevance == "Watchlist" and confidence < _WATCHLIST_MIN_CONFIDENCE:
            continue
        if confidence < _MIN_CONFIDENCE:
            continue

        result.append({
            "area_id":    area_id,
            "area_label": ACTIVE_AREAS[area_id]["label"],
            "relevance":  relevance,
            "confidence": confidence,
            "rationale":  rationale,
            "evidence":   evidence,
        })

    _order = {"Direct": 0, "Adjacent": 1, "Same-patient": 2, "Watchlist": 3}
    result.sort(key=lambda x: (_order.get(x["relevance"], 9), -x["confidence"]))
    return result


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

def _print_routing_decision(
    drug_name: str,
    research: dict,
    relevant_areas: list[dict],
    resolution: dict,
    evidence_tier: dict | None = None,
    combo_warnings: list[dict] | None = None,
    area_scores: list[dict] | None = None,
):
    drug_info = research.get("drug", {})
    rtype     = resolution.get("resolution_type", "candidate_new")

    print()
    print("═" * 65)
    print(f"  OUTPUT A — ROUTING DECISION")
    print("─" * 65)
    print(f"  Drug:    {drug_info.get('canonical_name', drug_name)}")
    if drug_info.get("brand_name"):
        print(f"           ({drug_info['brand_name']})")
    print(f"  Company: {drug_info.get('company', 'Unknown')}")
    print(f"  Target:  {drug_info.get('target', '?')}")
    print(f"  Stage:   {drug_info.get('stage', '?')} — {drug_info.get('primary_indication', '?')}")
    print(f"  Identity: {rtype}")
    if resolution.get("drug_id"):
        print(f"           → Meridian ID: {resolution['drug_id']}")

    # Evidence tier
    if evidence_tier:
        tier = evidence_tier["tier"]
        tier_icon = {"Confirmed": "✅", "Likely": "🟡", "Emerging": "🟠", "Hypothesis": "🔴"}.get(tier, "")
        print(f"  Evidence: {tier_icon} {tier} — {evidence_tier['rationale']}")
        if tier in ("Emerging", "Hypothesis"):
            print(f"  ⚠️  {evidence_tier['review_note']}")
    print()

    if not relevant_areas:
        print("  ⚪ No areas meet the minimum evidence threshold.")
        print("  This drug may not be in scope for active Meridian areas.")
    else:
        # Build score lookup if provided
        score_lookup = {s["area_id"]: s["strategic_value_score"] for s in (area_scores or [])}
        for area in relevant_areas:
            conf_bar = "█" * int(area["confidence"] * 10) + "░" * (10 - int(area["confidence"] * 10))
            svs      = score_lookup.get(area["area_id"])
            svs_str  = f"  Strategic Value: {svs}/10" if svs is not None else ""
            print(f"  {area['relevance']:<15} {area['area_label']}{svs_str}")
            print(f"  Confidence  [{conf_bar}] {area['confidence']:.0%}")
            print(f"  Rationale   {area['rationale'][:120]}")
            if area["evidence"]:
                print(f"  Evidence    {area['evidence'][:120]}")
            print()

    if research.get("competitive_context"):
        print(f"  Context: {research['competitive_context'][:200]}")
    if research.get("bd_angle"):
        print(f"  BD Angle: {research['bd_angle'][:200]}")
    print(f"  Data quality: {drug_info.get('data_quality', 'unknown')}")

    # Combo component warnings
    if combo_warnings:
        print()
        print(f"  ⚠️  COMBO COMPONENT GAPS ({len(combo_warnings)} issue(s)):")
        for w in combo_warnings:
            icon = "❌" if w["issue"] == "component_drug_missing" else "⚠️ "
            print(f"    {icon} {w['component']} / {w['area_id']}: {w['suggestion']}")

    print("═" * 65)


# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT B — COMPLETENESS AUDIT
# ══════════════════════════════════════════════════════════════════════════════

_DIM_LABELS = {
    "identity":         "Identity",
    "company":          "Company",
    "target":           "Target",
    "trials":           "Trials",
    "catalysts":        "Catalysts",
    "molecule_intel":   "Molecule Intel",
    "conference_intel": "Conference Intel",
    "deals":            "Deals",
}

def _score_icon(score) -> str:
    if score is None:  return "N/A"
    if score >= 90:    return "✓ 100%"
    if score >= 60:    return "~ " + str(score) + "%"
    return "✗ " + str(score) + "%"


def _print_completeness_audit(
    drug_name: str,
    coverage: dict,
    research: dict,
    graph_state: dict,
):
    dims    = coverage["dimensions"]
    overall = coverage["coverage_score"]

    print()
    print("═" * 65)
    print(f"  OUTPUT B — COMPLETENESS AUDIT")
    print("─" * 65)
    print(f"  {drug_name} Coverage: {overall}%")
    print()

    for dim_key, dim_label in _DIM_LABELS.items():
        score = dims.get(dim_key)
        icon  = _score_icon(score)
        print(f"    {dim_label:<20} {icon}")

    # Missing fields
    missing = []
    if dims.get("molecule_intel", 0) < 90:
        missing.append("Molecule Intelligence")
    if dims.get("catalysts", 0) < 50:
        upcoming = research.get("upcoming_catalysts") or []
        if upcoming:
            missing.append(f"Catalysts (found {len(upcoming)} upcoming in research — run enrichment)")
        else:
            missing.append("Upcoming catalysts")
    if dims.get("trials", 0) < 90:
        ncts = research.get("drug", {}).get("nct_ids") or []
        if ncts:
            missing.append(f"Trial data ({len(ncts)} NCT IDs found — run trial sync)")
        else:
            missing.append("Trial summaries")
    if dims.get("conference_intel", 0) < 50:
        missing.append("Conference activity (last 90 days)")
    if dims.get("deals") is not None and dims.get("deals", 0) < 50:
        missing.append("Deals / licensing coverage")

    if missing:
        print()
        print(f"  Missing: {' · '.join(missing)}")

    # Recommendations
    recs = []
    if dims.get("molecule_intel", 0) < 90:
        recs.append("Run molecule intelligence enrichment")
    if dims.get("catalysts", 0) < 50:
        recs.append("Run catalyst enrichment")
    if dims.get("trials", 0) < 90:
        recs.append("Run trial data sync")
    if dims.get("conference_intel", 0) < 50:
        recs.append("Run signal monitoring")

    if recs:
        print(f"  Recommended: {' · '.join(recs)}")

    print("═" * 65)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — WRITE DISCOVERY QUEUE ROW
# ══════════════════════════════════════════════════════════════════════════════

def _map_relevance_to_overlap(r: str) -> str:
    return {"Direct": "Direct", "Adjacent": "Adjacent", "Same-patient": "Same-Space", "Watchlist": "Watch"}.get(r, "Watch")

def _map_relevance_to_layer(r: str) -> int:
    return {"Direct": 1, "Adjacent": 2, "Same-patient": 3, "Watchlist": 4}.get(r, 4)

def _confidence_to_relevance_score(confidence: float, relevance: str) -> int:
    base = {"Direct": 8, "Adjacent": 6, "Same-patient": 5, "Watchlist": 4}.get(relevance, 3)
    return min(10, int(base + confidence * 2))


# ── Catalog Category Inference ─────────────────────────────────────────────────
# Invariant: every drug that receives a drug_areas row must have catalog_category
# set so it appears in the Drugs to Know tab. Use this helper at all drug inserts.
_CCat_TCE_TARGETS   = {"bcma", "cd3", "cd19", "cd20", "cd38", "cd33", "cd123",
                       "her2", "egfr", "pd-1", "pd-l1", "pdl1", "ctla-4", "ctla4",
                       "tim-3", "lag-3", "cd47", "vegf"}
_CCat_IMMUNO_KWORDS = {"tl1a", "tnfrsf25", "il-4r", "il4r", "tslp", "fcrn",
                       "neonatal fc", "il-23", "il23", "il-17", "il17", "tnf",
                       "il-13", "il13", "il-33", "il33", "il-31", "il31",
                       "integrin", "α4β7", "a4b7", "rankl", "baff", "april",
                       "igg4", "ige", "il-5", "il5", "il-6", "il6"}
_CCat_ONCOLOGY_AREAS = {"tcell", "t_cell"}
_CCat_IMMUNO_AREAS   = {"tl1a", "fcrn", "il4ra", "tslp", "autoimmune",
                         "ibd", "respiratory", "ige"}
_CCat_EARLY_STAGES   = {"preclinical", "phase 1", "phase i", "pre-ind",
                         "ind-enabling", "discovery"}

import re as _re_cc


def infer_catalog_category(target: str = "", modality: str = "",
                            stage: str = "", area_id: str = "") -> str:
    """Infer catalog_category from drug attributes. See company_enrichment.py for full docs."""
    tgt  = (target   or "").lower()
    mod  = (modality or "").lower()
    stg  = (stage    or "").lower()
    area = (area_id  or "").lower()

    tgt_parts = {p.strip() for p in _re_cc.split(r"[×x×/]", tgt) if p.strip()}
    if _CCat_TCE_TARGETS & tgt_parts:
        return "Oncology"
    if any(m in mod for m in ("adc", "car-t", "car t", "antibody-drug conjugate")):
        return "Oncology"
    if area in _CCat_ONCOLOGY_AREAS:
        return "Oncology"
    if "jak" in tgt or "small molecule" in mod or "oral small molecule" in mod:
        return "Small Molecule"
    is_immuno = any(kw in tgt for kw in _CCat_IMMUNO_KWORDS) or area in _CCat_IMMUNO_AREAS
    if is_immuno:
        return "Pipeline" if any(s in stg for s in _CCat_EARLY_STAGES) else "Immunology"
    return "Pipeline"


def build_promotion_payload(
    drug_name: str,
    drug_id:   str | None,
    research:  dict,
    relevant_areas: list[dict],
    graph_state: dict,
) -> dict:
    """
    Build the promotion_payload for the discovery_queue row.
    On approval, approve_discovery_item() will promote all nodes in this payload.
    """
    drug_info   = research.get("drug", {})
    mi_research = research.get("molecule_intelligence") or {}
    upcoming    = research.get("upcoming_catalysts") or []

    _drug_target   = drug_info.get("target") or ""
    _drug_modality = drug_info.get("modality") or ""
    _drug_stage    = drug_info.get("stage") or ""
    _primary_area  = relevant_areas[0]["area_id"] if relevant_areas else ""
    _inferred_cc   = infer_catalog_category(
        target   = _drug_target,
        modality = _drug_modality,
        stage    = _drug_stage,
        area_id  = _primary_area,
    )

    drug_node = {
        "id":           drug_id or _slug(drug_info.get("canonical_name") or drug_name),
        "name":         drug_info.get("canonical_name") or drug_name,
        "display_name": drug_info.get("display_name") or drug_name,
        "brand_name":   drug_info.get("brand_name"),
        "aliases":      drug_info.get("aliases") or [],
        "company_id":   drug_info.get("company_id_hint"),
        "target":       _drug_target or None,
        "mechanism":    drug_info.get("mechanism"),
        "modality":     _drug_modality or None,
        "stage":        _drug_stage or None,
        "data_source":  "catalog" if drug_id else "press_release",
        "catalog_category": _inferred_cc,
    }

    drug_area_scores = [
        {
            "drug_id":             drug_node["id"],
            "area_id":             a["area_id"],
            "overlap":             _map_relevance_to_overlap(a["relevance"]),
            "overlap_rationale":   a["rationale"],
            "area_fit":            a["relevance"],
            "area_fit_rationale":  a["evidence"],
        }
        for a in relevant_areas
    ]

    drug_areas = [{"drug_id": drug_node["id"], "area_id": a["area_id"]} for a in relevant_areas]

    # Molecule intelligence from research (if not already in DB)
    mi_node = None
    if mi_research:
        filled = {k: v for k, v in mi_research.items() if v and v != "null"}
        if filled:
            mi_node = {
                "drug_id":              drug_node["id"],
                "format":               mi_research.get("format"),
                "valency":              mi_research.get("valency"),
                "igg_subclass":         mi_research.get("igg_subclass"),
                "fc_engineering":       mi_research.get("fc_engineering"),
                "epitope":              mi_research.get("epitope"),
                "differentiation_claim": mi_research.get("differentiation_claim"),
                "enriched_by":          "drug_intake",
            }

    # Upcoming catalysts from research
    catalyst_nodes = [
        {
            "company_id":     drug_info.get("company_id_hint"),
            "drug_id":        drug_node["id"],
            "area_id":        relevant_areas[0]["area_id"] if relevant_areas else None,
            "catalyst_type":  c.get("event_type"),
            "label":          c.get("description"),
            "catalyst_date":  c.get("expected_date"),
            "significance":   c.get("significance"),
            "confidence_level": "inferred",
            "confidence_source": "drug_intake_research",
        }
        for c in upcoming[:5]  # cap at 5
    ]

    return {
        "drug":               drug_node,
        "drug_areas":         drug_areas,
        "drug_area_scores":   drug_area_scores,
        "molecule_intelligence": mi_node,
        "catalysts":          catalyst_nodes,
        "trials":             [],  # populated by trial enrichment post-approval
    }


def _slug(name: str) -> str:
    """Convert name to a reasonable Meridian-style id slug."""
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def write_drug_queue_rows(
    drug_name:     str,
    drug_id:       str | None,
    company_id:    str | None,
    resolution:    dict,
    research:      dict,
    relevant_areas: list[dict],
    coverage:      dict,
    run_id:        str,
    dry_run:       bool = False,
    evidence_tier: dict | None = None,
    graph_state:   dict | None = None,
) -> tuple[list[str], list[dict]]:
    """
    Write one discovery_queue row per relevant area.
    Returns list of area_ids successfully written.
    """
    drug_info = research.get("drug", {})
    drug_row  = resolution.get("drug_row") or {}
    canonical_name = drug_info.get("canonical_name") or drug_name
    resolved_company_id = company_id or drug_info.get("company_id_hint")
    resolved_company_name = drug_info.get("company") or ""
    resolved_drug_id = drug_id or _slug(canonical_name)

    # Check for existing queue rows to avoid duplicates
    existing_areas = _check_existing_drug_queue_rows(resolved_drug_id, [a["area_id"] for a in relevant_areas])

    promotion = build_promotion_payload(drug_name, drug_id, research, relevant_areas, {})
    written   = []
    area_score_rows: list[dict] = []  # per-area {area_id, strategic_value_score} for Output A

    completeness_gaps_json = {
        k: (str(v) if v is not None else "n/a")
        for k, v in coverage["dimensions"].items()
    }

    for area in relevant_areas:
        area_id = area["area_id"]

        if area_id in existing_areas:
            print(f"  ⏭️  {area_id}: skipped (recent non-rejected row already exists)")
            continue

        # Compute strategic value score for this area (must come before row dict)
        svs = compute_strategic_value_score(
            overlap       = _map_relevance_to_overlap(area["relevance"]),
            area_id       = area_id,
            stage         = drug_info.get("stage") or (drug_row.get("stage") if drug_row else None),
            catalysts     = graph_state.get("catalysts") or [] if isinstance(graph_state, dict) else [],
            deals         = graph_state.get("deals") or [] if isinstance(graph_state, dict) else [],
            evidence_tier = evidence_tier,
            company_id    = resolved_company_id,
        )

        row = {
            "company_name":            resolved_company_name or canonical_name,
            "company_id_suggested":    resolved_company_id,
            "drug_name":               canonical_name,
            "target":                  drug_info.get("target"),
            "stage":                   drug_info.get("stage"),
            "modality":                drug_info.get("modality"),
            "entity_type":             "molecule",
            "area_id":                 area_id,
            "overlap":                 _map_relevance_to_overlap(area["relevance"]),
            "competition_layer":       _map_relevance_to_layer(area["relevance"]),
            "confidence_score":        int(area["confidence"] * 100),
            "relevance_score":         _confidence_to_relevance_score(area["confidence"], area["relevance"]),
            "relevance_rationale":     area["rationale"],
            "reason":                  f"{area['relevance']} relevance to {ACTIVE_AREAS[area_id]['label']} — {area['evidence']}",
            "source_url":              drug_info.get("source_note"),
            "suggested_dest":          "update_drug" if drug_id else "new_drug",
            "discovered_by":           "drug_intake",
            "status":                  "pending",
            "discovery_run_id":        run_id,
            "relationship_type":       "drug_entity",
            "relationship_confidence": "high" if area["confidence"] >= 0.8 else "medium" if area["confidence"] >= 0.6 else "inferred",
            "why_discovered":          f"Drug Intake CLI — {drug_name}",
            "source":                  "user_intake",
            "evidence_tier":           evidence_tier["tier"] if evidence_tier else None,
            "strategic_value_score":   svs,
        }
        area_score_rows.append({"area_id": area_id, "strategic_value_score": svs})

        if dry_run:
            print(f"  [DRY RUN] Would write queue row: {area_id} / {area['relevance']} / confidence={area['confidence']:.2f} / strategic_value={svs}/10")
            written.append(area_id + f"(svs={svs})")
            continue

        # Attempt full row with new columns (migration v23 + v24)
        row_full = {
            **row,
            "coverage_score":         coverage["coverage_score"],
            "completeness_gaps":      json.dumps(completeness_gaps_json),
            "promotion_payload":      json.dumps(promotion),
            "strategic_value_score":  svs,
        }

        try:
            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/discovery_queue",
                headers=_sb_headers,
                json=row_full,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                written.append(area_id)
                print(f"  ✅ {area_id}: queued ({area['relevance']}, confidence={area['confidence']:.0%}, "
                      f"coverage={coverage['coverage_score']}%, strategic_value={svs}/10)")
            elif resp.status_code == 409:
                print(f"  ⏭️  {area_id}: conflict (row already exists)")
            else:
                # Fallback: try without new columns (migrations not yet applied)
                resp2 = requests.post(
                    f"{SUPABASE_URL}/rest/v1/discovery_queue",
                    headers=_sb_headers,
                    json=row,
                    timeout=10,
                )
                if resp2.status_code in (200, 201):
                    written.append(area_id)
                    print(f"  ✅ {area_id}: queued ({area['relevance']}, confidence={area['confidence']:.0%}) "
                          f"[apply migrations v23/v24 for coverage/payload/strategic_value columns]")
                else:
                    print(f"  ❌ {area_id}: write failed {resp2.status_code} — {resp2.text[:200]}")
        except Exception as e:
            print(f"  ❌ {area_id}: exception — {e}")

    return written, area_score_rows


def _check_existing_drug_queue_rows(drug_name_or_id: str, area_ids: list[str]) -> set[str]:
    """Return area_ids with a recent non-rejected queue row for this drug."""
    if not drug_name_or_id or not area_ids:
        return set()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/discovery_queue",
            headers={**_sb_headers, "Prefer": ""},
            params={
                "drug_name":     f"ilike.{drug_name_or_id}",
                "status":        "not.eq.rejected",
                "discovered_at": f"gte.{cutoff}",
                "select":        "area_id",
                "source":        "eq.user_intake",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return {row["area_id"] for row in resp.json() if row.get("area_id")}
    except Exception:
        pass
    return set()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN WORKFLOW
# ══════════════════════════════════════════════════════════════════════════════

def run_drug_intake(
    drug_name:    str,
    company_hint: str | None = None,
    area_filter:  str | None = None,
    dry_run:      bool = False,
    verbose:      bool = False,
    force:        bool = False,
):
    """
    Full drug intake workflow.
    Bounded stop: writes one reviewable discovery_queue row per relevant area.
    """
    ts     = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    slug   = drug_name.lower().replace(" ", "_").replace("-", "_")
    run_id = f"drug_intake_{slug}_{ts}"

    print()
    print(f"Drug Intake — '{drug_name}'")
    if area_filter:
        print(f"Area filter: {area_filter}")
    print(f"Run ID: {run_id}  |  dry_run={dry_run}")
    print("─" * 55)

    # ── Model-tier guard ─────────────────────────────────────────────────────
    _active_model = os.environ.get("INTAKE_MODEL", "claude-sonnet-4-6")
    if not dry_run and "haiku" in _active_model.lower():
        print(f"\n  ❌ Model tier error: INTAKE_MODEL='{_active_model}' cannot be used for live writes.")
        print(f"     Haiku hallucinates drug pipelines — fabricated drug names may enter discovery_queue.")
        print(f"     Set INTAKE_MODEL=claude-sonnet-4-6 (or unset INTAKE_MODEL) for live runs.")
        print(f"     Use --dry-run with Haiku for fast structural validation only.")
        return

    # ── Step 1: Drug identity resolution ────────────────────────────────────
    print("\n[1/5] Resolving drug identity...")
    resolution = resolve_drug_identity(drug_name, company_hint)
    rtype      = resolution["resolution_type"]
    drug_id    = resolution.get("drug_id")
    drug_row   = resolution.get("drug_row") or {}

    if rtype == "existing_drug":
        print(f"  ✅ Existing drug: '{drug_row.get('name', drug_name)}' (id: {drug_id}, score: {resolution['match_score']:.0%})")
        if drug_row.get("company_id"):
            print(f"     Company: {drug_row['company_id']} | Stage: {drug_row.get('stage','?')} | Target: {drug_row.get('target','?')}")
    elif rtype == "fuzzy_match":
        print(f"  ⚠️  Fuzzy match: '{drug_row.get('name', '')}' (id: {drug_id}, similarity: {resolution['match_score']:.0%})")
        print(f"     Proceeding as existing drug — use --force to confirm override")
    elif rtype == "ambiguous":
        print(f"  ⚠️  Ambiguous — multiple possible matches:")
        for c in resolution.get("candidates", [])[:3]:
            print(f"     • {c.get('name')} ({c.get('id')}) — {c.get('stage','?')} / {c.get('target','?')}")
        if not force:
            print(f"  Use --force to proceed as candidate_new, or use a more specific drug name.")
            return
        drug_id = None
        print(f"  --force: treating as candidate_new")
    else:
        print(f"  ℹ️  New drug candidate: '{drug_name}' — not found in Meridian")
        if company_hint:
            print(f"     Company hint: {company_hint}")

    company_id = drug_row.get("company_id") or company_hint

    # ── Step 2: Fetch current graph state ────────────────────────────────────
    print("\n[2/5] Fetching current graph state...")
    graph_state = fetch_graph_state(drug_id, company_id)

    if verbose:
        mi    = graph_state["molecule_intelligence"]
        trials = graph_state["trials"]
        cats  = graph_state["catalysts"]
        sigs  = graph_state["signals"]
        das   = graph_state["drug_area_scores"]
        print(f"  Molecule Intel:  {'✅ exists' if mi else '⚠️  missing'}")
        print(f"  Trials:          {len(trials)} row(s)")
        print(f"  Catalysts:       {len(cats)} upcoming row(s)")
        print(f"  Signals:         {len(sigs)} (last 90 days)")
        print(f"  Drug Area Scores: {len(das)} row(s)")
    else:
        has_mi = "✅" if graph_state["molecule_intelligence"] else "⚠️"
        print(f"  {has_mi} MI | {len(graph_state['trials'])} trials | {len(graph_state['catalysts'])} catalysts | {len(graph_state['signals'])} signals")

    # ── Step 3: Research ─────────────────────────────────────────────────────
    print(f"\n[3/5] Researching {drug_name}...")
    company_for_research = drug_row.get("company_id") or company_hint
    research = research_drug(drug_name, company_for_research, verbose=verbose)
    if not research:
        print("  ❌ Research failed. Cannot proceed.")
        return

    # ── Step 4: Score area relevance + evidence tier ─────────────────────────
    print("\n[4/5] Scoring area relevance and evidence tier...")
    relevant_areas = get_relevant_areas(research, area_filter)
    evidence_tier  = compute_evidence_tier(research)

    if not relevant_areas:
        if area_filter:
            print(f"  {area_filter} area does not meet the minimum evidence threshold for '{drug_name}'.")
        else:
            print(f"  No areas meet minimum evidence threshold.")
            print(f"  This drug may not be in scope for active Meridian areas.")
    else:
        for area in relevant_areas:
            print(f"  • {area['area_id']:<8} {area['relevance']:<15} confidence={area['confidence']:.0%}")

    tier_icon = {"Confirmed": "✅", "Likely": "🟡", "Emerging": "🟠", "Hypothesis": "🔴"}.get(evidence_tier["tier"], "")
    print(f"  {tier_icon} Evidence tier: {evidence_tier['tier']}")
    if evidence_tier["tier"] == "Hypothesis" and not dry_run:
        print(f"\n  🔴 Hypothesis-tier drug: no production drug row will be created without manual approval.")
        print(f"     Queue row will be written as a reviewable signal with status=pending.")

    # ── Combo component check ─────────────────────────────────────────────────
    combo_warnings = []
    if relevant_areas and drug_row:
        area_ids_for_combo = [a["area_id"] for a in relevant_areas]
        combo_warnings = check_combo_components(drug_id, drug_name, drug_row, area_ids_for_combo, verbose=verbose)
        if combo_warnings:
            print(f"\n  ⚠️  Combo component gaps detected ({len(combo_warnings)}):")
            for w in combo_warnings:
                print(f"     {w['component']} / {w['area_id']}: {w['issue']}")

    # ── Step 5: Compute coverage + write queue rows ───────────────────────────
    print("\n[5/5] Computing coverage score and writing queue row(s)...")
    coverage = compute_coverage_score(resolution, graph_state, research)
    print(f"  Coverage: {coverage['coverage_score']}%")

    written      = []
    area_scores  = []
    if relevant_areas:
        written, area_scores = write_drug_queue_rows(
            drug_name      = drug_name,
            drug_id        = drug_id,
            company_id     = company_id,
            resolution     = resolution,
            research       = research,
            relevant_areas = relevant_areas,
            coverage       = coverage,
            evidence_tier  = evidence_tier,
            graph_state    = graph_state,
            run_id         = run_id,
            dry_run        = dry_run,
        )

    # ── Outputs ───────────────────────────────────────────────────────────────
    _print_routing_decision(drug_name, research, relevant_areas, resolution,
                            evidence_tier=evidence_tier, combo_warnings=combo_warnings,
                            area_scores=area_scores)
    _print_completeness_audit(drug_name, coverage, research, graph_state)

    if written and not dry_run:
        print(f"\n  {len(written)} row(s) written to discovery_queue (source=drug_intake, status=pending)")
        print("  → Review in Meridian Dashboard → Discovery Queue tab")
    elif written and dry_run:
        print(f"\n  [DRY RUN] {len(written)} row(s) would be written.")
    elif not relevant_areas:
        print(f"\n  No queue rows written (no areas meet threshold).")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Drug-First Discovery Engine — Meridian Drug Intake CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/drug_intake.py --drug "Tozorakimab"
  python scripts/drug_intake.py --drug "Amlitelimab" --area il4ra
  python scripts/drug_intake.py --drug "QX031N" --company "Qyuns" --dry-run
  python scripts/drug_intake.py --drug "Tozorakimab" --dry-run --verbose
        """,
    )
    parser.add_argument("--drug",    required=True,  help="Drug name to research")
    parser.add_argument("--company", default=None,   help="Company hint (helps for unknown drugs)")
    parser.add_argument("--area",    default=None,   choices=list(ACTIVE_AREAS.keys()), help="Constrain scoring to one area")
    parser.add_argument("--dry-run", action="store_true", help="Research but do not write to Supabase")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--force",   action="store_true", help="Force proceed past ambiguous identity or existing drug")

    args = parser.parse_args()

    run_drug_intake(
        drug_name    = args.drug,
        company_hint = args.company,
        area_filter  = args.area,
        dry_run      = args.dry_run,
        verbose      = args.verbose,
        force        = args.force,
    )
