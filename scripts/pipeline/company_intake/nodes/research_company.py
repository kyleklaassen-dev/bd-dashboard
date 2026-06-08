"""
Node: research_company
Open-ended Claude research call — the same prompt drives both modes:
  mode="intake"  → Step [2/4]: discover the company across all active areas
  mode="reaudit" → Step [3/4]: refresh the live pipeline to diff against the DB
"""
from __future__ import annotations

import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_NODES    = os.path.dirname(_HERE)
_PIPELINE = os.path.dirname(_NODES)
_SCRIPTS  = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import ai.client as ai_client                 # noqa: E402
from ai.client import PromptConfig             # noqa: E402

from pipeline.company_intake.state import IntakeState     # noqa: E402
from pipeline.company_intake.nodes.model_guard import active_model  # noqa: E402

# ── Active Meridian areas (shared with score_areas / company_intake.py CLI) ──

ACTIVE_AREAS = {
    "tl1a":   {
        "label":    "TL1A × IBD",
        "keywords": ["TL1A", "TNF-like ligand 1A", "DR3", "IBD", "Crohn", "ulcerative colitis", "UC", "CD"],
    },
    "tslp":   {
        "label":    "TSLP × Respiratory",
        "keywords": ["TSLP", "thymic stromal lymphopoietin", "asthma", "COPD", "atopic", "eosinophil"],
    },
    "il4ra":  {
        "label":    "IL-4Rα × Atopy",
        "keywords": ["IL-4R", "IL-4Rα", "IL4", "dupilumab", "atopic dermatitis", "AD", "asthma", "CRSwNP"],
    },
    "fcrn":   {
        "label":    "FcRn × Autoimmune",
        "keywords": ["FcRn", "neonatal Fc receptor", "IgG", "autoimmune", "gMG", "ITP", "pemphigus", "HDFN", "nipocalimab", "rozanolixizumab", "efgartigimod"],
    },
    "igf1r":  {
        "label":    "IGF-1R × Thyroid Eye",
        "keywords": ["IGF-1R", "IGF1R", "TSH receptor", "TSHR", "thyroid eye disease", "TED", "Graves", "teprotumumab"],
    },
    "tcell":  {
        "label":    "T-cell Engineering × Autoimmune",
        "keywords": ["CAR-T", "T cell", "TCR", "BCMA", "CD19", "autoimmune", "cell therapy", "ACE", "CAR"],
    },
}

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

_RESEARCH_CFG = PromptConfig(
    name="company_intake_research",
    system="",
    model="claude-sonnet-4-6",
    max_tokens=8192,
)


def research_company(company_name: str, verbose: bool = False) -> dict | None:
    """
    Call Claude to research the company open-endedly across all active areas.
    Returns parsed JSON dict or None on failure.
    """
    prompt = RESEARCH_PROMPT.format(company_name=company_name)
    _model = active_model()

    if verbose:
        print(f"  → Calling Claude ({_model}) for open-ended research on '{company_name}'...")

    result = ai_client.run_json(_RESEARCH_CFG.override(model=_model), prompt)
    if not result.ok:
        print(f"  ❌ Research call failed or returned unparseable JSON")
        if result.raw_text:
            print(f"  Raw response (first 500 chars): {result.raw_text[:500]}")
        return None

    data = result.data
    if verbose:
        print(f"  → Research complete. Pipeline: {len(data.get('pipeline', []))} drugs, "
              f"Deals: {len(data.get('deals', []))} entries.")
    return data


def research_company_node(state: IntakeState) -> IntakeState:
    """
    Run Step [2/4] (intake) or [3/4] (reaudit) — open-ended Claude research.
    Sets state.research; aborts on failure.
    """
    if state.mode == "reaudit":
        print("\n[3/4] Researching live pipeline via Claude...")
    else:
        print("\n[2/4] Researching company across all Meridian areas...")

    state.research = research_company(state.company_name, verbose=state.verbose)

    if not state.research:
        if state.mode == "reaudit":
            print("  ❌ Research failed.")
        else:
            print("  ❌ Research failed. Cannot proceed.")
        state.abort("research_failed")
        state.mark_complete("research_company")
        return state

    if state.mode == "reaudit":
        pipeline = state.research.get("pipeline", [])
        print(f"  Pipeline found: {len(pipeline)} drug(s)")
        if state.verbose:
            for d in pipeline:
                print(f"    • {d.get('drug_name', '?'):35} {d.get('stage', '?'):12} {d.get('target', '?')}")

    state.mark_complete("research_company")
    return state
