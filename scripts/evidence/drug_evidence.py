"""
Drug evidence source backfill — business logic layer.

Orchestrates the two source types (CT.gov trial registrations and Europe PMC
publications) for a single drug or all drugs in an area.

This module knows nothing about HTTP or Supabase directly; it delegates to
sources/ (external APIs) and repositories/ (Supabase reads/writes).
"""
import time
from dataclasses import dataclass, field

from .repositories import drug_repository as drug_repo
from .repositories import drug_source_repository as source_repo
from .sources import ctgov, europe_pmc
from .matching import drug_publication_matcher as pub_matcher


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class DrugResult:
    drug_id: str
    ctgov_added: int = 0
    pubs_added: int = 0
    skipped: bool = False   # drug not found in DB

    @property
    def total(self) -> int:
        return self.ctgov_added + self.pubs_added


@dataclass
class AreaResult:
    area: str
    drug_results: list[DrugResult] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    @property
    def total_sources(self) -> int:
        return sum(r.total for r in self.drug_results)

    @property
    def drugs_with_new_sources(self) -> int:
        return sum(1 for r in self.drug_results if r.total > 0)


# ── Per-drug collection ────────────────────────────────────────────────────────

def collect_for_drug(
    drug_id: str,
    max_pubs: int = 3,
    dry_run: bool = False,
) -> DrugResult:
    result = DrugResult(drug_id=drug_id)

    drug = drug_repo.get_drug(drug_id)
    if not drug:
        result.skipped = True
        return result

    name = drug.get("display_name") or drug.get("name") or drug_id
    trials = drug_repo.get_trials_for_drug(drug_id)
    existing = source_repo.get_existing_source_urls(drug_id)

    # CT.gov trial registrations
    ctgov_rows = _build_ctgov_rows(drug_id, name, trials, existing)
    if ctgov_rows and not dry_run:
        source_repo.insert_sources(ctgov_rows)
    result.ctgov_added = len(ctgov_rows)

    # Europe PMC publications
    pub_rows = _build_pub_rows(drug, name, existing, max_pubs)
    if pub_rows and not dry_run:
        source_repo.insert_sources(pub_rows)
    result.pubs_added = len(pub_rows)

    return result


def _build_ctgov_rows(
    drug_id: str,
    drug_name: str,
    trials: list[dict],
    existing: set[str],
) -> list[dict]:
    rows = []
    for trial in trials:
        nct = trial.get("id")
        if not ctgov.is_valid_nct(nct):
            continue
        url = ctgov.study_url(nct)
        if url in existing:
            continue
        if not ctgov.verify_nct(nct):
            continue
        phase = trial.get("phase") or "Trial"
        indication = trial.get("indication") or ""
        claim = (f"{phase} trial" + (f" in {indication}" if indication else "") + f" ({nct})")[:300]
        rows.append({
            "drug_id":               drug_id,
            "drug_name":             drug_name,
            "claim_type":            "trial_registration",
            "claim_value":           claim,
            "source_url":            url,
            "source_type":           "ct_gov",
            "source_domain":         "clinicaltrials.gov",
            "content_confirms_claim": True,
            "confidence":            "confirmed",
            "added_by":              "evidence/drug_evidence",
            "session_label":         source_repo.SESSION_LABEL,
        })
        existing.add(url)
        time.sleep(0.1)
    return rows


def _build_pub_rows(
    drug: dict,
    drug_name: str,
    existing: set[str],
    max_pubs: int,
) -> list[dict]:
    drug_id = drug["id"]
    search_terms = [t for t in {drug_name, drug.get("name")} if t and len(str(t)) > 3]
    rows: list[dict] = []

    for term in search_terms[:2]:
        if len(rows) >= max_pubs:
            break
        pubs = europe_pmc.search_by_drug(term)
        for pub in pubs:
            if len(rows) >= max_pubs:
                break
            url = pub_matcher.doi_url(pub)
            if not url or url in existing:
                continue
            if not pub_matcher.is_relevant(drug_name, pub):
                continue
            rows.append({
                "drug_id":               drug_id,
                "drug_name":             drug_name,
                "claim_type":            "publication",
                "claim_value":           (pub.get("title") or "")[:300],
                "source_url":            url,
                "source_type":           "publication",
                "source_domain":         "doi.org",
                "content_confirms_claim": True,
                "confidence":            "inferred",
                "added_by":              "evidence/drug_evidence",
                "session_label":         source_repo.SESSION_LABEL,
            })
            existing.add(url)
        time.sleep(0.15)

    return rows


# ── Per-area collection ────────────────────────────────────────────────────────

def collect_for_area(
    area: str,
    limit: int = 0,
    max_pubs: int = 3,
    dry_run: bool = False,
) -> AreaResult:
    result = AreaResult(area=area)
    try:
        drug_ids = drug_repo.get_drug_ids_for_area(area)
        if limit:
            drug_ids = drug_ids[:limit]
        for drug_id in drug_ids:
            dr = collect_for_drug(drug_id, max_pubs=max_pubs, dry_run=dry_run)
            result.drug_results.append(dr)
    except Exception as e:
        result.error = str(e)
    return result
