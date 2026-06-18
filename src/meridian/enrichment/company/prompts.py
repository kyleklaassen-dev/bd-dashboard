#!/usr/bin/env python3
"""
Enrichment prompt construction (Step 5 — Company Enrichment).
============================================================
Extracted verbatim from company_enrichment.py (§3 large-file split).

Holds the prompt *configuration* for the Step-5 LLM enrichment call:
  - ENRICHMENT_SYSTEM        — the system prompt (data-quality contract)
  - load_enrichment_hints()  — flywheel: inject Kyle's confirmed ground-truth hints
  - enrichment_system_prompt() — system prompt + latest learned hints
  - AREA_DISEASE_CONTEXT     — per-area disease framing
  - build_step5_prompt()     — assembles the per-company user prompt

Pure prompt assembly — no Supabase I/O, no LLM calls, no writers. Response
parsing (parse_enrichment_response) and the writer (write_step5) stay in
company_enrichment.py.
"""

import os
import json
import datetime

TODAY = datetime.datetime.utcnow().strftime("%Y-%m-%d")

# repo root = four levels up from src/meridian/enrichment/company/ (this file's dir)
_THIS_DIR  = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_HINTS_PATH = os.path.join(_REPO_ROOT, "data", "enrichment_prompt_hints.md")
_ENRICHMENT_HINTS_CACHE = None  # lazily loaded, then memoized for the process


ENRICHMENT_SYSTEM = """You are a senior biopharma business development analyst for Ailux Biotherapeutics,
a biotech developing a TL1A×IL-23p19 bispecific antibody for IBD. You synthesize clinical, competitive,
and BD intelligence into structured data that powers a live competitive tracking dashboard.

KEY CONTEXT: Ailux's lead asset is a TL1A×IL-23p19 bispecific for UC/CD.
Primary BD goal: identify the right pharma partner — timing, deal structure, positioning.

OUTPUT RULES:
- Narrative text fields: 2-4 concise, dense sentences. No bullets. No markdown.
- BD Summary: financing, deal history, partnering strategy, cash runway, BD timing windows.
- Key Risk: the SINGLE most important risk specific to THIS company's program.
- vs_ailux: how this company/drug compares to Ailux — mechanism, stage, format, differentiation.
- Do not fabricate. If uncertain, use "expected", "anticipated", "estimated".
- Return ONLY valid JSON — no markdown fences, no explanation.

DATA QUALITY STANDARDS (mandatory — these prevent downstream display errors):

TARGET NOTATION (CRITICAL — target field must be targets ONLY, never include company or modality annotations):
- IL-23 inhibitors: ALWAYS specify "IL-23p19" (not "IL-23" alone). The p19 subunit is the
  specific target of all modern IL-23 inhibitors. IL-23p40 inhibitors are a different class.
- Bispecifics use "×" separator: "TL1A × IL-23p19" (NOT "TL1A/IL-23" or "anti-TL1A × IL-23")
- Rational combinations (two separate co-administered mAbs) use "+" separator: "IL-23p19 + TL1A"
- Monospecific mAbs: do NOT prefix with "Anti-" in the target field (use in mechanism field only)
- NEVER include modality labels in target: NOT "TL1A × IL-23p19 bispecific" — just "TL1A × IL-23p19"
- NEVER include company annotations in target: NOT "IL-23p40 × TL1A bispecific, Roche/Pfizer co-dev"
  The dashboard will display the "bispecific" modality from drug_format and the partner from partner_company.
  Target field = molecular targets only.

MECHANISM ↔ TARGET CONSISTENCY (CRITICAL — prevents the most damaging error class):
The `mechanism` text MUST describe the EXACT target named in the `target` field. The cytokine /
receptor / antigen in the mechanism must match `target`. The `target` field is the source of truth.
- NEVER default a drug's mechanism to a "TL1A / IL-23p19" description just because TL1A×IL-23 is
  Ailux's focus. MOST catalog drugs target OTHER pathways (IL-4Rα, TSLP, FcRn, CD19/BCMA, CD40L, …).
- Before writing mechanism, re-read the target field: if target = "IL-4Rα × TSLP", the mechanism is
  about IL-4/IL-13 and TSLP alarmin signaling — NOT TL1A/DR3. If target = "CD19 × BCMA × CD3", the
  mechanism is a T-cell engager — NOT FcRn.
- If you do not know the true mechanism, write a short target-consistent stub rather than inventing a
  TL1A/IL-23/FcRn description. A sparse-but-correct mechanism beats a confident wrong one.
(Audit 2026-06-05 found IBI3002, bosakitug, CND319/CND460, shr0817/hlx36 with mechanism text copied
from unrelated TL1A/IL-23/FcRn drugs — this rule exists to stop that.)

CO-DEVELOPMENT PARTNERSHIP DETECTION:
If you see text like "Company/Company co-dev" or "co-developed with Company" anywhere in the literature:
1. Extract the partner company name and put it in partner_company
2. Set partnership_type = "co_developed"
3. Set partnership_verified = false (mark as inferred — needs confirmation from official source)
4. Leave it OUT of the target field entirely
Confirmed co-development vs. inferred: only set partnership_verified = true when you find an explicit
official press release, ClinicalTrials.gov sponsor field, or SEC filing confirming the partnership.
If the partnership is from secondary sources (news articles, databases), set partnership_verified = false.

DRUG NAME FORMAT:
- If a drug has an approved brand name (e.g., Skyrizi, Rinvoq, Entyvio):
  → name field = "BrandName (INN)" e.g. "Skyrizi (Risankizumab)"
  → The pill will show "BrandName" — do NOT use the numbered code (e.g. NOT "BI 765063")
- If a drug has INN but no brand name: name field = "INN (NumberCode)" if code is meaningful,
  otherwise just "INN" (e.g. "Afimkibart" not "Afimkibart (RO7790121)")
- If only a code name exists (no INN yet): use code name (e.g. "XmAb942", "SPY002")

PCD / DATE GRANULARITY:
- Primary completion dates must include the SPECIFIC DAY when known: "April 28, 2028" NOT "Apr 2028"
- For catalyst dates where only month/quarter is known, use "Q3 2026" or "H2 2026" — never just a year
- Always pull PCD from the actual CT.gov filing (primary_completion_date) — include the day

VALIDATED REFERENCES:
- Every catalyst must include a source_url (CT.gov NCT link, press release, SEC filing, or company IR)
- Every deal must include a source_url — at minimum the company press release or SEC 8-K
- Every news item / recent development should reference its source
- Do not fabricate URLs. If you cannot find a verified URL, omit the field rather than guess.

CHINA CDE AWARENESS:
- Many China-based programs are registered on China's Clinical Trial Registry (www.chinadrugtrials.org.cn)
  but NOT on CT.gov. When researching Chinese biotech or programs with China CDE registry entries,
  note this explicitly in mechanism_detail (e.g., "Phase 1 registered on China CDE registry; NCT pending").

GOVERNANCE RULES (mandatory — violations cause downstream data integrity errors):

1. ATTRIBUTION: drugs.company_id = ORIGINATOR ALWAYS. Never set company_id to a licensee.
   Licensee relationships belong in company_partnerships / deals tables only.
   Full effective pipeline = drugs.company_id + company_partnerships join (see licensing_attribution governance).
   Canonical: ABBV-701.company_id = 'futuregen' (originator). AbbVie appears via partnership row.

2. COMPANY STATUS: Default to status='subsidiary' for all recent acquisitions.
   Only set status='acquired' when the company has provably dissolved (no independent website, pipeline,
   or leadership). Require parent_company_id for both subsidiary and acquired.
   Canonical: Blueprint Medicines = subsidiary (active website, named CSO). Prometheus = acquired (dissolved into Merck).

3. CO-DEV ATTRIBUTION: If a drug has multiple companies involved (co-development), set:
   - partner_company = co-developer name
   - partnership_type = "co_developed"
   - partnership_verified = false (until press release or CT.gov sponsor field confirms)
   Do NOT change company_id. Do NOT embed partner name in the target field.
   Both companies must show the drug in their pipeline view via co_developer_ids[].

4. BRAND NAME IMPLIES APPROVED: Any drug with a brand_name MUST have stage = 'approved' (or
   approved_us / approved_eu / approved_china / approved_us_eu / approved_partial).
   If you write a brand_name for a drug, simultaneously set stage to the appropriate approved variant.
   A dash "—" is NOT a valid brand_name — clear it to null.

5. SOURCE REQUIRED: Never write a co-developer, partner company name, or licensing deal without
   including a source_url (CT.gov NCT link, press release, SEC 8-K, or company IR page).
   Do not fabricate URLs. If no URL can be confirmed, set partnership_verified = false and
   note the source in source_notes. Omit source_url entirely rather than guess.

6. DEAL SEQUENCING: Before rating a company as a BD target for any Ailux asset, check whether
   they have an existing asset in the same mechanism with a readout expected in <18 months.
   If so, they will not acquire a redundant asset before seeing their own data — downgrade from
   "call now" and add a timing_note. Canonical constraint: AbbVie cannot be targeted for any
   TL1A bispecific until after ABBV-701 Phase 1 readout (expected Oct 2026).

SOURCE TRACEABILITY (mandatory for every drug and deal record you write):

Every claim you write to the database must have at least one source URL. This is how the
platform detects hallucinations and errors. For each drug INSERT or UPDATE, you MUST also
write at least one row to the drug_sources table using this structure:

  {
    "drug_id": "<drug_id>",
    "drug_name": "<drug_name>",
    "claim_type": "<stage|approval|mechanism|brand_name|company|indication|trial_registration|deal|partnership>",
    "claim_value": "<the value being sourced, e.g. 'Phase 3' or 'tulisokibart'>",
    "source_url": "<actual URL>",
    "source_type": "<clinicaltrials|fda_label|press_release|sec_filing|pubmed|company_website|ema_label|who_inn|news>",
    "source_domain": "<domain extracted from URL>",
    "content_confirms_claim": true,
    "confidence": "<high|medium|low>",
    "added_by": "enrichment",
    "session_label": "<area>_<YYYY-MM-DD>"
  }

Accepted source URL types (in order of preference):
  1. ClinicalTrials.gov NCT links: https://clinicaltrials.gov/study/NCT########
  2. FDA press announcements: https://www.fda.gov/news-events/press-announcements/...
  3. EMA approval decisions: https://www.ema.europa.eu/...
  4. Company IR press releases: company investor relations pages
  5. SEC 8-K filings: https://www.sec.gov/...
  6. PubMed abstracts: https://pubmed.ncbi.nlm.nih.gov/<PMID>/

Rules:
- If you cannot find a real URL for a claim, set claim_type='unverified' and omit source_url.
  Do NOT fabricate URLs. A missing source is less harmful than a hallucinated one.
- For stage claims: CT.gov NCT link is the gold standard. Always prefer it.
- For approval claims: FDA press announcement or EMA approval decision is required.
- For deal/partnership claims: press release or SEC 8-K is required.
- NCT numbers must be exactly 8 digits (e.g. NCT06197581). Reject any shorter/longer NCTs.
- Every drug you enrich should have at minimum one source row for its most important claim
  (typically stage or approval).

FINE-TUNING FLYWHEEL — CONFIRMED EXAMPLES (100% acceptance rate from kyle_reviews, 2026-05-29):
These are real examples Kyle has confirmed as correct. Use them as style and quality guides.

EXAMPLE: drug_summary (confirmed as high quality)
  DRUG: duvakitug (TL1A mAb, Sanofi/Teva co-dev, Phase 3 IBD)
  GOOD: "Duvakitug is a human IgG1-λ2 anti-TL1A mAb co-developed with Teva (equal cost/profit share),
  delivering the highest Phase 2b efficacy in the TL1A class: 48% clinical remission in UC and 48%
  endoscopic improvement in CD. Phase 3 TUSCANY-3 (UC) and TUSCANY-4 (CD) ongoing, primary completion
  ~2027. Sets the monospecific TL1A efficacy ceiling against which bispecifics will be compared."
  WHY GOOD: Leads with mechanism + deal structure, includes specific Phase 2b numbers, names the trials,
  anchors BD implication in final sentence. Dense, factual, no filler.

EXAMPLE: ailux_angle (confirmed as high quality)
  DRUG: duvakitug
  GOOD: "Direct comparator; Sanofi/Teva's most advanced TL1A program. Ph3 readout will set class expectations."
  DRUG: veligrotug (Prometheus/Merck, acquired TL1A program)
  GOOD: "TUSCANY-2 Phase 2b SUCCESS triggered $7.1B Roche acquisition — strongest validation of TL1A
  mechanism to date. Phase 3 (2027 readout) will set the efficacy ceiling for the class."
  DRUG: elegrobart (IGF-1R, Viridian)
  GOOD: "Biggest near-term threat to Tepezza class: SC self-administration + favorable safety profile.
  Phase 3 success makes elegrobart the likely BLA-stage competitor in 2027."
  WHY GOOD: Concise (≤2 sentences). BD-specific framing. Links the drug to Ailux's strategic position.
  Includes timing. Uses specific deal values when available. No speculation beyond what's implied by facts.

EXAMPLE: differentiation_thesis (confirmed as high quality)
  DRUG: abatacept (T-cell costimulation inhibitor)
  GOOD: "T-cell costimulation modulation; ~3d half-life; Q2W dosing"
  DRUG: ozanimod (S1P modulator)
  GOOD: "Potential fibrosis modification; upstream T-cell amplification control; ~7-10d half-life; Q4W"
  DRUG: elegrobart (IGF-1R SC autoinjector)
  GOOD: "SC autoinjector → at-home dosing; same IGF-1R mechanism as Tepezza but avoids infusion center; BLA Q1 2027"
  WHY GOOD: 3-5 tightly packed facts separated by semicolons. Never repeats drug_summary. Focuses on
  what makes the MOLECULE distinct (format, half-life, dosing schedule, engineering choice, route of admin)."""


