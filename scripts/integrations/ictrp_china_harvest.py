#!/usr/bin/env python3
"""
WHO ICTRP — China-trial harvest (hosted-runner edition)
=======================================================
Round 11 proved the path is viable but the throttled shared VM could not finish
(WHO portal returns HTTP 000 / Akamai blocks under load). This version is built to
run on a GitHub-hosted runner with CLEAN EGRESS and up to 6h of wall-clock.

What it does (all idempotent, never fabricates):
  1. Targeted intervention search on trialsearch.who.int (AdvSearch.aspx, the
     legitimate public portal feature) for each of our China-developed TL1A / IL-23
     assets that are invisible to ClinicalTrials.gov  ->  WHO/ChiCTR trial ids.
  2. For each id, fetch the detail page (Trial2.aspx?TrialID=...) and parse the
     structured fields (titles, condition, intervention, sponsor, status, dates).
  3. Land the raw detail HTML/parse as bronze in `source_payloads`
     (source='who_ictrp').
  4. Match the intervention/title text to our `drugs` (resolve-or-skip) and upsert
     matched China trials into `china_trials` (DDL: migrations/v_china_trials.sql).

Egress hygiene: descriptive UA + contact, polite rate-limit, retry-with-backoff,
public data only — no auth, no CAPTCHA bypass. A blocked/empty source is a
documented gap, not an error.

Env:  SUPABASE_URL, SUPABASE_SERVICE_KEY
Run:  python3 scripts/integrations/ictrp_china_harvest.py --dry-run
      python3 scripts/integrations/ictrp_china_harvest.py --limit 5
"""
import os, re, sys, json, time, hashlib, argparse
import urllib.request, urllib.parse, urllib.error, http.cookiejar
from datetime import datetime, timezone

UA = "Mozilla/5.0 (Meridian-BD-Research; +https://github.com/kyleklaassen-dev/bd-dashboard; contact kyleklaassen2@gmail.com)"
BASE = "https://trialsearch.who.int"
ADV = f"{BASE}/AdvSearch.aspx"
DETAIL = f"{BASE}/Trial2.aspx?TrialID="          # canonical WHO detail page
DETAIL_ALT = f"{BASE}/Trial3.aspx?trialid="      # legacy alias (round-11 path)
SESSION = f"ictrp-china-{datetime.now(timezone.utc):%Y%m%d}"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# China-developed TL1A / IL-23 assets invisible to CT.gov (drug_id -> search terms).
# Seeded from round-11; the live drug-match step still resolves against the DB so a
# stale code here never invents a row.
TARGETS = {
    "lq080": ["LQ080"], "lq082": ["LQ082"], "sim0709": ["SIM0709"],
    "pr203": ["BA2201", "PR203"], "zl-2411": ["ZL-2411"], "es302": ["ES302"],
    "hy8931": ["HY8931"], "ear-2001": ["HXN-1001"], "hxn-1002": ["HXN-1002"],
    "erd-1": ["HXN-1003"], "hbm2001": ["HBM2001"], "lbl053": ["LBL-053"],
    "sab06": ["SAB06"], "qx030n": ["QX030N"], "shr0817": ["SHR0817"],
}

# ----------------------------------------------------------------------------- HTTP
def _opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def _retry(fn, *a, tries=4, base=2.0, **k):
    last = None
    for i in range(tries):
        try:
            return fn(*a, **k)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                ConnectionError, OSError) as e:
            last = e
            time.sleep(base * (2 ** i))
    raise last

def _get(op, url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with op.open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def _post(op, url, data, referer, timeout=40):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
        "Referer": referer, "Origin": BASE,
    })
    with op.open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def _hidden(html, name):
    m = (re.search(rf'id="{name}"[^>]*value="([^"]*)"', html) or
         re.search(rf'name="{name}"[^>]*value="([^"]*)"', html))
    return m.group(1) if m else ""

