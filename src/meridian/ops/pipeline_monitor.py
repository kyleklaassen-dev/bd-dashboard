#!/usr/bin/env python3
"""
pipeline_monitor.py — Pipeline Page Change Detection

Fetches the pipeline page for each tracked company, hashes the content,
and compares against the last stored hash. When a page changes:
  1. Fires a signal (signal_type='pipeline_page_change') in the signals table
  2. Writes a discovery_queue row (source='pipeline_monitor') for human review

Designed to run nightly so any pipeline page update — new drug added, stage
advanced, program discontinued — surfaces in Meridian within 24 hours.

Usage:
  python3 scripts/pipeline_monitor.py --dry-run   # fetch + diff, no writes
  python3 scripts/pipeline_monitor.py             # fetch, diff, write on change
  python3 scripts/pipeline_monitor.py --company immunovant  # single company

Storage:
  Hashes are stored in the signals table (signal_type='pipeline_page_hash',
  source_url=<pipeline_url>, content_hash=<sha256>). The most recent hash per
  company/url is the ground truth. Using signals avoids a schema migration on
  the companies table while keeping the audit trail.

Adding new companies:
  Add an entry to PIPELINE_URLS below. The key is the company_id in Meridian;
  the value is the canonical pipeline page URL.
"""

import os
import sys
import json
import hashlib
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from html.parser import HTMLParser

# ── Supabase credentials ─────────────────────────────────────────────────────

SB_URL = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SB_KEY:
    key_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".supabase_service_key")
    if os.path.exists(key_file):
        with open(key_file) as f:
            SB_KEY = f.read().strip()

if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_KEY not set")
    sys.exit(1)

# ── Pipeline URLs to monitor ─────────────────────────────────────────────────
# key = company_id in Meridian, value = canonical pipeline page URL
# Add new companies here as they become relevant to active BD areas.

PIPELINE_URLS = {
    # ── T-cell Engineering / Autoimmune ─────────────────────────────────────
    "candid":        "https://candidtherapeutics.com/pipeline",
    "cabaletta":     "https://www.cabalettabio.com/pipeline",
    "kyverna":       "https://www.kyvernatx.com/pipeline/",
    "arcus":         "https://www.arcusbio.com/pipeline",

    # ── FcRn ────────────────────────────────────────────────────────────────
    "immunovant":    "https://www.immunovant.com/pipeline/",
    "argenx":        "https://www.argenx.com/pipeline",
    "ucb":           "https://www.ucb.com/our-science/pipeline",
    "janssen":       "https://www.janssen.com/pipeline",  # nipocalimab

    # ── TSLP / Respiratory ──────────────────────────────────────────────────
    "astrazeneca":   "https://www.astrazeneca.com/our-therapy-areas/respiratory-immunology/pipeline.html",
    "upstreambio":   "https://www.upstreambio.com/pipeline/",

    # ── IL-4Rα / Atopy ──────────────────────────────────────────────────────
    "apogee":        "https://apogeetx.com/pipeline",
    "leofarma":      "https://www.leo-pharma.com/what-we-do/pipeline",

    # ── TL1A / IBD ──────────────────────────────────────────────────────────
    "roche":         "https://www.roche.com/solutions/pipeline",
    "sanofi":        "https://www.sanofi.com/en/science-and-innovation/pipeline",
    "pfizer":        "https://www.pfizer.com/science/drug-product-pipeline",
    "abbvie":        "https://www.abbvie.com/our-science/pipeline.html",
    "merck":         "https://www.merck.com/research/pipeline/",
    "amgen":         "https://www.amgen.com/science/pipeline",
    "regeneron":     "https://www.regeneron.com/pipeline",
    "lilly":         "https://www.lilly.com/pipeline",
    "jnj":           "https://www.jnj.com/innovation/our-pharmaceutical-pipeline",

    # ── Smaller biotechs ────────────────────────────────────────────────────
    "spyre":         "https://www.spyretx.com/pipeline",
    "connectbiopharma": "https://www.connectbiopharma.com/pipeline",
    "earendil":      "https://www.earendilab.com/pipeline",
    "windward":      "https://www.windwardbio.com/pipeline",
    "aprinoia":      "https://www.aprinoia.com/pipeline",
}

# ── HTML text extractor ───────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    """Strip HTML tags and return visible text content."""
    def __init__(self):
        super().__init__()
        self._skip_tags = {"script", "style", "head", "noscript", "meta", "link"}
        self._skip = False
        self._skip_depth = 0
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip = True
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._skip_tags and self._skip:
            self._skip_depth -= 1
            if self._skip_depth <= 0:
                self._skip = False
                self._skip_depth = 0

    def handle_data(self, data):
        if not self._skip:
            stripped = data.strip()
            if stripped:
                self.chunks.append(stripped)

    def get_text(self):
        return " ".join(self.chunks)


