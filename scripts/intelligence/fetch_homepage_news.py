#!/usr/bin/env python3
"""fetch_homepage_news.py — Meridian Homepage News Intelligence Pilot

Fetches latest articles from trusted biotech news sources, scores relevance,
matches to Meridian entities, generates Claude summaries, and writes to the
news_articles table for display on the Meridian homepage.

Sources (confirmed live RSS feeds):
  - FierceBiotech       https://www.fiercebiotech.com/rss/xml
  - BioPharma Dive      https://www.biopharmadive.com/feeds/news/
  - STAT News           https://www.statnews.com/feed/

Endpoints News: 403 on all routes — articles will only appear if their URL
resolves via other means and is marked source_validation_status='limited'.

Scoring (deterministic, 0–100):
  - Source quality base:  Fierce/BPD/STAT = 15, others = 8
  - Company match:        +20 (Meridian watchlist)
  - Drug match:           +20 (Meridian drug aliases)
  - Target match:         +15 (TL1A, TSLP, IL-4Rα, FcRn, IGF1R, T-cell)
  - Deal/M&A keywords:    +20
  - Clinical/FDA keywords:+20
  - I&I/oncology biology: +10
  - Duplicate source:     +5 (same story from ≥2 sources)
  - Weak relevance:       −10 (generic hiring / finance / medtech)

Claude call (optional, requires ANTHROPIC_API_KEY):
  - Generates meridian_summary + why_it_matters for articles with score ≥ 40

Usage:
  python scripts/fetch_homepage_news.py
  python scripts/fetch_homepage_news.py --dry-run
  python scripts/fetch_homepage_news.py --no-claude
  python scripts/fetch_homepage_news.py --since 2026-05-20
  python scripts/fetch_homepage_news.py --limit 50
"""

import os, sys, json, hashlib, re, datetime, time, argparse, traceback
import urllib.request, urllib.error, urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

# ── Credentials ──────────────────────────────────────────────────────────────

_HERE = Path(__file__).parent.parent

def _read_cred(fname: str) -> str:
    p = _HERE / fname
    if p.exists():
        return p.read_text().strip()
    return os.environ.get(fname.lstrip(".").upper().replace("-","_"), "")

SUPABASE_URL  = "https://tghntyofptvfhmtchwcv.supabase.co"
SUPABASE_KEY  = _read_cred(".supabase_service_key") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY","")
ANTHROPIC_KEY = _read_cred(".anthropic_key") or os.environ.get("ANTHROPIC_API_KEY","")

TODAY_UTC = datetime.datetime.utcnow().date()
NOW_ISO   = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
WEEK_AGO  = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).date()

# ── RSS Sources ───────────────────────────────────────────────────────────────

RSS_SOURCES = [
    {
        "name":        "FierceBiotech",
        "url":         "https://www.fiercebiotech.com/rss/xml",
        "quality_base": 15,
        "ua":          "Mozilla/5.0 (compatible; Meridian-NewsBot/1.0)",
    },
    {
        "name":        "BioPharma Dive",
        "url":         "https://www.biopharmadive.com/feeds/news/",
        "quality_base": 15,
        "ua":          "Mozilla/5.0 (compatible; Meridian-NewsBot/1.0)",
    },
    {
        "name":        "STAT News",
        "url":         "https://www.statnews.com/feed/",
        "quality_base": 15,
        "ua":          "Mozilla/5.0 (compatible; Meridian-NewsBot/1.0)",
    },
]

# ── Relevance keyword banks ───────────────────────────────────────────────────

DEAL_KEYWORDS = [
    "acqui", "merger", "licens", "acquis", "partner", "collaboration",
    "milestone", "upfront", "billion", "million deal", "agreement",
    "in-license", "out-license", "option agreement", "co-develop",
]