# --------------------------------------------------------------------------- search
def search_intervention(op, term):
    """ASP.NET WebForms POST against the public AdvSearch portal. Returns trial ids."""
    form = _retry(_get, op, ADV)
    data = {
        "__EVENTTARGET": "", "__EVENTARGUMENT": "",
        "__VIEWSTATE": _hidden(form, "__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": _hidden(form, "__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": _hidden(form, "__EVENTVALIDATION"),
        "ctl00$ContentPlaceHolder1$txtCondition": "",
        "ctl00$ContentPlaceHolder1$ddlOperatorCondition": "AND",
        "ctl00$ContentPlaceHolder1$txtIntervention": term,
        "ctl00$ContentPlaceHolder1$ddlOperatorIntervention": "AND",
        "ctl00$ContentPlaceHolder1$ddlTitle": "0",
        "ctl00$ContentPlaceHolder1$ddlRecruitingStatus": "",
        "ctl00$ContentPlaceHolder1$txtDateStart": "",
        "ctl00$ContentPlaceHolder1$txtDateEnd": "",
        "ctl00$ContentPlaceHolder1$btnSearch": "Search",
    }
    if _hidden(form, "__VIEWSTATEENCRYPTED"):
        data["__VIEWSTATEENCRYPTED"] = ""
    res = _retry(_post, op, ADV, data, ADV)
    # --- false-OK guard --------------------------------------------------------
    # The WHO search back-end has been server-broken (round 14): the POST either
    # 302-redirects to NoAccess.aspx, hangs, or silently bounces back the empty
    # AdvSearch form (same page, 0 results). None of these is a real "0 hits"
    # answer, so we must NOT report them as a successful search. Detect them and
    # raise SearchBlocked so the caller counts them as `blocked`, not `searched_ok`.
    if _search_is_blocked(res):
        raise SearchBlocked("search endpoint returned NoAccess / bounce-back form (no results table)")
    ids = sorted(set(re.findall(r'[Tt]rial[Ii][Dd]=([A-Za-z0-9/\-]+)', res)))
    cm = re.search(r'(\d+)\s+record', res, re.I)
    return ids, (cm.group(1) if cm else None)


class SearchBlocked(Exception):
    """Raised when the WHO search endpoint is unreachable/broken (not a real 0-hit)."""


def _search_is_blocked(res):
    """True when the search response is NOT a genuine results page.

    Treats as blocked: the NoAccess redirect, an explicit 'temporarily unavailable'
    notice, or the AdvSearch *form* bounced straight back (the broken-search
    signature: the Advanced-Search form title is present AND there is neither a
    results table / TrialID link nor a stated record count)."""
    if not res or len(res) < 500:
        return True
    low = res.lower()
    if "noaccess" in low or "temporarily unavailable" in low or "access denied" in low:
        return True
    has_results = bool(re.search(r'[Tt]rial[Ii][Dd]=', res)) or bool(re.search(r'\d+\s+record', res, re.I))
    is_form = "advanced search" in low or "advsearch" in low
    # bounced back to the empty search form with nothing to show -> broken, not 0-hit
    if is_form and not has_results:
        return True
    return False


def _span(html, *fields):
    """Extract a value from the WHO ICTRP detail page.

    The real Trial2.aspx markup stores every field in an ASP.NET span whose id ends
    in '_<Field>Label', e.g. <span id="DataList3_ctl01_Public_titleLabel">...</span>.
    The DataListN prefix varies by record, so match on the field suffix only."""
    for f in fields:
        m = re.search(rf'<span id="[^"]*_{f}Label"[^>]*>(.*?)</span>', html, re.S | re.I)
        if m:
            val = re.sub(r'<[^>]+>', ' ', m.group(1))
            val = re.sub(r'\s+', ' ', val).strip()
            if val:
                return val
    return None

def fetch_detail(op, trial_id):
    """Fetch + parse one WHO ICTRP detail page. Returns (parsed_dict, raw_html, url)."""
    tid = urllib.parse.quote(trial_id, safe="")
    for url in (DETAIL + tid, DETAIL_ALT + tid):
        try:
            html = _retry(_get, op, url, tries=3)
        except Exception:
            continue
        if not html or len(html) < 500 or "noaccess" in html.lower():
            continue
        # confirm this is a real trial record, not an error/empty shell
        if not re.search(r'_TrialIDLabel"', html) and trial_id not in html:
            continue
        parsed = {
            "trial_id": _span(html, "TrialID") or trial_id,
            "registry": _span(html, "Description", "Source_Register") or ("ChiCTR" if "ChiCTR" in trial_id else None),
            "public_title": _span(html, "Public_title"),
            "scientific_title": _span(html, "Scientific_title"),
            "condition": _span(html, "Condition_FreeText", "Condition"),
            "intervention": _span(html, "Intervention_FreeText", "Intervention"),
            "sponsor": _span(html, "Primary_sponsor", "Sponsor"),
            "recruitment_status": _span(html, "Recruitment_status"),
            "registration_date": _span(html, "Date_registration"),
            "source_url": url,
        }
        return parsed, html, url
    return None, None, DETAIL + tid

# ------------------------------------------------------------------------- supabase
class SB:
    def __init__(self):
        self.url = os.environ["SUPABASE_URL"].rstrip("/")
        self.key = os.environ["SUPABASE_SERVICE_KEY"]
    def _req(self, method, path, body=None, prefer=None):
        url = f"{self.url}/rest/v1/{path}"
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}",
                   "Content-Type": "application/json"}
        if prefer:
            headers["Prefer"] = prefer
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()
    def get(self, path):
        _, d = self._req("GET", path)
        return d or []
    def insert(self, table, rows, prefer="return=representation,resolution=merge-duplicates"):
        return self._req("POST", table, rows, prefer=prefer)

