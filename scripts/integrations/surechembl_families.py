#!/usr/bin/env python3
"""
surechembl_families.py — INPADOC-style patent family members from SureChEMBL (EBI, keyless, free).

For every patent number in company_patents + drug_patents, look up its global family
(the jurisdictions it's filed in) and store members in patent_families, each with a
referenceable Google Patents URL. This is the IP "sources as reference" layer.

SureChEMBL needs hyphenated doc ids (US-20240327532-A1) and is flaky (transient nginx 503),
so every call retries with backoff. Run on a clean-egress runner for full coverage; the VM
works too but slowly. Idempotent (unique patent_number+family_doc_id).

Usage: python3 scripts/integrations/surechembl_families.py [--limit N] [--offset N] [--dry-run]
"""
import json, os, re, sys, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SB = "https://tghntyofptvfhmtchwcv.supabase.co/rest/v1"
KEY = open(os.path.join(ROOT, ".supabase_service_key")).read().strip()
SC = "https://www.surechembl.org/api"
HDR = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

def sb(path, method="GET", body=None, prefer=None):
    r = urllib.request.Request(f"{SB}/{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None)
    for k, v in HDR.items(): r.add_header(k, v)
    if prefer: r.add_header("Prefer", prefer)
    with urllib.request.urlopen(r, timeout=30) as resp:
        t = resp.read().decode(); return json.loads(t) if t else None

def sb_all(path):
    out, off = [], 0
    while True:
        r = urllib.request.Request(f"{SB}/{path}")
        for k, v in HDR.items(): r.add_header(k, v)
        r.add_header("Range-Unit", "items"); r.add_header("Range", f"{off}-{off+999}")
        with urllib.request.urlopen(r, timeout=30) as resp:
            c = json.loads(resp.read().decode())
        out += c
        if len(c) < 1000: return out
        off += 1000

def norm_hyphen(pn):
    """Normalize a patent number to SureChEMBL hyphenated doc id: US-20240327532-A1.
    Bare numeric (Orange Book) -> assume US grant; full CC+num+kind -> split."""
    if not pn: return None
    s = re.sub(r"[\s,]+", "", str(pn)).upper()
    if re.match(r"^[0-9]+$", s):           # bare Orange Book number -> US grant
        return f"US-{s}-B2"
    m = re.match(r"^([A-Z]{2})[-]?([0-9]+)[-]?([A-Z][0-9]?)?$", s)
    if not m: return None
    cc, num, kind = m.group(1), m.group(2), m.group(3) or ""
    return f"{cc}-{num}-{kind}" if kind else f"{cc}-{num}"

def gpat_url(doc_id):
    return "https://patents.google.com/patent/" + doc_id.replace("-", "")

def fetch_family(doc_id, tries=5):
    for i in range(tries):
        try:
            r = urllib.request.Request(f"{SC}/document/{doc_id}/family/members",
                headers={"Accept": "application/json", "User-Agent": "meridian-ip/1.0"})
            with urllib.request.urlopen(r, timeout=25) as resp:
                t = resp.read().decode()
            if t.lstrip().startswith("["):
                return json.loads(t)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            pass
        time.sleep(2 + 3 * i)
    return None

def main():
    args = sys.argv[1:]
    limit = int(args[args.index("--limit")+1]) if "--limit" in args else None
    offset = int(args[args.index("--offset")+1]) if "--offset" in args else 0
    dry = "--dry-run" in args

    # gather seed patents (number -> {drug_id, company_id})
    # NB: drug_patents uses patent_no, company_patents uses patent_number
    seeds = {}
    for r in sb_all("drug_patents?select=patent_no,drug_id"):
        pn = r.get("patent_no")
        if pn: seeds.setdefault(pn, {})["drug_id"] = r.get("drug_id")
    for r in sb_all("company_patents?select=patent_number,company_id"):
        pn = r.get("patent_number")
        if pn: seeds.setdefault(pn, {})["company_id"] = r.get("company_id")
    items = sorted(seeds.items())
    if offset: items = items[offset:]
    if limit: items = items[:limit]
    print(f"seeds to resolve: {len(items)} (of {len(seeds)} total)")

    written = blocked = nofam = 0
    for pn, link in items:
        doc = norm_hyphen(pn)
        if not doc:
            continue
        fam = fetch_family(doc)
        if fam is None:
            blocked += 1; print(f"  {pn}: blocked/unavailable"); continue
        if not fam:
            nofam += 1; continue
        rows = []
        for m in fam:
            mid = m.get("docId") or m.get("id") or (m if isinstance(m, str) else None)
            if not mid: continue
            cc = mid.split("-")[0] if "-" in mid else mid[:2]
            kind = mid.split("-")[-1] if mid.count("-") >= 2 else None
            rows.append(dict(patent_number=doc, family_doc_id=mid, jurisdiction=cc,
                kind_code=kind, drug_id=link.get("drug_id"), company_id=link.get("company_id"),
                source="surechembl", source_url=gpat_url(mid)))
        if dry:
            print(f"  {pn} -> {len(rows)} members ({','.join(sorted({r['jurisdiction'] for r in rows}))})")
        else:
            for i in range(0, len(rows), 500):
                sb("patent_families?on_conflict=patent_number,family_doc_id", "POST",
                   rows[i:i+500], prefer="resolution=merge-duplicates,return=minimal")
        written += len(rows)
        time.sleep(1)
    print(f"\nfamily members {'(dry) ' if dry else ''}written: {written} · seeds blocked: {blocked} · no-family: {nofam}")

if __name__ == "__main__":
    main()
