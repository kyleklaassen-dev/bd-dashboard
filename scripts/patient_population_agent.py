#!/usr/bin/env python3
"""
patient_population_agent.py — PATIENT-domain epidemiology enrichment (no fabrication)
------------------------------------------------------------------------------------
Fills `drugs.patient_population` (text) for drugs that lack it, by deriving a concise
QUANTIFIED population descriptor from the drug's lead indication (drugs.indication_short)
using authoritative epidemiology literature via Europe PMC REST.

NO-FABRICATION CONTRACT
-----------------------
- A drug is only filled when an actual Europe PMC abstract literally contains a
  quantified epidemiology figure (prevalence / incidence / "per 100,000" / "% of" /
  "X million") IN A SENTENCE THAT ALSO MENTIONS THE DISEASE. The stored descriptor is
  that verbatim sentence (HTML-stripped, whitespace-collapsed, length-capped),
  prefixed only with the disease's plain name.
- Real DOIs only (Europe PMC `doi` field). Never a guessed URL.
- Multi-disease analytical aggregates ("IgG-mediated autoimmune disease",
  "B-cell-mediated autoimmune disease", etc.) are NOT single diseases -> SKIPPED & reported.
- Drugs whose abstracts yield no qualifying quantified sentence -> SKIPPED & reported.

GOVERNANCE
----------
Every written fact gets a `drug_sources` row:
  claim_type='patient_population', source_type='publication', source_domain='doi.org',
  content_confirms_claim=true, confidence='confirmed', added_by='patient_agent',
  session_label='2026-06-07-patient'.
Never touches company_id / originator / any governance-protected field.

IDEMPOTENT
----------
- Skips drugs that already have a non-null patient_population.
- Skips writing a drug_sources row if one already exists for (drug_id, claim_type,
  added_by='patient_agent').

RELIABILITY DESIGN (two phases)
-------------------------------
Network (slow, EPMC) is isolated from DB writes:

  1) python3 scripts/patient_population_agent.py --build-cache [--offset N --limit M]
        Resolves each TARGET drug's lead indication -> unique disease set, fetches EPMC
        once per disease, caches {disease_key: {descriptor,url,title}} to
        scripts/.patient_epmc_cache.json. Chunk over the unique-disease list with
        --offset/--limit so each run fits a short window. Idempotent: cached diseases
        are skipped unless --refresh.

  2) python3 scripts/patient_population_agent.py --dry-run | --apply
        Pure DB pass (no network): maps every target drug to its cached disease and
        writes patient_population + drug_sources. Fast.
"""
import os, sys, re, json, time, argparse, urllib.request, urllib.parse, unicodedata, subprocess

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = (os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
       or open(os.path.join(WORK, ".supabase_service_key")).read().strip())
SUPA = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
UA = "meridian-patient-agent/1.0"
CACHE = os.path.join(WORK, "scripts", ".patient_epmc_cache.json")
SESSION = "2026-06-07-patient"
MAXLEN = 280

