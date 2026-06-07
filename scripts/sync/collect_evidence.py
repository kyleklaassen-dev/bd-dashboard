#!/usr/bin/env python3
"""
collect_evidence.py — the flywheel: turn collection gaps into cited sources
--------------------------------------------------------------------------
The collection queue says which claims lack an independent source. This goes and
gets them — from sources we can actually fetch and verify — then writes cited
drug_sources rows. On the next narrative regen those rows become INDEPENDENT
corroboration (registry / peer-reviewed tier), triangulation + independence rise,
and the gap auto-resolves. That is the self-feeding loop.

Two precise, low-noise collectors (both idempotent; only real fetched URLs):
  1. ct.gov registry backfill — one registry-tier source per trial NCT (verified
     to exist on clinicaltrials.gov).
  2. Europe PMC publications — peer-reviewed-tier sources mentioning the drug
     (relevance-checked: the drug name must appear in title/abstract).

NEVER fabricates a URL. Writes content_confirms_claim only for fetched, matched sources.

Run:
  python3 scripts/collect_evidence.py --drug-id duvakitug --dry-run
  python3 scripts/collect_evidence.py --area tl1a --limit 5
"""
import os, re, sys, json, time, argparse, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'narrative'))
import narrative_gen as ng  # get/_request + key handling

CTGOV = "https://clinicaltrials.gov/api/v2/studies"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
UA = "meridian-evidence-collector/1.0"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def existing_source_urls(did):
    return {s.get("source_url") for s in
            ng.get(f"drug_sources?drug_id=eq.{did}&select=source_url") if s.get("source_url")}


def collect_ctgov(drug, trials, have):
    did, dname = drug["id"], drug.get("display_name") or drug.get("name") or drug["id"]
    rows = []
    for t in trials:
        nct = t.get("id")
        if not nct or not re.match(r"NCT\d{8}$", str(nct)):
            continue
        url = f"https://clinicaltrials.gov/study/{nct}"
        if url in have:
            continue
        try:
            d = _fetch(f"{CTGOV}/{nct}?fields=protocolSection.identificationModule", timeout=12)
            ok = d.get("protocolSection", {}).get("identificationModule", {}).get("nctId") == nct
        except Exception:
            ok = False
        if not ok:
            continue
        ph, ind = t.get("phase") or "Trial", t.get("indication") or ""
        rows.append({
            "drug_id": did, "drug_name": dname, "claim_type": "trial_registration",
            "claim_value": (f"{ph} trial" + (f" in {ind}" if ind else "") + f" ({nct})")[:300],
            "source_url": url, "source_type": "ct_gov", "source_domain": "clinicaltrials.gov",
            "content_confirms_claim": True, "confidence": "confirmed",
            "added_by": "collect_evidence", "session_label": TODAY})
        have.add(url)
        time.sleep(0.1)
    return rows


def collect_pubs(drug, have, max_pubs):
    did, dname = drug["id"], drug.get("display_name") or drug.get("name") or drug["id"]
    # search by the drug's most identifying name; require the name to actually appear.
    terms = [t for t in {dname, drug.get("name")} if t and len(str(t)) > 3]
    needle = re.sub(r"[^a-z0-9]", "", (drug.get("name") or dname).lower())
    rows, seen = [], 0
    for term in terms[:2]:
        if seen >= max_pubs:
            break
        try:
            q = urllib.parse.quote(f'"{term}"')
            res = _fetch(f"{EPMC}?query={q}&format=json&pageSize=6&resultType=core")["resultList"]["result"]
        except Exception:
            continue
        for x in res:
            if seen >= max_pubs:
                break
            doi = (x.get("doi") or "").lower()
            if not doi:
                continue
            url = f"https://doi.org/{doi}"
            if url in have:
                continue
            blob = re.sub(r"[^a-z0-9]", "", ((x.get("title") or "") + " " + (x.get("abstractText") or "")).lower())
            if needle not in blob:                      # relevance guard — must mention the drug
                continue
            rows.append({
                "drug_id": did, "drug_name": dname, "claim_type": "publication",
                "claim_value": (x.get("title") or "")[:300],
                "source_url": url, "source_type": "publication", "source_domain": "doi.org",
                "content_confirms_claim": True, "confidence": "inferred",
                "added_by": "collect_evidence", "session_label": TODAY})
            have.add(url); seen += 1
        time.sleep(0.15)
    return rows


def collect_drug(did, max_pubs, only):
    drug = ng.get(f"drugs?id=eq.{did}&select=id,name,display_name")
    if not drug:
        return []
    drug = drug[0]
    trials = ng.get(f"trials?drug_id=eq.{did}&select=id,phase,indication")
    have = existing_source_urls(did)
    rows = []
    if only in ("both", "ctgov"):
        rows += collect_ctgov(drug, trials, have)
    if only in ("both", "pubs"):
        rows += collect_pubs(drug, have, max_pubs)
    return rows


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--drug-id"); g.add_argument("--area")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-pubs", type=int, default=3)
    ap.add_argument("--only", default="both", choices=["both", "ctgov", "pubs"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ids = ([args.drug_id] if args.drug_id else
           sorted({r["drug_id"] for r in ng.get(f"drug_targets?target_id=eq.{args.area}&select=drug_id")
                   if r.get("drug_id")}))
    if args.limit:
        ids = ids[:args.limit]

    total = 0
    for did in ids:
        rows = collect_drug(did, args.max_pubs, args.only)
        if rows:
            print(f"  {did}: +{len(rows)} sources "
                  f"({sum(r['source_type']=='ct_gov' for r in rows)} ct.gov, "
                  f"{sum(r['source_type']=='publication' for r in rows)} pubs)")
            for r in rows:
                print(f"      {r['source_type']:11} {r['source_url']}")
            if not args.dry_run:
                ng._request("POST", "drug_sources", rows, {"Prefer": "return=minimal"})
            total += len(rows)
    print(f"\n{'[dry-run] would add' if args.dry_run else 'added'} {total} sources across {len(ids)} drug(s).")


if __name__ == "__main__":
    main()