def _extract_text(html: str) -> str:
    """Return visible text from an HTML page, suitable for hashing."""
    try:
        parser = _TextExtractor()
        parser.feed(html)
        text = parser.get_text()
        # Normalise whitespace so minor layout changes don't look like content changes
        return " ".join(text.split())
    except Exception:
        return html


def _hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


# ── Supabase helpers ──────────────────────────────────────────────────────────

def sb_get(path: str, limit: int = 2000) -> list:
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Range": f"0-{limit-1}"}
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  ⚠️  GET {path}: {e}")
        return []


def sb_post(table: str, payload: dict) -> tuple:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=data, method="POST",
        headers={
            "apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation,resolution=ignore-duplicates",
        }
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode()[:300]}"


# ── Hash storage (signals table) ──────────────────────────────────────────────

_HASH_SIGNAL_TYPE = "pipeline_page_hash"


def _load_stored_hashes() -> dict:
    """
    Load the most recent pipeline_page_hash signal per company_id.
    Returns dict: company_id → {hash, signal_id, source_url}
    """
    rows = sb_get(
        f"signals?signal_type=eq.{_HASH_SIGNAL_TYPE}"
        f"&select=company_id,content_hash,source_url,id,created_at"
        f"&order=created_at.desc&limit=500"
    )
    # Keep only the most recent per company (order desc, first wins)
    stored = {}
    for row in rows:
        cid = row.get("company_id")
        if cid and cid not in stored:
            stored[cid] = {
                "hash":       row.get("content_hash"),
                "signal_id":  row.get("id"),
                "source_url": row.get("source_url"),
            }
    return stored


def _store_hash(company_id: str, pipeline_url: str, new_hash: str, dry_run: bool) -> None:
    """Write a new hash record to the signals table."""
    if dry_run:
        return
    sb_post("signals", {
        "company_id":    company_id,
        "area_id":       None,
        "signal_type":   _HASH_SIGNAL_TYPE,
        "headline":      f"Pipeline page hash updated: {company_id}",
        "source_url":    pipeline_url,
        "content_hash":  new_hash,
        "event_date":    datetime.now(timezone.utc).date().isoformat(),
        "relevance_score": 0,
        "enrichment_triggered": False,
    })


def _fire_change_signal(company_id: str, pipeline_url: str, dry_run: bool) -> None:
    """Fire a pipeline_page_change signal when a change is detected."""
    if dry_run:
        print(f"    [DRY RUN] Would fire signal: pipeline_page_change for {company_id}")
        return
    _, err = sb_post("signals", {
        "company_id":    company_id,
        "area_id":       None,
        "signal_type":   "pipeline_page_change",
        "headline":      f"Pipeline page changed: {company_id} — review for new/updated programs",
        "source_url":    pipeline_url,
        "event_date":    datetime.now(timezone.utc).date().isoformat(),
        "relevance_score": 6,
        "enrichment_triggered": False,
    })
    if err:
        print(f"    ⚠️  Signal write failed: {err}")
    else:
        print(f"    ✅ Signal fired: pipeline_page_change / {company_id}")


def _queue_reaudit(company_id: str, pipeline_url: str, run_id: str, dry_run: bool) -> None:
    """Write a discovery_queue row prompting a re-audit when a change is detected."""
    if dry_run:
        print(f"    [DRY RUN] Would queue re-audit: {company_id}")
        return
    _, err = sb_post("discovery_queue", {
        "company_name":            company_id,
        "company_id_suggested":    company_id,
        "entity_type":             "company",
        "area_id":                 "tcell",      # placeholder — re-audit will re-score all areas
        "overlap":                 "Adjacent",
        "competition_layer":       2,
        "confidence_score":        60,
        "relevance_score":         4,
        "relevance_rationale":     f"Pipeline page content changed for {company_id} — run re-audit to check for new programs.",
        "reason":                  f"pipeline_monitor: {company_id} pipeline page changed ({pipeline_url}). Run --re-audit to diff.",
        "source":                  "pipeline_monitor",
        "suggested_dest":          "update_company",
        "discovered_by":           "pipeline_monitor",
        "status":                  "pending",
        "discovery_run_id":        run_id,
        "relationship_type":       "pipeline",
        "relationship_confidence": "medium",
        "why_discovered":          (
            f"Automated pipeline page monitor detected content change at {pipeline_url}. "
            f"Re-run: python scripts/company_intake.py --company '{company_id}' --re-audit"
        ),
    })
    if err:
        print(f"    ⚠️  Queue write failed: {err}")
    else:
        print(f"    ✅ Queued re-audit: {company_id}")


