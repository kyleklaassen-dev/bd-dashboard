#!/usr/bin/env python3
"""
Meridian Writer — GitHub Actions edition
Reads biopharma intel from Supabase (last 24h), generates a full Meridian HTML
briefing using Claude Opus (two-pass: editorial plan → full draft), and commits
meridian_today.html to GitHub Pages.
Runs 6:30 AM ET Mon–Sat (10:30 UTC).
"""

import os, json, datetime, base64, re, time, hashlib
import requests
import anthropic

# Patient intelligence context (co-equal intelligence layer)
try:
    from patient_intelligence_module import PATIENT_INTELLIGENCE_CONTEXT, build_patient_context_block
    PATIENT_INTEL_AVAILABLE = True
except ImportError:
    PATIENT_INTELLIGENCE_CONTEXT = ""
    build_patient_context_block = lambda items: ""
    PATIENT_INTEL_AVAILABLE = False

# ── Credentials ─────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SUPABASE_URL      = os.environ["SUPABASE_URL"]
SUPABASE_KEY      = os.environ["SUPABASE_SERVICE_KEY"]
GITHUB_TOKEN      = os.environ["GITHUB_TOKEN"]
GITHUB_REPO       = os.environ.get("GITHUB_REPO", "kyleklaassen-dev/bd-dashboard")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}

GH_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept":        "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def log(msg):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ── Area display names ───────────────────────────────────────────────────────
AREA_NAMES = {
    "tl1a":  "TL1A / IBD",
    "tslp":  "TSLP / Severe Asthma",
    "il4ra": "IL-4Rα / Atopy",
    "igf1r": "IGF1R / Thyroid Eye Disease",
    "fcrn":  "FcRn / IgG Autoimmune",
    "tcell": "T-cell / Treg Therapy",
    "ibd":   "IBD (broad)",
    "respiratory": "Respiratory",
}


# ── Fetch intel from Supabase ────────────────────────────────────────────────
def fetch_recent_intel(hours_back=48):
    """Pull intel + area tags written in the last N hours."""
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(hours=hours_back)).strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/intel",
            headers=SB_HEADERS,
            params={
                "select": "id,intel_date,headline,body,source_url,source_name,importance,intel_type,intel_areas(area_id)",
                "intel_date": f"gte.{cutoff}",
                "order": "importance.desc,intel_date.desc",
            },
        )
        items = r.json()
        for item in items:
            areas = item.pop("intel_areas", []) or []
            item["areas"] = [a["area_id"] for a in areas]
        log(f"Fetched {len(items)} intel items (since {cutoff})")
        return items
    except Exception as e:
        log(f"Intel fetch error: {e}")
        return []


def fetch_recent_deals(days_back=7):
    """Pull any deals logged in the last week."""
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/deals",
            headers=SB_HEADERS,
            params={
                "select": "deal_date,from_company,to_company,area_id,deal_type,upfront_usd_m,total_usd_m,headline,detail",
                "deal_date": f"gte.{cutoff}",
                "order": "deal_date.desc",
            },
        )
        deals = r.json()
        log(f"Fetched {len(deals)} recent deals")
        return deals
    except Exception as e:
        log(f"Deals fetch error: {e}")
        return []


def fetch_upcoming_catalysts():
    """Pull unresolved catalysts sorted by date."""
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/catalysts",
            headers=SB_HEADERS,
            params={
                "select": "catalyst_date,label,area_id,significance,catalyst_type,notes",
                "resolved": "eq.false",
                "sort_date": f"gte.{today}",
                "order": "sort_date.asc",
                "limit": "20",
            },
        )
        cats = r.json()
        log(f"Fetched {len(cats)} upcoming catalysts")
        return cats
    except Exception as e:
        log(f"Catalysts fetch error: {e}")
        return []


def fetch_drug_context():
    """Fetch all drugs and companies for context enrichment of intel items."""
    drugs, companies = {}, {}
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/drugs",
            headers=SB_HEADERS,
            params={
                "select": "id,name,display_name,company_id,stage,target,mechanism,overlap,overlap_rationale,ailux_angle,partner_company,partnership_type,partnership_verified,indication_short",
                "limit": "500",
            },
        )
        for d in r.json():
            drugs[d["id"]] = d
            # Also index by lowercased name/display_name for matching
        log(f"Fetched {len(drugs)} drugs for context enrichment")
    except Exception as e:
        log(f"Drug context fetch error: {e}")

    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/companies",
            headers=SB_HEADERS,
            params={"select": "id,name,ticker", "limit": "200"},
        )
        for c in r.json():
            companies[c["id"]] = c
        log(f"Fetched {len(companies)} companies for context enrichment")
    except Exception as e:
        log(f"Company context fetch error: {e}")

    return drugs, companies


def fetch_ailux_position():
    """Fetch Ailux's competitive anchor from ailux_positions table."""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/ailux_positions",
            headers=SB_HEADERS,
            params={"select": "*", "limit": "10"},
        )
        positions = r.json()
        log(f"Fetched {len(positions)} Ailux position records")
        return positions
    except Exception as e:
        log(f"Ailux position fetch error: {e}")
        return []


def fetch_recent_meridian_issues(n=7):
    """Fetch recent Meridian issues for editorial continuity.
    Returns title + intel_ids so we can surface what was covered and avoid repetition.
    Skips today's issue if already present."""
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/meridian_issues",
            headers=SB_HEADERS,
            params={
                "select": "issue_date,title,intel_ids",
                "order": "issue_date.desc",
                "limit": str(n + 1),
            },
        )
        issues = [i for i in r.json() if i.get("issue_date") != today][:n]
        log(f"Fetched {len(issues)} prior Meridian issues for continuity")
        return issues
    except Exception as e:
        log(f"Recent issues fetch error: {e}")
        return []


def fetch_company_signals():
    """Fetch current company-level intelligence bullets from the dashboard."""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/company_signals",
            headers=SB_HEADERS,
            params={
                "select": "company_id,signal_type,signal_text,sort_order",
                "order": "company_id,sort_order",
            },
        )
        if r.status_code != 200:
            log(f"Company signals unavailable ({r.status_code}) — skipping")
            return []
        data = r.json()
        if not isinstance(data, list):
            log(f"Company signals unexpected response shape — skipping")
            return []
        log(f"Fetched {len(data)} company signals")
        return data
    except Exception as e:
        log(f"Company signals fetch error: {e}")
        return []


