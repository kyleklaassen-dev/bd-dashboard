#!/usr/bin/env python3
"""
One-run migration: creates governance_violations table and seeds initial violations.

Purpose:
  governance_violations is a soft-constraint enforcement table. Rather than
  hard-blocking inserts that violate governance rules (which would break enrichment),
  this table logs violations for human review. Key rules enforced:
  - brand_name_implies_approved: drug has brand_name but non-approved stage
  - codev_requires_source_url: deal/partnership has no source_url
  - approval_date_implies_approved: drug has approval milestone but non-approved stage

Usage:
    python3 scripts/apply_governance_violations.py

If automated execution is unavailable, the script prints the full SQL for manual
paste into: https://supabase.com/dashboard/project/tghntyofptvfhmtchwcv/sql/new
"""

import os, sys, pathlib

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests",
                           "--break-system-packages", "-q"])
    import requests

BASE_DIR     = pathlib.Path(__file__).parent.parent
SQL_FILE     = BASE_DIR / "migrations" / "legacy" / "schema_migration_governance_v1.sql"
KEY_FILE     = BASE_DIR / ".supabase_service_key"
SUPABASE_URL = "https://tghntyofptvfhmtchwcv.supabase.co"

DASHBOARD_URL = (
    "https://supabase.com/dashboard/project/"
    "tghntyofptvfhmtchwcv/sql/new"
)

VERIFICATION = [
    ("Table exists (expect rows >= 0)",
     "governance_violations?select=id&limit=1"),
    ("Unresolved violations",
     "governance_violations?select=rule_name,table_name,row_id&resolved=eq.false&limit=20"),
    ("brand_name violations",
     "governance_violations?select=row_id,description&rule_name=eq.brand_name_implies_approved&resolved=eq.false"),
    ("source_url violations",
     "governance_violations?select=row_id,description&rule_name=eq.codev_requires_source_url&resolved=eq.false"),
]


def load_service_key():
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if key:
        return key
    sys.exit("ERROR: .supabase_service_key not found.")


def headers(service_key):
    return {
        "apikey":        service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type":  "application/json",
        "Prefer":        "return=minimal",
    }


def table_exists(service_key):
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/governance_violations?select=id&limit=1",
        headers=headers(service_key),
        timeout=15,
    )
    return resp.status_code in (200, 206)


def run_sql_automated(service_key, sql):
    """Attempt automated DDL via pg-meta endpoint."""
    resp = requests.post(
        f"{SUPABASE_URL}/pg-meta/v0/query",
        headers=headers(service_key),
        json={"query": sql},
        timeout=60,
    )
    if resp.status_code == 404:
        return None
    if not resp.ok:
        return {"error": f"HTTP {resp.status_code}: {resp.text[:300]}"}
    try:
        return resp.json()
    except Exception:
        return {"ok": True, "raw": resp.text[:100]}


def verify(service_key):
    h = {
        "apikey":        service_key,
        "Authorization": f"Bearer {service_key}",
    }
    print("\n-- Verification --")
    for label, path in VERIFICATION:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers=h,
            timeout=15,
        )
        if resp.status_code in (200, 206):
            data = resp.json()
            print(f"  OK {label}: {len(data)} rows")
            for row in data[:5]:
                print(f"    {row}")
        else:
            print(f"  FAIL {label}: HTTP {resp.status_code} -- {resp.text[:100]}")


def print_manual_instructions(sql):
    print("\n" + "=" * 70)
    print("MANUAL EXECUTION REQUIRED")
    print("=" * 70)
    print(f"\n1. Open: {DASHBOARD_URL}")
    print("2. Paste the SQL below into the editor")
    print("3. Click 'Run' (or Cmd+Enter)")
    print("4. Run this script again to verify")
    print(f"\n-- SQL ({len(sql)} chars) --")
    print(sql)
    print("-- END SQL --")


def main():
    print("-" * 70)
    print("Meridian -- governance_violations migration")
    print("-" * 70)

    service_key = load_service_key()

    print("\n[1] Checking if governance_violations already exists...")
    if table_exists(service_key):
        print("    Table already exists.")
        print("[2] Running verification queries...")
        verify(service_key)
        return

    print("    Table not found -- proceeding with migration.")

    if not SQL_FILE.exists():
        sys.exit(f"ERROR: SQL file not found: {SQL_FILE}")
    sql = SQL_FILE.read_text()
    print(f"[2] Loaded: {SQL_FILE.name} ({len(sql)} chars)")

    print("[3] Attempting automated execution via pg-meta...")
    result = run_sql_automated(service_key, sql)

    if result is None:
        print("    pg-meta endpoint not available.")
        print_manual_instructions(sql)
        sys.exit(0)

    if "error" in result:
        print(f"    Automated execution failed: {result['error']}")
        print_manual_instructions(sql)
        sys.exit(1)

    print(f"    Automated execution result: {result}")

    print("[4] Verifying migration...")
    verify(service_key)
    print("\nDone.")


if __name__ == "__main__":
    main()
