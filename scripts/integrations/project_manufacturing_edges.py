#!/usr/bin/env python3
"""
project_manufacturing_edges.py — SUPPLIES / MANUFACTURES edges (idempotent, derived).

Projects the REAL openFDA establishment data in `manufacturing_sites` (drug/label.json
+ DailyMed SPL) into the entity_edges graph as company->drug edges:

  - is_supplies_candidate=true (external CMO: labeled manufacturer != asset owner)
        -> predicate SUPPLIES   (company SUPPLIES drug)
  - otherwise (in-house: manufacturer == owner)
        -> predicate MANUFACTURES (company MANUFACTURES drug)

Resolve-or-skip: a row is skipped if manufacturer_company_id is null, or the company /
drug node is absent from companies/drugs. No fabrication — every edge carries the
manufacturer_name + establishment_type in its rationale and the manufacturing_sites
source_url.

Idempotent: existing (subject_id, predicate, object_id) triples are read first and
skipped, so re-running with --write inserts 0 new edges. MANUFACTURES predicate added
additively in migrations/v144_manufactures_predicate.sql.

Usage:
    python3 project_manufacturing_edges.py            # dry run (prints plan)
    python3 project_manufacturing_edges.py --write    # upsert missing edges

Free/derived only — safe while backend API spend is paused.
"""
from __future__ import annotations
import argparse, json, os, sys, urllib.request, urllib.parse

WORKSPACE = os.environ.get("MERIDIAN_WORKSPACE", os.getcwd())
BASE = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
CREATED_BY = "project_manufacturing_edges.py"


def _key() -> str:
    for cand in (WORKSPACE, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))):
        p = os.path.join(cand, ".supabase_service_key")
        if os.path.exists(p):
            return open(p).read().strip()
    raise SystemExit("missing .supabase_service_key")


SK = _key()
H = {"apikey": SK, "Authorization": "Bearer " + SK}


def get(path: str):
    out, off = [], 0
    while True:
        req = urllib.request.Request(BASE + path + ("&" if "?" in path else "?") + f"offset={off}&limit=1000",
                                     headers=H)
        b = json.load(urllib.request.urlopen(req))
        out += b
        if len(b) < 1000:
            break
        off += 1000
    return out


def insert(rows: list):
    data = json.dumps(rows).encode()
    req = urllib.request.Request(BASE + "/entity_edges", data=data,
                                 headers={**H, "Content-Type": "application/json", "Prefer": "return=minimal"},
                                 method="POST")
    urllib.request.urlopen(req)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    sites = get("/manufacturing_sites?select=drug_id,manufacturer_name,manufacturer_company_id,"
                "owner_company_id,is_inhouse,is_supplies_candidate,establishment_type,source_url")
    company_ids = set(c["id"] for c in get("/companies?select=id"))
    drug_ids = set(d["id"] for d in get("/drugs?select=id"))

    # existing triples for both predicates
    existing = set()
    for pred in ("SUPPLIES", "MANUFACTURES"):
        for e in get(f"/entity_edges?select=subject_id,object_id&predicate=eq.{pred}"):
            existing.add((e["subject_id"], pred, e["object_id"]))

    plan, skipped = [], {"no_company_id": 0, "company_missing": 0, "drug_missing": 0, "already_exists": 0}
    seen_in_batch = set()
    for s in sites:
        cid = s.get("manufacturer_company_id")
        did = s.get("drug_id")
        if not cid:
            skipped["no_company_id"] += 1
            continue
        if cid not in company_ids:
            skipped["company_missing"] += 1
            continue
        if did not in drug_ids:
            skipped["drug_missing"] += 1
            continue
        pred = "SUPPLIES" if s.get("is_supplies_candidate") else "MANUFACTURES"
        triple = (cid, pred, did)
        if triple in existing or triple in seen_in_batch:
            skipped["already_exists"] += 1
            continue
        seen_in_batch.add(triple)
        mname = s.get("manufacturer_name") or cid
        etype = s.get("establishment_type") or "manufacturer"
        owner = s.get("owner_company_id") or "?"
        if pred == "SUPPLIES":
            rationale = (f"External manufacturing/supply relationship from manufacturing_sites "
                         f"(openFDA drug/label.json establishment + DailyMed SPL): {mname} ({cid}) is the "
                         f"labeled {etype} of {did}, whose asset owner is '{owner}'. manufacturer != owner "
                         f"-> external CMO supply edge. confidence=supported (openFDA-sourced).")
        else:
            rationale = (f"In-house manufacturing relationship from manufacturing_sites "
                         f"(openFDA drug/label.json establishment + DailyMed SPL): {mname} ({cid}) is the "
                         f"labeled {etype} of {did}; manufacturer == asset owner '{owner}' -> in-house "
                         f"MANUFACTURES edge. confidence=supported (openFDA-sourced).")
        plan.append({
            "subject_type": "company", "subject_id": cid,
            "predicate": pred,
            "object_type": "drug", "object_id": did,
            "confidence_level": "supported",
            "source_url": s.get("source_url"),
            "generation_method": "deterministic",
            "rationale": rationale,
            "created_by": CREATED_BY,
            "status": "active",
        })

    supplies = [p for p in plan if p["predicate"] == "SUPPLIES"]
    manuf = [p for p in plan if p["predicate"] == "MANUFACTURES"]
    print(f"manufacturing_sites rows: {len(sites)}")
    print(f"skips: {skipped}")
    print(f"new SUPPLIES: {len(supplies)}  new MANUFACTURES: {len(manuf)}  total new: {len(plan)}")

    if args.write and plan:
        for i in range(0, len(plan), 100):
            insert(plan[i:i + 100])
        print(f"WROTE {len(plan)} edges.")
    elif not args.write:
        print("(dry run — pass --write to insert)")


if __name__ == "__main__":
    main()
