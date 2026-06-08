#!/usr/bin/env python3
"""
v130 publication-influence collector — Semantic Scholar (FREE), bronze-first.

Enriches `publications` with literature-INFLUENCE signal:
  * influential_citation_count  (S2 influentialCitationCount)  + mirrors v128 s2_influential_citations
  * s2_citation_count           (S2 citationCount, cross-check vs Crossref cited_by_count)
  * tldr                        (S2 machine TLDR, tldr.text)
  * fields_of_study             (S2 fieldsOfStudy[])
  * s2_enriched_at              (fetch timestamp)            + mirrors v128 s2_fetched_at

BRONZE FIRST: every per-pmid S2 record is written to `source_payloads`
  (source='semantic_scholar', entity_type='publication', endpoint='paper.batch.v130')
  BEFORE promotion. Dedupe on payload_hash → idempotent.

RESOLVE-OR-SKIP: S2 lacks records for some PMIDs → those rows stay NULL (never fabricated).

IDEMPOTENCY: only pmids with s2_enriched_at IS NULL are (re)fetched; promotion PATCHes
  only when a target value actually changed. A clean re-run touches 0 rows (not-found
  pmids return no data → nothing to write).

Usage:
  python3 publication_influence.py            # dry run: counts + 1 sample batch, no writes
  python3 publication_influence.py --write     # fetch + bronze + promote
  python3 publication_influence.py --write --max-batches 2   # bounded window
  python3 publication_influence.py --report    # print enrichment stats (read-only)
"""
from __future__ import annotations
import argparse, json, os, sys, time, hashlib, datetime
import urllib.request, urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REF = "tghntyofptvfhmtchwcv"
REST = f"https://{REF}.supabase.co/rest/v1"
S2_BATCH = "https://api.semanticscholar.org/graph/v1/paper/batch"
FIELDS = "influentialCitationCount,citationCount,tldr,fieldsOfStudy,title"
UA = "MeridianBD/1.0 (mailto:kyleklaassen2@gmail.com)"
SOURCE = "semantic_scholar"
ENDPOINT = "paper.batch.v130"
SESSION_LABEL = "v130-pub-influence-2026-06-07"
BATCH_SIZE = 200
BATCH_DELAY = 2.0


def key(fn):
    with open(os.path.join(BASE, fn)) as f:
        return f.read().strip()


SK = key(".supabase_service_key")
HDR = {"apikey": SK, "Authorization": f"Bearer {SK}", "Content-Type": "application/json"}


def sb_get_all(table, params, page=1000):
    out, off = [], 0
    while True:
        url = f"{REST}/{table}?{params}&limit={page}&offset={off}"
        req = urllib.request.Request(url, headers=HDR)
        with urllib.request.urlopen(req, timeout=40) as r:
            chunk = json.loads(r.read().decode())
        out.extend(chunk)
        if len(chunk) < page:
            return out
        off += page


