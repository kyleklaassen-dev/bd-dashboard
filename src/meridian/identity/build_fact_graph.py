#!/usr/bin/env python3
"""
build_fact_graph.py — (re)build the fact -> entity relationship graph
=====================================================================
Scans every intel_facts.claim AND subject_name for known drugs/companies (via the
shared `entity_matcher.Registry`) and populates `intel_fact_entities`
(fact_id, entity_id, role=subject|mentioned). Also backfills intel_facts.subject_id
where it was null. Idempotent.

This is the relationship spine: a drug/company card or query can pull every fact
that NAMES the entity, not just the ones where it is the primary subject.

Run after chunk_extract (the chunk_extract.yml workflow calls it), or on demand:
    SUPABASE_SERVICE_KEY=... python3 src/meridian/identity/build_fact_graph.py

NOTE: edge inserts target the (fact_id, entity_id, role) unique constraint via
on_conflict so pre-existing edges don't 409 the whole batch (a past bug silently
dropped every new edge in a batch that contained any existing one).
"""
import os, sys, pathlib, requests, collections

BASE = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from entity_matcher import Registry

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
KEY = os.environ.get("SUPABASE_SERVICE_KEY") or (BASE / ".supabase_service_key").read_text().strip()
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
OC = "on_conflict=fact_id,entity_id,role"


def getall(t, p):
    out, s = [], 0
    while True:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{t}", headers={**H, "Range": f"{s}-{s+999}"}, params=p)
        d = r.json() if r.status_code in (200, 206) else []
        if not isinstance(d, list):
            break
        out += d
        if len(d) < 1000:
            break
        s += 1000
    return out


def build_edges(reg, facts):
    """Pure function: given a Registry and facts, return (edge_rows, subj_fill)."""
    rows = []
    subj_fill = collections.defaultdict(list)
    for f in facts:
        blob = (f.get("claim") or "") + "\n" + (f.get("subject_name") or "")
        hits = reg.resolve(blob)                       # [(etype, eid, surface, pos)]
        seen = {eid: (et, surface) for et, eid, surface, pos in hits}
        subj = f.get("subject_id")
        if not subj and hits:                          # backfill subject from best hit (drugs first)
            subj = hits[0][1]; f["subject_type"] = hits[0][0]
            subj_fill[(subj, f["subject_type"])].append(f["id"])
        for eid, (et, surface) in seen.items():
            rows.append({"fact_id": f["id"], "entity_type": et, "entity_id": eid,
                         "entity_name": surface, "role": "subject" if eid == subj else "mentioned",
                         "area_id": f.get("area_id")})
        if subj and subj not in seen:                  # ensure the declared subject always has an edge
            rows.append({"fact_id": f["id"], "entity_type": f.get("subject_type") or reg.id2type.get(subj, "company"),
                         "entity_id": subj, "entity_name": f.get("subject_name") or reg.id2name.get(subj),
                         "role": "subject", "area_id": f.get("area_id")})
    return rows, subj_fill


def insert_edges(rows):
    # dedup on the real unique key so a batch never conflicts with itself
    seen, uniq = set(), []
    for r in rows:
        k = (r["fact_id"], r["entity_id"], r["role"])
        if k not in seen:
            seen.add(k); uniq.append(r)
    ins = fail = 0; last = ""
    for i in range(0, len(uniq), 500):
        batch = uniq[i:i+500]
        r = requests.post(f"{SUPABASE_URL}/rest/v1/intel_fact_entities?{OC}",
                          headers={**H, "Prefer": "return=minimal,resolution=ignore-duplicates"}, json=batch)
        if r.status_code in (200, 201, 204):
            ins += len(batch)
        else:
            for row in batch:
                rr = requests.post(f"{SUPABASE_URL}/rest/v1/intel_fact_entities?{OC}",
                                   headers={**H, "Prefer": "return=minimal,resolution=ignore-duplicates"}, json=[row])
                if rr.status_code in (200, 201, 204):
                    ins += 1
                else:
                    fail += 1; last = f"{rr.status_code} {rr.text[:160]}"
    if fail:
        print(f"  WARN: {fail} edge rows failed (last: {last})")
    return ins, fail, len(uniq)


def main():
    reg = Registry(SUPABASE_URL, H)
    facts = getall("intel_facts", {"select": "id,subject_id,subject_type,subject_name,area_id,claim"})
    rows, subj_fill = build_edges(reg, facts)
    ins, fail, nuniq = insert_edges(rows)
    fixed = 0
    for (sid, st), ids in subj_fill.items():
        for j in range(0, len(ids), 200):
            ch = ids[j:j+200]
            if requests.patch(f"{SUPABASE_URL}/rest/v1/intel_facts?id=in.({','.join(map(str, ch))})",
                              headers={**H, "Prefer": "return=minimal"}, json={"subject_id": sid, "subject_type": st}).status_code in (200, 204):
                fixed += len(ch)
    print(f"graph: {ins} edges inserted/confirmed, {fail} failed, {nuniq} unique; "
          f"subject_id backfilled {fixed}; {len(facts)} facts scanned; "
          f"registry {len(reg.name2ids)} surfaces / {len(reg.ambiguous)} ambiguous")


if __name__ == "__main__":
    main()
