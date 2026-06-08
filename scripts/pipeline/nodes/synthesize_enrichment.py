"""
Node: synthesize_enrichment
Phase B of Step 5 — sends the full Supabase context + web intelligence to Claude
and parses the structured JSON enrichment response.
"""
from __future__ import annotations

import os
import sys

_HERE     = os.path.dirname(os.path.abspath(__file__))
_PIPELINE = os.path.dirname(_HERE)
_SCRIPTS  = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import ai.client as ai_client                          # noqa: E402
import ai.prompts.company_enrichment as _p_enrichment  # noqa: E402
from _common import log                                 # noqa: E402
from pipeline.state import PipelineState                # noqa: E402


def _ce():
    import company_enrichment  # noqa: PLC0415
    return company_enrichment


def synthesize_enrichment(state: PipelineState) -> PipelineState:
    """
    Builds the Step 5 prompt (Supabase context + web_intel), calls
    ai_client.run_json(), and stores the result in:
      state.synth_result   — full RunResult (tokens, cost, stop_reason, ok)
      state.synth_data     — parsed JSON dict (empty on failure)
      state.synth_raw_text — raw LLM text (for trajectory storage)

    Sets an error on state and returns early if synthesis fails.
    """
    ce = _ce()
    prompt = ce.build_step5_prompt(
        state.company_id,
        state.area_id,
        state.ctx.as_dict(),
        web_intel=state.web_intel,
    )

    cfg = _p_enrichment.PROMPT_CFG_FAST if state.fast_model else _p_enrichment.PROMPT_CFG
    if state.fast_model:
        log(f"  [fast mode] Using {cfg.model} (max_tokens={cfg.max_tokens})", indent=1)

    synth = ai_client.run_json(
        cfg,
        prompt,
        system_override=_p_enrichment.get_system(),
        max_retries=3,
    )

    state.synth_result   = synth
    state.synth_raw_text = synth.raw_text if synth else ""
    state.synth_data     = synth.data if (synth and synth.ok) else {}

    if synth:
        log(f"  {synth.tokens_in}in / {synth.tokens_out}out "
            f"(${synth.cost_usd:.4f}) stop={synth.stop_reason}", indent=1)
        if synth.truncated:
            log("  WARNING: response truncated at max_tokens — JSON may be incomplete.", indent=1)

    if not synth or not synth.ok:
        state.add_error("synthesize_enrichment", "Claude failed or parse error")

    state.mark_complete("synthesize_enrichment")
    return state
