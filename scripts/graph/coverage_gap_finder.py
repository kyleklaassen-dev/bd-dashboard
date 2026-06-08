#!/usr/bin/env python3
"""
Meridian Coverage Gap Finder — Tier 4 QA Agent
================================================
Phase A6 (extended) in the Weekend Sprint. Identifies what's missing —
drugs, companies, and relationships that SHOULD be in the database but aren't.

GAP TYPES:
  1. Low coverage_score drugs (<40) — add to research_queue
  2. Missing molecule_intelligence rows
  3. Missing drug_indications rows
  4. Missing catalyst_calendar for Phase 2/3 drugs
  5. Missing company_partnerships rows when deal exists
  6. Phantom companies (no drugs, no partnerships)
  7. entity_relationships with verification_needed=true
  8. Direct/Adjacent overlap drugs with null bd_angle (P0 priority)
  9. Phase 2/3 drugs with null risk_summary (P1 gap)

OUTPUT:
  Writes to research_queue table.
  Returns summary dict {gap_type: count}.

RUNS AS: Phase A6 in weekend_sprint.py (replaces/extends the existing A6 backlog scan)

USAGE (standalone):
  python scripts/coverage_gap_finder.py
  python scripts/coverage_gap_finder.py --dry-run
  python scripts/coverage_gap_finder.py --gap bd_angle
"""

import os
import sys
import json
import time
import datetime
import argparse
from typing import Optional, List, Dict, Set
from collections import defaultdict

import requests

# ── Path setup ───────────────────────────────────────────────────────────────
# NOTE: dirname(abspath(__file__)) resolved to scripts/, not the repo root,
# before the scripts/ reorg moved this file into scripts/graph/ — recompute
# relative to the true repo layout so credential-file lookups still work.
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT   = os.path.dirname(_SCRIPTS_DIR)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _common import load_credentials, sb_headers  # noqa: E402
import _db                                          # noqa: E402

# ── Credentials ──────────────────────────────────────────────────────────────

SUPABASE_URL, SUPABASE_KEY, _ = load_credentials(require_anthropic=False)
_db.init_db(SUPABASE_URL, SUPABASE_KEY)

SB_HEADERS = sb_headers(SUPABASE_KEY)

NOW_ISO  = datetime.datetime.utcnow().isoformat()
TODAY    = datetime.datetime.utcnow().strftime("%Y-%m-%d")
DRY_RUN  = False
RUN_ID   = f"cgf_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str, indent: int = 0):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {'  ' * indent}{msg}", flush=True)


# ── Supabase helpers ──────────────────────────────────────────────────────────

def sb_get(table: str, params: dict = None) -> List[dict]:
    return _db.sb_get(table, params or {})


def sb_post(table: str, data: dict) -> dict:
    if DRY_RUN:
        log(f"  [DRY-RUN] POST {table}: {json.dumps(data)[:120]}", indent=2)
        return data
    result = _db.sb_upsert(table, data)
    return result[0] if result else {}


def sb_upsert(table: str, rows: List[dict]) -> int:
    if DRY_RUN or not rows:
        if DRY_RUN:
            log(f"  [DRY-RUN] UPSERT {len(rows)} rows into {table}", indent=2)
        return len(rows)
    _db.sb_upsert(table, rows)
    return len(rows)


def table_exists(tname: str) -> bool:
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{tname}",
            headers=SB_HEADERS,
            params={"limit": "1"},
            timeout=10,
        )
        return r.status_code != 404
    except Exception:
        return False


# ── Priority constants ────────────────────────────────────────────────────────

PRIORITY_P0 = "P0"   # BD-critical, blocks analysis
PRIORITY_P1 = "P1"   # High value, enrichment needed soon
PRIORITY_P2 = "P2"   # Medium value
PRIORITY_P3 = "P3"   # Low priority, background

CLINICAL_STAGES = {"phase_2", "phase_3", "phase2", "phase3", "phase 2", "phase 3",
                   "phase ii", "phase iii", "phase2/3", "phase 2/3"}


