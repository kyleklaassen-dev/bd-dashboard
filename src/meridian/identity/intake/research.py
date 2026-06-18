#!/usr/bin/env python3
"""Identity resolution + company research (§3 company_intake split)."""

from __future__ import annotations

import json

from meridian.identity.company_identity_resolver import CompanyIdentityResolver
from meridian.identity.intake.common import _get_ai, ACTIVE_AREAS, SUPABASE_URL, SUPABASE_KEY
import os


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — IDENTITY RESOLUTION
# ══════════════════════════════════════════════════════════════════════════════

def resolve_identity(company_name: str, dry_run: bool = False) -> dict:
    """Resolve company name using CompanyIdentityResolver."""
    resolver = CompanyIdentityResolver(SUPABASE_URL, SUPABASE_KEY, dry_run=dry_run)
    result = resolver.resolve_with_detail(company_name, source="company_intake")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — OPEN-ENDED COMPANY RESEARCH
# ══════════════════════════════════════════════════════════════════════════════

RESEARCH_PROMPT = """You are a pharmaceutical competitive intelligence analyst.

Research the company: **{company_name}**

Your task is OPEN-ENDED DISCOVERY — do not assume any specific area of focus.
Research this company comprehensively across all biopharma/pharma activity.

Return a JSON object with this exact structure:

{{
  "company": {{
    "canonical_name": "string — official full company name",
    "short_name": "string — common short name / ticker name",
    "ticker": "string or null — stock ticker if public",
    "exchange": "string or null — NYSE/NASDAQ/HKEX/etc.",
    "geography": "string — primary HQ country",
    "company_type": "string — large_cap|mid_cap|small_cap|biotech|startup|private",
    "founded": "string or null — founding year",
    "website": "string or null",
    "tagline": "string — 1-sentence summary of what the company does"
  }},
  "pipeline": [
    {{
      "drug_name": "string — INN or code name",
      "brand_name": "string or null",
      "target": "string — molecular target(s)",
      "mechanism": "string — MoA",
      "modality": "string — mAb|bispecific|ADC|small molecule|cell therapy|etc.",
      "indication": "string — primary indication(s)",
      "stage": "string — Preclinical|Phase 1|Phase 2|Phase 3|Approved|Terminated",
      "nct_ids": ["string"],
      "partner": "string or null — licensor/licensee if applicable",
      "evidence_note": "string — brief citation or evidence summary"
    }}
  ],
  "deals": [
    {{
      "date": "string — YYYY or YYYY-MM",
      "type": "string — licensing|acquisition|collaboration|co-development|etc.",
      "partner": "string — other company",
      "asset": "string — drug or platform",
      "value": "string or null — deal value if disclosed",
      "description": "string — 1-2 sentence summary"
    }}
  ],
  "area_assessment": {{
    "tl1a":  {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "tslp":  {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "il4ra": {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "fcrn":  {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "igf1r": {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}},
    "tcell": {{"relevance": "Direct|Adjacent|Same-patient|Watchlist|Not relevant", "rationale": "string", "confidence": 0.0, "evidence": "string"}}
  }},
  "summary": "string — 2-3 sentences on what this company does and why it matters to a TL1A/FcRn/IL-4Rα IBD/autoimmune BD analyst",
  "data_quality": "string — high|medium|low — how much verified public information is available",
  "why_relevant": "string or null — if any area is Direct/Adjacent, explain the key BD angle in 1-2 sentences"
}}

Area definitions for scoring:
- TL1A/IBD: TL1A inhibitors, IL-23 inhibitors in IBD, IL-12/23, integrin inhibitors (IBD indication specifically), JAK inhibitors in IBD
- TSLP/Respiratory: TSLP inhibitors, IL-33, IL-4/13 in asthma, anti-eosinophil biologics (mepolizumab/benralizumab class)
- IL-4Rα/Atopy: IL-4Rα inhibitors, IL-13, IL-31, TSLP in atopic dermatitis, TARC pathway in AD
- FcRn/Autoimmune: FcRn inhibitors for IgG-mediated diseases (gMG, ITP, pemphigus, HDFN, SLE, MN)
- IGF-1R/Thyroid Eye: IGF-1R inhibitors or TSH receptor antibodies in TED or Graves disease
- T-cell/Autoimmune Cell Therapy: CAR-T, TCR-T, CAR-Treg, or related cell therapies for autoimmune indications

For confidence: 0.9–1.0 = clinical evidence in the area; 0.6–0.9 = preclinical or platform; 0.3–0.6 = platform company, possible indication; <0.3 = speculative

IMPORTANT:
- If you have limited information on this company, say so in data_quality and be conservative in scoring
- Do NOT fabricate clinical trial NCT IDs — leave nct_ids empty if unknown
- It is fine for most areas to be "Not relevant" — only score areas where real evidence exists
- Return ONLY the JSON object, no prose before or after

Company to research: {company_name}
"""

