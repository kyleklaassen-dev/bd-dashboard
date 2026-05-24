#!/usr/bin/env python3
"""
patch_stale_data.py
Two fixes in one pass:

A) Link drug_ids in landscape_expected_competitors:
   - ibi311 row: drug_id was NULL (drug didn't exist); now exists as 'ibi311'
   - oln102 row: drug_id was NULL (drug didn't exist); now exists as 'oln102'

B) Patch stale drug records:
   - veligrotug: stage 'Regulatory Review' → 'BLA Filed', route 'IV' → 'SC'
   - elegrobart:  stage 'Phase 3' → 'Phase 2'
   - yb-101:      route 'SC' → 'IV'
   - yarrow:      company name 'Yarrow Bioscience' → 'Yarrow Biotechnology'

Run:
  python3 scripts/patch_stale_data.py [--dry-run]
"""

import json, os, sys, urllib.request, urllib.error, urllib.parse, datetime

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

NOW = datetime.datetime.utcnow().isoformat()


def section(title):
    print(f"\n{'═'*60}\n  {title}\n{'═'*60}")


def get(table, params):
    qs = "&".join(
        f"{k}={urllib.parse.quote(str(v), safe='.()*,')}" for k, v in params.items()
    )
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{table}?{qs}", headers=HEADERS_READ)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  GET {table} HTTP {e.code}: {e.read().decode()[:300]}")
        return []


def patch(table, filters, updates, label=""):
    if DRY_RUN:
        filter_str = " AND ".join(f"{k}={v}" for k, v in filters.items())
        print(f"  [DRY RUN] PATCH {table} WHERE {filter_str}")
        print(f"            → {updates}")
        return True
    qs = "&".join(
        f"{k}={urllib.parse.quote(str(v), safe='.()*,')}" for k, v in filters.items()
    )
    data = json.dumps(updates).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}?{qs}",
        data=data,
        headers=HEADERS_PATCH,
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read())
            n = len(result) if isinstance(result, list) else 1
            return n
    except urllib.error.HTTPError as e:
        print(f"  PATCH {table} HTTP {e.code}: {e.read().decode()[:300]}")
        return 0


# ─────────────────────────────────────────────────────────────────
# 0. Pre-flight
# ─────────────────────────────────────────────────────────────────
section("PRE-FLIGHT")

# Find landscape_id
landscapes = get("competitive_landscapes", {
    "disease_name": "eq.Thyroid Eye Disease",
    "select": "id,disease_name",
})
if not landscapes:
    print("  ❌  No TED landscape found")
    sys.exit(1)
LANDSCAPE_ID = landscapes[0]["id"]
print(f"  landscape_id={LANDSCAPE_ID}")

# Current state of lec rows we'll patch
lec_rows = get("landscape_expected_competitors", {
    "landscape_id": f"eq.{LANDSCAPE_ID}",
    "drug_name":    "in.(ibi311,oln102)",
    "select":       "id,drug_name,drug_id,confirmed,tier",
})
print(f"  landscape_expected_competitors (ibi311, oln102):")
for r in lec_rows:
    print(f"    id={r['id']} drug_name={r['drug_name']} drug_id={r['drug_id']} confirmed={r['confirmed']}")

# Current drug data
drugs_before = get("drugs", {
    "id": "in.(veligrotug,elegrobart,yb-101)",
    "select": "id,stage,route,updated_at",
})
print(f"\n  Drugs before patch:")
for d in drugs_before:
    print(f"    {d['id']:<15} stage={d['stage']:<20} route={d['route']}")

# Yarrow company before
yarrow_before = get("companies", {"id": "eq.yarrow", "select": "id,name"})
print(f"\n  Yarrow company name: {yarrow_before[0]['name'] if yarrow_before else 'not found'}")


# ─────────────────────────────────────────────────────────────────
# A. Link drug_ids in landscape_expected_competitors
# ─────────────────────────────────────────────────────────────────
section("SECTION A: landscape_expected_competitors — link drug_ids")

lec_patches = [
    {
        "filters": {"landscape_id": f"eq.{LANDSCAPE_ID}", "drug_name": "eq.ibi311"},
        "updates": {"drug_id": "ibi311"},
        "label":   "ibi311: drug_id NULL → 'ibi311'",
    },
    {
        "filters": {"landscape_id": f"eq.{LANDSCAPE_ID}", "drug_name": "eq.oln102"},
        "updates": {"drug_id": "oln102"},
        "label":   "oln102: drug_id NULL → 'oln102'",
    },
]

for p in lec_patches:
    n = patch("landscape_expected_competitors", p["filters"], p["updates"])
    status = "✅" if n else "❌"
    print(f"  {status}  {p['label']}")


# ─────────────────────────────────────────────────────────────────
# B. Stale drug records
# ─────────────────────────────────────────────────────────────────
section("SECTION B: stale drug patches")

drug_patches = [
    {
        "filters": {"id": "eq.veligrotug"},
        "updates": {"stage": "BLA Filed", "route": "SC", "updated_at": NOW},
        "label":   "veligrotug: stage 'Regulatory Review' → 'BLA Filed', route IV → SC",
    },
    {
        "filters": {"id": "eq.elegrobart"},
        "updates": {"stage": "Phase 2", "updated_at": NOW},
        "label":   "elegrobart: stage 'Phase 3' → 'Phase 2'",
    },
    {
        "filters": {"id": "eq.yb-101"},
        "updates": {"route": "IV", "updated_at": NOW},
        "label":   "yb-101: route 'SC' → 'IV'",
    },
]

for p in drug_patches:
    n = patch("drugs", p["filters"], p["updates"])
    status = "✅" if n else "❌"
    print(f"  {status}  {p['label']}")

# Yarrow name fix
n = patch("companies", {"id": "eq.yarrow"}, {"name": "Yarrow Biotechnology"})
status = "✅" if n else "❌"
print(f"  {status}  yarrow: name → 'Yarrow Biotechnology'")


# ─────────────────────────────────────────────────────────────────
# Verify
# ─────────────────────────────────────────────────────────────────
section("VERIFICATION")

drugs_after = get("drugs", {
    "id": "in.(veligrotug,elegrobart,yb-101)",
    "select": "id,stage,route",
})
print(f"  Drugs after patch:")
for d in drugs_after:
    print(f"    {d['id']:<15} stage={d['stage']:<20} route={d['route']}")

yarrow_after = get("companies", {"id": "eq.yarrow", "select": "id,name"})
print(f"\n  Yarrow company name: {yarrow_after[0]['name'] if yarrow_after else 'not found'}")

lec_after = get("landscape_expected_competitors", {
    "landscape_id": f"eq.{LANDSCAPE_ID}",
    "drug_name":    "in.(ibi311,oln102)",
    "select":       "drug_name,drug_id,confirmed",
})
print(f"\n  landscape_expected_competitors (ibi311, oln102):")
for r in lec_after:
    linked = "✅" if r["drug_id"] else "❌"
    print(f"    {linked} {r['drug_name']:<10} drug_id={r['drug_id']}")

print(f"\n{'═'*60}")
if not DRY_RUN:
    print("  ✅  Done.")
print(f"{'═'*60}")
