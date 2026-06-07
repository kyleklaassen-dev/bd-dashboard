#!/usr/bin/env python3
"""
Meridian Research Pipeline — GitHub Actions edition
Fetches biopharma news from RSS feeds, enriches high-priority articles with
full-text content, extracts structured intel using Claude Sonnet (grounded in
Ailux competitive context), and writes to Supabase.
Runs 2:00 AM ET Mon–Sat (06:00 UTC).
"""

import os, json, hashlib, datetime, time, re, sys
import feedparser
import requests
import anthropic
from bs4 import BeautifulSoup

# CompanyIdentityResolver — canonical company name → company_id resolution
# Falls back gracefully if the module isn't available (e.g. first deploy)
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from company_identity_resolver import CompanyIdentityResolver
    _RESOLVER_AVAILABLE = True
except ImportError:
    _RESOLVER_AVAILABLE = False

# ── Credentials ─────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SUPABASE_URL      = os.environ["SUPABASE_URL"]
SUPABASE_KEY      = os.environ["SUPABASE_SERVICE_KEY"]

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}
SB_UPSERT = {**SB_HEADERS, "Prefer": "resolution=ignore-duplicates,return=representation"}

# ── Focus-area keyword map ───────────────────────────────────────────────────
FOCUS_AREAS = {
    "tl1a": ["TL1A", "TL-1A", "TNFSF15", "tulisokibart", "afimkibart", "duvakitug",
              "izokibep", "SIM0709", "HXN-1003", "RO7837195", "pf-07261271", "fg-m701",
              "IBD", "ulcerative colitis", "Crohn's disease", "bispecific TL1A",
              "IL-23 TL1A", "anti-TL1A"],
    "tslp":  ["TSLP", "tezepelumab", "astegolimab", "itepekimab", "Airsupra",
              "severe asthma", "COPD biologic", "alarmin asthma", "eosinophilic asthma"],
    "il4ra": ["IL-4Rα", "IL-4R alpha", "IL4RA", "dupilumab", "Dupixent",
              "atopic dermatitis", "prurigo nodularis", "eczema biologic",
              "allergic conjunctivitis biologic"],
    "igf1r": ["IGF1R", "IGF-1R", "IGF-1 receptor", "thyroid eye disease", "TED",
              "Graves orbitopathy", "teprotumumab", "Tepezza", "veligrotug",
              "orbital decompression", "proptosis trial"],
    "fcrn":  ["FcRn", "neonatal Fc receptor", "efgartigimod", "rozanolixizumab",
              "nipocalimab", "batoclimab", "Vyvgart", "IgG reduction therapy",
              "myasthenia gravis biologic", "CIDP FcRn", "pemphigus vulgaris FcRn"],
    "tcell": ["regulatory T cell", "Treg therapy", "CAR-Treg", "Treg infusion",
              "lupus cell therapy", "SLE cellular", "myositis T cell", "immune reset",
              "tolerance induction", "Sonoma Biotherapeutics", "Quell Therapeutics",
              "GigaGen", "Abata Therapeutics"],
}

# ── RSS feed list ────────────────────────────────────────────────────────────
# Primary sources first — fetched first, always full-text, always pass relevance filter
# ── Tier 1: Primary trade press — fetched first, full-text always, pass relevance filter ──
PRIMARY_FEEDS = [
    "https://endpts.com/feed/",
    "https://www.fiercebiotech.com/rss/xml",
]

# ── Tier 2: Direct company IR / press release feeds — fetched second, full-text always ──
# News straight from company websites is high-signal and often breaks before trade press.
COMPANY_FEEDS = [
    "https://investors.abbvie.com/rss/news-releases",              # AbbVie
    "https://www.roche.com/media/releases/med-cor-rss.xml",        # Roche
    "https://investor.lilly.com/rss/news-releases",                # Eli Lilly
    "https://investor.regeneron.com/rss/news-releases",            # Regeneron
    "https://investor.jnj.com/rss/news-releases",                  # J&J
    "https://www.astrazeneca.com/media-centre/press-releases.rss", # AstraZeneca
    "https://www.sanofi.com/en/media-room/press-releases.rss",     # Sanofi
    "https://www.novartis.com/news/media-releases/rss",            # Novartis
    "https://www.ucb.com/media/press-releases/rss",                # UCB
    "https://www.bmsstories.com/feed/",                            # BMS
    "https://news.pfizer.com/press-releases/rss",                  # Pfizer
    "https://www.merck.com/news/rss/press-releases/",              # Merck US
    "https://www.teva.com/media-room/press-releases/rss",          # Teva
    "https://www.boehringer-ingelheim.com/media/press-releases.rss", # BI
]

# ── Tier 3: Broader secondary sources ──
# NOTE: PRNewswire removed — too noisy (general press releases contaminate batches).
# Company IR feeds (COMPANY_FEEDS above) already cover all legit press releases.
# BusinessWire kept only if it surfaces conference/clinical data; remove if noisy.
SECONDARY_FEEDS = [
    "https://www.biopharmadive.com/feeds/news/",
    "https://www.statnews.com/feed/",
    "https://www.genengnews.com/feed/",
    "https://www.biospace.com/rss/news",
    "https://www.nature.com/nm/rss/current",
    "https://www.nejm.org/action/showFeed?jc=nejm&type=etoc&feed=rss",
    "https://www.businesswire.com/rss/home/?rss=G7",
]

RSS_FEEDS = PRIMARY_FEEDS + COMPANY_FEEDS + SECONDARY_FEEDS

# Canonical source name substrings for matching — used for full-text and priority logic
PRIMARY_SOURCE_NAMES = {"endpoints news", "fierce biotech"}
COMPANY_SOURCE_DOMAINS = {
    "abbvie", "roche", "lilly", "regeneron", "jnj", "janssen",
    "astrazeneca", "sanofi", "novartis", "ucb", "bms", "pfizer",
    "merck", "teva", "boehringer",
}

# Sources that are worth fetching full-text for (paywalls aside)
# prnewswire removed — too noisy to justify fetch budget
FULL_TEXT_SOURCES = {
    "endpoints news", "fierce biotech",
    "abbvie", "roche", "lilly", "regeneron", "johnson", "astrazeneca",
    "sanofi", "novartis", "ucb", "bristol", "pfizer", "merck", "teva",
    "boehringer", "stat news", "biopharmadive",
    "nature medicine", "new england journal of medicine",
}

# Title keywords that flag an article as high-priority for full-text fetch
HIGH_PRIORITY_TITLE_KEYWORDS = [
    "phase 3", "phase iii", "phase 2", "phase ii", "phase 1", "phase i",
    "trial results", "data readout", "primary endpoint", "topline", "pivotal",
    "approval", "approved", "fda", "ema", "bla", "nda", "breakthrough",
    "acquisition", "acquires", "acquired", "merger",
    "billion", "million deal", "license", "partnership", "co-develop",
    "bispecific", "tl1a", "il-23", "tslp", "il-4r", "fcrn", "igf1r",
]

# Compact Ailux context for extraction — keeps the model grounded without
# overloading the prompt (full context lives in write_meridian.py)
AILUX_CONTEXT_COMPACT = """
AILUX STRATEGIC CONTEXT (use to make body analysis specific, not generic):
- Ailux lead asset: ALX001, TL1A × IL-23p19 bispecific antibody for IBD (UC + CD). 2+2 symmetric bispecific, DR3-specific TL1A arm, p19-selective IL-23 arm, YTE Fc. FIH Q4 2027.
- TL1A class: tulisokibart (Merck, Ph3 ATLAS-UC ~Nov 2026 readout) + afimkibart (Roche, Ph3 Jan 2027) are the class-defining monospecifics. Merck reads out first.
- IL-23p19 class: risankizumab (AbbVie, approved), mirikizumab (Lilly, approved), guselkumab (J&J, CD Ph3). Proven SOC.
- RO7837195 (Roche/Pfizer): IL-23p40 × TL1A bispecific — most direct competitor to ALX001; targets p40 (blocks both IL-12 + IL-23), unlike ALX001's p19 selectivity.
- TNFSF15 CDx: TAG haplotype FAILED as predictive biomarker for tulisokibart. ALX001 Phase 2 should enroll unselected.
- BD priorities: combination data showing bispecific superiority; deal structures signaling asset valuations; early-entry signals in less-crowded Ailux areas (IGF1R/TED, FcRn, TSLP, Treg).
""".strip()


