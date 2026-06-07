"""
Company enrichment pipeline orchestrator.

run_company_pipeline(state) is the single entry point that replaces the monolithic
enrich_company() body.  It calls 8 nodes in sequence, each of which reads from
and writes to a shared PipelineState object.

Node sequence
─────────────
  1. load_context          → state.ctx (CompanyContext)
  2. generate_catalysts    → state.catalysts_generated
  3. gather_web_intel      → state.web_intel      [skipped if state.skip_web_search]
  4. synthesize_enrichment → state.synth_result / synth_data / synth_raw_text
       ↳ returns early if synthesis failed
  5. validate_enrichment   → state.validated_data / validation_stats
  6. write_enrichment      → (writes to Supabase, no new state fields)
  7. score_completeness    → state.completeness_score / tier / missing
  8. generate_deals        → state.deals_created

Called from company_enrichment.enrich_company().
"""
from __future__ import annotations

import os
import sys

# Ensure scripts/ and scripts/enrichment/ resolve — needed when nodes are
# imported here before company_enrichment.py has configured sys.path.
_HERE    = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_HERE)
_ENRICH  = os.path.join(_SCRIPTS, "enrichment")
for _p in (_SCRIPTS, _ENRICH):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from _common import log  # noqa: E402
from pipeline.state import PipelineState  # noqa: E402
from pipeline.nodes.load_context         import load_context         # noqa: E402
from pipeline.nodes.generate_catalysts   import generate_catalysts   # noqa: E402
from pipeline.nodes.gather_web_intel     import gather_web_intel     # noqa: E402
from pipeline.nodes.synthesize_enrichment import synthesize_enrichment  # noqa: E402
from pipeline.nodes.validate_enrichment  import validate_enrichment  # noqa: E402
from pipeline.nodes.write_enrichment     import write_enrichment     # noqa: E402
from pipeline.nodes.score_completeness   import score_completeness   # noqa: E402
from pipeline.nodes.generate_deals       import generate_deals       # noqa: E402


def run_company_pipeline(state: PipelineState) -> PipelineState:
    """
    Execute Steps 4-6 for one company × area via pipeline nodes.

    Returns the final PipelineState.  state.ok is False only if synthesis failed
    (mirroring the original enrich_company() boolean return).
    """
    log(f"\n{'='*56}")
    log(f"Enriching: {state.company_id} / {state.area_id}")
    log(f"{'='*56}")

    # ── Node 1: Load Supabase context ──────────────────────────────────────
    log("Fetching Supabase context...", indent=1)
    state = load_context(state)
    log(
        f"  {len(state.ctx.drugs)} drugs | {len(state.ctx.trials)} trials | "
        f"{len(state.ctx.catalysts)} catalysts | {len(state.ctx.deals)} deals | "
        f"{len(state.ctx.recent_intel)} intel items",
        indent=1,
    )

    # ── Node 2: Auto-catalysts from trial dates ────────────────────────────
    log("STEP 4 — Catalyst auto-generation...", indent=1)
    state = generate_catalysts(state)
    log(f"  {state.catalysts_generated} new catalysts", indent=1)

    # ── Node 3: Web intelligence (Phase A) ────────────────────────────────
    log("STEP 5 — Claude enrichment...", indent=1)
    log("  Phase A — Web intelligence search...", indent=1)
    if not state.skip_web_search:
        state = gather_web_intel(state)
        if state.web_intel:
            log(f"  Web intelligence gathered ({len(state.web_intel)} chars)", indent=1)
        else:
            log("  No web intelligence (continuing with Supabase context only)", indent=1)
    else:
        log("  Skipped (--skip-web-search flag set) — using Supabase context only", indent=1)

    # ── Node 4: Claude synthesis (Phase B) ────────────────────────────────
    log("  Phase B — Claude synthesis...", indent=1)
    state = synthesize_enrichment(state)
    if not state.ok:
        # synthesize_enrichment already recorded the error; surface it here
        log("  Claude failed or parse error — skipping", indent=1)
        return state

    # ── Node 5: Validate drug_updates + trajectory patches ────────────────
    state = validate_enrichment(state)

    # ── Node 6: Write validated data to Supabase ──────────────────────────
    state = write_enrichment(state)

    # ── Node 7: Completeness scoring ──────────────────────────────────────
    log("  Completeness scoring...", indent=1)
    state = score_completeness(state)
    log(
        f"  Score: {state.completeness_score}/100 ({state.completeness_tier}) | "
        f"{len(state.completeness_missing)} missing field(s)",
        indent=1,
    )
    if state.completeness_missing:
        log(f"    Missing: {', '.join(state.completeness_missing[:8])}", indent=2)

    # ── Node 8: Deal intelligence ──────────────────────────────────────────
    log("STEP 6 — Deal intelligence...", indent=1)
    state = generate_deals(state)
    log(f"  {state.deals_created} new deals", indent=1)

    return state