CLINICAL_FDA_KEYWORDS = [
    "fda approv", "fda accept", "approval", "bla ", "nda ", "pdufa",
    "phase 3", "phase iii", "phase 2/3", "pivotal", "topline", "top-line",
    "primary endpoint", "met endpoint", "data readout", "clinical data",
    "first-in-human", "first in human", "ind ", "ind filing",
    "accelerated approval", "breakthrough therapy", "fast track",
    "complete response letter", "crl ",
]

TARGET_KEYWORDS = {
    "tl1a":  ["tl1a", "tnfsf15", "tl-1a"],
    "tslp":  ["tslp", "thymic stromal", "astegolimab", "tezepelumab"],
    "il4ra": ["il-4r", "il4r", "dupilumab", "dupixent", "il-4/il-13"],
    "fcrn":  ["fcrn", "fc receptor", "efgartigimod", "nipocalimab", "rozanolixizumab"],
    "igf1r": ["igf-1r", "igf1r", "ted ", "thyroid eye", "teprotumumab", "veligrotug"],
    "tcell": ["bispecific", "t-cell engager", "car-t", "trop-2", "bcma", "cd3 "],
}

II_ONCO_KEYWORDS = [
    "inflammatory bowel", "crohn", "ulcerative colitis", " ibd ",
    "atopic dermatitis", "eczema", "asthma", "copd", "lupus", "sle ",
    "rheumatoid", " ra ", "psoriasis", "myasthenia", "graves",
    "antibody", "mab ", "biologic", "immunology", "autoimmun",
    "oncol", "tumor", "cancer", "adc ", "antibody-drug conjugate",
]

WEAK_KEYWORDS = [
    "chief medical officer", "chief executive", "ceo appoint", "board appoint",
    "appoints new", "names new", "hired as", "joins as", "elected to board",
    "medtech", "dental", "orthoped", "cardiovasc",  # unless also has strong signal
]

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str, indent: int = 0):
    print("  " * indent + msg, flush=True)

# ── Supabase helpers ──────────────────────────────────────────────────────────