def log(msg):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ── Full-text fetching ───────────────────────────────────────────────────────
def is_primary_source(article):
    """Return True if this article is from Endpoints News or Fierce Biotech."""
    source_lower = (article.get("source", "")).lower()
    return any(s in source_lower for s in PRIMARY_SOURCE_NAMES)

def is_company_source(article):
    """Return True if this article comes directly from a tracked company's IR/news feed."""
    source_lower = (article.get("source", "")).lower()
    url_lower    = (article.get("url", "")).lower()
    combined     = source_lower + " " + url_lower
    return any(d in combined for d in COMPANY_SOURCE_DOMAINS)

def is_direct_source(article):
    """Return True if article is from any top-tier source (trade press or direct company news)."""
    return is_primary_source(article) or is_company_source(article)

def is_high_priority(article):
    """Return True if this article warrants full-text fetching."""
    title_lower = (article.get("title", "")).lower()
    source_lower = (article.get("source", "")).lower()
    title_hit = any(kw in title_lower for kw in HIGH_PRIORITY_TITLE_KEYWORDS)
    source_hit = any(s in source_lower for s in FULL_TEXT_SOURCES)
    return title_hit or source_hit


def fetch_full_text(url, timeout=10):
    """
    Fetch and extract the main body text from an article URL.
    Returns cleaned text string, or None on failure.
    Caps output at 4000 chars to keep extraction prompts reasonable.
    """
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "MeridianBot/2.0 (research pipeline; not archiving)"},
            timeout=timeout,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove noise elements
        for tag in soup(["script", "style", "nav", "header", "footer",
                         "aside", "form", "iframe", "noscript", "button"]):
            tag.decompose()

        # Try common article body selectors first
        body_text = ""
        for selector in ["article", '[class*="article-body"]', '[class*="content-body"]',
                         "main", '[role="main"]', ".post-content", ".entry-content"]:
            el = soup.select_one(selector)
            if el:
                body_text = el.get_text(separator=" ", strip=True)
                break

        if not body_text:
            body_text = soup.get_text(separator=" ", strip=True)

        # Clean whitespace
        body_text = re.sub(r"\s+", " ", body_text).strip()
        return body_text[:4000] if body_text else None

    except Exception as e:
        return None


def enrich_with_full_text(articles, max_fetches=40):
    """
    Full-text enrichment with three-pass priority:

    Pass 1 — Tier 1 (Endpoints News, Fierce Biotech): always fetched, no cap.
    Pass 2 — Tier 2 (direct company IR feeds): always fetched, no cap.
    Pass 3 — Secondary sources: fetched up to remaining cap for high-priority articles.

    Articles tagged with ['full_text'] = text string on success.
    """
    fetched = 0

    # Pass 1: primary trade press — no cap
    for article in articles:
        if is_primary_source(article):
            text = fetch_full_text(article["url"])
            if text:
                article["full_text"] = text
                fetched += 1
                log(f"  [ENDPOINTS/FIERCE] {article['url'][:70]}… ({len(text)} chars)")
            time.sleep(0.4)

    # Pass 2: direct company IR news — no cap
    for article in articles:
        if is_company_source(article) and "full_text" not in article:
            text = fetch_full_text(article["url"])
            if text:
                article["full_text"] = text
                fetched += 1
                log(f"  [COMPANY IR] {article['url'][:70]}… ({len(text)} chars)")
            time.sleep(0.4)

    # Pass 3: secondary sources up to cap
    for article in articles:
        if fetched >= max_fetches:
            break
        if is_direct_source(article):
            continue  # already handled
        if is_high_priority(article) and "full_text" not in article:
            text = fetch_full_text(article["url"])
            if text:
                article["full_text"] = text
                fetched += 1
                log(f"  [SECONDARY] {article['url'][:70]}… ({len(text)} chars)")
            time.sleep(0.4)

    log(f"Full-text enrichment complete: {fetched} articles fetched")


# ── Step 1: Fetch feeds ──────────────────────────────────────────────────────
def fetch_feeds(hours_back=48):
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=hours_back)
    articles = []
    seen_urls = set()

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "MeridianBot/1.0"})
            count = 0
            for entry in feed.entries:
                link = entry.get("link", "")
                if not link or link in seen_urls:
                    continue
                seen_urls.add(link)

                # Parse publication date
                pub = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        pub = datetime.datetime(*entry.published_parsed[:6])
                    except Exception:
                        pass

                if pub and pub < cutoff:
                    continue

                articles.append({
                    "title":     entry.get("title", "").strip(),
                    "url":       link,
                    "summary":   (entry.get("summary", "") or entry.get("description", ""))[:1200].strip(),
                    "published": pub.strftime("%Y-%m-%d") if pub else None,
                    "source":    feed.feed.get("title", url),
                })
                count += 1
            log(f"  {url.split('/')[2]}: {count} articles")
        except Exception as e:
            log(f"  Feed error [{url}]: {e}")
        time.sleep(0.3)

    log(f"Total fetched: {len(articles)} articles")
    return articles


# ── Step 2: Filter for focus-area relevance ──────────────────────────────────
def filter_relevant(articles):
    """
    Keep articles that match focus-area keywords.
    Primary source articles (Endpoints News, Fierce Biotech) always pass through —
    the extraction LLM will discard irrelevant ones, but we don't want the keyword
    filter dropping legitimate biopharma coverage just because it misses a keyword.
    """
    relevant = []
    passthrough = 0
    for a in articles:
        text = (a["title"] + " " + a["summary"]).lower()
        matched = [area for area, kws in FOCUS_AREAS.items()
                   if any(kw.lower() in text for kw in kws)]
        if matched:
            a["areas"] = matched
            relevant.append(a)
        elif is_direct_source(a):
            # Direct sources (Endpoints, Fierce, company IR) always pass through.
            # The extraction LLM will discard truly irrelevant articles.
            a["areas"] = []
            relevant.append(a)
            passthrough += 1
    log(f"Relevant: {len(relevant)} / {len(articles)} articles "
        f"({passthrough} direct-source passthrough, no keyword match)")
    return relevant


# ── Step 3: Dedup against Supabase ──────────────────────────────────────────
def get_existing_urls():
    """Fetch source_urls already in intel table from last 7 days."""
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/intel",
            headers=SB_HEADERS,
            params={"select": "source_url", "intel_date": f"gte.{cutoff}"},
        )
        return {row["source_url"] for row in r.json() if row.get("source_url")}
    except Exception as e:
        log(f"Dedup fetch error: {e}")
        return set()


