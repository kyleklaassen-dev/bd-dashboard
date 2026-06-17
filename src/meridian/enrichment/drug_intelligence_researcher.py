#!/usr/bin/env python3
"""
drug_intelligence_researcher.py
================================
Researches a drug using all 100 Meridian intelligence questions across 8 domains.
Results are stored in:
  - drug_intelligence_qa         (all 100 Q&A pairs)
  - drug_clinical_benchmarks     (extracted efficacy data)
  - drug_development_timelines   (extracted milestone dates)

Usage:
    python3 src/meridian/enrichment/drug_intelligence_researcher.py --drug-id tulisokibart --indication uc
    python3 src/meridian/enrichment/drug_intelligence_researcher.py --drug-id nipocalimab --indication igg4-rd
    python3 src/meridian/enrichment/drug_intelligence_researcher.py --drug-id tulisokibart --indication uc --dry-run
    python3 src/meridian/enrichment/drug_intelligence_researcher.py --drug-id tulisokibart --indication uc --domain molecule
    python3 src/meridian/enrichment/drug_intelligence_researcher.py --list-drugs

Environment (set via env vars or key files in workspace root):
    SUPABASE_URL          https://tghntyofptvfhmtchwcv.supabase.co
    SUPABASE_SERVICE_KEY  (or .supabase_service_key file)
    ANTHROPIC_API_KEY     (or .anthropic_api_key file)
"""

import os
import sys
import json
import time
import argparse
import pathlib
import datetime
from typing import Optional

import requests
import anthropic

# ── Credentials ───────────────────────────────────────────────────────────────
BASE_DIR = pathlib.Path(__file__).resolve().parents[3]

def _load_key(env_var: str, file_name: str) -> str:
    val = os.environ.get(env_var, "").strip()
    if val:
        return val
    p = BASE_DIR / file_name
    if p.exists():
        return p.read_text().strip()
    sys.exit(f"ERROR: {env_var} not set and {file_name} not found in {BASE_DIR}")

SUPABASE_URL  = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
SERVICE_KEY   = _load_key("SUPABASE_SERVICE_KEY", ".supabase_service_key")
ANTHROPIC_KEY = _load_key("ANTHROPIC_API_KEY", ".anthropic_api_key")
CLAUDE_MODEL  = "claude-sonnet-4-6"

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

SB_HEADERS = {
    "apikey":        SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}
SB_UPSERT_HEADERS = {
    **SB_HEADERS,
    "Prefer": "resolution=merge-duplicates,return=representation",
}

# ── 100 Questions by Domain ────────────────────────────────────────────────────

