#!/usr/bin/env python3
"""
BD Platform — Partnership / Lineage Edge Seeder
===============================================
Relationship-completeness sprint (2026-06-06, cowork). Companion to
seed_company_edges.py. Connects the orphan companies that relate to the graph
through DEALS rather than competition — licensors, partners, acquirers — using
ONLY deterministic, source-of-record data already in Supabase. No fabrication.

WHY THIS IS NEEDED
------------------
Per the licensing-attribution governance rule, a drug's company_id is ALWAYS the
originator, so licensees/partners never get a DEVELOPED_BY edge — they sit
orphaned in entity_edges even though company_partnerships / asset_transfer_history
record a real, sourced relationship. This seeder projects those tables into edges.

TWO DETERMINISTIC STEPS (idempotent)
------------------------------------
1. PARTNERED_WITH  (bidirectional)  from company_partnerships
     lead_company_id <--PARTNERED_WITH--> partner_company_id   (scope = area_id)
   confidence: confirmed (verified + real source_url) / supported (verified only)
               / inferred (unverified). source_url carried when it's a real URL
   (the table's governance placeholders like "[codev_requires_source_url]..." are
   treated as no-source). partnership_type + deal_type recorded in the rationale.

2. Lineage  (directional)  from asset_transfer_history (both entity_ids resolved)
     transfer_type 'license'     -> to --LICENSED_FROM--> from   (licensee->licensor)
     transfer_type 'acquisition' -> to --ACQUIRED-->      from   (acquirer->target)
   confidence: confirmed if verified else inferred; source_url carried.

USAGE
-----
  python3 scripts/seed_partnership_edges.py --dry-run
  python3 scripts/seed_partnership_edges.py --apply
"""
import os, sys, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import meridian.products.narrative_gen as ng

CREATED_BY = "seed_partnership_edges"


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


def real_url(u):
    return isinstance(u, str) and u.strip().lower().startswith("http")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

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

    # ---- STEP 1: PARTNERED_WITH (bidirectional) from company_partnerships ----
    cp = fetch_all("company_partnerships?select=lead_company_id,partner_company_id,"
                   "partnership_type,deal_type,area_id,drug_id,partnership_verified,source_url")
    part_added = 0
    for p in cp:
        a, b = p.get("lead_company_id"), p.get("partner_company_id")
        if not a or not b or a == b or a not in companies or b not in companies:
            continue
        verified = bool(p.get("partnership_verified"))
        url = p.get("source_url") if real_url(p.get("source_url")) else None
        conf = "confirmed" if (verified and url) else ("supported" if verified else "inferred")
        area = p.get("area_id")
        ptype = p.get("partnership_type") or "partnership"
        dtype = p.get("deal_type") or ""
        drug = p.get("drug_id")
        rat = (f"Partnership from company_partnerships: {a} <-> {b} "
               f"({ptype}{'/' + dtype if dtype else ''}"
               f"{', drug ' + drug if drug else ''}"
               f"{', area ' + area if area else ''}). "
               f"{'verified' if verified else 'unverified'}.")
        for s, o in ((a, b), (b, a)):
            if add({
                "subject_type": "company", "subject_id": s, "predicate": "PARTNERED_WITH",
                "object_type": "company", "object_id": o, "scope_area_id": area,
                "confidence_level": conf, "source_url": url, "generation_method": "deterministic",
                "rationale": rat, "status": "active", "created_by": CREATED_BY,
            }):
                part_added += 1

    # ---- STEP 2: lineage from asset_transfer_history (directional) ----
    ath = fetch_all("asset_transfer_history?select=from_entity_id,to_entity_id,"
                    "transfer_type,verified,source_url,drug_id")
    lic_added = 0
    for t in ath:
        frm, to = t.get("from_entity_id"), t.get("to_entity_id")
        if not frm or not to or frm == to or frm not in companies or to not in companies:
            continue
        ttype = (t.get("transfer_type") or "").lower()
        pred = "ACQUIRED" if "acqui" in ttype else "LICENSED_FROM"
        url = t.get("source_url") if real_url(t.get("source_url")) else None
        conf = "confirmed" if (t.get("verified") and url) else ("supported" if t.get("verified") else "inferred")
        drug = t.get("drug_id")
        # ACQUIRED: acquirer(to) -> target(from); LICENSED_FROM: licensee(to) -> licensor(from)
        rat = (f"Asset transfer ({ttype}) from asset_transfer_history"
               f"{': drug ' + drug if drug else ''}: {to} {pred} {frm}.")
        if add({
            "subject_type": "company", "subject_id": to, "predicate": pred,
            "object_type": "company", "object_id": frm, "scope_area_id": None,
            "confidence_level": conf, "source_url": url, "generation_method": "deterministic",
            "rationale": rat, "status": "active", "created_by": CREATED_BY,
        }):
            lic_added += 1

    # ---- report ----
    print(f"STEP 1  PARTNERED_WITH (bidirectional) .. +{part_added}")
    print(f"STEP 2  LICENSED_FROM / ACQUIRED ........ +{lic_added}")
    print(f"TOTAL new edges: {len(new_rows)}")
    touched = set()
    for e in edges + new_rows:
        if e["subject_type"] == "company":
            touched.add(e["subject_id"])
        if e["object_type"] == "company":
            touched.add(e["object_id"])
    orphans_after = sorted(c for c in companies if c not in touched)
    print(f"Orphan companies AFTER: {len(orphans_after)}")
    print("  remaining (no asset, no competition, no deal — contextual/data-acquisition only):")
    print("   ", ", ".join(orphans_after))

    if args.apply and new_rows:
        applied, failed = 0, 0
        for i in range(0, len(new_rows), 200):
            batch = new_rows[i:i+200]
            res = ng._request("POST", "entity_edges", batch, {"Prefer": "return=minimal"})
            if res is None:          # ng._request returns None on HTTPError (and logs it)
                failed += len(batch)
            else:
                applied += len(batch)
        print(f"\nAPPLIED {applied} edges; FAILED {failed}." if failed
              else f"\nAPPLIED {applied} edges to entity_edges.")
    else:
        print("\n[dry-run] no writes.")


if __name__ == "__main__":
    main()