def fetch_graph_context():
    """
    Fetch entity_edges for graph-grounded competitive intelligence.

    Returns three structures:
      active_in:     {area_id: [company_ids]}  — who is in each area
      targets_edges: {entity_id: [target_ids]} — what each entity targets
      competes_with: [(subject_id, object_id)] — confirmed competitive pairs
    """
    active_in, targets_edges, competes_with = {}, {}, []

    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/entity_edges",
            headers=SB_HEADERS,
            params={
                "select": "subject_id,object_id",
                "predicate": "eq.ACTIVE_IN",
                "status": "eq.active",
                "limit": "500",
            },
        )
        if r.status_code == 200:
            for edge in r.json():
                area = edge.get("object_id")
                co   = edge.get("subject_id")
                if area and co:
                    active_in.setdefault(area, []).append(co)
            log(f"Graph: {sum(len(v) for v in active_in.values())} ACTIVE_IN edges across {len(active_in)} areas")
    except Exception as e:
        log(f"Graph ACTIVE_IN fetch error: {e}")

    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/entity_edges",
            headers=SB_HEADERS,
            params={
                "select": "subject_id,object_id",
                "predicate": "eq.TARGETS",
                "status": "eq.active",
                "limit": "300",
            },
        )
        if r.status_code == 200:
            for edge in r.json():
                subj = edge.get("subject_id")
                obj  = edge.get("object_id")
                if subj and obj:
                    targets_edges.setdefault(subj, []).append(obj)
            log(f"Graph: {len(targets_edges)} entities with TARGETS edges")
    except Exception as e:
        log(f"Graph TARGETS fetch error: {e}")

    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/entity_edges",
            headers=SB_HEADERS,
            params={
                "select": "subject_id,object_id",
                "predicate": "eq.COMPETES_WITH",
                "confidence_level": "eq.confirmed",
                "status": "eq.active",
                "limit": "200",
            },
        )
        if r.status_code == 200:
            seen = set()
            for e in r.json():
                subj, obj = e.get("subject_id"), e.get("object_id")
                if subj and obj:
                    pair = tuple(sorted([subj, obj]))
                    if pair not in seen:
                        seen.add(pair)
                        competes_with.append(pair)
            log(f"Graph: {len(competes_with)} unique COMPETES_WITH pairs (confirmed)")
    except Exception as e:
        log(f"Graph COMPETES_WITH fetch error: {e}")

    return active_in, targets_edges, competes_with


def fetch_recent_trials():
    """Fetch clinical trial records updated in the last 30 days."""
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/trials",
            headers=SB_HEADERS,
            params={
                "select": "drug_id,nct_id,phase,status,enrollment,primary_completion,sponsor,indication,updated_at",
                "updated_at": f"gte.{cutoff}T00:00:00",
                "order": "updated_at.desc",
                "limit": "60",
            },
        )
        trials = r.json() if r.status_code == 200 else []
        log(f"Fetched {len(trials)} recent trial records")
        return trials
    except Exception as e:
        log(f"Trials fetch error: {e}")
        return []


# ── Context enrichment ───────────────────────────────────────────────────────
def enrich_intel_with_drug_context(items, drugs, companies):
    """
    For each intel item, keyword-match against known drug names and company names.
    Append a compact DB-state block so the writer has live competitive context.
    """
    # Build lookup structures
    drug_lookup = {}   # lowercased token → drug record
    for d in drugs.values():
        for field in [d.get("name"), d.get("display_name"), d.get("id")]:
            if field and len(field) > 3:
                drug_lookup[field.lower()] = d

    company_lookup = {}  # lowercased token → company record
    for c in companies.values():
        for field in [c.get("name"), c.get("ticker"), c.get("id")]:
            if field and len(field) > 2:
                company_lookup[field.lower()] = c

    enriched = []
    for item in items:
        text = f"{item.get('headline','')} {item.get('body','')}".lower()

        matched_drugs = []
        seen_drug_ids = set()
        for token, drug in drug_lookup.items():
            if token in text and drug["id"] not in seen_drug_ids:
                matched_drugs.append(drug)
                seen_drug_ids.add(drug["id"])

        matched_companies = []
        seen_co_ids = set()
        for token, co in company_lookup.items():
            if token in text and co["id"] not in seen_co_ids:
                matched_companies.append(co)
                seen_co_ids.add(co["id"])

        ctx_lines = []
        for drug in matched_drugs[:4]:  # cap at 4 matched drugs
            parts = [
                f"  → {drug.get('display_name') or drug.get('name')} ({drug.get('company_id','')})",
                f"    Stage: {drug.get('stage','?')} | Target: {drug.get('target') or drug.get('mechanism','?')}",
                f"    Overlap: {drug.get('overlap','?')} | Indication: {drug.get('indication_short','?')}",
            ]
            if drug.get("ailux_angle"):
                parts.append(f"    BD Signal: {drug['ailux_angle']}")
            if drug.get("partner_company"):
                verified = "✓" if drug.get("partnership_verified") else "?"
                parts.append(f"    Partner: {drug['partner_company']} [{drug.get('partnership_type','')}] {verified}")
            ctx_lines.extend(parts)

        item = dict(item)
        item["_db_context"] = "\n".join(ctx_lines) if ctx_lines else None
        enriched.append(item)

    return enriched


# ── Build prompt data ────────────────────────────────────────────────────────
def build_intel_block(items):
    if not items:
        return "(No new intel items today)"
    lines = []
    for it in items:
        areas_str = ", ".join(AREA_NAMES.get(a, a) for a in it.get("areas", []))
        block = (
            f"[{it['importance'].upper()} | {it['intel_type']} | {areas_str}]\n"
            f"HEADLINE: {it['headline']}\n"
            f"DETAIL: {it['body']}\n"
            f"SOURCE: {it['source_name']} — {it['source_url']}\n"
            f"DATE: {it['intel_date']}"
        )
        if it.get("_db_context"):
            block += f"\nDB CONTEXT (live pipeline state for referenced assets):\n{it['_db_context']}"
        lines.append(block)
    return "\n\n---\n\n".join(lines)


def build_deals_block(deals):
    if not deals:
        return "(No recent deals)"
    lines = []
    for d in deals:
        val = f"${d['upfront_usd_m']}M upfront" if d.get("upfront_usd_m") else ""
        if d.get("total_usd_m"):
            val += f" / ${d['total_usd_m']}M total"
        lines.append(
            f"{d['deal_date']} | {d.get('deal_type','').upper()} | {AREA_NAMES.get(d['area_id'], d['area_id'])}\n"
            f"{d['from_company']} → {d['to_company']} {val}\n"
            f"{d['headline']}"
            + (f"\nDETAIL: {d['detail']}" if d.get("detail") else "")
        )
    return "\n\n".join(lines)


def build_catalysts_block(cats):
    if not cats:
        return "(No upcoming catalysts on record)"
    lines = []
    for c in cats:
        sig = c.get("significance", "").upper()
        notes = f" — {c['notes']}" if c.get("notes") else ""
        lines.append(
            f"{c['catalyst_date']} | {AREA_NAMES.get(c['area_id'], c['area_id'])} | {sig}\n"
            f"{c['label']}{notes}"
        )
    return "\n".join(lines)


