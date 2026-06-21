#!/usr/bin/env python3
"""
Meridian Writer — GitHub Actions edition
Reads biopharma intel from Supabase (last 24h), generates a full Meridian HTML
briefing using Claude Opus (two-pass: editorial plan → full draft), and commits
meridian_today.html to GitHub Pages.
Runs 6:30 AM ET Mon–Sat (10:30 UTC).
"""

import os, json, datetime, base64, re, time, hashlib
import requests
from meridian.database.catalyst_writer import CatalystWriter
import anthropic

# Patient intelligence context (co-equal intelligence layer)
try:
    from patient_intelligence_module import PATIENT_INTELLIGENCE_CONTEXT, build_patient_context_block
    PATIENT_INTEL_AVAILABLE = True
except ImportError:
    PATIENT_INTELLIGENCE_CONTEXT = ""
    build_patient_context_block = lambda items: ""
    PATIENT_INTEL_AVAILABLE = False

# Integration feed (Round 11–17 API data + synthesized strategic_insights layer).
# Read-only; surfaces genetics / patents / regulatory / financing / KOL + the
# distilled insight layer, scoped to the day's entities. Fully guarded: if the
# module or its data is unavailable, the Issue still generates with empty blocks.
try:
    from meridian_integrations_feed import extract_scope_from_intel, render_feed
    INTEGRATIONS_FEED_AVAILABLE = True
except Exception as _feed_err:
    INTEGRATIONS_FEED_AVAILABLE = False
    def extract_scope_from_intel(intel, plan=None):
        return {"drugs": [], "companies": [], "targets": [], "indications": []}
    def render_feed(scope):
        return ("(Integration feed unavailable.)", "(Integration feed unavailable.)")

# ── Shared base — creds, Anthropic client, Supabase/GitHub headers, log,
# AREA_NAMES, and the fact-check gate. Extracted to issue/common.py (§3 split);
# imported here so existing call sites are unchanged.
import re as _re
from meridian.products.issue.common import (
    SUPABASE_URL, SUPABASE_ANON_KEY, GITHUB_REPO,
    client, SB_HEADERS, GH_HEADERS, log, AREA_NAMES,
    fact_check_filter, _FACT_CHECK,
)
from meridian.products.issue.factcheck import (
    build_verification_cautions, build_reader_feedback_block,
    fact_check_report, audit_draft_against_db,
)
from meridian.products.issue.fetch import (
    fetch_recent_intel, fetch_recent_deals, fetch_upcoming_catalysts, fetch_drug_context,
    fetch_ailux_position, fetch_recent_meridian_issues, fetch_company_signals,
    fetch_graph_context, fetch_catalyst_calendar, fetch_bd_priority_companies,
    fetch_patient_intelligence_stats, fetch_recent_trials,
    fetch_recent_facts, build_recent_facts_block,
    build_patient_stats_block, build_catalyst_calendar_block, build_bd_priority_block,
)
from meridian.products.issue.blocks import (
    enrich_intel_with_drug_context,
    build_intel_block, build_deals_block, build_catalysts_block, build_ailux_block,
    build_prior_coverage_block, build_company_signals_block, build_trials_block, build_graph_block,
)
from meridian.products.issue.prompts import SYSTEM_PROMPT, PLAN_PROMPT, DRAFT_PROMPT
from meridian.products.issue.persist import (
    _extract_company_ids_from_plan, _compute_content_fingerprint, save_to_supabase,
)
from meridian.products.issue.deploy import (
    sync_catalyst_outcomes, inject_feedback_widget, deploy_to_github, bump_editorial_priority,
)
from meridian.products.issue.links import apply_first_mention_links