DOMAIN_QUESTIONS = {
    "molecule": {
        "range": (1, 20),
        "focus": "molecular mechanism, structure, pharmacology, preclinical biology",
        "questions": [
            (1,  "What is the precise epitope or binding site on the target, and how does this compare to competitors in the same class?"),
            (2,  "What is the mechanism of action — does it block ligand binding, induce receptor internalization, trigger ADCC/CDC, or act via another mechanism?"),
            (3,  "What downstream signaling pathways are inhibited or activated, and which are most relevant to disease pathology?"),
            (4,  "On which cell types is the target predominantly expressed in disease tissue versus healthy tissue?"),
            (5,  "What is the established biological role of this target in the disease — is it causative, amplifying, or downstream?"),
            (6,  "How does blocking or activating this target interrupt disease pathology? Describe the mechanistic chain from drug binding to clinical benefit."),
            (7,  "What is the drug's modality and format (e.g., IgG1/IgG4, bispecific, ADC, small molecule, CAR-T) and what functional properties does this confer?"),
            (8,  "What is the reported half-life (t1/2) in humans, and what is the PK basis (FcRn recycling, catabolism, target-mediated)?"),
            (9,  "What is the route of administration and how does it affect patient convenience versus clinical use?"),
            (10, "What is the dosing interval, and is there evidence of dose escalation, de-escalation, or maintenance dose reduction in trials?"),
            (11, "What are the known or predicted off-target effects, and have any been observed clinically?"),
            (12, "What preclinical models have been used to establish efficacy, and how well do they translate to the human disease?"),
            (13, "Is there a validated pharmacodynamic or predictive biomarker (e.g., serum level, tissue marker, genetic variant)?"),
            (14, "What is the PD readout used in clinical trials to confirm target engagement (e.g., cytokine suppression, receptor occupancy)?"),
            (15, "What is the tissue or disease compartment penetration evidence (e.g., mucosal IgA in IBD, synovial fluid in RA)?"),
            (16, "What is the immunogenicity profile — ADA rate, impact on PK/PD, neutralizing antibody frequency?"),
            (17, "What are the key manufacturing or formulation characteristics that affect cost-of-goods or supply chain?"),
            (18, "What combination strategies have been explored or proposed, and what is the rationale (additive vs synergistic)?"),
            (19, "What are the known or theoretical escape pathways — how might a patient become non-responsive over time?"),
            (20, "What are the key ADME characteristics (absorption, distribution, metabolism, excretion) and any notable drug-drug interaction risks?"),
        ],
    },
    "clinical": {
        "range": (21, 40),
        "focus": "trial design, efficacy endpoints, timelines, patient enrichment, safety",
        "questions": [
            (21, "What was the first-in-human (FIH) trial date, and what were the primary Phase 1 objectives and outcomes?"),
            (22, "What are the Phase 1 objectives and what dose-limiting toxicities or MTD findings were reported?"),
            (23, "What is the pivotal (Phase 2b/3) trial design — randomized vs open-label, placebo vs active comparator, parallel arms?"),
            (24, "What is the primary efficacy endpoint and what is the statistical threshold (e.g., remission rate vs placebo at Week 12)?"),
            (25, "What are the key secondary endpoints and are any of them payer-relevant (e.g., steroid-free remission, mucosal healing)?"),
            (26, "What patient enrichment strategies are used (biomarker selection, disease activity score cutoffs, prior biologic failure requirement)?"),
            (27, "What is the enrollment rate and current enrollment status of the pivotal trial?"),
            (28, "What is the primary completion date and topline data expected timing?"),
            (29, "What is the theoretical efficacy ceiling — based on Phase 2 data or class effects, what is the best plausible Phase 3 outcome?"),
            (30, "How was the clinical dose selected — what PK/PD or Phase 1 data justified the Phase 3 dose?"),
            (31, "Is there a responder analysis available — what fraction of patients achieve deep remission vs clinical remission vs response?"),
            (32, "What is the number-needed-to-treat (NNT) based on available Phase 2 data?"),
            (33, "What are the treatment-emergent adverse event (TEAE) rates — all grades and Grade 3+?"),
            (34, "What serious adverse events (SAEs) have been reported, and how do they compare to class benchmarks?"),
            (35, "Is there durability data — do remission rates hold at 1 year, and what is the maintenance dosing evidence?"),
            (36, "What steroid-free remission rate has been reported or is expected, and why does this matter for label positioning?"),
            (37, "What subgroup analyses have been conducted or are pre-specified (by biomarker, prior biologic failure, disease severity)?"),
            (38, "What drug-drug interaction (DDI) risks have been identified, particularly with standard IBD/immunosuppressive co-medications?"),
            (39, "What is the time-to-onset of clinical benefit (weeks to first symptom response)?"),
            (40, "What is the estimated FIH-to-NDA timeline, and how does it compare to class benchmarks?"),
        ],
    },
    "patient": {
        "range": (41, 55),
        "focus": "patient experience, quality of life, adherence, caregiver burden, PROs",
        "questions": [
            (41, "What is the typical patient profile — age, gender, disease duration, prior treatments at the time of enrollment?"),
            (42, "What is the typical disease trajectory for patients in this indication — episodic vs chronic progressive?"),
            (43, "What validated patient burden score (e.g., IBDQ, EQ-5D, PROMIS) is used and what is the baseline vs. treated score?"),
            (44, "What is the treatment history of the target patient — how many prior biologics, conventional therapies, or surgeries?"),
            (45, "What route of administration do patients prefer, and is there evidence of preference (IV vs SC vs oral)?"),
            (46, "What is the caregiver burden associated with this disease, and does the treatment reduce it?"),
            (47, "What are the top safety fears expressed by patients or physicians in this indication?"),
            (48, "What is the expected adherence rate, and what factors drive non-adherence in this patient population?"),
            (49, "What patient advocacy groups are active in this disease area, and what are their stated research priorities?"),
            (50, "What patient-reported outcome (PRO) measure is used in trials and is it FDA-qualified for this indication?"),
            (51, "How do patients define meaningful remission — what symptoms must resolve for them to consider treatment successful?"),
            (52, "What comorbidities are common in this patient population and do they affect treatment selection?"),
            (53, "What is the time-to-benefit expectation — when do patients typically notice improvement in symptoms?"),
            (54, "What long-term safety concern is most cited by patients or advocacy groups for this drug class?"),
            (55, "How does this drug compare to current standard of care from a patient perspective (convenience, tolerability, efficacy)?"),
        ],
    },
    "payer": {
        "range": (56, 65),
        "focus": "pricing, market access, formulary, HTA, cost-effectiveness",
        "questions": [
            (56, "What is the current or expected wholesale acquisition cost (WAC) and estimated net price after rebates?"),
            (57, "What step therapy requirement is likely — will payers require prior conventional or biologic failure?"),
            (58, "What HTA process applies (FDA, EMA, NICE, HAS) and what value framework will be used?"),
            (59, "What is the likely ICER threshold and does Phase 2 data suggest the drug will meet it?"),
            (60, "Do payers show preference for route of administration convenience (SC > IV) in this indication?"),
            (61, "What is the typical time-to-formulary coverage for a new biologic in this indication?"),
            (62, "What biosimilar threat exists — are there biosimilar entrants in the same class within the 10-year forecast window?"),
            (63, "What real-world evidence (RWE) requirements have payers or regulators signaled for this drug class?"),
            (64, "What patient assistance programs are standard in this class and are they likely to be required for coverage?"),
            (65, "What is the strongest cost-effectiveness argument for this drug — efficacy per dollar, reduced hospitalization, or steroid avoidance?"),
        ],
    },
    "competitive": {
        "range": (66, 80),
        "focus": "competitive landscape, differentiation, deals, class risk, whitespace",
        "questions": [
            (66, "Who is the best-in-class (BIC) competitor, and why are they considered best-in-class?"),
            (67, "What is the best-in-class efficacy benchmark — the specific number this drug must beat or match?"),
            (68, "How does this drug differentiate from the best-in-class — mechanism, safety, dosing, patient selection?"),
            (69, "What efficacy threshold would constitute head-to-head superiority over the BIC in the pivotal indication?"),
            (70, "What efficacy threshold would constitute meaningful differentiation without formal superiority?"),
            (71, "What Phase 2/3 competitors have readouts expected within the next 18 months, and what are their expected timelines?"),
            (72, "What competitive failures have occurred in this class, and what do they reveal about the indication or mechanism?"),
            (73, "What deal economics have been observed for this asset class — recent licensing/acquisition valuations?"),
            (74, "What class effect risk exists — if the MoA proves insufficient, does this drug fail with the class?"),
            (75, "What is the earliest core patent expiry for this drug, and what does the IP cliff look like?"),
            (76, "How does the geographic competitive landscape differ — is Europe or Asia more contested than the US?"),
            (77, "What combination strategies are competitors pursuing, and does this drug have a combination angle?"),
            (78, "What is the historical Phase 3 failure rate for this mechanism in this indication?"),
            (79, "What is the whitespace score — how crowded is the indication for this mechanism on a 0–10 scale?"),
            (80, "What is the Ailux asymmetric insight — what does Ailux's TL1A×IL-23p19 bispecific know or do that single-target competitors cannot?"),
        ],
    },
    "regulatory": {
        "range": (81, 90),
        "focus": "approval pathway, FDA guidance, label, CMC, pediatric",
        "questions": [
            (81, "What regulatory designations has this drug received (Breakthrough, Fast Track, RMAT, Orphan, Priority Review)?"),
            (82, "What FDA or EMA guidance documents define the regulatory path for this indication?"),
            (83, "What is the precedent drug whose approval endpoint defined the regulatory standard for this indication?"),
            (84, "What trial duration is required by regulators for induction and maintenance data in this indication?"),
            (85, "What is the likely label scope — which indications and patient subgroups are expected to be included?"),
            (86, "Is there likely to be a restricted prescribing requirement (REMS, specialist-only, biomarker requirement)?"),
            (87, "What CMC (chemistry, manufacturing, and controls) challenges are specific to this modality and indication?"),
            (88, "What pediatric development requirement applies, and has a pediatric investigation plan (PIP) been filed?"),
            (89, "What post-marketing commitments are likely to be required (REMS, Phase 4 studies, RWE)?"),
            (90, "What is the estimated approval probability based on phase, mechanism precedent, and trial design?"),
        ],
    },
    "ip": {
        "range": (91, 95),
        "focus": "patents, freedom to operate, IP disputes",
        "questions": [
            (91, "What are the core composition-of-matter patents and their expiry dates?"),
            (92, "What is the freedom-to-operate (FTO) status — are there blocking patents from competitors?"),
            (93, "What recent patent filings (last 3 years) have been made for this drug or close analogs?"),
            (94, "What design-around approaches would a biosimilar manufacturer need to take?"),
            (95, "Are there any active IP disputes, inter partes reviews (IPR), or litigation involving this drug or its target?"),
        ],
    },
    "strategic": {
        "range": (96, 100),
        "focus": "BD value, partner fit, licensing trigger, obsolescence risk",
        "questions": [
            (96, "What is the risk-adjusted NPV estimate for this asset, and what assumptions drive the range?"),
            (97, "What is the ideal partner profile for this asset — large pharma, mid-size specialty, or regional player?"),
            (98, "What is the optimal licensing trigger — at what clinical milestone should Ailux consider an out-licensing deal?"),
            (99, "What is the primary obsolescence risk — what competitive or scientific development could render this asset unnecessary?"),
            (100,"What is the Ailux-specific strategic advantage in developing this molecule, given its TL1A×IL-23p19 bispecific platform?"),
        ],
    },
}

