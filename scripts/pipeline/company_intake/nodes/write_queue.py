"""
Node: write_queue  (mode="intake" only)
Step [4/4] — write one discovery_queue row per relevant area (with a 30-day
dedup check), then print the final area-map summary.

Uses raw `requests` rather than _db: the write path needs per-status-code
branching (200/201 success, 409 conflict, fallback retry without the
`source` column when migration v22 hasn't landed yet) that _db.sb_post
collapses into a single Optional[dict].
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta

import requests

_HERE     = os.path.dirname(os.path.abspath(__file__))
_NODES    = os.path.dirname(_HERE)
_PIPELINE = os.path.dirname(_NODES)
_SCRIPTS  = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _common import sb_headers                                      # noqa: E402
from pipeline.company_intake.state import IntakeState               # noqa: E402
from pipeline.company_intake.nodes.research_company import ACTIVE_AREAS  # noqa: E402
from pipeline.company_intake.printing import print_area_map         # noqa: E402


def _headers(supabase_key: str) -> dict:
    return {**sb_headers(supabase_key), "Prefer": "return=minimal"}


# ── Overlap/layer/score helpers ───────────────────────────────────────────────

def _map_relevance_to_overlap(relevance: str) -> str:
    return {
        "Direct":       "Direct",
        "Adjacent":     "Adjacent",
        "Same-patient": "Same-Space",
        "Watchlist":    "Watch",
    }.get(relevance, "Watch")


def _map_relevance_to_layer(relevance: str) -> int:
    return {"Direct": 1, "Adjacent": 2, "Same-patient": 3, "Watchlist": 4}.get(relevance, 4)


def _confidence_to_relevance_score(confidence: float, relevance: str) -> int:
    base = {"Direct": 8, "Adjacent": 6, "Same-patient": 5, "Watchlist": 4}.get(relevance, 3)
    return min(10, int(base + confidence * 2))


def _map_relevance_to_relationship(relevance: str) -> str:
    return {
        "Direct":       "direct_competitor",
        "Adjacent":     "platform_overlap",
        "Same-patient": "same_patient_population",
        "Watchlist":    "strategic_watchlist",
    }.get(relevance, "strategic_watchlist")


# ── Dedup check ────────────────────────────────────────────────────────────────

def _check_existing_queue_rows(supabase_url: str, supabase_key: str,
                               company_id: str, area_ids: list[str]) -> set[str]:
    """
    Return the set of area_ids that already have a pending/reviewed queue row
    from the last 30 days (not rejected). These will be skipped.
    """
    if not company_id or not area_ids:
        return set()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        resp = requests.get(
            f"{supabase_url}/rest/v1/discovery_queue",
            headers={**sb_headers(supabase_key), "Prefer": ""},
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


# ── Queue row writer ───────────────────────────────────────────────────────────

def write_queue_rows(
    supabase_url: str,
    supabase_key: str,
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

    # Canonical name from research or resolver
    canonical_name = co_info.get("canonical_name") or company_name
    suggested_id   = company_id or resolution.get("canonical_name") or company_name.lower().replace(" ", "")

    # Check for existing rows to skip
    existing_areas = _check_existing_queue_rows(supabase_url, supabase_key, suggested_id,
                                                 [a["area_id"] for a in relevant_areas])
    written = []
    headers = _headers(supabase_key)

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
                f"{supabase_url}/rest/v1/discovery_queue",
                headers=headers,
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
                    f"{supabase_url}/rest/v1/discovery_queue",
                    headers=headers,
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


# ── Pipeline node ─────────────────────────────────────────────────────────────

def write_queue_node(state: IntakeState) -> IntakeState:
    """
    Step [4/4] — write discovery_queue rows for the relevant areas, then
    print the final area-map summary.
    """
    print(f"\n[4/4] Writing {len(state.relevant_areas)} row(s) to discovery_queue...")
    state.written_areas = write_queue_rows(
        supabase_url   = state.supabase_url,
        supabase_key   = state.supabase_key,
        company_name   = state.company_name,
        company_id     = state.company_id,
        resolution     = state.resolution,
        research       = state.research,
        relevant_areas = state.relevant_areas,
        run_id         = state.run_id,
        dry_run        = state.dry_run,
    )

    print_area_map(state.company_name, state.research, state.relevant_areas, state.written_areas)

    state.mark_complete("write_queue")
    return state