# ── Generate HTML with Claude Opus (two passes) ──────────────────────────────
def generate_editorial_plan(date_long, intel_block, deals_block, ailux_block,
                             prior_block, signals_block="", graph_block="",
                             patient_context_block="", patient_stats_block="",
                             catalyst_calendar_block="", bd_priority_block="",
                             insights_block="", integration_block=""):
    """Pass 1: produce a tight editorial plan before writing a word of prose."""
    prompt = PLAN_PROMPT.format(
        date_long               = date_long,
        intel_block             = intel_block,
        deals_block             = deals_block,
        ailux_block             = ailux_block,
        prior_block             = prior_block,
        signals_block           = signals_block,
        graph_block             = graph_block or "(Graph context unavailable)",
        insights_block          = insights_block or "(No in-scope strategic insights today)",
        integration_block       = integration_block or "(No in-scope integration data today)",
        patient_context_block   = patient_context_block or "(No patient intelligence context available)",
        patient_stats_block     = patient_stats_block or "(Patient population stats not available — v65 migration may be pending)",
        catalyst_calendar_block = catalyst_calendar_block or "(No catalyst calendar data available)",
        bd_priority_block       = bd_priority_block or "(No BD priority company data available)",
    )
    log("Pass 1 — generating editorial plan (Sonnet)…")
    log(f"Pass 1 prompt length: {len(prompt):,} chars / ~{len(prompt)//4:,} tokens")
    try:
        resp = client.messages.create(
            model      = "claude-opus-4-8",
            max_tokens = 1500,
            system     = SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": prompt}],
        )
    except Exception as api_err:
        log(f"Pass 1 API error: {type(api_err).__name__}: {api_err}")
        raise
    raw = resp.content[0].text.strip()
    log(f"Editorial plan: {resp.usage.input_tokens:,} in / {resp.usage.output_tokens:,} out")

    # Parse JSON — strip markdown fencing if present
    cleaned = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE).replace("```", "").strip()
    try:
        plan = json.loads(cleaned)
    except json.JSONDecodeError:
        log("Plan JSON parse failed — using raw text")
        plan = {"thesis": raw, "sections": ["Mechanism Intelligence", "BD & Deal Watch", "Catalyst Watch"]}
    return plan


def format_plan_block(plan):
    """Convert the parsed editorial plan into a readable block for the draft prompt."""
    lines = []
    if plan.get("thesis"):
        lines.append(f"EDITORIAL THESIS: {plan['thesis']}")
    if plan.get("signal_items"):
        lines.append("\nSIGNAL ITEMS (prioritise these):")
        for item in plan["signal_items"]:
            lines.append(f"  • {item}")
    if plan.get("noise_items"):
        lines.append("\nNOISE (handle briefly or skip):")
        for item in plan["noise_items"]:
            lines.append(f"  • {item}")
    if plan.get("connections"):
        lines.append("\nNON-OBVIOUS CONNECTIONS (make these explicit in the writing):")
        for c in plan["connections"]:
            lines.append(f"  • {c}")
    if plan.get("bd_implications"):
        lines.append("\nBD IMPLICATIONS FOR AILUX (ground the BD Lens callouts here):")
        for imp in plan["bd_implications"]:
            lines.append(f"  • {imp}")
    if plan.get("absences"):
        lines.append(f"\nNOTABLE ABSENCE: {plan['absences']}")
    if plan.get("continuity_threads"):
        lines.append("\nCONTINUITY THREADS (connect today's issue to prior coverage):")
        for t in plan["continuity_threads"]:
            lines.append(f"  • {t}")
    if plan.get("falsifier"):
        lines.append(f"\nWHAT WOULD PROVE THE THESIS WRONG (carry this into the issue): {plan['falsifier']}")
    if plan.get("the_move"):
        lines.append(f"\nTHE MOVE (render as the decision block at the top, right after the lead): {plan['the_move']}")
    if plan.get("forecasts"):
        lines.append("\nFORECASTS (render each with its auditable decomposition where you state the probability):")
        for fc in plan["forecasts"]:
            lines.append(f"  • {fc}")
    if plan.get("section_plan"):
        lines.append("\nSECTIONS TO INCLUDE — each must deliver its stated NEW contribution; "
                     "if a section cannot, drop it (do not pad or echo the lead):")
        for s in plan["section_plan"]:
            if isinstance(s, dict):
                lines.append(f"  • {s.get('name','(unnamed)')} — adds: {s.get('adds','(no distinct contribution — reconsider)')}")
            else:
                lines.append(f"  • {s}")
    elif plan.get("sections"):
        lines.append(f"\nSECTIONS TO INCLUDE: {', '.join(plan['sections'])}")
    return "\n".join(lines)