# ── Domain prompt template ────────────────────────────────────────────────────

DOMAIN_PROMPT_TEMPLATE = """\
You are a PhD-level biopharma analyst with deep expertise in {indication} treatment and {target_class} biology.

Drug profile:
  Name:       {drug_name}
  Target:     {target}
  Mechanism:  {mechanism}
  Modality:   {modality}
  Stage:      {stage}
  Company:    {company}
  Indication: {indication}
  Summary:    {summary}

Domain focus: {domain_focus}

Answer each question below. For each question, return a JSON object with exactly these fields:
  - question_id: integer
  - domain: string (the domain name)
  - question_text: string (copy of the question)
  - answer_short: 1–2 sentence direct answer (max 50 words)
  - answer_text: 2–5 sentence detailed answer with specific data, numbers, trial names, dates
  - confidence_score: float 0.0–1.0 (0.9+ = well-established, 0.5–0.8 = reasonably supported, <0.5 = estimated)
  - evidence_level: one of "high" | "medium" | "low" | "estimated" | "unknown"
  - source_urls: array of specific URLs (PubMed, CT.gov NCT links, FDA documents, press releases) — empty array if none
  - source_labels: array of human-readable labels matching source_urls (e.g. "NEJM 2024 Phase 2 UC", "NCT05242159") — empty array if none

Rules:
- Be specific: use exact percentages, week numbers, trial names (e.g. "ATLAS-UC", "TREMBLE-1")
- Cite sources: PubMed IDs as https://pubmed.ncbi.nlm.nih.gov/PMID/, NCT as https://clinicaltrials.gov/study/NCTxxxxxxx
- If uncertain: set evidence_level="estimated" and explain the basis in answer_text
- If truly unknown: set evidence_level="unknown", answer_short="Unknown. Insufficient public data available.", confidence_score=0.0
- Do NOT fabricate trial names, NCT numbers, or PubMed IDs
- Do NOT conflate this drug with competitors

Questions {q_start}–{q_end}:
{questions_text}

Return ONLY a JSON array of {n_questions} objects. No prose, no markdown fences, just the raw JSON array.
"""

