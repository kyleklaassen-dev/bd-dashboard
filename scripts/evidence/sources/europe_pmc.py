"""
Europe PMC search client.

Responsibilities:
  - Search publications by drug name
  - Search publications by disease phrase (with epidemiology filter)
  - Return raw result dicts; callers decide relevance
"""
import json
import urllib.parse
import urllib.request

from ..config import UA

_EPMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _fetch(query: str, page_size: int) -> list[dict]:
    q = urllib.parse.quote(query)
    req = urllib.request.Request(
        f"{_EPMC_API}?query={q}&format=json&pageSize={page_size}&resultType=core",
        headers={"User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)["resultList"]["result"]
    except Exception:
        return []


def search_by_drug(drug_name: str, page_size: int = 6) -> list[dict]:
    """Return publications mentioning the drug name. Raw EPMC result dicts."""
    return _fetch(f'"{drug_name}"', page_size=page_size)


def search_by_disease(phrase: str, page_size: int = 12) -> list[dict]:
    """Return publications about a disease, filtered to epidemiology/burden papers."""
    return _fetch(
        f'"{phrase}" AND (epidemiology OR prevalence OR incidence OR burden)',
        page_size=page_size,
    )