def build_ailux_block(positions):
    """Construct the Ailux competitive anchor block from DB + static context."""
    # Static context is always included; DB positions supplement it
    static = """AILUX IDENTITY & COMPETITIVE POSITION:
Ailux is an AI-native antibody design company. SPY002 is its lead asset: a TL1A × IL-23p19 bispecific antibody in development for IBD (UC and CD). The p19 subunit selectivity matters — it preserves IL-12-driven Th1 immunity unlike p40-targeted agents (e.g., RO7837195, Roche/Pfizer), making it mechanistically distinct.

TL1A CLASS STATE: Two monospecific anti-TL1A antibodies are in Phase 3 — tulisokibart (Merck, ATLAS-UC primary ~Nov 2026, first Ph3 TL1A readout) and afimkibart (Roche, AMETRINE-2 primary Jan 2027). Merck's readout is the single most consequential class validation event before Ailux reaches clinical inflection. A positive result validates sequencing and combination strategies and sets the monotherapy ceiling that a bispecific must exceed. A failure reshapes everything.

IL-23p19 CLASS STATE: Proven. Risankizumab (AbbVie, approved UC+CD), mirikizumab (Lilly, approved UC), guselkumab (J&J, CD Phase 3). Ailux enters against approved SOC — the clinical question is not "does IL-23 work" but "what does simultaneous TL1A+IL-23p19 blockade do beyond the sum of its parts."

BD PRIORITIES — what would actually move the needle for Ailux:
1. Combination data showing TL1A+IL-23 superiority over sequential therapy
2. Partner deals or licensing signals that reveal how the market values bispecific assets vs. monospecifics
3. Early-entry opportunities in less crowded Ailux areas (IGF1R/TED, FcRn, TSLP, T-cell/Treg)
4. Regulatory precedents for bispecific approval pathways in IBD
5. Clinical failures that reshape the competitive landscape or open white space"""

    if positions:
        pos_lines = []
        for p in positions:
            pos_lines.append(
                f"  Area: {p.get('area_id','')} | Ailux drug: {p.get('ailux_drug','')} "
                f"| Targets: {p.get('ailux_targets','')} | Stage: {p.get('ailux_stage','')}"
            )
            if p.get("ailux_angle"):
                pos_lines.append(f"  Angle: {p.get('ailux_angle')}")
        static += "\n\nLIVE DB POSITIONS:\n" + "\n".join(pos_lines)

    return static


def build_prior_coverage_block(recent_issues):
    """Give the writer a sense of what was covered in prior issues for continuity."""
    if not recent_issues:
        return "(No prior issue history available — this is the first issue.)"
    lines = []
    for i in recent_issues:
        intel_count = len(i.get("intel_ids") or [])
        lines.append(f"  {i['issue_date']}: {i['title']} ({intel_count} intel items)")
    return (
        "PRIOR ISSUE HISTORY (build on themes; connect to new developments; don't repeat without new signal):\n"
        + "\n".join(lines)
    )


def build_company_signals_block(signals):
    """Format current company intelligence bullets for the writer.
    Groups by company so the writer sees the full competitive posture of each player."""
    if not signals:
        return "(No company signals available)"
    by_company = {}
    for s in signals:
        cid = s.get("company_id", "?")
        by_company.setdefault(cid, []).append(s)
    lines = ["CURRENT COMPANY INTELLIGENCE (from live dashboard company cards):"]
    for company in sorted(by_company):
        lines.append(f"\n{company.upper()}:")
        for s in by_company[company]:
            stype = s.get("signal_type", "?").upper()
            lines.append(f"  [{stype}] {s.get('signal_text', '')}")
    return "\n".join(lines)


def build_trials_block(trials):
    """Format recent trial updates for editorial context."""
    if not trials:
        return "(No recent trial updates)"
    lines = ["RECENT CLINICAL TRIAL UPDATES (from dashboard trial tracker):"]
    for t in trials[:30]:  # cap at 30 to avoid prompt bloat
        drug   = t.get("drug_id", "?")
        phase  = t.get("phase", "?")
        status = t.get("status", "?")
        ind    = t.get("indication", "")
        nct    = t.get("nct_id", "")
        comp   = t.get("primary_completion", "")
        line   = f"  {drug} | Phase {phase} | {status} | {ind}"
        if comp:
            line += f" | completion: {comp}"
        if nct:
            line += f" | {nct}"
        lines.append(line)
    return "\n".join(lines)


def build_graph_block(active_in, targets_edges, competes_with):
    """
    Format entity_edges data as graph-grounded competitive intelligence.

    The graph supplements the editorial's drug/company context with stored
    structural relationships — who is where, what they target, and who
    directly competes. This is the L4-A graph injection layer.
    """
    if not active_in and not targets_edges and not competes_with:
        return "(Graph context unavailable)"

    PRIORITY_AREAS = ["tl1a", "tslp", "il4ra", "fcrn", "igf1r", "tcell", "ibd", "respiratory"]
    lines = ["GRAPH INTELLIGENCE (stored entity relationships — from entity_edges):"]

    # ── ACTIVE_IN: who is in each area ────────────────────────────────────────
    if active_in:
        lines.append("\nACTIVE PLAYERS BY AREA (ACTIVE_IN — confirmed company→area edges):")
        area_order = PRIORITY_AREAS + [a for a in sorted(active_in) if a not in PRIORITY_AREAS]
        for area in area_order:
            companies = active_in.get(area)
            if not companies:
                continue
            label = AREA_NAMES.get(area, area)
            lines.append(f"  {label}: {', '.join(sorted(companies))}")

    # ── TARGETS: mechanism convergence (which entities target the same mechanism) ──
    if targets_edges:
        # Reverse map: target → [entities]
        by_target = {}
        for entity, tgts in targets_edges.items():
            for t in tgts:
                by_target.setdefault(t, []).append(entity)
        # Only show contested mechanisms (≥2 entities)
        contested = {t: sorted(v) for t, v in by_target.items() if len(v) >= 2}
        if contested:
            lines.append("\nMECHANISM CONVERGENCE (TARGETS — mechanisms with multiple competing entities):")
            for target in sorted(contested, key=lambda t: -len(contested[t])):
                entities = contested[target]
                lines.append(f"  {target}: {', '.join(entities)} ({len(entities)} entities)")

    # ── COMPETES_WITH: direct competitive pairs ────────────────────────────────
    if competes_with:
        lines.append(f"\nDIRECT COMPETITIVE PAIRS (COMPETES_WITH — confirmed, {len(competes_with)} total):")
        # Group by shared tokens (rough area clustering)
        for subj, obj in competes_with[:50]:  # cap at 50 to avoid prompt bloat
            lines.append(f"  {subj} ↔ {obj}")

    return "\n".join(lines)


