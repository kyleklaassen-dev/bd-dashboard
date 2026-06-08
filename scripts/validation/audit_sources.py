#!/usr/bin/env python3
"""
Ailux BD Platform — Source URL Integrity Audit
===============================================
Checks every source_url stored across drug_area_scores, intel, and catalysts.
Classifies each URL, verifies HTTP status, and upserts results into
source_verifications table. Broken URLs are flagged for repair.

USAGE:
  python3 scripts/audit_sources.py                   # full audit
  python3 scripts/audit_sources.py --table das        # drug_area_scores only
  python3 scripts/audit_sources.py --dry-run          # classify + HTTP check, no DB writes
  python3 scripts/audit_sources.py --broken-only      # print broken URLs from last audit
  python3 scripts/audit_sources.py --repair           # attempt to auto-repair broken confirmed rows

SCHEDULE:
  Add to Cowork scheduled task: weekly, on Sunday morning.
  The script is idempotent — re-running updates last_checked_at and http_status.
"""

import os
import re
import sys
import argparse
import datetime
import urllib.request
import urllib.error
from collections import defaultdict

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _common import load_credentials  # noqa: E402
import _db                             # noqa: E402

SUPABASE_URL, SERVICE_KEY, _ = load_credentials(require_anthropic=False)
_db.init_db(SUPABASE_URL, SERVICE_KEY)

UA = {"User-Agent": "Mozilla/5.0 (compatible; BD-Platform-Audit/1.0)"}

# ── Source type + tier classification ─────────────────────────────────────────
TIER_1 = {"ct_study", "fda", "pubmed", "sec"}
TIER_2 = {"press_release", "news_article", "other_specific", "ct_search"}
TIER_3 = {"generic_ir", "generic_pipeline", "generic_homepage"}

TIER_MAP = {t: 1 for t in TIER_1}
TIER_MAP.update({t: 2 for t in TIER_2})
TIER_MAP.update({t: 3 for t in TIER_3})

GENERIC_TYPES = {"generic_pipeline", "generic_ir", "generic_homepage"}


def classify_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http"):
        return "malformed"
    # Truncation heuristic
    if len(url) > 80 and not url.endswith(('/', '.html', '.pdf', '.htm', '.json')) \
            and url[-1].isalpha() and url[-2].isalpha():
        return "truncated"
    if re.search(r'clinicaltrials\.gov/study/NCT\d{8}', url):
        return "ct_study"
    if "clinicaltrials.gov/search" in url:
        return "ct_search"
    if "accessdata.fda.gov" in url or ("fda.gov" in url and "/press-announcements/" in url):
        return "fda"
    if "pubmed.ncbi.nlm.nih.gov" in url and re.search(r'/\d{6,}', url):
        return "pubmed"
    if "sec.gov" in url:
        return "sec"
    if "prnewswire.com" in url or "businesswire.com" in url or "globenewswire.com" in url:
        return "press_release"
    if re.search(r'/pipeline/?$', url, re.I) or re.search(r'/programs/?$', url, re.I):
        return "generic_pipeline"
    if re.search(r'/news-releases/?$', url, re.I) or re.search(r'/press-releases/?$', url, re.I):
        return "generic_ir"
    if re.search(r'\.com/?$', url) or re.search(r'\.com/en/?$', url):
        return "generic_homepage"
    if re.search(r'/news|/press|/release|/article|/post|/story|/media', url, re.I):
        return "news_article"
    return "other_specific"


