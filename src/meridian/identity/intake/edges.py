#!/usr/bin/env python3
"""Graph edge writers (§3 company_intake split): acquisition / license / ACTIVE_IN edges."""

from __future__ import annotations

import requests

from meridian.identity.intake.common import _sb_headers, SUPABASE_URL


# ══════════════════════════════════════════════════════════════════════════════
# TRANSACTION INTAKE — ACQUISITION EDGE WRITER
# ══════════════════════════════════════════════════════════════════════════════
#
# Rule (v28, 2026-05-24): When a Transaction Intake processes an acquisition
# deal, it must write ownership_edges with deal_id set so every edge traces
# back to its originating deal record.
#
# Pattern for any acquisition:
#   1. Write (or find) deals row → get deal_id
#   2. Write ownership_edges:
#        • acquired_company ACQUIRED→ acquirer_company  (deal_id=deal_id)
#        • drug ORIGINATED_BY→ acquired_company          (deal_id=deal_id)
#        • drug CONTROLLED_BY→ acquirer_company          (deal_id=deal_id)
#
# Canonical examples (backfilled 2026-05-24):
#   UCB/Candid (deal 19), UCB/Antengene (deal 167), Merck/Prometheus (deal 28)
#
# Usage: call write_acquisition_edges() after a deals row is inserted and
# the company + drug IDs are confirmed.

def write_acquisition_edges(
    deal_id: int,
    acquirer_id: str,
    acquired_id: str,
    drug_ids: list[str],
    source_url: str | None = None,
    dry_run: bool = False,
) -> int:
    """
    Write ownership_edges for an acquisition transaction with deal_id FK set.

    Returns number of edges successfully written.
    """
    edges = [
        # Company-level acquisition edge
        {
            "subject_type":     "company",
            "subject_id":       acquired_id,
            "predicate":        "ACQUIRED",
            "object_type":      "company",
            "object_id":        acquirer_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        }
    ]

    for drug_id in drug_ids:
        # Drug originated in acquired company
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "ORIGINATED_BY",
            "object_type":      "company",
            "object_id":        acquired_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })
        # Drug now controlled by acquirer
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "CONTROLLED_BY",
            "object_type":      "company",
            "object_id":        acquirer_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })

    if dry_run:
        print(f"  [DRY RUN] Would write {len(edges)} acquisition ownership_edges (deal_id={deal_id})")
        for e in edges:
            print(f"    {e['subject_id']} -{e['predicate']}→ {e['object_id']}")
        return len(edges)

    ok = 0
    for edge in edges:
        try:
            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/ownership_edges",
                headers={**_sb_headers, "Prefer": "resolution=ignore-duplicates,return=representation"},
                json=edge,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                ok += 1
            else:
                print(f"  ⚠ Edge {edge['subject_id']}/{edge['predicate']}: {resp.status_code} {resp.text[:150]}")
        except Exception as e:
            print(f"  ❌ Edge write error: {e}")

    print(f"  ✓ {ok}/{len(edges)} acquisition ownership_edges written (deal_id={deal_id})")
    return ok


def write_license_edges(
    deal_id: int,
    licensor_id: str,
    licensee_id: str,
    drug_ids: list[str],
    source_url: str | None = None,
    dry_run: bool = False,
) -> int:
    """
    Write ownership_edges for a licensing deal with deal_id FK set.
    Used for in-licensing (licensee receives rights from licensor).
    """
    edges = []
    for drug_id in drug_ids:
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "ORIGINATED_BY",
            "object_type":      "company",
            "object_id":        licensor_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "LICENSED_IN",
            "object_type":      "company",
            "object_id":        licensee_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "LICENSED_FROM",
            "object_type":      "company",
            "object_id":        licensor_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })

    if dry_run:
        print(f"  [DRY RUN] Would write {len(edges)} license ownership_edges (deal_id={deal_id})")
        return len(edges)

    ok = 0
    for edge in edges:
        try:
            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/ownership_edges",
                headers={**_sb_headers, "Prefer": "resolution=ignore-duplicates,return=representation"},
                json=edge,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                ok += 1
            else:
                print(f"  ⚠ Edge {edge['subject_id']}/{edge['predicate']}: {resp.status_code} {resp.text[:150]}")
        except Exception as e:
            print(f"  ❌ Edge write error: {e}")

    print(f"  ✓ {ok}/{len(edges)} license ownership_edges written (deal_id={deal_id})")
    return ok


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH CONSISTENCY — ACTIVE_IN EDGE WRITER
# ══════════════════════════════════════════════════════════════════════════════
#
# Rule (v29, 2026-05-24): Every company_areas write must be paired with a
# corresponding entity_edges ACTIVE_IN row so the graph can answer
# "who is active in [area]?" as a single predicate lookup.
#
# This function is called by approve_discovery.py immediately after each
# sb_upsert("company_areas", ...) call.
#
# Idempotent: uses resolution=ignore-duplicates so re-running is safe.

def write_active_in_edge(
    company_id: str,
    area_id: str,
    dry_run: bool = False,
    created_by: str = "approve_discovery",
) -> bool:
    """
    Write a single entity_edges ACTIVE_IN row for company → area.
    Returns True if written (or dry-run), False on error.

    Idempotent — safe to call even if the edge already exists.
    """
    edge = {
        "subject_type":      "company",
        "subject_id":        company_id,
        "predicate":         "ACTIVE_IN",
        "object_type":       "area",
        "object_id":         area_id,
        "confidence_level":  "confirmed",
        "generation_method": "deterministic",
        "rationale":         "Derived from company_areas table",
        "status":            "active",
        "created_by":        created_by,
    }

    if dry_run:
        print(f"  [DRY RUN] Would write ACTIVE_IN edge: {company_id} → {area_id}")
        return True

    try:
        from meridian.database.edge_writer import EdgeWriter
        _r = EdgeWriter(verify_endpoints=False).write(edge)
        if not _r.get("rejected"):
            print(f"  + entity_edges ACTIVE_IN: {company_id} → {area_id}")
            return True
        print(f"  ⚠ ACTIVE_IN edge {company_id}/{area_id} rejected: {_r.get('rejected')}")
        return False
    except Exception as e:
        print(f"  ❌ ACTIVE_IN edge write error ({company_id}/{area_id}): {e}")
        return False