# ---- disease ontology: normalized-key -> (epmc phrase, relevance token, display label)
DISEASE = {
    "uc": ("ulcerative colitis", "ulcerative colitis", "Ulcerative colitis"),
    "ulcerative colitis": ("ulcerative colitis", "ulcerative colitis", "Ulcerative colitis"),
    "cd": ("Crohn disease", "crohn", "Crohn's disease"),
    "crohn": ("Crohn disease", "crohn", "Crohn's disease"),
    "crohn's disease": ("Crohn disease", "crohn", "Crohn's disease"),
    "ibd": ("inflammatory bowel disease", "inflammatory bowel", "Inflammatory bowel disease"),
    "inflammatory bowel disease": ("inflammatory bowel disease", "inflammatory bowel", "Inflammatory bowel disease"),
    "ted": ("thyroid eye disease", "thyroid eye", "Thyroid eye disease"),
    "thyroid eye disease": ("thyroid eye disease", "thyroid eye", "Thyroid eye disease"),
    "ad": ("atopic dermatitis", "atopic dermatitis", "Atopic dermatitis"),
    "atopic dermatitis": ("atopic dermatitis", "atopic dermatitis", "Atopic dermatitis"),
    "asthma": ("asthma", "asthma", "Asthma"),
    "pso": ("psoriasis", "psoriasis", "Psoriasis"),
    "ps": ("psoriasis", "psoriasis", "Psoriasis"),
    "psoriasis": ("psoriasis", "psoriasis", "Psoriasis"),
    "psa": ("psoriatic arthritis", "psoriatic arthritis", "Psoriatic arthritis"),
    "psoriatic arthritis": ("psoriatic arthritis", "psoriatic arthritis", "Psoriatic arthritis"),
    "ra": ("rheumatoid arthritis", "rheumatoid arthritis", "Rheumatoid arthritis"),
    "rheumatoid arthritis": ("rheumatoid arthritis", "rheumatoid arthritis", "Rheumatoid arthritis"),
    "axspa": ("axial spondyloarthritis", "spondyloarthritis", "Axial spondyloarthritis"),
    "as": ("ankylosing spondylitis", "ankylosing spondylitis", "Ankylosing spondylitis"),
    "ankylosing spondylitis": ("ankylosing spondylitis", "ankylosing spondylitis", "Ankylosing spondylitis"),
    "sle": ("systemic lupus erythematosus", "lupus", "Systemic lupus erythematosus"),
    "lupus": ("systemic lupus erythematosus", "lupus", "Systemic lupus erythematosus"),
    "ln": ("lupus nephritis", "lupus nephritis", "Lupus nephritis"),
    "lupus nephritis": ("lupus nephritis", "lupus nephritis", "Lupus nephritis"),
    "igan": ("IgA nephropathy", "iga nephropathy", "IgA nephropathy"),
    "iga nephropathy": ("IgA nephropathy", "iga nephropathy", "IgA nephropathy"),
    "sjogren": ("Sjogren syndrome", "sjogren", "Sjögren's syndrome"),
    "waiha": ("warm autoimmune hemolytic anemia", "hemolytic anemia", "Warm autoimmune hemolytic anemia"),
    "pemphigus": ("pemphigus", "pemphigus", "Pemphigus"),
    "gmg": ("myasthenia gravis", "myasthenia", "Myasthenia gravis"),
    "mg": ("myasthenia gravis", "myasthenia", "Myasthenia gravis"),
    "myasthenia gravis": ("myasthenia gravis", "myasthenia", "Myasthenia gravis"),
    "gpp": ("generalized pustular psoriasis", "pustular psoriasis", "Generalized pustular psoriasis"),
    "gpp flares": ("generalized pustular psoriasis", "pustular psoriasis", "Generalized pustular psoriasis"),
    "copd": ("chronic obstructive pulmonary disease", "obstructive pulmonary", "COPD"),
    "ms": ("multiple sclerosis", "multiple sclerosis", "Multiple sclerosis"),
    "multiple sclerosis": ("multiple sclerosis", "multiple sclerosis", "Multiple sclerosis"),
    "multiple myeloma": ("multiple myeloma", "myeloma", "Multiple myeloma"),
    "graves disease": ("Graves disease", "graves", "Graves' disease"),
    "ssc-ild": ("systemic sclerosis", "systemic sclerosis", "Systemic sclerosis"),
    "systemic sclerosis": ("systemic sclerosis", "systemic sclerosis", "Systemic sclerosis"),
    "eoe": ("eosinophilic esophagitis", "eosinophilic esophagitis", "Eosinophilic esophagitis"),
    "csu": ("chronic spontaneous urticaria", "urticaria", "Chronic spontaneous urticaria"),
    "hs": ("hidradenitis suppurativa", "hidradenitis", "Hidradenitis suppurativa"),
}
# tokens that are analytical aggregates, NOT single diseases -> skip
AGGREGATE = {
    "igg-mediated autoimmune disease", "b-cell-mediated autoimmune disease",
    "b cell-mediated autoimmune disease", "autoimmune disease", "autoimmune",
    "b cell malignancies", "b-cell malignancies", "viral lrti", "b cell malignancy",
}

NUM = r'\d[\d.,]*'
FIG = re.compile(r'(' + NUM + r')\s*(per\s?100[, ]?000|per\s?million|million|billion|%|cases per 100[, ]?000|/100[, ]?000)', re.I)
RATIO = re.compile(r'\b' + NUM + r'\s+in\s+' + NUM + r'\b', re.I)
EPI = re.compile(r'prevalen|inciden|affect|estimat|burden|per 100[, ]?000', re.I)
TAG = re.compile(r'<[^>]+>')


def _norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r'[^a-z0-9 ]', ' ', s).strip()


def _req(method, ep, data=None, prefer=None):
    # urllib hangs in this sandbox; curl is reliable. Shell out to curl.
    cmd = ["curl", "-s", "--max-time", "20", "-X", method,
           f"{SUPA}/{ep}",
           "-H", f"apikey: {KEY}", "-H", f"Authorization: Bearer {KEY}",
           "-H", "Content-Type: application/json"]
    if prefer:
        cmd += ["-H", f"Prefer: {prefer}"]
    if data is not None:
        cmd += ["--data", json.dumps(data)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=25).stdout
    except subprocess.TimeoutExpired:
        print(f"  curl timeout {ep[:70]}", file=sys.stderr)
        return None
    if not out.strip():
        return []
    try:
        j = json.loads(out)
    except json.JSONDecodeError:
        print(f"  bad JSON {ep[:70]}: {out[:160]}", file=sys.stderr)
        return None
    if isinstance(j, dict) and j.get("code") and j.get("message"):
        print(f"  PostgREST error {ep[:70]}: {out[:180]}", file=sys.stderr)
        return None
    return j


