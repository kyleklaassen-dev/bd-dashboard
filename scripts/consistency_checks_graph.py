#!/usr/bin/env python3
"""consistency_checks_graph.py — cross-entity / relational checks 5-8 (§3 split):
deal attribution, stage history, relationship symmetry, molecule-vs-drug stage."""
import difflib
from collections import defaultdict
from typing import Dict

from consistency_base import (
    sb_get, table_exists, log, stage_rank, normalize_stage,
    write_contradiction_typed, write_gov_violation, VALID_APPROVED,
)


# ── Check 5: Deal attribution gap ─────────────────────────────────────────────

def check_deal_attribution() -> Dict:
    log("Check 5: Deal attribution — missing partnership rows", indent=1)
    results = {"deals_checked": 0, "gaps": 0}

    try:
        deals = sb_get("deals", {
            "select": "id,drug_name,company_id,partner_company",
            "limit": "300",
        })
        results["deals_checked"] = len(deals)

        # Load all partnerships indexed by company pair
        partnerships = sb_get("company_partnerships", {
            "select": "id,company_id,partner_company_id",
            "limit": "1000",
        })
        partner_pairs: Set[tuple] = set()
        for p in partnerships:
            a = (p.get("company_id") or "").lower()
            b = (p.get("partner_company_id") or "").lower()
            if a and b:
                partner_pairs.add((a, b))
                partner_pairs.add((b, a))

        # Load companies (to resolve partner_company name → id)
        companies = sb_get("companies", {"select": "id,name", "limit": "500"})
        co_by_name: Dict[str, str] = {}
        co_by_id: Dict[str, str] = {}
        for c in companies:
            n = (c.get("name") or "").lower().strip()
            co_by_name[n] = c["id"]
            co_by_id[c["id"]] = n

        for deal in deals:
            company_id = (deal.get("company_id") or "").lower()
            partner_name = (deal.get("partner_company") or "").lower()
            if not company_id or not partner_name:
                continue

            # Try to resolve partner name to ID
            partner_id = co_by_name.get(partner_name)
            if not partner_id:
                # Try fuzzy match
                for cname, cid in co_by_name.items():
                    ratio = difflib.SequenceMatcher(None, partner_name, cname).ratio()
                    if ratio > 0.85:
                        partner_id = cid
                        break

            if not partner_id:
                continue  # Can't verify without ID

            # Check if partnership row exists
            if (company_id, partner_id.lower()) not in partner_pairs:
                log(
                    f"  GAP: Deal '{deal.get('drug_name')}' involves "
                    f"{company_id} ↔ {partner_name} "
                    f"but no company_partnerships row found",
                    indent=2
                )
                write_contradiction_typed(
                    entity_id=str(deal["id"]),
                    entity_type="deal",
                    field_name="company_partnerships",
                    value_a=f"{company_id} deal_type={deal.get('deal_type')}",
                    value_b=f"partner={partner_id} has no partnership row",
                    contradiction_type="deal_missing_partnership_row",
                    severity="info",
                )
                results["gaps"] += 1

    except Exception as e:
        log(f"  Deal attribution check failed: {e}", indent=2)

    log(f"  Deals checked: {results['deals_checked']}, gaps: {results['gaps']}", indent=2)
    return results


# ── Check 6: Stage history contradiction ─────────────────────────────────────

def check_stage_history() -> Dict:
    log("Check 6: Stage history chain validation", indent=1)
    results = {"checked": 0, "contradictions": 0}

    if not table_exists("drug_stage_history"):
        log("  drug_stage_history not found — skipping", indent=2)
        return {"skipped": "table_missing"}

    try:
        # Get stage history ordered by recorded_at
        history = sb_get("drug_stage_history", {
            "select": "drug_id,stage,recorded_at",
            "limit": "500",
            "order": "recorded_at.asc",
        })
        # Group by drug_id
        drug_history: Dict[str, List[dict]] = defaultdict(list)
        for h in history:
            did = h.get("drug_id")
            if did:
                drug_history[did].append(h)

        # Load current stages
        drugs = sb_get("drugs", {"select": "id,name,stage", "limit": "500"})
        drug_current: Dict[str, dict] = {d["id"]: d for d in drugs}

        for drug_id, hist_rows in drug_history.items():
            if not hist_rows:
                continue

            # Most recent history entry
            latest_hist_stage = hist_rows[-1].get("stage") or ""
            current_drug = drug_current.get(drug_id)
            if not current_drug:
                continue

            current_stage = current_drug.get("stage") or ""
            results["checked"] += 1

            # If current stage doesn't match latest history — contradiction
            if (
                latest_hist_stage
                and current_stage
                and normalize_stage(latest_hist_stage) != normalize_stage(current_stage)
            ):
                log(
                    f"  HISTORY MISMATCH: {current_drug.get('name')} — "
                    f"history_latest={latest_hist_stage} != current={current_stage}",
                    indent=2
                )
                write_contradiction_typed(
                    entity_id=drug_id,
                    entity_type="drug",
                    field_name="stage",
                    value_a=current_stage,
                    value_b=f"history_latest:{latest_hist_stage}",
                    contradiction_type="stage_history_contradiction",
                    severity="warning",
                )
                results["contradictions"] += 1

            # Also check for regressions in the history chain itself
            for j in range(1, len(hist_rows)):
                prev = stage_rank(hist_rows[j - 1].get("stage") or "")
                curr = stage_rank(hist_rows[j].get("stage") or "")
                if curr < prev - 1 and prev >= 0 and curr >= 0:
                    log(
                        f"  REGRESSION in history: {current_drug.get('name')} "
                        f"{hist_rows[j-1].get('stage')} → {hist_rows[j].get('stage')}",
                        indent=2
                    )
                    write_contradiction_typed(
                        entity_id=drug_id,
                        entity_type="drug",
                        field_name="stage_history_chain",
                        value_a=hist_rows[j - 1].get("stage"),
                        value_b=f"regression_to:{hist_rows[j].get('stage')}",
                        contradiction_type="stage_history_regression",
                        severity="warning",
                    )
                    results["contradictions"] += 1

    except Exception as e:
        log(f"  Stage history check failed: {e}", indent=2)

    log(f"  Checked: {results['checked']}, contradictions: {results['contradictions']}", indent=2)
    return results


