#!/usr/bin/env python3
"""Resumable curl-based prefetcher for Google Patents pages → data/patents_cache/.
Decouples slow network from the build script (which runs --no-fetch on the cache).
Shells out to curl (more robust than urllib on this runner). Bounded per invocation.

Usage: _patents_prefetch.py [start] [count] [pages]
  builds manifest if absent, then fetches manifest[start:start+count] x pages.
"""
import json, re, os, sys, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(BASE, "data", "patents_cache")
os.makedirs(CACHE, exist_ok=True)
MAN = os.path.join(CACHE, "_manifest.tsv")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
PUB_AFTER, PUB_BEFORE = "20100101", "20270101"

def build_manifest():
    drugs = json.load(open(os.path.join(CACHE, "drugs.json")))
    comps = {r["id"]: r for r in json.load(open("/tmp/companies.json"))}
    CORE = ["tl1a","il-23","il23","tslp","fcrn","igf-1r","ox40","il-4r","il-13","il-33","α4β7","a4b7","cd40","jak"]
    core = lambda t: any(k in (t or "").lower() for k in CORE)
    core_ids = sorted({d["company_id"] for d in drugs if d.get("company_id") and core(d.get("target"))})
    lines = []
    for cid in core_ids:
        name = comps.get(cid, {}).get("name", cid)
        inner = f"assignee={name}&country=US,WO,EP&type=PATENT&before=publication:{PUB_BEFORE}&after=publication:{PUB_AFTER}&sort=new"
        ck = "assignee_" + re.sub(r"[^a-z0-9]+", "-", cid.lower())
        lines.append(ck + "\t" + inner)
    LAND = {"TL1A": "TL1A", "IL-23p19": "IL-23 p19", "TSLP": "TSLP", "FcRn": "FcRn neonatal Fc receptor"}
    for canon, phrase in LAND.items():
        inner = f"q={phrase}&country=US,WO,EP&type=PATENT&before=publication:{PUB_BEFORE}&after=publication:{PUB_AFTER}&sort=new"
        ck = "target_" + re.sub(r"[^a-z0-9]+", "-", canon.lower())
        lines.append(ck + "\t" + inner)
    open(MAN, "w").write("\n".join(lines) + "\n")
    return lines

if not os.path.exists(MAN):
    build_manifest()
man = [l for l in open(MAN).read().splitlines() if l.strip()]

import urllib.parse
start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
count = int(sys.argv[2]) if len(sys.argv) > 2 else len(man)
pages = int(sys.argv[3]) if len(sys.argv) > 3 else 2

done = skipped = failed = 0
for line in man[start:start+count]:
    ck, inner = line.split("\t", 1)
    for pg in range(pages):
        path = os.path.join(CACHE, f"{ck}_p{pg}.json")
        if os.path.exists(path) and os.path.getsize(path) > 50:
            skipped += 1
            continue
        q = inner + (f"&page={pg}" if pg else "")
        enc = urllib.parse.quote(q, safe="")
        url = f"https://patents.google.com/xhr/query?url={enc}&exp="
        try:
            out = subprocess.run(["curl", "-s", "-m", "15", "-A", UA, url],
                                 capture_output=True, timeout=20).stdout
            if out and out[:1] == b"{":
                open(path, "wb").write(out)
                done += 1
            else:
                failed += 1
                print(f"  bad/empty {ck} p{pg} (len={len(out)})")
            time.sleep(0.8)
        except Exception as e:
            failed += 1
            print(f"  err {ck} p{pg}: {e}")
print(f"[prefetch {start}:{start+count} x{pages}p] fetched={done} skipped={skipped} failed={failed}")
