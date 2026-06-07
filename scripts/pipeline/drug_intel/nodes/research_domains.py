"""
Node 2: research_domains — run per-domain Claude calls and store Q&A records.
Iterates over DOMAIN_QUESTIONS, calls Claude for each, upserts results immediately.
"""
from __future__ import annotations
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from enrichment.drug_intelligence_researcher import (
    DOMAIN_QUESTIONS,
    call_claude_for_domain,
    store_qa,
)
from ..state import DrugIntelPipelineState


def run(state: DrugIntelPipelineState) -> DrugIntelPipelineState:
    domains_to_run = state.domains_filter or list(DOMAIN_QUESTIONS.keys())
    all_qa = []

    for domain in domains_to_run:
        if domain not in DOMAIN_QUESTIONS:
            print(f"  [SKIP] Unknown domain: {domain}")
            continue

        config = DOMAIN_QUESTIONS[domain]
        q_start, q_end = config["range"]
        print(f"  Domain: {domain} (Q{q_start}–Q{q_end})", end="", flush=True)

        t0 = time.time()
        qa_records = call_claude_for_domain(
            state.drug, domain, config, state.indication, verbose=state.verbose
        )
        elapsed = time.time() - t0
        print(f" → {len(qa_records)} answers in {elapsed:.1f}s")

        if qa_records:
            stored = store_qa(qa_records, dry_run=state.dry_run)
            state.qa_stored += stored
            if not state.dry_run and state.verbose:
                print(f"    Stored {stored} Q&A records.")

        all_qa.extend(qa_records)

        if not state.dry_run:
            time.sleep(0.5)

    state.all_qa = all_qa
    state.mark_complete("research_domains")
    return state
