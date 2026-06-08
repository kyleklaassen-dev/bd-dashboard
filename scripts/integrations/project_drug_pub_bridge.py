#!/usr/bin/env python3
"""
project_drug_pub_bridge.py — drug->publication REPORTED_IN bridge (idempotent, derived).

For every REPORTED_IN(trial -> publication) edge in entity_edges, resolve the trial's
drug(s) via the nct_id -> drug_id maps in trial_facts and trial_results, and add a
REPORTED_IN(drug -> publication) edge where one does not already exist. This projects
literature onto drugs (the drug "has literature" signal) without re-deriving it from a
new source — it is a pure graph bridge over edges we already trust.

  predicate REPORTED_IN  (drug REPORTED_IN publication)

Resolve-or-skip: a trial edge is skipped if its NCT maps to no drug, or the drug node is
absent from drugs. Idempotent: existing (drug, REPORTED_IN, publication) triples are read
first and skipped, so a re-run inserts 0 new edges. rationale cites the bridging NCT(s).

Usage:
    python3 project_drug_pub_bridge.py            # dry run
    python3 project_drug_pub_bridge.py --write    # upsert missing edges

Free/derived only — safe while backend API spend is paused.
"""
from __future__ import annotations
import argparse, json, os, urllib.request
from collections import defaultdict

WORKSPACE = os.environ.get("MERIDIAN_WORKSPACE", os.getcwd())
BASE = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
CREATED_BY = "project_drug_pub_bridge.py"


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

    # nct -> set(drug_id) from both trial tables
    nct2drug = defaultdict(set)
    for tbl in ("trial_facts", "trial_results"):
        for r in get(f"/{tbl}?select=nct_id,drug_id"):
            if r.get("nct_id") and r.get("drug_id"):
                nct2drug[r["nct_id"]].add(r["drug_id"])

    drug_ids = set(d["id"] for d in get("/drugs?select=id"))

    trial_pub = get("/entity_edges?select=subject_id,object_id&predicate=eq.REPORTED_IN"
                    "&subject_type=eq.trial&object_type=eq.publication")

    existing = set()
    for e in get("/entity_edges?select=subject_id,object_id&predicate=eq.REPORTED_IN"
                 "&subject_type=eq.drug&object_type=eq.publication"):
        existing.add((e["subject_id"], e["object_id"]))

    # (drug,pub) -> set of bridging NCTs
    candidates = defaultdict(set)
    skipped = {"nct_no_drug": 0, "drug_missing": 0}
    for e in trial_pub:
        nct, pub = e["subject_id"], e["object_id"]
        drugs = nct2drug.get(nct)
        if not drugs:
            skipped["nct_no_drug"] += 1
            continue
        for did in drugs:
            if did not in drug_ids:
                skipped["drug_missing"] += 1
                continue
            candidates[(did, pub)].add(nct)

    plan = []
    for (did, pub), ncts in candidates.items():
        if (did, pub) in existing:
            continue
        nct_list = ", ".join(sorted(ncts))
        plan.append({
            "subject_type": "drug", "subject_id": did,
            "predicate": "REPORTED_IN",
            "object_type": "publication", "object_id": pub,
            "confidence_level": "supported",
            "source_url": None,
            "generation_method": "deterministic",
            "rationale": (f"Drug-literature bridge: {did} is reported in publication {pub} via trial(s) "
                          f"{nct_list} (REPORTED_IN trial->publication edge + trial_facts/trial_results "
                          f"nct->drug map). Pure graph bridge over existing trusted edges."),
            "created_by": CREATED_BY,
            "status": "active",
        })

    distinct_drugs = len(set(p["subject_id"] for p in plan))
    print(f"trial->pub edges: {len(trial_pub)}  nct->drug keys: {len(nct2drug)}")
    print(f"candidate drug-pub pairs: {len(candidates)}  existing drug->pub: {len(existing)}")
    print(f"skips: {skipped}")
    print(f"new drug->pub edges: {len(plan)}  distinct drugs gaining literature: {distinct_drugs}")

    if args.write and plan:
        for i in range(0, len(plan), 100):
            insert(plan[i:i + 100])
        print(f"WROTE {len(plan)} edges.")
    elif not args.write:
        print("(dry run — pass --write to insert)")


if __name__ == "__main__":
    main()