BENCHMARK_EXTRACTION_PROMPT = """\
Given this drug intelligence Q&A data about {drug_name} in {indication}, extract all clinical benchmark data points.

Q&A data:
{qa_text}

For each distinct efficacy data point you can identify, return a JSON object with:
  - benchmark_type: one of "primary_remission" | "endoscopic_remission" | "clinical_response" | "deep_remission" | "mucosal_healing" | "clinical_remission" | "steroid_free_remission" | "histologic_remission"
  - rate_pct: numeric percentage (e.g. 26.1)
  - comparator_rate_pct: placebo or comparator rate if available, else null
  - dose_label: dose description (e.g. "500mg Q4W", "RZB 600mg SC")
  - timepoint_weeks: integer week number (e.g. 12)
  - n_enrolled: integer total enrolled in this arm, or null
  - trial_name: trial name (e.g. "ATLAS-UC", "TREMBLE-1"), or null
  - nct_id: NCT number without spaces (e.g. "NCT05242159"), or null
  - patient_enrichment: enrichment criteria if stated (e.g. "bio-naive", "bio-failure", "TNFSF15+"), or null
  - is_phase3: true if Phase 3, false otherwise
  - is_approved_label: true if from an approved label, false otherwise
  - source_url: best source URL for this data point

Return ONLY a JSON array. If no clear benchmark data is found, return an empty array [].
Do NOT fabricate numbers. Only include data that appears explicitly in the Q&A text above.
"""

