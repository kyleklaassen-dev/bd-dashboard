#!/usr/bin/env python3
"""
landscape_coverage_metrics.py — coverage sub-score computations (§3 split).

The six read-only metric functions (drug / relationship / catalyst coverage,
source validation, staleness penalty). Pure of writes; each reads via get().
Extracted verbatim from compute_landscape_coverage.py.
"""
from landscape_coverage_base import get


def fetch_landscape_drug_ids(landscape_id):
    """
    Get the set of drug_ids relevant to a landscape.
    Source: landscape_expected_competitors (confirmed drug_ids)
    + drugs in drug_areas that match the landscape's area.
    """
    # From expected competitors (drug_id may be null for Tier 3)
    lec_rows = get("landscape_expected_competitors", {
        "landscape_id": f"eq.{landscape_id}",
        "select":       "drug_id,drug_name,tier,confirmed,tier3_weight",
    })

    # Also get all drugs in the relevant areas from drug_areas
    # We'll resolve area_ids from the landscape row
    return lec_rows


def compute_drug_coverage(lec_rows, expected_drug_count):
    """
    drug_coverage_score = sum of weights for captured drugs / expected_drug_count
    - Tier 1/2 confirmed=TRUE:  weight 1.0
    - Tier 3 confirmed=TRUE:    weight tier3_weight (0.5)
    - confirmed=FALSE:          weight 0.0
    """
    if not expected_drug_count:
        return 0.0, {}

    numerator = 0.0
    details = {"confirmed": [], "missing": [], "tier3_pending": []}

    for row in lec_rows:
        if row["confirmed"]:
            w = float(row["tier3_weight"])
            numerator += w
            details["confirmed"].append(row["drug_name"])
        else:
            if row["tier"] == 3:
                details["tier3_pending"].append(row["drug_name"])
            else:
                details["missing"].append(row["drug_name"])

    score = min(numerator / expected_drug_count, 1.0)
    return score, details


def compute_relationship_coverage(landscape_id, expected_relationship_count):
    """
    relationship_coverage_score = active edges in scope / expected_relationship_count
    Queries entity_edges where scope_area_id matches areas for this landscape.
    """
    if not expected_relationship_count:
        return 0.0, {}

    # Get edges scoped to igf1r or ted (TED landscape areas)
    # Use scope_area_id = igf1r as primary; also catch TED-scoped edges
    edges_igf1r = get("entity_edges", {
        "scope_area_id": "eq.igf1r",
        "status":        "eq.active",
        "select":        "subject_id,predicate,object_id,staleness_status",
    })
    edges_ted = get("entity_edges", {
        "scope_area_id": "eq.ted",
        "status":        "eq.active",
        "select":        "subject_id,predicate,object_id,staleness_status",
    })

    # Deduplicate by (subject,predicate,object)
    seen = set()
    all_edges = []
    for e in edges_igf1r + edges_ted:
        key = (e["subject_id"], e["predicate"], e["object_id"])
        if key not in seen:
            seen.add(key)
            all_edges.append(e)

    captured = len(all_edges)
    score = min(captured / expected_relationship_count, 1.0)
    details = {
        "captured": captured,
        "expected": expected_relationship_count,
        "edges": [f"{e['subject_id']} {e['predicate']} {e['object_id']}" for e in all_edges],
    }
    return score, details


def compute_catalyst_coverage(area_ids, expected_catalyst_count):
    """
    catalyst_coverage_score = TED-relevant catalysts / expected_catalyst_count
    Counts catalysts with area_id in landscape areas + status pending/met.
    """
    if not expected_catalyst_count:
        return 0.0, {}

    catalysts = []
    for area_id in area_ids:
        rows = get("catalysts", {
            "area_id":         f"eq.{area_id}",
            "catalyst_status": "in.(pending,met)",
            "select":          "id,label,area_id,catalyst_status,catalyst_date",
        })
        catalysts.extend(rows)

    # Deduplicate by id
    seen_ids = set()
    unique_cats = []
    for c in catalysts:
        if c["id"] not in seen_ids:
            seen_ids.add(c["id"])
            unique_cats.append(c)

    captured = len(unique_cats)
    score = min(captured / expected_catalyst_count, 1.0)
    details = {
        "captured": captured,
        "expected": expected_catalyst_count,
        "note": f"Catalysts in areas {area_ids} with status in (pending,met)",
    }
    return score, details


def compute_source_validation(drug_ids_in_scope):
    """
    source_validation_score = sourced drug_area_scores rows / total
    'sourced' = source_url IS NOT NULL AND confidence_level IN (confirmed, supported)
    Scope: drug_area_scores rows where drug_id is in the landscape's drug set.
    """
    if not drug_ids_in_scope:
        return 0.0, {}

    id_list = ",".join(drug_ids_in_scope)
    all_rows = get("drug_area_scores", {
        "drug_id": f"in.({id_list})",
        "select":  "drug_id,area_id,source_url,confidence_level",
    })

    total = len(all_rows)
    if not total:
        return 0.0, {"total": 0, "sourced": 0}

    sourced = sum(
        1 for r in all_rows
        if r.get("source_url") and r.get("confidence_level") in ("confirmed", "supported")
    )
    score = sourced / total
    details = {
        "total":   total,
        "sourced": sourced,
        "unsourced_drugs": [
            r["drug_id"] for r in all_rows
            if not (r.get("source_url") and r.get("confidence_level") in ("confirmed", "supported"))
        ],
    }
    return score, details


def compute_staleness_penalty(landscape_id, drug_ids_in_scope):
    """
    staleness_penalty = stale items / total items tracked
    Sources: entity_edges (scope igf1r/ted) + mechanism_status (TED) + geographic_approvals (TED)
    'stale' = staleness_status IN (stale, needs_revalidation)
    """
    stale_items = []
    total_items = []

    # entity_edges
    for area in ["igf1r", "ted"]:
        rows = get("entity_edges", {
            "scope_area_id": f"eq.{area}",
            "status":        "eq.active",
            "select":        "subject_id,predicate,object_id,staleness_status",
        })
        for r in rows:
            key = f"edge:{r['subject_id']}.{r['predicate']}.{r['object_id']}"
            total_items.append(key)
            if r.get("staleness_status") in ("stale", "needs_revalidation"):
                stale_items.append(key)

    # mechanism_status (TED indication)
    mech_rows = get("mechanism_status", {
        "indication": "eq.TED",
        "select":     "target_name,indication,staleness_status",
    })
    for r in mech_rows:
        key = f"mechanism:{r['target_name']}×{r['indication']}"
        total_items.append(key)
        if r.get("staleness_status") in ("stale", "needs_revalidation"):
            stale_items.append(key)

    # geographic_approvals (TED)
    geo_rows = get("geographic_approvals", {
        "indication": "eq.TED",
        "select":     "drug_name,geography,staleness_status",
    })
    for r in geo_rows:
        key = f"geo:{r['drug_name']}×{r['geography']}"
        total_items.append(key)
        if r.get("staleness_status") in ("stale", "needs_revalidation"):
            stale_items.append(key)

    total = len(set(total_items))  # deduplicate
    stale = len(set(stale_items))

    if not total:
        return 0.0, {}

    penalty = stale / total
    details = {
        "stale":  stale,
        "total":  total,
        "stale_items": list(set(stale_items)),
    }
    return penalty, details