# ── Flywheel close: inject confirmed-ground-truth quality hints at runtime ─────
# apply_prompt_improvements.py reads Kyle's confirmed examples (training_pairs_*.jsonl)
# and writes data/enrichment_prompt_hints.md. This loader pulls that guidance into the
# live ENRICHMENT_SYSTEM prompt so the next enrichment run benefits from the latest
# confirmed signal. This is the step that was previously missing — the hints file was
# generated but never consumed at enrichment time.


def load_enrichment_hints() -> str:
    """Return the auto-generated quality-hints block (empty string if absent).

    Strips the file's own title/HTML-comment header and wraps the guidance in a
    clearly delimited section so it reads as an addendum to ENRICHMENT_SYSTEM.
    """
    global _ENRICHMENT_HINTS_CACHE
    if _ENRICHMENT_HINTS_CACHE is not None:
        return _ENRICHMENT_HINTS_CACHE
    block = ""
    try:
        if os.path.exists(_HINTS_PATH):
            raw = open(_HINTS_PATH, encoding="utf-8").read().strip()
            # Drop the auto-generated title line and the HTML comment marker.
            lines = [
                ln for ln in raw.splitlines()
                if not ln.startswith("# Enrichment Prompt Quality Hints")
                and not ln.strip().startswith("<!--")
            ]
            body = "\n".join(lines).strip()
            if body:
                block = (
                    "\n\n"
                    "LEARNED QUALITY GUIDANCE (auto-derived from Kyle's confirmed ground truth — "
                    "these reflect the length, structure, and content of values Kyle has personally "
                    "verified; match them closely):\n"
                    + body
                )
    except Exception:
        block = ""
    _ENRICHMENT_HINTS_CACHE = block
    return block


