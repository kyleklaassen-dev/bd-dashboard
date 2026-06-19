#!/usr/bin/env python3
"""consistency_checks_fields.py — single-entity field checks 1-4 (§3 split):
stage-vs-trials, brand-without-approval, company_id originator, duplicate entities."""
import difflib
from collections import defaultdict
from typing import Dict, List

from consistency_base import (
    sb_get, table_exists, log, stage_rank, normalize_stage,
    write_contradiction_typed, write_gov_violation, VALID_APPROVED,
)


# ── Check 1: Drug stage vs trials ─────────────────────────────────────────────

def check_stage_vs_trials() -> Dict:
    log("Check 1: Drug stage vs trials phase", indent=1)
    results = {"checked": 0, "contradictions": 0}

    # NOTE: phase data lives in the `trials` table (id, drug_id, phase, status).
    # `trial_registries` is a registry-search tracker with no phase column —
    # querying it returned HTTP 400, silently disabling this check.
    if not table_exists("trials"):
        log("  trials not found — skipping", indent=2)
        return {"skipped": "table_missing"}

    try:
        # Load per-trial data with drug_id and phase (681 rows as of 2026-06;
        # limit covers the full table to avoid silently checking a subset).
        reg_rows = sb_get("trials", {
            "select": "id,drug_id,phase,status",
            "limit": "1000",
        })
        # Index: drug_id → [phases]
        trial_phases: Dict[str, List[str]] = defaultdict(list)
        for r in reg_rows:
            did = r.get("drug_id")
            phase = r.get("phase")
            if did and phase:
                trial_phases[did].append(phase.lower())

        # Load drugs
        drugs = sb_get("drugs", {
            "select": "id,name,stage",
            "limit": "500",
        })

        for drug in drugs:
            did = drug["id"]
            drug_stage = normalize_stage(drug.get("stage") or "")
            trial_ps = trial_phases.get(did)
            if not trial_ps or not drug_stage:
                continue

            results["checked"] += 1

            # Find most advanced trial phase
            max_trial_rank = max((stage_rank(tp) for tp in trial_ps), default=-1)
            drug_rank = stage_rank(drug_stage)

            # Contradiction: trial shows higher phase than drug record
            # (allow ±1 difference as noise)
            if max_trial_rank > drug_rank + 1 and max_trial_rank >= 0:
                best_trial_phase = max(trial_ps, key=lambda p: stage_rank(p))
                log(
                    f"  MISMATCH: {drug.get('name')} — "
                    f"drugs.stage={drug.get('stage')} but "
                    f"trial shows phase={best_trial_phase}",
                    indent=2
                )
                write_contradiction_typed(
                    entity_id=did,
                    entity_type="drug",
                    field_name="stage",
                    value_a=drug.get("stage"),
                    value_b=best_trial_phase,
                    contradiction_type="stage_vs_trial",
                    severity="warning",
                )
                results["contradictions"] += 1

    except Exception as e:
        log(f"  Stage vs trial check failed: {e}", indent=2)

    log(f"  Checked: {results['checked']}, contradictions: {results['contradictions']}", indent=2)
    return results


# ── Check 2: Brand name without approval ──────────────────────────────────────

def check_brand_name_without_approval() -> Dict:
    log("Check 2: Brand name without approval stage", indent=1)
    results = {"checked": 0, "contradictions": 0}

    try:
        branded = sb_get("drugs", {
            "select": "id,name,brand_name,stage",
            "brand_name": "not.is.null",
            "limit": "200",
        })
        results["checked"] = len(branded)
        for drug in branded:
            stage = (drug.get("stage") or "").lower()
            brand = drug.get("brand_name") or ""
            # Skip if brand_name is a dash placeholder
            if brand.strip() in ("—", "-", "–", ""):
                continue
            if stage not in VALID_APPROVED:
                log(
                    f"  VIOLATION: {drug.get('name')} has brand_name='{brand}' "
                    f"but stage='{stage}' (must be approved)",
                    indent=2
                )
                write_contradiction_typed(
                    entity_id=drug["id"],
                    entity_type="drug",
                    field_name="brand_name+stage",
                    value_a=brand,
                    value_b=stage,
                    contradiction_type="brand_name_without_approval",
                    severity="critical",
                )
                write_gov_violation(
                    "brand_name_implies_approved",
                    "drug",
                    drug["id"],
                    f"brand_name='{brand}' but stage='{stage}' — brand name implies approved"
                )
                results["contradictions"] += 1
    except Exception as e:
        log(f"  Brand name check failed: {e}", indent=2)

    log(f"  Checked: {results['checked']}, contradictions: {results['contradictions']}", indent=2)
    return results


