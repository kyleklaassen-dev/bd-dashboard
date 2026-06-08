#!/usr/bin/env python3
"""
enrich_trial_identity.py — populate the study-identity resolver + publication crosswalk
--------------------------------------------------------------------------------------
Design: makes narrative triangulation DEEPER (docs question §"deeper connections").
For each registered trial we pull, from clinicaltrials.gov v2:
  • canonical identity  → trial_identity   (acronym, titles, sponsor ids → alias_tokens)
  • its publications    → trial_publications (pmid, DOI via Europe PMC, citation)
and backfill trials.study_acronym where null.

Why: a registry claim (clinicaltrials.gov) can then be triangulated against its
peer-reviewed paper (e.g. nejm.org) — a genuinely INDEPENDENT domain — and any DOI
in our data that no trial lists is exposed as a suspect/fabricated citation.

Run:
  python3 scripts/enrich_trial_identity.py --drug-id tulisokibart
  python3 scripts/enrich_trial_identity.py --area tl1a [--limit N]
  python3 scripts/enrich_trial_identity.py --nct NCT04996797 --dry-run
"""
import os, re, sys, json, time, argparse, urllib.request, urllib.error
from urllib.parse import quote

# scripts/ root must be importable for _common, _db, ai.* (this file's
# own directory is already on sys.path when run directly).
_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _common import load_credentials
_SUPABASE_URL, KEY, _ = load_credentials(require_anthropic=False)
SUPA = f"{_SUPABASE_URL}/rest/v1"
CTGOV = "https://clinicaltrials.gov/api/v2/studies"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
UA = "meridian-trial-identity/1.0"

# Generic all-caps tokens that must never become a study alias (would false-match).
_ALIAS_STOP = {"PHASE", "STUDY", "TRIAL", "RANDOMIZED", "DOUBLE", "BLIND", "PLACEBO",
               "CONTROLLED", "MULTICENTER", "SAFETY", "EFFICACY", "OPEN", "LABEL",
               "EXTENSION", "PART", "COHORT", "ACTIVE", "SUBJECTS", "PATIENTS"}