def research_company(company_name: str, verbose: bool = False) -> dict | None:
    """
    Call Claude to research the company open-endedly across all active areas.
    Returns parsed JSON dict or None on failure.
    """
    prompt = RESEARCH_PROMPT.format(company_name=company_name)

    # Model selection: use env var override for fast validation, default to sonnet for production
    _model = os.environ.get("INTAKE_MODEL", "claude-sonnet-4-6")

    if verbose:
        print(f"  → Calling Claude ({_model}) for open-ended research on '{company_name}'...")

    try:
        resp = _get_ai().messages.create(
            model=_model,
            max_tokens=8192,
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
            print(f"  → Research complete. Pipeline: {len(data.get('pipeline', []))} drugs, "
                  f"Deals: {len(data.get('deals', []))} entries.")
        return data

    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON parse error: {e}")
        print(f"  Raw response (first 500 chars): {raw[:500]}")
        return None
    except Exception as e:
        print(f"  ❌ Research call failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — AREA RELEVANCE FILTERING
# ══════════════════════════════════════════════════════════════════════════════

# Minimum evidence thresholds before writing a queue row
_RELEVANCE_INCLUDE = {"Direct", "Adjacent", "Same-patient"}
_RELEVANCE_WATCHLIST_MIN_CONFIDENCE = 0.6   # watchlist only if high-confidence
_MIN_CONFIDENCE = 0.5                        # skip any area below this

def _has_minimum_evidence(research: dict, area_id: str) -> bool:
    """
    Check if there's at least one molecule OR one clinical program found.
    Prevents writing queue rows for pure speculation.
    """
    pipeline = research.get("pipeline", [])
    if not pipeline:
        # No drugs found — only allow if company itself is in the area (strategic watchlist)
        area_data = research.get("area_assessment", {}).get(area_id, {})
        if area_data.get("relevance") == "Direct" and area_data.get("confidence", 0) >= 0.7:
            return True
        return False
    return True


def get_relevant_areas(research: dict) -> list[dict]:
    """
    Extract areas that meet the minimum evidence + confidence thresholds.
    Returns list of dicts with area_id, relevance, confidence, rationale, evidence.
    """
    assessment = research.get("area_assessment", {})
    result = []

    for area_id, area_info in assessment.items():
        if area_id not in ACTIVE_AREAS:
            continue

        relevance   = area_info.get("relevance", "Not relevant")
        confidence  = float(area_info.get("confidence", 0))
        rationale   = area_info.get("rationale", "")
        evidence    = area_info.get("evidence", "")

        # Skip non-relevant
        if relevance == "Not relevant":
            continue

        # Watchlist needs high confidence
        if relevance == "Watchlist" and confidence < _RELEVANCE_WATCHLIST_MIN_CONFIDENCE:
            continue

        # Minimum confidence floor
        if confidence < _MIN_CONFIDENCE:
            continue

        # Minimum evidence check
        if not _has_minimum_evidence(research, area_id):
            continue

        result.append({
            "area_id":    area_id,
            "area_label": ACTIVE_AREAS[area_id]["label"],
            "relevance":  relevance,
            "confidence": confidence,
            "rationale":  rationale,
            "evidence":   evidence,
        })

    # Sort: Direct first, then Adjacent, then Same-patient, then Watchlist
    _order = {"Direct": 0, "Adjacent": 1, "Same-patient": 2, "Watchlist": 3}
    result.sort(key=lambda x: (_order.get(x["relevance"], 9), -x["confidence"]))
    return result