TIMELINE_EXTRACTION_PROMPT = """\
Given this drug intelligence Q&A data about {drug_name}, extract all development milestone dates.

Q&A data:
{qa_text}

For each milestone you can identify, return a JSON object with:
  - milestone: one of "discovery" | "preclinical_start" | "ind_filing" | "fih" | "phase1_complete" | "phase2_start" | "phase2_primary" | "phase3_start" | "phase3_primary" | "nda_filing" | "approval"
  - milestone_label: human-readable label (e.g. "Phase 3 ATLAS-UC primary completion")
  - actual_date: ISO date string "YYYY-MM-DD" if known exactly, else null
  - estimated_date: ISO date string if approximate but month-level known, else null
  - estimated_year: integer year if only year is known, else null
  - estimated_quarter: string like "Q4 2026" if known, else null
  - date_basis: brief explanation of how this date was determined
  - confidence: one of "confirmed" | "high" | "medium" | "low" | "speculative"
  - source_url: best source URL for this date, or null
  - notes: any important qualifiers or caveats

Return ONLY a JSON array. If no milestone dates are found, return an empty array [].
Do NOT fabricate dates. Only include dates that appear explicitly in the Q&A text above.
"""

# ── Supabase helpers ──────────────────────────────────────────────────────────

def sb_get(table: str, params: dict) -> list:
    from urllib.parse import urlencode
    qs = urlencode(params)
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}?{qs}", headers=SB_HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()

def sb_upsert(table: str, payload: list | dict) -> list:
    if isinstance(payload, dict):
        payload = [payload]
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=SB_UPSERT_HEADERS,
        json=payload,
        timeout=30,
    )
    if not r.ok:
        print(f"  [WARN] upsert failed for {table}: {r.status_code} {r.text[:200]}")
    return r.json() if r.ok else []

# ── Drug loading ──────────────────────────────────────────────────────────────

def load_drug(drug_id: str) -> dict:
    rows = sb_get("drugs", {
        "select": "id,name,target,stage,mechanism,modality,company_id,drug_summary",
        "id": f"eq.{drug_id}",
    })
    if not rows:
        sys.exit(f"ERROR: Drug '{drug_id}' not found in Supabase. Use --list-drugs to see available IDs.")
    drug = rows[0]

    # Fetch company name
    company_rows = sb_get("companies", {
        "select": "id,name",
        "id": f"eq.{drug['company_id']}",
    })
    drug["company_name"] = company_rows[0]["name"] if company_rows else drug["company_id"]
    return drug

