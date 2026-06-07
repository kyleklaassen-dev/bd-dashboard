"""
Node 2: synthesize
Builds the enrichment prompt and calls Claude.
Populates state.prompt, state.llm_raw.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from enrichment._common import log
import enrichment.ai.client as ai_client
from enrichment.ai.client import PromptConfig
from ..state import DrugPipelineState

_DRUG_ENRICH_CFG = PromptConfig(
    name="drug_enrichment",
    system="You are a BD intelligence analyst. Return ONLY valid JSON — no markdown fences, no commentary.",
    model="claude-sonnet-4-6",
    max_tokens=800,
)


def run(state: DrugPipelineState) -> DrugPipelineState:
    from enrichment.drug_enrichment import build_enrichment_prompt

    prompt = build_enrichment_prompt(state.ctx)
    state.prompt = prompt

    result = ai_client.run_json(_DRUG_ENRICH_CFG, prompt)
    log(f"  Claude: {result.tokens_in}in/{result.tokens_out}out "
        f"${result.cost_usd:.4f} stop={result.stop_reason}", indent=2)

    if not result.ok:
        state.add_error("synthesize", "LLM call or JSON parse failed")
        return state

    state.llm_raw = result.data
    log(f"  Parsed keys: {list(result.data.keys())}", indent=2)

    state.mark_complete("synthesize")
    return state
