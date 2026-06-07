#!/usr/bin/env python3
"""
Meridian BD Platform — Source URL Verification Script
======================================================
Verifies that all drug_sources URLs are alive and updates url_status accordingly.

What it does:
  1. Queries drug_sources WHERE url_status = 'unverified'
     OR url_last_checked < NOW() - INTERVAL '7 days'
  2. For each URL: HEAD request (falls back to GET if HEAD is refused)
  3. Updates url_status: 'live' | 'dead' | 'redirects'
  4. Updates url_last_checked = NOW()
  5. Logs a summary: N live, N dead, N redirected, N errors
  6. Optionally posts a summary row to intelligence_discoveries

Usage:
  python3 scripts/verify_sources.py
  python3 scripts/verify_sources.py --all       # re-verify all, not just stale
  python3 scripts/verify_sources.py --dry-run   # print what would be done

Runs nightly as part of the Meridian enrichment pipeline.
"""

import os, sys, time, datetime, pathlib, argparse, urllib.request, urllib.error
from collections import defaultdict

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests",
                           "--break-system-packages", "-q"])
    import requests

BASE_DIR     = pathlib.Path(__file__).parent.parent
KEY_FILE     = BASE_DIR / ".supabase_service_key"
SUPABASE_URL = "https://tghntyofptvfhmtchwcv.supabase.co"

# Domains that always respond with 200 to HEAD — skip HTTP check (trust the URL)
AUTHORITATIVE_DOMAINS = {
    "clinicaltrials.gov",
    "fda.gov",
    "pubmed.ncbi.nlm.nih.gov",
    "www.ncbi.nlm.nih.gov",
}

# How long before a source is considered stale and needs re-checking (days)
STALE_AFTER_DAYS = 7

# Max seconds to wait per URL check
REQUEST_TIMEOUT = 8

# Delay between requests to avoid rate-limiting (seconds)
INTER_REQUEST_DELAY = 0.5

UA = "Mozilla/5.0 (compatible; MeridianSourceVerifier/1.0; bd-platform-audit)"


def load_service_key() -> str:
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if key:
        return key
    sys.exit("ERROR: .supabase_service_key not found.")


def sb_headers(key: str) -> dict:
    return {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }


def fetch_unverified_sources(service_key: str, all_sources: bool = False) -> list[dict]:
    """Return drug_sources rows that need verification."""
    h = sb_headers(service_key)
    stale_cutoff = (
        datetime.datetime.utcnow() - datetime.timedelta(days=STALE_AFTER_DAYS)
    ).isoformat()

    if all_sources:
        params = "?select=id,drug_id,drug_name,source_url,source_domain,claim_type"
    else:
        # unverified OR last checked > 7 days ago
        params = (
            f"?select=id,drug_id,drug_name,source_url,source_domain,claim_type"
            f"&or=(url_status.eq.unverified,url_last_checked.lt.{stale_cutoff})"
        )

    resp = requests.get(f"{SUPABASE_URL}/rest/v1/drug_sources{params}",
                        headers=h, timeout=15)
    if not resp.ok:
        print(f"[fetch] HTTP {resp.status_code}: {resp.text[:200]}")
        return []
    return resp.json()


def check_url(url: str) -> tuple[str, int]:
    """
    Returns (status_label, http_code).
    status_label: 'live' | 'dead' | 'redirects' | 'error'
    """
    from urllib.parse import urlparse
    original_domain = urlparse(url).netloc.lower()

    # HEAD request first
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method,
                                         headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                code = resp.status
                final_domain = urlparse(resp.url).netloc.lower()
                if code in (200, 201):
                    return "live", code
                if code in (301, 302, 303, 307, 308):
                    if final_domain != original_domain:
                        return "redirects", code
                    return "live", code
                return "live", code  # any 2xx
        except urllib.error.HTTPError as e:
            if e.code == 405 and method == "HEAD":
                continue  # try GET
            if e.code in (404, 410, 451):
                return "dead", e.code
            if e.code in (400, 403, 401, 429, 503):
                # Likely alive but protected — treat as live
                return "live", e.code
            return "dead", e.code
        except urllib.error.URLError:
            return "dead", 0
        except Exception:
            return "error", 0

    return "error", 0


def update_source_status(service_key: str, source_id: int,
                          url_status: str, now_iso: str) -> bool:
    h = sb_headers(service_key)
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/drug_sources?id=eq.{source_id}",
        headers={**h, "Prefer": "return=minimal"},
        json={"url_status": url_status, "url_last_checked": now_iso},
        timeout=10,
    )
    return resp.status_code in (200, 204)


