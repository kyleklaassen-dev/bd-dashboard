#!/usr/bin/env python3
"""
Meridian Writer — GitHub Actions edition
Reads biopharma intel from Supabase (last 24h), generates a full Meridian HTML
briefing using Claude Opus (two-pass: editorial plan → full draft), and commits
meridian_today.html to GitHub Pages.
Runs 6:30 AM ET Mon–Sat (10:30 UTC).
"""

import os, json, datetime, base64, re, time
import requests
import anthropic

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
def fetch_recent_intel(hours_back=30):
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
                "select": "id,name,display_name,company_id,stage,target,mechanism,overlap,partner_company,partnership_type,partnership_verified,indication_short",
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


def fetch_recent_meridian_issues(n=3):
    """Fetch recent Meridian issue titles to give the writer editorial continuity."""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/meridian_issues",
            headers=SB_HEADERS,
            params={
                "select": "issue_date,title",
                "order": "issue_date.desc",
                "limit": str(n),
            },
        )
        issues = r.json()
        log(f"Fetched {len(issues)} recent Meridian issues for continuity")
        return issues
    except Exception as e:
        log(f"Recent issues fetch error: {e}")
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
    """Give the writer a sense of what was covered recently to avoid repetition."""
    if not recent_issues:
        return "(No prior issue history available)"
    lines = [f"  {i['issue_date']}: {i['title']}" for i in recent_issues]
    return "Recent issues (avoid repeating without new development):\n" + "\n".join(lines)


# ── System prompt (editorial identity) ──────────────────────────────────────
SYSTEM_PROMPT = """You are the founding editor of The Meridian, a Monday–Saturday morning intelligence briefing published exclusively for the BD and strategy leadership of Ailux, an AI-native antibody design company.

YOUR READERS: PhD scientists who have published in Nature and NEJM. BD professionals who have closed nine-figure deals. They have already read the press releases. They do not need definitions of mechanisms, trial designs, or deal structures. They need the interpretive layer — the argument beneath the news.

YOUR EDITORIAL STANDARD:
- Every paragraph must contain one claim a smart, busy reader could not have made without reading this issue. If a paragraph only restates known facts, cut it or rewrite it.
- Never summarize what happened. Explain what it means and why it matters in the next 18 months.
- The BD Lens is not "this is relevant to Ailux." It is the specific implication for positioning, deal optionality, combination thesis, asset pricing, or clinical strategy — written at deal-room precision.
- When two stories connect non-obviously, make the connection explicit and argue it. That is where the value lives.
- When the news is quiet, say what is conspicuously absent and why that itself is signal. A mechanism with no news for three weeks when competitors are typically active is information.
- Be precise about mechanism. "IL-23 inhibition" is not acceptable. Specify the subunit, the pathway, the cell type, the downstream effect.
- Do not write "it remains to be seen." That hedge belongs in investor presentations, not intelligence briefings.
- Do not write "this space continues to evolve" or any equivalent platitude.

TONE: The writing of a scientist who also reads The Economist and thinks like a portfolio manager. Authoritative. Precise. Intellectually engaged. Occasionally pointed when the evidence warrants it."""


# ── Pass 1: Editorial planning ───────────────────────────────────────────────
PLAN_PROMPT = """Today is {date_long}.

You are planning today's issue of The Meridian before writing it. Read all available intelligence carefully, then produce a tight editorial plan.

INTELLIGENCE AVAILABLE:
{intel_block}

RECENT DEALS:
{deals_block}

PRIOR COVERAGE:
{prior_block}

AILUX CONTEXT:
{ailux_block}

Your editorial plan must answer:
1. THESIS: In one sentence, what is the single most important thing today's news collectively reveals about the competitive landscape? This becomes the editorial spine of the lede.
2. SIGNAL vs. NOISE: Which 3–5 items are genuinely significant and deserve analysis? Which are noise (announcements without substance, recycled data, obvious moves)?
3. CONNECTIONS: Identify 1–3 non-obvious connections between separate items. What do they point to together that neither suggests alone?
4. BD IMPLICATIONS: What are the 2–3 most specific implications for Ailux's BD strategy — not "this is relevant" but the actual tactical or positional inference?
5. ABSENCES: What notable development is conspicuously NOT in today's news that is worth flagging?
6. SECTION PLAN: Which sections should appear today? (Lead is always present. Others: Mechanism Intelligence / Clinical Inflection Points / BD & Deal Watch / Regulatory Watch.) Omit sections with nothing substantive to say.

Return your plan as JSON with keys: thesis, signal_items (list of headlines), noise_items (list of headlines), connections (list of strings), bd_implications (list of strings), absences (string), sections (list of section names)."""


