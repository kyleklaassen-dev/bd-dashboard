#!/usr/bin/env python3
"""Promotion-payload build + drug-queue row writer (§3 drug_intake split)."""

import json
import re
from datetime import datetime, timezone, timedelta

import requests

from meridian.ingestion.drugintake.common import (
    ACTIVE_AREAS, _sb_headers, SUPABASE_URL,
    _map_relevance_to_overlap, _map_relevance_to_layer, _confidence_to_relevance_score,
)
from meridian.ingestion.drugintake.scoring import compute_strategic_value_score
from meridian.enrichment.catalog_category import infer_catalog_category


def build_promotion_payload(
    drug_name: str,
    drug_id:   str | None,
    research:  dict,
    relevant_areas: list[dict],
    graph_state: dict,
) -> dict:
    """
    Build the promotion_payload for the discovery_queue row.
    On approval, approve_discovery_item() will promote all nodes in this payload.
    """
    drug_info   = research.get("drug", {})
    mi_research = research.get("molecule_intelligence") or {}
    upcoming    = research.get("upcoming_catalysts") or []

    _drug_target   = drug_info.get("target") or ""
    _drug_modality = drug_info.get("modality") or ""
    _drug_stage    = drug_info.get("stage") or ""
    _primary_area  = relevant_areas[0]["area_id"] if relevant_areas else ""
    _inferred_cc   = infer_catalog_category(
        target   = _drug_target,
        modality = _drug_modality,
        stage    = _drug_stage,
        area_id  = _primary_area,
    )

    drug_node = {
        "id":           drug_id or _slug(drug_info.get("canonical_name") or drug_name),
        "name":         drug_info.get("canonical_name") or drug_name,
        "display_name": drug_info.get("display_name") or drug_name,
        "brand_name":   drug_info.get("brand_name"),
        "aliases":      drug_info.get("aliases") or [],
        "company_id":   drug_info.get("company_id_hint"),
        "target":       _drug_target or None,
        "mechanism":    drug_info.get("mechanism"),
        "modality":     _drug_modality or None,
        "stage":        _drug_stage or None,
        "data_source":  "catalog" if drug_id else "press_release",
        "catalog_category": _inferred_cc,
    }

    drug_area_scores = [
        {
            "drug_id":             drug_node["id"],
            "area_id":             a["area_id"],
            "overlap":             _map_relevance_to_overlap(a["relevance"]),
            "overlap_rationale":   a["rationale"],
            "area_fit":            a["relevance"],
            "area_fit_rationale":  a["evidence"],
        }
        for a in relevant_areas
    ]

    drug_areas = [{"drug_id": drug_node["id"], "area_id": a["area_id"]} for a in relevant_areas]

    # Molecule intelligence from research (if not already in DB)
    mi_node = None
    if mi_research:
        filled = {k: v for k, v in mi_research.items() if v and v != "null"}
        if filled:
            mi_node = {
                "drug_id":              drug_node["id"],
                "format":               mi_research.get("format"),
                "valency":              mi_research.get("valency"),
                "igg_subclass":         mi_research.get("igg_subclass"),
                "fc_engineering":       mi_research.get("fc_engineering"),
                "epitope":              mi_research.get("epitope"),
                "differentiation_claim": mi_research.get("differentiation_claim"),
                "enriched_by":          "drug_intake",
            }

    # Upcoming catalysts from research
    catalyst_nodes = [
        {
            "company_id":     drug_info.get("company_id_hint"),
            "drug_id":        drug_node["id"],
            "area_id":        relevant_areas[0]["area_id"] if relevant_areas else None,
            "catalyst_type":  c.get("event_type"),
            "label":          c.get("description"),
            "catalyst_date":  c.get("expected_date"),
            "significance":   c.get("significance"),
            "confidence_level": "inferred",
            "confidence_source": "drug_intake_research",
        }
        for c in upcoming[:5]  # cap at 5
    ]

    return {
        "drug":               drug_node,
        "drug_areas":         drug_areas,
        "drug_area_scores":   drug_area_scores,
        "molecule_intelligence": mi_node,
        "catalysts":          catalyst_nodes,
        "trials":             [],  # populated by trial enrichment post-approval
    }