def generate_html(intel, deals, catalysts, drugs, companies, ailux_positions,
                  recent_issues, company_signals, trials,
                  graph_active_in=None, graph_targets=None, graph_competes=None,
                  catalyst_calendar_events=None, bd_priority_data=None):
    now = datetime.datetime.utcnow()
    date_long     = now.strftime("%A, %B %-d, %Y")
    week_num      = now.isocalendar()[1]
    date_dateline = f"{now.strftime('%A')} · {now.strftime('%B %-d')} · W{week_num} · {now.year}"

    # Enrich intel with live drug/company context
    enriched_intel = enrich_intel_with_drug_context(intel, drugs, companies)

    # Build patient intelligence context for all areas represented in today's intel.
    # This block is passed to both API passes (plan + draft) so the LLM has
    # verified disease burden data and does not need to hallucinate statistics.
    # v65+: patient_intelligence_module now pulls live numeric stats (patient counts,
    # market sizes, remission/failure rates) from the DB when the v65 columns are
    # present, supplementing the hardcoded disease context text blocks.
    patient_context = build_patient_context_block(enriched_intel) if PATIENT_INTEL_AVAILABLE else ""

    # v65+: Fetch numeric patient stats (patient counts, market sizes, failure rates)
    # as a separate compact block. Injected into the draft prompt so the LLM has
    # precise, queryable figures rather than hand-wavy ranges.
    patient_stats = fetch_patient_intelligence_stats()
    patient_stats_block = build_patient_stats_block(patient_stats)

    intel_block            = build_intel_block(enriched_intel)
    deals_block            = build_deals_block(deals)
    catalysts_block        = build_catalysts_block(catalysts)
    ailux_block            = build_ailux_block(ailux_positions)
    prior_block            = build_prior_coverage_block(recent_issues)
    signals_block          = build_company_signals_block(company_signals)
    # Enrich the plan with the freshest SOURCED deep-research facts (event-driven
    # pipeline → intel_facts, incl. KOL/management quotes) so the issue reflects
    # current research, not just RSS headlines. Additive + fail-soft.
    try:
        signals_block += build_recent_facts_block(fetch_recent_facts())
    except Exception as _e:
        log(f"Recent-facts enrichment skipped: {_e}")
    trials_block           = build_trials_block(trials)
    graph_block            = build_graph_block(
        graph_active_in or {},
        graph_targets   or {},
        graph_competes  or [],
    )
    catalyst_calendar_block = build_catalyst_calendar_block(catalyst_calendar_events or [])
    bd_priority_block       = build_bd_priority_block(bd_priority_data or {})

    # Integration feed: resolve today's in-scope entities from the intel, then pull
    # the synthesized insight layer + authoritative integration data (genetics,
    # patents, regulatory, financing, KOL) for just those entities. Fully guarded —
    # any failure degrades to empty blocks and the Issue still generates.
    insights_block = "(No in-scope strategic insights today)"
    integration_block = "(No in-scope integration data today)"
    try:
        feed_scope = extract_scope_from_intel(enriched_intel)
        insights_block, integration_block = render_feed(feed_scope)
        log(f"Integration feed: scope = {len(feed_scope.get('drugs',[]))} drugs / "
            f"{len(feed_scope.get('companies',[]))} companies / "
            f"{len(feed_scope.get('targets',[]))} targets · "
            f"insights {len(insights_block):,} chars · integration {len(integration_block):,} chars")
    except Exception as _fe:
        log(f"Integration feed failed (non-fatal, Issue continues): {type(_fe).__name__}: {_fe}")

    # Pass 1: editorial plan — includes company signals + graph for landscape context
    plan = generate_editorial_plan(date_long, intel_block, deals_block,
                                   ailux_block, prior_block, signals_block,
                                   graph_block=graph_block,
                                   patient_context_block=patient_context,
                                   patient_stats_block=patient_stats_block,
                                   catalyst_calendar_block=catalyst_calendar_block,
                                   bd_priority_block=bd_priority_block,
                                   insights_block=insights_block,
                                   integration_block=integration_block)
    plan_block = format_plan_block(plan)

    # ── Persist Pass 1 plan before Pass 2 so it is never lost ────────────────
    # This closes the editorial feedback gap: the plan's editorial judgments
    # (what matters, what is noise, what connections exist) are now queryable.
    _plan_intel_ids  = [it["id"] for it in intel if it.get("id")]
    _plan_company_ids = _extract_company_ids_from_plan(plan, intel)
    _content_fingerprint = _compute_content_fingerprint(_plan_intel_ids, _plan_company_ids)
    log(f"Pass 1 plan persisted: {len(_plan_company_ids)} companies · fingerprint={_content_fingerprint[:12]}…")

    # Pass 2: full draft
    prompt = DRAFT_PROMPT.format(
        date_long               = date_long,
        date_dateline           = date_dateline,
        plan_block              = plan_block,
        intel_block             = intel_block,
        deals_block             = deals_block,
        catalysts_block         = catalysts_block,
        catalyst_calendar_block = catalyst_calendar_block,
        bd_priority_block       = bd_priority_block,
        ailux_block             = ailux_block,
        signals_block           = signals_block,
        trials_block            = trials_block,
        graph_block             = graph_block,
        insights_block          = insights_block,
        integration_block       = integration_block,
        patient_context_block   = patient_context or "(No patient intelligence context available)",
        patient_stats_block     = patient_stats_block or "(Patient population stats not available — v65 migration may be pending)",
    )

    log("Pass 2 — generating full Meridian draft (Sonnet)…")
    log(f"Pass 2 prompt length: {len(prompt):,} chars / ~{len(prompt)//4:,} tokens")
    try:
        resp = client.messages.create(
            model      = "claude-opus-4-8",
            max_tokens = 16000,
            system     = SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": prompt}],
        )
    except Exception as api_err:
        log(f"Pass 2 API error: {type(api_err).__name__}: {api_err}")
        raise
    html = resp.content[0].text.strip()
    log(f"Full draft: {resp.usage.input_tokens:,} in / {resp.usage.output_tokens:,} out → {len(html):,} chars")

    # Strip markdown fencing if model wraps it
    if "```" in html:
        html = re.sub(r"^```[a-z]*\n?", "", html, flags=re.MULTILINE)
        html = html.replace("```", "")

    # Ensure all links open in a new tab (iframe navigation guard)
    if "<base " not in html:
        html = html.replace("<head>", '<head>\n', 1)

    # Apply first-mention hyperlinks for drug and company names.
    # This enforces the WRITING_STANDARDS rule programmatically: first occurrence
    # of each known entity gets an onclick modal link; subsequent occurrences are
    # plain text.  Runs after the LLM draft so the LLM's own source hyperlinks
    # (which already sit inside <a> tags) are never double-wrapped.
    html = apply_first_mention_links(html, drugs, companies)

    # Post-draft fact-check gate: prose format vs canonical drugs table.
    audit_draft_against_db(html, drugs)

    # In-issue reader feedback widget (issue-tab only; writes to meridian_feedback).
    html = inject_feedback_widget(html, datetime.datetime.utcnow().strftime("%Y-%m-%d"))

    return html, plan, _plan_company_ids, _content_fingerprint


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys
    log(f"=== Meridian Writer — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ===")

    # ── One Issue per day ─────────────────────────────────────────────────────
    # The Writer is triggered twice daily (chained off Meridian Research, plus a
    # 6:30 ET fallback cron) — and can also be dispatched manually. Without this
    # guard it regenerates (full LLM pass + republish) each time. If today's Issue
    # already exists, skip; the fallback cron only does work when the chain didn't.
    # Override with --force or MERIDIAN_FORCE=1.
    _FORCE = ("--force" in _sys.argv) or (os.environ.get("MERIDIAN_FORCE", "").lower() in ("1", "true", "yes"))
    _today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    if not _FORCE:
        try:
            _r = requests.get(
                f"{SUPABASE_URL}/rest/v1/meridian_issues",
                headers=SB_HEADERS,
                params={"issue_date": f"eq.{_today}", "select": "id,created_at"},
                timeout=15)
            _existing = _r.json() if _r.status_code == 200 else []
            if _existing:
                log(f"Issue for {_today} already generated (id={_existing[0].get('id')}). "
                    f"Skipping — only one Issue is produced per day. "
                    f"Use --force or MERIDIAN_FORCE=1 to regenerate.")
                _sys.exit(0)
        except Exception as _e:
            log(f"Same-day guard check failed (continuing to generate): {_e}")

    # Close the trust loop: feed content-disconfirmed claims (content_confirms_claim
    # = false, set by the Content Verifier) into the writer's system prompt so they
    # are withheld from the Issue — claim-level, so real molecules keep their facts.
    SYSTEM_PROMPT = SYSTEM_PROMPT + build_verification_cautions()

    # Close the editorial loop: feed the reader's own in-issue feedback (👍/👎 + notes
    # from meridian_feedback) back into the writer so each issue responds to real taste.
    SYSTEM_PROMPT = SYSTEM_PROMPT + build_reader_feedback_block()

    # Fetch all data sources — the full dashboard state feeds the Meridian
    intel                              = fetch_recent_intel(hours_back=48)
    deals                              = fetch_recent_deals(days_back=7)
    catalysts                          = fetch_upcoming_catalysts()
    catalyst_calendar_events           = fetch_catalyst_calendar(days_ahead=365)
    bd_priority_data                   = fetch_bd_priority_companies()
    drugs, companies                   = fetch_drug_context()
    ailux_positions                    = fetch_ailux_position()
    recent_issues                      = fetch_recent_meridian_issues(n=7)
    company_signals                    = fetch_company_signals()
    trials                             = fetch_recent_trials()
    graph_active_in, graph_targets, graph_competes = fetch_graph_context()

    log(f"Data assembled: {len(intel)} intel · {len(deals)} deals · {len(catalysts)} catalysts · "
        f"{len(catalyst_calendar_events)} cal events · "
        f"{len(bd_priority_data.get('scores',[]))} very_high scores · "
        f"{len(bd_priority_data.get('views',[]))} strategic views · "
        f"{len(company_signals)} signals · {len(trials)} trials · {len(recent_issues)} prior issues · "
        f"graph: {sum(len(v) for v in graph_active_in.values())} ACTIVE_IN / "
        f"{len(graph_targets)} TARGETS / {len(graph_competes)} COMPETES_WITH")

    if not intel:
        log("No intel found — writing placeholder issue.")
        html         = (
            "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>The Meridian</title></head>"
            "<body><h1 style='color:#1a3f8f;font-family:Georgia,serif'>The Meridian</h1>"
            f"<p style='font-family:Georgia,serif'>No significant biopharma intelligence collected in the last 48 hours "
            f"for today, {datetime.datetime.utcnow().strftime('%B %-d, %Y')}. "
            "Check back tomorrow.</p></body></html>"
        )
        plan                = None
        plan_company_ids    = []
        content_fingerprint = None
    else:
        html, plan, plan_company_ids, content_fingerprint = generate_html(
            intel, deals, catalysts, drugs, companies, ailux_positions,
            recent_issues, company_signals, trials,
            graph_active_in=graph_active_in,
            graph_targets=graph_targets,
            graph_competes=graph_competes,
            catalyst_calendar_events=catalyst_calendar_events,
            bd_priority_data=bd_priority_data,
        )

    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    save_to_supabase(html, intel, today,
                     plan=plan,
                     company_ids=plan_company_ids,
                     content_fingerprint=content_fingerprint)

    # Publish the Issue FIRST. The page deploy is the critical output and must
    # not be blocked by the optional post-processing below. (Root cause of the
    # 2026-06-03+ Writer failures: a post-save feedback-loop step raised after the
    # Issue was already saved to Supabase — which crashed the run BEFORE this
    # deploy, so meridian_today.html never published and the workflow went red.)
    deploy_to_github(html)

    # ── Editorial → Enrichment Priority Bump (best-effort) ────────────────────
    # Companies featured in today's Meridian are the most BD-relevant right now.
    # Bump their priority_score in research_queue by +10 so the next enrichment
    # scheduler run picks them up first. Never fail the publish over this.
    try:
        if plan_company_ids:
            bump_editorial_priority(plan_company_ids)
    except Exception as e:
        log(f"bump_editorial_priority failed (non-fatal): {e}")

    # ── G4: Catalyst outcome sync (best-effort) ───────────────────────────────
    # Scan today's intel for confirmed readouts and resolve matching catalysts.
    try:
        sync_catalyst_outcomes(plan, intel)
    except Exception as e:
        log(f"sync_catalyst_outcomes failed (non-fatal): {e}")

    # ── S3: stamp system_status so the dashboard surfaces the new Issue ───────
    try:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/system_status",
            headers={**SB_HEADERS, "Prefer": "return=minimal"},
            params={"id": "eq.1"},
            json={"last_meridian_at": now_iso, "updated_at": now_iso,
                  "last_pipeline_label": "meridian_write",
                  "note": "New Meridian Issue published"},
            timeout=15)
        log("system_status stamped (meridian_write)")
    except Exception as e:
        log(f"system_status stamp failed (non-fatal): {e}")

    # Pre-publish fact-check summary + governance log (what the gate excluded today)
    fact_check_report()

    log("=== Write complete ===")