# ── Check 7: entity_relationships bidirectional symmetry ─────────────────────

def check_relationship_symmetry() -> Dict:
    log("Check 7: entity_relationships bidirectional symmetry", indent=1)
    results = {"checked": 0, "missing_symmetric": 0}

    if not table_exists("entity_relationships"):
        log("  entity_relationships not found — skipping", indent=2)
        return {"skipped": "table_missing"}

    SYMMETRIC_TYPES = {"competes_with", "similar_to", "overlaps_with"}

    try:
        rels = sb_get("entity_relationships", {
            "select": "id,entity_id_a,entity_id_b,relationship_type",
            "limit": "500",
        })
        results["checked"] = len(rels)

        # Build set of (a, b, type) for quick lookup
        rel_set: Set[tuple] = set()
        for r in rels:
            a = str(r.get("entity_id_a") or "")
            b = str(r.get("entity_id_b") or "")
            t = (r.get("relationship_type") or "").lower()
            if a and b and t:
                rel_set.add((a, b, t))

        # Check symmetric types
        for r in rels:
            rel_type = (r.get("relationship_type") or "").lower()
            if rel_type not in SYMMETRIC_TYPES:
                continue
            a = str(r.get("entity_id_a") or "")
            b = str(r.get("entity_id_b") or "")
            if not a or not b:
                continue
            # Check if reverse exists
            if (b, a, rel_type) not in rel_set:
                log(
                    f"  ASYMMETRIC: {a} —[{rel_type}]→ {b} "
                    f"but reverse not found",
                    indent=2
                )
                write_contradiction_typed(
                    entity_id=a,
                    entity_type="entity_relationship",
                    field_name="relationship_type",
                    value_a=f"{a} {rel_type} {b}",
                    value_b=f"missing_reverse:{b} {rel_type} {a}",
                    contradiction_type="relationship_asymmetry",
                    severity="info",
                )
                results["missing_symmetric"] += 1

    except Exception as e:
        log(f"  Relationship symmetry check failed: {e}", indent=2)

    log(f"  Checked: {results['checked']}, missing symmetric: {results['missing_symmetric']}", indent=2)
    return results


# ── Check 8: molecule_intelligence vs drugs table ─────────────────────────────

def check_molecule_vs_drug_stage() -> Dict:
    log("Check 8: molecule_intelligence vs drugs.stage", indent=1)
    results = {"checked": 0, "mismatches": 0}

    if not table_exists("molecule_intelligence"):
        log("  molecule_intelligence not found — skipping", indent=2)
        return {"skipped": "table_missing"}

    try:
        mol_rows = sb_get("molecule_intelligence", {
            "select": "id,drug_id,development_stage",
            "development_stage": "not.is.null",
            "limit": "300",
        })

        drugs = sb_get("drugs", {"select": "id,name,stage", "limit": "500"})
        drug_map: Dict[str, dict] = {d["id"]: d for d in drugs}

        for mol in mol_rows:
            drug_id = mol.get("drug_id")
            if not drug_id:
                continue
            drug = drug_map.get(drug_id)
            if not drug:
                continue

            mol_stage = normalize_stage(mol.get("development_stage") or "")
            drug_stage = normalize_stage(drug.get("stage") or "")
            results["checked"] += 1

            mol_rank = stage_rank(mol_stage)
            drug_rank = stage_rank(drug_stage)

            # Flag if both are non-empty and differ by more than 1 rank
            if mol_stage and drug_stage and abs(mol_rank - drug_rank) > 1:
                log(
                    f"  MISMATCH: {drug.get('name')} — "
                    f"molecule_intelligence.development_stage={mol.get('development_stage')} "
                    f"vs drugs.stage={drug.get('stage')}",
                    indent=2
                )
                write_contradiction_typed(
                    entity_id=drug_id,
                    entity_type="drug",
                    field_name="development_stage",
                    value_a=drug.get("stage"),
                    value_b=f"molecule_intelligence:{mol.get('development_stage')}",
                    contradiction_type="molecule_vs_drug_stage",
                    severity="warning",
                )
                results["mismatches"] += 1

    except Exception as e:
        log(f"  Molecule vs drug stage check failed: {e}", indent=2)

    log(f"  Checked: {results['checked']}, mismatches: {results['mismatches']}", indent=2)
    return results


# ── Main entry point ──────────────────────────────────────────────────────────
