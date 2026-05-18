#!/usr/bin/env python3
"""
Meridian Writer — GitHub Actions edition
Reads biopharma intel from Supabase (last 24h), generates a full Meridian HTML
briefing using Claude Sonnet, and commits meridian_today.html to GitHub Pages.
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
        # Flatten area tags
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


# ── Build prompt data ────────────────────────────────────────────────────────
AREA_NAMES = {
    "tl1a":  "TL1A / IBD",
    "tslp":  "TSLP / Severe Asthma",
    "il4ra": "IL-4Rα / Atopy",
    "igf1r": "IGF1R / Thyroid Eye Disease",
    "fcrn":  "FcRn / IgG Autoimmune",
    "tcell": "T-cell / Treg Therapy",
}

WRITE_PROMPT = """You are the author of The Meridian, a high-quality Monday–Saturday morning intelligence briefing for the BD and strategy team at Ailux, an AI-native antibody design company. Ailux focuses on six therapeutic areas: TL1A (IBD), TSLP (asthma), IL-4Rα (atopy), IGF1R (thyroid eye disease), FcRn (IgG autoimmune), and T-cell/Treg therapy.

Today is {date_long}. Write today's complete issue of The Meridian as a self-contained HTML document.

INTELLIGENCE AVAILABLE TODAY:
{intel_block}

RECENT DEALS (last 7 days):
{deals_block}

UPCOMING CATALYSTS:
{catalysts_block}

WRITING INSTRUCTIONS:
- Open with a 2–4 paragraph editorial lede that weaves today's most important stories into a single thematic arc. This is the intellectual hook — write it like a sharp analyst who reads widely: science, strategy, geopolitics, business. No bullet points in the lede.
- For each focus area that has meaningful news, write a dedicated section with a bold H2 header, 2–4 paragraphs of analysis, and at minimum one "BD Lens" callout explaining what this means for Ailux's positioning. Link to source URLs where relevant.
- Include a "Catalyst Watch" section at the end as a compact HTML table listing upcoming readouts/filings.
- Include a "Deal Log" section if there are recent deals.
- Close with a 2–3 sentence "Closing Note" in italic.
- Tone: authoritative, precise, intellectually engaged. Not a press release summary. Provide synthesis and so-what analysis.
- Length: thorough but not padded — as long as the news warrants.

HTML INSTRUCTIONS:
Return ONLY valid, complete HTML starting with <!DOCTYPE html>. Use this exact CSS (copy it verbatim into the <style> block):

