#!/usr/bin/env python3
"""
FDA Orphan Drug Designations — hosted-runner export pull
========================================================
The accessdata.fda.gov OOPD CFM *search* resists scraping (Akamai 503 under the
shared VM), but the public results form exposes an Excel export
(Output_Format=Excel). FDA's "Excel" file is actually an HTML <table> served as
application/vnd.ms-excel — we POST the form, parse the table, match rows to our
`drugs` (resolve-or-skip), and write orphan rows to `regulatory_designations`
alongside the existing breakthrough / fast_track / PRIME rows. Bronze first.

Run from a GitHub-hosted runner (clean egress + retry/backoff).

Env:  SUPABASE_URL, SUPABASE_SERVICE_KEY
Run:  python3 scripts/integrations/fda_orphan_designations.py --dry-run
      python3 scripts/integrations/fda_orphan_designations.py --start-date 01/01/2015
"""
import os, re, sys, json, time, hashlib, argparse
import urllib.request, urllib.parse, urllib.error, http.cookiejar
from datetime import datetime, timezone
from html.parser import HTMLParser

UA = "Mozilla/5.0 (Meridian-BD-Research; +https://github.com/kyleklaassen-dev/bd-dashboard; contact kyleklaassen2@gmail.com)"
INDEX = "https://www.accessdata.fda.gov/scripts/opdlisting/oopd/"
RESULTS = "https://www.accessdata.fda.gov/scripts/opdlisting/oopd/OOPD_Results.cfm"
SESSION = f"fda-orphan-{datetime.now(timezone.utc):%Y%m%d}"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ------------------------------------------------------------------------- fetch
def _retry(fn, *a, tries=4, base=3.0, **k):
    last = None
    for i in range(tries):
        try:
            return fn(*a, **k)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                ConnectionError, OSError) as e:
            last = e
            time.sleep(base * (2 ** i))
    raise last

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Surface the 302 Location instead of blindly following it (the OOPD form
    redirects to a session-scoped results URL; the default handler drops the
    POST body and lands on a 404)."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, f"redirect:{newurl}", headers, fp)

def _build_opener(follow=True):
    cj = http.cookiejar.CookieJar()
    handlers = [urllib.request.HTTPCookieProcessor(cj)]
    if not follow:
        handlers.append(_NoRedirect())
    return urllib.request.build_opener(*handlers)

def _hidden(html, name):
    m = (re.search(rf'id="{name}"[^>]*value="([^"]*)"', html) or
         re.search(rf'name="{name}"[^>]*value="([^"]*)"', html))
    return m.group(1) if m else ""

def fetch_export(start_date, end_date, per_page=10000):
    """Drive the OOPD search the way a browser does, then retrieve the Excel export.
    1) GET the search form (sets the ColdFusion CFID/CFTOKEN session cookie).
    2) POST the form with Output_Format=Excel using that session.
    3) If the POST 302-redirects, follow the Location with the same session
       (that target is the actual results/Excel page).
    Returns raw HTML/Excel text. Works from clean egress; on the throttled VM the
    earlier step is Akamai-blocked, which is why this runs off-VM."""
    form = {
        "Product_name": "", "sponsor_name": "", "Designation": "",
        "Designation_Start_Date": start_date, "Designation_End_Date": end_date,
        "Search_param": "DESDATE",          # all designations
        "Output_Format": "Excel",           # the export
        "Sort_order": "Date_Reverse_Order",
        "RecordsPerPage": str(per_page),
        "newSearch": "Run Search",
    }
    hdr = {"User-Agent": UA, "Referer": INDEX,
           "Accept": "application/vnd.ms-excel,text/html,*/*"}

    def _do():
        op = _build_opener(follow=False)
        # 1) prime the session cookie
        try:
            with op.open(urllib.request.Request(INDEX, headers={"User-Agent": UA}),
                         timeout=60):
                pass
        except urllib.error.HTTPError:
            pass
        body = urllib.parse.urlencode(form).encode()
        # 2) POST results (no auto-follow so we can read Location)
        try:
            req = urllib.request.Request(RESULTS, data=body, headers={
                **hdr, "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://www.accessdata.fda.gov"})
            with op.open(req, timeout=90) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307) and str(e.reason).startswith("redirect:"):
                loc = str(e.reason).split("redirect:", 1)[1]
                if loc.startswith("/"):
                    loc = "https://www.accessdata.fda.gov" + loc
                elif not loc.startswith("http"):
                    loc = INDEX + loc
                # 3) follow the redirect target with the SAME session
                op2 = urllib.request.build_opener(
                    *[h for h in op.handlers
                      if isinstance(h, urllib.request.HTTPCookieProcessor)])
                with op2.open(urllib.request.Request(loc, headers=hdr),
                              timeout=90) as r2:
                    return r2.read().decode("utf-8", "replace")
            raise
    return _retry(_do)