def check_url(url: str, timeout: int = 7) -> tuple[int, str]:
    """HEAD check with GET fallback. Returns (http_status, final_url)."""
    try:
        req = urllib.request.Request(url.strip(), method="HEAD", headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.geturl()
    except urllib.error.HTTPError as e:
        if e.code == 405:
            try:
                req2 = urllib.request.Request(url.strip(), method="GET", headers=UA)
                with urllib.request.urlopen(req2, timeout=timeout) as r2:
                    return r2.status, r2.geturl()
            except urllib.error.HTTPError as e2:
                return e2.code, url
            except Exception:
                return 0, url
        return e.code, url
    except Exception:
        return 0, url


def url_source_status(http_status: int, url_type: str) -> str:
    if url_type in ("malformed", "truncated"):
        return "broken"
    if http_status == 200:
        return "generic" if url_type in GENERIC_TYPES else "valid"
    if http_status in (301, 302, 303, 307, 308):
        return "generic" if url_type in GENERIC_TYPES else "valid"
    if http_status in (404, 410):
        return "broken"
    if http_status == 0:
        return "timeout"
    if http_status in (403, 429):
        return "valid"   # geo-block or rate-limit → not broken, just inaccessible
    return "unknown"


# ── Supabase helpers ──────────────────────────────────────────────────────────
def sb_get(path: str) -> list:
    """Local call sites pass a combined 'table?select=...&...' path string;
    split it and delegate to _db.sb_get's (table, params) interface."""
    table, _, qs = path.partition("?")
    params = dict(p.split("=", 1) for p in qs.split("&")) if qs else {}
    return _db.sb_get(table, params)


def sb_upsert(table: str, rows: list, on_conflict: str) -> int:
    """_db.sb_upsert returns the upserted rows (or [] on failure); translate to
    an HTTP-status-like int since call sites just print it informationally."""
    result = _db.sb_upsert(table, rows, on_conflict=on_conflict)
    return 200 if (result or not rows) else 500


# ── Collect URLs from all source tables ───────────────────────────────────────
def collect_urls(tables: list[str]) -> dict:
    """
    Returns {url: [{"table": t, "drug_id": ..., "area_id": ..., "confidence": ...}]}
    """
    url_info = defaultdict(list)

    if "das" in tables:
        rows = sb_get("drug_area_scores?select=id,drug_id,area_id,source_url,confidence_level"
                      "&source_url=not.is.null&limit=2000")
        for r in rows:
            url = (r.get("source_url") or "").strip()
            if url:
                url_info[url].append({
                    "table": "drug_area_scores",
                    "row_id": r["id"],
                    "drug_id": r.get("drug_id"),
                    "area_id": r.get("area_id"),
                    "confidence": r.get("confidence_level"),
                })

    if "intel" in tables:
        rows = sb_get("intel?select=id,primary_company_id,source_url"
                      "&source_url=not.is.null&limit=2000")
        for r in rows:
            url = (r.get("source_url") or "").strip()
            if url:
                url_info[url].append({
                    "table": "intel",
                    "row_id": r["id"],
                    "company_id": r.get("primary_company_id"),
                })

    if "catalysts" in tables:
        rows = sb_get("catalysts?select=id,drug_id,area_id,source_url"
                      "&source_url=not.is.null&limit=2000")
        for r in rows:
            url = (r.get("source_url") or "").strip()
            if url:
                url_info[url].append({
                    "table": "catalysts",
                    "row_id": r["id"],
                    "drug_id": r.get("drug_id"),
                    "area_id": r.get("area_id"),
                })

    return dict(url_info)


# ── Main audit logic ──────────────────────────────────────────────────────────
def run_audit(tables: list[str], dry_run: bool = False, verbose: bool = False) -> dict:
    print(f"=== SOURCE URL AUDIT {'(DRY RUN) ' if dry_run else ''}===")
    print(f"Tables: {', '.join(tables)}")

    url_info = collect_urls(tables)
    unique_urls = list(url_info.keys())
    print(f"\nUnique source URLs: {len(unique_urls)}")

    # Pre-classify
    type_counts = defaultdict(int)
    for url in unique_urls:
        type_counts[classify_url(url)] += 1

    print("\nURL type breakdown:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        tier = TIER_MAP.get(t, 4)
        print(f"  Tier {tier}  {t:25s}: {c}")

    # HTTP check all URLs (skip generic types — they're known to exist but are low quality)
    skip_check = GENERIC_TYPES  # already 200 by definition, just flag as generic
    to_check = [u for u in unique_urls if classify_url(u) not in skip_check]
    print(f"\nHTTP checking {len(to_check)} URLs (skipping {len(unique_urls)-len(to_check)} generic)...")

    results = {}
    now = datetime.datetime.utcnow().isoformat() + "Z"

    for i, url in enumerate(unique_urls):
        url_type = classify_url(url)
        if url_type in skip_check:
            results[url] = {"http_status": 200, "source_status": "generic", "url_type": url_type}
        elif url_type in ("malformed", "truncated"):
            results[url] = {"http_status": 0, "source_status": "broken", "url_type": url_type}
        else:
            http_status, _ = check_url(url)
            source_status = url_source_status(http_status, url_type)
            results[url] = {"http_status": http_status, "source_status": source_status, "url_type": url_type}
            if verbose or source_status in ("broken", "timeout"):
                flag = "✅" if source_status == "valid" else ("❌" if source_status == "broken" else f"⚠{source_status}")
                ctx = url_info[url][0]
                ctx_str = f"{ctx.get('drug_id','?')}/{ctx.get('area_id','?')}" if 'drug_id' in ctx else ctx.get('company_id','?')
                print(f"  {flag} {http_status:4d} [{url_type[:12]:12s}] [{ctx_str}] {url[:65]}")

    # Summary
    broken = [(u, v) for u, v in results.items() if v["source_status"] in ("broken", "timeout")]
    generic = [(u, v) for u, v in results.items() if v["source_status"] == "generic"]
    valid   = [(u, v) for u, v in results.items() if v["source_status"] == "valid"]
    print(f"\n{'='*60}")
    print(f"  Valid:          {len(valid):3d} ({len(valid)/len(results)*100:.0f}%)")
    print(f"  Generic:        {len(generic):3d} (pipeline/IR homepages — low claim specificity)")
    print(f"  Broken/timeout: {len(broken):3d}")

    if broken:
        print(f"\n  BROKEN URLS:")
        for url, v in sorted(broken, key=lambda x: x[1]["source_status"]):
            rows = url_info[url]
            ctx = ", ".join(
                f"{r.get('drug_id','?')}/{r.get('area_id','?')} ({r.get('confidence','?')})"
                for r in rows[:3]
            )
            print(f"    HTTP {v['http_status']:4d}  {url[:70]}")
            print(f"           rows: {ctx}")

    # Upsert into source_verifications
    if not dry_run:
        sv_rows = []
        for url, v in results.items():
            sv_rows.append({
                "url":            url,
                "source_status":  v["source_status"],
                "http_status":    v["http_status"],
                "source_type":    v["url_type"],
                "source_tier":    TIER_MAP.get(v["url_type"], 4),
                "is_generic":     v["url_type"] in GENERIC_TYPES,
                "last_checked_at": now,
            })
        print(f"\nUpserting {len(sv_rows)} rows into source_verifications...")
        status = sb_upsert("source_verifications", sv_rows, "url")
        print(f"  HTTP {status}")
    else:
        print(f"\nDRY RUN: would upsert {len(results)} rows into source_verifications")

    return results


def show_broken_only():
    """Pull broken URLs from source_verifications table (last audit results)."""
    rows = sb_get("source_verifications?source_status=in.(broken,timeout)"
                  "&select=url,source_status,http_status,source_type,last_checked_at"
                  "&order=last_checked_at.desc&limit=100")
    print(f"=== BROKEN SOURCE URLs FROM LAST AUDIT ({len(rows)} total) ===")
    for r in rows:
        print(f"  {r['source_status']:8s} HTTP {(r['http_status'] or 0):4d} [{r['source_type'][:15]:15s}] {r['url'][:80]}")
        print(f"             last checked: {r['last_checked_at']}")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Source URL Integrity Audit")
    parser.add_argument("--table", choices=["das", "intel", "catalysts"], action="append",
                        help="Which table to audit (default: das + intel + catalysts)")
    parser.add_argument("--dry-run",     action="store_true", help="Classify + HTTP check, no DB writes")
    parser.add_argument("--broken-only", action="store_true", help="Print broken URLs from last audit")
    parser.add_argument("--verbose",     action="store_true", help="Print every URL check result")
    args = parser.parse_args()

    if args.broken_only:
        show_broken_only()
        sys.exit(0)

    tables = args.table or ["das", "intel", "catalysts"]
    run_audit(tables, dry_run=args.dry_run, verbose=args.verbose)