def _sb_headers(key: str | None = None) -> dict:
    k = key or SUPABASE_KEY
    return {
        "apikey": k, "Authorization": f"Bearer {k}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def sb_get(table: str, params: dict | None = None) -> list:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params:
        url += "?" + "&".join(f"{k}={urllib.parse.quote_plus(str(v))}" for k,v in params.items())
    req = urllib.request.Request(url, headers=_sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log(f"  ✗ sb_get /{table}: {e}")
        return []

def sb_upsert(table: str, record: dict, on_conflict: str) -> list | None:
    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}"
    headers = {**_sb_headers(), "Prefer": "resolution=merge-duplicates,return=representation"}
    body = json.dumps(record).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        if e.code == 409:
            return []
        log(f"  ✗ sb_upsert /{table}: HTTP {e.code} — {err[:200]}")
        return None
    except Exception as e:
        log(f"  ✗ sb_upsert /{table}: {e}")
        return None

def sb_update_where(table: str, updates: dict, filters: dict) -> None:
    """PATCH rows matching filters."""
    qs = "&".join(f"{k}={urllib.parse.quote_plus(str(v))}" for k,v in filters.items())
    url = f"{SUPABASE_URL}/rest/v1/{table}?{qs}"
    body = json.dumps(updates).encode()
    req = urllib.request.Request(url, data=body, headers=_sb_headers(), method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=20):
            pass
    except Exception as e:
        log(f"  ✗ sb_update_where /{table}: {e}")

# ── Entity watchlist ──────────────────────────────────────────────────────────

def load_watchlist() -> dict:
    """Load companies, drug aliases, and area keywords from Meridian DB."""
    log("Loading Meridian entity watchlist…")

    # Company aliases
    aliases_raw = sb_get("company_aliases", {"select": "alias_name,company_id", "limit": "500"})
    companies_raw = sb_get("companies", {"select": "id,name", "status": "neq.acquired", "limit": "200"})

    alias_map: dict[str, str] = {}
    for row in aliases_raw:
        if row.get("alias_name"):
            alias_map[row["alias_name"].lower()] = row["company_id"]
    for co in companies_raw:
        if co.get("name"):
            alias_map[co["name"].lower()] = co["id"]

    # Drug names
    drugs_raw = sb_get("drugs", {"select": "id,name,display_name,brand_name", "limit": "500"})
    drug_alias_set: set[str] = set()
    drug_id_map: dict[str, str] = {}
    for d in drugs_raw:
        for field in ("name", "display_name", "brand_name"):
            v = (d.get(field) or "").strip().lower()
            if v and len(v) >= 5:
                drug_alias_set.add(v)
                drug_id_map[v] = d["id"]

    log(f"  {len(alias_map)} company aliases, {len(drug_alias_set)} drug names")
    return {
        "alias_map": alias_map,
        "drug_alias_set": drug_alias_set,
        "drug_id_map": drug_id_map,
        "company_ids": {co["id"]: co["name"] for co in companies_raw},
    }

# ── Scoring ───────────────────────────────────────────────────────────────────

def score_article(
    headline: str,
    raw_summary: str,
    quality_base: int,
    watchlist: dict,
) -> tuple[int, list[str], list[str], list[str], str]:
    """
    Returns (score 0–100, matched_company_ids, matched_drug_ids, matched_area_ids, priority_level).
    """
    text = (headline + " " + (raw_summary or "")).lower()
    score = quality_base
    matched_companies: list[str] = []
    matched_drugs: list[str] = []
    matched_areas: list[str] = []

    # Company match (+20 per match, cap at 20)
    for alias, co_id in watchlist["alias_map"].items():
        if not alias or len(alias) < 4:
            continue
        if len(alias) < 8:
            if re.search(r'\b' + re.escape(alias) + r'\b', text):
                if co_id not in matched_companies:
                    matched_companies.append(co_id)
        elif alias in text:
            if co_id not in matched_companies:
                matched_companies.append(co_id)
    if matched_companies:
        score += min(20, len(matched_companies) * 8)

    # Drug match (+20 per match, cap at 20)
    for drug_alias in watchlist["drug_alias_set"]:
        if not drug_alias or len(drug_alias) < 5:
            continue
        if len(drug_alias) < 10:
            if re.search(r'\b' + re.escape(drug_alias) + r'\b', text):
                did = watchlist["drug_id_map"].get(drug_alias)
                if did and did not in matched_drugs:
                    matched_drugs.append(did)
        elif drug_alias in text:
            did = watchlist["drug_id_map"].get(drug_alias)
            if did and did not in matched_drugs:
                matched_drugs.append(did)
    if matched_drugs:
        score += min(20, len(matched_drugs) * 8)

    # Target/area match (+15, cap at 15)
    for area_id, kws in TARGET_KEYWORDS.items():
        for kw in kws:
            if kw in text:
                if area_id not in matched_areas:
                    matched_areas.append(area_id)
                break
    if matched_areas:
        score += min(15, len(matched_areas) * 8)

    # Deal/M&A keywords (+20)
    if any(kw in text for kw in DEAL_KEYWORDS):
        score += 20

    # Clinical/FDA keywords (+20)
    if any(kw in text for kw in CLINICAL_FDA_KEYWORDS):
        score += 20

    # I&I / oncology biologics (+10)
    if any(kw in text for kw in II_ONCO_KEYWORDS):
        score += 10

    # Weak signal penalty (−10)
    if any(kw in text for kw in WEAK_KEYWORDS):
        # Only penalize if no strong company/drug/deal signal
        if not matched_companies and not matched_drugs and not matched_areas:
            score -= 10

    score = max(0, min(100, score))

    if score >= 70:
        priority = "high"
    elif score >= 50:
        priority = "medium"
    elif score >= 30:
        priority = "standard"
    else:
        priority = "low"

    return score, matched_companies[:5], matched_drugs[:5], matched_areas, priority

# ── URL validation ────────────────────────────────────────────────────────────

def validate_url(url: str) -> tuple[str, int]:
    """
    HEAD-check a URL. Returns (status_str, http_code).
    status_str: 'valid' | 'limited' | 'invalid'
    """
    if not url or not url.startswith("http"):
        return "invalid", 0
    try:
        req = urllib.request.Request(
            url,
            method="HEAD",
            headers={"User-Agent": "Mozilla/5.0 (compatible; Meridian-NewsBot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            code = r.getcode()
            if code == 200:
                return "valid", code
            elif code in (301, 302, 307, 308):
                return "valid", code
            elif code in (401, 403):
                return "limited", code
            else:
                return "invalid", code
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return "limited", e.code
        return "invalid", e.code
    except Exception:
        return "invalid", 0

# ── RSS parsing ───────────────────────────────────────────────────────────────

def _clean_html(raw: str) -> str:
    """Strip HTML tags and decode entities."""
    s = re.sub(r'<[^>]+>', ' ', raw or "")
    s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">") \
         .replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    return re.sub(r'\s+', ' ', s).strip()

def _parse_date(raw: str | None) -> str | None:
    """Parse RSS date string to ISO8601."""
    if not raw:
        return None
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
        # FierceBiotech: "May 21, 2026 3:21pm"
        "%B %d, %Y %I:%M%p",
        "%B %d, %Y %I:%M %p",
        "%b %d, %Y %I:%M%p",
        "%b %d, %Y",
        "%B %d, %Y",
    ):
        try:
            dt = datetime.datetime.strptime(raw.strip(), fmt)
            return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            continue
    return None

def fetch_rss(source: dict, since_date: datetime.date | None = None) -> list[dict]:
    """Fetch + parse RSS feed. Returns list of article dicts."""
    try:
        req = urllib.request.Request(
            source["url"],
            headers={"User-Agent": source.get("ua", "Mozilla/5.0")},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"  ✗ {source['name']}: fetch failed — {e}")
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        log(f"  ✗ {source['name']}: XML parse error — {e}")
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item") or root.findall(".//atom:entry", ns)
    results = []

    for item in items:
        def _t(tag: str) -> str:
            # IMPORTANT: must use `is not None`, not truthiness — ET elements with no
            # child elements are falsy even when they have text (e.g. <link>URL</link>)
            el = item.find(tag)
            if el is None:
                el = item.find(f"atom:{tag}", ns)
            if el is None:
                return ""
            # Use itertext() to capture text from nested elements too
            # (FierceBiotech <title> contains a nested <a> tag)
            return "".join(el.itertext()).strip()

        headline = _clean_html(_t("title"))
        url = _t("link") or _t("guid")
        if not url:
            link_el = item.find("atom:link", ns)
            if link_el is not None:
                url = link_el.get("href", "")
        pub_raw = _t("pubDate") or _t("published") or _t("updated")
        pub_iso = _parse_date(pub_raw)
        summary = _clean_html(_t("description") or _t("summary") or _t("content"))[:2000]

        if not headline or not url:
            continue

        # Date filter
        if since_date and pub_iso:
            try:
                pub_d = datetime.datetime.fromisoformat(pub_iso.replace("Z","+00:00")).date()
                if pub_d < since_date:
                    continue
            except Exception:
                pass

        results.append({
            "headline":    headline,
            "article_url": url.strip(),
            "published_at": pub_iso,
            "raw_summary": summary,
            "source_name": source["name"],
            "source_url":  source["url"],
            "quality_base": source["quality_base"],
        })

    log(f"  ✓ {source['name']}: {len(results)} articles parsed")
    return results

# ── Claude summarization ──────────────────────────────────────────────────────

def generate_summary(headline: str, raw_summary: str, matched_companies: list, matched_areas: list) -> tuple[str, str]:
    """
    Call Claude (claude-haiku-4-5) to generate meridian_summary + why_it_matters.
    Returns ("", "") if API key missing or call fails.
    """
    if not ANTHROPIC_KEY:
        return "", ""

    company_ctx = ", ".join(matched_companies[:3]) if matched_companies else "none"
    area_ctx = ", ".join(matched_areas) if matched_areas else "none"

    prompt = f"""You are a BD intelligence analyst at Ailux, a preclinical biotech focused on TL1A, TSLP, IL-4Rα, FcRn, IGF1R, and T-cell engager programs in I&I and oncology.

Summarize this biotech news article for the Meridian dashboard homepage.

Headline: {headline}
Excerpt: {(raw_summary or '')[:600]}
Matched Meridian companies: {company_ctx}
Matched disease areas: {area_ctx}

Write two things:
1. SUMMARY: 2-3 sentences summarizing what happened factually. Be precise, use drug/company names. No fluff.
2. WHY IT MATTERS: 1-2 sentences explaining the BD strategic relevance to Ailux. Focus on deal precedents, competitive signals, target validation, or pipeline risk. If no strong relevance, say so briefly.

Format your response EXACTLY as:
SUMMARY: <text>
WHY_IT_MATTERS: <text>"""

    try:
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode())
        text = resp["content"][0]["text"].strip()
        summary_match = re.search(r'SUMMARY:\s*(.*?)(?=WHY_IT_MATTERS:|$)', text, re.DOTALL)
        why_match = re.search(r'WHY_IT_MATTERS:\s*(.*?)$', text, re.DOTALL)
        meridian_summary = summary_match.group(1).strip() if summary_match else ""
        why_it_matters = why_match.group(1).strip() if why_match else ""
        return meridian_summary, why_it_matters
    except Exception as e:
        log(f"  ✗ Claude summary failed: {e}", indent=2)
        return "", ""