def list_drugs() -> None:
    rows = sb_get("drugs", {"select": "id,name,stage,target,company_id", "order": "name.asc"})
    print(f"{'ID':<40} {'Name':<35} {'Stage':<15} {'Target':<30} Company")
    print("-" * 130)
    for r in rows:
        print(f"{r['id']:<40} {r['name']:<35} {(r['stage'] or ''):<15} {(r['target'] or ''):<30} {r['company_id']}")
    print(f"\n{len(rows)} drugs total.")

# ── Claude calls ──────────────────────────────────────────────────────────────

def call_claude_for_domain(
    drug: dict,
    domain: str,
    config: dict,
    indication: str,
    verbose: bool = False,
) -> list[dict]:
    """Call Claude for one domain, return parsed list of QA dicts."""
    q_start, q_end = config["range"]
    questions = config["questions"]

    questions_text = "\n".join(
        f"Q{qid}. {qtext}" for qid, qtext in questions
    )

    prompt = DOMAIN_PROMPT_TEMPLATE.format(
        drug_name=drug["name"],
        target=drug.get("target") or "unknown target",
        mechanism=drug.get("mechanism") or "unknown mechanism",
        modality=drug.get("modality") or "unknown modality",
        stage=drug.get("stage") or "unknown stage",
        company=drug.get("company_name") or drug.get("company_id") or "unknown company",
        indication=indication,
        summary=drug.get("drug_summary") or "No summary available.",
        target_class=(drug.get("target") or "biologic target").split(" ")[0],
        domain_focus=config["focus"],
        q_start=q_start,
        q_end=q_end,
        n_questions=len(questions),
        questions_text=questions_text,
    )

    if verbose:
        print(f"  Calling Claude for domain '{domain}' (Q{q_start}–Q{q_end})...")

    t0 = time.time()
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8096,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"  [ERROR] Claude call failed for domain {domain}: {e}")
        return []

    elapsed = time.time() - t0
    raw = response.content[0].text.strip()

    if verbose:
        print(f"  Domain '{domain}' completed in {elapsed:.1f}s, ~{len(raw)} chars")

    # Parse JSON
    try:
        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  [WARN] JSON parse failed for domain {domain}: {e}")
        print(f"  Raw response (first 500 chars): {raw[:500]}")
        return []

    if not isinstance(parsed, list):
        print(f"  [WARN] Expected JSON array for domain {domain}, got {type(parsed)}")
        return []

    # Normalize and validate each record
    normalized = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        qid = item.get("question_id")
        if qid is None:
            continue

        # Clamp confidence_score to valid range
        cs = item.get("confidence_score")
        if cs is not None:
            try:
                cs = float(cs)
                cs = max(0.0, min(1.0, cs))
            except (TypeError, ValueError):
                cs = None

        normalized.append({
            "drug_id": drug["id"],
            "question_id": int(qid),
            "domain": domain,
            "question_text": str(item.get("question_text", "")),
            "answer_short": item.get("answer_short"),
            "answer_text": item.get("answer_text"),
            "confidence_score": cs,
            "evidence_level": item.get("evidence_level"),
            "source_urls": item.get("source_urls") or [],
            "source_labels": item.get("source_labels") or [],
            "last_researched": datetime.datetime.utcnow().isoformat(),
            "researcher_model": CLAUDE_MODEL,
            "needs_update": False,
        })

    return normalized


