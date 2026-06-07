"""
Drug abstract sweep — business logic layer.

Fetches abstracts from Europe PMC and PubMed for a single drug or all
Phase 2+ drugs, deduplicates across sources, builds company_documents rows,
and delegates writes to document_repository.

No Supabase or HTTP details here — those live in sources/ and repositories/.
"""
import re
import time
from dataclasses import dataclass, field

from .repositories import drug_repository as drug_repo
from .repositories import document_repository as doc_repo
from .sources import europe_pmc, pubmed


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class DrugResult:
    drug_name: str
    written: int = 0
    skipped: bool = False   # drug name too short / not found


@dataclass
class DrugSweepResult:
    drug_results: list[DrugResult] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    @property
    def total_written(self) -> int:
        return sum(r.written for r in self.drug_results)


# ── Row builder ───────────────────────────────────────────────────────────────

def build_doc_row(ab: dict, drug: dict, drug_name: str) -> dict:
    """Convert a fetched abstract dict + drug record into a company_documents row."""
    pub_date = ab.get("pub_date") or None
    if pub_date and re.match(r'^\d{4}$', str(pub_date)):
        pub_date = f"{pub_date}-01-01"
    elif pub_date and re.match(r'^\d{4}-\w+$', str(pub_date)):
        pub_date = None  # month-name format not reliably parseable

    doc_type = "clinical_data" if "preprint" in (ab.get("source") or "") else "abstract"

    return {
        "company_id":       drug.get("company_id") or None,
        "drug_id":          drug.get("id") or None,
        "document_type":    doc_type,
        "title":            (ab.get("title", "") or "Untitled")[:400],
        "authors":          (ab.get("authors", "") or "")[:500] or None,
        "journal":          (ab.get("journal", "") or "")[:200] or None,
        "publication_date": pub_date,
        "source_url":       ab.get("source_url", ""),
        "pubmed_id":        ab.get("pmid") or None,
        "doi":              ab.get("doi") or None,
        "abstract_text":    (ab.get("abstract", "") or "")[:3000] or None,
        "drug_names":       [drug_name],
        "target":           (drug.get("target", "") or "")[:200] or None,
        "phase":            (drug.get("stage", "") or "")[:50] or None,
    }


# ── Per-drug collection ────────────────────────────────────────────────────────

def collect_for_drug(drug: dict, dry_run: bool = False, verbose: bool = False) -> DrugResult:
    name = (drug.get("name") or "").strip()
    result = DrugResult(drug_name=name)

    if not name or len(name) < 4:
        result.skipped = True
        return result

    abstracts = _fetch_and_dedup(name, drug.get("target"), verbose=verbose)
    if not abstracts:
        time.sleep(0.5)
        return result

    rows = [
        build_doc_row(ab, drug, name)
        for ab in abstracts
        if ab.get("title") and ab.get("source_url")
    ]

    if dry_run:
        result.written = len(rows)
        time.sleep(0.5)
        return result

    result.written = doc_repo.upsert_documents(rows)
    time.sleep(1)
    return result


def _fetch_and_dedup(
    drug_name: str,
    target: str | None,
    verbose: bool = False,
) -> list[dict]:
    queries = [drug_name]
    if target and target.strip():
        queries.append(f"{drug_name} {target}")

    seen: set[str] = set()
    results: list[dict] = []

    def _key(r: dict) -> str:
        return r.get("pmid") or r.get("source_url", "")

    for q in queries[:2]:
        if verbose:
            print(f"    EuropePMC: {q!r}")
        for pub in europe_pmc.search(q, max_results=6):
            k = _key(pub)
            if k and k not in seen:
                seen.add(k)
                results.append(pub)
        time.sleep(0.5)

        if verbose:
            print(f"    PubMed:    {q!r}")
        for pub in pubmed.search(q, max_results=4):
            k = _key(pub)
            if k and k not in seen:
                seen.add(k)
                results.append(pub)
        time.sleep(0.5)

    return results[:12]


# ── Full sweep ────────────────────────────────────────────────────────────────

def collect_all(dry_run: bool = False, verbose: bool = False) -> DrugSweepResult:
    result = DrugSweepResult()
    try:
        drugs = drug_repo.get_phase2_plus_drugs()
        print(f"Processing {len(drugs)} drugs for abstract fetching...")
        for drug in drugs:
            dr = collect_for_drug(drug, dry_run=dry_run, verbose=verbose)
            result.drug_results.append(dr)
            if dr.written > 0:
                verb = "[dry-run] would write" if dry_run else "wrote"
                print(f"  {dr.drug_name}: {verb} {dr.written} documents")
    except Exception as e:
        result.error = str(e)
    return result
