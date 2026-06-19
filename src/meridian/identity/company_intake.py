#!/usr/bin/env python3
"""
company_intake.py — Company-First Discovery Engine (Phase 1)

CLI tool: python -m meridian.identity.company_intake --company "Akeso"

PURPOSE
-------
Answers: "Is this company worth onboarding into Meridian, and which areas
          should it be enriched for?"

This is a *routing* tool, not a *classification* tool. It produces a discovery
package that goes into discovery_queue for human review. Final area scoring
and drug-level intelligence happen in research_intelligence.py AFTER approval.

WORKFLOW
--------
1. Resolve company identity via CompanyIdentityResolver
   - resolved_existing  → report what Meridian already knows, offer to re-enrich
   - alias_match        → same
   - unresolved         → warn about possible alias conflict, prompt for confirmation
   - candidate_new      → proceed with research

2. Research company across all active Meridian areas using Claude + ClinicalTrials.gov
   - Open-ended discovery prompt (no prior area assumption)
   - Identify molecules, targets, indications, trials, deals

3. Score area relevance for each active Meridian area
   - Direct / Adjacent / Same-patient competitor / Strategic watchlist / Not relevant
   - Minimum evidence threshold: at least one molecule OR one verified clinical program

4. Write discovery_queue rows with source='user_intake'
   - One row per relevant area (confidence ≥ 0.5)
   - Dedup: skip if same company×area row exists from last 30 days (not rejected)

5. Print summary area map to console

USAGE
-----
  python -m meridian.identity.company_intake --company "Akeso"
  python -m meridian.identity.company_intake --company "Hengrui" --dry-run
  python -m meridian.identity.company_intake --company "Zenas BioPharma" --verbose

ENVIRONMENT
-----------
  ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
  (or workspace files: .supabase_config, .supabase_service_key)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
import anthropic

# ── Resolver import ───────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meridian.identity.company_identity_resolver import CompanyIdentityResolver, get_credentials

# ── §3 SPLIT — base + research/queue/edges now in meridian.identity.intake.* ──
from meridian.identity.intake.common import (
    ANTHROPIC_API_KEY, SUPABASE_URL, _sb_headers, ACTIVE_AREAS,
)
from meridian.identity.intake.research import resolve_identity, research_company, get_relevant_areas
from meridian.identity.intake.queue import write_queue_rows
from meridian.identity.intake.edges import write_acquisition_edges, write_license_edges, write_active_in_edge


# ══════════════════════════════════════════════════════════════════════════════
# PRINTING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _print_area_map(company_name: str, research: dict, relevant_areas: list[dict], written: list[str]):
    co = research.get("company", {})
    print()
    print("═" * 65)
    print(f"  AREA MAP — {co.get('canonical_name', company_name)}")
    ticker = co.get("ticker")
    if ticker:
        print(f"  {ticker} · {co.get('exchange', '')} · {co.get('geography', '')}")
    print(f"  {co.get('tagline', '')}")
    print("═" * 65)

    if not relevant_areas:
        print("  No areas meet the minimum evidence threshold.")
        print("  Company may not operate in active Meridian focus areas.")
    else:
        for area in relevant_areas:
            aid = area["area_id"]
            label = ACTIVE_AREAS[aid]["label"]
            status = "✅ queued" if aid in written else "⏭️  skipped"
            conf_bar = "█" * int(area["confidence"] * 10) + "░" * (10 - int(area["confidence"] * 10))
            print(f"\n  {area['relevance']:<15} {label}")
            print(f"  Confidence  [{conf_bar}] {area['confidence']:.0%}  {status}")
            print(f"  Rationale   {area['rationale'][:120]}")
            if area["evidence"]:
                print(f"  Evidence    {area['evidence'][:120]}")

    pipeline = research.get("pipeline", [])
    if pipeline:
        print(f"\n  Pipeline ({len(pipeline)} drug{'s' if len(pipeline) != 1 else ''} found):")
        for d in pipeline[:6]:
            stage = d.get("stage", "?")
            print(f"    • {d['drug_name']} — {d['target']} — {stage} — {d['indication'][:60]}")
        if len(pipeline) > 6:
            print(f"    ... and {len(pipeline) - 6} more")

    deals = research.get("deals", [])
    if deals:
        print(f"\n  Deals ({len(deals)} found):")
        for dl in deals[:3]:
            print(f"    • {dl.get('date', '?')} — {dl.get('partner', '?')} — {dl.get('asset', '?')}")

    why = research.get("why_relevant")
    if why:
        print(f"\n  BD Angle: {why}")

    print()
    print(f"  Data quality: {research.get('data_quality', 'unknown')}")
    if written:
        print(f"  {len(written)} area row(s) written to discovery_queue (source=user_intake, status=pending)")
        print("  → Review in Meridian Dashboard → Discovery Queue tab")
    print("═" * 65)
    print()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def run_intake(company_name: str, dry_run: bool = False, verbose: bool = False, force: bool = False):
    """
    Full intake workflow for a single company name.
    """
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    slug = company_name.lower().replace(" ", "_").replace("&", "").replace("/", "_")
    run_id = f"intake_{slug}_{ts}"

    print()
    print(f"Company Intake — '{company_name}'")
    print(f"Run ID: {run_id}  |  dry_run={dry_run}")
    print("─" * 55)

    # ── Step 1: Identity resolution ──────────────────────────────────────────
    print("\n[1/4] Resolving company identity...")
    resolution = resolve_identity(company_name, dry_run=dry_run)
    rtype = resolution["resolution_type"]

    if rtype in ("resolved_existing", "alias_match"):
        existing_id = resolution["company_id"]
        print(f"  ℹ️  Company already in Meridian: {existing_id} ({rtype})")
        if not force:
            print(f"  Use --force to re-research an existing company.")
            print(f"  Or use the Company Database tab to view their current profile.")
            return
        print(f"  --force flag set: proceeding with research for {existing_id}")

    elif rtype == "unresolved":
        print(f"  ⚠️  Possible alias conflict detected:")
        print(f"     '{company_name}' is {resolution['fuzzy_ratio']:.0%} similar to "
              f"'{resolution['fuzzy_match']}' → {resolution['fuzzy_company_id']}")
        print(f"     If this is a new company, use --force to proceed.")
        print(f"     If this is an alias, add it via company_aliases table first.")
        if not force:
            return
        print(f"  --force flag set: treating as candidate_new.")

    else:
        # candidate_new — normal path
        print(f"  ✅ New company candidate: '{company_name}' (suggested_id: {resolution['canonical_name']})")

    company_id = resolution.get("company_id")  # None for new candidates

    # ── Model-tier guard ─────────────────────────────────────────────────────
    # Haiku hallucinates drug names and fabricates pipeline data.
    # Live writes to discovery_queue require Sonnet quality.
    _active_model = os.environ.get("INTAKE_MODEL", "claude-sonnet-4-6")
    if not dry_run and "haiku" in _active_model.lower():
        print(f"\n  ❌ Model tier error: INTAKE_MODEL='{_active_model}' cannot be used for live writes.")
        print(f"     Haiku hallucinates company pipelines — fabricated drug names may enter discovery_queue.")
        print(f"     Set INTAKE_MODEL=claude-sonnet-4-6 (or unset INTAKE_MODEL) for live runs.")
        print(f"     Use --dry-run with Haiku for fast structural validation only.")
        return

    # ── Step 2: Research ──────────────────────────────────────────────────────
    print("\n[2/4] Researching company across all Meridian areas...")
    research = research_company(company_name, verbose=verbose)
    if not research:
        print("  ❌ Research failed. Cannot proceed.")
        return

    # ── Step 3: Score area relevance ──────────────────────────────────────────
    print("\n[3/4] Scoring area relevance...")
    relevant_areas = get_relevant_areas(research)

    if not relevant_areas:
        print("  No areas meet minimum evidence threshold.")
        print("  This company may not be relevant to active Meridian areas.")
        _print_area_map(company_name, research, [], [])
        return

    for area in relevant_areas:
        print(f"  • {area['area_id']:<8} {area['relevance']:<15} confidence={area['confidence']:.0%}")

    # ── Step 4: Write queue rows ──────────────────────────────────────────────
    print(f"\n[4/4] Writing {len(relevant_areas)} row(s) to discovery_queue...")
    written = write_queue_rows(
        company_name   = company_name,
        company_id     = company_id,
        resolution     = resolution,
        research       = research,
        relevant_areas = relevant_areas,
        run_id         = run_id,
        dry_run        = dry_run,
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    _print_area_map(company_name, research, relevant_areas, written)


# ══════════════════════════════════════════════════════════════════════════════
# RE-AUDIT — diff live pipeline against DB drugs, push gaps to discovery_queue
# Extracted to intake/reaudit.py (§3 split). Re-exported so the CLI below + any
# existing importer keep working unchanged.
# ══════════════════════════════════════════════════════════════════════════════
from meridian.identity.intake.reaudit import (
    run_reaudit, _get_db_drugs_for_company, _drug_already_in_db,
)

# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Company-First Discovery Engine — research a company and route it to discovery_queue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m meridian.identity.company_intake --company "Akeso"
  python -m meridian.identity.company_intake --company "Hengrui Medicine" --verbose
  python -m meridian.identity.company_intake --company "Zenas BioPharma" --dry-run
  python -m meridian.identity.company_intake --company "AbbVie" --force       # re-research existing
  python -m meridian.identity.company_intake --company "UCB" --re-audit       # diff live pipeline vs DB
  python -m meridian.identity.company_intake --company "Candid" --re-audit --dry-run
        """,
    )
    parser.add_argument("--company",   required=True, help="Company name to research")
    parser.add_argument("--dry-run",   action="store_true", help="Research but do not write to Supabase")
    parser.add_argument("--verbose",   action="store_true", help="Print extra debug info")
    parser.add_argument("--force",     action="store_true",
                        help="Proceed even if company exists in DB or fuzzy conflict detected")
    parser.add_argument("--re-audit",  action="store_true",
                        help="Diff live pipeline against DB for an existing company; push gaps to discovery_queue")
    args = parser.parse_args()

    if args.re_audit:
        run_reaudit(
            company_name = args.company,
            dry_run      = args.dry_run,
            verbose      = args.verbose,
        )
    else:
        run_intake(
            company_name = args.company,
            dry_run      = args.dry_run,
            verbose      = args.verbose,
            force        = args.force,
        )
