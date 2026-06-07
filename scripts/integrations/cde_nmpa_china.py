#!/usr/bin/env python3
"""
CDE / NMPA China clinical-trial registry integration.

Source: https://www.chinadrugtrials.org.cn  (药物临床试验登记与信息公示平台)
The site sits behind a Riversafe (瑞数) "Botgate" dynamic JS anti-bot WAF. Plain
curl/urllib gets HTTP 202 + an obfuscated JS challenge. A headless Chromium
(Playwright) executes the challenge JS on the index page, which sets the
FSSBBIl1UgzbN7N80S/T cookies, after which the search endpoints return real data.

Search mechanism (reverse-engineered):
  - Page /clinicaltrials.searchlist.dhtml hosts form #searchfrm (POST).
  - Fields: keywords (broad), drugs_name (药物名称), appliers (申请人/sponsor),
    indication, reg_no, ...
  - JS fn searchList() sets currentpage=1 and submits #searchfrm.
  - Results render as a table; each row -> CTR registration number + status +
    Chinese drug name + indication + title, with a detail-page link.

Design: bronze-first, idempotent, resolve-or-skip, sourced.
  - Raw search payloads -> source_payloads (source='cde_nmpa'), deduped by hash.
  - Confident drug matches -> china_trials (upsert on trial_id).
  - A trial is a CONFIDENT match for an asset only when one of that asset's
    dev-code variants appears verbatim (hyphen/case-insensitive) in the trial's
    drug name or title. Sponsor-only enumeration is logged but never blindly
    promoted (resolve-or-skip).

Resumable: every search result is cached to disk; re-running adds 0. A wall-clock
budget (--budget) lets each invocation make progress within the runner timeout.

Usage:
  python3 cde_nmpa_china.py            # dry-run (no writes), default
  python3 cde_nmpa_china.py --write    # upsert source_payloads + china_trials
  python3 cde_nmpa_china.py --budget 30 --refresh   # re-fetch, 30s/invocation
"""
import argparse, json, hashlib, os, re, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CACHE_DIR = os.path.join(HERE, ".cde_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

SUPA = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
SESSION_LABEL = "cde_nmpa_china_2026-06-07"
BASE = "https://www.chinadrugtrials.org.cn"
INDEX = BASE + "/index.html"
SEARCH = BASE + "/clinicaltrials.searchlist.dhtml"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

def svc_key():
    # Prefer env (GitHub Actions runner: SUPABASE_SERVICE_KEY / SUPABASE_ANON_KEY),
    # fall back to local key files for local/dev usage. Never break either path.
    for var in ("SUPABASE_SERVICE_KEY", "SUPABASE_ANON_KEY"):
        v = os.environ.get(var)
        if v and v.strip():
            return v.strip()
    for fn in (".supabase_service_key", ".supabase_anon_key"):
        p = os.path.join(ROOT, fn)
        if os.path.exists(p):
            with open(p) as f:
                k = f.read().strip()
                if k:
                    return k
    raise RuntimeError(
        "No Supabase key found: set SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY) "
        "in env, or provide .supabase_service_key in the repo root.")

# --- target assets: pulled live from drugs; fallback to hardcoded canonical set
FALLBACK_TARGETS = [
    {"id": "lq080",   "name": "LQ080",   "company_id": "novamab",       "aliases": []},
    {"id": "lq082",   "name": "LQ082",   "company_id": "novamab",       "aliases": []},
    {"id": "sim0709", "name": "SIM0709", "company_id": "simcere",       "aliases": []},
    {"id": "shr0817", "name": "SHR0817", "company_id": "hengrui",       "aliases": []},
    {"id": "zl-2411", "name": "ZL-2411", "company_id": "zailab",        "aliases": []},
    {"id": "hlx36",   "name": "HLX36",   "company_id": "henlius",       "aliases": []},
    {"id": "es302",   "name": "ES302",   "company_id": "elpiscience",   "aliases": ["ES-302"]},
    {"id": "hbm2001", "name": "HBM2001", "company_id": "harbourbiomed", "aliases": []},
    {"id": "lbl053",  "name": "LBL-053", "company_id": "leads",         "aliases": ["LBL053"]},
    {"id": "qx030n",  "name": "QX030N",  "company_id": "qyuns",         "aliases": ["CLD-423"]},
]

# Chinese sponsor short-names (简称). ONLY high-confidence names included; the
# match gate still requires a verbatim dev-code, so an imperfect sponsor name
# only affects recall, never correctness.
SPONSOR_CN = {
    "hengrui": "恒瑞",
    "simcere": "先声",
    "zailab": "再鼎医药",
    "henlius": "复宏汉霖",
    "harbourbiomed": "和铂医药",
    "leads": "维立志博",
    "qyuns": "荃信",
    # novamab / elpiscience Chinese short-names unverified -> rely on code search
}

def code_variants(code):
    """Generate hyphen/case variants for matching, e.g. SHR0817 -> {SHR0817, SHR-0817}."""
    c = code.strip()
    out = {c, c.replace("-", ""), c.upper(), c.replace("-", "").upper()}
    # insert a hyphen at the letter->digit boundary
    m = re.match(r"^([A-Za-z]+)[- ]?(\d.*)$", c)
    if m:
        out.add(f"{m.group(1)}-{m.group(2)}")
        out.add(f"{m.group(1)}{m.group(2)}")
    return {v for v in out if v}

def norm(s):
    return re.sub(r"[\s\-]", "", (s or "")).upper()

# ---------------- Supabase helpers ----------------
def sb_get(path):
    req = urllib.request.Request(SUPA + path, headers={
        "apikey": svc_key(), "Authorization": "Bearer " + svc_key()})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def sb_write(table, rows, on_conflict=None):
    if not rows:
        return 0
    url = SUPA + "/" + table
    if on_conflict:
        url += "?on_conflict=" + on_conflict
    body = json.dumps(rows).encode()
    headers = {"apikey": svc_key(), "Authorization": "Bearer " + svc_key(),
               "Content-Type": "application/json",
               "Prefer": "resolution=merge-duplicates,return=minimal"}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return len(rows) if r.status in (200, 201, 204) else 0
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"[sb_write {table}] {e.code}: {e.read().decode()[:300]}\n")
        raise

