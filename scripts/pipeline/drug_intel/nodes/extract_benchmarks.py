"""Node 3: extract_benchmarks — extract clinical benchmarks from Q&A and store."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from enrichment.drug_intelligence_researcher import extract_benchmarks, store_benchmarks
from ..state import DrugIntelPipelineState


def run(state: DrugIntelPipelineState) -> DrugIntelPipelineState:
    print(f"\n  Extracting clinical benchmarks...", end="", flush=True)
    benchmarks = extract_benchmarks(
        state.drug, state.indication, state.all_qa, verbose=state.verbose
    )
    stored = store_benchmarks(benchmarks, dry_run=state.dry_run)
    print(f" → {stored} benchmarks")

    state.benchmarks = benchmarks
    state.benchmarks_stored = stored
    state.mark_complete("extract_benchmarks")
    return state
