#!/usr/bin/env python3
"""
backfill_biomarker_drug_ids.py
==============================
BUG 3 FIX: drug_biomarkers rows were seeded at indication level without drug_id.

Strategy:
  1. Read all drug_biomarkers rows where drug_id IS NULL.
  2. For each row, find associated drug_ids via drug_indications for that indication_id.
  3. Select the best anchor drug: prefer the Ailux lead (spy002 for UC,
     tulisokibart/afimkibart for CD) — these biomarkers were seeded in the context
     of the TL1A program.
  4. PATCH drug_id on each row.

Fallback: if no preferred drug found, use the first clinical-stage drug from
drug_indications for that indication.
"""

import os, sys, json, requests

# Credentials
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _read(f):
    for base in [_REPO, os.path.dirname(os.path.abspath(__file__))]:
        p = os.path.join(base, f)
        if os.path.exists(p):
            return open(p).read().strip()
    return ""

SUPABASE_URL = (
    os.environ.get("SUPABASE_URL")
    or "https://tghntyofptvfhmtchwcv.supabase.co"
)
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or _read(".supabase_service_key")
)

if not SUPABASE_KEY:
    print("ERROR: No SUPABASE_SERVICE_KEY")
    sys.exit(1)

REST = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

def sb_get(table, params):
    r = requests.get(f"{REST}/{table}", headers=HEADERS, params=params, timeout=15)
    if r.status_code == 200:
        return r.json()
    print(f"  GET {table} error: {r.status_code} {r.text[:200]}")
    return []

def sb_patch(table, payload, params):
    h = {**HEADERS, "Prefer": "return=minimal"}
    r = requests.patch(f"{REST}/{table}", headers=h, params=params, json=payload, timeout=15)
    return r.status_code in (200, 204)

# Preferred anchor drug per indication (TL1A/IBD program context)
# These biomarkers were seeded for the Ailux TL1A program intelligence layer.
PREFERRED_DRUG = {
    "uc":  "spy002",        # Ailux TL1A×IL-23p19 in UC Phase 2
    "cd":  "afimkibart",    # Roche anti-TL1A in CD (most advanced TL1A in CD)
    "ibd": "spy002",        # fallback IBD → Ailux
}

def main():
    # 1. Get all drug_biomarkers with null drug_id
    rows = sb_get("drug_biomarkers", {"drug_id": "is.null", "select": "id,indication_id,biomarker_name"})
    print(f"Found {len(rows)} drug_biomarkers rows with drug_id=NULL")

    if not rows:
        print("Nothing to fix.")
        return

    # 2. For each unique indication, get candidate drug_ids from drug_indications
    indication_drug_map = {}  # indication_id → list of drug_ids
    indication_ids = list({r["indication_id"] for r in rows if r.get("indication_id")})

    for ind_id in indication_ids:
        candidates = sb_get("drug_indications", {
            "indication_id": f"eq.{ind_id}",
            "select": "drug_id",
        })
        indication_drug_map[ind_id] = [c["drug_id"] for c in candidates]
        print(f"  {ind_id}: {len(indication_drug_map[ind_id])} candidate drugs → {indication_drug_map[ind_id][:5]}")

    # 3. For each row, select best anchor drug
    fixed = 0
    for row in rows:
        ind_id = row.get("indication_id")
        row_id = row["id"]
        biomarker = row.get("biomarker_name", "")

        # Preferred drug for this indication
        preferred = PREFERRED_DRUG.get(ind_id)
        candidates = indication_drug_map.get(ind_id, [])

        if preferred and preferred in candidates:
            drug_id = preferred
        elif candidates:
            drug_id = candidates[0]
        else:
            print(f"  Row {row_id} ({biomarker}): no candidates found for {ind_id} — skipping")
            continue

        ok = sb_patch("drug_biomarkers", {"drug_id": drug_id}, {"id": f"eq.{row_id}"})
        status = "✓" if ok else "✗"
        print(f"  {status} Row {row_id} ({biomarker}, {ind_id}) → drug_id={drug_id}")
        if ok:
            fixed += 1

    print(f"\nDone: {fixed}/{len(rows)} rows patched.")

if __name__ == "__main__":
    main()
