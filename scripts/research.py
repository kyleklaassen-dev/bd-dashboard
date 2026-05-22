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
SECONDARY_FEEDS = [
    "https://www.biopharmadive.com/feeds/news/",
    "https://www.statnews.com/feed/",
    "https://www.genengnews.com/feed/",
    "https://www.biospace.com/rss/news",
    "https://www.nature.com/nm/rss/current",
    "https://www.nejm.org/action/showFeed?jc=nejm&type=etoc&feed=rss",
    "https://www.prnewswire.com/rss/news-releases-list.rss",
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
FULL_TEXT_SOURCES = {
    "endpoints news", "fierce biotech",
    "abbvie", "roche", "lilly", "regeneron", "johnson", "astrazeneca",
    "sanofi", "novartis", "ucb", "bristol", "pfizer", "merck", "teva",
    "boehringer", "stat news", "biopharmadive",
    "nature medicine", "new england journal of medicine", "prnewswire",
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
- Ailux lead asset: SPY002, TL1A × IL-23p19 bispecific antibody for IBD (UC + CD)
- TL1A class: tulisokibart (Merck, Ph3 ATLAS-UC ~Nov 2026 readout) + afimkibart (Roche, Ph3 Jan 2027) are the class-defining monospecifics. Merck reads out first.
- IL-23p19 class: risankizumab (AbbVie, approved), mirikizumab (Lilly, approved), guselkumab (J&J, CD Ph3). Proven SOC.
- RO7837195 (Roche/Pfizer): IL-23p40 × TL1A bispecific — most direct competitor to SPY002; targets p40 (blocks both IL-12 + IL-23), unlike SPY002's p19 selectivity.
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
Skip articles where the focus-area relevance is tangential (e.g., a general immunology paper with no clinical or commercial implications for these programs).

Return ONLY a valid JSON array. No markdown, no explanation, no wrapper text."""


def extract_intel(articles):
    all_intel = []
    batch_size = 6  # Smaller batches — Sonnet writes richer body text, needs more headroom

    for i in range(0, len(articles), batch_size):
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
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    for item in intel_items:
        # ── Intel record ──────────────────────────────────────────────────
        intel_rec = {
            "intel_date":  item.get("intel_date") or today,
            "headline":    (item.get("headline") or "")[:200],
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
                "headline":        (item.get("headline") or "")[:200],
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
        f"(company junction rows written inline)")


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

    articles = fetch_feeds(hours_back=48)
    relevant = filter_relevant(articles)

    if not relevant:
        log("No relevant articles found — done.")
    else:
        existing_urls = get_existing_urls()
        new_articles = [a for a in relevant if a["url"] not in existing_urls]
        log(f"New (not in Supabase): {len(new_articles)} articles")

        if new_articles:
            # Enrich high-priority articles with full body text before extraction
            enrich_with_full_text(new_articles, max_fetches=15)
            intel = extract_intel(new_articles)
            if intel:
                write_to_supabase(intel, company_map=company_map, resolver=resolver)

    log("=== Research complete ===")