# ── Pass 2: Full draft ───────────────────────────────────────────────────────
DRAFT_PROMPT = """Today is {date_long}. Write today's complete issue of The Meridian as a self-contained HTML document.

EDITORIAL PLAN (developed before writing — follow it):
{plan_block}

INTELLIGENCE:
{intel_block}

RECENT DEALS (last 7 days):
{deals_block}

UPCOMING CATALYSTS:
{catalysts_block}

AILUX CONTEXT:
{ailux_block}

─────────────────────────────────────────────
SECTION STRUCTURE (build exactly this architecture):

1. LEAD — No section header. 3–5 paragraphs. Open with the editorial thesis in the first sentence — a claim, not a summary. Build the argument across paragraphs. Weave the day's most important stories into a single thematic arc. No bullet points. This is the intellectual core of the issue.

2. MECHANISM INTELLIGENCE — One subsection per target/pathway with meaningful news. Header: name the mechanism with a subtitle that argues something (e.g., "TL1A: Setting the Monospecific Ceiling" not "TL1A Update"). Each subsection: 2–4 paragraphs of analysis + one BD Lens callout. Link source URLs inline as anchor tags.

3. CLINICAL INFLECTION POINTS — Only if there are meaningful data readouts, enrollment milestones, or trial events that change the prior on a mechanism or asset. If today has no genuine clinical news, omit this section entirely rather than pad it.

4. BD & DEAL WATCH — If there are recent deals. For each deal: what was the strategic logic, what does the pricing signal about asset valuation, who is now foreclosed from this asset. Go beyond describing the deal to arguing its implications.

5. CATALYST WATCH — Always include. HTML table with columns: Event | Asset | Area | Expected | Significance. Order by date ascending.

6. CLOSING NOTE — 2–3 sentences in italic. End on a forward-looking observation or open question, not a summary of what was just written.

─────────────────────────────────────────────
BD LENS FORMAT — use this HTML for every BD Lens callout:
<div class="bd-lens">
  <p class="label">BD LENS</p>
  <p>[Specific, actionable implication for Ailux's BD or clinical strategy. Not generic. Not "this is relevant." The actual inference a deal-room professional would draw.]</p>
</div>

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


# ── Generate HTML with Claude Opus (two passes) ──────────────────────────────
def generate_editorial_plan(date_long, intel_block, deals_block, ailux_block, prior_block):
    """Pass 1: produce a tight editorial plan before writing a word of prose."""
    prompt = PLAN_PROMPT.format(
        date_long   = date_long,
        intel_block  = intel_block,
        deals_block  = deals_block,
        ailux_block  = ailux_block,
        prior_block  = prior_block,
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
    if plan.get("sections"):
        lines.append(f"\nSECTIONS TO INCLUDE: {', '.join(plan['sections'])}")
    return "\n".join(lines)


def generate_html(intel, deals, catalysts, drugs, companies, ailux_positions, recent_issues):
    now = datetime.datetime.utcnow()
    date_long     = now.strftime("%A, %B %-d, %Y")
    week_num      = now.isocalendar()[1]
    date_dateline = f"{now.strftime('%A')} · {now.strftime('%B %-d')} · W{week_num} · {now.year}"

    # Enrich intel with live drug/company context
    enriched_intel = enrich_intel_with_drug_context(intel, drugs, companies)

    intel_block     = build_intel_block(enriched_intel)
    deals_block     = build_deals_block(deals)
    catalysts_block = build_catalysts_block(catalysts)
    ailux_block     = build_ailux_block(ailux_positions)
    prior_block     = build_prior_coverage_block(recent_issues)

    # Pass 1: editorial plan
    plan = generate_editorial_plan(date_long, intel_block, deals_block, ailux_block, prior_block)
    plan_block = format_plan_block(plan)

    # Pass 2: full draft
    prompt = DRAFT_PROMPT.format(
        date_long       = date_long,
        date_dateline   = date_dateline,
        plan_block      = plan_block,
        intel_block     = intel_block,
        deals_block     = deals_block,
        catalysts_block = catalysts_block,
        ailux_block     = ailux_block,
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

    return html


# ── Persist issue to Supabase archive ────────────────────────────────────────
def save_to_supabase(html_content: str, intel: list, date_str: str):
    """Upsert the generated issue into meridian_issues for the archive.

    Uses check-then-patch/insert to avoid PostgREST merge-duplicates ambiguity
    (default conflict resolution is on primary key, not issue_date).
    """
    title     = f"The Meridian — {datetime.datetime.utcnow().strftime('%B %-d, %Y')}"
    intel_ids = [it["id"] for it in intel if it.get("id")]
    now_str   = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

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
                json={"title": title, "body_html": html_content,
                      "intel_ids": intel_ids, "updated_at": now_str},
            )
            verb = "Updated"
        else:
            # INSERT brand-new row
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/meridian_issues",
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                json={"issue_date": date_str, "title": title,
                      "body_html": html_content, "intel_ids": intel_ids,
                      "updated_at": now_str},
            )
            verb = "Inserted"

        if r.status_code in (200, 201, 204):
            log(f"{verb} issue {date_str} in Supabase meridian_issues ✓")
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


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log(f"=== Meridian Writer — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ===")

    # Fetch all data sources in parallel-ish order
    intel          = fetch_recent_intel(hours_back=30)
    deals          = fetch_recent_deals(days_back=7)
    catalysts      = fetch_upcoming_catalysts()
    drugs, companies = fetch_drug_context()
    ailux_positions  = fetch_ailux_position()
    recent_issues    = fetch_recent_meridian_issues(n=4)

    if not intel:
        log("No intel found — writing placeholder issue.")
        html = (
            "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>The Meridian</title></head>"
            "<body><h1 style='color:#1a3f8f;font-family:Georgia,serif'>The Meridian</h1>"
            f"<p style='font-family:Georgia,serif'>No significant biopharma intelligence collected in the last 24 hours "
            f"for today, {datetime.datetime.utcnow().strftime('%B %-d, %Y')}. "
            "Check back tomorrow.</p></body></html>"
        )
    else:
        html = generate_html(intel, deals, catalysts, drugs, companies, ailux_positions, recent_issues)

    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    save_to_supabase(html, intel, today)
    deploy_to_github(html)
    log("=== Write complete ===")