def sb_patch(table, match, body):
    req = urllib.request.Request(
        f"{REST}/{table}?{match}", data=json.dumps(body).encode(),
        headers={**HDR, "Prefer": "return=minimal"}, method="PATCH")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def sb_insert(table, rows):
    if not rows:
        return 204
    req = urllib.request.Request(
        f"{REST}/{table}", data=json.dumps(rows).encode(),
        headers={**HDR, "Prefer": "return=minimal"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


def sb_upsert(table, rows, on_conflict):
    if not rows:
        return 204
    req = urllib.request.Request(
        f"{REST}/{table}?on_conflict={on_conflict}", data=json.dumps(rows).encode(),
        headers={**HDR, "Prefer": "resolution=merge-duplicates,return=minimal"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.status


def s2_batch(pmids):
    """POST a batch of PMID:xxx ids; returns list aligned to input (null where unknown)."""
    ids = [f"PMID:{p}" for p in pmids]
    body = json.dumps({"ids": ids}).encode()
    url = f"{S2_BATCH}?fields={FIELDS}"
    for attempt in range(5):
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json", "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                wait = 5 * (attempt + 1)
                print(f"    S2 {e.code}; backoff {wait}s", flush=True)
                time.sleep(wait)
                continue
            if e.code == 400:
                # S2 returns 400 when an entire batch has no resolvable ids
                # (all S2-not-found). Resolve-or-skip: treat as no data, never fabricate.
                print(f"    S2 400 (no resolvable ids in batch of {len(pmids)}); skipping", flush=True)
                return [None] * len(pmids)
            raise
        except urllib.error.URLError as e:
            wait = 5 * (attempt + 1)
            print(f"    S2 URLError {e}; backoff {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError("S2 batch failed after retries")


def existing_bronze_hashes():
    rows = sb_get_all("source_payloads",
                      f"select=external_id,payload_hash&source=eq.{SOURCE}&endpoint=eq.{ENDPOINT}")
    return {(r["external_id"], r["payload_hash"]) for r in rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--max-batches", type=int, default=0, help="0 = all")
    args = ap.parse_args()

    if args.report:
        return report()

    # publications with a pmid; fetch only not-yet-enriched (idempotent resume)
    pubs = sb_get_all("publications",
                      "select=id,pmid,cited_by_count,influential_citation_count,s2_citation_count,tldr,fields_of_study,s2_enriched_at&pmid=not.is.null")
    print(f"publications with pmid: {len(pubs)}")
    todo = [p for p in pubs if p.get("s2_enriched_at") is None]
    print(f"not yet enriched (s2_enriched_at IS NULL): {len(todo)}")
    by_pmid = {p["pmid"]: p for p in pubs}

    if not args.write:
        # dry run: one sample batch, no writes
        sample = [p["pmid"] for p in todo[:5]]
        if sample:
            res = s2_batch(sample)
            found = sum(1 for x in res if x)
            print(f"DRY RUN sample batch ({len(sample)} pmids): {found} found in S2")
            for x in res:
                if x:
                    print("  -", x.get("influentialCitationCount"), "infl |",
                          x.get("citationCount"), "cit |", (x.get("title") or "")[:70])
        print("DRY RUN — no writes. Re-run with --write.")
        return

    bronze_seen = existing_bronze_hashes()
    batches = [todo[i:i + BATCH_SIZE] for i in range(0, len(todo), BATCH_SIZE)]
    if args.max_batches:
        batches = batches[:args.max_batches]

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    promoted = found = notfound = bronze_new = unchanged = 0

    for bi, batch in enumerate(batches, 1):
        pmids = [p["pmid"] for p in batch]
        print(f"[batch {bi}/{len(batches)}] {len(pmids)} pmids", flush=True)
        res = s2_batch(pmids)
        bronze_rows = []
        for pmid, rec in zip(pmids, res):
            pub = by_pmid[pmid]
            if not rec:
                notfound += 1
                continue  # resolve-or-skip: leave NULL, no bronze
            found += 1
            payload = {
                "influentialCitationCount": rec.get("influentialCitationCount"),
                "citationCount": rec.get("citationCount"),
                "tldr": (rec.get("tldr") or {}).get("text") if rec.get("tldr") else None,
                "fieldsOfStudy": rec.get("fieldsOfStudy"),
                "title": rec.get("title"),
                "paperId": rec.get("paperId"),
            }
            phash = hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            # BRONZE first (idempotent on (external_id, payload_hash))
            if (pmid, phash) not in bronze_seen:
                bronze_rows.append({
                    "source": SOURCE, "entity_type": "publication",
                    "meridian_id": pub["id"], "external_id": pmid,
                    "endpoint": ENDPOINT, "payload": payload, "payload_hash": phash,
                    "fetched_at": now, "session_label": SESSION_LABEL, "promoted": False,
                })
                bronze_seen.add((pmid, phash))
        if bronze_rows:
            sb_insert("source_payloads", bronze_rows)
            bronze_new += len(bronze_rows)

        # PROMOTE — bulk merge-upsert (one POST per batch), only changed rows
        promote_rows = []
        for pmid, rec in zip(pmids, res):
            if not rec:
                continue
            pub = by_pmid[pmid]
            infl = rec.get("influentialCitationCount")
            cit = rec.get("citationCount")
            tldr = (rec.get("tldr") or {}).get("text") if rec.get("tldr") else None
            fos = rec.get("fieldsOfStudy") or None
            same = (pub.get("influential_citation_count") == infl and
                    pub.get("s2_citation_count") == cit and
                    pub.get("tldr") == tldr and
                    pub.get("fields_of_study") == fos and
                    pub.get("s2_enriched_at") is not None)
            if same:
                unchanged += 1
                continue
            promote_rows.append({
                "id": pub["id"],
                "influential_citation_count": infl,
                "s2_influential_citations": infl,   # mirror v128
                "s2_citation_count": cit,
                "tldr": tldr,
                "fields_of_study": fos,
                "s2_enriched_at": now,
                "s2_fetched_at": now,               # mirror v128
            })
        if promote_rows:
            sb_upsert("publications", promote_rows, "id")
            promoted += len(promote_rows)
        print(f"    batch {bi}: +{len(bronze_rows)} bronze, +{len(promote_rows)} promoted", flush=True)
        if bi < len(batches):
            time.sleep(BATCH_DELAY)

    print(f"\nDONE: found={found} notfound={notfound} promoted={promoted} "
          f"unchanged={unchanged} bronze_new={bronze_new}")


def report():
    pubs = sb_get_all("publications",
                      "select=pmid,title,cited_by_count,influential_citation_count,s2_citation_count,tldr,fields_of_study,s2_enriched_at&pmid=not.is.null")
    n = len(pubs)
    enriched = [p for p in pubs if p.get("s2_enriched_at")]
    has_infl = [p for p in pubs if p.get("influential_citation_count") is not None]
    has_tldr = [p for p in pubs if p.get("tldr")]
    print(f"publications w/ pmid: {n}")
    print(f"s2_enriched_at set:   {len(enriched)}")
    print(f"influential_citation_count set: {len(has_infl)}")
    print(f"tldr set: {len(has_tldr)}")
    vals = sorted([p["influential_citation_count"] for p in has_infl])
    if vals:
        import statistics
        buckets = {"0": 0, "1-4": 0, "5-19": 0, "20-99": 0, "100+": 0}
        for v in vals:
            if v == 0: buckets["0"] += 1
            elif v < 5: buckets["1-4"] += 1
            elif v < 20: buckets["5-19"] += 1
            elif v < 100: buckets["20-99"] += 1
            else: buckets["100+"] += 1
        print(f"influential_citation_count: min={vals[0]} median={statistics.median(vals)} "
              f"max={vals[-1]} mean={statistics.mean(vals):.1f}")
        print("distribution:", buckets)
    print("\nTOP 10 by influentialCitationCount:")
    top = sorted(has_infl, key=lambda p: p["influential_citation_count"], reverse=True)[:10]
    for p in top:
        print(f"  {p['influential_citation_count']:>5}  (cit {p.get('s2_citation_count')})  "
              f"{(p.get('title') or '')[:80]}")


if __name__ == "__main__":
    main()
