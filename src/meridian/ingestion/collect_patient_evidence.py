#!/usr/bin/env python3
"""
collect_patient_evidence.py — patient/epidemiology source collector (Collector v2)
----------------------------------------------------------------------------------
The drug flywheel (collect_evidence.py) sources DRUG claims from ct.gov + Europe PMC.
This is its patient-layer sibling: it sources the unmet-need / epidemiology facts in
`indication_patient_intelligence` that currently carry NO external reference
(source_urls empty -> they land INTERNAL-tier in the narrative machinery).

DETERMINISTIC + NO FABRICATION
------------------------------
- Only single-disease rows are sourced (explicit DISEASE map). The "Target Area" /
  "(Broad)" analytical aggregates are NOT single diseases — they are SKIPPED and
  reported, never sourced with a disease paper.
- Sources come ONLY from Europe PMC results that (a) have a real DOI and (b) mention
  the disease in title/abstract (relevance guard). Epidemiology/burden/prevalence
  titles are preferred. Never fabricates a URL.
- Idempotent: rows that already have a real source_url are skipped. Writes the
  row-level `source_urls` list (the established convention; these are disease-level
  supporting references, not per-field citations).

Run:
  python3 scripts/collect_patient_evidence.py --dry-run
  python3 scripts/collect_patient_evidence.py --apply
"""
import os, sys, re, json, time, argparse, urllib.request, urllib.parse

WORK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
KEY = (os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
       or open(os.path.join(WORK, ".supabase_service_key")).read().strip())
SUPA = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
UA = "meridian-patient-collector/1.0"

# indication_name -> (europepmc disease phrase, relevance token that must appear)
DISEASE = {
    "Multiple Myeloma": ("multiple myeloma", "myeloma"),
    "Generalized Myasthenia Gravis": ("myasthenia gravis", "myasthenia"),
    "Thyroid Eye Disease": ("thyroid eye disease", "thyroid eye"),
    "Crohn's Disease": ("Crohn disease", "crohn"),
    "Ulcerative Colitis": ("ulcerative colitis", "ulcerative colitis"),
    "Atopic Dermatitis": ("atopic dermatitis", "atopic dermatitis"),
    "Gastric/GEJ Adenocarcinoma - FGFR2b+": ("gastric adenocarcinoma", "gastric"),
    "IBD (Inflammatory Bowel Disease)": ("inflammatory bowel disease", "inflammatory bowel"),
}
PREF = ("epidemiology", "prevalence", "incidence", "burden", "epidemiolog")


def _req(method, ep, data=None, prefer=None):
    h = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    r = urllib.request.Request(f"{SUPA}/{ep}", data=json.dumps(data).encode() if data is not None else None,
                               headers=h, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            raw = resp.read(); return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} {ep[:60]}: {e.read().decode()[:160]}", file=sys.stderr); return None


def epmc_sources(phrase, token, max_n=2):
    q = urllib.parse.quote(f'"{phrase}" AND (epidemiology OR prevalence OR incidence OR burden)')
    try:
        req = urllib.request.Request(f"{EPMC}?query={q}&format=json&pageSize=12&resultType=core",
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.load(r)["resultList"]["result"]
    except Exception as e:
        print(f"    EPMC error for {phrase}: {e}", file=sys.stderr); return []
    tnorm = re.sub(r"[^a-z0-9 ]", "", token.lower())
    scored = []
    for x in res:
        doi = (x.get("doi") or "").lower()
        if not doi:
            continue
        blob = ((x.get("title") or "") + " " + (x.get("abstractText") or "")).lower()
        if tnorm not in re.sub(r"[^a-z0-9 ]", "", blob):     # relevance guard
            continue
        title = (x.get("title") or "")
        pref = any(p in title.lower() for p in PREF)
        scored.append((0 if pref else 1, f"https://doi.org/{doi}", title))
    scored.sort(key=lambda s: s[0])
    out, seen = [], set()
    for _, url, title in scored:
        if url in seen:
            continue
        seen.add(url); out.append((url, title))
        if len(out) >= max_n:
            break
    return out


def has_real(su):
    return isinstance(su, list) and any(str(u).startswith("http") for u in su)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    rows = _req("GET", "indication_patient_intelligence?select=id,indication_name,source_urls") or []
    sourced, skipped_agg, no_hits = 0, [], []
    for r in rows:
        name = r.get("indication_name")
        if has_real(r.get("source_urls")):
            continue                                          # idempotent
        if name not in DISEASE:
            skipped_agg.append(name); continue
        phrase, token = DISEASE[name]
        hits = epmc_sources(phrase, token)
        time.sleep(0.2)
        if not hits:
            no_hits.append(name); continue
        urls = [u for u, _ in hits]
        print(f"  {name}: +{len(urls)} source(s)")
        for u, t in hits:
            print(f"      {u}  — {t[:90]}")
        if args.apply:
            _req("PATCH", f"indication_patient_intelligence?id=eq.{r['id']}",
                 {"source_urls": urls}, prefer="return=minimal")
        sourced += 1

    print(f"\n{'APPLIED' if args.apply else '[dry-run] would source'}: {sourced} disease rows")
    print(f"Skipped {len(skipped_agg)} analytical aggregates (not single diseases — not sourced): {', '.join(skipped_agg)}")
    if no_hits:
        print(f"No relevant EPMC hit for: {', '.join(no_hits)}")


if __name__ == "__main__":
    main()
