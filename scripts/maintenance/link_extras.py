#!/usr/bin/env python3
"""Connectivity backfill: source_documents.entity_id (from title/text) and
signals.company_id (from headline), via the shared entity_matcher. Dry-run default."""
import os, sys, pathlib, requests
BASE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE / "src" / "meridian" / "identity"))
from entity_matcher import Registry
URL = "https://tghntyofptvfhmtchwcv.supabase.co"
KEY = os.environ.get("SUPABASE_SERVICE_KEY") or (BASE / ".supabase_service_key").read_text().strip()
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
APPLY = "--apply" in sys.argv
reg = Registry(URL, H)

def getall(t, p):
    out, s = [], 0
    while True:
        r = requests.get(f"{URL}/rest/v1/{t}", headers={**H, "Range": f"{s}-{s+999}"}, params=p)
        d = r.json() if r.status_code in (200, 206) else []
        if not isinstance(d, list): return out
        out += d
        if len(d) < 1000: break
        s += 1000
    return out

def patch(t, rid, body):
    requests.patch(f"{URL}/rest/v1/{t}?id=eq.{rid}", headers={**H, "Prefer": "return=minimal"}, json=body)

# 1) source_documents.entity_id from title (+ first 400 chars extracted_text), prefer drug
docs = [d for d in getall("source_documents", {"select": "id,entity_id,title,extracted_text"}) if not d.get("entity_id")]
dn = 0
for d in docs:
    blob = (d.get("title") or "") + " " + (d.get("extracted_text") or "")[:400]
    hits = reg.resolve(blob)
    drug = next((h for h in hits if h[0] == "drug"), None)
    pick = drug or (hits[0] if hits else None)
    if pick:
        dn += 1
        if APPLY: patch("source_documents", d["id"], {"entity_id": pick[1], "entity_type": pick[0]})
print(f"source_documents: {len(docs)} unlinked -> {dn} matchable{' (written)' if APPLY else ''}")

# 2) signals.company_id from headline, only when exactly one company resolves
sigs = [s for s in getall("signals", {"select": "id,company_id,headline,raw_headline"}) if not s.get("company_id")]
sn = 0
for s in sigs:
    blob = (s.get("headline") or "") + " " + (s.get("raw_headline") or "")
    cos = [h for h in reg.resolve(blob) if h[0] == "company"]
    if len(cos) == 1:
        sn += 1
        if APPLY: patch("signals", s["id"], {"company_id": cos[0][1]})
print(f"signals: {len(sigs)} unlinked -> {sn} single-company matchable{' (written)' if APPLY else ''}")
print("DRY RUN — add --apply to write" if not APPLY else "done")
