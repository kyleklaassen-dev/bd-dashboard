#!/usr/bin/env python3
"""
trial_id_audit.py — catalog-wide ClinicalTrials.gov integrity audit
-------------------------------------------------------------------
Why: MT-251 exposed that drug rows carry NCTs that are FABRICATED (don't exist)
or MISATTRIBUTED (the real trial belongs to a different asset). Internal SQL can't
catch this — the truth lives at ClinicalTrials.gov. This script verifies every
NCT the catalog references against the registry and flags mismatches.

Method (proven on MT-251, 2026-06-05):
  - NCT07423299  -> CT.gov page has NO study title  => NONEXISTENT (fabricated)
  - NCT07219368  -> title "...MT-201"               => REAL, but drug=mt-251 => MISMATCH

For each (drug, nct):
  1. Fetch the CT.gov v2 API record.
  2. NONEXISTENT  -> 404 / empty record.
  3. MISMATCH     -> exists, but none of the drug's identifiers (code/name/aliases)
                     appear in the brief title or intervention names.
  4. MATCH        -> drug identifier found in title/interventions.
Findings (NONEXISTENT, MISMATCH) are logged to governance_violations (unresolved =
review queue). NOTHING is auto-edited — trial reassignment is a human judgment call.

⚠ PRE-UNLINK RULE (added 2026-06-11 after a false-delete incident):
A MISMATCH means "the drug's stored aliases weren't found in the trial" — NOT proof the
link is wrong. Trials name drugs by DEVELOPMENT CODE (PF-04965842=abrocitinib,
LNK01001=zemprocitinib) which may be absent from aliases, and codes can COLLIDE across
assets (VTx-002 gene-therapy vs VTX002 small-molecule). NEVER delete a (drug, NCT) link
on a MISMATCH flag without calling verify_unlink(drug_id, nct) and getting clear=True.
That gate returns the trial's real interventions + lead sponsor so a dev-code match or a
code collision is caught instead of silently deleting a correct link. When it returns
clear=False, confirm sponsor/molecule by hand (and backfill the dev code into drugs.aliases).

Run:
  python3 src/meridian/validation/trial_id_audit.py --area tl1a --dry-run      # focus set, no writes
  python3 src/meridian/validation/trial_id_audit.py --all --apply              # whole catalog, log findings
"""

import os, re, sys, json, time, argparse, urllib.request, urllib.error
from datetime import datetime, timezone

SUPA = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
CTGOV = "https://clinicaltrials.gov/api/v2/studies"
WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _secret(env_name, filename):
    """Read a credential from an env var (CI) or a workspace file (local)."""
    v = os.environ.get(env_name)
    if v:
        return v.strip()
    p = os.path.join(WORKSPACE, filename)
    return open(p).read().strip() if os.path.exists(p) else None


KEY = _secret("SUPABASE_SERVICE_KEY", ".supabase_service_key")
ACTOR = "trial_id_audit.py@v0"
SESSION = f"trial-audit-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
NCT_RE = re.compile(r"NCT\d{8}", re.I)