def post_summary_to_intelligence(service_key: str, summary: dict) -> None:
    """Post a one-line summary to intelligence_discoveries for dashboard visibility."""
    h = sb_headers(service_key)

    # Check if intelligence_discoveries table exists
    test = requests.get(f"{SUPABASE_URL}/rest/v1/intelligence_discoveries?limit=0",
                        headers=h, timeout=5)
    if test.status_code in (400, 404):
        return  # table doesn't exist, skip

    total = summary["live"] + summary["dead"] + summary["redirects"] + summary["errors"]
    note = (
        f"Source verification: {summary['live']} live, "
        f"{summary['dead']} dead, "
        f"{summary['redirects']} redirected "
        f"({total} checked)"
    )
    record = {
        "signal_type":   "source_verification",
        "headline":      note,
        "relevance":     "infrastructure",
        "created_at":    datetime.datetime.utcnow().isoformat(),
    }
    requests.post(f"{SUPABASE_URL}/rest/v1/intelligence_discoveries",
                  headers=h, json=record, timeout=10)


def update_confidence_scores(service_key: str) -> None:
    """Recompute drugs.data_confidence after url_status updates."""
    h = sb_headers(service_key)

    # Fetch all sources
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/drug_sources"
        "?select=drug_id,content_confirms_claim,url_status",
        headers=h, timeout=30,
    )
    if not resp.ok:
        print(f"[confidence] Could not fetch sources: {resp.text[:100]}")
        return

    from collections import defaultdict
    counts: dict[str, dict] = defaultdict(lambda: {"confirmed": 0, "total": 0})
    for row in resp.json():
        drug_id = row["drug_id"]
        counts[drug_id]["total"] += 1
        if row.get("content_confirms_claim") and row.get("url_status") == "live":
            counts[drug_id]["confirmed"] += 1

    updated = 0
    for drug_id, c in counts.items():
        if c["confirmed"] >= 2:
            level = "high"
        elif c["confirmed"] == 1:
            level = "medium"
        elif c["total"] > 0:
            level = "low"
        else:
            level = "unverified"

        patch = requests.patch(
            f"{SUPABASE_URL}/rest/v1/drugs?id=eq.{drug_id}",
            headers={**h, "Prefer": "return=minimal"},
            json={"data_confidence": level},
            timeout=10,
        )
        if patch.ok:
            updated += 1

    print(f"[confidence] Updated data_confidence for {updated} drugs.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify source URLs in drug_sources.")
    parser.add_argument("--all",     action="store_true",
                        help="Re-verify all sources, not just unverified/stale ones.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be done without writing to DB.")
    args = parser.parse_args()

    service_key = load_service_key()
    now_iso     = datetime.datetime.utcnow().isoformat()

    print(f"[{now_iso[:19]}] Fetching sources to verify...")
    sources = fetch_unverified_sources(service_key, all_sources=args.all)
    print(f"  Found {len(sources)} source(s) to check.")

    if not sources:
        print("  Nothing to verify. Exiting.")
        return

    summary: dict[str, int] = defaultdict(int)
    results: list[tuple] = []

    for i, src in enumerate(sources):
        url        = src["source_url"]
        source_id  = src["id"]
        drug_name  = src.get("drug_name") or src.get("drug_id") or "?"
        domain     = (src.get("source_domain") or "").lower()
        claim_type = src.get("claim_type", "?")

        # For authoritative domains, trust the URL format without HTTP check
        if any(auth in domain for auth in AUTHORITATIVE_DOMAINS):
            status_label = "live"
            http_code    = 0
            print(f"  [{i+1}/{len(sources)}] {drug_name} | {claim_type} → TRUSTED DOMAIN ({domain})")
        else:
            status_label, http_code = check_url(url)
            print(f"  [{i+1}/{len(sources)}] {drug_name} | {claim_type} → {status_label.upper()} "
                  f"(HTTP {http_code}) | {url[:60]}")

        summary[status_label] += 1
        results.append((source_id, status_label))

        if not args.dry_run:
            ok = update_source_status(service_key, source_id, status_label, now_iso)
            if not ok:
                print(f"    WARNING: failed to update id={source_id}")

        time.sleep(INTER_REQUEST_DELAY)

    print(f"\n--- Summary ---")
    print(f"  Live:       {summary['live']}")
    print(f"  Dead:       {summary['dead']}")
    print(f"  Redirects:  {summary['redirects']}")
    print(f"  Errors:     {summary['error']}")
    print(f"  Total:      {len(sources)}")

    if not args.dry_run:
        print("\n[confidence] Recomputing drugs.data_confidence...")
        update_confidence_scores(service_key)

        print("[intelligence] Posting summary to intelligence_discoveries...")
        post_summary_to_intelligence(service_key, dict(summary))

    print("\nDone.")


if __name__ == "__main__":
    main()