# ── Page fetch ────────────────────────────────────────────────────────────────

def _fetch_page(url: str, timeout: int = 15) -> str | None:
    """
    Fetch a URL and return normalised visible text.
    Returns None on error.
    Note: many pipeline pages are JavaScript-rendered; raw fetch captures the
    HTML shell + any server-rendered text. Enough for change detection even if
    not all content is present.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; MeridianPipelineMonitor/1.0; "
                    "+https://github.com/kyleklaassen-dev/bd-dashboard)"
                )
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return _extract_text(raw)
    except Exception as e:
        return None


# ── Main monitor loop ─────────────────────────────────────────────────────────

def run(dry_run: bool = False, company_filter: str | None = None) -> None:
    ts     = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    run_id = f"pipeline_monitor_{ts}"

    print("=" * 65)
    print("  PIPELINE MONITOR")
    print(f"  Run: {run_id}")
    if dry_run:
        print("  [DRY RUN — no writes to DB]")
    print("=" * 65)

    # Load stored hashes
    stored = _load_stored_hashes()
    print(f"\n  Stored hashes loaded: {len(stored)} companies")

    # Filter companies if requested
    companies = {k: v for k, v in PIPELINE_URLS.items()
                 if company_filter is None or k == company_filter}

    print(f"  Companies to check: {len(companies)}\n")

    results = {"unchanged": 0, "changed": 0, "new": 0, "error": 0}

    for company_id, url in sorted(companies.items()):
        print(f"  {company_id:25} → {url[:60]}")

        # Fetch page
        text = _fetch_page(url)
        if text is None:
            print(f"    ⚠️  Fetch failed — skipping")
            results["error"] += 1
            continue

        if len(text) < 100:
            print(f"    ⚠️  Page content too short ({len(text)} chars) — likely JS-rendered shell, skipping hash")
            results["error"] += 1
            continue

        new_hash = _hash_content(text)

        # Compare
        prev = stored.get(company_id)
        if prev is None:
            # First time we've seen this company
            print(f"    ✦  NEW — storing baseline hash (content: {len(text)} chars)")
            _store_hash(company_id, url, new_hash, dry_run)
            results["new"] += 1

        elif prev["hash"] == new_hash:
            print(f"    ✓  Unchanged")
            results["unchanged"] += 1

        else:
            print(f"    ⚡ CHANGED — hash mismatch (content: {len(text)} chars)")
            _fire_change_signal(company_id, url, dry_run)
            _queue_reaudit(company_id, url, run_id, dry_run)
            _store_hash(company_id, url, new_hash, dry_run)
            results["changed"] += 1

    # Summary
    print("\n" + "=" * 65)
    print("SUMMARY")
    print("-" * 40)
    print(f"  Unchanged:           {results['unchanged']}")
    print(f"  Changed (⚡):        {results['changed']}")
    print(f"  New (baseline set):  {results['new']}")
    print(f"  Errors:              {results['error']}")
    if results["changed"]:
        print(f"\n  ⚡ {results['changed']} pipeline page(s) changed.")
        print(f"  Review in Meridian → Signals panel and Discovery Queue.")
        print(f"  Re-audit changed companies:")
        print(f"    python scripts/company_intake.py --company '<company>' --re-audit")
    if dry_run:
        print("\n  [DRY RUN] No changes written. Re-run without --dry-run to persist.")
    print("=" * 65)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline page change detection — hash pipeline pages and fire signals on change",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/pipeline_monitor.py --dry-run        # check all, no writes
  python3 scripts/pipeline_monitor.py                  # check all, write on change
  python3 scripts/pipeline_monitor.py --company ucb    # single company
  python3 scripts/pipeline_monitor.py --company immunovant --dry-run

To add a company:
  Edit the PIPELINE_URLS dict near the top of this file.
  Add: "company_id": "https://company.com/pipeline"
  Run once to set baseline: python3 scripts/pipeline_monitor.py --company <id>
        """,
    )
    parser.add_argument("--dry-run",  action="store_true", help="Fetch and compare but do not write to DB")
    parser.add_argument("--company",  type=str, default=None,
                        help="Only check one company by company_id (e.g. 'immunovant')")
    args = parser.parse_args()

    run(dry_run=args.dry_run, company_filter=args.company)
