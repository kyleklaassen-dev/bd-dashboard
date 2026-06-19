#!/usr/bin/env python3
"""Tier 1 Signal Monitor — Meridian BD Platform

Lightweight nightly/quad-hourly scanner. No LLM. Detects biotech events from
RSS feeds and ClinicalTrials.gov updates. Scores relevance heuristically using
company and drug alias matching. High-relevance signals (score ≥ 8) trigger
targeted Tier 2 enrichment dispatch.

Sources:
  - FDA press releases RSS
  - FierceBiotech RSS
  - BioPharma Dive RSS
  - STAT News RSS
  - ClinicalTrials.gov — updates to tracked NCT IDs

Usage:
  python src/meridian/ops/signal_monitor.py
  python src/meridian/ops/signal_monitor.py --area tl1a
  python src/meridian/ops/signal_monitor.py --company abbvie
  python src/meridian/ops/signal_monitor.py --dry-run
  python src/meridian/ops/signal_monitor.py --since 2026-05-20
"""

import os, sys, json, hashlib, re, datetime, time, argparse, traceback
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path


# ── §3 split: IO/config → signal_base, scoring → signal_scoring ──
from meridian.ops.signal_base import (
    log, sb_get, sb_upsert, sb_insert, _sb_request,
    TODAY, NOW_ISO, RSS_SOURCES, TIER2_THRESHOLD,
    SUPABASE_URL, SUPABASE_KEY, SUPABASE_ANON,
)
from meridian.ops.signal_scoring import (
    score_signal, _extract_title_from_html,
    DISEASE_KEYWORDS, PHASE_KEYWORDS, DEAL_KEYWORDS, PIPELINE_KEYWORDS,
)

def load_watchlist() -> dict:
    """Load companies, areas, and aliases to build the relevance scoring inputs."""
    log("Loading watchlist from Supabase…")

    # Companies + their areas
    companies_raw = sb_get("companies", {"select": "id,name", "status": "neq.acquired", "limit": "200"})
    company_areas_raw = sb_get("company_areas", {"select": "company_id,area_id", "limit": "1000"})

    # company_id → set of area_ids
    co_areas: dict[str, set] = {}
    for ca in company_areas_raw:
        co_areas.setdefault(ca["company_id"], set()).add(ca["area_id"])

    # company_id → company name
    co_names: dict[str, str] = {c["id"]: c["name"] for c in companies_raw}

    # company aliases (all lowercased for matching)
    aliases_raw = sb_get("company_aliases", {"select": "company_id,alias_name", "limit": "1000"})
    # alias → company_id map
    alias_map: dict[str, str] = {}
    for a in aliases_raw:
        alias_map[a["alias_name"].lower()] = a["company_id"]
    # Also add company IDs and names directly
    for co_id, co_name in co_names.items():
        alias_map[co_id.lower()] = co_id
        alias_map[co_name.lower()] = co_id

    # Drug aliases (canonical drug name variants for headline matching)
    drug_aliases_raw = sb_get("drug_aliases", {"select": "canonical_id,alias_name", "limit": "2000"})
    # all drug alias strings (lowercased)
    drug_alias_set: set[str] = {a["alias_name"].lower() for a in drug_aliases_raw}

    # Also add drug display names from drugs table
    drugs_raw = sb_get("drugs", {"select": "id,display_name,name", "limit": "2000"})
    for d in drugs_raw:
        if d.get("display_name"):
            drug_alias_set.add(d["display_name"].lower())
        if d.get("name"):
            drug_alias_set.add(d["name"].lower())

    log(f"  {len(co_names)} companies | {len(alias_map)} aliases | {len(drug_alias_set)} drug aliases | {len(co_areas)} area mappings")

    return {
        "co_names":       co_names,
        "co_areas":       co_areas,
        "alias_map":      alias_map,
        "drug_alias_set": drug_alias_set,
    }