# ── System prompt (editorial identity) ──────────────────────────────────────
SYSTEM_PROMPT = """You are the founding editor of The Meridian, a Monday–Saturday morning intelligence briefing published exclusively for the BD and strategy leadership of Ailux, an AI-native antibody design company.

YOUR ROLE: The Meridian is the daily consolidation layer of the Ailux BD intelligence platform. Every piece of information flowing through the dashboard — company signals, clinical trial updates, deal activity, catalyst tracking, live intel — converges here. Your job is to synthesize all of it into a single coherent argument about what the competitive landscape looked like this morning, and what it means for Ailux's next 18 months.

YOUR READERS: PhD scientists who have published in Nature and NEJM. BD professionals who have closed nine-figure deals. They have already read the press releases. They do not need definitions of mechanisms, trial designs, or deal structures. They need the interpretive layer — the argument beneath the news.

YOUR EDITORIAL STANDARD:
- Every paragraph must contain one claim a smart, busy reader could not have made without reading this issue. If a paragraph only restates known facts, cut it or rewrite it.
- Never summarize what happened. Explain what it means and why it matters in the next 18 months.
- The BD Lens is not "this is relevant to Ailux." It is the specific implication for positioning, deal optionality, combination thesis, asset pricing, or clinical strategy — written at deal-room precision.
- When two stories connect non-obviously, make the connection explicit and argue it. That is where the value lives.
- Draw threads across issues. If Monday covered a deal and today brings data from the same program, say so explicitly — this is how the briefing builds a living model of the landscape.
- When the news is quiet, say what is conspicuously absent and why that itself is signal. A mechanism with no news for three weeks when competitors are typically active is information.
- Company signals and trial status from the dashboard are primary inputs — they represent the accumulated intelligence state, not just today's news. Use them.
- Be precise about mechanism. "IL-23 inhibition" is not acceptable. Specify the subunit, the pathway, the cell type, the downstream effect.
- Do not write "it remains to be seen." That hedge belongs in investor presentations, not intelligence briefings.
- Do not write "this space continues to evolve" or any equivalent platitude.

SOURCE HIERARCHY: Endpoints News and Fierce Biotech are the primary trade sources. Direct company press releases are equally authoritative. When these sources conflict with secondary sources, prefer Endpoints/Fierce/company-direct. All factual claims must be hyperlinked to their source.

TONE: The writing of a scientist who also reads The Economist and thinks like a portfolio manager. Authoritative. Precise. Intellectually engaged. Occasionally pointed when the evidence warrants it.

HARD PROHIBITIONS:
- Do not include any contact information, email addresses, or tip lines. The Meridian has no public inbox.
- Do not include any sign-off line such as "Questions or tips:" or any equivalent.
- The issue-meta footer should contain only the confidentiality disclaimer — no contact details of any kind.

WRITING_STANDARDS:
- Resolve contradictions before writing. If two sources disagree on a drug's target or mechanism, the definitive answer is the primary literature or EMA/FDA label. Never present both versions as equally valid.
- No speculation about company strategy, executive intent, or institutional behavior unless supported by a press release, earnings call transcript, or investor letter. Inference is not evidence.
- Every competitive paragraph must include at minimum: patient population (N, geography), current SOC response rate, and what clinical improvement means for this patient. Numbers are mandatory.
- Cite exact trial data: registry ID or trial name, primary endpoint metric, value at which dose and timepoint, N enrolled or completed. Do not round or generalize.
- First mention of a drug name in the HTML output: wrap in <a href="#" onclick="openDrugModal('{drug_id}')">drug name</a>. Subsequent mentions: plain text.
- First mention of a company name: wrap in <a href="#" onclick="openCompanyModal('{company_id}')">company name</a>. Subsequent mentions: plain text.
- Target is the molecular target. Mechanism is how the drug engages it. Pathway is the downstream biology. Name all three distinctly.
- If a drug's mechanism is unknown or disputed, say so explicitly and do not write competitive analysis around it until resolved."""

SYSTEM_PROMPT = SYSTEM_PROMPT + "\n\n" + PATIENT_INTELLIGENCE_CONTEXT


# ── Pass 1: Editorial planning ───────────────────────────────────────────────
PLAN_PROMPT = """Today is {date_long}.

You are planning today's issue of The Meridian before writing it. The Meridian is the daily consolidation layer of the Ailux BD intelligence platform — every signal flowing through the dashboard feeds this issue. Read all available intelligence carefully, then produce a tight editorial plan.

INTELLIGENCE AVAILABLE:
{intel_block}

RECENT DEALS:
{deals_block}

COMPANY INTELLIGENCE (live dashboard state):
{signals_block}

GRAPH INTELLIGENCE (stored entity relationships — who is active where, what they target, who competes with whom):
{graph_block}

PRIOR COVERAGE:
{prior_block}

AILUX CONTEXT:
{ailux_block}

## Today's Patient Intelligence Context
{patient_context_block}

Your editorial plan must answer:
1. THESIS: In one sentence, what is the single most important thing today's full intelligence picture reveals about the competitive landscape? This becomes the editorial spine of the lede.
2. SIGNAL vs. NOISE: Which 3–5 items are genuinely significant and deserve analysis? Which are noise (announcements without substance, recycled data, obvious moves)?
3. CONNECTIONS: Identify 1–3 non-obvious connections between separate items — including connections to prior issue themes. What do they point to together that neither suggests alone?
4. BD IMPLICATIONS: What are the 2–3 most specific implications for Ailux's BD strategy — not "this is relevant" but the actual tactical or positional inference?
5. ABSENCES: What notable development is conspicuously NOT in today's news that is worth flagging?
6. CONTINUITY: Are there threads from prior issues that today's intelligence advances, resolves, or complicates? Name them.
7. SECTION PLAN: Which sections should appear today? (Lead is always present. Others: Mechanism Intelligence / Clinical Inflection Points / BD & Deal Watch / Regulatory Watch.) Omit sections with nothing substantive to say.

Return your plan as JSON with keys: thesis, signal_items (list of headlines), noise_items (list of headlines), connections (list of strings), bd_implications (list of strings), absences (string), continuity_threads (list of strings), sections (list of section names)."""


