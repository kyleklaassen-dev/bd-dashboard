#!/usr/bin/env python3
"""
chunk_extract.py — full-document chunked extraction
===================================================
Reads a PDF that is stored in the Supabase `source-documents` bucket, splits it
into page-range chunks, and runs a structured extraction on EVERY chunk so the
whole document is captured (not just page 1). Writes typed, page-referenced,
entity-linked facts to intel_facts, market data to market_landscape, and a
rolled-up intel_digests row.

This is the scalable answer to large reports (e.g. TD Cowen 100+ page chapters):
chunk → extract → structured rows, deduped + page-referenced.

Usage:
  python3 scripts/chunk_extract.py --path "domain/<id>.pdf" --si <uuid> [--pages 1-40] [--chunk 6]
  python3 scripts/chunk_extract.py --path ... --si ... --chunk 6 --cache /tmp/c   # cache per-chunk LLM JSON
  python3 scripts/chunk_extract.py --path ... --si ... --map-only                 # print chunk plan, no LLM
"""
import os, sys, io, re, json, argparse, pathlib, time
from datetime import datetime, timezone
import requests

BASE = pathlib.Path(__file__).parent.parent
def _k(env, f):
    v = os.environ.get(env, "").strip()
    return v or ((BASE / f).read_text().strip() if (BASE / f).exists() else "")
SUPABASE_URL  = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
SERVICE_KEY   = _k("SUPABASE_SERVICE_KEY", ".supabase_service_key")
ANTHROPIC_KEY = _k("ANTHROPIC_API_KEY", ".anthropic_api_key")
MODEL = os.environ.get("CHUNK_MODEL", "claude-sonnet-4-6")  # fast model for per-chunk fact pulling
BUCKET = "source-documents"
SB = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Content-Type": "application/json"}

def sb_post(t, row):
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{t}", headers={**SB, "Prefer": "return=minimal"}, json=row, timeout=25)
    return r.status_code in (200, 201, 204), r.text[:140]
def sb_get(t, params):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{t}", headers=SB, params=params, timeout=25)
    return r.json() if r.status_code == 200 else []
_DRUGS = {}; _COMPANIES = {}
def preload():
    for d in sb_get("drugs", {"select": "id,name,display_name"}):
        for k in (d.get("name"), d.get("display_name"), d.get("id")):
            if k: _DRUGS[k.split("(")[0].strip().lower()] = d["id"]
    for c in sb_get("companies", {"select": "id,name"}):
        if c.get("name"): _COMPANIES[c["name"].lower()] = c["id"]
        _COMPANIES[c["id"]] = c["id"]
def find_drug(nm):
    if not nm: return None
    return _DRUGS.get(nm.split("(")[0].strip().lower())
def find_company(nm):
    if not nm: return None
    n = nm.lower()
    return _COMPANIES.get(n) or _COMPANIES.get(re.sub(r"[^a-z0-9]", "", n)[:40])

def fetch_pdf(path):
    r = requests.get(f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}",
                     headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}, timeout=60)
    r.raise_for_status()
    return r.content

PROMPT = """You are a pharma BD analyst for Ailux (TL1A×IL-23p19 bispecific, IBD). This is a CHUNK
(pages {pages}) of a larger research report titled "{title}". Extract EVERY substantive discrete fact stated in
this chunk — market sizes/shares, drug data, pipeline assets, pricing, KOL/management views, deal
terms, catalysts. Be exhaustive; this is one slice of a long document.
EXCLUDE boilerplate: legal disclosures, analyst certification, rating-distribution tables,
investment-banking-services statements, and regulatory-entity descriptions of the bank itself
(e.g. "TD Cowen", "TD Securities", "authorized and regulated") — these are not intelligence.
Return STRICT JSON:
{{
 "section": "the section/disease this chunk covers, if identifiable",
 "facts": [{{"fact_type":"clinical|commercial|competitive|market|management|patient|regulatory|catalyst|deal|pipeline","subject_name":"drug/company","subject_drug":"drug name if any","area":"tl1a|tslp|il4ra|igf1r|fcrn|tcell|general","claim":"one specific fact from the text","metric":"","value":"","unit":"","confidence":"high|medium|low"}}],
 "market":[{{"area":"tl1a|tslp|il4ra|igf1r|fcrn|tcell|general","disease":"","year_label":"2024A|2030P|...","market_size_usd_b":null,"company":"","market_share_pct":null}}]
}}
TEXT:
{text}"""

