#!/usr/bin/env python3
"""
verify_publication_values.py — cross-publication value agreement (v77)
---------------------------------------------------------------------
For each trial that has a LINKED publication (trial_publications, via the v73
ct.gov crosswalk), fetch the paper's abstract from Europe PMC and check whether
our stored efficacy numbers (drug_clinical_benchmarks.rate_pct) actually appear
in it. Records `confirmed` (the paper reports our number — independent
confirmation) or `unconfirmed_in_abstract` into benchmark_publication_checks.

This is the real cross-SOURCE agreement layer (the intra-DB check in v74 only
compares values we already stored).

Run:
  python3 scripts/verify_publication_values.py --drug-id tulisokibart
  python3 scripts/verify_publication_values.py --area tl1a
"""
import os, re, sys, json, argparse, urllib.request, urllib.error
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import narrative_gen as ng  # reuse get/_request/resolver/recipe + key handling

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
TOL = 1.5  # percentage points


def abstract_values(pmid, _cache={}):
    if pmid in _cache:
        return _cache[pmid]
    vals = set()
    try:
        req = urllib.request.Request(f"{EPMC}?query=ext_id:{pmid}%20src:med&format=json&resultType=core",
                                     headers={"User-Agent": "meridian-pubcheck/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.load(r).get("resultList", {}).get("result", [])
        ab = (res[0].get("abstractText") or "") if res else ""
        vals = {float(x) for x in re.findall(r"(\d{1,3}(?:\.\d)?)\s*%", ab)}
    except Exception as e:
        print(f"    epmc warn pmid {pmid}: {e}", file=sys.stderr)
    _cache[pmid] = vals
    return vals


def check_drug(did):
    recipe = ng.fetch_recipe(did)
    pubs = recipe.get("trial_publications", []) or []
    if not pubs:
        return []
    pub_by_nct = {}
    for p in pubs:
        pub_by_nct.setdefault(p["nct_id"], p)
    resolver = ng.build_study_resolver(recipe)
    rows = []
    for b in recipe.get("benchmarks", []) or []:
        rate = b.get("rate_pct")
        dl = str(b.get("dose_label") or "")
        if rate is None or not re.search(r"\d+\s*mg|\bIV\b|\bSC\b", dl, re.I):
            continue
        ncts = ng.resolve_ncts(b.get("trial_name") or "", b.get("source_url"), resolver)
        nct = next((n for n in ncts if n in pub_by_nct), None)
        if not nct:
            continue
        pub = pub_by_nct[nct]
        if not pub.get("pmid"):
            continue
        avals = abstract_values(pub["pmid"])
        if not avals:
            continue
        hit = any(abs(float(rate) - v) <= TOL for v in avals)
        rows.append({
            "drug_id": did, "nct_id": nct, "pmid": pub.get("pmid"), "doi": pub.get("doi"),
            "metric": b.get("benchmark_type"), "timepoint_weeks": b.get("timepoint_weeks"),
            "dose_label": dl, "stored_value": float(rate),
            "status": "confirmed" if hit else "unconfirmed_in_abstract",
            "abstract_values": sorted(avals)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--drug-id"); g.add_argument("--area")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ids = ([args.drug_id] if args.drug_id else
           sorted({r["drug_id"] for r in ng.get(f"drug_targets?target_id=eq.{args.area}&select=drug_id")
                   if r.get("drug_id")}))
    allrows = []
    for did in ids:
        rows = check_drug(did)
        for r in rows:
            print(f"  {r['status']:24} {did}/{r['nct_id']} {r['metric']} {r['stored_value']}% "
                  f"(abstract: {r['abstract_values']})")
        allrows += rows
    nconf = sum(1 for r in allrows if r["status"] == "confirmed")
    print(f"\n{len(allrows)} checks: {nconf} confirmed by paper, "
          f"{len(allrows)-nconf} unconfirmed-in-abstract.")
    if allrows and not args.dry_run:
        for r in allrows:
            r["checked_at"] = datetime.now(timezone.utc).isoformat()
        ng._request("POST", "benchmark_publication_checks?on_conflict="
                    "drug_id,nct_id,metric,timepoint_weeks,dose_label,stored_value",
                    allrows, {"Prefer": "resolution=merge-duplicates,return=minimal"})
        print(f"  wrote {len(allrows)} publication checks.")
    elif args.dry_run:
        print("[dry-run] no write.")


if __name__ == "__main__":
    main()