def _get(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _sb(method, endpoint, data=None, prefer=None):
    hdrs = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
            "User-Agent": UA}
    if prefer:
        hdrs["Prefer"] = prefer
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(f"{SUPA}/{endpoint}", data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as e:
        print(f"  SB {e.code} {method} {endpoint.split('?')[0]}: {e.read().decode()[:200]}", file=sys.stderr)
        return None


def ncts_for(args):
    if args.nct:
        return [args.nct]
    if args.drug_id:
        return sorted({r["id"] for r in _sb("GET", f"trials?drug_id=eq.{args.drug_id}&select=id") or []})
    if args.area:
        ids = sorted({r["drug_id"] for r in _sb("GET", f"drug_targets?target_id=eq.{args.area}&select=drug_id") or []
                      if r.get("drug_id")})
        ncts = []
        for d in ids:
            ncts += [r["id"] for r in _sb("GET", f"trials?drug_id=eq.{d}&select=id") or []]
        return sorted(set(ncts))
    raise SystemExit("need --nct, --drug-id, or --area")


def alias_tokens(idm):
    toks = set()
    for v in [idm.get("acronym"), idm.get("orgStudyIdInfo", {}).get("id")]:
        if v:
            toks.add(v.strip().upper())
    for s in idm.get("secondaryIdInfos", []) or []:
        if s.get("id"):
            toks.add(s["id"].strip().upper())
    # distinctive title tokens: an embedded acronym or sponsor code (has a digit or a hyphen,
    # all-caps, len>=4), e.g. MK-7240, PRA023 — skip plain English words.
    for t in re.findall(r"\b[A-Z0-9][A-Z0-9\-]{3,}\b", (idm.get("briefTitle") or "")):
        base = t.split("-")[0]
        if base in _ALIAS_STOP:
            continue
        if re.search(r"\d", t) or "-" in t:
            toks.add(t.upper())
    return sorted(toks)


def pmid_to_doi(pmid):
    try:
        r = _get(f"{EPMC}?query=ext_id:{pmid}%20src:med&format=json&resultType=core", timeout=15)
        res = r.get("resultList", {}).get("result", [])
        if res:
            doi = (res[0].get("doi") or "").lower() or None
            jrnl = res[0].get("journalInfo", {}).get("journal", {}).get("title")
            return doi, jrnl
    except Exception as e:
        print(f"    epmc warn pmid {pmid}: {e}", file=sys.stderr)
    return None, None


def enrich_one(nct, drug_by_nct, dry):
    try:
        d = _get(f"{CTGOV}/{nct}?fields=protocolSection.identificationModule,"
                 f"protocolSection.referencesModule", timeout=20)["protocolSection"]
    except Exception as e:
        print(f"  {nct}: ctgov fetch failed ({e})", file=sys.stderr)
        return 0, 0
    idm = d.get("identificationModule", {})
    aliases = alias_tokens(idm)
    ident = {
        "nct_id": nct, "drug_id": drug_by_nct.get(nct),
        "acronym": idm.get("acronym"), "brief_title": idm.get("briefTitle"),
        "official_title": idm.get("officialTitle"),
        "org_study_id": idm.get("orgStudyIdInfo", {}).get("id"),
        "secondary_ids": [s.get("id") for s in idm.get("secondaryIdInfos", []) or [] if s.get("id")],
        "alias_tokens": aliases, "source": "ctgov",
    }
    refs = d.get("referencesModule", {}).get("references", []) or []
    pubs = []
    for r in refs:
        pmid = r.get("pmid")
        if not pmid:
            continue
        doi, jrnl = pmid_to_doi(pmid)
        pubs.append({"nct_id": nct, "pmid": str(pmid), "doi": doi, "journal": jrnl,
                     "citation": (r.get("citation") or "")[:600],
                     "pub_url": f"https://doi.org/{doi}" if doi else None,
                     "ref_type": r.get("type"), "source": "ctgov"})
        time.sleep(0.15)

    print(f"  {nct}: acronym={ident['acronym']} aliases={len(aliases)} pubs={len(pubs)}")
    if dry:
        for p in pubs:
            print(f"      pub pmid={p['pmid']} doi={p['doi']} [{p['ref_type']}]")
        return len(aliases), len(pubs)

    _sb("POST", "trial_identity?on_conflict=nct_id", ident,
        "resolution=merge-duplicates,return=minimal")
    # backfill the trials row's acronym when ct.gov has one and ours is null
    if ident["acronym"]:
        _sb("PATCH", f"trials?id=eq.{nct}&study_acronym=is.null",
            {"study_acronym": ident["acronym"]}, "return=minimal")
    if pubs:
        _sb("POST", "trial_publications?on_conflict=nct_id,pmid", pubs,
            "resolution=merge-duplicates,return=minimal")
    return len(aliases), len(pubs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nct")
    ap.add_argument("--drug-id")
    ap.add_argument("--area")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ncts = ncts_for(args)
    if args.limit:
        ncts = ncts[:args.limit]
    # map nct -> drug_id for the identity rows
    drug_by_nct = {}
    for r in _sb("GET", f"trials?id=in.({','.join(ncts)})&select=id,drug_id") or []:
        drug_by_nct[r["id"]] = r.get("drug_id")

    print(f"Enriching {len(ncts)} trial(s){' [dry-run]' if args.dry_run else ''}")
    ta = tp = 0
    for nct in ncts:
        a, p = enrich_one(nct, drug_by_nct, args.dry_run)
        ta += a; tp += p
    print(f"\nDone: {ta} alias tokens, {tp} publications across {len(ncts)} trials.")


if __name__ == "__main__":
    main()
