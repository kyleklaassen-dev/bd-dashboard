"""
Patient evidence source backfill — business logic layer.

Walks indication_patient_intelligence rows that have no real source URLs,
searches Europe PMC for epidemiology papers per mapped disease, and patches
source_urls on matching rows.

Rows are skipped when:
  - They already have a real source URL (idempotent)
  - The indication name is not in DISEASE_MAP (analytical aggregates, broad
    target areas — these are not single diseases and must not be sourced
    with a single disease paper)
"""
import time
from dataclasses import dataclass, field

from .config import DISEASE_MAP
from .repositories import patient_intel_repository as patient_repo
from .sources import europe_pmc
from .matching import disease_publication_matcher as disease_matcher


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class RowResult:
    row_id: str
    indication_name: str
    urls_added: int = 0
    skipped_existing: bool = False
    skipped_aggregate: bool = False
    no_hits: bool = False


@dataclass
class PatientEvidenceResult:
    row_results: list[RowResult] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    @property
    def sourced(self) -> int:
        return sum(1 for r in self.row_results if r.urls_added > 0)

    @property
    def skipped_aggregates(self) -> list[str]:
        return [r.indication_name for r in self.row_results if r.skipped_aggregate]

    @property
    def no_hits_names(self) -> list[str]:
        return [r.indication_name for r in self.row_results if r.no_hits]


# ── Collection ────────────────────────────────────────────────────────────────

def collect_all(dry_run: bool = False) -> PatientEvidenceResult:
    result = PatientEvidenceResult()
    try:
        rows = patient_repo.get_all_rows()
        for row in rows:
            rr = _process_row(row, dry_run=dry_run)
            result.row_results.append(rr)
    except Exception as e:
        result.error = str(e)
    return result


def _has_real_url(source_urls) -> bool:
    return isinstance(source_urls, list) and any(
        str(u).startswith("http") for u in source_urls
    )


def _process_row(row: dict, dry_run: bool) -> RowResult:
    row_id = row["id"]
    name = row.get("indication_name") or ""
    rr = RowResult(row_id=row_id, indication_name=name)

    if _has_real_url(row.get("source_urls")):
        rr.skipped_existing = True
        return rr

    if name not in DISEASE_MAP:
        rr.skipped_aggregate = True
        return rr

    phrase, token = DISEASE_MAP[name]
    pubs = europe_pmc.search_by_disease(phrase)
    time.sleep(0.2)

    hits = disease_matcher.filter_and_rank(pubs, token)
    if not hits:
        rr.no_hits = True
        return rr

    urls = [url for url, _ in hits]
    if not dry_run:
        patient_repo.patch_source_urls(row_id, urls)

    rr.urls_added = len(urls)
    return rr