def load_targets():
    try:
        ids = ",".join(t["id"] for t in FALLBACK_TARGETS)
        rows = sb_get(f"/drugs?select=id,name,aliases,company_id&id=in.({ids})")
        if rows:
            return [{"id": r["id"], "name": r["name"],
                     "company_id": r.get("company_id"),
                     "aliases": r.get("aliases") or []} for r in rows]
    except Exception as e:
        sys.stderr.write(f"[load_targets] DB fetch failed, using fallback: {e}\n")
    return FALLBACK_TARGETS

# ---------------- Playwright search ----------------
def cache_path(term):
    h = hashlib.sha1(term.encode()).hexdigest()[:16]
    return os.path.join(CACHE_DIR, f"{h}.json")

def cached(term):
    p = cache_path(term)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return None

def store_cache(term, data):
    with open(cache_path(term), "w") as f:
        json.dump(data, f, ensure_ascii=False)

def parse_rows(page):
    """Extract structured trial rows from the rendered results table."""
    return page.evaluate(r"""() => {
      const rows = [];
      document.querySelectorAll('table tr').forEach(tr => {
        const a = tr.querySelector('a[href*="searchlistdetail"], a[href*="clinicaltrials"]');
        const txt = tr.innerText || '';
        const m = txt.match(/CTR\d{8}/);
        if (!m) return;
        const cells = [...tr.querySelectorAll('td')].map(td => (td.innerText||'').trim());
        let href = a ? a.getAttribute('href') : null;
        if (href && href.startsWith('/')) href = 'https://www.chinadrugtrials.org.cn' + href;
        rows.push({ctr: m[0], cells: cells, detail: href, raw: txt.replace(/\s+/g,' ').trim()});
      });
      return rows;
    }""")