# ── Step 4: Extract intel with Claude Sonnet ─────────────────────────────────
EXTRACT_PROMPT = """You are an analyst for a biopharma BD intelligence platform. Your extractions feed a daily briefing read by PhD scientists and senior BD professionals at Ailux — they already know the mechanisms and deal structures. The value you add is precision and strategic inference, not description.

FOCUS AREAS:
- tl1a: TL1A antibodies for IBD (UC + Crohn's)
- tslp: TSLP antibodies for severe asthma / COPD
- il4ra: IL-4Rα antibodies for atopic dermatitis / atopy
- igf1r: IGF1R antibodies for thyroid eye disease (TED / Graves' orbitopathy)
- fcrn: FcRn inhibitors for autoimmune IgG diseases (MG, pemphigus, CIDP)
- tcell: T-cell engineering / Treg therapy for immune reset

{ailux_context}

ARTICLES TO ANALYZE:
{articles}

For each article with meaningful intelligence relevant to a focus area, extract one record.

FIELD INSTRUCTIONS:
- "area_id": one of: tl1a | tslp | il4ra | igf1r | fcrn | tcell
- "intel_type": news | data | deal | regulatory | conference
- "importance": high (Ph3 data/approval/major deal) | medium (Ph2/IND/partnership) | low (preclinical/minor)
- "headline": ≤120 chars — state what happened, be specific (drug name, company, data readout, deal size)
- "body": 3–5 sentences. Do NOT summarize the article. Instead:
    (1) State the mechanistic or clinical fact precisely (which target, which endpoint, which patient population, what effect size if available).
    (2) Explain what this changes in the competitive landscape — what was true before, what is now different.
    (3) State the specific implication for the TL1A/bispecific/Ailux competitive thesis, or for the relevant Ailux focus area.
    Write for readers who do not need definitions. Be precise. Be direct. No hedging language.
- "source_url": exact article URL
- "source_name": publication name
- "intel_date": YYYY-MM-DD or null
- "drug_names": array of drug/molecule names mentioned ([] if none)
- "company_names": array of company names ([] if none)
- "is_deal": true only if this reports a partnership, license, M&A, or collaboration
- "deal_from": acquirer/licensee company name if is_deal else null
- "deal_to": licensor/target company name if is_deal else null
- "deal_upfront_usd_m": upfront payment in USD millions (number or null)
- "deal_total_usd_m": total deal value in USD millions including milestones (number or null)
- "deal_type": acquisition | license | collab | option — or null
- "has_catalyst": true if article mentions an upcoming clinical/regulatory event with a specific timeframe
- "catalyst_label": specific label — drug name + event type + timeframe (e.g. "tulisokibart ATLAS-UC Ph3 primary ~Nov 2026")
- "catalyst_date": approximate date string like "Q3 2026" or "Nov 2026" or null
- "significance": high | medium | low

Skip earnings calls, macro news, and speculative commentary with no new factual content.
Skip articles where the focus-area relevance is clearly tangential (e.g., a general immunology paper with no clinical or commercial implications for these programs).

PAYWALLED / SHORT CONTENT: If the full text is missing or very brief (< 200 chars) but the headline clearly signals a relevant clinical event (trial data, approval, deal, IND filing), extract a record using the headline and any available summary. Set importance conservatively. Do NOT skip solely because content is short — headline intelligence is still intelligence.

GOVERNANCE RULES FOR DEAL EXTRACTION:
- deal_from = licensee/acquirer (the company gaining rights). deal_to = licensor/originator (the company giving rights).
- The drug's originating company (inventor/developer) is always deal_to in a licensing deal.
  Example: AbbVie licensed ABBV-701 from FutureGen → deal_from="abbvie", deal_to="futuregen".
- For acquisitions: deal_from = acquirer, deal_to = acquired company.
- Never swap deal_from and deal_to just because the acquirer is larger or more prominent.
- source_url must be the actual article URL — always include it for deal records.

Return ONLY a valid JSON array. No markdown, no explanation, no wrapper text."""


def extract_intel(articles):
    all_intel = []
    batch_size = 6  # Smaller batches — Sonnet writes richer body text, needs more headroom

    total_batches = (len(articles) + batch_size - 1) // batch_size
    for i in range(0, len(articles), batch_size):
        batch_num = i // batch_size + 1
        log(f"  [EXTRACT {batch_num}/{total_batches}] articles {i+1}–{min(i+batch_size, len(articles))} of {len(articles)}")
        batch = articles[i:i + batch_size]
        batch_text = "\n\n---\n\n".join(
            _format_article_for_extraction(a) for a in batch
        )

        try:
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=6000,
                messages=[{"role": "user", "content": EXTRACT_PROMPT.format(
                    articles=batch_text,
                    ailux_context=AILUX_CONTEXT_COMPACT,
                )}],
            )
            text = resp.content[0].text.strip()
            # Strip markdown fencing if present
            if "```" in text:
                text = re.sub(r"^```[a-z]*\n?", "", text, flags=re.MULTILINE)
                text = text.replace("```", "").strip()
            intel = json.loads(text)
            all_intel.extend(intel)
            log(f"  Batch {i // batch_size + 1}: extracted {len(intel)} items "
                f"({resp.usage.input_tokens:,} in / {resp.usage.output_tokens:,} out)")
        except json.JSONDecodeError as e:
            log(f"  JSON parse error batch {i // batch_size + 1}: {e}")
        except Exception as e:
            log(f"  Extraction error batch {i // batch_size + 1}: {e}")
        time.sleep(0.8)

    log(f"Total extracted: {len(all_intel)} intel items")
    return all_intel


def _format_article_for_extraction(a):
    """Format one article for the extraction prompt, preferring full_text over summary."""
    content_label = "FULL TEXT" if a.get("full_text") else "SUMMARY"
    content = a.get("full_text") or a.get("summary", "")
    return (
        f"TITLE: {a['title']}\n"
        f"URL: {a['url']}\n"
        f"SOURCE: {a['source']}\n"
        f"DATE: {a['published'] or 'unknown'}\n"
        f"AREAS MATCHED: {', '.join(a['areas'])}\n"
        f"{content_label}: {content}"
    )


# ── Step 5: Write to Supabase ────────────────────────────────────────────────
def sb_post(table, record):
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=SB_HEADERS, json=record)
    if r.status_code not in (200, 201):
        log(f"  Supabase error [{table}]: {r.status_code} {r.text[:200]}")
        return None
    data = r.json()
    return data[0] if data else None


