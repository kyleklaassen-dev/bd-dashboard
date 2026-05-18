#!/usr/bin/env python3
"""
Meridian Research Pipeline — GitHub Actions edition
Fetches biopharma news from RSS feeds, extracts structured intel using
Claude Haiku, writes to Supabase. Runs 4 AM ET Mon–Sat.
"""

import os, json, hashlib, datetime, time
import feedparser
import requests
import anthropic

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
RSS_FEEDS = [
    "https://endpts.com/feed/",
    "https://www.biospace.com/rss/news",
    "https://www.fiercebiotech.com/rss/xml",
    "https://www.biopharmadive.com/feeds/news/",
    "https://www.statnews.com/feed/",
    "https://www.genengnews.com/feed/",
    "https://www.nature.com/nm/rss/current",
    "https://www.nejm.org/action/showFeed?jc=nejm&type=etoc&feed=rss",
    "https://www.prnewswire.com/rss/news-releases-list.rss",
    "https://www.businesswire.com/rss/home/?rss=G7",
]


def log(msg):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


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
    relevant = []
    for a in articles:
        text = (a["title"] + " " + a["summary"]).lower()
        matched = [area for area, kws in FOCUS_AREAS.items()
                   if any(kw.lower() in text for kw in kws)]
        if matched:
            a["areas"] = matched
            relevant.append(a)
    log(f"Relevant: {len(relevant)} / {len(articles)} articles matched focus areas")
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


# ── Step 4: Extract intel with Claude Haiku ──────────────────────────────────
EXTRACT_PROMPT = """You are an analyst for a biopharma BD intelligence platform tracking 6 focus areas:
- tl1a: TL1A antibodies for IBD (UC + Crohn's)
- tslp: TSLP antibodies for severe asthma / COPD
- il4ra: IL-4Rα antibodies for atopic dermatitis / atopy
- igf1r: IGF1R antibodies for thyroid eye disease
- fcrn: FcRn inhibitors for autoimmune IgG diseases
- tcell: T-cell engineering / Treg therapy for immune reset (SLE, myositis)

Analyze the articles below. For each that contains meaningful new intelligence relevant to one of these areas, extract a structured record.

ARTICLES:
{articles}

Return a JSON array. Each object must have EXACTLY these fields:
- "area_id": one of: tl1a | tslp | il4ra | igf1r | fcrn | tcell
- "intel_type": one of: news | data | deal | regulatory | conference
- "importance": one of: high | medium | low
- "headline": single sentence ≤120 chars — what happened
- "body": 2-4 sentences — what happened, why it matters for BD strategy, what to watch
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
- "deal_type": one of acquisition | license | collab | option — or null
- "has_catalyst": true if article mentions an upcoming clinical/regulatory event with a date
- "catalyst_label": brief label for the catalyst event or null
- "catalyst_date": approximate date string like "Q3 2026" or "Nov 2026" or null
- "significance": high | medium | low (same as importance)

Importance guide: high=major deal/approval/Ph3 data, medium=Ph2/partnership/IND, low=preclinical/minor news
Only include articles clearly relevant to the focus areas. Skip earnings/macro news unless it directly affects a focus area program.
Return ONLY a valid JSON array, no markdown, no explanation."""


def extract_intel(articles):
    all_intel = []
    batch_size = 8

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        batch_text = "\n\n---\n\n".join(
            f"TITLE: {a['title']}\nURL: {a['url']}\nSOURCE: {a['source']}\n"
            f"DATE: {a['published'] or 'unknown'}\nAREAS MATCHED: {', '.join(a['areas'])}\n"
            f"SUMMARY: {a['summary']}"
            for a in batch
        )

        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                messages=[{"role": "user", "content": EXTRACT_PROMPT.format(articles=batch_text)}],
            )
            text = resp.content[0].text.strip()
            # Strip markdown fencing if present
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            intel = json.loads(text)
            all_intel.extend(intel)
            log(f"  Batch {i // batch_size + 1}: extracted {len(intel)} items "
                f"(${resp.usage.input_tokens/1e6*1:.4f} in / ${resp.usage.output_tokens/1e6*5:.4f} out)")
        except json.JSONDecodeError as e:
            log(f"  JSON parse error batch {i // batch_size + 1}: {e}")
        except Exception as e:
            log(f"  Extraction error batch {i // batch_size + 1}: {e}")
        time.sleep(0.5)

    log(f"Total extracted: {len(all_intel)} intel items")
    return all_intel


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


def write_to_supabase(intel_items, company_map=None):
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

        # ── intel_companies junction ───────────────────────────────────────
        company_names = item.get("company_names") or []
        written_co_ids = set()
        for co_name in company_names:
            if not co_name:
                continue
            co_id = resolve_company_id(co_name, company_map or {})
            if co_id and co_id not in written_co_ids:
                sb_post("intel_companies", {"intel_id": intel_id, "company_id": co_id})
                written_co_ids.add(co_id)

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

    articles = fetch_feeds(hours_back=48)
    relevant = filter_relevant(articles)

    if not relevant:
        log("No relevant articles found — done.")
    else:
        existing_urls = get_existing_urls()
        new_articles = [a for a in relevant if a["url"] not in existing_urls]
        log(f"New (not in Supabase): {len(new_articles)} articles")

        if new_articles:
            intel = extract_intel(new_articles)
            if intel:
                write_to_supabase(intel, company_map=company_map)

    log("=== Research complete ===")
