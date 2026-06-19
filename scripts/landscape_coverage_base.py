#!/usr/bin/env python3
"""
landscape_coverage_base.py — IO + creds + dry-run gate for compute_landscape_coverage.py (§3 split).

Holds the Supabase REST helpers (get/patch/insert), the section() printer, the
credentials, and the import-time DRY_RUN flag (read by patch/insert so writes are
suppressed under --dry-run). Extracted verbatim. The metrics module imports get();
the orchestrator imports get/patch/insert/section.
"""
import json, os, sys, urllib.request, urllib.error, urllib.parse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SB_URL   = "https://tghntyofptvfhmtchwcv.supabase.co"
DRY_RUN  = "--dry-run" in sys.argv

with open(os.path.join(BASE_DIR, ".supabase_service_key")) as f:
    SERVICE_KEY = f.read().strip()

HEADERS_READ = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}
HEADERS_PATCH = {**HEADERS_READ, "Prefer": "return=representation"}
HEADERS_INSERT = {**HEADERS_READ, "Prefer": "resolution=ignore-duplicates,return=representation"}


def get(table, params, limit=1000):
    params = {**params, "limit": str(limit)}
    qs = "&".join(
        f"{k}={urllib.parse.quote(str(v), safe='.()*,=')}" for k, v in params.items()
    )
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{table}?{qs}", headers=HEADERS_READ)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  GET {table} HTTP {e.code}: {e.read().decode()[:300]}")
        return []


def patch(table, filters, updates):
    if DRY_RUN:
        return True
    qs = "&".join(
        f"{k}={urllib.parse.quote(str(v), safe='.()*,')}" for k, v in filters.items()
    )
    data = json.dumps(updates).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}?{qs}",
        data=data,
        headers={**HEADERS_PATCH},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req) as r:
            r.read()
            return True
    except urllib.error.HTTPError as e:
        print(f"  PATCH {table} HTTP {e.code}: {e.read().decode()[:300]}")
        return False


def insert(table, rows):
    if DRY_RUN or not rows:
        return len(rows)
    data = json.dumps(rows if isinstance(rows, list) else [rows]).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=data,
        headers=HEADERS_INSERT,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read()) if r.status in (200, 201) else []
            return len(result) if result else len(rows)
    except urllib.error.HTTPError as e:
        print(f"  INSERT {table} HTTP {e.code}: {e.read().decode()[:300]}")
        return 0


def section(title):
    print(f"\n{'═'*60}\n  {title}\n{'═'*60}")