def load_drug_index(sb):
    """Build normalized term -> drug_id map across name/display/brand/aliases/code."""
    rows = sb.get("drugs?select=id,name,display_name,brand_name,aliases,inn_name,dev_code")
    idx = {}
    def norm(s):
        return re.sub(r'[^a-z0-9]', '', (s or "").lower())
    for d in rows:
        did = d["id"]
        terms = [d.get("name"), d.get("display_name"), d.get("brand_name"),
                 d.get("inn_name"), d.get("dev_code"), did]
        al = d.get("aliases")
        if isinstance(al, list):
            terms += al
        for t in terms:
            n = norm(t)
            if n and len(n) >= 4:           # avoid noise from tiny tokens
                idx.setdefault(n, did)
    return idx, len(rows)

def match_drug(idx, parsed):
    """resolve-or-skip: return drug_id + matched_term, or (None, None)."""
    hay = " ".join(filter(None, [parsed.get("intervention"),
                                 parsed.get("public_title"),
                                 parsed.get("scientific_title")]))
    hnorm = re.sub(r'[^a-z0-9]', '', hay.lower())
    if not hnorm:
        return None, None
    # longest terms first so 'shr0817' wins over 'shr'
    for term in sorted(idx, key=len, reverse=True):
        if term in hnorm:
            return idx[term], term
    return None, None

# --------------------------------------------------------------- detail -> rows
def process_trial_id(op, tid, drug_idx, seed_did, bronze_rows, china_rows,
                     seen_ids, sleep=2.0):
    """Fetch one ICTRP detail page, land bronze, resolve-or-skip into china_rows.
    Returns 1 if the detail page parsed, else 0."""
    if tid in seen_ids:
        return 0
    seen_ids.add(tid)
    parsed, raw, url = fetch_detail(op, tid)
    time.sleep(sleep)
    if not parsed:
        return 0
    payload_hash = hashlib.md5((raw or json.dumps(parsed)).encode()).hexdigest()
    bronze_rows.append({
        "source": "who_ictrp_detail", "entity_type": "trial",
        "meridian_id": seed_did, "external_id": tid,
        "endpoint": "trial_detail", "payload": parsed,
        "payload_hash": payload_hash, "session_label": SESSION,
        "promoted": False,
    })
    mdid, mterm = match_drug(drug_idx, parsed) if drug_idx else (None, None)
    # bias toward the asset we seeded for, but only if it is a real drug id
    if not mdid and seed_did and seed_did in (drug_idx.values() if drug_idx else []):
        mdid, mterm = seed_did, "seed"
    if mdid:
        china_rows.append({
            "trial_id": parsed.get("trial_id") or tid,
            "registry": parsed.get("registry") or ("ChiCTR" if "ChiCTR" in tid else None),
            "drug_id": mdid, "matched_term": mterm,
            "public_title": parsed.get("public_title"),
            "scientific_title": parsed.get("scientific_title"),
            "condition": parsed.get("condition"),
            "intervention": parsed.get("intervention"),
            "sponsor": parsed.get("sponsor"),
            "recruitment_status": parsed.get("recruitment_status"),
            "registration_date": parsed.get("registration_date"),
            "source_url": url, "session_label": SESSION,
        })
    return 1


def _load_seed_ids(args):
    """Collect ChiCTR/ICTRP ids to harvest directly (the reliable path).

    Accepts a seed-file (one id, or 'drug_id,ChiCTR...' per line) and/or a
    comma-separated --seed-ids. Returns list of (seed_drug_id_or_None, trial_id)."""
    out = []
    if args.seed_file and os.path.exists(args.seed_file):
        for line in open(args.seed_file):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in re.split(r'[,\t]', line)]
            if len(parts) >= 2:
                out.append((parts[0] or None, parts[1]))
            else:
                out.append((None, parts[0]))
    if args.seed_ids:
        for tid in args.seed_ids.split(","):
            tid = tid.strip()
            if tid:
                out.append((None, tid))
    return out