def extract_benchmarks(
    drug: dict,
    indication: str,
    all_qa: list[dict],
    verbose: bool = False,
) -> list[dict]:
    """Call Claude to extract clinical benchmarks from Q&A data."""
    # Only use clinical domain Q&A for benchmark extraction
    clinical_qa = [
        q for q in all_qa
        if q["domain"] in ("clinical", "competitive", "payer")
    ]
    if not clinical_qa:
        return []

    qa_text = "\n\n".join(
        f"Q{q['question_id']} ({q['domain']}): {q['question_text']}\n"
        f"A: {q.get('answer_text', q.get('answer_short', ''))}"
        for q in clinical_qa
    )

    prompt = BENCHMARK_EXTRACTION_PROMPT.format(
        drug_name=drug["name"],
        indication=indication,
        qa_text=qa_text,
    )

    if verbose:
        print("  Extracting clinical benchmarks...")

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"  [ERROR] Benchmark extraction failed: {e}")
        return []

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  [WARN] Benchmark JSON parse failed. Raw: {raw[:300]}")
        return []

    if not isinstance(parsed, list):
        return []

    # Add drug_id and indication_id to each benchmark
    normalized = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        item["drug_id"] = drug["id"]
        item["indication_id"] = indication
        item["last_updated"] = datetime.datetime.utcnow().isoformat()
        normalized.append(item)

    return normalized


def extract_timeline(
    drug: dict,
    all_qa: list[dict],
    verbose: bool = False,
) -> list[dict]:
    """Call Claude to extract development milestones from Q&A data."""
    qa_text = "\n\n".join(
        f"Q{q['question_id']} ({q['domain']}): {q['question_text']}\n"
        f"A: {q.get('answer_text', q.get('answer_short', ''))}"
        for q in all_qa
    )

    prompt = TIMELINE_EXTRACTION_PROMPT.format(
        drug_name=drug["name"],
        qa_text=qa_text,
    )

    if verbose:
        print("  Extracting development timeline...")

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        print(f"  [ERROR] Timeline extraction failed: {e}")
        return []

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  [WARN] Timeline JSON parse failed. Raw: {raw[:300]}")
        return []

    if not isinstance(parsed, list):
        return []

    # Add drug_id
    normalized = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        item["drug_id"] = drug["id"]
        normalized.append(item)

    return normalized


# ── Storage ───────────────────────────────────────────────────────────────────

def store_qa(qa_records: list[dict], dry_run: bool = False) -> int:
    if not qa_records:
        return 0
    if dry_run:
        print(f"  [DRY RUN] Would upsert {len(qa_records)} Q&A records into drug_intelligence_qa")
        return len(qa_records)
    result = sb_upsert("drug_intelligence_qa", qa_records)
    return len(result) if isinstance(result, list) else len(qa_records)


def store_benchmarks(benchmarks: list[dict], dry_run: bool = False) -> int:
    if not benchmarks:
        return 0
    if dry_run:
        print(f"  [DRY RUN] Would insert {len(benchmarks)} benchmarks into drug_clinical_benchmarks")
        return len(benchmarks)
    # Benchmarks don't have a unique key — insert only (don't upsert to avoid duplication on re-run)
    # Use upsert headers but without conflict resolution — plain POST
    plain_headers = {**SB_HEADERS}
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/drug_clinical_benchmarks",
        headers=plain_headers,
        json=benchmarks,
        timeout=30,
    )
    if not r.ok:
        print(f"  [WARN] Benchmark insert failed: {r.status_code} {r.text[:200]}")
        return 0
    return len(benchmarks)


def store_timeline(timeline: list[dict], dry_run: bool = False) -> int:
    if not timeline:
        return 0
    if dry_run:
        print(f"  [DRY RUN] Would upsert {len(timeline)} timeline events into drug_development_timelines")
        return len(timeline)
    result = sb_upsert("drug_development_timelines", timeline)
    return len(result) if isinstance(result, list) else len(timeline)


# ── Main research orchestrator ────────────────────────────────────────────────

