#!/usr/bin/env python3
"""
drug_intake.py — Drug-First Discovery Engine (Task #93)

CLI tool: python src/meridian/ingestion/drug_intake.py --drug "Tozorakimab"

PURPOSE
-------
Entry point into the Meridian entity graph from a drug anchor.

Given a drug name, this script:
  1. Resolves drug identity against the Meridian drugs table
  2. Fetches the current graph state (what Meridian already knows)
  3. Researches the drug open-endedly via Claude Sonnet
  4. Produces two outputs:
       Output A — Routing Decision: which areas does this drug belong in, at what overlap tier?
       Output B — Completeness Audit: what does the graph still need for this drug?
  5. Writes a discovery_queue row with source='drug_intake', coverage_score,
     completeness_gaps, promotion_payload, and evidence_tier for human review

MODEL TIER RULE
---------------
Live writes require Claude Sonnet. Haiku is blocked for live writes.
Use --dry-run with INTAKE_MODEL=claude-haiku-4-5-20251001 for fast structural validation.

EVIDENCE TIER
-------------
All drugs route through the same pipeline regardless of stage. The evidence_tier field
makes the confidence level explicit so reviewers can calibrate accordingly.

  Confirmed  — Named molecule + named company + clinical stage (Phase 1–Approved)
               High data quality. Can be promoted directly.
  Likely     — Named molecule + company source + preclinical/IND-enabling, OR
               medium data quality with clinical stage.
               Promote with standard review.
  Emerging   — Mechanism known, molecule partially named or stage=Discovery/Undisclosed.
               Low data quality. Promote only after manual verification.
  Hypothesis — Strategic inference only. No named molecule or no company anchor.
               Do NOT create a production drug row without manual approval.
               Keep as signal unless evidence is subsequently confirmed.

COMBO COMPONENT RULE
--------------------
If a combination drug (e.g. guselkumab-golimumab) is linked to an area,
each component drug is checked for: existence in drugs, drug_areas, drug_area_scores.
Missing component area links are surfaced as warnings (graph completeness gaps).

USAGE
-----
  python src/meridian/ingestion/drug_intake.py --drug "Tozorakimab"
  python src/meridian/ingestion/drug_intake.py --drug "Amlitelimab" --area il4ra
  python src/meridian/ingestion/drug_intake.py --drug "QX031N" --company "Qyuns" --dry-run
  python src/meridian/ingestion/drug_intake.py --drug "Tozorakimab" --dry-run --verbose

ENVIRONMENT
-----------
  ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
  INTAKE_MODEL  (optional) — model override; defaults to claude-sonnet-4-6
                             Haiku blocked for live writes.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    import requests
except ImportError:
    import urllib.request as _ur, urllib.parse as _up, urllib.error as _ue, json as _rjson
    class _Resp:
        def __init__(self, code, body):
            self.status_code = code
            self._body = body
        def json(self):     return _rjson.loads(self._body)
        @property
        def text(self):     return self._body.decode() if isinstance(self._body, bytes) else self._body
    class _Requests:
        @staticmethod
        def _call(method, url, headers=None, params=None, json=None, **kw):
            if params: url += '?' + _up.urlencode(params)
            data = _rjson.dumps(json).encode() if json else None
            req  = _ur.Request(url, data=data, headers=headers or {}, method=method)
            try:
                with _ur.urlopen(req) as r: return _Resp(r.status, r.read())
            except _ue.HTTPError as e:      return _Resp(e.code,   e.read())
        def get(self,  url, **kw): return self._call('GET',  url, **kw)
        def post(self, url, **kw): return self._call('POST', url, **kw)
        def patch(self,url, **kw): return self._call('PATCH',url, **kw)
    requests = _Requests()

import anthropic

# ── §3 SPLIT — base + research/scoring/queue now in meridian.ingestion.drugintake.* ──
from meridian.ingestion.drugintake.common import (
    SUPABASE_URL, ACTIVE_AREAS,
)
from meridian.ingestion.drugintake.research import resolve_drug_identity, fetch_graph_state, research_drug, get_relevant_areas
from meridian.ingestion.drugintake.scoring import compute_coverage_score, compute_evidence_tier, check_combo_components
from meridian.ingestion.drugintake.queue import write_drug_queue_rows


def _print_routing_decision(
    drug_name: str,
    research: dict,
    relevant_areas: list[dict],
    resolution: dict,
    evidence_tier: dict | None = None,
    combo_warnings: list[dict] | None = None,
    area_scores: list[dict] | None = None,
):
    drug_info = research.get("drug", {})
    rtype     = resolution.get("resolution_type", "candidate_new")

    print()
    print("═" * 65)
    print(f"  OUTPUT A — ROUTING DECISION")
    print("─" * 65)
    print(f"  Drug:    {drug_info.get('canonical_name', drug_name)}")
    if drug_info.get("brand_name"):
        print(f"           ({drug_info['brand_name']})")
    print(f"  Company: {drug_info.get('company', 'Unknown')}")
    print(f"  Target:  {drug_info.get('target', '?')}")
    print(f"  Stage:   {drug_info.get('stage', '?')} — {drug_info.get('primary_indication', '?')}")
    print(f"  Identity: {rtype}")
    if resolution.get("drug_id"):
        print(f"           → Meridian ID: {resolution['drug_id']}")

    # Evidence tier
    if evidence_tier:
        tier = evidence_tier["tier"]
        tier_icon = {"Confirmed": "✅", "Likely": "🟡", "Emerging": "🟠", "Hypothesis": "🔴"}.get(tier, "")
        print(f"  Evidence: {tier_icon} {tier} — {evidence_tier['rationale']}")
        if tier in ("Emerging", "Hypothesis"):
            print(f"  ⚠️  {evidence_tier['review_note']}")
    print()

    if not relevant_areas:
        print("  ⚪ No areas meet the minimum evidence threshold.")
        print("  This drug may not be in scope for active Meridian areas.")
    else:
        # Build score lookup if provided
        score_lookup = {s["area_id"]: s["strategic_value_score"] for s in (area_scores or [])}
        for area in relevant_areas:
            conf_bar = "█" * int(area["confidence"] * 10) + "░" * (10 - int(area["confidence"] * 10))
            svs      = score_lookup.get(area["area_id"])
            svs_str  = f"  Strategic Value: {svs}/10" if svs is not None else ""
            print(f"  {area['relevance']:<15} {area['area_label']}{svs_str}")
            print(f"  Confidence  [{conf_bar}] {area['confidence']:.0%}")
            print(f"  Rationale   {area['rationale'][:120]}")
            if area["evidence"]:
                print(f"  Evidence    {area['evidence'][:120]}")
            print()

    if research.get("competitive_context"):
        print(f"  Context: {research['competitive_context'][:200]}")
    if research.get("bd_angle"):
        print(f"  BD Angle: {research['bd_angle'][:200]}")
    print(f"  Data quality: {drug_info.get('data_quality', 'unknown')}")

    # Combo component warnings
    if combo_warnings:
        print()
        print(f"  ⚠️  COMBO COMPONENT GAPS ({len(combo_warnings)} issue(s)):")
        for w in combo_warnings:
            icon = "❌" if w["issue"] == "component_drug_missing" else "⚠️ "
            print(f"    {icon} {w['component']} / {w['area_id']}: {w['suggestion']}")

    print("═" * 65)


# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT B — COMPLETENESS AUDIT
# ══════════════════════════════════════════════════════════════════════════════

_DIM_LABELS = {
    "identity":         "Identity",
    "company":          "Company",
    "target":           "Target",
    "trials":           "Trials",
    "catalysts":        "Catalysts",
    "molecule_intel":   "Molecule Intel",
    "conference_intel": "Conference Intel",
    "deals":            "Deals",
}

def _score_icon(score) -> str:
    if score is None:  return "N/A"
    if score >= 90:    return "✓ 100%"
    if score >= 60:    return "~ " + str(score) + "%"
    return "✗ " + str(score) + "%"


def _print_completeness_audit(
    drug_name: str,
    coverage: dict,
    research: dict,
    graph_state: dict,
):
    dims    = coverage["dimensions"]
    overall = coverage["coverage_score"]

    print()
    print("═" * 65)
    print(f"  OUTPUT B — COMPLETENESS AUDIT")
    print("─" * 65)
    print(f"  {drug_name} Coverage: {overall}%")
    print()

    for dim_key, dim_label in _DIM_LABELS.items():
        score = dims.get(dim_key)
        icon  = _score_icon(score)
        print(f"    {dim_label:<20} {icon}")

    # Missing fields
    missing = []
    if dims.get("molecule_intel", 0) < 90:
        missing.append("Molecule Intelligence")
    if dims.get("catalysts", 0) < 50:
        upcoming = research.get("upcoming_catalysts") or []
        if upcoming:
            missing.append(f"Catalysts (found {len(upcoming)} upcoming in research — run enrichment)")
        else:
            missing.append("Upcoming catalysts")
    if dims.get("trials", 0) < 90:
        ncts = research.get("drug", {}).get("nct_ids") or []
        if ncts:
            missing.append(f"Trial data ({len(ncts)} NCT IDs found — run trial sync)")
        else:
            missing.append("Trial summaries")
    if dims.get("conference_intel", 0) < 50:
        missing.append("Conference activity (last 90 days)")
    if dims.get("deals") is not None and dims.get("deals", 0) < 50:
        missing.append("Deals / licensing coverage")

    if missing:
        print()
        print(f"  Missing: {' · '.join(missing)}")

    # Recommendations
    recs = []
    if dims.get("molecule_intel", 0) < 90:
        recs.append("Run molecule intelligence enrichment")
    if dims.get("catalysts", 0) < 50:
        recs.append("Run catalyst enrichment")
    if dims.get("trials", 0) < 90:
        recs.append("Run trial data sync")
    if dims.get("conference_intel", 0) < 50:
        recs.append("Run signal monitoring")

    if recs:
        print(f"  Recommended: {' · '.join(recs)}")

    print("═" * 65)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — WRITE DISCOVERY QUEUE ROW
# ══════════════════════════════════════════════════════════════════════════════


def run_drug_intake(
    drug_name:    str,
    company_hint: str | None = None,
    area_filter:  str | None = None,
    dry_run:      bool = False,
    verbose:      bool = False,
    force:        bool = False,
):
    """
    Full drug intake workflow.
    Bounded stop: writes one reviewable discovery_queue row per relevant area.
    """
    ts     = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    slug   = drug_name.lower().replace(" ", "_").replace("-", "_")
    run_id = f"drug_intake_{slug}_{ts}"

    print()
    print(f"Drug Intake — '{drug_name}'")
    if area_filter:
        print(f"Area filter: {area_filter}")
    print(f"Run ID: {run_id}  |  dry_run={dry_run}")
    print("─" * 55)

    # ── Model-tier guard ─────────────────────────────────────────────────────
    _active_model = os.environ.get("INTAKE_MODEL", "claude-sonnet-4-6")
    if not dry_run and "haiku" in _active_model.lower():
        print(f"\n  ❌ Model tier error: INTAKE_MODEL='{_active_model}' cannot be used for live writes.")
        print(f"     Haiku hallucinates drug pipelines — fabricated drug names may enter discovery_queue.")
        print(f"     Set INTAKE_MODEL=claude-sonnet-4-6 (or unset INTAKE_MODEL) for live runs.")
        print(f"     Use --dry-run with Haiku for fast structural validation only.")
        return

    # ── Step 1: Drug identity resolution ────────────────────────────────────
    print("\n[1/5] Resolving drug identity...")
    resolution = resolve_drug_identity(drug_name, company_hint)
    rtype      = resolution["resolution_type"]
    drug_id    = resolution.get("drug_id")
    drug_row   = resolution.get("drug_row") or {}

    if rtype == "existing_drug":
        print(f"  ✅ Existing drug: '{drug_row.get('name', drug_name)}' (id: {drug_id}, score: {resolution['match_score']:.0%})")
        if drug_row.get("company_id"):
            print(f"     Company: {drug_row['company_id']} | Stage: {drug_row.get('stage','?')} | Target: {drug_row.get('target','?')}")
    elif rtype == "fuzzy_match":
        print(f"  ⚠️  Fuzzy match: '{drug_row.get('name', '')}' (id: {drug_id}, similarity: {resolution['match_score']:.0%})")
        print(f"     Proceeding as existing drug — use --force to confirm override")
    elif rtype == "ambiguous":
        print(f"  ⚠️  Ambiguous — multiple possible matches:")
        for c in resolution.get("candidates", [])[:3]:
            print(f"     • {c.get('name')} ({c.get('id')}) — {c.get('stage','?')} / {c.get('target','?')}")
        if not force:
            print(f"  Use --force to proceed as candidate_new, or use a more specific drug name.")
            return
        drug_id = None
        print(f"  --force: treating as candidate_new")
    else:
        print(f"  ℹ️  New drug candidate: '{drug_name}' — not found in Meridian")
        if company_hint:
            print(f"     Company hint: {company_hint}")

    company_id = drug_row.get("company_id") or company_hint

    # ── Step 2: Fetch current graph state ────────────────────────────────────
    print("\n[2/5] Fetching current graph state...")
    graph_state = fetch_graph_state(drug_id, company_id)

    if verbose:
        mi    = graph_state["molecule_intelligence"]
        trials = graph_state["trials"]
        cats  = graph_state["catalysts"]
        sigs  = graph_state["signals"]
        das   = graph_state["drug_area_scores"]
        print(f"  Molecule Intel:  {'✅ exists' if mi else '⚠️  missing'}")
        print(f"  Trials:          {len(trials)} row(s)")
        print(f"  Catalysts:       {len(cats)} upcoming row(s)")
        print(f"  Signals:         {len(sigs)} (last 90 days)")
        print(f"  Drug Area Scores: {len(das)} row(s)")
    else:
        has_mi = "✅" if graph_state["molecule_intelligence"] else "⚠️"
        print(f"  {has_mi} MI | {len(graph_state['trials'])} trials | {len(graph_state['catalysts'])} catalysts | {len(graph_state['signals'])} signals")

    # ── Step 3: Research ─────────────────────────────────────────────────────
    print(f"\n[3/5] Researching {drug_name}...")
    company_for_research = drug_row.get("company_id") or company_hint
    research = research_drug(drug_name, company_for_research, verbose=verbose)
    if not research:
        print("  ❌ Research failed. Cannot proceed.")
        return

    # ── Step 4: Score area relevance + evidence tier ─────────────────────────
    print("\n[4/5] Scoring area relevance and evidence tier...")
    relevant_areas = get_relevant_areas(research, area_filter)
    evidence_tier  = compute_evidence_tier(research)

    if not relevant_areas:
        if area_filter:
            print(f"  {area_filter} area does not meet the minimum evidence threshold for '{drug_name}'.")
        else:
            print(f"  No areas meet minimum evidence threshold.")
            print(f"  This drug may not be in scope for active Meridian areas.")
    else:
        for area in relevant_areas:
            print(f"  • {area['area_id']:<8} {area['relevance']:<15} confidence={area['confidence']:.0%}")

    tier_icon = {"Confirmed": "✅", "Likely": "🟡", "Emerging": "🟠", "Hypothesis": "🔴"}.get(evidence_tier["tier"], "")
    print(f"  {tier_icon} Evidence tier: {evidence_tier['tier']}")
    if evidence_tier["tier"] == "Hypothesis" and not dry_run:
        print(f"\n  🔴 Hypothesis-tier drug: no production drug row will be created without manual approval.")
        print(f"     Queue row will be written as a reviewable signal with status=pending.")

    # ── Combo component check ─────────────────────────────────────────────────
    combo_warnings = []
    if relevant_areas and drug_row:
        area_ids_for_combo = [a["area_id"] for a in relevant_areas]
        combo_warnings = check_combo_components(drug_id, drug_name, drug_row, area_ids_for_combo, verbose=verbose)
        if combo_warnings:
            print(f"\n  ⚠️  Combo component gaps detected ({len(combo_warnings)}):")
            for w in combo_warnings:
                print(f"     {w['component']} / {w['area_id']}: {w['issue']}")

    # ── Step 5: Compute coverage + write queue rows ───────────────────────────
    print("\n[5/5] Computing coverage score and writing queue row(s)...")
    coverage = compute_coverage_score(resolution, graph_state, research)
    print(f"  Coverage: {coverage['coverage_score']}%")

    written      = []
    area_scores  = []
    if relevant_areas:
        written, area_scores = write_drug_queue_rows(
            drug_name      = drug_name,
            drug_id        = drug_id,
            company_id     = company_id,
            resolution     = resolution,
            research       = research,
            relevant_areas = relevant_areas,
            coverage       = coverage,
            evidence_tier  = evidence_tier,
            graph_state    = graph_state,
            run_id         = run_id,
            dry_run        = dry_run,
        )

    # ── Outputs ───────────────────────────────────────────────────────────────
    _print_routing_decision(drug_name, research, relevant_areas, resolution,
                            evidence_tier=evidence_tier, combo_warnings=combo_warnings,
                            area_scores=area_scores)
    _print_completeness_audit(drug_name, coverage, research, graph_state)

    if written and not dry_run:
        print(f"\n  {len(written)} row(s) written to discovery_queue (source=drug_intake, status=pending)")
        print("  → Review in Meridian Dashboard → Discovery Queue tab")
    elif written and dry_run:
        print(f"\n  [DRY RUN] {len(written)} row(s) would be written.")
    elif not relevant_areas:
        print(f"\n  No queue rows written (no areas meet threshold).")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Drug-First Discovery Engine — Meridian Drug Intake CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/meridian/ingestion/drug_intake.py --drug "Tozorakimab"
  python src/meridian/ingestion/drug_intake.py --drug "Amlitelimab" --area il4ra
  python src/meridian/ingestion/drug_intake.py --drug "QX031N" --company "Qyuns" --dry-run
  python src/meridian/ingestion/drug_intake.py --drug "Tozorakimab" --dry-run --verbose
        """,
    )
    parser.add_argument("--drug",    required=True,  help="Drug name to research")
    parser.add_argument("--company", default=None,   help="Company hint (helps for unknown drugs)")
    parser.add_argument("--area",    default=None,   choices=list(ACTIVE_AREAS.keys()), help="Constrain scoring to one area")
    parser.add_argument("--dry-run", action="store_true", help="Research but do not write to Supabase")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--force",   action="store_true", help="Force proceed past ambiguous identity or existing drug")

    args = parser.parse_args()

    run_drug_intake(
        drug_name    = args.drug,
        company_hint = args.company,
        area_filter  = args.area,
        dry_run      = args.dry_run,
        verbose      = args.verbose,
        force        = args.force,
    )