def _slug(name: str) -> str:
    """Convert name to a reasonable Meridian-style id slug."""
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def write_drug_queue_rows(
    drug_name:     str,
    drug_id:       str | None,
    company_id:    str | None,
    resolution:    dict,
    research:      dict,
    relevant_areas: list[dict],
    coverage:      dict,
    run_id:        str,
    dry_run:       bool = False,
    evidence_tier: dict | None = None,
    graph_state:   dict | None = None,
) -> tuple[list[str], list[dict]]:
    """
    Write one discovery_queue row per relevant area.
    Returns list of area_ids successfully written.
    """
    drug_info = research.get("drug", {})
    drug_row  = resolution.get("drug_row") or {}
    canonical_name = drug_info.get("canonical_name") or drug_name
    resolved_company_id = company_id or drug_info.get("company_id_hint")
    resolved_company_name = drug_info.get("company") or ""
    resolved_drug_id = drug_id or _slug(canonical_name)

    # Check for existing queue rows to avoid duplicates
    existing_areas = _check_existing_drug_queue_rows(resolved_drug_id, [a["area_id"] for a in relevant_areas])

    promotion = build_promotion_payload(drug_name, drug_id, research, relevant_areas, {})
    written   = []
    area_score_rows: list[dict] = []  # per-area {area_id, strategic_value_score} for Output A

    completeness_gaps_json = {
        k: (str(v) if v is not None else "n/a")
        for k, v in coverage["dimensions"].items()
    }

    for area in relevant_areas:
        area_id = area["area_id"]

        if area_id in existing_areas:
            print(f"  ⏭️  {area_id}: skipped (recent non-rejected row already exists)")
            continue

        # Compute strategic value score for this area (must come before row dict)
        svs = compute_strategic_value_score(
            overlap       = _map_relevance_to_overlap(area["relevance"]),
            area_id       = area_id,
            stage         = drug_info.get("stage") or (drug_row.get("stage") if drug_row else None),
            catalysts     = graph_state.get("catalysts") or [] if isinstance(graph_state, dict) else [],
            deals         = graph_state.get("deals") or [] if isinstance(graph_state, dict) else [],
            evidence_tier = evidence_tier,
            company_id    = resolved_company_id,
        )

        row = {
            "company_name":            resolved_company_name or canonical_name,
            "company_id_suggested":    resolved_company_id,
            "drug_name":               canonical_name,
            "target":                  drug_info.get("target"),
            "stage":                   drug_info.get("stage"),
            "modality":                drug_info.get("modality"),
            "entity_type":             "molecule",
            "area_id":                 area_id,
            "overlap":                 _map_relevance_to_overlap(area["relevance"]),
            "competition_layer":       _map_relevance_to_layer(area["relevance"]),
            "confidence_score":        int(area["confidence"] * 100),
            "relevance_score":         _confidence_to_relevance_score(area["confidence"], area["relevance"]),
            "relevance_rationale":     area["rationale"],
            "reason":                  f"{area['relevance']} relevance to {ACTIVE_AREAS[area_id]['label']} — {area['evidence']}",
            "source_url":              drug_info.get("source_note"),
            "suggested_dest":          "update_drug" if drug_id else "new_drug",
            "discovered_by":           "drug_intake",
            "status":                  "pending",
            "discovery_run_id":        run_id,
            "relationship_type":       "drug_entity",
            "relationship_confidence": "high" if area["confidence"] >= 0.8 else "medium" if area["confidence"] >= 0.6 else "inferred",
            "why_discovered":          f"Drug Intake CLI — {drug_name}",
            "source":                  "user_intake",
            "evidence_tier":           evidence_tier["tier"] if evidence_tier else None,
            "strategic_value_score":   svs,
        }
        area_score_rows.append({"area_id": area_id, "strategic_value_score": svs})

        if dry_run:
            print(f"  [DRY RUN] Would write queue row: {area_id} / {area['relevance']} / confidence={area['confidence']:.2f} / strategic_value={svs}/10")
            written.append(area_id + f"(svs={svs})")
            continue

        # Attempt full row with new columns (migration v23 + v24)
        row_full = {
            **row,
            "coverage_score":         coverage["coverage_score"],
            "completeness_gaps":      json.dumps(completeness_gaps_json),
            "promotion_payload":      json.dumps(promotion),
            "strategic_value_score":  svs,
        }

        try:
            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/discovery_queue",
                headers=_sb_headers,
                json=row_full,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                written.append(area_id)
                print(f"  ✅ {area_id}: queued ({area['relevance']}, confidence={area['confidence']:.0%}, "
                      f"coverage={coverage['coverage_score']}%, strategic_value={svs}/10)")
            elif resp.status_code == 409:
                print(f"  ⏭️  {area_id}: conflict (row already exists)")
            else:
                # Fallback: try without new columns (migrations not yet applied)
                resp2 = requests.post(
                    f"{SUPABASE_URL}/rest/v1/discovery_queue",
                    headers=_sb_headers,
                    json=row,
                    timeout=10,
                )
                if resp2.status_code in (200, 201):
                    written.append(area_id)
                    print(f"  ✅ {area_id}: queued ({area['relevance']}, confidence={area['confidence']:.0%}) "
                          f"[apply migrations v23/v24 for coverage/payload/strategic_value columns]")
                else:
                    print(f"  ❌ {area_id}: write failed {resp2.status_code} — {resp2.text[:200]}")
        except Exception as e:
            print(f"  ❌ {area_id}: exception — {e}")

    return written, area_score_rows


def _check_existing_drug_queue_rows(drug_name_or_id: str, area_ids: list[str]) -> set[str]:
    """Return area_ids with a recent non-rejected queue row for this drug."""
    if not drug_name_or_id or not area_ids:
        return set()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/discovery_queue",
            headers={**_sb_headers, "Prefer": ""},
            params={
                "drug_name":     f"ilike.{drug_name_or_id}",
                "status":        "not.eq.rejected",
                "discovered_at": f"gte.{cutoff}",
                "select":        "area_id",
                "source":        "eq.user_intake",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return {row["area_id"] for row in resp.json() if row.get("area_id")}
    except Exception:
        pass
    return set()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN WORKFLOW
# ══════════════════════════════════════════════════════════════════════════════