def load_tracked_trials() -> dict[str, dict]:
    """Load NCT_id → trial record for trials we're tracking.

    The trials table uses 'id' as the NCT number (e.g. 'NCT05428163').
    No company_id column on trials — we'll look up via drug_id.
    """
    trials = sb_get("trials", {"select": "id,drug_id,canonical_drug_id", "limit": "2000"})
    # drug_id → company_id lookup via drugs table
    drugs = sb_get("drugs", {"select": "id,company_id", "limit": "2000"})
    drug_co: dict[str, str] = {d["id"]: d.get("company_id","") for d in drugs}

    result: dict[str, dict] = {}
    for t in trials:
        nct = t.get("id", "")
        if nct and nct.startswith("NCT"):
            t["company_id"] = drug_co.get(t.get("drug_id",""), "")
            result[nct] = t
    return result


# ── Relevance scoring ─────────────────────────────────────────────────────────


def fetch_rss(source: dict, since_date: datetime.date | None = None) -> list[dict]:
    """Fetch and parse an RSS feed. Returns list of {headline, url, date, type, source_name}."""
    try:
        req = urllib.request.Request(
            source["url"],
            headers={"User-Agent": source.get("ua", "Mozilla/5.0")},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"  ✗ {source['name']}: fetch failed — {e}", indent=1)
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        log(f"  ✗ {source['name']}: XML parse failed — {e}", indent=1)
        return []

    items = root.findall(".//item")
    results = []
    for item in items:
        title_raw = item.findtext("title", "") or ""
        headline  = _extract_title_from_html(title_raw).strip()
        if not headline:
            # Try description as fallback
            desc = item.findtext("description", "") or ""
            headline = _extract_title_from_html(desc)[:200].strip()
        if not headline:
            continue

        url = item.findtext("link", "") or ""
        if not url:
            url = item.findtext("{http://www.w3.org/2005/Atom}link", "") or ""
        url = url.strip()

        pub_raw = item.findtext("pubDate", "") or item.findtext("dc:date", "") or ""
        event_date = _parse_date(pub_raw)

        if since_date and event_date and event_date < since_date:
            continue  # skip items older than --since

        results.append({
            "headline":    headline,
            "source_url":  url,
            "event_date":  event_date.isoformat() if event_date else TODAY,
            "signal_type": source["signal_type"],
            "source_name": source["name"],
        })

    return results


def _parse_date(raw: str) -> datetime.date | None:
    """Parse RSS pubDate strings like 'Wed, 20 May 2026 09:53:58 EDT'."""
    if not raw:
        return None
    # Try common formats
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z",
                "%a, %d %b %Y %H:%M:%S %z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d",
                "%b %d, %Y %I:%M%p"):
        try:
            return datetime.datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            pass
    # Try extracting just the date portion
    m = re.search(r'(\d{1,2})\s+(\w{3,9})\s+(\d{4})', raw)
    if m:
        try:
            return datetime.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %B %Y").date()
        except ValueError:
            try:
                return datetime.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y").date()
            except ValueError:
                pass
    return None


# ── ClinicalTrials.gov update scan ────────────────────────────────────────────