def research_drug(
    drug_id: str,
    indication: str,
    dry_run: bool = False,
    verbose: bool = False,
    domains_filter: Optional[list[str]] = None,
) -> dict:
    """
    Full 100-question research run for one drug + indication.
    Returns summary dict with counts.
    """
    print(f"\nResearching drug: {drug_id} | indication: {indication}")
    print("=" * 60)

    # Load drug record
    drug = load_drug(drug_id)
    print(f"  Drug:    {drug['name']}")
    print(f"  Target:  {drug.get('target', 'unknown')}")
    print(f"  Stage:   {drug.get('stage', 'unknown')}")
    print(f"  Company: {drug.get('company_name', drug.get('company_id', 'unknown'))}")
    print()

    all_qa: list[dict] = []
    domains_to_run = domains_filter or list(DOMAIN_QUESTIONS.keys())

    t_total_start = time.time()

    for domain in domains_to_run:
        if domain not in DOMAIN_QUESTIONS:
            print(f"  [SKIP] Unknown domain: {domain}")
            continue

        config = DOMAIN_QUESTIONS[domain]
        q_start, q_end = config["range"]
        print(f"  Domain: {domain} (Q{q_start}–Q{q_end})", end="", flush=True)

        t0 = time.time()
        qa_records = call_claude_for_domain(drug, domain, config, indication, verbose=verbose)
        elapsed = time.time() - t0

        print(f" → {len(qa_records)} answers in {elapsed:.1f}s")

        if qa_records:
            stored = store_qa(qa_records, dry_run=dry_run)
            if not dry_run and verbose:
                print(f"    Stored {stored} Q&A records.")

        all_qa.extend(qa_records)

        # Brief pause to avoid rate limiting
        if not dry_run:
            time.sleep(0.5)

    # Extract and store benchmarks
    print(f"\n  Extracting clinical benchmarks...", end="", flush=True)
    benchmarks = extract_benchmarks(drug, indication, all_qa, verbose=verbose)
    stored_benchmarks = store_benchmarks(benchmarks, dry_run=dry_run)
    print(f" → {stored_benchmarks} benchmarks")

    # Extract and store timeline
    print(f"  Extracting development timeline...", end="", flush=True)
    timeline = extract_timeline(drug, all_qa, verbose=verbose)
    stored_timeline = store_timeline(timeline, dry_run=dry_run)
    print(f" → {stored_timeline} timeline events")

    total_elapsed = time.time() - t_total_start

    summary = {
        "drug_id": drug_id,
        "drug_name": drug["name"],
        "indication": indication,
        "qa_count": len(all_qa),
        "benchmark_count": stored_benchmarks,
        "timeline_count": stored_timeline,
        "elapsed_seconds": round(total_elapsed, 1),
        "dry_run": dry_run,
    }

    print(f"\nCompleted in {total_elapsed:.1f}s")
    print(f"  Q&A records:       {len(all_qa)}/100")
    print(f"  Benchmarks stored: {stored_benchmarks}")
    print(f"  Timeline events:   {stored_timeline}")
    if dry_run:
        print("  [DRY RUN — nothing written to Supabase]")

    return summary


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Meridian Drug Intelligence Researcher — 100-question brain for any drug.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 src/meridian/enrichment/drug_intelligence_researcher.py --drug-id tulisokibart --indication uc
  python3 src/meridian/enrichment/drug_intelligence_researcher.py --drug-id nipocalimab --indication igg4-rd --dry-run
  python3 src/meridian/enrichment/drug_intelligence_researcher.py --drug-id tulisokibart --indication uc --domain molecule clinical
  python3 src/meridian/enrichment/drug_intelligence_researcher.py --list-drugs
        """,
    )
    parser.add_argument("--drug-id", type=str, help="Supabase drug ID to research")
    parser.add_argument("--indication", type=str, help="Indication to focus on (e.g. 'uc', 'cd', 'igg4-rd')")
    parser.add_argument("--dry-run", action="store_true", help="Run research but do not write to Supabase")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed progress")
    parser.add_argument(
        "--domain",
        nargs="+",
        choices=list(DOMAIN_QUESTIONS.keys()),
        help="Research only specific domains (default: all 8)",
    )
    parser.add_argument("--list-drugs", action="store_true", help="List all drug IDs in Supabase and exit")

    args = parser.parse_args()

    if args.list_drugs:
        list_drugs()
        return

    if not args.drug_id:
        parser.error("--drug-id is required (or use --list-drugs to see options)")
    if not args.indication:
        parser.error("--indication is required (e.g. --indication uc)")

    research_drug(
        drug_id=args.drug_id,
        indication=args.indication,
        dry_run=args.dry_run,
        verbose=args.verbose,
        domains_filter=args.domain,
    )


if __name__ == "__main__":
    main()
