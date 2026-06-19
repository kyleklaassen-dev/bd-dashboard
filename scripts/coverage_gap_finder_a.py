#!/usr/bin/env python3
"""coverage_gap_finder_a.py — gap checks 1-5 (§3 split): low coverage, missing
molecule_intelligence, missing drug_indications, missing catalysts, deals w/o partnerships."""
from typing import Dict

from coverage_gap_base import (
    sb_get, table_exists, log, is_clinical, write_queue_item,
    PRIORITY_P0, PRIORITY_P1, PRIORITY_P2, PRIORITY_P3,
)


# ── Gap 1: Low coverage score ────────────────────────────────────────────────

def gap_low_coverage_score() -> Dict:
    log("Gap 1: Low coverage_score drugs (<40)", indent=1)
    results = {"found": 0, "queued": 0}

    try:
        low_drugs = sb_get("coverage_scores", {
            "entity_type": "eq.drug",
            "overall_score": "lt.40",
            "select": "entity_id,overall_score",
            "order": "overall_score.asc",
            "limit": "100",
        })
        results["found"] = len(low_drugs)
        log(f"  Drugs with coverage_score < 40: {len(low_drugs)}", indent=2)

        # Load drug details for context
        drug_ids = [r["entity_id"] for r in low_drugs]
        drugs_meta: Dict[str, dict] = {}
        if drug_ids:
            try:
                drugs = sb_get("drugs", {
                    "select": "id,name,stage,overlap",
                    "limit": "200",
                })
                for d in drugs:
                    if d["id"] in drug_ids:
                        drugs_meta[d["id"]] = d
            except Exception:
                pass

        for score_row in low_drugs:
            eid = score_row["entity_id"]
            score = score_row.get("overall_score", 0)
            drug = drugs_meta.get(eid, {})
            overlap = drug.get("overlap") or "unknown"
            stage = drug.get("stage") or "unknown"

            # Priority based on overlap and stage
            if overlap in ("Direct", "Adjacent") and is_clinical(stage):
                priority = PRIORITY_P0
            elif overlap in ("Direct", "Adjacent"):
                priority = PRIORITY_P1
            elif is_clinical(stage):
                priority = PRIORITY_P1
            else:
                priority = PRIORITY_P2

            write_queue_item(
                entity_type="drug",
                entity_id=eid,
                gap_type="low_coverage_score",
                priority=priority,
                reason=f"coverage_score={score}, overlap={overlap}, stage={stage}",
            )
            results["queued"] += 1

    except Exception as e:
        log(f"  Low coverage check failed: {e}", indent=2)

    log(f"  Queued: {results['queued']}", indent=2)
    return results


# ── Gap 2: Missing molecule_intelligence ────────────────────────────────────

def gap_missing_molecule_intelligence() -> Dict:
    log("Gap 2: Missing molecule_intelligence rows", indent=1)
    results = {"found": 0, "queued": 0}

    if not table_exists("molecule_intelligence"):
        log("  molecule_intelligence not found — skipping", indent=2)
        return {"skipped": "table_missing"}

    try:
        # All drugs
        all_drugs = sb_get("drugs", {
            "select": "id,name,stage,overlap",
            "limit": "500",
        })
        drug_ids = {d["id"] for d in all_drugs}
        drug_map = {d["id"]: d for d in all_drugs}

        # All molecule_intelligence rows
        mol_rows = sb_get("molecule_intelligence", {
            "select": "drug_id",
            "limit": "500",
        })
        mol_drug_ids = {r.get("drug_id") for r in mol_rows if r.get("drug_id")}

        missing = drug_ids - mol_drug_ids
        results["found"] = len(missing)
        log(f"  Drugs missing molecule_intelligence row: {len(missing)}", indent=2)

        for drug_id in missing:
            drug = drug_map.get(drug_id, {})
            overlap = drug.get("overlap") or "unknown"
            stage = drug.get("stage") or "unknown"

            priority = (
                PRIORITY_P1 if overlap in ("Direct", "Adjacent") else PRIORITY_P2
            )
            write_queue_item(
                entity_type="drug",
                entity_id=drug_id,
                gap_type="missing_molecule_intelligence",
                priority=priority,
                reason=f"No molecule_intelligence row. overlap={overlap}, stage={stage}",
            )
            results["queued"] += 1

    except Exception as e:
        log(f"  Molecule intelligence gap check failed: {e}", indent=2)

    log(f"  Queued: {results['queued']}", indent=2)
    return results


# ── Gap 3: Missing drug_indications ─────────────────────────────────────────