# ------------------------------------------------------------------------- parse
class _Table(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell, self._in = [], None, None, False
    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell, self._in = [], True
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None:
            self._row.append(re.sub(r'\s+', ' ', "".join(self._cell)).strip())
            self._in = False
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None
    def handle_data(self, data):
        if self._in:
            self._cell.append(data)

def parse_rows(raw):
    """Return list of dict rows keyed by normalized header names."""
    p = _Table(); p.feed(raw)
    rows = p.rows
    if not rows:
        return [], []
    # find the header row: the one containing 'designation' or 'generic'
    hi = 0
    for i, r in enumerate(rows[:5]):
        joined = " ".join(r).lower()
        if "designation" in joined or "generic" in joined or "orphan" in joined:
            hi = i; break
    header = [h.strip().lower() for h in rows[hi]]
    out = []
    for r in rows[hi + 1:]:
        if len(r) < 2 or not any(r):
            continue
        out.append({header[i] if i < len(header) else f"col{i}": v
                    for i, v in enumerate(r)})
    return out, header

def _find(row, *keys):
    # wants-outer: an earlier `want` (more specific) wins over a later one, and we
    # never let a non-date lookup land on a '...date' column (avoids 'designation'
    # matching 'designation date').
    for want in keys:
        date_want = "date" in want
        for k in row:
            if want in k and (date_want or "date" not in k):
                return row[k]
    return None

def _to_iso(d):
    if not d:
        return None
    d = d.strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%B %d, %Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(d, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.search(r'(\d{4})', d)
    return f"{m.group(1)}-01-01" if m else None

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
    def insert(self, table, rows, prefer="resolution=merge-duplicates"):
        return self._req("POST", table, rows, prefer=prefer)

def load_drug_index(sb):
    rows = sb.get("drugs?select=id,name,display_name,brand_name,aliases,inn_name,dev_code")
    idx = {}
    def norm(s):
        return re.sub(r'[^a-z0-9]', '', (s or "").lower())
    for d in rows:
        terms = [d.get("name"), d.get("display_name"), d.get("brand_name"),
                 d.get("inn_name"), d.get("dev_code"), d["id"]]
        al = d.get("aliases")
        if isinstance(al, list):
            terms += al
        for t in terms:
            n = norm(t)
            if n and len(n) >= 4:
                idx.setdefault(n, d["id"])
    return idx, len(rows)

def match(idx, *texts):
    hay = re.sub(r'[^a-z0-9]', '', " ".join(filter(None, texts)).lower())
    if not hay:
        return None, None
    for term in sorted(idx, key=len, reverse=True):
        if term in hay:
            return idx[term], term
    return None, None

# ------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--start-date", default="01/01/1983")
    ap.add_argument("--end-date", default=datetime.now().strftime("%m/%d/%Y"))
    ap.add_argument("--limit", type=int, default=0, help="cap parsed rows (0=all)")
    args = ap.parse_args()

    print(f"FDA Orphan Designations · session={SESSION} · "
          f"{args.start_date}..{args.end_date} · dry_run={args.dry_run}\n")

    try:
        raw = fetch_export(args.start_date, args.end_date)
    except Exception as e:
        # A blocked external source is a documented gap, not a build failure.
        print(f"!! FDA OOPD export unreachable after retries ({type(e).__name__}: {e}). "
              "Re-run the workflow later — hosted egress is usually intermittent, "
              "not permanent. No data written.")
        return
    low = raw.lower()
    if ("access denied" in low or "<title>error" in low or
            ("503" in raw[:200] and "table" not in low)):
        print("!! FDA blocked the request (Akamai). Re-run the workflow; hosted "
              "egress usually clears within retries. No data written.")
        return

    rows, header = parse_rows(raw)
    print(f"parsed header: {header}")
    print(f"parsed {len(rows)} designation rows")
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("!! no rows parsed — export shape may have changed. Raw head:")
        print(raw[:500])
        return

    sb = None
    drug_idx, n_drugs = {}, 0
    if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"):
        sb = SB()
        drug_idx, n_drugs = load_drug_index(sb)
    print(f"drugs loaded for matching: {n_drugs}\n")

    bronze, designations, matched = [], [], 0
    existing_cache = {}

    for r in rows:
        generic = _find(r, "generic", "drug")
        trade = _find(r, "trade", "brand")
        indication = _find(r, "orphan designation", "designation", "indication")
        ddate = _to_iso(_find(r, "date"))
        sponsor = _find(r, "sponsor", "company")
        bronze.append({
            "source": "fda_oopd", "entity_type": "designation",
            "meridian_id": None, "external_id": None,
            "endpoint": "orphan_export", "payload": r,
            "payload_hash": hashlib.md5(json.dumps(r, sort_keys=True).encode()).hexdigest(),
            "session_label": SESSION, "promoted": False,
        })
        if not drug_idx:
            continue
        did, term = match(drug_idx, generic, trade)
        if not did:
            continue                      # resolve-or-skip
        # idempotency: skip if an orphan row already exists for this drug+indication+date
        if did not in existing_cache:
            existing_cache[did] = sb.get(
                f"regulatory_designations?drug_id=eq.{did}"
                f"&designation_type=eq.orphan&select=indication,granted_date")
        dupe = any((e.get("indication") == indication and e.get("granted_date") == ddate)
                   for e in existing_cache[did])
        if dupe:
            continue
        matched += 1
        designations.append({
            "drug_id": did, "designation_type": "orphan",
            "indication": indication, "granted_date": ddate,
            "granting_authority": "FDA",
            "source": RESULTS,
            "notes": f"FDA Orphan Drug Designation. Trade name: {trade or 'n/a'}. "
                     f"Sponsor: {sponsor or 'n/a'}. Matched via '{term}'. "
                     f"Pulled {TODAY} from OOPD Excel export.",
        })

    print(f"summary: bronze={len(bronze)} matched_to_drugs={matched} "
          f"new_orphan_rows={len(designations)}")

    if args.dry_run:
        print("DRY RUN — no writes. Sample matched designations:")
        for d in designations[:8]:
            print("  ", d["drug_id"], "|", d["granted_date"], "|",
                  (d["indication"] or "")[:60])
        return
    if not sb:
        print("!! no Supabase creds — cannot write.")
        return

    if bronze:
        code, _ = sb.insert("source_payloads", bronze)
        print(f"bronze source_payloads -> HTTP {code} ({len(bronze)} rows)")
    if designations:
        code, resp = sb.insert("regulatory_designations", designations,
                               prefer="return=minimal")
        print(f"regulatory_designations (orphan) -> HTTP {code} ({len(designations)} rows)")
        if code >= 300:
            print("   resp:", str(resp)[:300])
    print("=== done ===")

if __name__ == "__main__":
    main()
