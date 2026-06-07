"""
PubMed search client.

Uses the NCBI E-utilities: esearch to get PMIDs, then efetch to retrieve
structured XML records. Returns the same dict shape as europe_pmc.search()
so callers can merge results from both sources uniformly.
"""
import json
import re
import urllib.parse
import urllib.request

from ..config import UA

_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def search(query: str, max_results: int = 5) -> list[dict]:
    """
    Search PubMed and return structured publication dicts.
    Returns same shape as europe_pmc.search().
    """
    pmids = _esearch(query, max_results)
    if not pmids:
        return []
    return _efetch(pmids)


def _esearch(query: str, max_results: int) -> list[str]:
    encoded = urllib.parse.quote(query)
    url = (
        f"{_ESEARCH}"
        f"?db=pubmed&term={encoded}&retmax={max_results}"
        f"&retmode=json&sort=date"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        return data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"  PubMed esearch error for {query!r}: {e}")
        return []


def _efetch(pmids: list[str]) -> list[dict]:
    ids_str = ",".join(pmids)
    url = f"{_EFETCH}?db=pubmed&id={ids_str}&rettype=xml&retmode=xml"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            xml = r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  PubMed efetch error: {e}")
        return []

    results = []
    for art in re.findall(r'<PubmedArticle>(.*?)</PubmedArticle>', xml, re.DOTALL):
        pmid_m  = re.search(r'<PMID[^>]*>(\d+)</PMID>', art)
        title_m = re.search(r'<ArticleTitle>(.*?)</ArticleTitle>', art, re.DOTALL)
        abs_m   = re.search(r'<AbstractText[^>]*>(.*?)</AbstractText>', art, re.DOTALL)
        jrnl_m  = re.search(r'<Title>(.*?)</Title>', art)
        year_m  = re.search(r'<PubDate>.*?<Year>(\d{4})</Year>', art, re.DOTALL)
        month_m = re.search(r'<PubDate>.*?<Month>(\w+)</Month>', art, re.DOTALL)

        pmid = pmid_m.group(1) if pmid_m else ""
        if not pmid:
            continue
        title = re.sub(r'<[^>]+>', '', title_m.group(1) if title_m else "")[:400]
        if not title:
            continue

        year  = year_m.group(1) if year_m else ""
        month = month_m.group(1) if month_m else ""
        pub_date = f"{year}-{month}-01" if year and month else (year or None)

        results.append({
            "pmid":          pmid,
            "doi":           None,
            "title":         title,
            "authors":       "",
            "journal":       re.sub(r'<[^>]+>', '', jrnl_m.group(1) if jrnl_m else "")[:200],
            "pub_date":      pub_date,
            "abstract":      re.sub(r'<[^>]+>', '', abs_m.group(1) if abs_m else "")[:3000],
            "is_conference": False,
            "source_url":    f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "source":        "pubmed",
        })

    return results