def lead_disease(indication_short):
    """Parse drugs.indication_short -> (disease_key, phrase, token, label) or None."""
    if not indication_short:
        return None
    # split on common separators; drop parenthetical/year noise per-segment
    segs = re.split(r'[·/;,—]| - ', indication_short)
    for seg in segs:
        s = re.sub(r'\([^)]*\)', '', seg)            # drop (...) qualifiers
        s = re.sub(r'\bphase\s*[0-9].*', '', s, flags=re.I)
        key = _norm(s)
        if not key:
            continue
        if key in AGGREGATE:
            continue
        if key in DISEASE:
            ph, tok, lab = DISEASE[key]
            return (key, ph, tok, lab)
        # token-contains fallback (e.g. "sle  ra  sjogren autoimmune")
        for w in key.split():
            if w in DISEASE:
                ph, tok, lab = DISEASE[w]
                return (w, ph, tok, lab)
    return None


def clean_sentence(s):
    s = TAG.sub(" ", s)
    s = re.sub(r'\s+', ' ', s).strip()
    s = s.strip(" .;,")
    return s


def epmc_descriptor(phrase, token):
    """Return (descriptor_sentence, doi_url, paper_title) or None. Verbatim, no fabrication."""
    q = urllib.parse.quote(f'"{phrase}" AND (epidemiology OR prevalence OR incidence OR burden)')
    try:
        req = urllib.request.Request(
            f"{EPMC}?query={q}&format=json&pageSize=10&resultType=core",
            headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            res = json.load(r)["resultList"]["result"]
    except Exception as e:
        print(f"    EPMC error for {phrase}: {e}", file=sys.stderr)
        return None
    tnorm = _norm(token)
    # disease names accepted *inside the figure sentence* (phrase + normalized key/abbrev)
    accepted = {tnorm, _norm(key)}
    accepted = {a for a in accepted if a}
    SCOPE = ("worldwide", "global", "united states", " us ", "europe", "general population",
             "adults", "children", "population", "estimated", "nationwide", "national")
    # single-country / developing-region studies whose absolute rates do not generalize
    # -> hard-skip so we never ship a misleading "global" population descriptor
    HARDSKIP = ("ethiopia", "iran", "nigeria", "india", "saudi", "pakistan", "bangladesh",
                "egypt", "ghana", "uganda", "kenya", "tanzania", "morocco", "tunisia",
                "single-center", "single center", "tertiary", "hospital-based")
    REGION = ("korea", "china", "japan", "taiwan", "brazil", "turkey", "thailand")
    cands = []
    for x in res:
        doi = (x.get("doi") or "").lower()
        if not doi:
            continue
        ab = TAG.sub(" ", x.get("abstractText") or "")
        if tnorm not in _norm(ab):                       # paper relevance guard
            continue
        for raw in re.split(r'(?<=[.;])\s+(?=[A-Z0-9])', ab):
            sl = _norm(raw)
            if not EPI.search(raw):
                continue
            if not (FIG.search(raw) or RATIO.search(raw)):
                continue
            # require the disease to be named IN the figure-bearing sentence (quality)
            if not any(re.search(r'\b' + re.escape(a) + r'\b', sl) for a in accepted):
                continue
            if any(t in sl for t in HARDSKIP):           # non-generalizable single-country study
                continue
            sent = clean_sentence(raw)
            if not sent or len(sent) < 25:
                continue
            score = len(sent) / 600.0
            if "prevalen" in sl:
                score -= 2.0
            if "inciden" in sl:
                score -= 1.0
            if "per 100" in sl or "million" in sl:
                score -= 1.2
            if any(t in sl for t in SCOPE):
                score -= 1.0
            if any(t in sl for t in REGION):             # deprioritize narrow regional studies
                score += 2.0
            cands.append((score, sent, f"https://doi.org/{doi}", x.get("title") or ""))
    if not cands:
        return None
    cands.sort(key=lambda c: c[0])
    _, sent, url, title = cands[0]
    if len(sent) > MAXLEN:
        sent = sent[:MAXLEN].rsplit(" ", 1)[0] + "…"
    return (sent, url, title)


def target_drugs():
    rows = _req("GET", "drugs?select=id,name,indication_short,overlap,stage"
                       "&patient_population=is.null"
                       "&overlap=in.(Direct,Adjacent,Same-Space)"
                       "&order=name") or []
    return rows


def load_cache():
    if os.path.exists(CACHE):
        return json.load(open(CACHE))
    return {}


def save_cache(c):
    json.dump(c, open(CACHE, "w"), indent=1)


# --------------------------------------------------------------------------- modes
def build_cache(offset, limit, refresh):
    rows = target_drugs()
    # unique disease set among targets (skip aggregates / empty)
    diseases, skipped = {}, []
    for r in rows:
        ld = lead_disease(r.get("indication_short"))
        if ld is None:
            skipped.append(r["name"])
            continue
        key, ph, tok, lab = ld
        diseases.setdefault(key, (ph, tok, lab))
    keys = sorted(diseases)
    cache = load_cache()
    todo = [k for k in keys if refresh or k not in cache]
    chunk = todo[offset: offset + limit] if limit else todo[offset:]
    print(f"{len(rows)} target drugs | {len(keys)} unique diseases | "
          f"{len(todo)} uncached | processing {len(chunk)} this run "
          f"(offset={offset} limit={limit})")
    print(f"unmappable (aggregate/empty indication, will be skipped in write): {len(skipped)}")
    for k in chunk:
        ph, tok, lab = diseases[k]
        res = epmc_descriptor(ph, tok)
        time.sleep(0.1)
        if res is None:
            cache[k] = {"label": lab, "descriptor": None, "url": None, "title": None}
            print(f"  [no figure] {lab}")
        else:
            sent, url, title = res
            cache[k] = {"label": lab, "descriptor": sent, "url": url, "title": title}
            print(f"  [ok] {lab}: {url}\n        {sent[:150]}")
        save_cache(cache)
    remaining = [k for k in keys if k not in cache]
    print(f"\ncache now holds {len(cache)} diseases; {len(remaining)} remaining: {remaining}")


def existing_source_drug_ids():
    rows = _req("GET", "drug_sources?select=drug_id&added_by=eq.patient_agent"
                       "&claim_type=eq.patient_population") or []
    return {r["drug_id"] for r in rows}


def write(apply):
    rows = target_drugs()
    cache = load_cache()
    have_src = existing_source_drug_ids()
    filled, skip_agg, skip_nofig, skip_nocache, src_added = [], [], [], [], 0
    for r in rows:
        ld = lead_disease(r.get("indication_short"))
        if ld is None:
            skip_agg.append(r["name"])
            continue
        key = ld[0]
        ent = cache.get(key)
        if ent is None:
            skip_nocache.append(r["name"])
            continue
        if not ent.get("descriptor"):
            skip_nofig.append(f"{r['name']} ({ent['label']})")
            continue
        desc = f"{ent['label']} — {ent['descriptor']}"
        if len(desc) > MAXLEN + 40:
            desc = desc[:MAXLEN + 40].rsplit(" ", 1)[0] + "…"
        url = ent["url"]
        filled.append((r["id"], r["name"], desc, url))
        if apply:
            _req("PATCH", f"drugs?id=eq.{urllib.parse.quote(r['id'])}",
                 {"patient_population": desc}, prefer="return=minimal")
            if r["id"] not in have_src:
                row = {
                    "drug_id": r["id"], "drug_name": r["name"],
                    "claim_type": "patient_population", "claim_value": desc,
                    "source_url": url, "source_type": "publication",
                    "source_domain": "doi.org", "content_confirms_claim": True,
                    "confidence": "confirmed", "added_by": "patient_agent",
                    "session_label": SESSION,
                }
                res = _req("POST", "drug_sources", row, prefer="return=minimal")
                if res is not None:
                    src_added += 1
                    have_src.add(r["id"])
    tag = "APPLIED" if apply else "[dry-run]"
    print(f"\n{tag} patient_population fills: {len(filled)}")
    for did, nm, desc, url in filled:
        print(f"  {nm}: {desc[:130]}\n      ↳ {url}")
    print(f"\ndrug_sources rows added: {src_added}")
    print(f"SKIPPED — aggregate/empty indication ({len(skip_agg)}): {', '.join(skip_agg)}")
    print(f"SKIPPED — no quantified figure in abstract ({len(skip_nofig)}): {', '.join(skip_nofig)}")
    if skip_nocache:
        print(f"SKIPPED — disease not yet cached, run --build-cache ({len(skip_nocache)}): {', '.join(skip_nocache)}")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build-cache", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refresh", action="store_true", help="re-fetch already-cached diseases")
    a = ap.parse_args()
    if a.build_cache:
        build_cache(a.offset, a.limit, a.refresh)
    else:
        write(a.apply)


if __name__ == "__main__":
    main()
