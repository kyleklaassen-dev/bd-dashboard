#!/usr/bin/env python3
"""
refresh_target_pair_whitespace.py — recount competing bispecifics in
target_pair_whitespace from the live drugs table.

Extracted from weekend_sprint.py phase D9 (the sprint is retired). Keeps the
dashboard's target_pair_whitespace counts fresh. Run weekly via
meridian-weekly-maintenance.yml.

  python scripts/refresh_target_pair_whitespace.py            # write
  python scripts/refresh_target_pair_whitespace.py --dry-run  # no writes
"""
import os
import sys
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
if not SUPABASE_KEY:
    for _f in (".supabase_service_key",):
        _p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), _f)
        if os.path.exists(_p):
            SUPABASE_KEY = open(_p).read().strip()
            break

_BASE = f"{SUPABASE_URL}/rest/v1"
_HDRS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json"}

P1_STAGES = ("phase 1", "phase i", "phase1")
P2_STAGES = ("phase 2", "phase ii", "phase2", "phase 2/3", "phase 2a", "phase 2b")


def _req(method: str, path: str, params: dict | None = None, payload: dict | None = None):
    url = f"{_BASE}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={**_HDRS, "Prefer": "return=minimal"}, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        return json.loads(body) if body and method == "GET" else None


def table_exists(tname: str) -> bool:
    try:
        _req("GET", tname, {"limit": "1"})
        return True
    except urllib.error.HTTPError as e:
        return e.code != 404
    except Exception:
        return False


def refresh(dry_run: bool = False) -> dict:
    results = {"rows_checked": 0, "rows_updated": 0}
    if not table_exists("target_pair_whitespace"):
        print("  target_pair_whitespace table not found — skipping")
        return {"skipped": "table_missing"}

    rows = _req("GET", "target_pair_whitespace", {"select": "id,target_a,target_b", "limit": "200"}) or []
    drugs = _req("GET", "drugs", {"select": "id,target,stage", "limit": "1000"}) or []

    for row in rows:
        results["rows_checked"] += 1
        ta = (row.get("target_a") or "").lower()
        tb = (row.get("target_b") or "").lower()
        if not ta or not tb:
            continue
        p1 = sum(1 for d in drugs
                 if ta in (d.get("target") or "").lower() and tb in (d.get("target") or "").lower()
                 and (d.get("stage") or "").lower() in P1_STAGES)
        p2 = sum(1 for d in drugs
                 if ta in (d.get("target") or "").lower() and tb in (d.get("target") or "").lower()
                 and (d.get("stage") or "").lower() in P2_STAGES)
        if dry_run:
            print(f"  [DRY-RUN] {ta}×{tb}: P1={p1}, P2={p2}")
            continue
        try:
            _req("PATCH", "target_pair_whitespace", {"id": f"eq.{row['id']}"},
                 {"competing_bispecifics_phase1": p1, "competing_bispecifics_phase2": p2})
            results["rows_updated"] += 1
        except Exception as e:
            print(f"  Row {row['id']} update failed: {e}")

    print(f"  target_pair_whitespace: {results['rows_checked']} checked, "
          f"{results['rows_updated']} updated{' [DRY RUN]' if dry_run else ''}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh target_pair_whitespace competing-bispecific counts")
    parser.add_argument("--dry-run", action="store_true", help="Compute only, no DB writes")
    args = parser.parse_args()
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_SERVICE_KEY not set and .supabase_service_key not found")
        sys.exit(1)
    refresh(dry_run=args.dry_run)
