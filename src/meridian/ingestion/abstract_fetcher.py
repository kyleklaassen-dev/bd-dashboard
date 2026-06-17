#!/usr/bin/env python3
"""
Abstract fetcher for Meridian BD Platform.
Sources: Europe PMC, PubMed, bioRxiv/medRxiv
Targets: TL1A, IL-23, FcRn, IGF-1R/TSHR, IL-4Rα, IL-13, TSLP, CD19×BCMA

Usage:
    python src/meridian/ingestion/abstract_fetcher.py                    # all Phase 2+ drugs
    python src/meridian/ingestion/abstract_fetcher.py --drug tulisokibart
    python src/meridian/ingestion/abstract_fetcher.py --preprints        # monitor mode only
    python src/meridian/ingestion/abstract_fetcher.py --dry-run          # fetch but don't write

Environment:
    SUPABASE_URL, SUPABASE_SERVICE_KEY  (or reads from .supabase_service_key)
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, date

# ── Configuration ─────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")

EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
PUBMED_ESEARCH   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH    = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Meridian-BD/1.0)"}

# Stages worth fetching abstracts for
TARGET_STAGES = {
    "phase_2", "phase_2b", "phase_2_positive", "phase_2b_positive",
    "phase_3", "phase_3_positive",
    "approved", "approved_us", "approved_eu", "approved_china",
    "approved_us_eu", "approved_partial",
    "bla_filed", "nda_filed"
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_service_key():
    if os.environ.get("SUPABASE_SERVICE_KEY"):
        return os.environ["SUPABASE_SERVICE_KEY"]
    # Local dev path
    for path in [
        "/sessions/determined-intelligent-cannon/mnt/BD Platform/.supabase_service_key",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".supabase_service_key"),
    ]:
        if os.path.exists(path):
            return open(path).read().strip()
    raise RuntimeError("SUPABASE_SERVICE_KEY not set and .supabase_service_key not found")


def supabase_get(path, params=None, raw_qs=None):
    """
    Fetch from Supabase REST.
    params: dict — values are URL-encoded (safe for simple strings).
    raw_qs: str  — appended verbatim after '?' (use for in.(...) filters).
    """
    service_key = get_service_key()
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if raw_qs:
        url += "?" + raw_qs
    elif params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}"
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def supabase_upsert(table, rows, conflict_column="source_url"):
    """Upsert rows to a Supabase table. Deduplicates on source_url if present."""
    if not rows:
        return 0
    service_key = get_service_key()
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    payload = json.dumps(rows).encode()
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=ignore-duplicates,return=minimal"
    })
    try:
        urllib.request.urlopen(req, timeout=30)
        return len(rows)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  Write error {e.code}: {body[:200]}", file=sys.stderr)
        return 0


# ── Europe PMC ────────────────────────────────────────────────────────────────

def search_europepmc(query, max_results=10):
    """Search Europe PMC for papers and conference abstracts."""
    encoded = urllib.parse.quote(query)
    url = (f"{EUROPEPMC_SEARCH}"
           f"?query={encoded}&format=json&pageSize={max_results}"
           f"&sort=date&resultType=core")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        results = []
        for item in data.get("resultList", {}).get("result", []):
            pub_type = item.get("pubType", "").lower()
            is_conference = "conference" in pub_type or "abstract" in pub_type
            pmid = item.get("pmid", "")
            doi = item.get("doi", "")
            if pmid:
                source_url = f"https://europepmc.org/article/med/{pmid}"
            elif doi:
                source_url = f"https://doi.org/{doi}"
            else:
                continue  # no stable URL — skip
            authors_raw = item.get("authorList", {}).get("author", [])
            authors = ", ".join([a.get("fullName", "") for a in authors_raw[:5]])
            if len(authors_raw) > 5:
                authors += " et al."
            abstract_raw = item.get("abstractText", "") or ""
            results.append({
                "pmid": pmid or None,
                "doi": doi or None,
                "title": (item.get("title", "") or "")[:400],
                "authors": authors[:500],
                "journal": (item.get("journalTitle", "")
                            or item.get("bookOrReportDetails", {}).get("publisher", ""))[:200],
                "pub_date": item.get("firstPublicationDate", "") or None,
                "abstract": abstract_raw[:3000],
                "is_conference": is_conference,
                "source_url": source_url,
                "source": "europepmc"
            })
        return results
    except Exception as e:
        print(f"  EuropePMC error for '{query}': {e}", file=sys.stderr)
        return []


# ── PubMed ────────────────────────────────────────────────────────────────────

def search_pubmed(query, max_results=5):
    """Search PubMed and fetch structured abstracts."""
    encoded = urllib.parse.quote(query)
    search_url = (f"{PUBMED_ESEARCH}"
                  f"?db=pubmed&term={encoded}&retmax={max_results}"
                  f"&retmode=json&sort=date")
    try:
        req = urllib.request.Request(search_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            search_data = json.loads(r.read())
        pmids = search_data.get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return []

        ids_str = ",".join(pmids)
        fetch_url = (f"{PUBMED_EFETCH}"
                     f"?db=pubmed&id={ids_str}&rettype=xml&retmode=xml")
        req = urllib.request.Request(fetch_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            xml = r.read().decode("utf-8", errors="ignore")

        results = []
        articles = re.findall(r'<PubmedArticle>(.*?)</PubmedArticle>', xml, re.DOTALL)
        for art in articles:
            pmid_m   = re.search(r'<PMID[^>]*>(\d+)</PMID>', art)
            title_m  = re.search(r'<ArticleTitle>(.*?)</ArticleTitle>', art, re.DOTALL)
            abs_m    = re.search(r'<AbstractText[^>]*>(.*?)</AbstractText>', art, re.DOTALL)
            jrnl_m   = re.search(r'<Title>(.*?)</Title>', art)
            year_m   = re.search(r'<PubDate>.*?<Year>(\d{4})</Year>', art, re.DOTALL)
            month_m  = re.search(r'<PubDate>.*?<Month>(\w+)</Month>', art, re.DOTALL)

            pmid = pmid_m.group(1) if pmid_m else ""
            if not pmid:
                continue
            title = re.sub(r'<[^>]+>', '', title_m.group(1) if title_m else "")[:400]
            if not title:
                continue
            abstract = re.sub(r'<[^>]+>', '', abs_m.group(1) if abs_m else "")[:3000]
            year = year_m.group(1) if year_m else ""
            month = month_m.group(1) if month_m else ""
            pub_date = f"{year}-{month}-01" if year and month else (year or None)

            results.append({
                "pmid": pmid,
                "doi": None,
                "title": title,
                "authors": "",
                "journal": re.sub(r'<[^>]+>', '', jrnl_m.group(1) if jrnl_m else "")[:200],
                "pub_date": pub_date,
                "abstract": abstract,
                "is_conference": False,
                "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "source": "pubmed"
            })
        return results
    except Exception as e:
        print(f"  PubMed error for '{query}': {e}", file=sys.stderr)
        return []


# ── bioRxiv / medRxiv ─────────────────────────────────────────────────────────

def search_biorxiv(query, max_results=5):
    """Search bioRxiv and medRxiv for preprints via Europe PMC (includes preprints)."""
    # Europe PMC indexes bioRxiv/medRxiv; use SRC:PPR filter for preprints
    results = search_europepmc(f"({query}) SRC:PPR", max_results=max_results)
    for r in results:
        r["source"] = "preprint"
    return results


# ── Preprint Monitor ──────────────────────────────────────────────────────────

def monitor_preprints(target_keywords=None):
    """
    Monitor bioRxiv and medRxiv for relevant preprints.
    Returns list of fetched result dicts (not written — caller decides).
    """
    if target_keywords is None:
        target_keywords = [
            "TL1A DR3 IBD",
            "IL-23p19 bispecific",
            "FcRn inhibitor autoimmune",
            "IGF-1R thyroid eye disease",
            "TSLP atopic dermatitis bispecific",
            "CD19 BCMA T cell engager autoimmune",
            "tulisokibart",
            "afimkibart",
            "efgartigimod",
            "nipocalimab",
            "zumilokibart",
            "spesolimab IBD",
            "mirikizumab",
        ]
    all_results = []
    seen_urls = set()
    print(f"Monitoring preprints for {len(target_keywords)} keyword groups...")
    for kw in target_keywords:
        hits = search_biorxiv(kw, max_results=3)
        for h in hits:
            if h.get("source_url") and h["source_url"] not in seen_urls:
                seen_urls.add(h["source_url"])
                h["query_keyword"] = kw
                all_results.append(h)
        time.sleep(0.4)
    print(f"  Found {len(all_results)} unique preprints.")
    return all_results


# ── Per-drug abstract fetch ───────────────────────────────────────────────────

def fetch_abstracts_for_drug(drug_name, target=None, indication=None, verbose=False):
    """
    Fetch all available abstracts for a drug across all sources.
    Returns deduplicated list of result dicts.
    """
    queries = [drug_name]
    if target and target.strip():
        queries.append(f"{drug_name} {target}")
    if indication and indication.strip():
        queries.append(f"{drug_name} {indication}")

    all_results = []
    seen_keys = set()  # deduplicate by (pmid or source_url)

    def dedup_key(r):
        return r.get("pmid") or r.get("source_url", "")

    for q in queries[:2]:
        if verbose:
            print(f"    EuropePMC: {q!r}")
        for result in search_europepmc(q, max_results=6):
            k = dedup_key(result)
            if k and k not in seen_keys:
                seen_keys.add(k)
                all_results.append(result)
        time.sleep(0.5)

        if verbose:
            print(f"    PubMed:    {q!r}")
        for result in search_pubmed(q, max_results=4):
            k = dedup_key(result)
            if k and k not in seen_keys:
                seen_keys.add(k)
                all_results.append(result)
        time.sleep(0.5)

    return all_results[:12]  # cap per drug


# ── Build Supabase row ────────────────────────────────────────────────────────

def build_doc_row(ab, drug, drug_name):
    """Convert a fetched abstract dict + drug record into a company_documents row."""
    pub_date = ab.get("pub_date") or None
    # Normalise date to YYYY-MM-DD if it looks like a year only
    if pub_date and re.match(r'^\d{4}$', str(pub_date)):
        pub_date = f"{pub_date}-01-01"
    elif pub_date and re.match(r'^\d{4}-\w+$', str(pub_date)):
        # e.g. "2024-Jan"
        pub_date = None  # can't reliably convert month names here

    doc_type = "abstract"
    if ab.get("is_conference"):
        doc_type = "abstract"  # conference abstracts still go in 'abstract' bucket
    if "preprint" in ab.get("source", ""):
        doc_type = "clinical_data"

    return {
        "company_id": drug.get("company_id") or None,
        "drug_id": drug.get("id") or None,
        "document_type": doc_type,
        "title": (ab.get("title", "") or "Untitled")[:400],
        "authors": (ab.get("authors", "") or "")[:500] or None,
        "journal": (ab.get("journal", "") or "")[:200] or None,
        "publication_date": pub_date,
        "source_url": ab.get("source_url", ""),
        "pubmed_id": ab.get("pmid") or None,
        "doi": ab.get("doi") or None,
        "abstract_text": (ab.get("abstract", "") or "")[:3000] or None,
        "drug_names": [drug_name],
        "target": (drug.get("target", "") or "")[:200] or None,
        "phase": (drug.get("stage", "") or "")[:50] or None,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Meridian abstract fetcher")
    parser.add_argument("--drug",      help="Fetch abstracts for a specific drug name")
    parser.add_argument("--preprints", action="store_true",
                        help="Run preprint monitor only, write results to company_documents")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Fetch but do not write to Supabase")
    parser.add_argument("--verbose",   action="store_true")
    args = parser.parse_args()

    # ── Preprint monitor mode ─────────────────────────────────────────────────
    if args.preprints:
        preprints = monitor_preprints()
        if args.dry_run:
            print(f"[DRY RUN] Would write {len(preprints)} preprints")
            for p in preprints[:5]:
                print(f"  {p.get('title', '')[:80]}")
            return

        rows = []
        for p in preprints:
            if not p.get("title"):
                continue
            pub_date = p.get("pub_date") or None
            if pub_date and re.match(r'^\d{4}$', str(pub_date)):
                pub_date = f"{pub_date}-01-01"
            rows.append({
                "document_type": "other",
                "title": p["title"][:400],
                "authors": (p.get("authors", "") or "")[:500] or None,
                "journal": (p.get("journal", "") or "")[:200] or None,
                "publication_date": pub_date,
                "source_url": p.get("source_url", ""),
                "pubmed_id": p.get("pmid") or None,
                "doi": p.get("doi") or None,
                "abstract_text": (p.get("abstract", "") or "")[:3000] or None,
                "key_findings": p.get("query_keyword"),
            })
        written = supabase_upsert("company_documents", rows)
        print(f"Preprint monitor: {written} documents written.")
        return

    # ── Drug-specific mode ────────────────────────────────────────────────────
    if args.drug:
        drug_name_enc = urllib.parse.quote(args.drug)
        drugs = supabase_get(
            "drugs",
            raw_qs=f"name=ilike.*{drug_name_enc}*&select=id,name,dev_code,target,stage,company_id&limit=5"
        )
        if not drugs:
            print(f"No drug found matching '{args.drug}'")
            return
    else:
        # All Phase 2+ drugs — use raw_qs to preserve in.(...) syntax unencoded
        stage_values = ",".join(TARGET_STAGES)
        qs = f"select=id,name,dev_code,target,stage,company_id&stage=in.({stage_values})&limit=80"
        drugs = supabase_get("drugs", raw_qs=qs)

    print(f"Processing {len(drugs)} drugs for abstract fetching...")
    total_written = 0
    drug_stats = []

    for drug in drugs:
        name = (drug.get("name") or "").strip()
        if not name or len(name) < 4:
            continue

        if args.verbose:
            print(f"\n[{drug.get('stage','')}] {name}")

        abstracts = fetch_abstracts_for_drug(
            name,
            target=drug.get("target"),
            verbose=args.verbose
        )

        if not abstracts:
            if args.verbose:
                print(f"  No abstracts found.")
            time.sleep(0.5)
            continue

        rows = [build_doc_row(ab, drug, name) for ab in abstracts
                if ab.get("title") and ab.get("source_url")]

        if args.dry_run:
            print(f"  [DRY RUN] {name}: {len(rows)} rows (not written)")
            drug_stats.append((name, len(rows)))
            time.sleep(0.5)
            continue

        written = supabase_upsert("company_documents", rows)
        total_written += written
        drug_stats.append((name, written))
        print(f"  {name}: {written} documents written")

        time.sleep(1)  # rate limit

    print(f"\nDone. {total_written} total documents written to company_documents.")

    if drug_stats:
        print("\nTop drugs by abstract count:")
        for drug_name, count in sorted(drug_stats, key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {count:3d}  {drug_name}")


if __name__ == "__main__":
    main()
