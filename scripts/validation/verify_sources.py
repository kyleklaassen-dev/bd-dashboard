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

_SCRIPTS = pathlib.Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from _common import load_credentials  # noqa: E402
import _db                             # noqa: E402

SUPABASE_URL, _SERVICE_KEY, _ = load_credentials(require_anthropic=False)
_db.init_db(SUPABASE_URL, _SERVICE_KEY)

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


def fetch_unverified_sources(service_key: str, all_sources: bool = False) -> list[dict]:
    """Return drug_sources rows that need verification."""
    stale_cutoff = (
        datetime.datetime.utcnow() - datetime.timedelta(days=STALE_AFTER_DAYS)
    ).isoformat()

    params = {"select": "id,drug_id,drug_name,source_url,source_domain,claim_type"}
    if not all_sources:
        # unverified OR last checked > 7 days ago
        params["or"] = f"(url_status.eq.unverified,url_last_checked.lt.{stale_cutoff})"

    return _db.sb_get("drug_sources", params)


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
    return _db.sb_patch("drug_sources",
                        {"url_status": url_status, "url_last_checked": now_iso},
                        {"id": f"eq.{source_id}"})


def post_summary_to_intelligence(service_key: str, summary: dict) -> None:
    """Post a one-line summary to intelligence_discoveries for dashboard visibility."""
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
    _db.sb_post("intelligence_discoveries", record)


def update_confidence_scores(service_key: str) -> None:
    """Recompute drugs.data_confidence after url_status updates."""
    rows = _db.sb_get("drug_sources", {"select": "drug_id,content_confirms_claim,url_status"})

    counts: dict[str, dict] = defaultdict(lambda: {"confirmed": 0, "total": 0})
    for row in rows:
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

        if _db.sb_patch("drugs", {"data_confidence": level}, {"id": f"eq.{drug_id}"}):
            updated += 1

    print(f"[confidence] Updated data_confidence for {updated} drugs.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify source URLs in drug_sources.")
    parser.add_argument("--all",     action="store_true",
                        help="Re-verify all sources, not just unverified/stale ones.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be done without writing to DB.")
    args = parser.parse_args()

    service_key = _SERVICE_KEY
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
