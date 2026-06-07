#!/usr/bin/env python3
"""
Round 14 (2026-06-07) — Company/assignee patent layer → `company_patents` (v115).

A patent exclusivity / FTO signal layer BEYOND the Orange-Book NDA patents in
`drug_patents`. Matches our tracked companies as patent ASSIGNEES and our tracked
drug/target tokens against patent titles + abstracts, for freedom-to-operate and
exclusivity-cliff precision on pipeline (incl. pre-approval) assets.

SOURCE (free, no key, no auth, no CAPTCHA): Google Patents public XHR JSON
    https://patents.google.com/xhr/query?url=<inner-query>&exp=

  Why not PatentsView? Its free no-key legacy API (api.patentsview.org) is
  DECOMMISSIONED (301 -> data.uspto.gov transition guide). The replacement,
  search.patentsview.org, needs a free API key AND was egress-blocked from the
  runner (HTTP 000). Google Patents' public XHR JSON is the working free source.
  This module keeps the requested filename for the caller; the source is honestly
  labelled 'google_patents' everywhere (table, source_payloads, source_url).

DESIGN
  PASS A — assignee-anchored: for each prioritized company, query Google Patents
    by assignee name (recent-first, publication >= 2010). company_id = the queried
    company (resolve-by-construction). Scan title+abstract for drug/target tokens.
  PASS B — target-landscape: for the FTO-core targets (TL1A, IL-23p19, ...), query
    by the target phrase (no assignee), resolve the returned assignee -> a Meridian
    company when possible. matched_target is set by token presence. Catches
    FTO-relevant patents from ANY assignee (kept even if the assignee is untracked,
    because the target resolves into our universe).

RULES (governance)
  * Bronze-first: every raw Google Patents page lands in source_payloads
    (source='google_patents') before silver rows are written.
  * Resolve-or-skip: a row is kept ONLY if company_id OR matched_target OR
    matched_drug_id is non-null. No fabrication of patents/assignees/matches.
  * Idempotent: natural key = patent_number; upsert merge-duplicates => re-run adds 0.
  * SILVER ONLY: does NOT touch entity_edges / strategic_insights.
  * Resumable: each Google Patents page is cached to data/patents_cache/ so a
    re-run (or a wedged-runner retry) skips already-fetched pages.

FAMILY-GRAPH DEPTH (limitation): family_country_codes captures the AGGREGATED family
  jurisdictions Google Patents returns (US/EP/CN/JP/WO ... + active state). That is a
  coarse family signal, NOT a full INPADOC member graph. True families need EPO OPS /
  Lens credentials (absent in this workspace).

USAGE
  python3 scripts/integrations/patentsview_patents.py              # dry-run (default): fetch+build, NO writes
  python3 scripts/integrations/patentsview_patents.py --apply-ddl  # create table v115 via Management API, then dry-run
  python3 scripts/integrations/patentsview_patents.py --write      # fetch + bronze + upsert company_patents
  python3 scripts/integrations/patentsview_patents.py --write --apply-ddl
  Flags: --pages N (per-query pages, default 2), --limit-companies N (cap PASS A), --no-fetch (cache-only)
"""
import json, os, sys, re, time, html, urllib.parse, urllib.request, urllib.error
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REF = "tghntyofptvfhmtchwcv"
REST = f"https://{REF}.supabase.co/rest/v1"
MGMT_URL = f"https://api.supabase.com/v1/projects/{REF}/database/query"
CACHE_DIR = os.path.join(BASE_DIR, "data", "patents_cache")
SESSION = "round14-2026-06-07"
SOURCE = "google_patents"
GP_BASE = "https://patents.google.com/xhr/query"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

DRY = "--write" not in sys.argv
APPLY_DDL = "--apply-ddl" in sys.argv
NO_FETCH = "--no-fetch" in sys.argv
def _argval(flag, default):
    if flag in sys.argv:
        try: return int(sys.argv[sys.argv.index(flag) + 1])
        except Exception: return default
    return default
PAGES = _argval("--pages", 2)
LIMIT_COMPANIES = _argval("--limit-companies", 0)  # 0 = no cap
PUB_AFTER = "20100101"
PUB_BEFORE = "20270101"

os.makedirs(CACHE_DIR, exist_ok=True)

def key(f):
    return open(os.path.join(BASE_DIR, f)).read().strip()
SVC = key(".supabase_service_key")
ANON = key(".supabase_anon_key")

