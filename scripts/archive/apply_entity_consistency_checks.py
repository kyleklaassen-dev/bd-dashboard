#!/usr/bin/env python3
"""
One-run migration: creates entity_consistency_checks table and seeds 7 Phase 4A candidates.

Usage:
    python3 scripts/apply_entity_consistency_checks.py

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
SQL_FILE     = BASE_DIR / "migrations" / "entity_consistency_checks_v1.sql"
KEY_FILE     = BASE_DIR / ".supabase_service_key"
SUPABASE_URL = "https://tghntyofptvfhmtchwcv.supabase.co"

DASHBOARD_URL = (
    "https://supabase.com/dashboard/project/"
    "tghntyofptvfhmtchwcv/sql/new"
)

# ── Verification queries (run after migration) ────────────────────────────────
VERIFICATION = [
    ("Row count (expect 7)",
     "entity_consistency_checks?select=id&limit=100"),
    ("Open high-severity (expect 0)",
     "entity_consistency_checks?select=entity_id,classification&status=eq.open&severity=eq.high"),
    ("Held items",
     "entity_consistency_checks?select=entity_id,issue_key,review_status&review_status=eq.held"),
    ("upadacitinib row",
     "entity_consistency_checks?select=entity_id,status,review_status&entity_id=eq.upadacitinib"),
    ("batoclimab row",
     "entity_consistency_checks?select=entity_id,status,review_status&entity_id=eq.batoclimab"),
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
        f"{SUPABASE_URL}/rest/v1/entity_consistency_checks?select=id&limit=1",
        headers=headers(service_key),
        timeout=15,
    )
    return resp.status_code in (200, 206)


def run_sql_automated(service_key, sql):
    """Attempt automated DDL via pg-meta endpoint (may not be available)."""
    resp = requests.post(
        f"{SUPABASE_URL}/pg-meta/v0/query",
        headers=headers(service_key),
        json={"query": sql},
        timeout=60,
    )
    if resp.status_code == 404:
        return None  # endpoint not available
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
    print("\n── Verification ──────────────────────────────────────────")
    all_pass = True
    for label, path in VERIFICATION:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers=h,
            timeout=15,
        )
        if resp.status_code in (200, 206):
            data = resp.json()
            print(f"  ✓ {label}: {len(data)} rows — {data}")
        else:
            print(f"  ✗ {label}: HTTP {resp.status_code} — {resp.text[:100]}")
            all_pass = False
    return all_pass


def print_manual_instructions(sql):
    print("\n" + "═" * 70)
    print("MANUAL EXECUTION REQUIRED")
    print("═" * 70)
    print(f"\n1. Open: {DASHBOARD_URL}")
    print("2. Paste the SQL below into the editor")
    print("3. Click 'Run' (or Cmd+Enter)")
    print("4. Run this script again to verify: python3 scripts/apply_entity_consistency_checks.py")
    print("\n── SQL (" + str(len(sql)) + " chars) ──────────────────────────────────────────")
    print(sql)
    print("── END SQL ──────────────────────────────────────────────────────────")


def main():
    print("─" * 70)
    print("Meridian — entity_consistency_checks migration")
    print("─" * 70)

    service_key = load_service_key()

    # ── Step 1: Check if already exists ──────────────────────────────────────
    print("\n[1] Checking if entity_consistency_checks already exists...")
    if table_exists(service_key):
        print("    Table already exists.")
        print("[2] Running verification queries against existing table...")
        verify(service_key)
        return

    print("    Table not found — proceeding with migration.")

    # ── Step 2: Load SQL ──────────────────────────────────────────────────────
    if not SQL_FILE.exists():
        sys.exit(f"ERROR: SQL file not found: {SQL_FILE}")
    sql = SQL_FILE.read_text()
    print(f"[2] Loaded: {SQL_FILE.name} ({len(sql)} chars)")

    # ── Step 3: Attempt automated execution ──────────────────────────────────
    print("[3] Attempting automated execution via pg-meta...")
    result = run_sql_automated(service_key, sql)

    if result is None:
        print("    pg-meta endpoint not available on this instance.")
        print_manual_instructions(sql)
        sys.exit(0)

    if "error" in result:
        print(f"    Automated execution failed: {result['error']}")
        print_manual_instructions(sql)
        sys.exit(1)

    print("    ✓ Migration executed.")

    # ── Step 4: Verify ────────────────────────────────────────────────────────
    print("[4] Verifying migration...")
    if table_exists(service_key):
        print("    ✓ Table is live.")
        verify(service_key)
        print("\n✅ entity_consistency_checks is ready.")
    else:
        print("    ✗ Table not found after migration — check Supabase dashboard.")
        sys.exit(1)

    print("─" * 70)


if __name__ == "__main__":
    main()
