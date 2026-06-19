#!/usr/bin/env python3
"""
competes_edges.py — pure edge-generation transforms for seed_competes_with.py (§3 split).

Group drug rows by (area, target), derive the deterministic COMPETES_WITH edge
pairs, and build the validation tests. Pure (data in -> data out); depends only
on the target normalizers. Extracted verbatim.
"""
from __future__ import annotations

import datetime
from collections import defaultdict

from competes_targets import TARGET_ALIASES, is_bispecific_target

NOW_ISO = datetime.datetime.utcnow().isoformat() + "Z"

def group_by_area_target(das_rows: list[dict], drug_lookup: dict) -> tuple[dict, list]:
    """
    Groups Direct drugs by (area_id, canonical_target).
    Returns:
      groups:    {(area_id, canonical_target): [drug_dict, ...]}
      uncertain: list of uncertain-case descriptions
    """
    groups: dict[tuple, list] = defaultdict(list)
    uncertain: list[dict] = []

    for row in das_rows:
        drug_id = row["drug_id"]
        area_id = row["area_id"]
        drug = drug_lookup.get(drug_id)

        if not drug:
            uncertain.append({
                "case":    "drug_not_found",
                "drug_id": drug_id,
                "area_id": area_id,
                "note":    "drug_id in drug_area_scores has no matching drugs row",
            })
            continue

        # Skip terminated drugs — they competed historically but not now
        if drug["stage"] in ("terminated", "discontinued"):
            continue

        canon = drug["canonical_target"]
        mapped = drug["target_is_mapped"]

        if not canon:
            uncertain.append({
                "case":    "missing_target",
                "drug_id": drug_id,
                "area_id": area_id,
                "name":    drug["name"],
                "note":    "drug.target is null or empty — cannot assign COMPETES_WITH",
            })
            continue

        if not mapped:
            uncertain.append({
                "case":    "unmapped_target",
                "drug_id": drug_id,
                "area_id": area_id,
                "name":    drug["name"],
                "raw_target": drug["target"],
                "note":    f"target '{drug['target']}' not in TARGET_ALIASES — needs manual review",
            })
            # Still group by canonical (lowercased raw) so we can surface pairs
            # but we'll flag the resulting edges as uncertain

        groups[(area_id, canon)].append({
            "drug_id":          drug_id,
            "name":             drug["name"],
            "target":           drug["target"],
            "canonical_target": canon,
            "target_is_mapped": mapped,
            "area_id":          area_id,
            "status":           drug["stage"],
        })

    return dict(groups), uncertain


def generate_edge_pairs(groups: dict) -> tuple[list, list]:
    """
    For each group with ≥2 drugs, generate bidirectional COMPETES_WITH pairs.
    Returns:
      safe_edges:      pairs where both drugs have mapped targets
      uncertain_edges: pairs where ≥1 drug has an unmapped target
    """
    safe_edges: list[dict] = []
    uncertain_edges: list[dict] = []

    for (area_id, canon), drugs_in_group in groups.items():
        if len(drugs_in_group) < 2:
            continue

        # Check if any drug in the group has a bispecific target
        has_bispecific = any(is_bispecific_target(d["canonical_target"]) for d in drugs_in_group)

        for d_a, d_b in combinations(drugs_in_group, 2):
            all_mapped = d_a["target_is_mapped"] and d_b["target_is_mapped"]

            rationale = (
                f"Both drugs are 'Direct' competitors in area '{area_id}' with "
                f"shared normalized target '{canon}'. "
                f"Generated deterministically by seed_competes_with.py on {NOW_ISO[:10]}."
            )

            edge_pair = [
                # Forward
                {
                    "subject_type":     "drug",
                    "subject_id":       d_a["drug_id"],
                    "predicate":        "COMPETES_WITH",
                    "object_type":      "drug",
                    "object_id":        d_b["drug_id"],
                    "scope_area_id":    area_id,
                    "confidence_level": "supported" if all_mapped else "inferred",
                    "generation_method": "deterministic",
                    "rationale":        rationale,
                    "status":           "active",
                    "created_by":       "seed_competes_with.py",
                    "notes":            None if all_mapped else f"⚠ target '{d_a['target']}' or '{d_b['target']}' not in alias map",
                },
                # Reverse (symmetric)
                {
                    "subject_type":     "drug",
                    "subject_id":       d_b["drug_id"],
                    "predicate":        "COMPETES_WITH",
                    "object_type":      "drug",
                    "object_id":        d_a["drug_id"],
                    "scope_area_id":    area_id,
                    "confidence_level": "supported" if all_mapped else "inferred",
                    "generation_method": "deterministic",
                    "rationale":        rationale,
                    "status":           "active",
                    "created_by":       "seed_competes_with.py",
                    "notes":            None if all_mapped else f"⚠ target '{d_b['target']}' or '{d_a['target']}' not in alias map",
                },
            ]

            if all_mapped:
                safe_edges.extend(edge_pair)
            else:
                uncertain_edges.extend(edge_pair)

    return safe_edges, uncertain_edges


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION TEST GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def build_validation_tests(safe_edges: list[dict]) -> list[dict]:
    """
    For each unique drug pair, generate one 'competes_with_edge_exists' validation test.
    Uses the A→B direction (not both) to avoid duplicates.
    """
    seen_pairs: set[tuple] = set()
    tests: list[dict] = []

    for edge in safe_edges:
        if edge["subject_id"] < edge["object_id"]:  # canonical ordering
            pair = (edge["subject_id"], edge["object_id"], edge["scope_area_id"])
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            tests.append({
                "test_name":       f"competes_with — {edge['subject_id']} vs {edge['object_id']} ({edge['scope_area_id']})",
                "test_type":       "competes_with_edge_exists",
                "entity_type":     "drug",
                "entity_id":       edge["subject_id"],
                "field_name":      "competitor",
                "expected_value":  edge["object_id"],
                "expected_operator": "eq",
                "area_id":         edge["scope_area_id"],
                "priority":        "P2",
                "notes":           f"COMPETES_WITH edge must exist between {edge['subject_id']} and {edge['object_id']} in area {edge['scope_area_id']}",
            })

    return tests
