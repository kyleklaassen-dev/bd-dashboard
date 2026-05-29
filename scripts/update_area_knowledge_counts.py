#!/usr/bin/env python3
"""
update_area_knowledge_counts.py
================================
BUG 6 FIX: All 13 area_knowledge rows have drug_count_direct=NULL and drug_count_total=NULL.

Strategy:
  - drug_count_direct = distinct drugs from drug_targets where target_id matches the area
  - drug_count_total  = drug_count_direct PLUS drugs linked via drug_indications
    (for disease areas like uc, cd, ibd, ted, mg, cidp, graves, ra)

Area slug → target mapping:
  tl1a     → drug_targets.target_id IN (tl1a)
  il23     → drug_targets.target_id IN (il23p19, il12_23p40)
  ibd      → drug_indications.indication_id IN (uc, cd) [disease area]
  uc       → drug_indications.indication_id = uc
  cd       → drug_indications.indication_id = cd
  fcrn     → drug_targets.target_id = fcrn
  ted      → drug_indications.indication_id = ted
  atopy    → drug_targets.target_id IN (il4ra, tslp, il13, il33) + indication=ad
  bispecific → drugs where modality ILIKE '%bispecific%'
  ra       → drug_indications.indication_id = ra
  graves   → drug_indications.indication_id IN (ted, graves)
  mg       → drug_indications.indication_id IN (gmg, mg)
  cidp     → drug_indications.indication_id = cidp
"""

import os, sys, json, requests

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _read(f):
    for base in [_REPO, os.path.dirname(os.path.abspath(__file__))]:
        p = os.path.join(base, f)
        if os.path.exists(p):
            return open(p).read().strip()
    return ""

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://tghntyofptvfhmtchwcv.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or _read(".supabase_service_key")

if not SUPABASE_KEY:
    print("ERROR: No SUPABASE_SERVICE_KEY"); sys.exit(1)

REST = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

def sb_get(table, params):
    r = requests.get(f"{REST}/{table}", headers=HEADERS, params=params, timeout=20)
    if r.status_code == 200:
        return r.json()
    print(f"  GET {table}: {r.status_code} {r.text[:200]}")
    return []

def sb_patch(table, payload, params):
    h = {**HEADERS, "Prefer": "return=minimal"}
    r = requests.patch(f"{REST}/{table}", headers=h, params=params, json=payload, timeout=15)
    return r.status_code in (200, 204)

# ─── Data loading helpers ─────────────────────────────────────────────────────

def get_drugs_by_target(target_ids):
    """Return distinct drug_ids from drug_targets matching any target_id."""
    if not target_ids:
        return set()
    in_filter = "in.(" + ",".join(target_ids) + ")"
    rows = sb_get("drug_targets", {"target_id": in_filter, "select": "drug_id", "limit": "500"})
    return {r["drug_id"] for r in rows if r.get("drug_id")}

def get_drugs_by_indication(indication_ids):
    """Return distinct drug_ids from drug_indications matching any indication_id."""
    if not indication_ids:
        return set()
    in_filter = "in.(" + ",".join(indication_ids) + ")"
    rows = sb_get("drug_indications", {"indication_id": in_filter, "select": "drug_id", "limit": "500"})
    return {r["drug_id"] for r in rows if r.get("drug_id")}

def get_bispecific_drugs():
    """Return drug_ids where modality contains 'bispecific'."""
    rows = sb_get("drugs", {"modality": "ilike.*bispecific*", "select": "id", "limit": "500"})
    return {r["id"] for r in rows if r.get("id")}


# ─── Area slug → count computation ───────────────────────────────────────────

AREA_DEFINITIONS = {
    # slug: (direct_target_ids, total_indication_ids)
    # direct = drugs in drug_targets; total also includes drug_indications
    "tl1a":      (["tl1a"],                                   ["uc", "cd"]),
    "il23":      (["il23p19", "il12_23p40"],                  ["uc", "cd"]),
    "ibd":       ([],                                          ["uc", "cd"]),
    "uc":        ([],                                          ["uc"]),
    "cd":        ([],                                          ["cd"]),
    "fcrn":      (["fcrn"],                                   ["gmg", "cidp", "waiha", "pemphigus"]),
    "ted":       (["igf1r", "tshr"],                          ["ted"]),
    "atopy":     (["il4ra", "tslp", "il13", "il33"],          ["ad", "asthma", "ad"]),
    "bispecific": None,  # special: modality-based
    "ra":        ([],                                          ["ra"]),
    "graves":    (["tshr"],                                   ["ted"]),
    "mg":        (["fcrn"],                                   ["gmg"]),
    "cidp":      (["fcrn"],                                   ["cidp"]),
}


def compute_counts(slug):
    """Return (drug_count_direct, drug_count_total) for an area slug."""
    if slug == "bispecific":
        drugs = get_bispecific_drugs()
        return len(drugs), len(drugs)

    defn = AREA_DEFINITIONS.get(slug)
    if defn is None:
        print(f"  No definition for slug '{slug}' — skipping")
        return None, None

    target_ids, indication_ids = defn

    direct_drugs = get_drugs_by_target(target_ids) if target_ids else set()
    ind_drugs = get_drugs_by_indication(indication_ids) if indication_ids else set()

    total_drugs = direct_drugs | ind_drugs

    # drug_count_direct = drugs linked via molecular targets
    # drug_count_total  = any drug linked to this area (target or indication)
    direct_count = len(direct_drugs) if target_ids else len(ind_drugs)
    total_count = len(total_drugs)

    return direct_count, total_count


def main():
    # Get all area_knowledge rows
    rows = sb_get("area_knowledge", {"select": "id,area_slug"})
    print(f"Found {len(rows)} area_knowledge rows\n")
    print(f"{'Slug':<15} {'Direct':>8} {'Total':>8} {'Status'}")
    print("-" * 40)

    updated = 0
    for row in rows:
        row_id = row["id"]
        slug = row["area_slug"]

        direct_count, total_count = compute_counts(slug)
        if direct_count is None:
            continue

        ok = sb_patch(
            "area_knowledge",
            {"drug_count_direct": direct_count, "drug_count_total": total_count},
            {"id": f"eq.{row_id}"},
        )
        status = "✓" if ok else "✗"
        print(f"{slug:<15} {direct_count:>8} {total_count:>8} {status}")
        if ok:
            updated += 1

    print(f"\nDone: {updated}/{len(rows)} rows updated.")

if __name__ == "__main__":
    main()
