"""
Preprint source client (bioRxiv / medRxiv).

Europe PMC indexes bioRxiv and medRxiv. The SRC:PPR filter restricts results
to preprints only. Returns the same rich dict shape as europe_pmc.search()
with source overridden to "preprint".
"""
from . import europe_pmc


def search(query: str, max_results: int = 5) -> list[dict]:
    """
    Search for preprints matching query.
    Wraps Europe PMC with SRC:PPR to restrict to bioRxiv/medRxiv.
    """
    results = europe_pmc.search(f"({query}) SRC:PPR", max_results=max_results)
    for r in results:
        r["source"] = "preprint"
    return results