# ── Pass 2: Full draft ───────────────────────────────────────────────────────
DRAFT_PROMPT = """Today is {date_long}. Write today's complete issue of The Meridian as a self-contained HTML document.

The Meridian is the daily consolidation layer of the Ailux BD intelligence platform. It synthesizes every signal the platform has captured — live intel, company signals, trial updates, deals, catalysts — into a single coherent morning briefing. Use all of the data below.

EDITORIAL PLAN (developed before writing — follow it):
{plan_block}

INTELLIGENCE (last 48 hours — primary sources: Endpoints News, Fierce Biotech, direct company press releases):
{intel_block}

RECENT DEALS (last 7 days):
{deals_block}

UPCOMING CATALYSTS:
{catalysts_block}

COMPANY INTELLIGENCE (live state from dashboard company cards):
{signals_block}

GRAPH INTELLIGENCE (stored entity relationships — who is active where, mechanism convergence, confirmed competitive pairs):
{graph_block}

CLINICAL TRIAL TRACKER (recent updates from dashboard trial panel):
{trials_block}

AILUX CONTEXT:
{ailux_block}

## Today's Patient Intelligence Context
{patient_context_block}

─────────────────────────────────────────────
SECTION STRUCTURE (build exactly this architecture):

1. LEAD — No section header. 3–5 paragraphs. Open with the editorial thesis in the first sentence — a claim, not a summary. Build the argument across paragraphs. Weave the day's most important stories into a single thematic arc. No bullet points. This is the intellectual core of the issue.

2. MECHANISM INTELLIGENCE — One subsection per target/pathway with meaningful news. Header: name the mechanism with a subtitle that argues something (e.g., "TL1A: Setting the Monospecific Ceiling" not "TL1A Update"). Each subsection: 2–4 paragraphs of analysis + one BD Lens callout. Link source URLs inline as anchor tags.

3. CLINICAL INFLECTION POINTS — Only if there are meaningful data readouts, enrollment milestones, or trial events that change the prior on a mechanism or asset. If today has no genuine clinical news, omit this section entirely rather than pad it.

4. BD & DEAL WATCH — If there are recent deals. For each deal: what was the strategic logic, what does the pricing signal about asset valuation, who is now foreclosed from this asset. Go beyond describing the deal to arguing its implications.

5. CATALYST WATCH — Always include. HTML table with columns: Event | Asset | Area | Expected | Significance. Order by date ascending.

6. CLOSING NOTE — 2–3 sentences in italic. End on a forward-looking observation or open question, not a summary of what was just written.

─────────────────────────────────────────────
4-LAYER NARRATIVE FORMAT — mandatory for any drug event, clinical trial result, or deal:
When writing about any drug event, clinical trial result, or deal involving a drug in the IBD, atopy, TED, FcRn, T-cell, or GI oncology space, apply the 4-layer format:
1. What the molecule does (1 sentence)
2. Who the patient is and what they face (2-3 sentences)
3. What the mechanism means for the patient's daily life (1-2 sentences)
4. What this means for BD strategy and deal value (1-2 sentences)

─────────────────────────────────────────────
BD LENS FORMAT — use this HTML for every BD Lens callout:
<div class="bd-lens">
  <p class="label">BD LENS</p>
  <p>[Specific, actionable implication for Ailux's BD or clinical strategy. Not generic. Not "this is relevant." The actual inference a deal-room professional would draw.]</p>
</div>

─────────────────────────────────────────────
SOURCE LINKING — MANDATORY:
Every factual claim drawn from an intel item MUST be hyperlinked to its source_url using an inline anchor tag. This is non-negotiable.
- Format: <a href="SOURCE_URL">linked text</a>
- Link on the most specific noun — drug name, trial name, company name, or the key phrase — not generic words like "reported" or "announced"
- When Endpoints News or Fierce Biotech is the source, prefer those links over others covering the same story
- Aim for at minimum one hyperlink per paragraph. Dense sourcing is a feature, not clutter.
- If two sources cover the same claim, link both: "Endpoints <a href="...">reported</a> and Fierce <a href="...">confirmed</a>"
- Do NOT write "(Source: X)" footnotes. Links are inline, in context.

─────────────────────────────────────────────
HTML INSTRUCTIONS:
Return ONLY valid, complete HTML starting with <!DOCTYPE html>. Use this exact CSS verbatim:

* {{ box-sizing: border-box; }}
body {{ max-width: 860px; margin: 0 auto; padding: 36px 40px 80px; font-family: Georgia, 'Times New Roman', serif; font-size: 17px; color: #1a1a1a; line-height: 1.8; background: #fff; }}
h1 {{ color: #1a3f8f; font-size: 38px; margin: 0 0 6px 0; letter-spacing: -0.5px; }}
h2 {{ color: #1a3f8f; font-size: 22px; margin: 40px 0 4px 0; border-bottom: 1px solid #dce6f7; padding-bottom: 6px; }}
h3 {{ color: #1e3a5f; font-size: 18px; margin: 28px 0 6px 0; font-style: italic; }}
p {{ margin: 0 0 14px 0; }}
.dateline {{ font-family: Calibri, Helvetica, sans-serif; font-size: 14px; color: #3d5166; letter-spacing: 0.5px; text-transform: uppercase; }}
.tagline {{ font-style: italic; font-size: 16px; color: #3d5166; margin: 0 0 24px 0; }}
hr.thick {{ border: none; border-top: 3px solid #1a3f8f; margin: 10px 0 4px 0; }}
hr.thin {{ border: none; border-top: 1px solid #d0d9ea; margin: 4px 0 28px 0; }}
a {{ color: #1a3f8f; text-decoration: none; border-bottom: 1px solid #bfdbfe; }}
a:hover {{ border-bottom-color: #1a3f8f; }}
table {{ width: 100%; border-collapse: collapse; margin: 16px 0 24px 0; font-size: 14px; font-family: Calibri, Helvetica, sans-serif; }}
th {{ background: #1a3f8f; color: #fff; font-weight: 700; padding: 10px 12px; text-align: left; border: 1px solid #1a3f8f; }}
td {{ padding: 9px 12px; border: 1px solid #dce6f7; vertical-align: top; line-height: 1.5; }}
tr:nth-child(even) td {{ background: #f5f8ff; }}
.bd-lens {{ border-left: 4px solid #1a3f8f; background: #f0f4fb; padding: 18px 22px; margin: 22px 0; border-radius: 0 4px 4px 0; }}
.bd-lens p {{ margin: 0 0 6px 0; }}
.bd-lens p:last-child {{ margin: 0; }}
.label {{ font-family: Calibri, Helvetica, sans-serif; font-size: 11px; font-weight: 700; letter-spacing: 2px; color: #1a3f8f; text-transform: uppercase; margin-bottom: 8px !important; }}
.closing {{ font-style: italic; color: #3d5166; font-size: 16px; border-top: 1px solid #d0d9ea; padding-top: 20px; margin-top: 40px; }}
.issue-meta {{ font-family: Calibri, Helvetica, sans-serif; font-size: 13px; color: #64748b; margin-top: 60px; padding-top: 16px; border-top: 1px solid #e8edf5; }}

The header block must be exactly:
<p class="dateline">{date_dateline}</p>
<hr class="thick">
<h1>The Meridian</h1>
<p class="tagline">Intelligence for the intersection of science, strategy, and the examined life.</p>
<hr class="thin">

Return ONLY the HTML document. No markdown. No explanation outside the HTML."""


