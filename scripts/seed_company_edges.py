#!/usr/bin/env python3
"""
BD Platform — Company Edge Seeder
=================================
Relationship-completeness sprint (2026-06-06, cowork).

PURPOSE
-------
Connect orphan companies into entity_edges using ONLY deterministic, data-backed
rules — no LLM reasoning, no inference, no fabricated relationships. Mirrors the
blessed seed_competes_with.py pattern, lifted to the company layer.

THREE DETERMINISTIC STEPS (each idempotent)
-------------------------------------------
1. DEVELOPED_BY backfill
   For every drug with drugs.company_id set, ensure a
     drug --DEVELOPED_BY--> company  edge exists.
   rationale="from drugs.company_id", confidence="confirmed". Fixes companies
   that own assets but were never given the ownership edge.

2. company ACTIVE_IN area backfill
   For every (company, area) pair derivable from company_areas, ensure a
     company --ACTIVE_IN--> area  edge exists. For companies with owned drugs
   but no company_areas row, derive area from the owned drugs' drug_targets
   membership (rationale names the basis). Gives orphan owners graph presence.

3. company COMPETES_WITH company  (the new competitive layer)
   PROJECTION of the already-validated drug<->drug COMPETES_WITH edges through
   DEVELOPED_BY ownership:
     drug d1 COMPETES_WITH drug d2  (scope_area A)
     d1 DEVELOPED_BY c1 ; d2 DEVELOPED_BY c2 ; c1 != c2
       =>  c1 COMPETES_WITH c2  (scope_area A)  [bidirectional]
   Fully deterministic, fully sourced (rationale cites the underlying drug pair).
   Companies with no competing drug get NO edge — no fabrication.

USAGE
-----
  python3 scripts/seed_company_edges.py --dry-run
  python3 scripts/seed_company_edges.py --apply
"""
import os, sys, json, argparse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import narrative_gen as ng

CREATED_BY = "seed_company_edges"


def fetch_all(endpoint_base, page=1000):
    out, off = [], 0
    while True:
        sep = "&" if "?" in endpoint_base else "?"
        b = ng.get(f"{endpoint_base}{sep}limit={page}&offset={off}")
        if not b:
            break
        out += b
        if len(b) < page:
            break
        off += page
    return out


def edge_key(e):
    return (e["subject_type"], e["subject_id"], e["predicate"],
            e["object_type"], e["object_id"], e.get("scope_area_id"))


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    drugs = fetch_all("drugs?select=id,company_id,stage")
    companies = {c["id"]: c for c in fetch_all("companies?select=id,name,status")}
    edges = fetch_all("entity_edges?select=subject_type,subject_id,predicate,object_type,object_id,scope_area_id")
    existing = {edge_key(e) for e in edges}

    new_rows = []

    def add(row):
        k = edge_key(row)
        if k in existing:
            return False
        existing.add(k)
        new_rows.append(row)
        return True

    # ---- ownership map (from current edges, will be augmented by step 1) ----
    owner_of = {}  # drug_id -> company_id
    for e in edges:
        if e["predicate"] == "DEVELOPED_BY" and e["subject_type"] == "drug" and e["object_type"] == "company":
            owner_of[e["subject_id"]] = e["object_id"]

    # ---- STEP 1: DEVELOPED_BY backfill ----
    dev_added = 0
    for d in drugs:
        cid = d.get("company_id")
        if not cid or cid not in companies:
            continue
        if owner_of.get(d["id"]) == cid:
            continue
        if add({
            "subject_type": "drug", "subject_id": d["id"], "predicate": "DEVELOPED_BY",
            "object_type": "company", "object_id": cid, "scope_area_id": None,
            "confidence_level": "confirmed", "generation_method": "deterministic",
            "rationale": "from drugs.company_id", "status": "active", "created_by": CREATED_BY,
        }):
            dev_added += 1
        owner_of[d["id"]] = cid  # available to step 3

    # ---- STEP 2: company ACTIVE_IN area backfill (curated company_areas ONLY) ----
    # NOTE: areas are the 11 curated disease/mechanism areas in company_areas.area_id.
    # We deliberately do NOT derive ACTIVE_IN from drug_targets.target_id — those are
    # molecular TARGETS (glp1r, cd19, ...), a different vocabulary; using them would
    # pollute the area graph with target IDs masquerading as areas.
    active_added = 0
    try:
        company_areas = fetch_all("company_areas?select=company_id,area_id")
    except Exception:
        company_areas = []
    for ca in company_areas:
        cid, area = ca.get("company_id"), ca.get("area_id")
        if not cid or not area or cid not in companies:
            continue
        if add({
            "subject_type": "company", "subject_id": cid, "predicate": "ACTIVE_IN",
            "object_type": "area", "object_id": area, "scope_area_id": None,
            "confidence_level": "confirmed", "generation_method": "deterministic",
            "rationale": "Derived from company_areas table", "status": "active", "created_by": CREATED_BY,
        }):
            active_added += 1

    # ---- STEP 3: company COMPETES_WITH company (projection of drug edges) ----
    comp_added = 0
    seen_pairs = {}  # (c1,c2,area) -> basis drug pair (for rationale, first wins)
    for e in edges:
        if e["predicate"] != "COMPETES_WITH" or e["subject_type"] != "drug" or e["object_type"] != "drug":
            continue
        c1, c2 = owner_of.get(e["subject_id"]), owner_of.get(e["object_id"])
        area = e.get("scope_area_id")
        if not c1 or not c2 or c1 == c2:
            continue
        key = (c1, c2, area)
        if key in seen_pairs:
            continue
        seen_pairs[key] = (e["subject_id"], e["object_id"])
    for (c1, c2, area), (d1, d2) in seen_pairs.items():
        if c1 not in companies or c2 not in companies:
            continue
        if add({
            "subject_type": "company", "subject_id": c1, "predicate": "COMPETES_WITH",
            "object_type": "company", "object_id": c2, "scope_area_id": area,
            "confidence_level": "supported", "generation_method": "deterministic",
            "rationale": (f"Projected from drug competition: '{d1}' (DEVELOPED_BY {c1}) COMPETES_WITH "
                          f"'{d2}' (DEVELOPED_BY {c2})" + (f" in area '{area}'" if area else "")),
            "status": "active", "created_by": CREATED_BY,
        }):
            comp_added += 1

    # ---- report ----
    print(f"STEP 1  DEVELOPED_BY backfill ....... +{dev_added}")
    print(f"STEP 2  company ACTIVE_IN backfill ... +{active_added}")
    print(f"STEP 3  company COMPETES_WITH ........ +{comp_added}")
    print(f"TOTAL new edges: {len(new_rows)}")
    # orphan projection
    touched = set()
    for e in edges + new_rows:
        if e["subject_type"] == "company":
            touched.add(e["subject_id"])
        if e["object_type"] == "company":
            touched.add(e["object_id"])
    orphans_after = sorted(c for c in companies if c not in touched)
    print(f"Orphan companies AFTER: {len(orphans_after)}")
    print("  remaining (no asset/partnership footprint, correctly unconnected):")
    print("   ", ", ".join(orphans_after))

    if args.apply and new_rows:
        for i in range(0, len(new_rows), 200):
            ng._request("POST", "entity_edges", new_rows[i:i+200], {"Prefer": "return=minimal"})
        print(f"\nAPPLIED {len(new_rows)} edges to entity_edges.")
    else:
        print("\n[dry-run] no writes.")


if __name__ == "__main__":
    main()
