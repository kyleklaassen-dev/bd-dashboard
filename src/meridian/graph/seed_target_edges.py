#!/usr/bin/env python3
"""
seed_target_edges.py — connect every drug to ALL of its targets in entity_edges.
================================================================================
The legacy deterministic seeder linked a combo drug (e.g. 'TSLP x IL-4Ra') to
only ONE component target, leaving (a) the combo target nodes (tl1a_il23p19 …)
orphaned and (b) the second target unlinked — breaking Drug->Target->Company
traversal for the entire bispecific set (incl. ALX001 & SL-846).

This seeder parses drugs.target and creates the missing TARGETS edges to:
  * the combo target node (matched by component set, order-independent), and
  * each component single-target node that exists in the ontology.
Additive + idempotent (skips edges already present). Dry-run by default.

    SUPABASE_SERVICE_KEY=... python3 scripts/seed_target_edges.py            # dry run
    SUPABASE_SERVICE_KEY=... python3 scripts/seed_target_edges.py --apply
"""
import os, re, sys, pathlib, requests

BASE = pathlib.Path(__file__).resolve().parents[3]
URL = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
KEY = os.environ.get("SUPABASE_SERVICE_KEY") or (BASE / ".supabase_service_key").read_text().strip()
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
APPLY = "--apply" in sys.argv
OC = "on_conflict=subject_id,predicate,object_id"

# component-string -> ontology single-target-id synonyms (after dash/space/greek strip)
SYN = {"il4r": "il4ra", "il4ralpha": "il4ra", "alpha4beta7": "a4b7", "a4b7": "a4b7",
       "tl1adr3": "tl1a", "dr3tl1a": "dr3", "pdl1": "pdl1", "pd1": "pd1",
       "il23": "il23p19", "p19": "il23p19", "hif1a": "phd1_hif1a", "hif2alpha": "hif2a"}


def getall(t, p):
    out, s = [], 0
    while True:
        r = requests.get(f"{URL}/rest/v1/{t}", headers={**H, "Range": f"{s}-{s+999}"}, params=p)
        d = r.json() if r.status_code in (200, 206) else []
        if not isinstance(d, list):
            break
        out += d
        if len(d) < 1000:
            break
        s += 1000
    return out


def norm(tok):
    t = tok.strip().lower().replace("α", "a").replace("β", "b").replace("γ", "g")
    t = re.sub(r"[\s\-\.\(\)/]", "", t)
    return SYN.get(t, t)


def main():
    targets = {t["id"] for t in getall("targets", {"select": "id"})}
    tset_index = {frozenset(tid.split("_")): tid for tid in targets}  # component-set -> combo id
    drugs = getall("drugs", {"select": "id,name,target"})
    existing = {(e["subject_id"], e["object_id"])
                for e in getall("entity_edges", {"select": "subject_id,object_id", "predicate": "eq.TARGETS"})}

    rows, by_kind = [], {"combo_node": 0, "component": 0}
    unresolved = set()
    for d in drugs:
        raw = (d.get("target") or "").strip()
        if not raw:
            continue
        comps = [c for c in re.split(r"×|\bx\b|/|\+|,|\band\b", raw, flags=re.I) if c.strip()]
        comp_ids = []
        for c in comps:
            nid = norm(c)
            if nid in targets:
                comp_ids.append(nid)
            else:
                # fallback: scan whitespace/parenthetical sub-tokens for an ontology id
                subs = [norm(s) for s in re.split(r"[\s\(\)]+", c) if s.strip()]
                hit = next((s for s in subs if s in targets), None)
                if hit:
                    comp_ids.append(hit)
                elif nid:
                    unresolved.add((nid, c.strip()))
        link_to = set(comp_ids)
        if len(comp_ids) >= 2:                                  # try to find the combo node
            combo = tset_index.get(frozenset(comp_ids))
            if combo:
                link_to.add(combo)
        for tid in link_to:
            if (d["id"], tid) in existing:
                continue
            kind = "combo_node" if "_" in tid and tid not in comp_ids else "component"
            by_kind[kind] += 1
            rows.append({"subject_type": "drug", "subject_id": d["id"], "predicate": "TARGETS",
                         "object_type": "target", "object_id": tid, "generation_method": "deterministic",
                         "status": "active", "confidence_level": "confirmed",
                         "rationale": f"Derived from drugs.target='{raw}'"})

    print(f"{'APPLY' if APPLY else 'DRY RUN'}: {len(rows)} new TARGETS edges "
          f"(combo-node {by_kind['combo_node']}, component {by_kind['component']}); "
          f"{len(existing)} already present")
    if unresolved:
        print("  unresolved target tokens (no ontology node):",
              ", ".join(sorted({f'{n}<{c}>' for n, c in unresolved})[:20]))
    if APPLY and rows:
        ins = 0  # de-duped in-memory AND idempotent at the DB layer via the
                 # entity_edges_subj_pred_obj_uniq constraint (added 2026-06-09).
        for i in range(0, len(rows), 200):
            r = requests.post(f"{URL}/rest/v1/entity_edges?on_conflict=subject_id,predicate,object_id",
                              headers={**H, "Prefer": "return=minimal,resolution=ignore-duplicates"}, json=rows[i:i+200])
            if r.status_code in (200, 201, 204):
                ins += len(rows[i:i+200])
            else:
                print("  ERR", r.status_code, r.text[:200]); break
        print(f"  inserted {ins} edges")


if __name__ == "__main__":
    main()
