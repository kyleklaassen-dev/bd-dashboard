#!/usr/bin/env python3
"""
dryrun_meridian.py — safe, side-effect-free preview of the Meridian Writer.

WHY
---
The live Writer (write_meridian.py main()) calls the Anthropic API (cost — paused),
writes the Issue to Supabase, and deploys to GitHub Pages. This harness lets you
inspect the integration work WITHOUT any of that:

  default (assemble-only, ZERO API cost):
      Fetches live data from Supabase, builds every prompt block INCLUDING the new
      integration feed, assembles the exact Pass-1 and Pass-2 prompts, and writes
      them to outputs/ for review. No API call, no DB write, no deploy.

  --live (one real generation, still NO save/deploy):
      Additionally calls write_meridian.generate_html() to produce a real sample
      Issue HTML to outputs/. Calls the Anthropic API (costs tokens) but does NOT
      save to Supabase or deploy to GitHub. Use only when you want to eyeball a
      real issue and have accepted the API cost.

USAGE
    python3 scripts/dryrun_meridian.py            # assemble-only (free)
    python3 scripts/dryrun_meridian.py --live     # + one real generation
"""

import os, sys, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTDIR = os.path.join(ROOT, "outputs")
os.makedirs(OUTDIR, exist_ok=True)


def _read(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return default


# ── Env setup BEFORE importing write_meridian (its imports hard-require these) ──
SVC = _read(os.path.join(ROOT, ".supabase_service_key"))
ANON = _read(os.path.join(ROOT, ".supabase_anon_key"))
os.environ.setdefault("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", SVC)
if ANON:
    os.environ.setdefault("SUPABASE_ANON_KEY", ANON)
os.environ.setdefault("GITHUB_TOKEN", "dryrun-noop")          # never used (no deploy)
# Real API key only needed for --live; assemble-only never calls the API.
_akey = (_read(os.path.join(ROOT, ".anthropic_api_key"))
         or _read(os.path.join(ROOT, ".anthropic_key"))
         or "dryrun-noop")
os.environ.setdefault("ANTHROPIC_API_KEY", _akey)

sys.path.insert(0, HERE)
import write_meridian as wm   # noqa: E402

LIVE = "--live" in sys.argv

# Representative fallback scope if there is no fresh intel in the last 48h, so the
# harness always demonstrates the integration feed end-to-end.
FALLBACK_SEED = {
    "drugs": ["abs-101", "duvakitug", "tulisokibart"],
    "companies": ["absci", "merck", "sanofi", "takeda"],
    "indications": ["uc", "cd", "ibd"],
}


def main():
    stamp = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H%M")
    print(f"[dryrun] assemble-only={'no' if LIVE else 'yes'}  feed_available={wm.INTEGRATIONS_FEED_AVAILABLE}")

    # 1. Fetch live data (read-only) — same sources as main()
    intel    = wm.fetch_recent_intel(hours_back=48)
    deals    = wm.fetch_recent_deals(days_back=7)
    catalysts = wm.fetch_upcoming_catalysts()
    cal      = wm.fetch_catalyst_calendar(days_ahead=365)
    bd       = wm.fetch_bd_priority_companies()
    drugs, companies = wm.fetch_drug_context()
    ailux    = wm.fetch_ailux_position()
    recent   = wm.fetch_recent_meridian_issues(n=7)
    signals  = wm.fetch_company_signals()
    trials   = wm.fetch_recent_trials()
    ga, gt, gc = wm.fetch_graph_context()
    print(f"[dryrun] data: {len(intel)} intel · {len(deals)} deals · {len(drugs)} drugs · {len(companies)} companies")

    enriched = wm.enrich_intel_with_drug_context(intel, drugs, companies)

    # 2. Integration feed — real scope from intel, or fallback if no fresh intel
    if enriched:
        scope = wm.extract_scope_from_intel(enriched)
    else:
        from meridian_integrations_feed import expand_scope
        scope = expand_scope(FALLBACK_SEED)
        print("[dryrun] no fresh intel — using representative fallback scope")
    insights_block, integration_block = wm.render_feed(scope)
    print(f"[dryrun] scope: {len(scope['drugs'])} drugs / {len(scope['companies'])} companies / {len(scope['targets'])} targets")

    # 3. Build every other prompt block (same as generate_html)
    patient_context = wm.build_patient_context_block(enriched) if wm.PATIENT_INTEL_AVAILABLE else ""
    pstats = wm.fetch_patient_intelligence_stats()
    blocks = dict(
        intel_block=wm.build_intel_block(enriched),
        deals_block=wm.build_deals_block(deals),
        catalysts_block=wm.build_catalysts_block(catalysts),
        ailux_block=wm.build_ailux_block(ailux),
        prior_block=wm.build_prior_coverage_block(recent),
        signals_block=wm.build_company_signals_block(signals),
        trials_block=wm.build_trials_block(trials),
        graph_block=wm.build_graph_block(ga or {}, gt or {}, gc or []),
        catalyst_calendar_block=wm.build_catalyst_calendar_block(cal or []),
        bd_priority_block=wm.build_bd_priority_block(bd or {}),
        patient_context_block=patient_context or "(none)",
        patient_stats_block=wm.build_patient_stats_block(pstats) or "(none)",
        insights_block=insights_block,
        integration_block=integration_block,
    )

    now = datetime.datetime.utcnow()
    plan_prompt = wm.PLAN_PROMPT.format(date_long=now.strftime("%A, %B %d, %Y"), **{
        k: blocks[k] for k in (
            "intel_block","deals_block","ailux_block","prior_block","signals_block",
            "graph_block","insights_block","integration_block","patient_context_block",
            "patient_stats_block","catalyst_calendar_block","bd_priority_block")})

    draft_prompt = wm.DRAFT_PROMPT.format(
        date_long=now.strftime("%A, %B %d, %Y"),
        date_dateline=now.strftime("%A · %B %d · %Y"),
        plan_block="(dry-run placeholder — Pass 1 would generate the editorial plan here)",
        **{k: blocks[k] for k in (
            "intel_block","deals_block","catalysts_block","catalyst_calendar_block",
            "bd_priority_block","ailux_block","signals_block","trials_block","graph_block",
            "insights_block","integration_block","patient_context_block","patient_stats_block")})

    # 4. Write artifacts
    feed_path = os.path.join(OUTDIR, f"dryrun_feed_{stamp}.txt")
    with open(feed_path, "w") as f:
        f.write(f"SCOPE: {json.dumps(scope)}\n\n{'='*78}\n{insights_block}\n\n{'='*78}\n{integration_block}\n")

    prompts_path = os.path.join(OUTDIR, f"dryrun_prompts_{stamp}.txt")
    with open(prompts_path, "w") as f:
        f.write(f"# SYSTEM PROMPT (editorial identity + data-usage rules; ~{len(wm.SYSTEM_PROMPT)//4:,} tokens)\n")
        f.write("# NOTE: at live runtime main() also appends verification cautions + reader feedback.\n\n")
        f.write(wm.SYSTEM_PROMPT)
        f.write(f"\n\n\n{'#'*78}\n# PASS 1 — PLAN PROMPT (~{len(plan_prompt)//4:,} tokens, {len(plan_prompt):,} chars)\n\n")
        f.write(plan_prompt)
        f.write(f"\n\n\n{'#'*78}\n# PASS 2 — DRAFT PROMPT (~{len(draft_prompt)//4:,} tokens, {len(draft_prompt):,} chars)\n\n")
        f.write(draft_prompt)

    # 5. Confirmations
    has_genetics = "genetic" in integration_block.lower()
    has_insights = "STRATEGIC INSIGHTS" in insights_block
    print(f"[dryrun] feed written      → {feed_path}")
    print(f"[dryrun] prompts written   → {prompts_path}")
    print(f"[dryrun] PLAN  prompt ~{len(plan_prompt)//4:,} tokens")
    print(f"[dryrun] DRAFT prompt ~{len(draft_prompt)//4:,} tokens")
    print(f"[dryrun] genetics present in integration block: {has_genetics}")
    print(f"[dryrun] strategic insights present: {has_insights}")
    print(f"[dryrun] '{{insights_block}}' present in DRAFT prompt text: {insights_block[:40] in draft_prompt}")

    if LIVE:
        if os.environ.get("ANTHROPIC_API_KEY", "dryrun-noop") in ("dryrun-noop", ""):
            print("[dryrun] --live requested but no real ANTHROPIC_API_KEY found "
                  "(.anthropic_key or env). Skipping generation.")
            return
        print("[dryrun] --live: calling generate_html (real API; NO save/deploy)…")
        html, plan, *_ = wm.generate_html(
            intel, deals, catalysts, drugs, companies, ailux, recent, signals, trials,
            graph_active_in=ga, graph_targets=gt, graph_competes=gc,
            catalyst_calendar_events=cal, bd_priority_data=bd)
        html_path = os.path.join(OUTDIR, f"dryrun_issue_{stamp}.html")
        with open(html_path, "w") as f:
            f.write(html)
        print(f"[dryrun] sample issue HTML → {html_path} ({len(html):,} chars)  [NOT saved/deployed]")


if __name__ == "__main__":
    main()