# ── Deduplication ─────────────────────────────────────────────────────────────

def _url_hash(url: str) -> str:
    return hashlib.sha256(url.lower().strip().encode()).hexdigest()

def _content_hash(headline: str) -> str:
    # Normalize: lowercase, strip punctuation, collapse spaces
    normalized = re.sub(r'[^\w\s]', '', headline.lower())
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()

# ── Main pipeline ─────────────────────────────────────────────────────────────

def run(args) -> None:
    log("=" * 60)
    log(f"Meridian Homepage News Fetch — {NOW_ISO}")
    log("=" * 60)

    since_date = None
    if args.since:
        try:
            since_date = datetime.date.fromisoformat(args.since)
            log(f"Filtering articles since: {since_date}")
        except ValueError:
            log(f"  ✗ Invalid --since date: {args.since}")

    # ── Step 1: Reset time-window flags for existing rows ─────────────────
    # Articles set is_this_week=true at write time and are never re-fetched once they
    # exit the RSS window (typically 2–4 weeks of RSS history). Without this reset,
    # old articles keep is_this_week=true indefinitely, making the homepage section
    # show stale content as if it were current.
    if not args.dry_run:
        log("\n[1] Refreshing time-window flags on existing rows…")
        week_start = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Expire is_this_week for articles older than 7 days
        sb_update_where(
            "news_articles",
            {"is_this_week": False},
            {"published_at": f"lt.{week_start}", "is_this_week": "eq.true"},
        )
        # Expire is_today for articles not published today
        sb_update_where(
            "news_articles",
            {"is_today": False},
            {"published_at": f"lt.{today_start}", "is_today": "eq.true"},
        )
        log("  ✓ Expired stale is_this_week / is_today flags")

    # ── Step 2: Load entity watchlist ────────────────────────────────────
    log("\n[2] Loading entity watchlist…")
    watchlist = load_watchlist()

    # ── Step 3: Fetch RSS feeds ───────────────────────────────────────────
    log("\n[3] Fetching RSS feeds…")
    all_articles: list[dict] = []
    for source in RSS_SOURCES:
        articles = fetch_rss(source, since_date=since_date)
        all_articles.extend(articles)
        time.sleep(0.5)  # be polite

    log(f"  Total fetched: {len(all_articles)} articles")
    if args.limit:
        all_articles = all_articles[:args.limit]
        log(f"  Capped at {args.limit} (--limit flag)")

    # ── Step 4: Dedup by URL hash ────────────────────────────────────────
    log("\n[4] Deduplicating…")
    seen_urls: set[str] = set()
    seen_headlines: dict[str, str] = {}  # content_hash → source
    unique_articles: list[dict] = []

    for art in all_articles:
        uh = _url_hash(art["article_url"])
        ch = _content_hash(art["headline"])
        if uh in seen_urls:
            log(f"  Skip (dup URL): {art['headline'][:60]}", indent=1)
            continue
        seen_urls.add(uh)
        if ch in seen_headlines:
            log(f"  Skip (dup content): {art['headline'][:60]}", indent=1)
            continue
        seen_headlines[ch] = art["source_name"]
        art["url_hash"] = uh
        art["content_hash"] = ch
        unique_articles.append(art)

    log(f"  {len(unique_articles)} unique articles after dedup")

    # ── Step 5: Score + match ─────────────────────────────────────────────
    log("\n[5] Scoring and entity matching…")
    scored: list[dict] = []
    for art in unique_articles:
        score, co_ids, drug_ids, area_ids, priority = score_article(
            art["headline"], art["raw_summary"], art["quality_base"], watchlist
        )
        art["relevance_score"] = score
        art["matched_company_ids"] = co_ids
        art["matched_drug_ids"] = drug_ids
        art["matched_area_ids"] = area_ids
        art["matched_target_ids"] = []
        art["priority_level"] = priority
        scored.append(art)

    # Sort by score desc
    scored.sort(key=lambda a: a["relevance_score"], reverse=True)
    high = sum(1 for a in scored if a["priority_level"] == "high")
    med  = sum(1 for a in scored if a["priority_level"] == "medium")
    log(f"  Score distribution: {high} high / {med} medium / {len(scored)-high-med} standard+low")

    # ── Step 6: URL validation ────────────────────────────────────────────
    log("\n[6] Validating article URLs…")
    for art in scored:
        status, code = validate_url(art["article_url"])
        art["source_validation_status"] = status
        art["http_status"] = code
        art["last_validated_at"] = NOW_ISO
        if status == "invalid":
            log(f"  ✗ Invalid URL ({code}): {art['article_url'][:80]}", indent=1)
        time.sleep(0.1)  # light throttle

    valid_count   = sum(1 for a in scored if a["source_validation_status"] == "valid")
    limited_count = sum(1 for a in scored if a["source_validation_status"] == "limited")
    invalid_count = sum(1 for a in scored if a["source_validation_status"] == "invalid")
    log(f"  {valid_count} valid / {limited_count} limited / {invalid_count} invalid")

    # ── Step 7: Claude summaries (high-priority articles only) ────────────
    if not args.no_claude and ANTHROPIC_KEY:
        log("\n[7] Generating Claude summaries (score ≥ 40, valid/limited URLs)…")
        for art in scored:
            if art["relevance_score"] < 40:
                continue
            if art["source_validation_status"] == "invalid":
                continue
            if art.get("meridian_summary"):
                continue  # already generated
            log(f"  Summarizing: {art['headline'][:60]}…", indent=1)
            summary, why = generate_summary(
                art["headline"],
                art["raw_summary"],
                art["matched_company_ids"],
                art["matched_area_ids"],
            )
            art["meridian_summary"] = summary
            art["why_it_matters"] = why
            time.sleep(0.3)  # rate limit
    else:
        log("\n[7] Skipping Claude summaries (--no-claude or no API key)")

    # ── Step 8: Compute time-window flags ─────────────────────────────────
    log("\n[8] Computing time-window flags…")
    for art in scored:
        pub_str = art.get("published_at") or ""
        if pub_str:
            try:
                pub_dt = datetime.datetime.fromisoformat(pub_str.replace("Z","+00:00"))
                pub_d  = pub_dt.date()
                art["is_today"]     = pub_d >= TODAY_UTC
                art["is_this_week"] = pub_d >= WEEK_AGO
            except Exception:
                art["is_today"] = False
                art["is_this_week"] = False
        else:
            art["is_today"] = False
            art["is_this_week"] = False

    # ── Step 9: Write to Supabase ─────────────────────────────────────────
    log("\n[9] Writing to news_articles…")
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0}

    for art in scored:
        # Skip articles with invalid URLs
        if art["source_validation_status"] == "invalid":
            stats["skipped"] += 1
            continue

        record = {
            "source_name":              art["source_name"],
            "source_url":               art["source_url"],
            "article_url":              art["article_url"],
            "headline":                 art["headline"],
            "published_at":             art.get("published_at"),
            "fetched_at":               NOW_ISO,
            "raw_summary":              art.get("raw_summary", ""),
            "meridian_summary":         art.get("meridian_summary", ""),
            "why_it_matters":           art.get("why_it_matters", ""),
            "relevance_score":          art["relevance_score"],
            "priority_level":           art["priority_level"],
            "matched_company_ids":      art["matched_company_ids"],
            "matched_drug_ids":         art["matched_drug_ids"],
            "matched_target_ids":       art["matched_target_ids"],
            "matched_area_ids":         art["matched_area_ids"],
            "source_validation_status": art["source_validation_status"],
            "http_status":              art["http_status"],
            "last_validated_at":        art["last_validated_at"],
            "content_hash":             art["content_hash"],
            "url_hash":                 art["url_hash"],
            "is_today":                 art["is_today"],
            "is_this_week":             art["is_this_week"],
            "review_status":            "auto",
        }

        if args.dry_run:
            log(f"  [DRY] {art['priority_level'].upper():8} score={art['relevance_score']:5.1f}  {art['headline'][:65]}")
            continue

        result = sb_upsert("news_articles", record, on_conflict="url_hash")
        if result is None:
            stats["failed"] += 1
        elif result == []:
            stats["updated"] += 1
        else:
            stats["inserted"] += 1

    log(f"\n  Done: {stats['inserted']} inserted / {stats['updated']} updated / {stats['skipped']} skipped / {stats['failed']} failed")

    # ── Summary ────────────────────────────────────────────────────────────
    log("\n" + "=" * 60)
    log("FETCH COMPLETE")
    log(f"  Articles fetched:  {len(all_articles)}")
    log(f"  After dedup:       {len(unique_articles)}")
    log(f"  Valid for display: {valid_count + limited_count}")
    today_disp  = [a for a in scored if a["is_today"]     and a["source_validation_status"] != "invalid"]
    week_disp   = [a for a in scored if a["is_this_week"] and a["source_validation_status"] != "invalid"]
    log(f"  Today window:      {len(today_disp)} articles")
    log(f"  This week window:  {len(week_disp)} articles")
    top3 = [a for a in scored if a["source_validation_status"] != "invalid"][:3]
    if top3:
        log("\nTop 3 by relevance score:")
        for a in top3:
            log(f"  [{a['relevance_score']:.0f}] {a['source_name']} — {a['headline'][:70]}", indent=1)
    log("=" * 60)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Meridian Homepage News Fetcher")
    parser.add_argument("--dry-run", action="store_true", help="Score and log without writing to DB")
    parser.add_argument("--no-claude", action="store_true", help="Skip Claude summary generation")
    parser.add_argument("--since", type=str, help="Only fetch articles since YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=0, help="Cap total articles processed")
    args = parser.parse_args()
    run(args)
