"""
Node: gather_web_intel
Phase A of Step 5 — runs 4 live web searches via Claude to collect clinical data,
financing, BD activity, and catalyst timing for the company.

Self-contained — no dependency on company_enrichment.py.
"""
from __future__ import annotations

import datetime
import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_PIPELINE = os.path.dirname(_HERE)
_SCRIPTS  = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import ai.client as ai_client                            # noqa: E402
import ai.prompts.company_intel_search as _p_intel       # noqa: E402
from _common import log                                   # noqa: E402
from pipeline.state import PipelineState                  # noqa: E402


# ── Area label map ────────────────────────────────────────────────────────────
# Maps area_id → human-readable competitive context for web search queries.

AREA_LABELS_MAP: dict[str, str] = {
    # Monospecifics — include indication + patient population context
    "tl1a": (
        "TL1A (anti-TL1A antibodies, IBD — UC/CD). "
        "ALSO include: IL-23 inhibitors, IL-23+TNF combo programs (e.g. VEGA/DUET), "
        "JAK inhibitors, and integrin inhibitors with active Phase 2+ IBD programs. "
        "These compete for the same biologic-naive and biologic-experienced UC/CD patients."
    ),
    "tslp": (
        "TSLP (anti-TSLP antibodies, severe asthma/atopic disease). "
        "ALSO include: IL-33, IL-25/TSLP pathway inhibitors, and companies with "
        "active Phase 2+ programs in severe asthma, CRSwNP, or atopic dermatitis "
        "that compete in the same patient population."
    ),
    "il4ra": (
        "IL-4Rα (anti-IL-4Rα or IL-4/IL-13 pathway, atopic dermatitis/asthma). "
        "ALSO include: OX40/OX40L inhibitors, IL-13 inhibitors, IL-31 inhibitors, "
        "and any company with active Phase 2+ programs in moderate-to-severe AD "
        "competing against dupilumab-class agents."
    ),
    "igf1r": (
        "IGF1R (anti-IGF1R, thyroid eye disease / oncology). "
        "ALSO include: TSHR-targeting programs, TSH receptor antibody-targeting approaches, "
        "and any Phase 2+ programs in thyroid eye disease (TED/Graves' orbitopathy)."
    ),
    "fcrn": (
        "FcRn (anti-FcRn, autoimmune/IgG-mediated disease). "
        "ALSO include: programs for CIDP, myasthenia gravis, ITP, pemphigus, NMOSD, "
        "lupus nephritis, and other IgG-mediated autoimmune diseases where FcRn "
        "inhibition or IgG reduction is the mechanism."
    ),
    "tcell": (
        "T-cell engagers / bispecific T-cell redirectors (oncology — hematologic malignancies). "
        "ALSO include: CAR-T programs, CD19/CD20/BCMA-targeted bispecifics, and "
        "any Phase 1+ programs in B-cell malignancies, multiple myeloma, or "
        "autoimmune disease using T-cell redirection."
    ),
    # Bispecifics
    "il4ra_tslp":  "IL-4Rα×TSLP bispecific (atopic dermatitis/asthma)",
    "il4ra_ox40l": "IL-4Rα×OX40L bispecific (atopic dermatitis/asthma)",
    "igf1r_tshr":  "IGF1R×TSHR bispecific (thyroid eye disease / oncology)",
    # Other
    "ace":  "ACE2-based programs (respiratory/cardiometabolic)",
    # Broad groupings (used as indication_group fallback)
    "ibd":    "IBD (inflammatory bowel disease — UC/CD)",
    "atopic": "Atopic disease (AD, asthma, EoE)",
}


# ── Core logic ────────────────────────────────────────────────────────────────

def gather_web_intelligence(company_name: str, area_id: str,
                             drugs: list, ticker: str = "") -> str:
    """
    Phase A of Step 5: use Claude with web_search to gather live intelligence.

    Runs 4 targeted searches:
      1. Clinical data — trial results, efficacy endpoints, conference readouts
      2. Financing — funding rounds, investors, cash runway, IPO/SPAC details
      3. BD activity — partnerships, licensing deals, M&A, collaborations
      4. Catalyst timeline — company-guided data windows, PDUFA dates, filings

    Returns a structured text block to inject into the Phase B enrichment prompt.
    Falls back to empty string on any failure (Phase B continues with Supabase context only).
    """
    area_label = AREA_LABELS_MAP.get(area_id, area_id)
    drug_names = ", ".join(d.get("name", "") for d in drugs[:4] if d.get("name"))
    ticker_str = f" (Ticker: {ticker})" if ticker and ticker.upper() not in ("PRIVATE", "N/A", "") else ""
    year = datetime.datetime.utcnow().year

    prompt = f"""Research {company_name}{ticker_str} for a competitive intelligence database.
Area of focus: {area_label}
Key programs to research: {drug_names or 'see company pipeline'}

Use web_search to find and extract SPECIFIC facts on all four topics:

TOPIC 1 — CLINICAL DATA (current AND historical)
Search for trial results across ALL phases — not just the most recent.
What endpoints did they hit? What were the response rates, p-values, or biomarker results?
Which conferences (ECCO, DDW, ACR, ASCO, NEJM, Lancet, NEJM Evidence)?
Any Phase 3 readouts, POC data, dose-selection results in the last 24 months?
CRITICAL: Also search for earlier Phase 1 and Phase 2 proof-of-concept or dose-finding trials that preceded the current Phase 3 program. These are often the scientific foundation for Phase 3 and may have published results (even if the trial completed 2-4 years ago). Search specifically for: "[drug name] Phase 1 results", "[drug name] Phase 2 results", "[drug name] proof of concept", "[drug name] dose escalation". A completed Phase 2b that missed its primary endpoint is MORE important to capture than a currently-recruiting Phase 3, because it carries the key risk data.

TOPIC 2 — FINANCING & COMPANY STATUS
All funding rounds with amounts, dates, and lead investors.
IPO, SPAC, or public listing details if applicable.
Current cash position or runway guidance if disclosed.
Key shareholders or strategic investors.

TOPIC 3 — BD ACTIVITY
Any licensing deals, partnerships, co-development agreements, M&A.
Deal terms where disclosed: upfront, milestones, royalties, geography.
Any stated partnering strategy or BD timeline guidance from management.

TOPIC 4 — CATALYST TIMELINE
Company-guided data readout windows for each program.
Any upcoming PDUFA dates, regulatory filings, or NDA/BLA submissions.
Expected enrollment completion or primary completion dates from company guidance (not just CT.gov).

Search year range: {year - 1}–{year}.
Be specific. Extract actual numbers and dates. Indicate uncertainty where present."""

    result = ai_client.run_text(_p_intel.PROMPT_CFG, prompt, timeout=90.0)
    if result:
        usage = ai_client.token_usage()
        log(f"  Web search: {usage['in']}in / {usage['out']}out", indent=2)
    else:
        log("  Web search failed (non-fatal) — empty response", indent=2)
    return result


# ── Pipeline node ─────────────────────────────────────────────────────────────

def gather_web_intel(state: PipelineState) -> PipelineState:
    """
    Calls gather_web_intelligence() to produce a structured text block
    that is injected into the Phase B synthesis prompt.
    Returns empty string on any failure — Phase B continues without it.
    Populates state.web_intel.
    """
    co = state.ctx.company
    state.web_intel = gather_web_intelligence(
        company_name=co.get("name", state.company_id),
        area_id=state.area_id,
        drugs=state.ctx.drugs,
        ticker=co.get("ticker", ""),
    )
    state.mark_complete("gather_web_intel")
    return state
