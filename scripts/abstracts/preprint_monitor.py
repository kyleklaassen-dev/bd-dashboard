"""
Preprint monitor sweep — business logic layer.

Searches bioRxiv and medRxiv for recent preprints matching tracked keywords,
deduplicates across keyword groups, builds company_documents rows, and
delegates writes to document_repository.
"""
import re
import time
from dataclasses import dataclass, field

from .config import PREPRINT_KEYWORDS
from .repositories import document_repository as doc_repo
from .sources import preprint as preprint_src


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class PreprintResult:
    found: int = 0
    written: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


# ── Row builder ───────────────────────────────────────────────────────────────

def build_preprint_row(p: dict) -> dict | None:
    """Convert a preprint search result into a company_documents row."""
    if not p.get("title"):
        return None

    pub_date = p.get("pub_date") or None
    if pub_date and re.match(r'^\d{4}$', str(pub_date)):
        pub_date = f"{pub_date}-01-01"

    return {
        "document_type":  "other",
        "title":          p["title"][:400],
        "authors":        (p.get("authors", "") or "")[:500] or None,
        "journal":        (p.get("journal", "") or "")[:200] or None,
        "publication_date": pub_date,
        "source_url":     p.get("source_url", ""),
        "pubmed_id":      p.get("pmid") or None,
        "doi":            p.get("doi") or None,
        "abstract_text":  (p.get("abstract", "") or "")[:3000] or None,
        "key_findings":   p.get("query_keyword"),
    }


# ── Collection ────────────────────────────────────────────────────────────────

def collect(
    keywords: list[str] | None = None,
    dry_run: bool = False,
) -> PreprintResult:
    result = PreprintResult()
    try:
        kws = keywords or PREPRINT_KEYWORDS
        all_preprints = _sweep(kws)
        result.found = len(all_preprints)
        print(f"Preprint monitor: found {result.found} unique preprints across {len(kws)} keyword groups.")

        rows = [r for p in all_preprints if (r := build_preprint_row(p)) is not None]

        if dry_run:
            print(f"  [dry-run] would write {len(rows)} preprint rows")
            for p in all_preprints[:5]:
                print(f"    {p.get('title', '')[:80]}")
            result.written = len(rows)
            return result

        result.written = doc_repo.upsert_documents(rows)
        print(f"  {result.written} preprint documents written.")
    except Exception as e:
        result.error = str(e)
    return result


def _sweep(keywords: list[str]) -> list[dict]:
    """Search each keyword group, deduplicate by source_url, return all hits."""
    seen: set[str] = set()
    results: list[dict] = []

    for kw in keywords:
        hits = preprint_src.search(kw, max_results=3)
        for h in hits:
            url = h.get("source_url", "")
            if url and url not in seen:
                seen.add(url)
                h["query_keyword"] = kw
                results.append(h)
        time.sleep(0.4)

    return results