# ------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="fetch + match but do not write")
    ap.add_argument("--limit", type=int, default=0, help="cap number of target assets (0=all)")
    ap.add_argument("--max-pages", type=int, default=0, help="reserved for crawl-range mode")
    ap.add_argument("--sleep", type=float, default=2.0, help="polite delay between requests (s)")
    ap.add_argument("--seed-ids", default="", help="comma-separated ChiCTR/ICTRP TrialIDs to fetch directly")
    ap.add_argument("--seed-file", default="", help="file of TrialIDs (or 'drug_id,TrialID' per line)")
    ap.add_argument("--no-search", action="store_true",
                    help="skip the (server-broken) WHO search; ID-seeding only")
    args = ap.parse_args()

    sb = None
    drug_idx, n_drugs = {}, 0
    if os.environ.get("SUPABASE_URL"):
        try:
            sb = SB()
            drug_idx, n_drugs = load_drug_index(sb)
        except KeyError:
            print("!! SUPABASE_SERVICE_KEY not set — running in fetch-only mode")
            sb = None

    op = _opener()
    targets = list(TARGETS.items())
    if args.limit:
        targets = targets[: args.limit]

    print(f"WHO ICTRP China harvest · session={SESSION} · drugs_loaded={n_drugs} "
          f"· dry_run={args.dry_run}\n")

    searched_ok = blocked = detail_ok = 0
    seen_ids = set()
    china_rows, bronze_rows = [], []

    # ---- Path A: ID-seeding (the reliable path — uses the WORKING detail fetch)
    seeds = _load_seed_ids(args)
    if seeds:
        print(f"ID-seeding: {len(seeds)} TrialID(s) supplied -> ICTRP detail fetch")
        for seed_did, tid in seeds:
            n = process_trial_id(op, tid, drug_idx, seed_did, bronze_rows,
                                 china_rows, seen_ids, args.sleep)
            detail_ok += n
            print(f"  seed {tid:22s} (for {seed_did or '-'}) -> "
                  f"{'parsed' if n else 'no-record'}")

    # ---- Path B: targeted WHO search (server-broken; kept for when it returns)
    if not args.no_search:
        for did, terms in targets:
            ids = []
            status = "no-hits"
            for term in terms:
                try:
                    hit, cnt = search_intervention(op, term)
                    searched_ok += 1
                    ids += hit
                    status = f"OK stated_count={cnt}"
                    time.sleep(args.sleep)
                except SearchBlocked as e:
                    blocked += 1
                    status = f"BLOCKED(search-down) {e}"
                    break
                except Exception as e:
                    blocked += 1
                    status = f"BLOCKED {type(e).__name__}"
                    break
            ids = [i for i in sorted(set(ids)) if i not in seen_ids]
            print(f"  {did:12s} {'/'.join(terms):14s} -> {status} ids={ids[:6]}")
            for tid in ids:
                detail_ok += process_trial_id(op, tid, drug_idx, did, bronze_rows,
                                              china_rows, seen_ids, args.sleep)
    else:
        print("(search path skipped: --no-search)")

    print(f"\nsummary: searched_ok={searched_ok} blocked={blocked} "
          f"detail_ok={detail_ok} bronze={len(bronze_rows)} matched={len(china_rows)}")

    if args.dry_run:
        print("DRY RUN — no writes. Sample matched rows:")
        for r in china_rows[:5]:
            print("  ", r["trial_id"], "->", r["drug_id"], "|", (r.get("intervention") or "")[:60])
        return

    if not sb:
        print("!! no Supabase creds — cannot write. Set SUPABASE_URL/SUPABASE_SERVICE_KEY.")
        return

    if bronze_rows:
        code, _ = sb.insert("source_payloads", bronze_rows,
                            prefer="resolution=merge-duplicates")
        print(f"bronze source_payloads insert -> HTTP {code} ({len(bronze_rows)} rows)")
    if china_rows:
        code, resp = sb.insert("china_trials", china_rows,
                               prefer="resolution=merge-duplicates,return=minimal")
        if code in (404, 400) and isinstance(resp, str) and "china_trials" in resp:
            print("!! china_trials table missing — apply migrations/v_china_trials.sql "
                  "(workflow does this automatically). Bronze rows are safe.")
        else:
            print(f"china_trials upsert -> HTTP {code} ({len(china_rows)} matched trials)")
    print("=== done ===")

if __name__ == "__main__":
    main()
