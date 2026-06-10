#!/usr/bin/env python3
"""
build_fact_graph.py — (re)build the fact -> entity relationship graph
=====================================================================
Scans every intel_facts.claim for known drugs/companies and populates
`intel_fact_entities` (fact_id, entity_id, role=subject|mentioned). Also backfills
intel_facts.subject_id where it was null. Idempotent (ignore-duplicates).

This is the relationship spine: a drug/company card or query can pull every fact
that NAMES the entity, not just the ones where it is the primary subject.

Run after chunk_extract (the chunk_extract.yml workflow calls it), or on demand:
    SUPABASE_SERVICE_KEY=... python3 scripts/build_fact_graph.py
"""
import os, re, pathlib, requests, collections

BASE = pathlib.Path(__file__).parent.parent
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
KEY = os.environ.get("SUPABASE_SERVICE_KEY") or (BASE / ".supabase_service_key").read_text().strip()
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
STOP = {"data","study","phase","trial","results","approved","patients","disease","therapy",
        "health","group","sciences","cohort","arm","other","general"}

def getall(t, p):
    out, s = [], 0
    while True:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/{t}", headers={**H, "Range": f"{s}-{s+999}"}, params=p)
        d = r.json() if r.status_code in (200, 206) else []
        out += d
        if len(d) < 1000: break
        s += 1000
    return out

def build_registry():
    reg, gen2id = {}, {}
    for d in getall("drugs", {"select": "id,name,display_name,brand_name,aliases"}):
        for k in [d.get("name"), d.get("brand_name")] + (d.get("aliases") or []):
            if k and len(k.strip()) >= 4: reg[k.strip()] = ("drug", d["id"])
        dn = (d.get("display_name") or "").split("(")[0].strip()
        if len(dn) >= 4: reg.setdefault(dn, ("drug", d["id"]))
        if d.get("name"): gen2id[d["name"].strip().lower()] = d["id"]
    for r in getall("rx_market_tracker", {"select": "drug_name,brand_name"}):
        gid = gen2id.get((r.get("drug_name") or "").strip().lower())
        if gid:
            for k in [r.get("brand_name"), r.get("drug_name")]:
                if k and len(k.strip()) >= 4: reg[k.strip()] = ("drug", gid)
    for c in getall("companies", {"select": "id,name"}):
        nm = (c.get("name") or "").strip()
        if not nm:
            continue
        if len(nm) >= 4:
            reg[nm] = ("company", c["id"])
        # also register a cleaned short form so claim text that omits the legal
        # suffix (e.g. "Shattuck Labs") still matches "Shattuck Labs, Inc.".
        # Strip ONLY corporate/legal suffixes (not industry words like
        # "Pharmaceuticals"/"Therapeutics") to avoid risky short-name collisions.
        short, prev = nm, None
        while short != prev:
            prev = short
            short = re.sub(
                r",?\s+(inc|llc|l\.l\.c\.|ltd|limited|corp|corporation|co|company|"
                r"plc|s\.a\.|sa|ag|n\.v\.|nv|gmbh|holdings|group)\.?$",
                "", short, flags=re.I).strip().rstrip(",").strip()
        if short and short != nm and len(short) >= 4:
            reg.setdefault(short, ("company", c["id"]))
    return reg

def main():
    reg = build_registry()
    names = sorted([n for n in reg if n.lower() not in STOP], key=len, reverse=True)
    pat = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z0-9])", re.I)
    low2reg = {n.lower(): reg[n] for n in reg}
    facts = getall("intel_facts", {"select": "id,subject_id,subject_type,subject_name,area_id,claim"})
    rows = []; subj_fill = collections.defaultdict(list)
    for f in facts:
        claim = f.get("claim") or ""; seen = {}
        for m in pat.finditer(claim):
            t = low2reg.get(m.group(1).lower())
            if t: seen.setdefault(t[1], (t[0], m.group(1), m.start()))
        subj = f.get("subject_id")
        if not subj and seen:
            o = sorted(seen.items(), key=lambda kv: (kv[1][0] != "drug", kv[1][2]))
            subj = o[0][0]; f["subject_type"] = o[0][1][0]
            subj_fill[(subj, f["subject_type"])].append(f["id"])
        for eid, (et, enm, pos) in seen.items():
            rows.append({"fact_id": f["id"], "entity_type": et, "entity_id": eid, "entity_name": enm,
                         "role": "subject" if eid == subj else "mentioned", "area_id": f.get("area_id")})
        if subj and subj not in seen:
            rows.append({"fact_id": f["id"], "entity_type": f.get("subject_type") or "company",
                         "entity_id": subj, "entity_name": f.get("subject_name"), "role": "subject", "area_id": f.get("area_id")})
    # dedup on the real unique key (fact_id, entity_id, role) so a batch can
    # never conflict with itself.
    seen_keys, uniq = set(), []
    for r in rows:
        k = (r["fact_id"], r["entity_id"], r["role"])
        if k in seen_keys:
            continue
        seen_keys.add(k); uniq.append(r)
    rows = uniq

    # IMPORTANT: target the (fact_id, entity_id, role) unique constraint via
    # on_conflict. Without it PostgREST defaults the ON CONFLICT to the primary
    # key (id), so any pre-existing edge makes the whole batch 409 and silently
    # drops every new edge in it (the bug that left manually-added facts
    # unlinked from their cards).
    OC = "on_conflict=fact_id,entity_id,role"
    ins = fail = 0
    last_err = ""
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        r = requests.post(f"{SUPABASE_URL}/rest/v1/intel_fact_entities?{OC}",
                          headers={**H, "Prefer": "return=minimal,resolution=ignore-duplicates"},
                          json=batch)
        if r.status_code in (200, 201, 204):
            ins += len(batch)
        else:
            # per-row fallback so one bad row can't drop an entire batch
            for row in batch:
                rr = requests.post(f"{SUPABASE_URL}/rest/v1/intel_fact_entities?{OC}",
                                   headers={**H, "Prefer": "return=minimal,resolution=ignore-duplicates"},
                                   json=[row])
                if rr.status_code in (200, 201, 204):
                    ins += 1
                else:
                    fail += 1; last_err = f"{rr.status_code} {rr.text[:160]}"
    if fail:
        print(f"  WARN: {fail} edge rows failed to insert (last: {last_err})")
    fixed = 0
    for (sid, st), ids in subj_fill.items():
        for j in range(0, len(ids), 200):
            ch = ids[j:j+200]
            if requests.patch(f"{SUPABASE_URL}/rest/v1/intel_facts?id=in.({','.join(map(str,ch))})",
                              headers={**H, "Prefer": "return=minimal"}, json={"subject_id": sid, "subject_type": st}).status_code in (200, 204):
                fixed += len(ch)
    print(f"graph: {ins} edges inserted/confirmed, {fail} failed, {len(rows)} unique edges; "
          f"subject_id backfilled {fixed}; {len(facts)} facts scanned")

if __name__ == "__main__":
    main()