def fetch_ct_updates(tracked_trials: dict[str, dict], since_date: datetime.date | None) -> list[dict]:
    """Check ClinicalTrials.gov for status updates to tracked NCT IDs.

    Uses the CT.gov v2 API with a date filter. Returns synthetic signals for
    trials whose status, phase, or primary completion date changed.
    """
    if not tracked_trials:
        return []

    # Query recent updates from ClinicalTrials.gov for our tracked NCT IDs
    # Use the 'lastUpdatePostDate' filter for efficiency
    since_str = (since_date or datetime.date.today() - datetime.timedelta(days=2)).isoformat()

    # Build NCT ID list in batches (CT.gov has URL length limits)
    nct_ids = list(tracked_trials.keys())
    results = []

    batch_size = 20
    for i in range(0, min(len(nct_ids), 200), batch_size):  # cap at 200 trials
        batch = nct_ids[i:i+batch_size]
        query = " OR ".join(f'AREA[NCTId]{nct}' for nct in batch)

        url = (
            "https://clinicaltrials.gov/api/v2/studies"
            f"?query.term={urllib.parse.quote(query)}"
            "&fields=NCTId,BriefTitle,OverallStatus,Phase,PrimaryCompletionDate,LastUpdatePostDate"
            f"&filter.advanced=AREA[LastUpdatePostDate]RANGE[{since_str},%20MAX]"
            "&pageSize=100&format=json"
        )

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Meridian/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            log(f"  ✗ CT.gov batch {i//batch_size + 1}: {e}", indent=1)
            continue

        for study in data.get("studies", []):
            proto = study.get("protocolSection", {})
            id_mod    = proto.get("identificationModule", {})
            status_mod = proto.get("statusModule", {})

            nct_id    = id_mod.get("nctId", "")
            title     = id_mod.get("briefTitle", "")[:200]
            status    = status_mod.get("overallStatus", "")
            pcd       = status_mod.get("primaryCompletionDateStruct", {}).get("date", "")
            last_upd  = status_mod.get("lastUpdatePostDateStruct", {}).get("date", "")

            if nct_id not in tracked_trials:
                continue

            trial_info = tracked_trials[nct_id]
            co_id = trial_info.get("company_id")

            headline = f"CT.gov update: {title} ({nct_id}) — Status: {status}"
            if pcd:
                headline += f", PCD: {pcd}"

            results.append({
                "headline":    headline,
                "source_url":  f"https://clinicaltrials.gov/study/{nct_id}",
                "event_date":  last_upd or TODAY,
                "signal_type": "trial_update",
                "source_name": "ClinicalTrials.gov",
                "_co_id_hint": co_id,  # pre-identified company
            })

        time.sleep(0.3)  # be polite to CT.gov API

    return results


# ── Content fingerprint ───────────────────────────────────────────────────────

def _content_hash(co_id: str | None, headline: str, event_date: str) -> str:
    s = f"{co_id or ''}|{headline.lower()[:100]}|{event_date}"
    return hashlib.md5(s.encode()).hexdigest()


# ── Signal write ─────────────────────────────────────────────────────────────

def write_signal(item: dict, company_id: str | None, relevance_score: int, dry_run: bool) -> str | None:
    """Write signal to Supabase. Returns inserted signal id or None on dedup/failure."""
    c_hash = _content_hash(company_id, item["headline"], item.get("event_date", TODAY))

    # Check dedup on content_hash first (avoid dupe even if URL is different)
    existing = sb_get("signals", {"content_hash": f"eq.{c_hash}", "select": "id", "limit": "1"})
    if existing:
        return None  # already seen this signal

    rec = {
        "company_id":      company_id,
        "signal_type":     item["signal_type"],
        "headline":        item["headline"][:400],
        "raw_headline":    item["headline"][:400],
        "source_url":      item.get("source_url") or None,
        "content_hash":    c_hash,
        "event_date":      item.get("event_date") or TODAY,
        "relevance_score": relevance_score,
        "source_name":     item.get("source_name", ""),
        "enrichment_triggered": False,
    }

    if dry_run:
        return "dry-run-id"

    result = sb_insert("signals", rec)
    if result and isinstance(result, list) and result:
        return result[0].get("id")
    return None


def enqueue_enrichment(company_id: str, area_ids: set[str],
                       signal_id: str, priority: int, dry_run: bool) -> int:
    """Write enrichment_queue rows for each area the company is tracked in."""
    enqueued = 0
    for area_id in area_ids:
        # Skip if already pending
        existing = sb_get("enrichment_queue", {
            "company_id": f"eq.{company_id}",
            "area_id":    f"eq.{area_id}",
            "status":     "eq.pending",
            "select":     "id",
            "limit":      "1",
        })
        if existing:
            continue

        rec = {
            "company_id": company_id,
            "area_id":    area_id,
            "trigger":    "signal",
            "signal_id":  signal_id,
            "priority":   priority,
            "status":     "pending",
        }
        if not dry_run:
            sb_insert("enrichment_queue", rec)
        enqueued += 1

    return enqueued


