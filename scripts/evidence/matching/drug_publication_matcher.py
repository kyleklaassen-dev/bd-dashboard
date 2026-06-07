"""
Relevance guard for drug publications.

A publication is relevant if the drug's identifying name appears in the
combined title + abstract text. This prevents false positives where Europe
PMC returns papers that mention the drug name only in references or metadata.
"""
import re


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def is_relevant(drug_name: str, pub: dict) -> bool:
    """Return True if the publication mentions the drug in title or abstract."""
    needle = _normalize(drug_name)
    if not needle or len(needle) < 4:
        return False
    blob = _normalize(
        (pub.get("title") or "") + " " + (pub.get("abstractText") or "")
    )
    return needle in blob


def doi_url(pub: dict) -> str | None:
    doi = (pub.get("doi") or "").lower().strip()
    return f"https://doi.org/{doi}" if doi else None