# ─── Supabase helpers ─────────────────────────────────────────────────────────
def sb_get(path):
    rows, off = [], 0
    while True:
        url = f"{REST}/{path}{'&' if '?' in path else '?'}limit=1000&offset={off}"
        req = urllib.request.Request(url, headers={"apikey": ANON, "Authorization": f"Bearer {ANON}"})
        d = json.load(urllib.request.urlopen(req))
        rows += d
        if len(d) < 1000:
            break
        off += 1000
    return rows

def sb_upsert(table, rows, on_conflict):
    if not rows:
        return 0
    url = f"{REST}/{table}?on_conflict={on_conflict}"
    hdr = {"apikey": SVC, "Authorization": f"Bearer {SVC}", "Content-Type": "application/json",
           "Prefer": "resolution=merge-duplicates,return=minimal"}
    n = 0
    for i in range(0, len(rows), 200):
        chunk = rows[i:i+200]
        req = urllib.request.Request(url, data=json.dumps(chunk).encode(), headers=hdr, method="POST")
        try:
            urllib.request.urlopen(req); n += len(chunk)
        except urllib.error.HTTPError as e:
            print("UPSERT ERR", table, e.code, e.read().decode()[:500]); raise
    return n

def sb_insert_new(table, rows):
    """Plain insert (bronze). Ignores rows that violate a unique index (idempotent)."""
    if not rows:
        return 0
    url = f"{REST}/{table}"
    hdr = {"apikey": SVC, "Authorization": f"Bearer {SVC}", "Content-Type": "application/json",
           "Prefer": "return=minimal"}
    n = 0
    for i in range(0, len(rows), 100):
        chunk = rows[i:i+100]
        req = urllib.request.Request(url, data=json.dumps(chunk).encode(), headers=hdr, method="POST")
        try:
            urllib.request.urlopen(req); n += len(chunk)
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code in (409,) or "duplicate" in body.lower():
                continue
            print("BRONZE ERR", table, e.code, body[:300])
    return n

def count(table, filt=""):
    q = f"{REST}/{table}?select=id&limit=1" + (f"&{filt}" if filt else "")
    req = urllib.request.Request(q, headers={"apikey": ANON, "Authorization": f"Bearer {ANON}", "Prefer": "count=exact"})
    return int(urllib.request.urlopen(req).headers["content-range"].split("/")[-1])

def execute_sql(query, label=""):
    pat = key(".supabase_pat")
    hdr = {"Authorization": f"Bearer {pat}", "Content-Type": "application/json",
           "User-Agent": "curl/8.0.1", "Accept": "*/*"}
    req = urllib.request.Request(MGMT_URL, data=json.dumps({"query": query}).encode(), headers=hdr, method="POST")
    try:
        urllib.request.urlopen(req); print(f"  DDL ok: {label}")
    except urllib.error.HTTPError as e:
        print(f"  DDL FAIL {label}: {e.code} {e.read().decode()[:400]}"); raise

# ─── Google Patents fetch (cached, resumable, polite) ─────────────────────────
def gp_fetch(inner_q, cache_key, page=0):
    """Fetch one Google Patents XHR page. Cache to disk; reuse if present."""
    path = os.path.join(CACHE_DIR, f"{cache_key}_p{page}.json")
    if os.path.exists(path) and os.path.getsize(path) > 2:
        with open(path) as f:
            return json.load(f)
    if NO_FETCH:
        return None
    inner = inner_q + (f"&page={page}" if page else "")
    enc = urllib.parse.quote(inner, safe="")
    url = f"{GP_BASE}?url={enc}&exp="
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode())
            with open(path, "w") as f:
                json.dump(data, f)
            time.sleep(1.1)  # polite rate-limit
            return data
        except Exception as e:
            print(f"    fetch retry {attempt+1} ({cache_key} p{page}): {e}")
            time.sleep(2.5 * (attempt + 1))
    return None

def gp_results(data):
    try:
        return data["results"]["cluster"][0]["result"]
    except Exception:
        return []

def gp_total_pages(data):
    try:
        return int(data["results"].get("total_num_pages", 1))
    except Exception:
        return 1