def _sb(method, ep, data=None, prefer=None):
    hdr = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    if prefer: hdr["Prefer"] = prefer
    req = urllib.request.Request(f"{SUPA}/{ep}", data=json.dumps(data).encode() if data is not None else None,
                                 headers=hdr, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read(); return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as e:
        print(f"  SB {e.code}: {e.read().decode()[:120]}", file=sys.stderr); return None


def ctgov_record(nct):
    """Return (exists, brief_title, intervention_names[]) for an NCT."""
    url = (f"{CTGOV}/{nct}?fields=protocolSection.identificationModule,"
           f"protocolSection.armsInterventionsModule")
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "Mozilla/5.0 meridian-audit"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404: return (False, None, [])
        raise
    ps = d.get("protocolSection", {})
    title = ps.get("identificationModule", {}).get("briefTitle", "")
    ints = [i.get("name", "") for i in
            ps.get("armsInterventionsModule", {}).get("interventions", [])]
    return (True, title, ints)


def drug_identifiers(drug_id):
    """Tokens that should appear in a matching trial: the drug code, name, aliases.
    drug_aliases is keyed by canonical_id (col=alias_name), NOT drug_id — joining wrong
    here caused false-positive MISMATCHes."""
    toks = {drug_id.lower().replace("-", " "), drug_id.lower()}
    rows = _sb("GET", f"drugs?id=eq.{drug_id}&select=name,display_name,brand_name,aliases,canonical_drug_id")
    cid = None
    if rows:
        d = rows[0]; cid = d.get("canonical_drug_id")
        for k in ("name", "display_name", "brand_name"):
            if d.get(k): toks.add(str(d[k]).lower())
        if isinstance(d.get("aliases"), list):
            toks |= {str(a).lower() for a in d["aliases"] if a}
    if cid:
        for a in _sb("GET", f"drug_aliases?canonical_id=eq.{cid}&select=alias_name") or []:
            if a.get("alias_name"): toks.add(a["alias_name"].lower())
    return {t for t in toks if len(t) >= 3}


NCT8 = re.compile(r"NCT\d{8}", re.I)


def collect_refs(area=None):
    """(drug_id, nct) references from the structured NCT columns + drugs.source_url.
    Uses the Management API (CTE) when a PAT is available, else a pure-PostgREST
    fallback so the job runs in CI with only SUPABASE_SERVICE_KEY."""
    pat = _secret("SUPABASE_PAT", ".supabase_pat")
    if pat:
        try:
            return _run_sql(_refs_sql(area), pat)
        except Exception as e:
            print(f"  (management API unavailable, PostgREST fallback: {e})", file=sys.stderr)

    # PostgREST fallback: pull each source, extract NCTs, union in Python.
    refs = set()
    def add(did, raw):
        m = NCT8.search(str(raw or ""))
        if did and m:
            refs.add((did, m.group(0).upper()))
    for r in _sb("GET", "catalysts?select=drug_id,related_trial_id&related_trial_id=ilike.*NCT*") or []:
        add(r.get("drug_id"), r.get("related_trial_id"))
    for r in _sb("GET", "drug_clinical_benchmarks?select=drug_id,nct_id&nct_id=ilike.*NCT*") or []:
        add(r.get("drug_id"), r.get("nct_id"))
    for r in _sb("GET", "drug_bispecific_landscape?select=drug_id,nct_id&nct_id=ilike.*NCT*") or []:
        add(r.get("drug_id"), r.get("nct_id"))
    for r in _sb("GET", "platform_trials?select=backbone_drug_id,nct_id&nct_id=ilike.*NCT*") or []:
        add(r.get("backbone_drug_id"), r.get("nct_id"))
    for r in _sb("GET", "drugs?select=id,source_url&source_url=ilike.*NCT*") or []:
        add(r.get("id"), r.get("source_url"))
    if area:
        keep = {r["drug_id"] for r in
                _sb("GET", f"drug_targets?select=drug_id&target_id=eq.{area}") or []}
        refs = {(d, n) for d, n in refs if d in keep}
    return [{"drug_id": d, "nct": n} for d, n in sorted(refs)]


def _refs_sql(area):
    where_join = (f" join drug_targets dt on dt.drug_id=r.drug_id and dt.target_id='{area}'"
                  if area else "")
    return (
      "with r as ("
      " select drug_id, upper(related_trial_id) nct from catalysts where related_trial_id ~* 'NCT[0-9]{8}'"
      " union select drug_id, upper(nct_id) from drug_clinical_benchmarks where nct_id ~* 'NCT[0-9]{8}'"
      " union select drug_id, upper(nct_id) from drug_bispecific_landscape where nct_id ~* 'NCT[0-9]{8}'"
      " union select backbone_drug_id, upper(nct_id) from platform_trials where nct_id ~* 'NCT[0-9]{8}'"
      " union select id, upper((regexp_matches(coalesce(source_url,''),'NCT[0-9]{8}'))[1]) from drugs where source_url ~* 'NCT[0-9]{8}'"
      f") select distinct r.drug_id, r.nct from r{where_join} where r.drug_id is not null order by 1,2")


def _run_sql(sql, pat):
    req = urllib.request.Request(
        "https://api.supabase.com/v1/projects/tghntyofptvfhmtchwcv/database/query",
        data=json.dumps({"query": sql}).encode(),
        headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0 meridian"}, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def _compact(s):
    """Lowercase, strip all non-alphanumerics — so 'SM101' == 'sm-101' == 'sm 101'."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def classify(drug_id, nct):
    exists, title, ints = ctgov_record(nct)
    if not exists:
        return ("NONEXISTENT", f"{nct} not found on ClinicalTrials.gov (fabricated).", title)
    text = title + " " + " ".join(ints)
    hay = text.lower()
    hay_c = _compact(text)
    toks = drug_identifiers(drug_id)

    def hit(t):
        # 1) original loose substring match (keeps prior behaviour)
        if t in hay:
            return True
        # 2) casing/punctuation-insensitive match — fixes false MISMATCHes where the
        #    registry code is hyphenated but the trial spells it solid (sm-101 vs SM101).
        #    Guarded at len>=4 so short codes can't coincidentally match.
        tc = _compact(t)
        return len(tc) >= 4 and tc in hay_c

    if any(hit(t) for t in toks):
        return ("MATCH", title, title)
    # Surface what the trial ACTUALLY studies, so a reviewer can spot a real link the
    # alias set missed (a development code: e.g. interventions=['PF-04965842']=abrocitinib)
    # BEFORE anyone unlinks. This is the verification aid that prevents false-delete.
    iv = "; ".join(i for i in ints if i) or "none listed (observational/registry?)"
    return ("MISMATCH", f"{nct} exists as '{title}' — no identifier for '{drug_id}' "
                        f"({', '.join(sorted(toks))[:60]}) present; likely another asset. "
                        f"⚠ VERIFY before unlinking — trial interventions: [{iv}].", title)


def verify_unlink(drug_id, nct):
    """Pre-unlink safety gate. NEVER delete a misattributed (drug, NCT) link without
    calling this and getting clear=True. Returns the trial's real interventions + sponsor
    so a development-code match (PF-04965842=abrocitinib) or a code COLLISION
    (VTx-002 gene-therapy vs VTX002 small-molecule — same code, different asset/sponsor)
    is caught instead of silently deleting a correct link."""
    exists, title, ints = ctgov_record(nct)
    if not exists:
        return {"clear": True, "reason": "trial does not exist (fabricated NCT)",
                "interventions": [], "sponsor": None}
    sponsor, study_type = _ctgov_meta(nct)
    toks = drug_identifiers(drug_id)
    iv_blob = _compact(" ".join(ints))
    code_hit = sorted(t for t in toks if len(_compact(t)) >= 4 and _compact(t) in iv_blob)
    if code_hit:
        return {"clear": False,
                "reason": f"BLOCK: drug identifier {code_hit} appears in interventions — "
                          f"likely a real link (dev code) OR a code collision. "
                          f"Confirm sponsor/molecule manually. sponsor='{sponsor}'.",
                "interventions": ints, "sponsor": sponsor, "study_type": study_type}
    return {"clear": True,
            "reason": f"clear to unlink — drug absent from interventions; trial studies "
                      f"{ints or '(observational/registry — no drug intervention)'}; sponsor='{sponsor}'.",
            "interventions": ints, "sponsor": sponsor, "study_type": study_type}


def _ctgov_meta(nct):
    """(lead_sponsor, study_type) for a trial — used by verify_unlink."""
    url = (f"{CTGOV}/{nct}?fields=protocolSection.sponsorCollaboratorsModule,"
           f"protocolSection.designModule")
    try:
        with urllib.request.urlopen(urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 meridian-audit"}), timeout=20) as r:
            ps = json.loads(r.read()).get("protocolSection", {})
        sponsor = (ps.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}) or {}).get("name")
        return sponsor, ps.get("designModule", {}).get("studyType")
    except Exception:
        return None, None


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--area"); g.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.5)
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    refs = collect_refs(None if args.all else args.area)
    print(f"Auditing {len(refs)} (drug, NCT) references "
          f"[{'all' if args.all else args.area}]...\n")
    counts = {"MATCH": 0, "MISMATCH": 0, "NONEXISTENT": 0}
    for row in refs:
        did, nct = row["drug_id"], row["nct"]
        try:
            verdict, detail, title = classify(did, nct)
        except Exception as e:
            print(f"  ? {did} {nct}: error {e}"); continue
        counts[verdict] += 1
        if verdict != "MATCH":
            print(f"  ✗ {verdict:11} {did:18} {nct}  {detail[:80]}")
            if apply:
                _sb("POST", "governance_violations?on_conflict=table_name,row_id,rule_name", [{
                    "table_name": "drugs", "row_id": did,
                    "rule_name": f"trial_{'fabricated' if verdict=='NONEXISTENT' else 'misattributed'}_{nct}",
                    "description": detail, "resolved": False,
                    "resolution_notes": f"{ACTOR} {SESSION}. Review/reassign — NOT auto-edited.",
                }], prefer="resolution=merge-duplicates,return=minimal")
        time.sleep(args.sleep)
    print(f"\nSUMMARY: {counts['MATCH']} match | {counts['MISMATCH']} misattributed | "
          f"{counts['NONEXISTENT']} fabricated  (of {len(refs)})")
    if not apply:
        print("[dry-run] no governance rows written.")


if __name__ == "__main__":
    main()