# ── First-mention hyperlink post-processor ───────────────────────────────────
def apply_first_mention_links(html: str, drugs: dict, companies: dict) -> str:
    """
    Post-processing pass: wrap the FIRST occurrence of each known drug name and
    company name in the HTML with the appropriate onclick modal link.  All
    subsequent occurrences are left as plain text.

    Rules:
      - Drug first mention  → <a href="#" onclick="openDrugModal('{id}')">name</a>
      - Company first mention → <a href="#" onclick="openCompanyModal('{id}')">name</a>
      - Names already inside an <a …> tag are skipped (source links placed by LLM).
      - Only replaces exact-case matches with word-boundary guards to avoid
        partial-word collisions (e.g. "Roche" inside "Roche/Genentech" is handled
        by longest-match ordering).
      - Skips tokens shorter than 4 characters to reduce false positives.

    This closes the gap when the LLM fails to apply the onclick pattern itself,
    and enforces the WRITING_STANDARDS first-mention rule programmatically.
    """
    import re as _re

    # Build sorted lists: longest name first to avoid partial replacements
    drug_entries = []
    for d in drugs.values():
        for field in [d.get("display_name"), d.get("name")]:
            if field and len(field) >= 4:
                drug_entries.append((field, d["id"]))
    # Deduplicate by name, keep first occurrence (display_name preferred)
    seen_drug_names = set()
    drug_entries_dedup = []
    for name, did in sorted(drug_entries, key=lambda x: -len(x[0])):
        if name.lower() not in seen_drug_names:
            seen_drug_names.add(name.lower())
            drug_entries_dedup.append((name, did))

    company_entries = []
    for c in companies.values():
        if c.get("name") and len(c["name"]) >= 4:
            company_entries.append((c["name"], c["id"]))
    company_entries = sorted(company_entries, key=lambda x: -len(x[0]))

    # Helper: check if position pos in html is already inside an <a> tag
    def _inside_anchor(html_str, pos):
        """Return True if pos falls between an <a …> and its </a>."""
        preceding = html_str[:pos]
        open_count  = len(_re.findall(r'<a[\s>]', preceding, _re.IGNORECASE))
        close_count = len(_re.findall(r'</a>', preceding, _re.IGNORECASE))
        return open_count > close_count

    def _replace_first(html_str, token, replacement):
        """Replace the first word-boundary occurrence of token (case-sensitive)
        that is NOT already inside an anchor tag."""
        pattern = _re.compile(r'(?<![a-zA-Z0-9\-])' + _re.escape(token) + r'(?![a-zA-Z0-9\-])')
        for m in pattern.finditer(html_str):
            if not _inside_anchor(html_str, m.start()):
                return html_str[:m.start()] + replacement + html_str[m.end():]
        return html_str  # no eligible occurrence found

    # Apply drug links
    drug_linked = set()
    for name, did in drug_entries_dedup:
        if name.lower() not in drug_linked:
            link = f'<a href="#" onclick="openDrugModal(\'{did}\')">{name}</a>'
            new_html = _replace_first(html, name, link)
            if new_html is not html:  # replacement was made
                html = new_html
                drug_linked.add(name.lower())

    # Apply company links
    co_linked = set()
    for name, cid in company_entries:
        if name.lower() not in co_linked:
            link = f'<a href="#" onclick="openCompanyModal(\'{cid}\')">{name}</a>'
            new_html = _replace_first(html, name, link)
            if new_html is not html:
                html = new_html
                co_linked.add(name.lower())

    log(f"First-mention links applied: {len(drug_linked)} drugs, {len(co_linked)} companies")
    return html


