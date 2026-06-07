"""
Relevance filtering and scoring for disease/epidemiology publications.

A publication passes if:
  1. It has a real DOI
  2. The disease relevance token appears in the normalized title + abstract

Survivors are scored: epidemiology/burden titles rank above generic ones.
Returns de-duplicated (url, title) pairs, best-first, up to max_results.
"""
import re

from ..config import EPMC_PREF_TERMS


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower())


def filter_and_rank(
    pubs: list[dict],
    relevance_token: str,
    max_results: int = 2,
) -> list[tuple[str, str]]:
    """
    Return (url, title) pairs that mention relevance_token, sorted so
    epidemiology/prevalence titles come first.
    """
    token = _normalize(relevance_token)
    scored: list[tuple[int, str, str]] = []

    for pub in pubs:
        doi = (pub.get("doi") or "").lower().strip()
        if not doi:
            continue
        title = pub.get("title") or ""
        blob = _normalize(title + " " + (pub.get("abstractText") or ""))
        if token not in blob:
            continue
        pref = any(p in title.lower() for p in EPMC_PREF_TERMS)
        scored.append((0 if pref else 1, f"https://doi.org/{doi}", title))

    scored.sort(key=lambda s: s[0])

    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _, url, title in scored:
        if url in seen:
            continue
        seen.add(url)
        out.append((url, title))
        if len(out) >= max_results:
            break

    return out
