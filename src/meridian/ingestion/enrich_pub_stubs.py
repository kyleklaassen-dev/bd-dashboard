#!/usr/bin/env python3
"""
enrich_pub_stubs.py — fill bare publication nodes (PMID-only stubs created to satisfy
drug->publication edges) with title/journal/year/abstract from Europe PMC, BY PMID.

The drug-name-based abstract_fetcher won't reach these (they came from CT.gov trial
references), so this enriches them directly. Idempotent: only touches rows with a
null title. Free API, no key.

Usage: python3 scripts/enrich_pub_stubs.py [--limit N]
Env:   SUPABASE_URL, SUPABASE_SERVICE_KEY
"""
import os, sys, json, time, datetime, urllib.request, urllib.parse, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database import client as c

NOW = datetime.datetime.utcnow().isoformat()
LIMIT = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--limit=")), None)
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
UA = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 meridian-pubstub-enrich"}


def _get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  ! {e}", file=sys.stderr); return None


def main():
    stubs = c.select_all("publications", {"select": "id,pmid", "title": "is.null", "pmid": "not.is.null"})
    if LIMIT:
        stubs = stubs[:LIMIT]
    print(f"{len(stubs)} bare publication stubs to enrich")
    n = 0
    for s in stubs:
        pmid = s["pmid"]
        res = _get(f"{EPMC}?{urllib.parse.urlencode({'query': f'ext_id:{pmid} AND src:med', 'format': 'json', 'resultType': 'core'})}")
        hit = ((res or {}).get("resultList", {}).get("result") or [None])[0]
        if not hit:
            time.sleep(0.2); continue
        authors = [a.get("fullName") for a in (hit.get("authorList", {}) or {}).get("author", []) if a.get("fullName")]
        mesh = [m.get("descriptorName") for m in (hit.get("meshHeadingList", {}) or {}).get("meshHeading", []) if m.get("descriptorName")]
        py = hit.get("pubYear")
        patch = dict(title=(hit.get("title") or "")[:600] or None,
                     journal=((hit.get("journalInfo", {}).get("journal", {})) or {}).get("title"),
                     pub_year=int(py) if str(py or "").isdigit() else None,
                     authors=authors or None, mesh_terms=mesh or None,
                     abstract=(hit.get("abstractText") or "")[:8000] or None,
                     doi=hit.get("doi"), is_open_access=(hit.get("isOpenAccess") == "Y"),
                     cited_by_count=hit.get("citedByCount"), updated_at=NOW)
        c.update("publications", f"id=eq.{s['id']}", {k: v for k, v in patch.items() if v is not None})
        n += 1
        time.sleep(0.25)
    print(f"enriched {n} publication stubs")


if __name__ == "__main__":
    main()