# ── Generate HTML with Claude Opus (two passes) ──────────────────────────────
def generate_editorial_plan(date_long, intel_block, deals_block, ailux_block,
                             prior_block, signals_block="", graph_block="",
                             patient_context_block=""):
    """Pass 1: produce a tight editorial plan before writing a word of prose."""
    prompt = PLAN_PROMPT.format(
        date_long             = date_long,
        intel_block           = intel_block,
        deals_block           = deals_block,
        ailux_block           = ailux_block,
        prior_block           = prior_block,
        signals_block         = signals_block,
        graph_block           = graph_block or "(Graph context unavailable)",
        patient_context_block = patient_context_block or "(No patient intelligence context available)",
    )
    log("Pass 1 — generating editorial plan (Opus)…")
    resp = client.messages.create(
        model      = "claude-opus-4-6",
        max_tokens = 1500,
        system     = SYSTEM_PROMPT,
        messages   = [{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip()
    log(f"Editorial plan: {resp.usage.input_tokens:,} in / {resp.usage.output_tokens:,} out")

    # Parse JSON — strip markdown fencing if present
    cleaned = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE).replace("```", "").strip()
    try:
        plan = json.loads(cleaned)
    except json.JSONDecodeError:
        log("Plan JSON parse failed — using raw text")
        plan = {"thesis": raw, "sections": ["Mechanism Intelligence", "BD & Deal Watch", "Catalyst Watch"]}
    return plan


def format_plan_block(plan):
    """Convert the parsed editorial plan into a readable block for the draft prompt."""
    lines = []
    if plan.get("thesis"):
        lines.append(f"EDITORIAL THESIS: {plan['thesis']}")
    if plan.get("signal_items"):
        lines.append("\nSIGNAL ITEMS (prioritise these):")
        for item in plan["signal_items"]:
            lines.append(f"  • {item}")
    if plan.get("noise_items"):
        lines.append("\nNOISE (handle briefly or skip):")
        for item in plan["noise_items"]:
            lines.append(f"  • {item}")
    if plan.get("connections"):
        lines.append("\nNON-OBVIOUS CONNECTIONS (make these explicit in the writing):")
        for c in plan["connections"]:
            lines.append(f"  • {c}")
    if plan.get("bd_implications"):
        lines.append("\nBD IMPLICATIONS FOR AILUX (ground the BD Lens callouts here):")
        for imp in plan["bd_implications"]:
            lines.append(f"  • {imp}")
    if plan.get("absences"):
        lines.append(f"\nNOTABLE ABSENCE: {plan['absences']}")
    if plan.get("continuity_threads"):
        lines.append("\nCONTINUITY THREADS (connect today's issue to prior coverage):")
        for t in plan["continuity_threads"]:
            lines.append(f"  • {t}")
    if plan.get("sections"):
        lines.append(f"\nSECTIONS TO INCLUDE: {', '.join(plan['sections'])}")
    return "\n".join(lines)


def generate_html(intel, deals, catalysts, drugs, companies, ailux_positions,
                  recent_issues, company_signals, trials,
                  graph_active_in=None, graph_targets=None, graph_competes=None):
    now = datetime.datetime.utcnow()
    date_long     = now.strftime("%A, %B %-d, %Y")
    week_num      = now.isocalendar()[1]
    date_dateline = f"{now.strftime('%A')} · {now.strftime('%B %-d')} · W{week_num} · {now.year}"

    # Enrich intel with live drug/company context
    enriched_intel = enrich_intel_with_drug_context(intel, drugs, companies)

    # Build patient intelligence context for all areas represented in today's intel.
    # This block is passed to both API passes (plan + draft) so the LLM has
    # verified disease burden data and does not need to hallucinate statistics.
    patient_context = build_patient_context_block(enriched_intel) if PATIENT_INTEL_AVAILABLE else ""

    intel_block     = build_intel_block(enriched_intel)
    deals_block     = build_deals_block(deals)
    catalysts_block = build_catalysts_block(catalysts)
    ailux_block     = build_ailux_block(ailux_positions)
    prior_block     = build_prior_coverage_block(recent_issues)
    signals_block   = build_company_signals_block(company_signals)
    trials_block    = build_trials_block(trials)
    graph_block     = build_graph_block(
        graph_active_in or {},
        graph_targets   or {},
        graph_competes  or [],
    )

    # Pass 1: editorial plan — includes company signals + graph for landscape context
    plan = generate_editorial_plan(date_long, intel_block, deals_block,
                                   ailux_block, prior_block, signals_block,
                                   graph_block=graph_block,
                                   patient_context_block=patient_context)
    plan_block = format_plan_block(plan)

    # ── Persist Pass 1 plan before Pass 2 so it is never lost ────────────────
    # This closes the editorial feedback gap: the plan's editorial judgments
    # (what matters, what is noise, what connections exist) are now queryable.
    _plan_intel_ids  = [it["id"] for it in intel if it.get("id")]
    _plan_company_ids = _extract_company_ids_from_plan(plan, intel)
    _content_fingerprint = _compute_content_fingerprint(_plan_intel_ids, _plan_company_ids)
    log(f"Pass 1 plan persisted: {len(_plan_company_ids)} companies · fingerprint={_content_fingerprint[:12]}…")

    # Pass 2: full draft
    prompt = DRAFT_PROMPT.format(
        date_long             = date_long,
        date_dateline         = date_dateline,
        plan_block            = plan_block,
        intel_block           = intel_block,
        deals_block           = deals_block,
        catalysts_block       = catalysts_block,
        ailux_block           = ailux_block,
        signals_block         = signals_block,
        trials_block          = trials_block,
        graph_block           = graph_block,
        patient_context_block = patient_context or "(No patient intelligence context available)",
    )

    log("Pass 2 — generating full Meridian draft (Opus)…")
    resp = client.messages.create(
        model      = "claude-opus-4-6",
        max_tokens = 16000,
        system     = SYSTEM_PROMPT,
        messages   = [{"role": "user", "content": prompt}],
    )
    html = resp.content[0].text.strip()
    log(f"Full draft: {resp.usage.input_tokens:,} in / {resp.usage.output_tokens:,} out → {len(html):,} chars")

    # Strip markdown fencing if model wraps it
    if "```" in html:
        html = re.sub(r"^```[a-z]*\n?", "", html, flags=re.MULTILINE)
        html = html.replace("```", "")

    # Ensure all links open in a new tab (iframe navigation guard)
    if "<base " not in html:
        html = html.replace("<head>", '<head>\n<base target="_blank" rel="noopener">', 1)

    # Apply first-mention hyperlinks for drug and company names.
    # This enforces the WRITING_STANDARDS rule programmatically: first occurrence
    # of each known entity gets an onclick modal link; subsequent occurrences are
    # plain text.  Runs after the LLM draft so the LLM's own source hyperlinks
    # (which already sit inside <a> tags) are never double-wrapped.
    html = apply_first_mention_links(html, drugs, companies)

    return html, plan, _plan_company_ids, _content_fingerprint


# ── Editorial plan helpers ────────────────────────────────────────────────────

def _extract_company_ids_from_plan(plan: dict, intel: list) -> list:
    """
    Extract company IDs from the editorial plan for persistence.
    Combines companies mentioned in signal_items with primary_company_id
    from featured intel items.
    Returns a deduplicated list of company ID strings.
    """
    company_ids = set()

    # Pull from plan sections (signal items often name companies)
    # We use the intel primary_company_id as the canonical source since
    # plan signal_items are free-text and not FK-linked.
    intel_map = {str(it.get("id")): it for it in intel}
    for item_ref in plan.get("signal_items", []):
        # signal_items are free-text descriptions — scan for known company slugs
        for it in intel:
            if it.get("primary_company_id") and any(
                str(it["id"])[:8] in item_ref or
                (it.get("headline","")[:20]).lower() in item_ref.lower()
                for _ in [1]  # single iteration, just for short-circuit eval
            ):
                company_ids.add(it["primary_company_id"])

    # Also include primary_company_id from all featured intel
    # (this is the most reliable source since it's FK-linked)
    for it in intel:
        if it.get("primary_company_id"):
            company_ids.add(it["primary_company_id"])

    return sorted(company_ids)


def _compute_content_fingerprint(intel_ids: list, company_ids: list) -> str:
    """
    SHA-256 fingerprint of the intel + company set for this issue.
    Enables repeat-story detection: if today's fingerprint matches a
    recent issue's fingerprint, the same stories are being featured again.
    """
    canonical = "|".join(sorted(str(i) for i in intel_ids)) + "##" + \
                "|".join(sorted(str(c) for c in company_ids))
    return hashlib.sha256(canonical.encode()).hexdigest()


# ── Persist issue to Supabase archive ────────────────────────────────────────
def save_to_supabase(html_content: str, intel: list, date_str: str,
                     plan: dict = None, company_ids: list = None,
                     content_fingerprint: str = None):
    """Upsert the generated issue into meridian_issues for the archive.

    Persists:
      - body_html: the full HTML output (Pass 2)
      - plan_json: the editorial plan from Pass 1 (E8 — editorial loop persistence)
      - intel_ids: IDs of intel items that fed this issue
      - company_ids: companies featured (derived from plan + intel attribution)
      - content_fingerprint: SHA-256 hash for repeat-story detection

    Uses check-then-patch/insert to avoid PostgREST merge-duplicates ambiguity
    (default conflict resolution is on primary key, not issue_date).
    """
    title     = f"The Meridian — {datetime.datetime.utcnow().strftime('%B %-d, %Y')}"
    intel_ids = [it["id"] for it in intel if it.get("id")]
    now_str   = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build the payload with all new fields
    base_payload = {
        "title":               title,
        "body_html":           html_content,
        "intel_ids":           intel_ids,
        "updated_at":          now_str,
    }
    if plan is not None:
        base_payload["plan_json"] = plan
    if company_ids is not None:
        base_payload["company_ids"] = company_ids
    if content_fingerprint is not None:
        base_payload["content_fingerprint"] = content_fingerprint

    # ── Repeat-story detection ───────────────────────────────────────────────
    # If today's fingerprint matches a recent issue, log a warning.
    # Does not block publication — editorial judgement required.
    if content_fingerprint:
        try:
            cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
            dup_r = requests.get(
                f"{SUPABASE_URL}/rest/v1/meridian_issues",
                params={"select": "issue_date,content_fingerprint",
                        "issue_date": f"gte.{cutoff}",
                        "content_fingerprint": f"eq.{content_fingerprint}"},
                headers=SB_HEADERS,
            )
            dups = dup_r.json() if dup_r.status_code == 200 else []
            dups = [d for d in dups if d.get("issue_date") != date_str]
            if dups:
                log(f"⚠ REPEAT DETECTION: fingerprint matches {dups[0]['issue_date']} — same stories as a recent issue")
                base_payload["repeat_of_issue_date"] = dups[0]["issue_date"]
        except Exception as dup_e:
            log(f"Repeat detection check error (non-fatal): {dup_e}")

    try:
        # Check whether a row already exists for today
        chk = requests.get(
            f"{SUPABASE_URL}/rest/v1/meridian_issues",
            params={"select": "id", "issue_date": f"eq.{date_str}"},
            headers=SB_HEADERS,
        )
        existing = chk.json() if chk.status_code == 200 else []

        if existing:
            # PATCH the existing row in-place
            row_id = existing[0]["id"]
            r = requests.patch(
                f"{SUPABASE_URL}/rest/v1/meridian_issues",
                params={"id": f"eq.{row_id}"},
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                json=base_payload,
            )
            verb = "Updated"
        else:
            # INSERT brand-new row
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/meridian_issues",
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                json={"issue_date": date_str, **base_payload},
            )
            verb = "Inserted"

        if r.status_code in (200, 201, 204):
            log(f"{verb} issue {date_str} in Supabase meridian_issues ✓ (plan_json={'yes' if plan else 'no'}, fingerprint={content_fingerprint[:12] if content_fingerprint else 'none'}…)")
        else:
            log(f"Supabase save warning {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log(f"Supabase save error (non-fatal): {e}")


# ── Commit HTML to GitHub Pages via blob API ─────────────────────────────────
def deploy_to_github(html_content, filename="meridian_today.html"):
    api = f"https://api.github.com/repos/{GITHUB_REPO}"

    ref_r = requests.get(f"{api}/git/ref/heads/main", headers=GH_HEADERS)
    ref_r.raise_for_status()
    head_sha = ref_r.json()["object"]["sha"]

    commit_r = requests.get(f"{api}/git/commits/{head_sha}", headers=GH_HEADERS)
    commit_r.raise_for_status()
    base_tree_sha = commit_r.json()["tree"]["sha"]

    blob_r = requests.post(f"{api}/git/blobs", headers=GH_HEADERS, json={
        "content":  base64.b64encode(html_content.encode()).decode(),
        "encoding": "base64",
    })
    blob_r.raise_for_status()
    blob_sha = blob_r.json()["sha"]

    tree_r = requests.post(f"{api}/git/trees", headers=GH_HEADERS, json={
        "base_tree": base_tree_sha,
        "tree": [{"path": filename, "mode": "100644", "type": "blob", "sha": blob_sha}],
    })
    tree_r.raise_for_status()
    new_tree_sha = tree_r.json()["sha"]

    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    commit_post = requests.post(f"{api}/git/commits", headers=GH_HEADERS, json={
        "message": f"Meridian issue {today} [auto]",
        "tree":    new_tree_sha,
        "parents": [head_sha],
    })
    commit_post.raise_for_status()
    new_commit_sha = commit_post.json()["sha"]

    patch_r = requests.patch(f"{api}/git/refs/heads/main", headers=GH_HEADERS, json={
        "sha": new_commit_sha, "force": False,
    })
    patch_r.raise_for_status()
    log(f"Deployed {filename} → commit {new_commit_sha[:7]}")


# ── Editorial → Enrichment Priority Bump ─────────────────────────────────────
def bump_editorial_priority(company_ids: list, boost: int = 10):
    """
    Bump priority_score for companies featured in today's Meridian.

    Meridian editorial judgment is the strongest signal for BD relevance.
    If a company appears in the briefing, it should be among the first to
    re-enrich. This function finds the company's research_queue row and
    applies a +boost to priority_score, capped at 100.

    Falls back gracefully: if research_queue doesn't have a row for a company,
    no error is raised.
    """
    if not company_ids:
        return

    bumped = []
    errors = []
    for co_id in company_ids:
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/research_queue",
                headers=SB_HEADERS,
                params={"company_id": f"eq.{co_id}", "select": "id,company_id,priority_score", "limit": "1"},
                timeout=10,
            )
            rows = r.json() if r.status_code == 200 else []
            if not rows:
                continue  # Company not in research_queue — skip silently

            row = rows[0]
            current_score = row.get("priority_score") or 0
            new_score     = min(100, current_score + boost)

            patch_r = requests.patch(
                f"{SUPABASE_URL}/rest/v1/research_queue",
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                params={"id": f"eq.{row['id']}"},
                json={"priority_score": new_score, "updated_at": datetime.datetime.utcnow().isoformat()},
                timeout=10,
            )
            if patch_r.status_code in (200, 204):
                bumped.append(f"{co_id}:{current_score}→{new_score}")
        except Exception as e:
            errors.append(f"{co_id}: {e}")

    if bumped:
        log(f"Editorial priority bumps (+{boost}): {', '.join(bumped)}")
    if errors:
        log(f"Priority bump errors (non-fatal): {'; '.join(errors)}")


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log(f"=== Meridian Writer — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ===")

    # Fetch all data sources — the full dashboard state feeds the Meridian
    intel                              = fetch_recent_intel(hours_back=48)
    deals                              = fetch_recent_deals(days_back=7)
    catalysts                          = fetch_upcoming_catalysts()
    drugs, companies                   = fetch_drug_context()
    ailux_positions                    = fetch_ailux_position()
    recent_issues                      = fetch_recent_meridian_issues(n=7)
    company_signals                    = fetch_company_signals()
    trials                             = fetch_recent_trials()
    graph_active_in, graph_targets, graph_competes = fetch_graph_context()

    log(f"Data assembled: {len(intel)} intel · {len(deals)} deals · {len(catalysts)} catalysts · "
        f"{len(company_signals)} signals · {len(trials)} trials · {len(recent_issues)} prior issues · "
        f"graph: {sum(len(v) for v in graph_active_in.values())} ACTIVE_IN / "
        f"{len(graph_targets)} TARGETS / {len(graph_competes)} COMPETES_WITH")

    if not intel:
        log("No intel found — writing placeholder issue.")
        html         = (
            "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>The Meridian</title></head>"
            "<body><h1 style='color:#1a3f8f;font-family:Georgia,serif'>The Meridian</h1>"
            f"<p style='font-family:Georgia,serif'>No significant biopharma intelligence collected in the last 48 hours "
            f"for today, {datetime.datetime.utcnow().strftime('%B %-d, %Y')}. "
            "Check back tomorrow.</p></body></html>"
        )
        plan                = None
        plan_company_ids    = []
        content_fingerprint = None
    else:
        html, plan, plan_company_ids, content_fingerprint = generate_html(
            intel, deals, catalysts, drugs, companies, ailux_positions,
            recent_issues, company_signals, trials,
            graph_active_in=graph_active_in,
            graph_targets=graph_targets,
            graph_competes=graph_competes,
        )

    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    save_to_supabase(html, intel, today,
                     plan=plan,
                     company_ids=plan_company_ids,
                     content_fingerprint=content_fingerprint)

    # ── Editorial → Enrichment Priority Bump ─────────────────────────────────
    # Companies featured in today's Meridian are the most BD-relevant right now.
    # Bump their priority_score in research_queue by +10 so the next enrichment
    # scheduler run picks them up first. This closes the editorial → enrichment
    # feedback loop: intelligence output feeds back into intelligence input priority.
    if plan_company_ids:
        bump_editorial_priority(plan_company_ids)

    deploy_to_github(html)
    log("=== Write complete ===")
