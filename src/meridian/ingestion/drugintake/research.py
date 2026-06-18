#!/usr/bin/env python3
"""Drug identity resolution + research (§3 drug_intake split)."""

import json
import difflib
from datetime import datetime, timezone, timedelta

import requests

from meridian.ingestion.drugintake.common import _get_ai, ACTIVE_AREAS, _sb_headers, SUPABASE_URL, SUPABASE_KEY
import os


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