def enrichment_system_prompt() -> str:
    """ENRICHMENT_SYSTEM with the latest learned quality hints appended."""
    return ENRICHMENT_SYSTEM + load_enrichment_hints()


# ── Disease-area framing for area-aware assessment generation ─────────────────
# Maps area_id → (disease_label, ailux_in_area, bd_frame)
# ailux_in_area: True if Ailux directly competes in this area
# bd_frame: how to frame Ailux implications when NOT a direct competitor
AREA_DISEASE_CONTEXT = {
    "tl1a": {
        "disease": "IBD (UC/CD)",
        "ailux_in_area": True,
        "bd_frame": "direct competitor — assess mechanistic, clinical, and partnership threat to Ailux's TL1A×IL-23p19 bispecific program",
    },
    "ibd": {
        "disease": "IBD (UC/CD)",
        "ailux_in_area": True,
        "bd_frame": "direct competitor — assess mechanistic, clinical, and partnership threat to Ailux's TL1A×IL-23p19 bispecific program",
    },
    "igf1r": {
        "disease": "Thyroid Eye Disease (TED / Graves' orbitopathy)",
        "ailux_in_area": False,
        "bd_frame": "non-competing area — assess the company's TED franchise strength, then explain BD relevance to Ailux: valuation benchmarks set by anti-IGF1R deals, whether they are a potential partner/acquirer in the broader autoimmune space, or whether their clinical data informs Ailux's competitive landscape indirectly",
    },
    "igf1r_tshr": {
        "disease": "Thyroid Eye Disease (TED / Graves' orbitopathy)",
        "ailux_in_area": False,
        "bd_frame": "non-competing area — assess the company's TED franchise strength, then explain BD relevance to Ailux: valuation benchmarks set by anti-IGF1R deals, whether they are a potential partner/acquirer in the broader autoimmune space, or whether their clinical data informs Ailux's competitive landscape indirectly",
    },
    "tslp": {
        "disease": "Severe Asthma / Respiratory",
        "ailux_in_area": False,
        "bd_frame": "non-competing area — assess the company's respiratory franchise strength, then explain BD relevance to Ailux: deal structures and valuations that benchmark biologics in adjacent autoimmune markets, whether they are a potential BD partner or acquirer across their broader immunology portfolio",
    },
    "il4ra": {
        "disease": "Atopic Dermatitis / Atopic Disease",
        "ailux_in_area": False,
        "bd_frame": "non-competing area — assess the company's atopic disease franchise strength, then explain BD relevance to Ailux: deal benchmarks from the IL-4Rα/dupilumab competitive set, whether they are a potential BD partner in the broader autoimmune space",
    },
    "il4ra_tslp": {
        "disease": "Atopic Dermatitis / Atopic Disease",
        "ailux_in_area": False,
        "bd_frame": "non-competing area — assess the company's atopic disease franchise strength, then explain BD relevance to Ailux: deal benchmarks from IL-4Rα/dupilumab competitive set, partnering potential across immunology",
    },
    "fcrn": {
        "disease": "Autoimmune / IgG-mediated Disease (CIDP, MG, ITP, NMOSD, etc.)",
        "ailux_in_area": False,
        "bd_frame": "non-competing area — assess the company's FcRn/IgG-mediated disease franchise strength, then explain BD relevance to Ailux: deal structures and valuations for broad autoimmune platforms, whether they are a potential BD partner or acquirer",
    },
    "tcell": {
        "disease": "T-Cell Engagers / Oncology",
        "ailux_in_area": False,
        "bd_frame": "non-competing area — assess the company's T-cell engager/oncology franchise strength, then explain BD relevance to Ailux: whether they have a broader immunology BD mandate that might include IBD/autoimmune assets",
    },
}


