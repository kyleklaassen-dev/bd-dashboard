#!/usr/bin/env python3
"""
unify_graph.py — fold report-derived intelligence into the main entity_edges graph
===================================================================================
Two deterministic, idempotent passes that connect the new Document-Intelligence
layer (intel_facts / intel_fact_entities) into the 26k-edge `entity_edges` graph so
report facts are traversable alongside trials, patents, targets and authors:

  1. TARGETS        drug -> target   (parsed from drugs.target, resolved via targets)
  2. COMPETES_WITH  drug -> drug     (drugs co-mentioned in a fact_type='competitive' fact)

Only allowed predicates/generation_methods are used. Pre-filters against existing
edges so re-runs add nothing duplicate. Run after build_fact_graph.py.

Run: SUPABASE_SERVICE_KEY=... python3 scripts/unify_graph.py
"""
import os, re, pathlib, collections, itertools, requests

BASE = pathlib.Path(__file__).parent.parent
URL = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
KEY = os.environ.get("SUPABASE_SERVICE_KEY") or (BASE / ".supabase_service_key").read_text().strip()
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

def getall(t, p):
    out, s = [], 0
    while True:
        r = requests.get(f"{URL}/rest/v1/{t}", headers={**H, "Range": f"{s}-{s+999}"}, params=p)
        d = r.json() if r.status_code in (200, 206) else []
        out += d
        if len(d) < 1000: break
        s += 1000
    return out

def insert(rows):
    n = 0
    for i in range(0, len(rows), 400):
        r = requests.post(f"{URL}/rest/v1/entity_edges",
                          headers={**H, "Prefer": "return=minimal,resolution=ignore-duplicates"},
                          json=rows[i:i+400])
        if r.status_code in (200, 201, 204): n += len(rows[i:i+400])
    return n

def main():
    # target resolver
    tmap = {}
    for t in getall("targets", {"select": "id,label,gene_symbol,alt_names,full_name"}):
        for k in [t.get("id"), t.get("label"), t.get("gene_symbol"), t.get("full_name")] + (t.get("alt_names") or []):
            if k: tmap[re.sub(r"[^a-z0-9]", "", str(k).lower())] = t["id"]
    def resolve(s):
        out = []
        for tok in re.split(r"[×x/+]|,|\band\b", s or ""):
            k = re.sub(r"[^a-z0-9]", "", tok.lower())
            if k and k in tmap and tmap[k] not in out: out.append(tmap[k])
        return out

    # ── 1) TARGETS: drug -> target ────────────────────────────────────────────
    have_t = {(e["subject_id"], e["object_id"]) for e in getall("entity_edges", {"select": "subject_id,object_id", "predicate": "eq.TARGETS"})}
    trows = []
    for d in getall("drugs", {"select": "id,target"}):
        for tid in resolve(d.get("target")):
            if (d["id"], tid) not in have_t:
                trows.append({"subject_type": "drug", "subject_id": d["id"], "predicate": "TARGETS",
                              "object_type": "target", "object_id": tid, "generation_method": "deterministic",
                              "confidence_level": "confirmed", "status": "active",
                              "rationale": f"Derived from drugs.target='{d.get('target')}'", "created_by": "unify_graph"})
                have_t.add((d["id"], tid))
    print("TARGETS edges added:", insert(trows))

    # ── 2) COMPETES_WITH: drugs co-mentioned in a competitive fact ────────────
    have_c = set()
    for e in getall("entity_edges", {"select": "subject_id,object_id", "predicate": "eq.COMPETES_WITH"}):
        have_c.add((e["subject_id"], e["object_id"])); have_c.add((e["object_id"], e["subject_id"]))
    fmeta = {f["id"]: f for f in getall("intel_facts", {"select": "id,fact_type,source_url"})}
    byfact = collections.defaultdict(list)
    for e in getall("intel_fact_entities", {"select": "fact_id,entity_id,entity_type,area_id"}):
        byfact[e["fact_id"]].append(e)
    crows = []
    for fid, ents in byfact.items():
        if (fmeta.get(fid) or {}).get("fact_type") != "competitive": continue
        drugs = {e["entity_id"]: e for e in ents if e["entity_type"] == "drug"}
        if len(drugs) < 2: continue
        area = ents[0].get("area_id"); src = (fmeta.get(fid) or {}).get("source_url")
        for a, b in itertools.combinations(sorted(drugs), 2):
            if (a, b) in have_c: continue
            have_c.add((a, b)); have_c.add((b, a))
            crows.append({"subject_type": "drug", "subject_id": a, "predicate": "COMPETES_WITH",
                          "object_type": "drug", "object_id": b, "scope_area_id": area,
                          "generation_method": "deterministic", "confidence_level": "inferred", "status": "active",
                          "source_url": src, "rationale": "co-mentioned as competitors in submitted research", "created_by": "unify_graph"})
    print("COMPETES_WITH edges added:", insert(crows))

if __name__ == "__main__":
    main()