def stamp_system_status_research(note=None):
    """Best-effort: stamp system_status.last_research_at so the dashboard's
    freshness banner reflects the latest research run. Never fatal."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rec = {"last_research_at": now_iso, "updated_at": now_iso,
           "last_pipeline_label": "research"}
    if note:
        rec["note"] = note[:500]
    try:
        r = requests.patch(f"{SUPABASE_URL}/rest/v1/system_status",
                           headers=SB_HEADERS, params={"id": "eq.1"},
                           json=rec, timeout=15)
        if r.status_code in (200, 204):
            log("  system_status stamped (research)")
        else:
            log(f"  system_status stamp HTTP {r.status_code} (non-fatal)")
    except Exception as e:
        log(f"  system_status stamp failed (non-fatal): {e}")


# ── Company name → ID lookup ─────────────────────────────────────────────────
# Known aliases that differ from the simple lowercase ID
COMPANY_ALIASES = {
    "johnson & johnson":     "jnj",
    "j&j":                   "jnj",
    "j & j":                 "jnj",
    "eli lilly":              "lilly",
    "roche":                  "roche",
    "roche/genentech":        "roche",
    "genentech":              "roche",
    "boehringer ingelheim":   "boehringer",
    "boehringer":             "boehringer",
    "bristol myers squibb":   "bms",
    "bristol-myers squibb":   "bms",
    "astrazeneca":            "astrazeneca",
    "abbvie":                 "abbvie",
    "merck":                  "merck",
    "merck & co":             "merck",
    "merck & co.":            "merck",
    "generate:biomedicines":  "generate",
    "harbour biomed":         "harbourbiomed",
    "santa ana bio":          "santaana",
    "futuregen biopharmaceutical": "futuregen",
    "nanjing leads":          "leads",
    "shandong boan":          "shboan",
    "novamab":                "novamab",
}


def get_company_map():
    """Fetch all companies from Supabase. Returns dict: lowercase_name → id."""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/companies",
            headers=SB_HEADERS,
            params={"select": "id,name"},
        )
        rows = r.json()
        cmap = {}
        for row in rows:
            cmap[row["id"].lower()] = row["id"]        # id → id (e.g. "argenx" → "argenx")
            cmap[row["name"].lower()] = row["id"]      # full name → id (e.g. "argenx" → "argenx")
        # Merge in hardcoded aliases
        cmap.update(COMPANY_ALIASES)
        return cmap
    except Exception as e:
        log(f"Company map fetch error: {e}")
        return {}


def resolve_company_id(name, company_map):
    """Try to resolve a company name string to a Supabase company id."""
    lc = name.strip().lower()
    if lc in company_map:
        return company_map[lc]
    # Partial / substring match
    for key, cid in company_map.items():
        if len(lc) >= 4 and (lc in key or key in lc):
            return cid
    return None


def write_to_supabase(intel_items, company_map=None, resolver=None):
    inserted_intel = 0
    inserted_deals = 0
    inserted_catalysts = 0
    skipped_intel = 0
    skipped_deals = 0
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    total = len(intel_items)

    # ── Pre-fetch existing headlines (last 120 days) to prevent nightly duplication ──
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=120)).strftime("%Y-%m-%d")
    existing_intel_headlines: set[str] = set()
    existing_deal_headlines:  set[str] = set()
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/intel?select=headline&intel_date=gte.{cutoff}&limit=2000",
            headers=SB_HEADERS, timeout=10)
        if r.status_code == 200:
            existing_intel_headlines = {row["headline"] for row in r.json() if row.get("headline")}
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/deals?select=headline&deal_date=gte.{cutoff}&limit=1000",
            headers=SB_HEADERS, timeout=10)
        if r.status_code == 200:
            existing_deal_headlines = {row["headline"] for row in r.json() if row.get("headline")}
        log(f"  Dedup cache: {len(existing_intel_headlines)} intel, {len(existing_deal_headlines)} deal headlines loaded")
    except Exception as e:
        log(f"  WARN: dedup pre-fetch failed ({e}); continuing without dedup guard")

    for idx, item in enumerate(intel_items, 1):
        log(f"  [WRITE {idx}/{total}] {item.get('area_id','?')} — {(item.get('headline') or '')[:80]}")
        # ── Intel dedup check (exact + fuzzy similarity) ─────────────────
        intel_headline_key = (item.get("headline") or "")[:200]
        if intel_headline_key in existing_intel_headlines:
            log(f"  [SKIP dupe intel] {intel_headline_key[:80]}")
            skipped_intel += 1
            continue
        # Fuzzy dedup: skip if any existing headline is >82% similar
        import difflib as _dl
        _h_lower = intel_headline_key.lower()
        _fuzzy_dupe = any(
            _dl.SequenceMatcher(None, _h_lower, _ex.lower()).ratio() > 0.82
            for _ex in existing_intel_headlines
        )
        if _fuzzy_dupe:
            log(f"  [SKIP fuzzy-dupe intel] {intel_headline_key[:80]}")
            skipped_intel += 1
            continue
        existing_intel_headlines.add(intel_headline_key)
        # ── Intel record ──────────────────────────────────────────────────
        intel_rec = {
            "intel_date":  item.get("intel_date") or today,
            "headline":    intel_headline_key,
            "body":        item.get("body") or "",
            "source_url":  item.get("source_url") or "",
            "source_name": item.get("source_name") or "",
            "verified":    False,
            "importance":  item.get("importance") or "medium",
            "intel_type":  item.get("intel_type") or "news",
        }
        row = sb_post("intel", intel_rec)
        if not row:
            continue
        intel_id = row["id"]
        inserted_intel += 1

        # ── intel_areas junction ──────────────────────────────────────────
        sb_post("intel_areas", {"intel_id": intel_id, "area_id": item["area_id"]})

        # ── intel_companies junction + primary_company_id ─────────────────
        company_names = item.get("company_names") or []
        written_co_ids = set()
        primary_co_id: str | None = None
        for co_name in company_names:
            if not co_name:
                continue
            if resolver:
                co_id = resolver.resolve(co_name, source="research.py")
            else:
                co_id = resolve_company_id(co_name, company_map or {})
            if co_id and co_id not in written_co_ids:
                sb_post("intel_companies", {"intel_id": intel_id, "company_id": co_id})
                written_co_ids.add(co_id)
                if primary_co_id is None:
                    primary_co_id = co_id  # first resolved company = primary
        # Patch primary_company_id onto the intel row if we resolved at least one
        if primary_co_id:
            import requests as _req
            _req.patch(
                f"{SUPABASE_URL}/rest/v1/intel?id=eq.{intel_id}",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json={"primary_company_id": primary_co_id},
                timeout=5,
            )

        # ── Deal record ───────────────────────────────────────────────────
        if item.get("is_deal") and item.get("deal_from"):
            deal_headline_key = (item.get("headline") or "")[:200]
            if deal_headline_key in existing_deal_headlines:
                log(f"  [SKIP dupe deal] {deal_headline_key[:80]}")
                skipped_deals += 1
            else:
                # Fuzzy dedup for deals too
                import difflib as _dl2
                _dh_lower = deal_headline_key.lower()
                _deal_fuzzy = any(
                    _dl2.SequenceMatcher(None, _dh_lower, _ex.lower()).ratio() > 0.82
                    for _ex in existing_deal_headlines
                )
                if _deal_fuzzy:
                    log(f"  [SKIP fuzzy-dupe deal] {deal_headline_key[:80]}")
                    skipped_deals += 1
                else:
                    existing_deal_headlines.add(deal_headline_key)
                deal_date = item.get("intel_date") or today
                deal_rec = {
                    "deal_date":       deal_date,
                    "deal_date_label": datetime.datetime.strptime(deal_date[:7], "%Y-%m").strftime("%b %Y")
                                       if deal_date else today[:7],
                    "from_company":    item.get("deal_from") or "",
                    "to_company":      item.get("deal_to") or "",
                    "area_id":         item["area_id"],
                    "deal_type":       item.get("deal_type") or "license",
                    "upfront_usd_m":   item.get("deal_upfront_usd_m"),
                    "total_usd_m":     item.get("deal_total_usd_m"),
                    "headline":        deal_headline_key,
                    "detail":          item.get("body") or "",
                    "source_url":      item.get("source_url") or "",
                    "ailux_signal":    "",
                }
                if sb_post("deals", deal_rec):
                    inserted_deals += 1

        # ── Catalyst record ───────────────────────────────────────────────
        if item.get("has_catalyst") and item.get("catalyst_label"):
            cat_date_str = item.get("catalyst_date") or ""
            # Parse sort_date (best effort)
            sort_date = today
            try:
                import re
                m = re.search(r"(20\d\d)", cat_date_str)
                year = int(m.group(1)) if m else datetime.datetime.utcnow().year
                months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
                          "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12,
                          "q1":1,"q2":4,"q3":7,"q4":10,"h1":1,"h2":7}
                for k, v in months.items():
                    if k in cat_date_str.lower():
                        sort_date = f"{year}-{v:02d}-01"
                        break
            except Exception:
                pass

            cat_rec = {
                "catalyst_date":  cat_date_str,
                "sort_date":      sort_date,
                "label":          (item.get("catalyst_label") or "")[:200],
                "area_id":        item["area_id"],
                "significance":   item.get("significance") or "medium",
                "catalyst_type":  "readout",
                "notes":          item.get("body") or "",
                "resolved":       False,
            }
            if sb_post("catalysts", cat_rec):
                inserted_catalysts += 1

    log(f"Wrote → intel: {inserted_intel}, deals: {inserted_deals}, catalysts: {inserted_catalysts} "
        f"| Skipped dupes → intel: {skipped_intel}, deals: {skipped_deals} "
        f"(company junction rows written inline)")


# ── New-source sweep helpers ─────────────────────────────────────────────────

def write_to_research_queue(item: dict) -> None:
    """
    Write a single item to the research_queue table.

    Expected keys (matching coverage_gap_finder.py schema):
        entity_type  — "trial" | "company" | "drug"
        entity_id    — globally unique identifier (NCT ID, company slug, etc.)
        gap_type     — e.g. "new_trial_registration" | "sec_8k_filing"
        priority     — "P0" | "P1" | "P2"
        reason       — human-readable context string (truncated to 1000 chars)
        source       — script name
        status       — "pending"

    Uses on_conflict=entity_id,gap_type so repeated nightly runs update
    the existing row rather than accumulating duplicates.
    """
    payload = json.dumps([{
        "entity_type": item.get("entity_type", "trial"),
        "entity_id":   str(item.get("entity_id", ""))[:200],
        "gap_type":    item.get("gap_type", "new_source_signal"),
        "priority":    item.get("priority", "P1"),
        "reason":      str(item.get("reason", ""))[:1000],
        "source":      item.get("source", "research_sweep"),
        "status":      "pending",
    }]).encode()

    req = requests.post(
        f"{SUPABASE_URL}/rest/v1/research_queue",
        data=payload,
        headers={
            **SB_HEADERS,
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        params={"on_conflict": "entity_id,gap_type"},
        timeout=10,
    )
    if req.status_code not in (200, 201):
        log(f"  research_queue write error: {req.status_code} {req.text[:150]}")


def run_new_source_sweep() -> None:
    """
    Phase 6 (nightly supplement): new-data-source sweep.

    Runs AFTER the main RSS→extract→write pipeline. Calls:
      1. ctgov_poller.poll_ctgov_new_registrations — newly registered trials
         by mechanism keyword. Writes to research_queue (entity_type=trial).
      2. edgar_fetcher.process_company — 8-K filings for the 14 tracked
         companies. Writes to source_documents via edgar_fetcher's own writer.

    Neither step requires the Anthropic API; both are pure fetch→parse→store.
    """
    log("--- Phase 6: New-source sweep (CT.gov + EDGAR) ---")

    # ── 6a: CT.gov new registrations ──────────────────────────────────────
    try:
        # Import here to avoid circular deps and make the import optional
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from ctgov_poller import poll_ctgov_new_registrations, write_trial_to_research_queue
        new_trials = poll_ctgov_new_registrations(days_back=7)
        log(f"  CT.gov: {len(new_trials)} new trial registrations found")
        written = 0
        for trial in new_trials:
            ok = write_trial_to_research_queue(trial, SUPABASE_KEY)
            if ok:
                written += 1
        log(f"  CT.gov: {written}/{len(new_trials)} written to research_queue")
    except Exception as exc:
        log(f"  CT.gov sweep error: {exc}")

    # ── 6b: EDGAR 8-K sweep (14 tracked companies, 14-day window) ─────────
    try:
        from edgar_fetcher import TRACKED_COMPANIES, process_company
        log(f"  EDGAR: scanning {len(TRACKED_COMPANIES)} companies for 8-Ks (14 days back)")
        edgar_saved = 0
        for company in TRACKED_COMPANIES:
            saved = process_company(
                company,
                form_types=["8-K"],
                days_back=14,
                service_key=SUPABASE_KEY,
                dry_run=False,
            )
            edgar_saved += len(saved)
            time.sleep(1.0)  # EDGAR courtesy delay between companies
        log(f"  EDGAR: {edgar_saved} relevant 8-K documents saved to source_documents")
    except Exception as exc:
        log(f"  EDGAR sweep error: {exc}")

    log("--- Phase 6 complete ---")


# ── GAP 1 FIX: PK/PD queue processor ─────────────────────────────────────────

PKPD_CLAUDE_MODEL = "claude-haiku-4-5-20251001"

PKPD_EXTRACTION_PROMPT = """\
Extract PK/PD parameters from this abstract. Return JSON only — no markdown, no explanation.
Use null for any field not mentioned. Confidence should reflect how clearly the value appears
(1.0 = explicit numeric in results section, 0.5 = approximate or inferred, 0.0 = not found).

