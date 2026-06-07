"""
Europe PMC search client — rich publication records.

Returns structured dicts with pmid, doi, title, authors, journal,
pub_date, abstract, is_conference, source_url, and source tag.
These are richer than the simpler URL-only variant in scripts/evidence/sources/europe_pmc.py,
which serves a different purpose (drug source backfill).
"""
import json
import urllib.parse
import urllib.request

from ..config import UA

_EPMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def search(query: str, max_results: int = 10) -> list[dict]:
    """
    Search Europe PMC and return rich publication dicts, sorted by date descending.
    Skips results with no stable URL (no pmid and no doi).
    """
    encoded = urllib.parse.quote(query)
    url = (
        f"{_EPMC_API}"
        f"?query={encoded}&format=json&pageSize={max_results}"
        f"&sort=date&resultType=core"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
    except Exception as e:
        print(f"  EuropePMC error for {query!r}: {e}")
        return []

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
            continue

        authors_raw = item.get("authorList", {}).get("author", [])
        authors = ", ".join(a.get("fullName", "") for a in authors_raw[:5])
        if len(authors_raw) > 5:
            authors += " et al."

        results.append({
            "pmid":          pmid or None,
            "doi":           doi or None,
            "title":         (item.get("title", "") or "")[:400],
            "authors":       authors[:500],
            "journal":       (item.get("journalTitle", "")
                              or item.get("bookOrReportDetails", {}).get("publisher", ""))[:200],
            "pub_date":      item.get("firstPublicationDate") or None,
            "abstract":      (item.get("abstractText", "") or "")[:3000],
            "is_conference": is_conference,
            "source_url":    source_url,
            "source":        "europepmc",
        })

    return results