def is_clinical(stage: str) -> bool:
    return (stage or "").lower().replace("-", " ").replace("_", " ") in CLINICAL_STAGES


def write_queue_item(
    entity_type: str,
    entity_id: str,
    gap_type: str,
    priority: str,
    reason: str,
) -> Dict:
    """Write a gap item to research_queue."""
    row = {
        "entity_type": entity_type,
        "entity_id":   str(entity_id),
        "gap_type":    gap_type,
        "priority":    priority,
        "reason":      reason[:500],
        "detected_at": NOW_ISO,
        "source":      "coverage_gap_finder",
        "run_id":      RUN_ID,
        "status":      "pending",
    }
    if table_exists("research_queue"):
        try:
            sb_post("research_queue", row)
        except Exception as e:
            log(f"  research_queue write failed: {e}", indent=3)
    return row


# ── Gap 1: Low coverage score ────────────────────────────────────────────────

def gap_low_coverage_score() -> Dict:
    log("Gap 1: Low coverage_score drugs (<40)", indent=1)
    results = {"found": 0, "queued": 0}

    try:
        low_drugs = sb_get("coverage_scores", {
            "entity_type": "eq.drug",
            "coverage_score": "lt.40",
            "select": "entity_id,coverage_score",
            "order": "coverage_score.asc",
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
            score = score_row.get("coverage_score", 0)
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
            "select": "catalyst_drug_id,drug_id",
            "limit": "500",
        })
        covered_ids: Set[str] = set()
        for cat in cats:
            for field in ["catalyst_drug_id", "drug_id"]:
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

GAP_CHECKS = {
    "low_coverage":          gap_low_coverage_score,
    "molecule_intelligence": gap_missing_molecule_intelligence,
    "drug_indications":      gap_missing_drug_indications,
    "catalyst_calendar":     gap_missing_catalyst_entries,
    "deal_partnerships":     gap_deals_without_partnerships,
    "phantom_companies":     gap_phantom_companies,
    "unverified_rels":       gap_unverified_relationships,
    "bd_angle":              gap_null_bd_angle,
    "risk_summary":          gap_null_risk_summary,
}


def run(dry_run: bool = False, gap_type: str = None) -> Dict:
    global DRY_RUN
    DRY_RUN = dry_run

    log("Coverage Gap Finder — Tier 4 QA Agent")
    log(f"Run ID: {RUN_ID}")
    log(f"Dry-run: {DRY_RUN}")

    # Verify research_queue table exists
    if not table_exists("research_queue"):
        log("  WARNING: research_queue table not found — gap items will be logged only", indent=1)

    checks_to_run = (
        {gap_type: GAP_CHECKS[gap_type]}
        if gap_type and gap_type in GAP_CHECKS
        else GAP_CHECKS
    )

    all_results: Dict[str, Dict] = {}
    summary: Dict[str, int] = {}

    for name, fn in checks_to_run.items():
        try:
            result = fn()
            all_results[name] = result
            summary[name] = result.get("queued", result.get("found", 0))
        except Exception as e:
            log(f"  Gap check '{name}' raised exception: {e}", indent=2)
            all_results[name] = {"error": str(e)}
            summary[name] = 0

    total_queued = sum(summary.values())

    log("=" * 60)
    log(f"Coverage Gap Finder Complete")
    log(f"  Total items queued: {total_queued}")
    for gap, count in summary.items():
        log(f"  {gap}: {count}", indent=1)

    all_results["summary"] = summary
    all_results["total_queued"] = total_queued
    return all_results


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Meridian Coverage Gap Finder — find missing data"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Run without writing to Supabase")
    parser.add_argument("--gap", default=None,
                        choices=list(GAP_CHECKS.keys()),
                        help="Run only one gap check type")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run, gap_type=args.gap)
    print(json.dumps(result, indent=2, default=str))
