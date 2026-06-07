"""Node 4: extract_timeline — extract development milestones from Q&A and store."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from enrichment.drug_intelligence_researcher import extract_timeline, store_timeline
from ..state import DrugIntelPipelineState


def run(state: DrugIntelPipelineState) -> DrugIntelPipelineState:
    print(f"  Extracting development timeline...", end="", flush=True)
    timeline = extract_timeline(state.drug, state.all_qa, verbose=state.verbose)
    stored = store_timeline(timeline, dry_run=state.dry_run)
    print(f" → {stored} timeline events")

    state.timeline = timeline
    state.timeline_stored = stored
    state.mark_complete("extract_timeline")
    return state