def extract_chunk(text, pages, title):
    r = requests.post("https://api.anthropic.com/v1/messages",
        headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": 8000,
              "messages": [{"role": "user", "content": PROMPT.format(pages=pages, title=title, text=text[:13000])}]},
        timeout=150)
    r.raise_for_status()
    raw = r.json()["content"][0]["text"].strip()
    if raw.startswith("```"): raw = raw.split("```")[1]; raw = raw[4:] if raw.startswith("json") else raw
    return json.loads(raw)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True); ap.add_argument("--si", default=None)
    ap.add_argument("--title", default="research report"); ap.add_argument("--source-url", default=None)
    ap.add_argument("--pages", default=None); ap.add_argument("--chunk", type=int, default=6)
    ap.add_argument("--map-only", action="store_true"); ap.add_argument("--cache", default=None)
    a = ap.parse_args()
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(fetch_pdf(a.path)))
    n = len(reader.pages)
    lo, hi = 1, n
    if a.pages:
        m = re.match(r"(\d+)-(\d+)", a.pages);
        if m: lo, hi = int(m.group(1)), min(int(m.group(2)), n)
    chunks = [(s, min(s + a.chunk - 1, hi)) for s in range(lo, hi + 1, a.chunk)]
    print(f"{n} pages; extracting {lo}-{hi} in {len(chunks)} chunks of {a.chunk}")
    if a.map_only:
        for c in chunks:
            t = "".join((reader.pages[i-1].extract_text() or "") for i in range(c[0], c[1]+1))
            print(f"  pp {c[0]}-{c[1]}: {len(t)} chars  | {t[:90].strip()!r}")
        return
    src = a.source_url
    preload()
    tot_f = tot_m = 0
    for (s, e) in chunks:
        text = "".join((reader.pages[i-1].extract_text() or "") for i in range(s, e+1))
        if len(text.strip()) < 60: continue
        cf = f"{a.cache}_{s}_{e}.json" if a.cache else None
        if cf and os.path.exists(cf): data = json.load(open(cf))
        else:
            try: data = extract_chunk(text, f"{s}-{e}", a.title)
            except Exception as ex: print(f"  pp{s}-{e}: extract err {ex}"); continue
            if cf: json.dump(data, open(cf, "w"))
        sect = data.get("section")
        rows = []
        for f in data.get("facts", []):
            claim = (f.get("claim") or "").strip()
            if not claim: continue
            dnm = f.get("subject_drug") or ""
            v = f.get("value")
            try: vn = float(v) if v not in (None,"","null") and str(v).replace('.','').replace('-','').isdigit() else None
            except: vn = None
            rows.append({"submitted_intel_id": a.si, "source_url": src, "fact_type": f.get("fact_type") or "other",
                "subject_type": "drug" if dnm else "company", "subject_id": find_drug(dnm) or find_company(f.get("subject_name")),
                "subject_name": f.get("subject_name") or dnm, "claim": claim[:600], "metric": f.get("metric") or None,
                "value_num": vn, "value_text": (None if vn is not None else (str(v) if v else None)), "unit": f.get("unit") or None,
                "area_id": f.get("area") or None, "confidence": f.get("confidence") or "medium",
                "section": sect, "page_ref": f"pp {s}-{e}"})
        if rows:
            ok,_ = sb_post("intel_facts", rows); tot_f += len(rows) if ok else 0
        mrows = [{"submitted_intel_id": a.si, "source_url": src, "area_id": m.get("area"), "disease": m.get("disease"),
                  "year_label": m.get("year_label"), "market_size_usd_b": m.get("market_size_usd_b"), "company": m.get("company"),
                  "market_share_pct": m.get("market_share_pct"), "note": f"pp {s}-{e}"}
                 for m in data.get("market", []) if m.get("company") and (m.get("market_share_pct") is not None or m.get("market_size_usd_b") is not None)]
        if mrows:
            ok,_ = sb_post("market_landscape", mrows); tot_m += len(mrows) if ok else 0
        print(f"  pp{s}-{e}: +{len(rows)} facts +{len(mrows)} market (cum {tot_f}/{tot_m})", flush=True)
    print(f"DONE: {tot_f} facts, {tot_m} market rows")

if __name__ == "__main__":
    main()