def build_step5_prompt(company_id: str, area_id: str, ctx: dict,
                       web_intel: str = "") -> str:
    co        = ctx["company"]
    profile   = ctx["profile"]
    ailux_pos = ctx.get("ailux_pos", {})
    is_public = (co.get("ticker") or "").upper() not in ("PRIVATE", "", "N/A")

    drugs_text = json.dumps([{
        k: v for k, v in d.items()
        if k in ("id","name","mechanism","mechanism_detail","drug_summary","stage","stage_detail",
                 "key_data","route","dosing_type","drug_format","half_life_note","indication_short",
                 "target","cls","overlap","entity_type","aliases")
    } for d in ctx["drugs"]], indent=2)

    trials_text = json.dumps([{
        k: v for k, v in t.items()
        if k in ("id","trial_name","phase","status","indication","n_enrollment",
                 "primary_endpoint","pcd_label","primary_completion_date","sponsor",
                 "study_acronym")
    } for t in ctx["trials"][:12]], indent=2)

    existing_cats = json.dumps([{
        "date": c.get("catalyst_date"), "label": c.get("label"),
        "significance": c.get("significance"),
    } for c in ctx["catalysts"]], indent=2)

    existing_deals = json.dumps([{
        "date": d.get("deal_date_label"), "headline": d.get("headline"),
        "from": d.get("from_company"), "to": d.get("to_company"),
        "upfront": d.get("upfront_usd_m"), "total": d.get("total_usd_m"),
    } for d in ctx["deals"][:8]], indent=2)

    recent_intel = json.dumps([{
        "date": i.get("intel_date"),
        "headline": i.get("headline"),
        "body": (i.get("body") or "")[:300],
    } for i in ctx["recent_intel"][:6]], indent=2)

    current_profile = json.dumps({
        # Structured intelligence (primary) — shown so model can update/refine existing analysis
        "platform_intelligence": profile.get("platform_intelligence"),
        "bd_intelligence":       profile.get("bd_intelligence"),
        # Scalar fields
        "key_risk":         profile.get("key_risk", ""),
        "why_it_matters":   profile.get("why_it_matters", ""),
        "vs_ailux":         profile.get("vs_ailux", ""),
        # LEGACY TEXT — for context only; do NOT return platform_summary or bd_summary in output
        "_legacy_platform_summary": (profile.get("platform_summary") or "")[:400] or None,
        "_legacy_bd_summary":       (profile.get("bd_summary") or "")[:400] or None,
    }, indent=2)

    financial_fields = (
        '"market_cap_usd_m": null or number,'
        if is_public else
        '"cash_runway": "e.g. H2 2028 or null",'
        '"financing_history": [{"date": "YYYY-MM", "amount_usd_m": X, "series": "Series A", "investors": ["name"]}],'
        '"key_investors": ["name1", "name2"],'
    )

    # Build Ailux competitive anchor block — fetched from ailux_positions table.
    # This is the reference the LLM uses to classify every drug as Direct/Adjacent/Watch.
    # If no position row exists for this area, the block is omitted and the LLM uses
    # its own judgment (acceptable for new areas, but adding a row is strongly preferred).
    if ailux_pos:
        # Build same-space block only if the column exists in the row
        _ss_criteria = ailux_pos.get('same_space_criteria', '')
        _ss_examples = ailux_pos.get('same_space_examples', '')
        _same_space_block = (
            f"SAME-SPACE — {_ss_criteria}\n"
            f"  Examples: {_ss_examples}\n\n"
        ) if _ss_criteria else ""

        ailux_block = (
            "\nAILUX COMPETITIVE ANCHOR (read this before classifying any drug):\n"
            f"Ailux drug: {ailux_pos.get('ailux_drug','SPY002')} | "
            f"Targets: {ailux_pos.get('ailux_targets','')} | "
            f"Modality: {ailux_pos.get('ailux_modality','')} | "
            f"Stage: {ailux_pos.get('ailux_stage','')}\n"
            f"Ailux angle: {ailux_pos.get('ailux_angle','')}\n\n"
            "FOUR-TIER CLASSIFICATION RULES (apply to EVERY drug and combo you write):\n"
            f"DIRECT — {ailux_pos.get('direct_criteria','')}\n"
            f"  Examples: {ailux_pos.get('direct_examples','')}\n\n"
            f"ADJACENT — {ailux_pos.get('adjacent_criteria','')}\n"
            f"  Examples: {ailux_pos.get('adjacent_examples','')}\n\n"
            + _same_space_block +
            f"WATCH — {ailux_pos.get('watch_criteria','')}\n"
            f"  Examples: {ailux_pos.get('watch_examples','')}\n\n"
            f"NOTES: {ailux_pos.get('notes','')}\n"
        )
    else:
        ailux_block = (
            "\nNOTE: No ailux_positions row found for this area. "
            "Use your best judgment to classify overlap using this FOUR-TIER hierarchy:\n"
            "  DIRECT = same molecular target as Ailux, or combo that includes Ailux's primary target\n"
            "  ADJACENT = same disease/patient population with different mechanism that validates biology "
            "or is an explicit combination candidate (e.g. IL-23, α4β7 in IBD)\n"
            "  SAME-SPACE = approved SOC in the same disease area via a fundamentally different pathway "
            "(competes for patients, defines efficacy bar, but not a mechanistic threat)\n"
            "  WATCH = same patient population but entirely different mechanism (JAK, S1P, RIPK1, TNF), "
            "or early-stage with unconfirmed relevance to this area\n"
        )

    # Build web intelligence section separately to avoid f-string nesting issues
    if web_intel:
        web_intel_section = (
            "\nWEB INTELLIGENCE (live research - highest priority source):\n"
            + web_intel
            + "\n\nINSTRUCTION: Use WEB INTELLIGENCE as your primary source for clinical endpoints, "
            "financing amounts, deal terms, and catalyst timing. It contains current data retrieved "
            "directly from press releases, SEC filings, and company IR pages. Cross-reference with "
            "TRIALS/DEALS above; prefer web data where it is more specific or more recent.\n"
        )
    else:
        web_intel_section = ""

    # ── Area-specific framing block ─────────────────────────────────────────────
    # Tells the LLM which disease area this is and how to frame Ailux implications.
    # Prevents assessments from being anchored to IBD/TL1A on non-IBD tabs.
    _area_ctx = AREA_DISEASE_CONTEXT.get(area_id, {})
    _disease_label = _area_ctx.get("disease", area_id.upper())
    _ailux_in_area = _area_ctx.get("ailux_in_area", True)
    _bd_frame = _area_ctx.get("bd_frame", "assess competitive position and BD implications for Ailux")

    if _ailux_in_area:
        area_framing_block = (
            f"\nAREA FRAMING — {_disease_label}:\n"
            f"This is AILUX'S PRIMARY COMPETITIVE AREA. Ailux's TL1A×IL-23p19 bispecific (SPY002) "
            f"directly competes in {_disease_label}. Frame ALL assessments relative to how this company's "
            f"programs affect Ailux's competitive positioning, partner audience, and BD timing in this area.\n"
            f"  • platform_intelligence.assessment: What does this company's trajectory mean for Ailux's "
            f"position in {_disease_label}?\n"
            f"  • vs_ailux: Direct mechanism and stage comparison to SPY002 (TL1A×IL-23p19 bispecific).\n"
            f"  • why_it_matters: Why does this competitor matter to Ailux's BD strategy in {_disease_label}?\n"
        )
    else:
        area_framing_block = (
            f"\nAREA FRAMING — {_disease_label}:\n"
            f"THIS IS NOT AILUX'S PRIMARY COMPETITIVE AREA. Ailux does not have a program in {_disease_label}. "
            f"Do NOT frame assessments as if Ailux competes here. Instead, use a TWO-LAYER structure:\n"
            f"  LAYER 1 — Disease Assessment: Describe this company's competitive position, pipeline "
            f"strength, and strategic trajectory IN {_disease_label.upper()} specifically. "
            f"What is their franchise strategy, stage, and market position in this disease?\n"
            f"  LAYER 2 — Ailux Implications: {_bd_frame}.\n\n"
            f"IMPORTANT INSTRUCTION FOR NON-COMPETING AREAS:\n"
            f"  • platform_intelligence.assessment: '[ASSESSED] In {_disease_label}: [company's position]. "
            f"Ailux BD angle: [specific implication — benchmark, partner potential, cross-area signal].'\n"
            f"  • vs_ailux: Do NOT say 'no overlap' as the answer. Instead say: 'Not a direct competitor in "
            f"{_disease_label}; Ailux monitors [company] as [specific BD reason — acquirer, benchmark-setter, "
            f"cross-area BD signal].'\n"
            f"  • why_it_matters: Answer with a specific BD reason — not 'no overlap'. Examples: "
            f"'Sets $XM licensing benchmark for [mechanism] assets', 'Potential acquirer — broad immunology "
            f"mandate includes [area]', 'Clinical data validates [shared biology] relevant to Ailux'.\n"
        )

    return f"""Enrich company: {co.get('name', company_id)} (ID: {company_id})
Area: {area_id}  |  Public: {is_public}  |  Today: {TODAY}

CURRENT PROFILE:
{current_profile}

DRUGS:
{drugs_text}

TRIALS (from ClinicalTrials.gov — Step 3):
{trials_text}

EXISTING CATALYSTS:
{existing_cats}

EXISTING DEALS:
{existing_deals}

RECENT INTEL:
{recent_intel}
{web_intel_section}
{ailux_block}
{area_framing_block}
Return JSON with EXACTLY these fields:

⚠ CRITICAL SCHEMA REQUIREMENT:
- "platform_intelligence" and "bd_intelligence" are REQUIRED structured objects — NEVER return null for these.
- DO NOT return "platform_summary" or "bd_summary" as text strings — those fields are DEPRECATED. If you return them, they will be ignored. The only accepted format is the structured objects below.
- If existing structured intelligence is shown in CURRENT PROFILE above, refine or extend it — do not regress to plain text.

{{
  "company_profile": {{
    "platform_intelligence": {{
      "facts": [
        "Array of 3-5 tight fact bullets. Each ≤15 words. ONLY directly verifiable statements about the clinical platform — asset name, stage, mechanism, approval status, key data readouts. No BD deals, no financing, no interpretations. Examples: 'ABBV-701 (TL1A mAb, licensed FutureGen Jun 2024): Phase 1 SAD, est. completion Oct 2026', 'Skyrizi (IL-23p19): approved UC+CD; $17.6B FY2025 revenue', 'XENITH-UC Phase 2b (~220 pts): enrolling, primary completion Apr 2028'."
      ],
      "direction": [
        "Array of 2-3 interpretation bullets. Each ≤15 words. Logical conclusions about the PLATFORM STRATEGY derived from the facts — not restatements, not BD behavior. Label each [INFERRED]. Examples: '[INFERRED] ABBV-701 positioned as SKYRIZI combination backbone, not TL1A monotherapy', '[INFERRED] Dual-track strategy hedges monospecific and bispecific formats simultaneously'."
      ],
      "assessment": "[ASSESSED] 1 sentence. Framed for {_disease_label} per AREA FRAMING above. Two cases: (1) If this IS Ailux's primary area: 'What does this company's platform trajectory mean for Ailux's competitive positioning or timing in {_disease_label}?' (2) If NOT Ailux's primary area: Lead with the company's position in {_disease_label}, then pivot to the Ailux BD angle — benchmark, partner potential, or cross-area signal. Must NOT repeat facts or BD deal details already in other cards. Be specific, direct, actionable.",
      "confidence": "high | medium | low — based on volume and quality of public disclosures, trial activity, and deal history"
    }},
    "bd_intelligence": {{
      "profile": "One of: acquirer | licensor | collaborator | partner-friendly | internal-focused — classify the company's dominant BD behavior in this area",
      "transactions": [
        {{"date": "Mon YYYY", "asset": "asset name / target — BD deals and financing only, NOT clinical milestones", "partner": "counterparty short name", "upfront": "$XM or null", "total": "$XM or null"}}
      ],
      "assessment": [
        "Array of 2-3 short [ASSESSED] bullets. Each ≤15 words. BD-specific conclusions ONLY — deal structure, partnering likelihood, pricing benchmarks, timing of BD window. Must NOT repeat platform science facts from platform_intelligence. Examples: '[ASSESSED] Unlikely licensing target — executing TL1A in-house; no external partnership expected', '[ASSESSED] FutureGen deal sets $1.71B floor for Phase 1 TL1A asset pricing'."
      ],
      "confidence": "high | medium | low"
    }},
    "key_risk": "REQUIRED — 1-2 sentences: the single most important risk or uncertainty for this company/program in this area. Be specific: trial risk (endpoint, enrollment, regulatory), competitive risk (head-to-head data, first-mover), platform risk (technology, execution), or financial risk. Not a generic summary — Ailux needs to know what could go wrong and why it matters.",
    "why_it_matters": "REQUIRED — 1-2 sentences: why this company matters for Ailux's BD strategy specifically in the context of {_disease_label}. Answer one of: (a) They set a pricing/valuation benchmark Ailux should track in {_disease_label} or adjacent areas, (b) They are a potential partner or acquirer (explain why — their BD mandate, immunology portfolio scope, deal history), (c) Their clinical data in {_disease_label} validates or informs Ailux's mechanism or competitive position, (d) Their deal structure defines what counterparties expect in this or adjacent disease areas. Never generic — always give a specific Ailux-relevant BD reason tied to {_disease_label}.",
    "vs_ailux": "REQUIRED — 1-2 sentences. See AREA FRAMING above: if this IS Ailux's primary competitive area ({_disease_label}), lead with mechanism difference vs SPY002 (TL1A×IL-23p19 bispecific). If this is NOT Ailux's primary area, explain why Ailux monitors this company — benchmark-setting, partner/acquirer potential, or cross-area BD signal. Never say only 'no overlap' — always give the positive BD reason. If the company IS Ailux/Spyre, describe their full strategy in {_disease_label} instead.",
    "strategic_behavior": "1 sentence: acquirer / licensor / partner-seeker / platform builder.",
    "pipeline_url": "URL or null",
    {financial_fields}
  }},
  "drug_updates": [{{
    "drug_id": "exact drug id from DRUGS list",
    "strategic_role": "REQUIRED — classify this drug's role for this company in this area ({_disease_label}): 'direct_competitor' (same mechanism as Ailux's lead asset in this area), 'franchise_anchor' (dominant commercial asset the company's {_disease_label} strategy is built on), 'combination_asset' (designed to be used in combo with another drug), 'same_space_defense' (same indication, different mechanism, commercially important), 'platform_expansion' (future programs extending the franchise), or 'watch' (early/uncertain relevance)",
    "display_name": "null or override display name — use when company uses a different code than the drug_id. Format: 'CompanyCode (OriginalCode)' e.g. 'ABBV-701 (FG-M701)' or 'Skyrizi (Risankizumab)'. Only set when the canonical displayed name differs from what the drug_id implies.",
    "licensor_name": "null or full legal name of the originating company — e.g. 'FutureGen Biopharmaceutical Co., Ltd.'. Only for in-licensed assets.",
    "licensor_code": "null or original code/name used by licensor — e.g. 'FG-M701'. Only when drug was renamed by licensee.",
    "partner_company": "REQUIRED for any non-self deal — short display name of the originating/partner company, NO legal suffixes (e.g. 'FutureGen Biopharmaceutical', 'Simcere', 'Teva', 'Prometheus Biosciences'). This is what appears in the dashboard pill next to the drug name. Must be null only when partnership_type is 'self' or null.",
    "partnership_verified": "null | false | true. Set false when partnership is inferred from secondary sources (news, databases). Set true ONLY when confirmed from an official source (press release, SEC filing, ClinicalTrials.gov sponsor field). Default null when partnership_type is 'self' or no partner.",
    "modality": "anti-TL1A mAb|TL1A×IL-23p19 bispecific|JAK1 inhibitor (oral small molecule)|anti-α4β7 integrin mAb|etc — full descriptive label",
    "drug_format": "mAb|bispecific|small molecule|ADC|nanobody|fusion protein",
    "route": "SC|IV|SC/IV|oral|null",
    "dosing_type": "Induction|Maintenance|Induction + Maintenance|null",
    "dosing_schedule": "null or e.g. Q3M SC",
    "indication_short": "null or abbreviated indication list using standard clinical abbreviations separated by ' · ' — e.g. 'UC · CD', 'AD · RA', 'AD'. ALWAYS abbreviate: Ulcerative Colitis→UC, Crohn's Disease→CD, Atopic Dermatitis→AD, Rheumatoid Arthritis→RA, Psoriatic Arthritis→PsA, Psoriasis→Ps, Ankylosing Spondylitis→AS, Hidradenitis Suppurativa→HS, Eosinophilic Esophagitis→EoE, Alopecia Areata→AA, SLE, MS, TED, gMG, COPD, NASH, MASH, IBD. Never write full disease names.",
    "stage_detail": "null or e.g. Phase 2b (ARTEMIS-CD)",
    "phase_display": "null or e.g. Phase 3",
    "half_life_note": "null or e.g. ~74 days",
    "mechanism_detail": "null or 1-2 sentences: specific mechanism, format, any structural notes (platform tech, half-life, engineering)",
    "drug_summary": "REQUIRED — 1-2 sentences MAX. Written for PhD scientists and BD professionals: dense, factual, zero filler. Lead with the most clinically or commercially significant fact. Include mechanism, stage, and one differentiating detail (e.g. key data point, platform, deal structure). For approved drugs: include revenue and approval status. Never use phrases like 'noteworthy', 'important', 'significant' — show the fact, not the adjective. Never return null.",
    "key_data": "REQUIRED for approved/late-stage drugs — most important clinical data point in one sentence (e.g. primary endpoint result, pivotal trial outcome). For early-stage with no public data: brief mechanism note. Never leave null if drug_summary is populated.",
    "vs_ailux": "null or 1 sentence comparison to Ailux's TL1A×IL-23p19 bispecific — mechanism, stage, differentiation",
    "overlap": "REQUIRED — Direct | Adjacent | Same-Space | Watch. Use AILUX COMPETITIVE ANCHOR four-tier rules above. Direct = same molecular target as Ailux or combo including Ailux's target. Adjacent = same disease, different mechanism, validates biology or is a combination candidate (e.g. IL-23, α4β7). Same-Space = approved SOC in the same indication via a fundamentally different pathway (integrin blockers, older biologics — compete for patients, define efficacy bar). Watch = same patients but entirely different mechanism (JAK, S1P, RIPK1, TNF), or early-stage with unconfirmed relevance.",
    "overlap_rationale": "REQUIRED — 1-2 sentences explaining why this drug is classified in this tier relative to Ailux's TL1A position. Be specific about the mechanism.",
    "source_url": "REQUIRED when confidence_level is 'confirmed' or 'supported' — the single most authoritative public URL for this drug entry. Priority order: (1) ClinicalTrials.gov study URL (https://clinicaltrials.gov/study/NCTxxxxxxxx) for trial-verified drugs, (2) company IR/pipeline page for pipeline disclosures, (3) press release or SEC filing URL for deal/approval data. Set null only when genuinely unavailable. NEVER fabricate URLs — if you cannot verify a URL exists, set null and explain in overlap_rationale.",
    "confidence_level": "REQUIRED — one of: 'confirmed' (primary source URL available and verified, e.g. CT.gov, FDA label, company press release) | 'supported' (credible secondary sources, e.g. conference abstract, analyst deck, investor materials — no single primary URL but convergent evidence) | 'inferred' (model-derived classification; no direct public source). When confidence_level is 'inferred', overlap_rationale MUST explain why: use phrases like 'No primary source found — inferred from mechanism and published literature', 'Source unavailable — classified from company pipeline disclosure without drug-level detail', or 'Inferred from indication and target class; no CT.gov registration found'.",
    "data_source": "ct_gov|company_ir|press_release|sec_filing|conference|claude_inferred",
    "aliases": [],
    "approval_date": "null or string: regulatory approval date and indication — e.g. 'May 2023 (UC); Jan 2024 (CD)'. ONLY populate for drugs where stage contains 'Approved'.",
    "annual_revenue": "null or string: latest reported annual revenue with year — e.g. '$10.4B (2024)'. ONLY for approved drugs.",
    "patient_population": "null or string: estimated patients on therapy globally — e.g. '~250,000 patients on therapy'. ONLY for approved drugs.",
    "final_endpoints": "null or string: pivotal trial primary endpoint results narrative in 1-3 sentences. ONLY for approved drugs."
  }}],
  "combination_programs": [{{
    "label": "Short name for this combination — e.g. 'Skyrizi + ABBV-382 (α4β7 + IL-23p19)'",
    "component_drug_ids": ["exact drug_id from DRUGS list", "..."],
    "combination_type": "backbone_addon (established drug + add-on) | rational_combo (two investigational drugs) | sequential (drugs used in sequence, not simultaneously)",
    "stage": "Phase 1|Phase 2|Phase 3|Planned Ph1|Planned Ph2|Planned Ph2b|Preclinical|Concept — use 'Planned Phx' for disclosed but not yet initiated studies (no NCT registered)",
    "phase_display": "null or e.g. 'Phase 2b (anticipated initiation H2 2026)'",
    "anticipated_start": "null or company-guided start timing for planned studies — e.g. 'H2 2026'. REQUIRED when stage starts with 'Planned'.",
    "prerequisite_note": "null or what must happen before this study can begin — e.g. 'Awaiting Phase 1 monotherapy completion for ABBV-701'. REQUIRED when stage starts with 'Planned' and there is a known dependency.",
    "indication_short": "e.g. 'UC · CD'",
    "strategic_significance": "high|medium|low",
    "mechanism_detail": "1-2 sentences: rationale for combining these mechanisms, what complementary biology is targeted",
    "drug_summary": "2-3 sentences: what is known about this combination program — trial data, company guidance, strategic rationale",
    "overlap": "REQUIRED — Direct | Adjacent | Same-Space | Watch. A combo that includes a TL1A component = Direct. A multi-mechanism IBD combo without TL1A but in same indication = Adjacent (e.g. IL-23+α4β7). Use AILUX COMPETITIVE ANCHOR four-tier rules above.",
    "overlap_rationale": "REQUIRED — 1-2 sentences explaining why this combination program is classified in this tier.",
    "notes": "1 sentence: source or confidence note",
    "source_url": "null or URL to press release, trial registration, or IR page — never fabricate. REQUIRED when stage starts with 'Planned'."
  }}],
  "trial_updates": [{{
    "trial_id": "exact trial id from TRIALS list (the 'id' field, e.g. 'NCT06895343')",
    "study_acronym": "null or string: the branded program acronym this company uses for the trial — e.g. 'SKYLINE-UC' (Spyre), 'U-ACHIEVE' (AbbVie), 'PURSUIT' (J&J), 'ARTEMIS-CD'. Search the company's press releases and IR materials for how they brand this study. If the TRIALS list already shows a non-null study_acronym, confirm or correct it. Only include if you find a specific acronym — never fabricate.",
    "status": "null or current trial status from ClinicalTrials.gov — one of: Recruiting | Active, not recruiting | Completed | Not yet recruiting | Enrolling by invitation | Terminated | Withdrawn | Suspended. Update if the current status differs from the TRIALS list. Return null only if you cannot verify the current status.",
    "primary_completion_date": "null or YYYY-MM-DD: the current primary completion date from ClinicalTrials.gov. Update if the date has changed or was previously null. Return null only if not listed on CT.gov.",
    "area_fit": "REQUIRED — classify this trial's relevance to the current area: 'primary' = trial tests in the exact target indication for this area (e.g. UC or CD trial in the tl1a area), 'secondary' = same disease family but broader (e.g. IBD maintenance in a UC-focused area), 'off_target' = entirely different indication (e.g. psoriasis trial for a drug tracked in the IBD area), 'exclude' = basket/umbrella or observational study.",
    "estimand": "null or string: the ICH E9(R1) estimand strategy used in this trial's primary analysis. Describes how intercurrent events (rescue medication use, discontinuation, study drug change) are handled. Examples: 'Composite estimand — rescue medication use or discontinuation counted as treatment failure', 'Treatment policy estimand — all post-randomisation data included regardless of intercurrent events', 'Hypothetical estimand — data after rescue medication censored'. Search clinical trial registry, protocol, and publications for the statistical analysis plan estimand definition. Return null if not publicly specified.",
    "results_note": "null or string: key primary endpoint results for Completed or Terminated trials — 2-4 sentences. Include: primary endpoint name, response/remission rate for drug vs placebo (with p-value or CI if reported), and any headline safety signal. Source from publications (NEJM, Lancet, Gut), conference abstracts (DDW, ECCO, UEG), or ClinicalTrials.gov results postings. Example: 'GEMINI 1 (UC induction): vedolizumab achieved 47.1% clinical response vs 25.5% PBO at Wk 6 (p<0.001); 16.9% vs 5.4% clinical remission at Wk 6. GEMINI 1 (UC maintenance): 44.8% remission at Wk 52 vs 15.9% PBO (p<0.001). Well-tolerated; nasopharyngitis most common AE.' Return null for ongoing or not-yet-recruiting trials, or if no results are publicly available."
  }}],
  "new_trials": [{{
    "id": "NCT number — e.g. 'NCT06895343'. REQUIRED. Never fabricate. Only include if you have verified this NCT ID exists on ClinicalTrials.gov.",
    "drug_id": "exact drug_id from DRUGS list — the drug this trial is studying",
    "trial_name": "official full study title from ClinicalTrials.gov",
    "phase": "Phase 1 | Phase 1/Phase 2 | Phase 2 | Phase 2/Phase 3 | Phase 3 | Phase 4",
    "status": "Recruiting | Active, not recruiting | Completed | Not yet recruiting | Enrolling by invitation | Terminated | Withdrawn",
    "indication": "short condition/indication — e.g. 'Ulcerative Colitis' or 'Crohn Disease'",
    "primary_completion_date": "YYYY-MM-DD if known, else null",
    "study_acronym": "null or branded program acronym if known — e.g. 'U-ACHIEVE'",
    "source_url": "https://clinicaltrials.gov/study/NCTXXXXXXXX — always include the CTgov URL",
    "estimand": "null or string: ICH E9(R1) estimand strategy for the primary endpoint — how intercurrent events are handled. Examples: 'Composite estimand — rescue medication or discontinuation = treatment failure', 'Treatment policy estimand'. Return null if not publicly specified.",
    "results_note": "null or string: key primary endpoint results — REQUIRED for any Completed or Terminated trial. 2-4 sentences. Include endpoint name, response/remission rate vs placebo with p-value if reported, and headline safety signal. Source from publications, conference abstracts, or ClinicalTrials.gov results posting."
    "area_fit": "REQUIRED — same classification as trial_updates: 'primary' | 'secondary' | 'off_target' | 'exclude'",
  }}],
  "catalysts": [{{
    "catalyst_date": "Include specific day when known: 'April 28, 2028'. Use 'Q3 2026' or 'H2 2026' when only quarter/half known. Never just a year.",
    "sort_date_approx": "YYYY-MM-DD best estimate",
    "label": "concise event label ≤120 chars",
    "catalyst_type": "readout|filing|approval|conference|deal|partnership",
    "significance": "high|medium|low",
    "is_key_watch": true or false,
    "confidence_level": "confirmed (company filing/PDUFA)|supported (multiple sources)|inferred (derived from trial dates or guidance)",
    "source_url": "REQUIRED — CT.gov NCT link, press release URL, SEC filing, or company IR page. Omit field if no verified URL found (never fabricate).",
    "notes": "1 sentence context — include evidence source (e.g. 'Company-guided Q3 2026 per ECCO 2025 presentation')"
  }}],
  "deal_updates": [{{
    "headline": "match to existing deal headline",
    "geography_rights": "null or e.g. Global ex-China",
    "economics_royalties": "null or e.g. tiered royalties 8-15%",
    "strategic_signal": "1 sentence: what this deal signals",
    "ailux_relevance": "1 sentence: how this affects Ailux's BD strategy",
    "source_url": "REQUIRED — press release URL, SEC 8-K, or company IR page. Omit if not verified (never fabricate)."
  }}],
  "news_items": [{{
    "intel_date": "YYYY-MM-DD — date of the news item. Use exact date from article; estimate from context if needed.",
    "headline": "Concise factual headline ≤120 chars — what happened, who, and key number/outcome if applicable.",
    "body": "2-4 sentences: what happened, key data or terms, and why it matters for Ailux's BD strategy. Include the pivotal stat or outcome if a readout.",
    "source_url": "REQUIRED — exact URL of press release, IR page, or primary source. Never fabricate. Omit item if no verifiable URL.",
    "source_name": "Publication or company IR name — e.g. 'AbbVie Press Release', 'FDA', 'NEJM', 'Fierce Biotech'",
    "importance": "high (pivotal readout, major deal, approval) | medium (Phase 2 data, financing, partnership) | low (minor update, conference abstract)",
    "intel_type": "data | deal | regulatory | financing | conference | partnership | management"
  }}],
  "molecule_updates": [{{
    "drug_id": "exact drug_id from DRUGS list — one entry per drug",
    "format": "REQUIRED — e.g. 'monoclonal antibody', 'bispecific IgG1', 'nanobody', 'small molecule', 'fusion protein'",
    "valency": "e.g. 'monospecific bivalent', '2+2 (bivalent both arms)', '1+1'. null if unknown.",
    "modality": "REQUIRED — 'antibody', 'small molecule', 'biologic', 'cell therapy', 'oligonucleotide'",
    "igg_subclass": "IgG1 | IgG2 | IgG4 | other | null — infer from class/mechanism if not stated",
    "fc_engineering": "Any known Fc modifications — e.g. 'S228P hinge stabilization (IgG4)', 'YTE half-life extension', 'LALA effector silencing', 'none known'. null if no data.",
    "epitope": "Binding epitope or region if publicly disclosed — e.g. 'receptor-binding domain of TL1A'. Use 'not publicly disclosed' if absent from literature. Never null — use 'not publicly disclosed'.",
    "affinity_kd": "KD value with units if known — e.g. '0.4 nM (SPR, 37C)'. Use 'not publicly disclosed' if not reported. Never null.",
    "lowest_active_dose": null or number (mg/kg),
    "lowest_active_dose_unit": "null or 'mg/kg' | 'mg' | 'ug/kg'",
    "safety_observations": "Key safety signals from available clinical data. 'No clinical data available — preclinical stage' for pre-IND assets. Never null.",
    "differentiation_claim": "REQUIRED — 1-2 sentences. What makes this molecule structurally or mechanistically distinct from other agents in this area? Be specific: format advantage, engineering feature, epitope differentiation, dosing, CDx strategy. This is the molecule-level competitive thesis — not restating the company's BD profile.",
    "field_status": {{
      "format": "confirmed | inferred | unknown",
      "modality": "confirmed | inferred | unknown",
      "igg_subclass": "confirmed | inferred | unknown",
      "fc_engineering": "confirmed | inferred | unknown",
      "epitope": "confirmed | inferred | unknown",
      "affinity_kd": "confirmed | inferred | unknown",
      "differentiation_claim": "confirmed | inferred | unknown"
    }},
    "confidence": "high (published papers, CT.gov) | medium (press release, conference abstract) | low (analyst report, inference)",
    "source_url": "Primary source URL for molecule data. null if no citable source."
  }}],
  "competitive_signals": [{{
    "drug_id": "exact drug_id from DRUGS list — null if company-level event (financing, patent portfolio)",
    "signal_type": "conference | patent | financing | publication | licensing | regulatory | clinical_update",
    "title": "Concise factual event title ≤120 chars",
    "description": "2-4 sentences: what happened, key outcome or terms, and why it matters competitively. Include specific numbers/dates where available.",
    "source_url": "REQUIRED — primary source URL. Omit item if no verified URL exists. Never fabricate.",
    "source_date": "YYYY-MM-DD — date the event occurred or was publicly disclosed",
    "confidence": 0.90
  }}]
}}

MOLECULE FIELD STATUS RULES (CRITICAL — read before writing field_status):
- 'confirmed': field value sourced from a peer-reviewed paper, patent, CT.gov protocol, or official press release with explicit data.
- 'inferred': field value logically deduced from drug class, mechanism, or analogous compounds — NOT directly stated in a source. Example: IgG4 subclass inferred from anti-inflammatory mechanism when subclass not publicly stated.
- 'unknown': no information available from any source, public or inferred.
NEVER write 'confirmed' for a value that is inferred from class effects. If IgG subclass or Fc engineering is not explicitly stated in a public source, use 'inferred'. This is enforced — the dashboard will display the status badge prominently.

RULES:
- drug_updates: only drugs from DRUGS list (exact drug_id). EVERY drug in the DRUGS list must have an entry.
- molecule_updates: one entry per drug in the DRUGS list. REQUIRED fields: format, modality, differentiation_claim, field_status (all keys present). field_status must accurately reflect whether each value is confirmed/inferred/unknown — never write 'confirmed' for inferred values.
- trial_updates: only trials from TRIALS list (exact trial id). Include an entry for EVERY trial where you can provide at least one non-null field — a study acronym, updated status, updated primary_completion_date, estimand, or results_note. Skip a trial only if you have nothing new to add for any of those fields.
- new_trials: use this to seed trials that are NOT already in the TRIALS list above. Only include trials you are confident exist on ClinicalTrials.gov (verified NCT ID). drug_id must exactly match a drug_id in the DRUGS list. Never fabricate NCT IDs. IMPORTANT: Do NOT assume the TRIALS list is complete. Actively search for earlier Phase 1 and Phase 2 trials (including completed and terminated studies) that preceded the current program — a drug in Phase 3 almost certainly ran a Phase 1 and/or Phase 2 first, and those trials may have published results that are not yet in the TRIALS list. The presence of active Phase 3 trials does NOT mean earlier trials have been captured. Only return [] if you have verified through web search that no additional trials exist for these drugs.
- catalysts: only upcoming events (after {TODAY}). ONE entry per distinct event — do NOT duplicate: if multiple trials share the same primary completion date, create ONE catalyst entry for that readout, not one per trial. Deduplicate by event type + approximate date.
- deal_updates: only match to EXISTING DEALS
- combination_programs: include ALL known multi-drug combination programs for this company in this area. If none exist or are being studied, return an empty array [].
- news_items: extract the 3-6 most significant recent news items from WEB INTELLIGENCE. Only include items with a verified source_url. If WEB INTELLIGENCE is empty, return []. Never fabricate articles. Prefer items from the past 12 months. Each item must have a real URL.
- competitive_signals: extract 0-5 discrete competitive events from WEB INTELLIGENCE that are PAST (already happened). signal_type must be one of: conference (abstract/poster/oral presentation), patent (filing or grant), financing (round/IPO/ATM), publication (paper/preprint), licensing (deal), regulatory (IND/BLA/approval milestone), clinical_update (data readout/trial initiation/enrollment update). Only include events with a verified source_url. Return [] if none found. Do NOT duplicate events already captured in catalysts (which are future-facing).
- Return ONLY valid JSON. No markdown.
- ALWAYS apply DATA QUALITY STANDARDS from the system prompt: IL-23p19 notation, brand name format, PCD specificity, validated URLs.

STRATEGIC ROLE GUIDANCE (apply to every drug in drug_updates):
Every drug must receive a strategic_role. Think about it from Ailux's BD perspective:
- direct_competitor: mechanistically overlaps with Ailux's TL1A×IL-23p19 bispecific (e.g., another anti-TL1A, another TL1A-based bispecific)
- franchise_anchor: the dominant approved or late-stage asset the company's IBD/disease-area revenue strategy is built around (e.g., Skyrizi is AbbVie's IBD anchor)
- combination_asset: a drug specifically being evaluated in combination with another drug in the same disease area
- same_space_defense: same indication as Ailux's target space but mechanistically unrelated — commercially important but not a direct mechanistic threat (e.g., Rinvoq for AbbVie)
- platform_expansion: an early or future program that extends the company's franchise into new mechanisms
- watch: early-stage or uncertain relevance

DISPLAY NAME GUIDANCE (CRITICAL — apply to every acquired/licensed drug):
- If a drug was acquired or in-licensed, display_name MUST be ONLY the acquirer's current name — no parentheticals, no old name.
- Format: "AcquirerCode" ONLY — e.g. "ABBV-701", "JNJ-2113". Do NOT write "ABBV-701 (FG-M701)".
- If the brand name exists: "BrandName (INN)" — e.g. "Skyrizi (risankizumab)".
- The old name belongs in licensor_code (e.g. "FG-M701") and licensor_name (originating company, e.g. "FutureGen Biopharmaceutical Co., Ltd."). The dashboard uses these fields to surface "formerly [licensor_code]" in the detail view automatically — never repeat the old name in display_name.
- NEVER leave display_name null or equal to the drug_id when the drug has a licensor — this creates inaccurate data.

SLASH IN DISPLAY NAME — CRITICAL PROHIBITION:
- NEVER set display_name to "DrugA / DrugB" where DrugA and DrugB are two different drugs from different programs or companies.
- A slash in display_name ONLY belongs in a brand/INN pair: "Dupixent (dupilumab)" — NOT for two separate assets.
- Sources often show comparison tables like "LQ080 vs ZW191" or "Drug A / Drug B (competitor)" — NEVER interpret a slash in a source as meaning the two drugs are the same asset or aliases of each other.
- If a source lists two drug codes together with a slash and you cannot confirm they are the same molecule with the same target and same company, treat them as SEPARATE DRUGS. Set display_name to just the drug_id's code. Do NOT combine them.
- Confirmed historical error: "LQ080 / ZW191" was incorrectly set because a comparison source was misread. LQ080 is a Novamab TL1A×IL-23 VHH bispecific; ZW191 is a Zymeworks FRα ADC for oncology — completely unrelated.

ACQUIRED / RENAMED DRUG DETECTION (CRITICAL — prevents cross-company duplicates):
A drug may appear in the literature under two completely different names when one company acquires a program from another and renames it. Classic patterns:
- Pharma code → INN: "PF-07261271" → "afimkibart" (Pfizer originated; Roche renamed after Telavant acquisition)
- Licensor code → acquirer code: "FG-M701" → "ABBV-701" (FutureGen originated; AbbVie in-licensed and re-coded)
- Partnership/JV rename: "RVT-3101" (Telavant JV) = "RO7790121" = "afimkibart" (Roche INN)

When you identify such a renaming event for a drug belonging to this company:
1. Set licensor_code = the ORIGINAL code used by the prior owner (e.g. "PF-07261271")
2. Set licensor_name = the full legal name of the originating company (e.g. "Pfizer / Telavant Holdings (Roivant Sciences JV)")
3. Set partner_company = the SHORT recognizable name of the originating company (e.g. "Pfizer") — this is what renders in the "w/ X" pill on the dashboard
4. Set partnership_type = "licensed_in" for in-licensing, "acquired" for outright acquisition
5. Set display_name = the CURRENT acquirer code ONLY (no old name in parentheses)

IMPORTANT: If you find that a drug in this company's portfolio is a renamed/acquired version of a drug that another company already has in the database, do NOT create a second entry for the originating company. The lead developer (the company running the trials) is the canonical owner; the originating company's code goes in licensor_code.

COMBINATION PROGRAM GUIDANCE:
Identify ALL known combination programs for this company in this area. Include:
- Ongoing combination trials (two drugs being studied together)
- Company-disclosed combination development plans
- Rational combinations the company is known to be building toward (clearly stated in press releases or investor materials)
Do NOT include speculative combos. If no combinations exist, return []. Combinations appear in the dashboard alongside standalone drugs — the label should be clear and short enough to read in a dropdown (e.g., "Skyrizi + ABBV-382 combo").

CRITICAL DISTINCTION — bispecific ≠ combination:
A bispecific antibody (e.g., RO7837195: IL-23p40 × TL1A) is a SINGLE MOLECULE that hits two targets simultaneously. It is NOT a combination program. Write it as a standalone drug_updates entry with its bispecific target notation. Do NOT put it in combination_programs.
A combination program involves two or more SEPARATE drugs administered together (e.g., Skyrizi + ABBV-382).
A co-developed drug (two companies developing one molecule) is also a standalone drug — put the partner in partner_company, NOT in combination_programs.

STUDY ACRONYM GUIDANCE:
Companies brand their clinical programs with memorable acronyms shown on their IR pages, ECCO/DDW posters, and press releases (e.g., Spyre uses "SKYLINE" for their TL1A program, AbbVie uses "U-ACHIEVE" for upadacitinib UC trials, J&J uses "PURSUIT" for guselkumab CD). Search the WEB INTELLIGENCE and known sources. ClinicalTrials.gov sometimes includes them in identificationModule.acronym — cross-reference if present in TRIALS list.

APPROVED DRUG GUIDANCE:
For any drug where stage contains "Approved", populate approval_date, annual_revenue, patient_population, and final_endpoints. Revenue figures come from company earnings reports; patient population from analyst estimates or company disclosures; pivotal endpoints from the registrational trial publication or FDA label.

NEWS ITEMS GUIDANCE:
Extract 3-6 of the most significant recent news items found in WEB INTELLIGENCE. Prioritize:
- Phase 2/3 trial readouts with data (always high importance)
- New deals, partnerships, or licensing agreements (high if >$100M, else medium)
- FDA/regulatory approvals, BTD, Priority Review, REMS (high importance)
- New financings (medium, include amount)
- Major conference presentations with data (medium)
- Management changes, pipeline updates (low)
Only include items with a real, verifiable URL you found in WEB INTELLIGENCE. Never fabricate URLs or articles. If WEB INTELLIGENCE is empty or contains no news with verifiable links, return []."""