def gap_missing_drug_indications() -> Dict:
    log("Gap 3: Missing drug_indications rows", indent=1)
    results = {"found": 0, "queued": 0}

    if not table_exists("drug_indications"):
        log("  drug_indications not found — skipping", indent=2)
        return {"skipped": "table_missing"}

    try:
        all_drugs = sb_get("drugs", {
            "select": "id,name,stage,overlap",
            "limit": "500",
        })
        drug_map = {d["id"]: d for d in all_drugs}
        drug_ids = set(drug_map.keys())

        di_rows = sb_get("drug_indications", {
            "select": "drug_id",
            "limit": "1000",
        })
        covered_ids = {r.get("drug_id") for r in di_rows if r.get("drug_id")}

        missing = drug_ids - covered_ids
        results["found"] = len(missing)
        log(f"  Drugs missing drug_indications rows: {len(missing)}", indent=2)

        for drug_id in missing:
            drug = drug_map.get(drug_id, {})
            overlap = drug.get("overlap") or "unknown"
            stage = drug.get("stage") or "unknown"

            priority = (
                PRIORITY_P1 if is_clinical(stage) else PRIORITY_P2
            )
            write_queue_item(
                entity_type="drug",
                entity_id=drug_id,
                gap_type="missing_drug_indications",
                priority=priority,
                reason=f"No drug_indications rows. stage={stage}, overlap={overlap}",
            )
            results["queued"] += 1

    except Exception as e:
        log(f"  Drug indications gap check failed: {e}", indent=2)

    log(f"  Queued: {results['queued']}", indent=2)
    return results


# ── Gap 4: Missing catalyst_calendar for Phase 2/3 ──────────────────────────

def gap_missing_catalyst_entries() -> Dict:
    log("Gap 4: Missing catalyst_calendar for Phase 2/3 drugs", indent=1)
    results = {"found": 0, "queued": 0}

    if not table_exists("catalyst_calendar"):
        log("  catalyst_calendar not found — skipping", indent=2)
        return {"skipped": "table_missing"}

    try:
        # Phase 2/3 drugs
        clinical_drugs = sb_get("drugs", {
            "select": "id,name,stage,overlap",
            "limit": "300",
        })
        clinical_drugs = [d for d in clinical_drugs if is_clinical(d.get("stage") or "")]
        clinical_ids = {d["id"] for d in clinical_drugs}
        drug_map = {d["id"]: d for d in clinical_drugs}

        # Catalyst entries
        cats = sb_get("catalyst_calendar", {
            "select": "drug_id",
            "limit": "500",
        })
        covered_ids: Set[str] = set()
        for cat in cats:
            for field in ["drug_id"]:
                val = cat.get(field)
                if val:
                    covered_ids.add(str(val))

        missing = clinical_ids - covered_ids
        results["found"] = len(missing)
        log(f"  Phase 2/3 drugs missing catalyst_calendar entry: {len(missing)}", indent=2)

        for drug_id in missing:
            drug = drug_map.get(drug_id, {})
            overlap = drug.get("overlap") or "unknown"
            stage = drug.get("stage") or "unknown"

            priority = (
                PRIORITY_P1 if overlap in ("Direct", "Adjacent") else PRIORITY_P2
            )
            write_queue_item(
                entity_type="drug",
                entity_id=drug_id,
                gap_type="missing_catalyst_calendar",
                priority=priority,
                reason=f"Clinical stage drug with no catalyst entry. stage={stage}, overlap={overlap}",
            )
            results["queued"] += 1

    except Exception as e:
        log(f"  Catalyst calendar gap check failed: {e}", indent=2)

    log(f"  Queued: {results['queued']}", indent=2)
    return results


# ── Gap 5: Missing company_partnerships when deal exists ─────────────────────

def gap_deals_without_partnerships() -> Dict:
    log("Gap 5: Deals without corresponding company_partnerships row", indent=1)
    results = {"deals_checked": 0, "gaps": 0, "queued": 0}

    try:
        deals = sb_get("deals", {
            "select": "id,drug_name,company_id,partner_company,deal_type",
            "limit": "300",
        })
        results["deals_checked"] = len(deals)

        # Load all partnerships
        partnerships = sb_get("company_partnerships", {
            "select": "id,company_id,partner_company_id",
            "limit": "1000",
        })
        partner_set: Set[tuple] = set()
        for p in partnerships:
            a = (p.get("company_id") or "").lower()
            b = (p.get("partner_company_id") or "").lower()
            if a and b:
                partner_set.add((a, b))
                partner_set.add((b, a))

        for deal in deals:
            co_id = (deal.get("company_id") or "").lower()
            partner = (deal.get("partner_company") or "").lower()
            if not co_id or not partner:
                continue

            # Check by company_id (exact) — if partner is a company ID
            if (co_id, partner) not in partner_set:
                log(
                    f"  GAP: deal '{deal.get('drug_name')}' "
                    f"{co_id} ↔ {partner} has no partnership row",
                    indent=2
                )
                write_queue_item(
                    entity_type="deal",
                    entity_id=str(deal["id"]),
                    gap_type="deal_missing_partnership_row",
                    priority=PRIORITY_P2,
                    reason=(
                        f"Deal '{deal.get('drug_name')}' involves "
                        f"{co_id} ↔ {partner} but no company_partnerships row found"
                    ),
                )
                results["gaps"] += 1
                results["queued"] += 1

    except Exception as e:
        log(f"  Deal/partnership gap check failed: {e}", indent=2)

    log(f"  Gaps found: {results['gaps']}", indent=2)
    return results
