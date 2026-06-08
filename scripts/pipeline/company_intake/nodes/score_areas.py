"""
Node: score_areas  (mode="intake" only)
Step [3/4] — score area relevance against the minimum evidence + confidence
thresholds and decide which areas are worth a discovery_queue row.
"""
from __future__ import annotations

import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_NODES    = os.path.dirname(_HERE)
_PIPELINE = os.path.dirname(_NODES)
_SCRIPTS  = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from pipeline.company_intake.state import IntakeState              # noqa: E402
from pipeline.company_intake.nodes.research_company import ACTIVE_AREAS  # noqa: E402
from pipeline.company_intake.printing import print_area_map        # noqa: E402

# Minimum evidence thresholds before writing a queue row
_RELEVANCE_INCLUDE = {"Direct", "Adjacent", "Same-patient"}
_RELEVANCE_WATCHLIST_MIN_CONFIDENCE = 0.6   # watchlist only if high-confidence
_MIN_CONFIDENCE = 0.5                        # skip any area below this


def _has_minimum_evidence(research: dict, area_id: str) -> bool:
    """
    Check if there's at least one molecule OR one clinical program found.
    Prevents writing queue rows for pure speculation.
    """
    pipeline = research.get("pipeline", [])
    if not pipeline:
        # No drugs found — only allow if company itself is in the area (strategic watchlist)
        area_data = research.get("area_assessment", {}).get(area_id, {})
        if area_data.get("relevance") == "Direct" and area_data.get("confidence", 0) >= 0.7:
            return True
        return False
    return True


def get_relevant_areas(research: dict) -> list[dict]:
    """
    Extract areas that meet the minimum evidence + confidence thresholds.
    Returns list of dicts with area_id, relevance, confidence, rationale, evidence.
    """
    assessment = research.get("area_assessment", {})
    result = []

    for area_id, area_info in assessment.items():
        if area_id not in ACTIVE_AREAS:
            continue

        relevance   = area_info.get("relevance", "Not relevant")
        confidence  = float(area_info.get("confidence", 0))
        rationale   = area_info.get("rationale", "")
        evidence    = area_info.get("evidence", "")

        # Skip non-relevant
        if relevance == "Not relevant":
            continue

        # Watchlist needs high confidence
        if relevance == "Watchlist" and confidence < _RELEVANCE_WATCHLIST_MIN_CONFIDENCE:
            continue

        # Minimum confidence floor
        if confidence < _MIN_CONFIDENCE:
            continue

        # Minimum evidence check
        if not _has_minimum_evidence(research, area_id):
            continue

        result.append({
            "area_id":    area_id,
            "area_label": ACTIVE_AREAS[area_id]["label"],
            "relevance":  relevance,
            "confidence": confidence,
            "rationale":  rationale,
            "evidence":   evidence,
        })

    # Sort: Direct first, then Adjacent, then Same-patient, then Watchlist
    _order = {"Direct": 0, "Adjacent": 1, "Same-patient": 2, "Watchlist": 3}
    result.sort(key=lambda x: (_order.get(x["relevance"], 9), -x["confidence"]))
    return result


def score_areas_node(state: IntakeState) -> IntakeState:
    """
    Step [3/4] — score area relevance. When nothing clears the threshold,
    print the (empty) area map and abort before writing to discovery_queue.
    """
    print("\n[3/4] Scoring area relevance...")
    state.relevant_areas = get_relevant_areas(state.research)

    if not state.relevant_areas:
        print("  No areas meet minimum evidence threshold.")
        print("  This company may not be relevant to active Meridian areas.")
        print_area_map(state.company_name, state.research, [], [])
        state.abort("no_relevant_areas")
        state.mark_complete("score_areas")
        return state

    for area in state.relevant_areas:
        print(f"  • {area['area_id']:<8} {area['relevance']:<15} confidence={area['confidence']:.0%}")

    state.mark_complete("score_areas")
    return state