def total_count(page):
    body = page.inner_text("body")
    m = re.search(r"共\s*(\d+)\s*条", body)
    return int(m.group(1)) if m else None

def run_search(page, field, value):
    page.evaluate("""([f,v])=>{
      const frm=document.getElementById('searchfrm');
      ['keywords','reg_no','indication','case_no','drugs_name','appliers',
       'communities','researchers','agencies'].forEach(n=>{
         const el=frm.querySelector('[name='+n+']'); if(el) el.value='';});
      const el=frm.querySelector('[name='+f+']'); if(el) el.value=v;
    }""", [field, value])
    page.evaluate("()=>searchList()")
    page.wait_for_timeout(3000)
    return {"total": total_count(page), "rows": parse_rows(page)}

def bootstrap(page):
    page.goto(INDEX, wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(3800)  # let Riversafe JS set cookies
    page.goto(SEARCH, wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(2500)

# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="ignore cache, re-fetch")
    ap.add_argument("--budget", type=float, default=28.0,
                    help="wall-clock seconds of fetching per invocation (runner-safe)")
    ap.add_argument("--sponsor", action="store_true",
                    help="also enumerate by sponsor short-name (recall, logged-only)")
    args = ap.parse_args()

    targets = load_targets()
    # Build search plan: per asset, keyword searches over all code variants.
    plan = []  # (term, field, asset)
    for t in targets:
        codes = set()
        codes |= code_variants(t["name"])
        for a in (t.get("aliases") or []):
            codes |= code_variants(a)
        t["_match"] = {norm(c) for c in codes}
        for c in sorted(codes):
            plan.append((c, "keywords", t))
    sponsor_plan = []
    if args.sponsor:
        seen = set()
        for t in targets:
            cn = SPONSOR_CN.get(t["company_id"])
            if cn and cn not in seen:
                seen.add(cn)
                sponsor_plan.append((cn, "appliers", t["company_id"]))

    # What still needs fetching?
    def needs(term):
        return args.refresh or cached(term) is None
    todo = [(term, f, ctx) for (term, f, ctx) in plan + sponsor_plan if needs(term)]

    fetched_now = 0
    if todo:
        from playwright.sync_api import sync_playwright
        deadline = time.time() + args.budget
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True, args=[
                "--no-sandbox", "--disable-blink-features=AutomationControlled"])
            ctx = b.new_context(user_agent=UA, locale="zh-CN")
            pg = ctx.new_page()
            bootstrap(pg)
            for term, field, _ in todo:
                if time.time() > deadline:
                    print(f"[budget] stopping; {len([1 for tt,_,_ in todo if cached(tt) is None])} terms remain")
                    break
                try:
                    res = run_search(pg, field, term)
                    res["_term"] = term
                    res["_field"] = field
                    res["_fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    store_cache(term, res)
                    fetched_now += 1
                    print(f"[fetch] {field}={term} total={res['total']} rows={len(res['rows'])}")
                except Exception as e:
                    print(f"[fetch] {field}={term} ERROR {e}")
            b.close()
    else:
        print("[cache] all search terms cached; nothing to fetch")

    # ---- Match + assemble writes from cache ----
    payload_rows = []
    trial_rows = []
    per_asset = {t["id"]: {"name": t["name"], "matched": [], "searched": 0, "blocked": 0} for t in targets}
    seen_payload_hash = set()

    asset_evidence = {}  # id -> {terms:[], totals:[], rows:[]}
    for term, field, t in plan:
        c = cached(term)
        if c is None:
            continue
        per_asset[t["id"]]["searched"] += 1
        ev = asset_evidence.setdefault(t["id"], {"terms": [], "rows": []})
        ev["terms"].append({"term": term, "field": field, "total": c.get("total"),
                            "row_count": len(c.get("rows", []))})
        ev["rows"].extend(c.get("rows", []))
        # confident match gate: dev-code variant appears verbatim in row text
        for r in c.get("rows", []):
            hay = norm(r.get("raw", "")) + norm(" ".join(r.get("cells", [])))
            if any(mc and mc in hay for mc in t["_match"]):
                cells = r.get("cells", [])
                status = next((x for x in cells if any(k in x for k in ("招募", "进行中", "已完成", "暂停", "终止"))), None)
                drug_cn = next((x for x in cells if re.search(r"[一-鿿]", x) and len(x) < 60 and x != status), None)
                trial_rows.append({
                    "trial_id": r["ctr"], "registry": "CDE_NMPA",
                    "drug_id": t["id"], "matched_term": term,
                    "public_title": r.get("raw", "")[:500],
                    "scientific_title": None,
                    "condition": None,
                    "intervention": drug_cn,
                    "sponsor": SPONSOR_CN.get(t["company_id"]) or t["company_id"],
                    "recruitment_status": status,
                    "registration_date": None,
                    "source_url": r.get("detail") or SEARCH,
                    "session_label": SESSION_LABEL,
                })
                if r["ctr"] not in [m["ctr"] for m in per_asset[t["id"]]["matched"]]:
                    per_asset[t["id"]]["matched"].append({"ctr": r["ctr"], "via": term})

    # One bronze evidence row per asset documenting the CDE gap-check (incl. true
    # negatives). This makes "we searched CDE for asset X on DATE -> N results"
    # a sourced, idempotent fact rather than something living only in chat.
    for t in targets:
        ev = asset_evidence.get(t["id"])
        if not ev:
            continue
        body = {"asset": t["name"], "company_id": t["company_id"],
                "searched_terms": ev["terms"],
                "confident_matches": [m["ctr"] for m in per_asset[t["id"]]["matched"]],
                "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "note": ("dev-code not registered in CDE/NMPA under any code variant"
                         if not per_asset[t["id"]]["matched"] else "matched via dev-code")}
        ph = hashlib.sha256((t["id"] + json.dumps(ev["terms"], sort_keys=True)).encode()).hexdigest()
        payload_rows.append({
            "source": "cde_nmpa", "entity_type": "drug",
            "meridian_id": t["id"], "external_id": t["name"],
            "endpoint": SEARCH,
            "payload": body, "payload_hash": ph[:48],
            "session_label": SESSION_LABEL,
        })

    # dedupe trial_rows by trial_id (keep first)
    seen = set(); uniq_trials = []
    for tr in trial_rows:
        if tr["trial_id"] in seen:
            continue
        seen.add(tr["trial_id"]); uniq_trials.append(tr)

    print("\n=== PER-ASSET RESULT ===")
    for t in targets:
        a = per_asset[t["id"]]
        status = "FOUND" if a["matched"] else ("SEARCHED-NO-MATCH" if a["searched"] else "PENDING-FETCH")
        print(f"  {t['name']:<9} ({t['company_id']:<14}) {status:<18} matched={[m['ctr'] for m in a['matched']]}")

    print(f"\nsource_payloads to write: {len(payload_rows)}")
    print(f"china_trials (confident, unique) to write: {len(uniq_trials)}")
    for tr in uniq_trials:
        print(f"   {tr['trial_id']}  drug={tr['drug_id']}  via={tr['matched_term']}  {tr['source_url']}")

    if args.write:
        # idempotent: skip source_payloads whose hash already exists (no unique
        # constraint assumed on the table, so dedupe in the client).
        existing = set()
        try:
            for r in sb_get("/source_payloads?source=eq.cde_nmpa&select=payload_hash"):
                existing.add(r.get("payload_hash"))
        except Exception:
            pass
        fresh = [p for p in payload_rows if p["payload_hash"] not in existing]
        n1 = sb_write("source_payloads", fresh) if fresh else 0
        n2 = sb_write("china_trials", uniq_trials, on_conflict="trial_id") if uniq_trials else 0
        print(f"\n[WRITE] source_payloads +{n1} (skipped {len(payload_rows)-len(fresh)} existing), china_trials +{n2}")
    else:
        print("\n[DRY-RUN] no writes. pass --write to persist.")

if __name__ == "__main__":
    main()
