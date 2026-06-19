#!/usr/bin/env python3
"""coverage_gap_finder_b.py — gap checks 6-9 (§3 split): phantom companies,
unverified relationships, null bd_angle, null risk_summary."""
from typing import Dict

from coverage_gap_base import (
    sb_get, table_exists, log, is_clinical, write_queue_item,
    PRIORITY_P0, PRIORITY_P1, PRIORITY_P2, PRIORITY_P3,
)


# ── Gap 6: Phantom companies ─────────────────────────────────────────────────

def gap_phantom_companies() -> Dict:
    log("Gap 6: Phantom companies (no drugs, no partnerships)", indent=1)
    results = {"found": 0, "queued": 0}

    try:
        companies = sb_get("companies", {
            "select": "id,name,status",
            "limit": "500",
        })
        co_ids = {c["id"] for c in companies}
        co_map = {c["id"]: c for c in companies}

        # Company IDs that appear in drugs
        drugs = sb_get("drugs", {
            "select": "company_id",
            "limit": "1000",
        })
        drugs_co_ids = {d.get("company_id") for d in drugs if d.get("company_id")}

        # Company IDs in partnerships
        partnerships = sb_get("company_partnerships", {
            "select": "company_id,partner_company_id",
            "limit": "1000",
        })
        partner_co_ids: Set[str] = set()
        for p in partnerships:
            if p.get("company_id"):
                partner_co_ids.add(p["company_id"])
            if p.get("partner_company_id"):
                partner_co_ids.add(p["partner_company_id"])

        active_ids = drugs_co_ids | partner_co_ids
        phantoms = co_ids - active_ids
        results["found"] = len(phantoms)
        log(f"  Phantom companies (no drugs, no partnerships): {len(phantoms)}", indent=2)

        for co_id in phantoms:
            co = co_map.get(co_id, {})
            status = co.get("status") or "unknown"
            if status == "acquired":
                # Acquired companies with no drugs = expected (drug folded to acquirer)
                continue
            write_queue_item(
                entity_type="company",
                entity_id=co_id,
                gap_type="phantom_company",
                priority=PRIORITY_P3,
                reason=(
                    f"Company '{co.get('name')}' (status={status}) has no drugs and "
                    f"no partnership rows — may be orphaned record"
                ),
            )
            results["queued"] += 1

    except Exception as e:
        log(f"  Phantom company check failed: {e}", indent=2)

    log(f"  Queued: {results['queued']}", indent=2)
    return results


# ── Gap 7: entity_relationships with verification_needed ─────────────────────

def gap_unverified_relationships() -> Dict:
    log("Gap 7: entity_relationships with verification_needed=true", indent=1)
    results = {"found": 0, "queued": 0}

    if not table_exists("entity_relationships"):
        log("  entity_relationships not found — skipping", indent=2)
        return {"skipped": "table_missing"}

    try:
        unverified = sb_get("entity_relationships", {
            "select": "id,entity_id_a,entity_id_b,relationship_type",
            "verification_needed": "eq.true",
            "limit": "100",
        })
        results["found"] = len(unverified)
        log(f"  Unverified entity_relationships: {len(unverified)}", indent=2)

        for rel in unverified:
            write_queue_item(
                entity_type="entity_relationship",
                entity_id=str(rel["id"]),
                gap_type="unverified_relationship",
                priority=PRIORITY_P2,
                reason=(
                    f"Relationship {rel.get('entity_id_a')} "
                    f"—[{rel.get('relationship_type')}]→ "
                    f"{rel.get('entity_id_b')} needs human verification"
                ),
            )
            results["queued"] += 1

    except Exception as e:
        log(f"  Unverified relationship check failed: {e}", indent=2)

    log(f"  Queued: {results['queued']}", indent=2)
    return results


# ── Gap 8: Direct/Adjacent with null bd_angle (P0) ──────────────────────────

def gap_null_bd_angle() -> Dict:
    log("Gap 8: Direct/Adjacent overlap drugs with null bd_angle (P0)", indent=1)
    results = {"found": 0, "queued": 0}

    try:
        drugs = sb_get("drugs", {
            "select": "id,name,stage,overlap",
            "bd_angle": "is.null",
            "overlap": "in.(Direct,Adjacent)",
            "limit": "100",
        })
        results["found"] = len(drugs)
        log(f"  Direct/Adjacent drugs missing bd_angle: {len(drugs)}", indent=2)

        for drug in drugs:
            write_queue_item(
                entity_type="drug",
                entity_id=drug["id"],
                gap_type="missing_bd_angle",
                priority=PRIORITY_P0,
                reason=(
                    f"Direct/Adjacent drug '{drug.get('name')}' "
                    f"(stage={drug.get('stage')}) missing bd_angle — "
                    f"P0: required for BD analysis"
                ),
            )
            results["queued"] += 1

    except Exception as e:
        log(f"  bd_angle gap check failed: {e}", indent=2)

    log(f"  Queued: {results['queued']}", indent=2)
    return results


# ── Gap 9: Phase 2/3 with null risk_summary (P1) ────────────────────────────

def gap_null_risk_summary() -> Dict:
    log("Gap 9: Phase 2/3 drugs with null risk_summary (P1)", indent=1)
    results = {"found": 0, "queued": 0}

    try:
        drugs = sb_get("drugs", {
            "select": "id,name,stage,overlap",
            "risk_summary": "is.null",
            "limit": "100",
        })
        # Filter to clinical stage
        clinical = [d for d in drugs if is_clinical(d.get("stage") or "")]
        results["found"] = len(clinical)
        log(f"  Phase 2/3 drugs missing risk_summary: {len(clinical)}", indent=2)

        for drug in clinical:
            overlap = drug.get("overlap") or "unknown"
            priority = (
                PRIORITY_P0 if overlap in ("Direct", "Adjacent") else PRIORITY_P1
            )
            write_queue_item(
                entity_type="drug",
                entity_id=drug["id"],
                gap_type="missing_risk_summary",
                priority=priority,
                reason=(
                    f"Clinical drug '{drug.get('name')}' (stage={drug.get('stage')}, "
                    f"overlap={overlap}) missing risk_summary"
                ),
            )
            results["queued"] += 1

    except Exception as e:
        log(f"  risk_summary gap check failed: {e}", indent=2)

    log(f"  Queued: {results['queued']}", indent=2)
    return results


# ── Main entry point ──────────────────────────────────────────────────────────