# ─── text helpers ─────────────────────────────────────────────────────────────
def clean(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()

def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def yr(d):
    return int(d[:4]) if d and len(d) >= 4 and d[:4].isdigit() else None

def plus20(filing):
    if not filing or len(filing) < 10:
        return None
    try:
        y, m, d = filing[:4], filing[5:7], filing[8:10]
        return f"{int(y)+20:04d}-{m}-{d}"
    except Exception:
        return None

# ─── reference data ───────────────────────────────────────────────────────────
print("Loading Meridian reference data ...")
companies = sb_get("companies?select=id,name,status")
drugs = sb_get("drugs?select=id,name,brand_name,inn_name,dev_code,target,company_id")
comp_by_id = {c["id"]: c for c in companies}

# Manual assignee aliases where the patent legal entity != our display name.
COMPANY_ASSIGNEE_ALIASES = {
    "jnj": ["johnson & johnson", "janssen"],
    "roche": ["genentech", "hoffmann-la roche", "chugai"],
    "abbvie": ["abbvie"],
    "bms": ["bristol-myers squibb", "bristol myers", "celgene"],
    "lilly": ["eli lilly"],
    "novartis": ["novartis"],
    "sanofi": ["sanofi"],
    "astrazeneca": ["astrazeneca", "medimmune"],
    "merck": ["merck sharp", "merck & co"],
    "regeneron": ["regeneron"],
    "amgen": ["amgen"],
    "pfizer": ["pfizer"],
    "takeda": ["takeda"],
    "gilead": ["gilead"],
    "biogen": ["biogen"],
}

# normalized-assignee-token -> company_id, for PASS B resolution
assignee_index = {}
for c in companies:
    toks = [c["name"]] + COMPANY_ASSIGNEE_ALIASES.get(c["id"], [])
    for t in toks:
        nt = norm(t)
        if len(nt) >= 4:
            assignee_index.setdefault(nt, c["id"])

def resolve_assignee(raw):
    nraw = norm(raw)
    if not nraw:
        return None
    for nt, cid in assignee_index.items():
        if nt in nraw:
            return cid
    return None

# Canonical target tokens (FTO-relevant) -> search variants for title/abstract matching
TARGET_VARIANTS = {
    "TL1A": ["tl1a", "tnf-like ligand 1a", "tnfsf15", "tnf like ligand 1a"],
    "IL-23p19": ["il-23", "il23", "interleukin-23", "interleukin 23", "p19"],
    "TSLP": ["tslp", "thymic stromal lymphopoietin"],
    "FcRn": ["fcrn", "neonatal fc receptor"],
    "IGF-1R": ["igf-1r", "igf1r", "insulin-like growth factor 1 receptor", "insulin like growth factor"],
    "OX40L": ["ox40l", "ox40 ligand", "tnfsf4"],
    "IL-4Rα": ["il-4r", "il4r", "interleukin-4 receptor"],
    "IL-13": ["il-13", "interleukin-13", "interleukin 13"],
    "IL-33": ["il-33", "interleukin-33", "interleukin 33"],
    "α4β7": ["alpha4beta7", "α4β7", "a4b7 integrin"],
    "CD40L": ["cd40l", "cd154", "cd40 ligand"],
    "IL-17A": ["il-17", "il17", "interleukin-17"],
}
def match_targets(text):
    tl = text.lower()
    hits = []
    for canon, variants in TARGET_VARIANTS.items():
        if any(v in tl for v in variants):
            hits.append(canon)
    return hits

# drug-token -> drug_id (distinctive tokens only)
GENERIC = {"anti", "antibody", "antibodies", "human", "humanized", "bispecific", "fusion",
           "protein", "receptor", "inhibitor", "agonist", "monoclonal", "therapy", "therapeutic"}
drug_token_index = {}
for d in drugs:
    for fld in ("dev_code", "inn_name", "brand_name", "name"):
        v = d.get(fld)
        if not v:
            continue
        t = v.strip().lower()
        if len(t) >= 4 and t not in GENERIC and not t.startswith("—"):
            # keep alnum tokens (dev codes like alx001) or distinct INNs (ending -mab/-nib/...)
            if re.match(r"^[a-z]{2,}[- ]?\d", t) or re.search(r"(mab|nib|cept|stat|sen|llo|mab)\b", t) or len(t.split()) == 1:
                drug_token_index.setdefault(t, d["id"])
def match_drugs(text):
    tl = " " + text.lower() + " "
    hits = []
    for tok, did in drug_token_index.items():
        if re.search(r"(?<![a-z0-9])" + re.escape(tok) + r"(?![a-z0-9])", tl):
            hits.append(did)
    return hits

# Prioritized company set = those with a tracked drug in a core target area.
CORE_TARGET_KEYS = ["tl1a", "il-23", "il23", "tslp", "fcrn", "igf-1r", "ox40", "il-4r",
                    "il-13", "il-33", "α4β7", "a4b7", "cd40", "jak"]
def is_core_target(t):
    t = (t or "").lower()
    return any(k in t for k in CORE_TARGET_KEYS)
core_company_ids = sorted({d["company_id"] for d in drugs
                           if d.get("company_id") and is_core_target(d.get("target"))})
if LIMIT_COMPANIES:
    core_company_ids = core_company_ids[:LIMIT_COMPANIES]
print(f"  companies={len(companies)} drugs={len(drugs)} "
      f"core-assignee-companies={len(core_company_ids)} drug-tokens={len(drug_token_index)}")

# ─── DDL ──────────────────────────────────────────────────────────────────────
if APPLY_DDL and not DRY:
    sql = open(os.path.join(BASE_DIR, "migrations", "v115_company_patents.sql")).read()
    # strip the rollback comment block tail is harmless; send whole file
    execute_sql(sql, "v115 company_patents")
    execute_sql("NOTIFY pgrst, 'reload schema';", "reload schema")

# ─── build silver rows ────────────────────────────────────────────────────────
# accumulator keyed by patent_number; merge across passes
acc = {}          # patent_number -> row dict
bronze = []       # source_payloads rows
seen_cache = set()

def ingest(patent, queried_company=None, method="assignee_query", landscape_target=None):
    pub = patent.get("publication_number")
    if not pub:
        return
    title = clean(patent.get("title"))
    snip = clean(patent.get("snippet"))
    text = f"{title} {snip}"
    assignee = clean(patent.get("assignee"))
    grant = patent.get("grant_date") or None
    filing = patent.get("filing_date") or None
    pubdate = patent.get("publication_date") or None
    prio = patent.get("priority_date") or None

    # resolution
    company_id = queried_company or resolve_assignee(assignee)
    tgt_hits = match_targets(text)
    if landscape_target and landscape_target not in tgt_hits:
        tgt_hits.append(landscape_target)
    drug_hits = match_drugs(text)
    matched_target = tgt_hits[0] if tgt_hits else None
    matched_drug = drug_hits[0] if drug_hits else None

    # resolve-or-skip
    if not (company_id or matched_target or matched_drug):
        return

    # family country codes (coarse family signal)
    fam = []
    try:
        for cs in patent.get("family_metadata", {}).get("aggregated", {}).get("country_status", []):
            cc = cs.get("country_code")
            if cc and cc not in fam:
                fam.append(cc)
    except Exception:
        pass

    # confidence (company attribution)
    if company_id and norm(assignee) and any(
            nt in norm(assignee) for nt, cid in assignee_index.items() if cid == company_id):
        conf = "confirmed"
    elif company_id and queried_company:
        conf = "inferred"          # assignee-name search matched but raw string didn't token-confirm (e.g. localized)
    elif company_id:
        conf = "confirmed"
    else:
        conf = "unverified"        # target/drug hit, assignee not in our universe (still FTO-relevant)

    gp_id = None
    # patent.get id is on the wrapper, not patent dict; reconstruct
    gp_id = f"patent/{pub}/en"
    row = {
        "patent_number": pub,
        "patent_id": gp_id,
        "patent_title": title[:500] if title else None,
        "patent_date": grant or pubdate,
        "grant_date": grant,
        "filing_date": filing,
        "priority_date": prio,
        "publication_date": pubdate,
        "grant_year": yr(grant),
        "expiry_estimate": plus20(filing),
        "assignee_org": assignee[:300] if assignee else None,
        "company_id": company_id,
        "matched_drug_id": matched_drug,
        "matched_target": matched_target,
        "family_country_codes": fam or None,
        "source": SOURCE,
        "source_url": f"https://patents.google.com/patent/{pub}/en",
        "match_method": method,
        "confidence": conf,
        "session_label": SESSION,
        "fetched_at": None,
    }
    prev = acc.get(pub)
    if prev:
        # merge: keep a non-null company_id, union target/drug, mark both methods
        if not prev.get("company_id") and company_id:
            prev["company_id"] = company_id
            prev["confidence"] = conf
        prev["matched_target"] = prev.get("matched_target") or matched_target
        prev["matched_drug_id"] = prev.get("matched_drug_id") or matched_drug
        if prev.get("match_method") != method:
            prev["match_method"] = "both"
    else:
        acc[pub] = row

def run_query(inner_q, cache_key, pages, queried_company=None, method="assignee_query", landscape_target=None):
    first = gp_fetch(inner_q, cache_key, 0)
    if not first:
        return 0
    n_pages = min(pages, gp_total_pages(first))
    fetched = 0
    for pg in range(n_pages):
        data = first if pg == 0 else gp_fetch(inner_q, cache_key, pg)
        if not data:
            break
        # bronze: store the raw page once
        ck = f"{cache_key}_p{pg}"
        if ck not in seen_cache:
            seen_cache.add(ck)
            bronze.append({
                "source": SOURCE, "entity_type": ("company" if queried_company else "target"),
                "meridian_id": queried_company or landscape_target,
                "external_id": cache_key, "endpoint": "xhr/query",
                "payload": data, "session_label": SESSION,
            })
        for r in gp_results(data):
            ingest(r.get("patent", {}), queried_company=queried_company,
                   method=method, landscape_target=landscape_target)
            fetched += 1
    return fetched

# PASS A — assignee-anchored over core companies
print(f"\nPASS A — assignee-anchored ({len(core_company_ids)} companies, {PAGES} page(s) each) ...")
for cid in core_company_ids:
    name = comp_by_id.get(cid, {}).get("name", cid)
    inner = (f"assignee={name}&country=US,WO,EP&type=PATENT"
             f"&before=publication:{PUB_BEFORE}&after=publication:{PUB_AFTER}&sort=new")
    ck = "assignee_" + re.sub(r"[^a-z0-9]+", "-", cid.lower())
    got = run_query(inner, ck, PAGES, queried_company=cid, method="assignee_query")
    print(f"  {cid:<18} {name[:30]:<30} results~{got}")

# PASS B — target-landscape for the FTO-core targets
LANDSCAPE_TARGETS = {
    "TL1A": "TL1A",
    "IL-23p19": "IL-23 p19",
    "TSLP": "TSLP",
    "FcRn": "FcRn neonatal Fc receptor",
}
print(f"\nPASS B — target-landscape ({len(LANDSCAPE_TARGETS)} targets, {PAGES} page(s) each) ...")
for canon, phrase in LANDSCAPE_TARGETS.items():
    inner = (f"q={phrase}&country=US,WO,EP&type=PATENT"
             f"&before=publication:{PUB_BEFORE}&after=publication:{PUB_AFTER}&sort=new")
    ck = "target_" + re.sub(r"[^a-z0-9]+", "-", canon.lower())
    got = run_query(inner, ck, PAGES, method="target_landscape", landscape_target=canon)
    print(f"  {canon:<12} results~{got}")

# ─── summary ──────────────────────────────────────────────────────────────────
rows = list(acc.values())
with_company = [r for r in rows if r.get("company_id")]
with_target = [r for r in rows if r.get("matched_target")]
with_drug = [r for r in rows if r.get("matched_drug_id")]
tl1a_il23 = [r for r in rows if r.get("matched_target") in ("TL1A", "IL-23p19")]

from collections import Counter
by_company = Counter(r["company_id"] for r in with_company)

print("\n" + "=" * 70)
print(f"BUILD SUMMARY  ({'DRY-RUN' if DRY else 'WRITE'})")
print(f"  patents fetched (pages cached) : {len(seen_cache)} pages")
print(f"  unique patents kept (resolved) : {len(rows)}")
print(f"  -> matched to a tracked company: {len(with_company)}")
print(f"  -> matched a target token      : {len(with_target)}")
print(f"  -> matched a drug token        : {len(with_drug)}")
print(f"  -> TL1A / IL-23p19 (FTO core)  : {len(tl1a_il23)}")
print(f"  bronze pages to land           : {len(bronze)}")
print("\n  Top assignees among our companies (by patent count):")
for cid, n in by_company.most_common(15):
    print(f"    {n:>4}  {cid:<18} {comp_by_id.get(cid,{}).get('name','')[:32]}")
print("\n  Sample TL1A / IL-23p19 hits:")
for r in tl1a_il23[:12]:
    print(f"    {r['patent_number']:<16} {r.get('matched_target'):<9} "
          f"{(r.get('company_id') or '—'):<14} exp~{r.get('expiry_estimate')}  {(r.get('patent_title') or '')[:46]}")

# ─── write ────────────────────────────────────────────────────────────────────
if DRY:
    print("\nDRY-RUN: no writes. Re-run with --write (and --apply-ddl on first run).")
    sys.exit(0)

print("\nWriting bronze -> source_payloads ...")
# idempotent bronze: source_payloads has no unique key, so skip pages already landed
# for this source (check-then-insert on source+external_id, like the other integrations).
existing_bronze = {r.get("external_id") for r in
                   sb_get(f"source_payloads?select=external_id&source=eq.{SOURCE}")}
bronze_new = [b for b in bronze if b.get("external_id") not in existing_bronze]
nb = sb_insert_new("source_payloads", bronze_new)
print(f"  bronze pages new: {nb} (skipped {len(bronze)-len(bronze_new)} already landed)")

print("Upserting silver -> company_patents (on_conflict=patent_number) ...")
nw = sb_upsert("company_patents", rows, "patent_number")
print(f"  rows upserted: {nw}")
try:
    total = count("company_patents")
    print(f"  company_patents total rows now: {total}")
except Exception as e:
    print(f"  (count failed: {e})")
print("Done.")
