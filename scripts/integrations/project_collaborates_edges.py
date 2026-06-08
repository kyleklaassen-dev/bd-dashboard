#!/usr/bin/env python3
"""
project_collaborates_edges.py — COLLABORATES edges (idempotent, derived).

Projects academic-industry co-authorship from `institution_company_bridge` (built from
OpenAlex co-authorship overlap) into entity_edges as institution->company edges where
shared_papers >= MIN_PAPERS (default 3, a meaningful-collaboration threshold).

  predicate COLLABORATES  (institution COLLABORATES company)

Resolve-or-skip: a row is skipped if the company node is absent from companies, or if the
institution_id is not a usable node id. Idempotent: existing (institution, COLLABORATES,
company) triples are read first and skipped, so a re-run inserts 0 new edges. COLLABORATES
predicate already exists in the entity_edges CHECK.

Counts are a lower bound (OpenAlex institution disambiguation may split a single real
institution across country-variant rows). No fabrication — rationale cites shared_papers
and the bridge basis.

Usage:
    python3 project_collaborates_edges.py            # dry run
    python3 project_collaborates_edges.py --write    # upsert missing edges

Free/derived only — safe while backend API spend is paused.
"""
from __future__ import annotations
import argparse, json, os, urllib.request

WORKSPACE = os.environ.get("MERIDIAN_WORKSPACE", os.getcwd())
BASE = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
CREATED_BY = "project_collaborates_edges.py"
MIN_PAPERS = int(os.environ.get("MIN_PAPERS", "3"))


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

    bridge = get(f"/institution_company_bridge?select=institution_id,company_id,shared_papers,basis"
                 f"&shared_papers=gte.{MIN_PAPERS}")
    company_ids = set(c["id"] for c in get("/companies?select=id"))

    existing = set()
    for e in get("/entity_edges?select=subject_id,object_id&predicate=eq.COLLABORATES"):
        existing.add((e["subject_id"], e["object_id"]))

    plan, skipped = [], {"company_missing": 0, "no_institution": 0, "already_exists": 0}
    seen = set()
    for b in bridge:
        inst = b.get("institution_id")
        cid = b.get("company_id")
        if not inst:
            skipped["no_institution"] += 1
            continue
        if cid not in company_ids:
            skipped["company_missing"] += 1
            continue
        key = (inst, cid)
        if key in existing or key in seen:
            skipped["already_exists"] += 1
            continue
        seen.add(key)
        n = b.get("shared_papers")
        basis = b.get("basis") or "co_authorship"
        plan.append({
            "subject_type": "institution", "subject_id": inst,
            "predicate": "COLLABORATES",
            "object_type": "company", "object_id": cid,
            "confidence_level": "supported",
            "source_url": None,
            "generation_method": "deterministic",
            "rationale": (f"Academic-industry co-authorship: {n} shared papers between institution and "
                          f"company (threshold>={MIN_PAPERS}). basis={basis}. Derived from "
                          f"institution_company_bridge. Counts are a lower bound (OpenAlex institution "
                          f"disambiguation may split across country-variant rows)."),
            "created_by": CREATED_BY,
            "status": "active",
        })

    print(f"bridge rows (>= {MIN_PAPERS} papers): {len(bridge)}")
    print(f"skips: {skipped}")
    print(f"new COLLABORATES: {len(plan)}")

    if args.write and plan:
        for i in range(0, len(plan), 100):
            insert(plan[i:i + 100])
        print(f"WROTE {len(plan)} edges.")
    elif not args.write:
        print("(dry run — pass --write to insert)")


if __name__ == "__main__":
    main()
