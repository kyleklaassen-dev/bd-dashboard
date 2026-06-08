"""
Node: write_gaps  (mode="reaudit" only)
Step [4/4] (write phase) — score area relevance for each gap drug by
keyword match and push it to discovery_queue with source='re_audit'.

Uses raw `requests`, mirroring write_queue.py: the original branches on
HTTP status (200/201 vs. other) with bespoke per-row messages that
_db.sb_post's Optional[dict] return would flatten.
"""
from __future__ import annotations

import os
import sys

import requests

_HERE     = os.path.dirname(os.path.abspath(__file__))
_NODES    = os.path.dirname(_HERE)
_PIPELINE = os.path.dirname(_NODES)
_SCRIPTS  = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _common import sb_headers                                          # noqa: E402
from pipeline.company_intake.state import IntakeState                   # noqa: E402
from pipeline.company_intake.nodes.research_company import ACTIVE_AREAS  # noqa: E402
from pipeline.company_intake.nodes.score_areas import get_relevant_areas  # noqa: E402


def write_gaps_node(state: IntakeState) -> IntakeState:
    """Step [4/4] write phase — push each gap drug to discovery_queue (source=re_audit)."""
    headers = {**sb_headers(state.supabase_key), "Prefer": "return=minimal"}
    written = 0

    for drug in state.new_drugs:
        drug_name = drug.get("drug_name", "unknown")
        target    = drug.get("target", "")
        stage     = drug.get("stage", "")
        mechanism = drug.get("mechanism", "")

        # Score area relevance for this specific drug using its target/indication text
        drug_text = f"{target} {mechanism} {drug.get('indication', '')}".lower()

        relevant_areas = []
        for area_id, area_info in ACTIVE_AREAS.items():
            area_keywords = [k.lower() for k in area_info["keywords"]]
            if any(kw in drug_text for kw in area_keywords):
                relevant_areas.append(area_id)

        # If no keyword match, fall back to the company's existing areas
        if not relevant_areas:
            relevant_areas = [a["area_id"] for a in get_relevant_areas(state.research)][:2]

        for area_id in relevant_areas:
            row = {
                "company_name":            state.company_name,
                "company_id_suggested":    state.company_id,
                "drug_name":               drug_name,
                "target":                  target,
                "stage":                   stage,
                "modality":                drug.get("modality"),
                "entity_type":             "molecule",
                "area_id":                 area_id,
                "overlap":                 "Adjacent",
                "competition_layer":       2,
                "confidence_score":        70,
                "relevance_score":         5,
                "relevance_rationale":     f"Re-audit: '{drug_name}' found on live pipeline page but absent from Meridian DB.",
                "reason":                  f"Re-audit gap: {drug_name} ({stage}, {target}) — not in Meridian for {area_id}.",
                "source":                  "re_audit",
                "suggested_dest":          "update_company",
                "discovered_by":           "company_intake_reaudit",
                "status":                  "pending",
                "discovery_run_id":        state.run_id,
                "relationship_type":       "pipeline",
                "relationship_confidence": "medium",
                "why_discovered":          (
                    f"Re-audit of {state.company_name} pipeline: '{drug_name}' appears on live pipeline page "
                    f"but has no corresponding drugs row in Meridian. Stage: {stage}. Target: {target}. "
                    f"Mechanism: {mechanism}. Review and promote via drug_intake.py if confirmed."
                ),
            }

            if state.dry_run:
                print(f"  [DRY RUN] Would queue: {drug_name} → {area_id}")
                written += 1
                continue

            try:
                resp = requests.post(
                    f"{state.supabase_url}/rest/v1/discovery_queue",
                    headers=headers,
                    json=row,
                    timeout=10,
                )
                if resp.status_code in (200, 201):
                    print(f"  ✅ Queued: {drug_name} → {area_id} (re_audit)")
                    written += 1
                else:
                    print(f"  ⚠️  Queue write failed ({resp.status_code}): {resp.text[:200]}")
            except Exception as e:
                print(f"  ❌ Queue write error: {e}")

    state.gaps_written = written

    print(f"\n{'[DRY RUN] Would write' if state.dry_run else 'Written'}: {written} discovery_queue row(s) (source=re_audit)")
    if not state.dry_run and written:
        print("  → Review in Meridian → Discovery Queue tab, filter source=re_audit.")
        print("  → Promote each gap via: python scripts/drug_intake.py --drug '<drug_name>' --company '<company>'")

    state.mark_complete("write_gaps")
    return state
