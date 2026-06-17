#!/usr/bin/env python3
"""
refresh_orange_purple_book.py — keep FDA Orange/Purple Book data FRESH in the
EXISTING dashboard tables (drug_patents, drug_exclusivity). NOT a new table:
the one-off 2026-06-07 load had no recurring refresh; this is that refresh.

Orange Book = downloadable '~'-delimited data files (products/patent/exclusivity),
NOT a REST API. Purple Book = downloadable CSV (biologics/biosimilars). Both run
on a GitHub runner (FDA egress is open there). Deterministic, idempotent
(uuid5 natural keys), scoped to application numbers we already track -> no dupes.

Usage: python3 src/meridian/ingestion/refresh_orange_purple_book.py [--dry-run]
Env:   SUPABASE_URL, SUPABASE_SERVICE_KEY
"""
import os, sys, io, csv, zipfile, uuid, datetime, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from meridian.database import client as c

DRY = "--dry-run" in sys.argv
NOW = datetime.datetime.utcnow().isoformat()
NS = uuid.UUID("c9f3e2d1-3333-4444-8555-2b3c4d5e6f70")
_uid = lambda k: str(uuid.uuid5(NS, k))
OB_ZIP = "https://www.fda.gov/media/76860/download?attachment"   # Orange Book Data Files (FDA canonical link)
UA = {"User-Agent": "Mozilla/5.0 meridian-ob-refresh"}
digits = lambda s: "".join(ch for ch in (s or "") if ch.isdigit())
_yn = lambda v: True if (v or "").strip().upper() == "Y" else None  # "" -> NULL (boolean cols)


def applno_to_drug():
    """Map numeric FDA application number -> our drug_id, from tables that already
    carry the crosswalk (so we only ingest drugs Meridian tracks)."""
    m = {}
    for tbl in ("fda_approvals", "drug_exclusivity", "drug_patents"):
        for r in c.select_all(tbl, {"select": "drug_id,application_number"}):
            an = digits(r.get("application_number"))
            if an and r.get("drug_id"):
                m[an] = r["drug_id"]
    return m


def _download_zip(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return zipfile.ZipFile(io.BytesIO(r.read()))


def _delim_rows(zf, name):
    fn = next((n for n in zf.namelist() if n.lower().endswith(name)), None)
    if not fn:
        return []
    txt = zf.read(fn).decode("latin-1")
    return list(csv.DictReader(io.StringIO(txt), delimiter="~"))


def refresh_orange_book(a2d):
    zf = _download_zip(OB_ZIP)
    src = "orange_book"
    # patents -> drug_patents
    pat, exc = [], []
    for row in _delim_rows(zf, "patent.txt"):
        did = a2d.get(digits(row.get("Appl_No")))
        if not did:
            continue
        pno = row.get("Patent_No")
        pat.append(dict(id=_uid(f"obp_{did}_{row.get('Appl_No')}_{pno}"), drug_id=did,
            application_number=row.get("Appl_No"), patent_no=pno,
            patent_expire_date=row.get("Patent_Expire_Date_Text"),
            drug_substance_flag=_yn(row.get("Drug_Substance_Flag")), drug_product_flag=_yn(row.get("Drug_Product_Flag")),
            patent_use_code=row.get("Patent_Use_Code"), source=src,
            source_url=OB_ZIP, fetched_at=NOW))
    for row in _delim_rows(zf, "exclusivity.txt"):
        did = a2d.get(digits(row.get("Appl_No")))
        if not did:
            continue
        code = row.get("Exclusivity_Code")
        exc.append(dict(id=_uid(f"obe_{did}_{row.get('Appl_No')}_{code}"), drug_id=did,
            application_number=row.get("Appl_No"), exclusivity_code=code,
            exclusivity_date=row.get("Exclusivity_Date"), source=src, is_biologic=False,
            source_url=OB_ZIP, fetched_at=NOW))
    pat = list({(r["drug_id"], r["patent_no"]): r for r in pat}.values())  # de-dupe by real unique key
    exc = list({(r["drug_id"], r["exclusivity_code"], r["exclusivity_date"]): r for r in exc}.values())
    print(f"Orange Book: {len(pat)} patent rows, {len(exc)} exclusivity rows (scoped to tracked drugs)")
    if not DRY:
        for i in range(0, len(pat), 200): c.insert("drug_patents", pat[i:i+200], on_conflict="drug_id,patent_no")
        for i in range(0, len(exc), 200):
            c.insert("drug_exclusivity", exc[i:i+200], on_conflict="drug_id,exclusivity_code,exclusivity_date")
    _stamp("orange_book")


def refresh_purple_book(a2d):
    """Purple Book CSV URL is month-stamped; try recent months, best-effort."""
    # FDA moved the host (purplebooksearch.fda.gov/files -> accessdata.fda.gov/drugsatfda_docs/PurpleBook)
    # and uses INCONSISTENT month casing (e.g. 'january' but 'February'); try both, newest first.
    base = "https://www.accessdata.fda.gov/drugsatfda_docs/PurpleBook/{y}/purplebook-search-{m}-data-download.csv"
    mn = ["january","february","march","april","may","june",
          "july","august","september","october","november","december"]
    today = datetime.date.today()
    periods, yy, mo = [], today.year, today.month
    for _ in range(14):                       # last ~14 months, newest first
        periods.append((yy, mo)); mo -= 1
        if mo == 0: yy, mo = yy - 1, 12
    got = None
    for (py, pm) in periods:
        for m in (mn[pm-1], mn[pm-1].capitalize()):
            url = base.format(y=py, m=m)
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                    got = (url, r.read().decode("latin-1")); break
            except Exception:
                continue
        if got: break
    if not got:
        print("Purple Book: no monthly CSV reachable this run (non-fatal)"); return
    url, txt = got
    rows = list(csv.DictReader(io.StringIO(txt)))
    out = []
    for row in rows:
        bla = digits(row.get("BLA Number") or row.get("Application Number"))
        did = a2d.get(bla)
        if not did:
            continue
        out.append(dict(id=_uid(f"pb_{did}_{bla}"), drug_id=did, application_number=row.get("BLA Number"),
            exclusivity_code=None, exclusivity_date=row.get("Exclusivity Expiration Date"),
            source="purple_book", is_biologic=True, bla_number=bla,
            product_type="biologic", source_url=url, fetched_at=NOW))
    print(f"Purple Book: {len(out)} biologic rows from {url}")
    if out and not DRY:
        for i in range(0, len(out), 200): c.insert("drug_exclusivity", out[i:i+200], on_conflict="id")
    _stamp("purple_book")


def _stamp(src):
    if not DRY:
        c.update("api_sources", f"source=eq.{src}", {"last_run": NOW})


if __name__ == "__main__":
    a2d = applno_to_drug()
    print(f"tracked application numbers: {len(a2d)}" + (" (DRY)" if DRY else ""))
    # Each source is independent and FDA file endpoints can hiccup — never let one
    # failed download fail the whole monthly job (existing data stays as-is).
    for fn in (refresh_orange_book, refresh_purple_book):
        try:
            fn(a2d)
        except Exception as e:
            print(f"  ! {fn.__name__} failed (non-fatal): {type(e).__name__}: {e}", file=sys.stderr)
    print("Done.")