# ── Check 3: company_id originator rule ──────────────────────────────────────

def check_company_id_originator() -> Dict:
    log("Check 3: company_id originator rule", indent=1)
    results = {"checked": 0, "potential_violations": 0}

    try:
        # Load deals with drug_name and company references
        deals = sb_get("deals", {
            "select": "id,drug_name,company_id,partner_company,deal_type",
            "limit": "300",
        })

        # Load drugs indexed by name
        drugs = sb_get("drugs", {
            "select": "id,name,company_id",
            "limit": "500",
        })
        drug_by_name: Dict[str, dict] = {}
        for d in drugs:
            n = (d.get("name") or "").lower().strip()
            if n:
                drug_by_name[n] = d

        results["checked"] = len(deals)

        for deal in deals:
            drug_name = (deal.get("drug_name") or "").lower().strip()
            deal_company_id = deal.get("company_id") or ""

            # Find matching drug
            drug = drug_by_name.get(drug_name)
            if not drug:
                continue

            drug_company_id = drug.get("company_id") or ""

            # Contradiction: deal.company_id differs from drug.company_id
            # and there's no obvious licensing relationship implied
            if (
                deal_company_id
                and drug_company_id
                and deal_company_id.lower() != drug_company_id.lower()
                and deal.get("deal_type") not in ("licensing", "sublicensing", "option")
            ):
                log(
                    f"  POTENTIAL VIOLATION: deal for '{deal.get('drug_name')}' — "
                    f"deal.company_id={deal_company_id} but drug.company_id={drug_company_id}",
                    indent=2
                )
                write_contradiction_typed(
                    entity_id=drug["id"],
                    entity_type="drug",
                    field_name="company_id",
                    value_a=f"{drug_company_id} (drug) vs {deal_company_id} (deal {deal['id']})",
                    value_b=deal_company_id,
                    contradiction_type="company_id_originator_mismatch",
                    severity="warning",
                )
                results["potential_violations"] += 1

    except Exception as e:
        log(f"  company_id originator check failed: {e}", indent=2)

    log(f"  Checked: {results['checked']}, potential violations: {results['potential_violations']}", indent=2)
    return results


# ── Check 4: Duplicate entity detection ──────────────────────────────────────

def check_duplicate_entities() -> Dict:
    log("Check 4: Duplicate entity detection (>85% name similarity)", indent=1)
    results = {"drug_pairs": 0, "company_pairs": 0}
    THRESHOLD = 0.85

    def find_near_duplicates(records: List[dict], id_field: str, name_field: str,
                             threshold: float, entity_type: str) -> int:
        pairs_found = 0
        items = [
            (str(r[id_field]), (r.get(name_field) or "").lower().strip())
            for r in records if r.get(name_field)
        ]
        for i, (id1, n1) in enumerate(items):
            if not n1:
                continue
            for id2, n2 in items[i + 1:]:
                if not n2 or id1 == id2:
                    continue
                ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
                if ratio >= threshold and n1 != n2:
                    log(
                        f"  DUPLICATE CANDIDATE: {entity_type} '{n1}' ↔ '{n2}' "
                        f"(similarity={ratio:.2f})",
                        indent=2
                    )
                    write_contradiction_typed(
                        entity_id=id1,
                        entity_type=entity_type,
                        field_name="name",
                        value_a=n1,
                        value_b=f"possible_duplicate:{id2}:{n2}",
                        contradiction_type="duplicate_entity",
                        severity="warning",
                        resolution="needs_review",
                    )
                    pairs_found += 1
        return pairs_found

    try:
        drugs = sb_get("drugs", {"select": "id,name", "limit": "500"})
        results["drug_pairs"] = find_near_duplicates(
            drugs, "id", "name", THRESHOLD, "drug"
        )
        log(f"  Drug duplicate candidates: {results['drug_pairs']}", indent=2)
    except Exception as e:
        log(f"  Drug duplicate check failed: {e}", indent=2)

    try:
        companies = sb_get("companies", {"select": "id,name", "limit": "500"})
        results["company_pairs"] = find_near_duplicates(
            companies, "id", "name", THRESHOLD, "company"
        )
        log(f"  Company duplicate candidates: {results['company_pairs']}", indent=2)
    except Exception as e:
        log(f"  Company duplicate check failed: {e}", indent=2)

    return results