# ── Main scan ─────────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    dry_run     = args.dry_run
    filter_co   = args.company
    filter_area = args.area
    since_date  = (datetime.date.fromisoformat(args.since)
                   if args.since else
                   datetime.date.today() - datetime.timedelta(days=2))

    log(f"Signal Monitor — {NOW_ISO}")
    log(f"  since={since_date} | dry_run={dry_run} | filter_co={filter_co} | filter_area={filter_area}")
    log("")

    watchlist     = load_watchlist()
    tracked_trials = load_tracked_trials()

    # ── Collect all candidate articles ────────────────────────────────────────
    all_items: list[dict] = []

    for source in RSS_SOURCES:
        items = fetch_rss(source, since_date=since_date)
        log(f"  {source['name']}: {len(items)} items fetched")
        all_items.extend(items)

    ct_items = fetch_ct_updates(tracked_trials, since_date=since_date)
    log(f"  ClinicalTrials.gov: {len(ct_items)} updates")
    all_items.extend(ct_items)

    log(f"\nTotal candidates: {len(all_items)}")
    log("")

    # ── Score, filter, write ───────────────────────────────────────────────────
    stats = {"scanned": 0, "relevant": 0, "new_signals": 0, "enqueued": 0, "skipped_dedup": 0}

    for item in all_items:
        stats["scanned"] += 1

        headline = item["headline"]

        # Company_id hint from CT.gov scan (pre-resolved)
        co_id_hint = item.pop("_co_id_hint", None)

        score, matched_co = score_signal(
            headline, item.get("source_url", ""), item["signal_type"], watchlist
        )
        company_id = co_id_hint or matched_co

        # Apply CLI filters
        if filter_co and company_id != filter_co:
            continue
        if filter_area and company_id:
            co_areas = watchlist["co_areas"].get(company_id, set())
            if filter_area not in co_areas:
                continue

        if score <= 0:
            continue  # no relevance signal at all

        stats["relevant"] += 1

        if args.verbose or (dry_run and score >= TIER2_THRESHOLD):
            tier2_flag = " ⚡ TIER2" if score >= TIER2_THRESHOLD else ""
            log(f"  [{score:2d}/10] {item['source_name']:20s} | co={company_id or '?':20s} | {headline[:80]}{tier2_flag}")

        # Write signal
        signal_id = write_signal(item, company_id, score, dry_run)
        if signal_id is None:
            stats["skipped_dedup"] += 1
            continue

        stats["new_signals"] += 1

        # Enqueue targeted enrichment for high-relevance signals
        if score >= TIER2_THRESHOLD and company_id:
            co_areas = watchlist["co_areas"].get(company_id, set())
            if co_areas:
                n = enqueue_enrichment(company_id, co_areas, signal_id, score, dry_run)
                stats["enqueued"] += n
                if n > 0:
                    log(f"  → Enqueued Tier 2 for {company_id} × {sorted(co_areas)} (score={score})", indent=1)

    log("")
    log("── Summary ──────────────────────────────────────────────────────────")
    log(f"  Scanned:       {stats['scanned']:>4}")
    log(f"  Relevant:      {stats['relevant']:>4}  (score > 0)")
    log(f"  New signals:   {stats['new_signals']:>4}  (written to DB)")
    log(f"  Dedup skipped: {stats['skipped_dedup']:>4}  (already in signals table)")
    log(f"  Tier 2 queued: {stats['enqueued']:>4}  (enrichment_queue rows)")
    if dry_run:
        log("  [DRY RUN — no rows written]")
    log("")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tier 1 signal monitor")
    parser.add_argument("--dry-run",  action="store_true", help="Score and log but don't write to DB")
    parser.add_argument("--company",  default=None, help="Filter to one company_id")
    parser.add_argument("--area",     default=None, help="Filter to one area_id")
    parser.add_argument("--since",    default=None, help="Only process items since this date (YYYY-MM-DD)")
    parser.add_argument("--verbose",  action="store_true", help="Print every relevant signal, not just Tier 2")
    args = parser.parse_args()

    try:
        run(args)
    except KeyboardInterrupt:
        log("\nInterrupted.")
        sys.exit(1)
    except Exception:
        log(f"\n✗ Fatal error:\n{traceback.format_exc()}")
        sys.exit(1)
