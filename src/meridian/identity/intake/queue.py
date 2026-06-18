#!/usr/bin/env python3
"""Research-queue row writer (§3 company_intake split)."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import requests

from meridian.identity.intake.common import (
    ACTIVE_AREAS, _sb_headers, SUPABASE_URL,
    _map_relevance_to_overlap, _map_relevance_to_layer,
    _confidence_to_relevance_score, _map_relevance_to_relationship,
)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — DEDUP CHECK
# ══════════════════════════════════════════════════════════════════════════════

def _check_existing_queue_rows(company_id: str, area_ids: list[str]) -> set[str]:
    """
    Return the set of area_ids that already have a pending/reviewed queue row
    from the last 30 days (not rejected). These will be skipped.
    """
    if not company_id or not area_ids:
        return set()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/discovery_queue",
            headers={**_sb_headers, "Prefer": ""},
            params={
                "company_id_suggested": f"eq.{company_id}",
                "status":              "not.eq.rejected",
                "discovered_at":       f"gte.{cutoff}",
                "select":              "area_id",
            },
        )
        if resp.status_code == 200:
            return {row["area_id"] for row in resp.json() if row.get("area_id")}
    except Exception:
        pass
    return set()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — WRITE DISCOVERY QUEUE ROWS
# ══════════════════════════════════════════════════════════════════════════════

def write_queue_rows(
    company_name: str,
    company_id: str | None,
    resolution: dict,
    research: dict,
    relevant_areas: list[dict],
    run_id: str,
    dry_run: bool = False,
) -> list[str]:
    """
    Write one discovery_queue row per relevant area.
    Returns list of area_ids successfully written.
    """
    co_info    = research.get("company", {})
    pipeline   = research.get("pipeline", [])
    deals      = research.get("deals", [])

    # Canonical name from research or resolver
    canonical_name = co_info.get("canonical_name") or company_name
    suggested_id   = company_id or resolution.get("canonical_name") or company_name.lower().replace(" ", "")

    # Check for existing rows to skip
    existing_areas = _check_existing_queue_rows(suggested_id, [a["area_id"] for a in relevant_areas])
    written = []

    for area in relevant_areas:
        area_id = area["area_id"]

        if area_id in existing_areas:
            print(f"  ⏭️  {area_id}: skipped (recent row already exists, not rejected)")
            continue

        # Find drugs most relevant to this area
        area_keywords  = [k.lower() for k in ACTIVE_AREAS[area_id]["keywords"]]
        relevant_drugs = []
        for drug in pipeline:
            drug_text = (
                (drug.get("target") or "") + " " +
                (drug.get("indication") or "") + " " +
                (drug.get("mechanism") or "")
            ).lower()
            if any(kw in drug_text for kw in area_keywords):
                relevant_drugs.append(drug)

        # Build a drug summary string for the why_discovered field
        drug_summary = "; ".join(
            f"{d['drug_name']} ({d['target']}, {d['stage']})"
            for d in relevant_drugs[:3]
        ) or "No specific drug identified — platform-level relevance"

        # Build queue row
        row = {
            "company_name":           canonical_name,
            "company_id_suggested":   suggested_id,
            "drug_name":              relevant_drugs[0]["drug_name"] if relevant_drugs else None,
            "target":                 relevant_drugs[0]["target"]    if relevant_drugs else None,
            "stage":                  relevant_drugs[0]["stage"]     if relevant_drugs else None,
            "modality":               relevant_drugs[0].get("modality") if relevant_drugs else None,
            "entity_type":            "molecule" if relevant_drugs else "company",
            "area_id":                area_id,
            "overlap":                _map_relevance_to_overlap(area["relevance"]),
            "competition_layer":      _map_relevance_to_layer(area["relevance"]),
            "confidence_score":       int(area["confidence"] * 100),
            "relevance_score":        _confidence_to_relevance_score(area["confidence"], area["relevance"]),
            "relevance_rationale":    area["rationale"],
            "reason":                 f"{area['relevance']} relevance to {ACTIVE_AREAS[area_id]['label']} — {area['evidence']}",
            "source_url":             None,
            "suggested_dest":         "new_company" if not company_id else "update_company",
            "discovered_by":          "company_intake",
            "status":                 "pending",
            "discovery_run_id":       run_id,
            "relationship_type":      _map_relevance_to_relationship(area["relevance"]),
            "relationship_confidence": "high" if area["confidence"] >= 0.8 else "medium" if area["confidence"] >= 0.6 else "inferred",
            "why_discovered":         f"User intake: '{company_name}' → {area_id}. Evidence: {drug_summary}. {area['rationale']}",
        }

        # Add source column if it exists (migration v22 may not be applied yet)
        row["source"] = "user_intake"

        if dry_run:
            print(f"  [DRY RUN] Would write queue row: {area_id} / {area['relevance']} / confidence={area['confidence']:.2f}")
            written.append(area_id)
            continue

        try:
            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/discovery_queue",
                headers=_sb_headers,
                json=row,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                written.append(area_id)
                print(f"  ✅ {area_id}: queued ({area['relevance']}, confidence={area['confidence']:.0%})")
            elif resp.status_code == 409:
                print(f"  ⏭️  {area_id}: conflict (row already exists)")
            else:
                # Try without 'source' column in case migration not applied
                row_no_source = {k: v for k, v in row.items() if k != "source"}
                resp2 = requests.post(
                    f"{SUPABASE_URL}/rest/v1/discovery_queue",
                    headers=_sb_headers,
                    json=row_no_source,
                    timeout=10,
                )
                if resp2.status_code in (200, 201):
                    written.append(area_id)
                    print(f"  ✅ {area_id}: queued ({area['relevance']}, confidence={area['confidence']:.0%}) [source col pending migration]")
                else:
                    print(f"  ❌ {area_id}: write failed {resp2.status_code} — {resp2.text[:200]}")
        except Exception as e:
            print(f"  ❌ {area_id}: exception — {e}")

    return written