* {{ box-sizing: border-box; }}
body {{ max-width: 1500px; margin: 0 auto; padding: 36px 80px 60px; font-family: Georgia, 'Times New Roman', serif; font-size: 17px; color: #1a1a1a; line-height: 1.75; background: #fff; }}
h1 {{ color: #1a3f8f; font-size: 36px; margin: 0 0 6px 0; }}
h2 {{ color: #1a3f8f; font-size: 24px; margin: 30px 0 6px 0; }}
h3 {{ color: #3d5166; font-size: 19px; margin: 20px 0 8px 0; }}
p {{ margin: 0 0 12px 0; }}
.dateline {{ font-family: Calibri, Helvetica, sans-serif; font-size: 15px; color: #3d5166; }}
.tagline {{ font-style: italic; font-size: 16px; color: #3d5166; }}
hr.thick {{ border: none; border-top: 2.5px solid #1a3f8f; }}
hr.thin {{ border: none; border-top: 0.5px solid #ccc; }}
a {{ color: #1a3f8f; }}
table {{ width: 100%; border-collapse: collapse; margin: 14px 0; font-size: 15px; }}
th {{ background: #1a3f8f; color: #fff; font-family: Calibri, Helvetica, sans-serif; font-weight: bold; padding: 9px 10px; border: 1px solid #ccc; }}
td {{ padding: 9px 10px; border: 1px solid #ccc; line-height: 1.5; }}
.bd-lens {{ border-left: 4px solid #1a3f8f; background: #f0f4fb; padding: 16px 20px; margin: 18px 0; }}
.label {{ font-family: Calibri, Helvetica, sans-serif; font-size: 13px; font-weight: bold; letter-spacing: 1.5px; }}
.caption {{ font-style: italic; font-size: 14px; color: #3d5166; }}
.closing {{ font-style: italic; color: #3d5166; font-size: 16px; }}

The header block should be:
<p class="dateline">{date_dateline}</p>
<hr class="thick">
<h1>The Meridian</h1>
<p class="tagline">Intelligence for the intersection of science, strategy, and the examined life.</p>
<hr class="thin">

Return ONLY the HTML document. No markdown. No explanation outside the HTML."""


def build_intel_block(items):
    if not items:
        return "(No new intel items today)"
    lines = []
    for it in items:
        areas_str = ", ".join(AREA_NAMES.get(a, a) for a in it.get("areas", []))
        lines.append(
            f"[{it['importance'].upper()} | {it['intel_type']} | {areas_str}]\n"
            f"HEADLINE: {it['headline']}\n"
            f"DETAIL: {it['body']}\n"
            f"SOURCE: {it['source_name']} — {it['source_url']}\n"
            f"DATE: {it['intel_date']}"
        )
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
        )
    return "\n\n".join(lines)


def build_catalysts_block(cats):
    if not cats:
        return "(No upcoming catalysts on record)"
    lines = []
    for c in cats:
        lines.append(
            f"{c['catalyst_date']} | {AREA_NAMES.get(c['area_id'], c['area_id'])} | {c['significance'].upper()}\n"
            f"{c['label']}"
        )
    return "\n".join(lines)


# ── Generate HTML with Claude Sonnet ────────────────────────────────────────
def generate_html(intel, deals, catalysts):
    now = datetime.datetime.utcnow()
    date_long     = now.strftime("%A, %B %-d, %Y")
    week_num      = now.isocalendar()[1]
    date_dateline = f"{now.strftime('%A')} · {now.strftime('%B %-d')} · W{week_num} · {now.year}"

    prompt = WRITE_PROMPT.format(
        date_long     = date_long,
        date_dateline = date_dateline,
        intel_block    = build_intel_block(intel),
        deals_block    = build_deals_block(deals),
        catalysts_block= build_catalysts_block(catalysts),
    )

    log("Calling Claude Sonnet to generate Meridian HTML…")
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    html = resp.content[0].text.strip()
    # Strip markdown fencing if model wraps it
    if "```" in html:
        html = re.sub(r"^```[a-z]*\n?", "", html, flags=re.MULTILINE)
        html = html.replace("```", "")
    log(f"Generated {len(html):,} chars "
        f"(in={resp.usage.input_tokens:,} / out={resp.usage.output_tokens:,})")
    return html


# ── Commit HTML to GitHub Pages via blob API ─────────────────────────────────
def deploy_to_github(html_content, filename="meridian_today.html"):
    api = f"https://api.github.com/repos/{GITHUB_REPO}"

    # 1. Get current HEAD
    ref_r = requests.get(f"{api}/git/ref/heads/main", headers=GH_HEADERS)
    ref_r.raise_for_status()
    head_sha = ref_r.json()["object"]["sha"]

    # 2. Get base tree SHA
    commit_r = requests.get(f"{api}/git/commits/{head_sha}", headers=GH_HEADERS)
    commit_r.raise_for_status()
    base_tree_sha = commit_r.json()["tree"]["sha"]

    # 3. Create blob
    blob_r = requests.post(f"{api}/git/blobs", headers=GH_HEADERS, json={
        "content":  base64.b64encode(html_content.encode()).decode(),
        "encoding": "base64",
    })
    blob_r.raise_for_status()
    blob_sha = blob_r.json()["sha"]

    # 4. Create tree
    tree_r = requests.post(f"{api}/git/trees", headers=GH_HEADERS, json={
        "base_tree": base_tree_sha,
        "tree": [{"path": filename, "mode": "100644", "type": "blob", "sha": blob_sha}],
    })
    tree_r.raise_for_status()
    new_tree_sha = tree_r.json()["sha"]

    # 5. Create commit
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    commit_post = requests.post(f"{api}/git/commits", headers=GH_HEADERS, json={
        "message": f"Meridian issue {today} [auto]",
        "tree":    new_tree_sha,
        "parents": [head_sha],
    })
    commit_post.raise_for_status()
    new_commit_sha = commit_post.json()["sha"]

    # 6. Update ref
    patch_r = requests.patch(f"{api}/git/refs/heads/main", headers=GH_HEADERS, json={
        "sha": new_commit_sha, "force": False,
    })
    patch_r.raise_for_status()
    log(f"Deployed {filename} → commit {new_commit_sha[:7]}")


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log(f"=== Meridian Writer — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ===")

    intel     = fetch_recent_intel(hours_back=30)
    deals     = fetch_recent_deals(days_back=7)
    catalysts = fetch_upcoming_catalysts()

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
        html = generate_html(intel, deals, catalysts)

    deploy_to_github(html)
    log("=== Write complete ===")