{
  "half_life_h": null,
  "half_life_unit": null,
  "cmax_value": null,
  "cmax_unit": null,
  "auc_value": null,
  "auc_unit": null,
  "bioavailability_pct": null,
  "vd_value": null,
  "vd_unit": null,
  "clearance_value": null,
  "clearance_unit": null,
  "route": null,
  "species": null,
  "confidence": 0.0
}

Rules:
- half_life_unit: use "h" for hours, "d" for days, "wk" for weeks
- route: MUST be exactly ONE of: "SC", "IV", "oral", or null — never a combination like "SC/IV"
  If multiple routes are studied, pick the PRIMARY route or null
- species: "human", "mouse", "monkey", "rat", or null
- If half_life_h is given in days in the abstract, convert to hours (multiply by 24) and set half_life_unit="h"
- Only extract values explicitly stated — do not infer or estimate
- confidence above 0.5 means the abstract explicitly reports the parameter with a numeric value

Abstract:
{abstract_text}"""


def fetch_pubmed_abstract(pmid: str, timeout: int = 10) -> str:
    """
    Fetch abstract text for a PubMed PMID via the NCBI efetch API.
    Returns empty string on failure.
    """
    try:
        url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pubmed&id={pmid}&rettype=abstract&retmode=text"
        )
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Meridian-BD/1.0"})
        if resp.status_code == 200:
            return resp.text
    except Exception as exc:
        log(f"  PubMed fetch error (PMID {pmid}): {exc}")
    return ""


def extract_pk_with_claude(abstract_text: str) -> dict:
    """
    Use Claude claude-haiku-4-5-20251001 to extract PK parameters from a PubMed abstract.
    Returns parsed dict with extracted parameters; empty dict on failure or low confidence.
    Only returns fields where confidence > 0.5.
    """
    if not abstract_text or len(abstract_text.strip()) < 50:
        return {}

    # Truncate to ~4000 chars to keep costs minimal
    abstract_trimmed = abstract_text[:4000]

    prompt = PKPD_EXTRACTION_PROMPT.replace("{abstract_text}", abstract_trimmed)

    try:
        resp = client.messages.create(
            model=PKPD_CLAUDE_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)
        confidence = float(parsed.get("confidence", 0.0))

        if confidence <= 0.5:
            return {}

        # Build output dict — only non-null fields that map to db columns
        result = {}

        if parsed.get("half_life_h") is not None:
            result["half_life_hours"] = float(parsed["half_life_h"])

        if parsed.get("bioavailability_pct") is not None:
            result["bioavailability_pct"] = float(parsed["bioavailability_pct"])

        if parsed.get("cmax_value") is not None:
            result["cmax_ng_ml"] = float(parsed["cmax_value"])

        if parsed.get("auc_value") is not None:
            result["auc_inf_ng_hr_ml"] = float(parsed["auc_value"])

        if parsed.get("vd_value") is not None:
            result["volume_distribution_l"] = float(parsed["vd_value"])

        if parsed.get("clearance_value") is not None:
            result["clearance_ml_hr_kg"] = float(parsed["clearance_value"])

        # dose_route is the column name in drug_pk_parameters (not "route")
        # Only allow exact values: SC, IV, oral — reject combined strings like "SC/IV"
        route_val = str(parsed.get("route") or "").strip()
        if route_val in ("SC", "IV", "oral"):
            result["dose_route"] = route_val

        # species is not a column in drug_pk_parameters — embed in notes instead
        if parsed.get("species"):
            result["_species"] = str(parsed["species"])

        result["_confidence"] = confidence  # internal — not written to db column
        return result

    except json.JSONDecodeError as exc:
        log(f"    Claude PK extraction: JSON parse error — {exc}")
        return {}
    except Exception as exc:
        log(f"    Claude PK extraction error: {exc}")
        return {}


def process_pkpd_queue() -> int:
    """
    GAP 1 FIX: Process research_queue items where context_type='pkpd_literature'.
    Uses Claude claude-haiku-4-5-20251001 for structured extraction (replaces regex).

    For each item:
      1. Extract PMID from the reason field.
      2. Fetch the PubMed abstract via NCBI efetch.
      3. Send abstract to Claude — get structured PK parameter JSON.
      4. If confidence > 0.5, write to drug_pk_parameters.
      5. Mark the research_queue item as assigned_status='completed'.

    Returns count of items processed.
    """
    log("--- Phase 7: PK/PD queue processor (Claude-powered) ---")

    # Fetch ALL pkpd queue items regardless of status — reset completed so they
    # get reprocessed by Claude (regex run may have missed parameters).
    queue_items = []
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/research_queue",
            headers=SB_HEADERS,
            params={
                "context_type": "eq.pkpd_literature",
                "select": "id,entity_id,reason,assigned_status",
                "limit": "100",
            },
            timeout=15,
        )
        if r.status_code == 200:
            queue_items = r.json()
        else:
            log(f"  research_queue fetch error: {r.status_code}")
    except Exception as exc:
        log(f"  PK/PD queue fetch error: {exc}")
        return 0

    log(f"  Found {len(queue_items)} PK/PD queue items (all statuses)")
    if not queue_items:
        return 0

    processed = 0
    pk_written = 0
    NOW_ISO = datetime.datetime.utcnow().isoformat()

    for item in queue_items:
        item_id = item["id"]
        drug_id = item.get("entity_id", "")
        reason = item.get("reason", "")

        # Extract PMID from reason text: "PMID 39073504"
        pmid_match = re.search(r"PMID\s+(\d+)", reason)
        if not pmid_match:
            log(f"  No PMID found in reason for {drug_id}: {reason[:80]}")
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/research_queue",
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                params={"id": f"eq.{item_id}"},
                json={"assigned_status": "completed"},
                timeout=10,
            )
            processed += 1
            continue

        pmid = pmid_match.group(1)
        source_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

        log(f"  Processing {drug_id} — PMID {pmid}")
        time.sleep(0.4)  # NCBI courtesy delay

        abstract = fetch_pubmed_abstract(pmid)
        if not abstract:
            log(f"    No abstract returned for PMID {pmid}")
        else:
            pk_params = extract_pk_with_claude(abstract)
            confidence = pk_params.pop("_confidence", 0.0)

            if pk_params:
                log(f"    Claude extracted PK params (conf={confidence:.2f}): {list(pk_params.keys())}")
                # _species is not a column — move it to notes
                species_note = pk_params.pop("_species", None)
                notes_str = f"Claude-extracted from PubMed PMID {pmid} (conf={confidence:.2f})"
                if species_note:
                    notes_str += f"; species={species_note}"
                pk_rec = {
                    "drug_id":      drug_id,
                    # source_type CHECK constraint: Phase1|Phase2|Phase3|label|abstract|poster|investor_PR|ClinicalTrials
                    "source_type":  "abstract",
                    "source_url":   source_url,
                    "notes":        notes_str,
                    "verified":     False,
                    **pk_params,
                }
                try:
                    pr = requests.post(
                        f"{SUPABASE_URL}/rest/v1/drug_pk_parameters",
                        headers={**SB_HEADERS, "Prefer": "resolution=ignore-duplicates,return=minimal"},
                        json=pk_rec,
                        timeout=15,
                    )
                    if pr.status_code in (200, 201, 204):
                        pk_written += 1
                        log(f"    ✓ Wrote drug_pk_parameters for {drug_id} (PMID {pmid})")
                    else:
                        log(f"    ✗ Write failed: {pr.status_code} {pr.text[:100]}")
                except Exception as exc:
                    log(f"    Write error: {exc}")
            else:
                log(f"    No PK parameters found by Claude (confidence too low or none present) — PMID {pmid}")

        # Mark research_queue item as completed
        try:
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/research_queue",
                headers={**SB_HEADERS, "Prefer": "return=minimal"},
                params={"id": f"eq.{item_id}"},
                json={"assigned_status": "completed", "last_action_at": NOW_ISO},
                timeout=10,
            )
        except Exception:
            pass

        processed += 1
        time.sleep(0.2)  # avoid Claude rate-limit on haiku

    log(f"  PK/PD queue: {processed} items processed, {pk_written} drug_pk_parameters rows written")
    log("--- Phase 7 complete ---")
    return processed


# ── Phase 9: Asset differentiation profile staleness check ───────────────────
# Queries asset_differentiation_profiles for last_updated timestamps, then
# checks intelligence_discoveries and research_queue for recent competitor
# events touching ALX001/ALX002/ALX005 competitor programs.
# Flags profiles where a relevant competitor update is newer than last_updated
# and writes a research_queue item for human review.

ASSET_COMPETITOR_MAP = {
    "alx001": ["SPY072", "tulisokibart", "RO7837195", "SIM0709", "duvakitug", "risankizumab", "mirikizumab"],
    "alx002": ["KT501", "CLN-978", "HXN-1031", "CND460", "belimumab", "anifrolumab"],
    "alx005": ["efgartigimod", "rozanolixizumab", "nipocalimab", "IMVT-1402", "batoclimab"],
}

def _run_asset_profile_staleness_check():
    """Check if any asset_differentiation_profiles need KOL Q&A refresh based on recent competitor intel."""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    # Fetch current profile timestamps
    prof_resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/asset_differentiation_profiles",
        headers=headers,
        params={"select": "program_id,last_updated"},
        timeout=15,
    )
    if prof_resp.status_code != 200:
        log(f"  Phase 9: could not fetch profiles ({prof_resp.status_code})")
        return

    profiles = {p["program_id"]: p["last_updated"] for p in prof_resp.json()}

    # Fetch recent intelligence_discoveries (last 14 days)
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    intel_resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/intelligence_discoveries",
        headers=headers,
        params={"select": "drug_name,discovery_text,created_at", "created_at": f"gte.{cutoff}", "limit": "200"},
        timeout=15,
    )
    recent_intel = intel_resp.json() if intel_resp.status_code == 200 else []

    flagged = []
    for program_id, competitors in ASSET_COMPETITOR_MAP.items():
        profile_ts = profiles.get(program_id)
        if not profile_ts:
            continue
        for item in recent_intel:
            drug = (item.get("drug_name") or "").lower()
            text = (item.get("discovery_text") or "").lower()
            created = item.get("created_at", "")
            # Check if this intel mentions a competitor for this program
            if any(c.lower() in drug or c.lower() in text for c in competitors):
                # Check if intel is newer than profile
                if created > profile_ts:
                    flagged.append({
                        "program_id": program_id,
                        "competitor_trigger": drug or "unknown",
                        "intel_date": created,
                        "profile_updated": profile_ts,
                    })
                    break  # one flag per program is enough

    if flagged:
        log(f"  Phase 9: {len(flagged)} program(s) flagged for profile review: {[f['program_id'] for f in flagged]}")
        # Write to research_queue
        queue_rows = []
        for f in flagged:
            queue_rows.append({
                "queue_type": "asset_profile_review",
                "drug_name": f["program_id"].upper(),
                "priority": "medium",
                "notes": (
                    f"Competitor update detected for {f['program_id'].upper()} profile. "
                    f"Trigger: {f['competitor_trigger']} ({f['intel_date'][:10]}). "
                    f"Profile last updated: {f['profile_updated'][:10]}. "
                    "Review KOL Q&A and pharma_bd_objections for accuracy."
                ),
                "status": "pending",
            })
        if queue_rows:
            rq_resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/research_queue",
                headers={**headers, "Prefer": "resolution=merge-duplicates"},
                json=queue_rows,
                timeout=15,
            )
            if rq_resp.status_code in (200, 201):
                log(f"  Phase 9: {len(queue_rows)} research_queue item(s) written for human review")
            else:
                log(f"  Phase 9: research_queue write failed ({rq_resp.status_code})")
    else:
        log("  Phase 9: all asset profiles current — no staleness flags")


# ── Phase 10: Bispecific Competitive Monitor ──────────────────────────────────
# Watches for readout events from competing TL1A×IL-23 bispecifics and other
# bispecifics competing with ALX001. Queries catalyst_calendar + drug_timeline_estimates
# for imminent readouts and creates research_queue items + flags drug_intelligence_qa
# for update when competitor data is newly available.

BISPECIFIC_WATCH_LIST = [
    # drug_id, common names, watch_event, expected_date, priority
    {
        "drug_id": "mt-251",
        "names": ["MT-251", "mt-251", "mountainview"],
        "watch_event": "Phase 1 primary readout",
        "expected_date": "2027-03-01",
        "priority": "P0",
        "rationale": "TL1A×IL-23p19 bispecific — closest mechanism match to ALX001; Phase 1 primary data defines class safety profile",
    },
    {
        "drug_id": "ro7837195",
        "names": ["RO7837195", "ro7837195", "roche-pfizer", "RG6462"],
        "watch_event": "Phase 2b primary readout",
        "expected_date": "2027-08-01",
        "priority": "P0",
        "rationale": "IL-23p40×TL1A bispecific (Roche/Pfizer) — first bispecific Phase 2b readout in class; will establish bispecific efficacy benchmark",
    },
    {
        "drug_id": "spy072",
        "names": ["SPY072", "spy072", "SPY001", "spyre", "Spyre Therapeutics"],
        "watch_event": "Spyre platform study Phase 2 update",
        "expected_date": "2028-06-01",
        "priority": "P0",
        "rationale": "Spyre platform: monoAb vs combination arms — will be first direct test of bispecific hypothesis; critical for ALX001 positioning",
    },
    {
        "drug_id": "apg333",
        "names": ["APG333", "apg333", "AscentagePharma"],
        "watch_event": "Phase 1 safety/PK readout",
        "expected_date": "2026-12-01",
        "priority": "P1",
        "rationale": "TL1A-based bispecific in Phase 1; earlier safety data could shift class risk perception",
    },
    {
        "drug_id": "tulisokibart",
        "names": ["tulisokibart", "MK-7240", "PRA023", "ATLAS-UC", "atlas-uc"],
        "watch_event": "ATLAS-UC Phase 3 primary readout",
        "expected_date": "2026-11-01",
        "priority": "P0",
        "rationale": "TL1A monoAb Phase 3 readout — defines TL1A class efficacy ceiling and regulatory bar; directly sets ALX001 Phase 2 success threshold",
    },
    {
        "drug_id": "duvakitug",
        "names": ["duvakitug", "QP110", "Sanofi", "duvak"],
        "watch_event": "Phase 3 primary readout",
        "expected_date": "2027-06-01",
        "priority": "P1",
        "rationale": "Second TL1A monoAb Phase 3; confirms or modifies tulisokibart efficacy benchmark",
    },
]

# Number of days before expected_date to flag as "imminent"
BISPECIFIC_IMMINENT_DAYS = 90


def _run_bispecific_competitive_monitor():
    """
    Phase 10: Bispecific competitive event monitor.

    1. For each drug in BISPECIFIC_WATCH_LIST, checks how close we are to the
       watch_event expected_date.
    2. If within BISPECIFIC_IMMINENT_DAYS days: writes a research_queue item
       (priority P0 or P1) to flag for active monitoring.
    3. Checks intelligence_discoveries + news_articles for any recent mention of
       the drug that might indicate data has been published early or leaked.
    4. If recent data detected: flags drug_intelligence_qa rows for the drug
       (competitive Q66-Q80) by setting needs_update=TRUE.
    5. Also checks catalyst_calendar and drug_timeline_estimates for any
       newly resolved catalyst events.
    """
    log("--- Phase 10: Bispecific Competitive Monitor ---")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

    today = datetime.datetime.utcnow().date()
    flagged_imminent = []
    flagged_data_detected = []

    # Step 1: Check proximity to expected readout dates
    for watch in BISPECIFIC_WATCH_LIST:
        try:
            expected = datetime.date.fromisoformat(watch["expected_date"])
            days_until = (expected - today).days
            if 0 <= days_until <= BISPECIFIC_IMMINENT_DAYS:
                flagged_imminent.append({**watch, "days_until": days_until})
                log(f"  IMMINENT: {watch['drug_id']} — {watch['watch_event']} in {days_until} days")
            elif days_until < 0:
                log(f"  PAST DUE: {watch['drug_id']} — {watch['watch_event']} was expected {-days_until} days ago (check if data published)")
                # Past due = check for actual data below
                flagged_imminent.append({**watch, "days_until": days_until, "past_due": True})
        except Exception as exc:
            log(f"  Date parse error for {watch['drug_id']}: {exc}")
            continue

    # Step 2: Check intelligence_discoveries for recent mentions of watch drugs
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        intel_resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/intelligence_discoveries",
            headers=headers,
            params={
                "select": "drug_name,discovery_text,created_at,headline",
                "created_at": f"gte.{cutoff}",
                "limit": "300",
            },
            timeout=15,
        )
        recent_intel = intel_resp.json() if intel_resp.status_code == 200 else []
    except Exception:
        recent_intel = []

    # Step 3: Check news_articles for recent mentions
    try:
        news_resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/news_articles",
            headers=headers,
            params={
                "select": "title,body,published_at",
                "published_at": f"gte.{cutoff}",
                "limit": "200",
            },
            timeout=15,
        )
        recent_news = news_resp.json() if news_resp.status_code == 200 else []
    except Exception:
        recent_news = []

    # Data detection keywords — indicate actual trial data has been reported
    DATA_KEYWORDS = [
        "phase 2", "phase 3", "primary endpoint", "clinical remission", "topline",
        "readout", "data", "results", "trial met", "trial failed", "dose response",
        "efficacy", "asco", "ddw", "ueg", "ecco", "nejm", "lancet", "gastroenterology",
    ]

    for watch in BISPECIFIC_WATCH_LIST:
        drug_names_lower = [n.lower() for n in watch["names"]]
        mentions = []

        for item in recent_intel:
            drug = (item.get("drug_name") or "").lower()
            text = (item.get("discovery_text") or "").lower() + " " + (item.get("headline") or "").lower()
            if any(n in drug or n in text for n in drug_names_lower):
                has_data_keyword = any(kw in text for kw in DATA_KEYWORDS)
                mentions.append({"source": "intelligence_discoveries", "has_data": has_data_keyword, "date": item.get("created_at", "")})

        for item in recent_news:
            text = ((item.get("title") or "") + " " + (item.get("body") or "")).lower()
            if any(n in text for n in drug_names_lower):
                has_data_keyword = any(kw in text for kw in DATA_KEYWORDS)
                mentions.append({"source": "news_articles", "has_data": has_data_keyword, "date": item.get("published_at", "")})

        if mentions:
            has_data_mention = any(m["has_data"] for m in mentions)
            log(f"  MENTION: {watch['drug_id']} — {len(mentions)} recent mention(s), data_keywords={has_data_mention}")
            if has_data_mention:
                flagged_data_detected.append({**watch, "mentions": len(mentions)})

    # Step 4: Write research_queue items for imminent/past-due events
    queue_rows = []
    for f in flagged_imminent:
        days = f["days_until"]
        label = f"PAST DUE ({-days}d)" if days < 0 else f"T-{days}d"
        queue_rows.append({
            "entity_type": "drug",
            "entity_id": f["drug_id"],
            "gap_type": "competitive_readout_imminent",
            "priority": f["priority"],
            "reason": (
                f"[{label}] {f['drug_id'].upper()} — {f['watch_event']}. "
                f"Expected: {f['expected_date']}. Rationale: {f['rationale']}"
            )[:1000],
            "source": "bispecific_competitive_monitor",
            "status": "pending",
        })

    if queue_rows:
        rq = requests.post(
            f"{SUPABASE_URL}/rest/v1/research_queue",
            headers={**headers, "Prefer": "resolution=ignore-duplicates,return=minimal"},
            json=queue_rows,
            timeout=15,
        )
        if rq.status_code in (200, 201):
            log(f"  Phase 10: {len(queue_rows)} research_queue item(s) written (imminent/past-due readouts)")
        else:
            log(f"  Phase 10: research_queue write error: {rq.status_code} {rq.text[:150]}")

    # Step 5: For drugs where data was detected, flag drug_intelligence_qa Q66-Q80
    # (competitive questions) for the ALX001 drug as needs_update=TRUE
    alx001_competitive_qs = list(range(66, 81))  # Q66–Q80 competitive domain
    for f in flagged_data_detected:
        drug_id = f["drug_id"]
        log(f"  Phase 10: Data detected for {drug_id} — flagging ALX001 competitive QA for update")
        # Flag ALX001 competitive Q&A
        for q_id in alx001_competitive_qs:
            try:
                requests.patch(
                    f"{SUPABASE_URL}/rest/v1/drug_intelligence_qa",
                    headers={**headers, "Prefer": "return=minimal"},
                    params={"drug_id": "eq.anti-tl1a-xpf005-arm", "question_id": f"eq.{q_id}"},
                    json={
                        "needs_update": True,
                        "last_researched": datetime.datetime.utcnow().isoformat(),
                    },
                    timeout=10,
                )
            except Exception:
                pass
        log(f"  Phase 10: Flagged Q66-Q80 for ALX001 due to {drug_id} data detection ({f['mentions']} mentions)")

    # Step 6: Check catalyst_calendar for resolved bispecific catalysts
    try:
        catalyst_resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/catalyst_calendar",
            headers=headers,
            params={
                "select": "drug_name,catalyst_date,catalyst_type,resolved,area_id",
                "resolved": "eq.false",
                "limit": "100",
            },
            timeout=15,
        )
        catalysts = catalyst_resp.json() if catalyst_resp.status_code == 200 else []
        bispecific_catalysts = []
        all_names_lower = []
        for w in BISPECIFIC_WATCH_LIST:
            all_names_lower.extend([n.lower() for n in w["names"]])
        for cat in catalysts:
            name = (cat.get("drug_name") or "").lower()
            if any(n in name for n in all_names_lower):
                bispecific_catalysts.append(cat)
        if bispecific_catalysts:
            log(f"  Phase 10: {len(bispecific_catalysts)} unresolved bispecific catalyst(s) in catalyst_calendar")
            for cat in bispecific_catalysts:
                log(f"    - {cat.get('drug_name')} | {cat.get('catalyst_date')} | {cat.get('catalyst_type')}")
        else:
            log("  Phase 10: No unresolved bispecific catalysts in catalyst_calendar")
    except Exception as exc:
        log(f"  Phase 10: catalyst_calendar check error: {exc}")

    total_flagged = len(flagged_imminent) + len(flagged_data_detected)
    log(f"--- Phase 10 complete: {total_flagged} event(s) flagged ---")


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log(f"=== Meridian Research Pipeline — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ===")

    company_map = get_company_map()
    log(f"Loaded {len(company_map)} company name → ID mappings")

    # Prefer CompanyIdentityResolver (alias table + audit log) over fragile substring matching
    resolver = None
    if _RESOLVER_AVAILABLE:
        try:
            resolver = CompanyIdentityResolver(SUPABASE_URL, SUPABASE_KEY)
            log("CompanyIdentityResolver initialised (alias table + audit logging active)")
        except Exception as e:
            log(f"CompanyIdentityResolver init failed, falling back to company_map: {e}")

    log("--- Phase 1/5: Fetching RSS feeds ---")
    articles = fetch_feeds(hours_back=48)
    log("--- Phase 2/5: Filtering for focus-area relevance ---")
    relevant = filter_relevant(articles)

    if not relevant:
        log("No relevant articles found — done.")
    else:
        log("--- Phase 3/5: Deduplicating against Supabase ---")
        existing_urls = get_existing_urls()
        new_articles = [a for a in relevant if a["url"] not in existing_urls]
        log(f"New (not in Supabase): {len(new_articles)} articles")

        if new_articles:
            log("--- Phase 4/5: Enriching with full text ---")
            # Enrich high-priority articles with full body text before extraction
            enrich_with_full_text(new_articles, max_fetches=15)
            log("--- Phase 5/5: Extracting intel + writing to Supabase ---")
            intel = extract_intel(new_articles)
            if intel:
                write_to_supabase(intel, company_map=company_map, resolver=resolver)

    # Phase 6: CT.gov + EDGAR sweep — runs unconditionally (independent of RSS results)
    run_new_source_sweep()

    # Phase 7: PK/PD queue processor — reads research_queue pkpd_literature items,
    # fetches PubMed abstracts, extracts PK parameters, writes to drug_pk_parameters
    try:
        process_pkpd_queue()
    except Exception as exc:
        log(f"Phase 7 PK/PD queue error (non-fatal): {exc}")

    # GAP 3 FIX: Source verifier — run nightly to validate source URLs and
    # write to source_validation_log. Called here so it runs as part of nightly pipeline.
    # source_verifier.run() checks URLs from deals, partnerships, enriched_field_log, etc.
    # and writes results to source_validation_log (populating a previously empty table).
    try:
        from source_verifier import run as run_source_verifier
        log("--- Phase 8: Source URL verification ---")
        run_source_verifier(dry_run=False, limit=50)
        log("--- Phase 8 complete ---")
    except ImportError:
        log("source_verifier not available — skipping Phase 8")
    except Exception as exc:
        log(f"Phase 8 source verifier error (non-fatal): {exc}")

    # Phase 9: Asset differentiation profile staleness check
    # Queries asset_differentiation_profiles + recent intelligence to flag
    # profiles that may need KOL Q&A or objection updates based on competitor
    # data changes. Logs flagged programs to research_queue for human review.
    try:
        log("--- Phase 9: Asset differentiation profile staleness check ---")
        _run_asset_profile_staleness_check()
        log("--- Phase 9 complete ---")
    except Exception as exc:
        log(f"Phase 9 asset profile check error (non-fatal): {exc}")

    # Phase 10: Bispecific competitive monitor — watches for imminent and past-due
    # readout events from TL1A×IL-23p19 bispecifics and class-defining monoAbs;
    # flags ALX001 competitive Q&A for update when competitor data is detected.
    try:
        log("--- Phase 10: Bispecific Competitive Monitor ---")
        _run_bispecific_competitive_monitor()
    except Exception as exc:
        log(f"Phase 10 bispecific monitor error (non-fatal): {exc}")

    # S3: stamp system_status so the dashboard surfaces a fresh-data signal.
    stamp_system_status_research(note="Nightly research pipeline complete")

    log("=== Research complete ===")
