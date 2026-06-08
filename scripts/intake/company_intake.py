#!/usr/bin/env python3
"""
company_intake.py — Company-First Discovery Engine (Phase 1)

CLI tool: python scripts/company_intake.py --company "Akeso"

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

The actual workflow (both this "intake" mode and the "--re-audit" diff mode)
runs as a LangGraph pipeline — see pipeline/company_intake/. This module is
the thin CLI entry point: it loads credentials, builds the initial state, and
invokes the graph.

USAGE
-----
  python scripts/company_intake.py --company "Akeso"
  python scripts/company_intake.py --company "Hengrui" --dry-run
  python scripts/company_intake.py --company "Zenas BioPharma" --verbose

ENVIRONMENT
-----------
  ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
  (or workspace files: .supabase_config, .supabase_service_key)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

import requests

# ── Bootstrap: scripts/ on sys.path for _common, _db, ai.*, pipeline.* ───────
_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _common import load_credentials, sb_headers  # noqa: E402
import _db                                          # noqa: E402
import ai.client as ai_client                       # noqa: E402

SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY = load_credentials()
_db.init_db(SUPABASE_URL, SUPABASE_KEY)
ai_client.setup(ANTHROPIC_API_KEY)

_sb_headers = {**sb_headers(SUPABASE_KEY), "Prefer": "return=minimal"}

# Re-exported for callers that import the active-areas map from this module
# (the canonical definition now lives alongside the research prompt).
from pipeline.company_intake.nodes.research_company import ACTIVE_AREAS  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════════
# TRANSACTION INTAKE — ACQUISITION EDGE WRITER
# ══════════════════════════════════════════════════════════════════════════════
#
# Rule (v28, 2026-05-24): When a Transaction Intake processes an acquisition
# deal, it must write ownership_edges with deal_id set so every edge traces
# back to its originating deal record.
#
# Pattern for any acquisition:
#   1. Write (or find) deals row → get deal_id
#   2. Write ownership_edges:
#        • acquired_company ACQUIRED→ acquirer_company  (deal_id=deal_id)
#        • drug ORIGINATED_BY→ acquired_company          (deal_id=deal_id)
#        • drug CONTROLLED_BY→ acquirer_company          (deal_id=deal_id)
#
# Canonical examples (backfilled 2026-05-24):
#   UCB/Candid (deal 19), UCB/Antengene (deal 167), Merck/Prometheus (deal 28)
#
# Usage: call write_acquisition_edges() after a deals row is inserted and
# the company + drug IDs are confirmed.

def write_acquisition_edges(
    deal_id: int,
    acquirer_id: str,
    acquired_id: str,
    drug_ids: list[str],
    source_url: str | None = None,
    dry_run: bool = False,
) -> int:
    """
    Write ownership_edges for an acquisition transaction with deal_id FK set.

    Returns number of edges successfully written.
    """
    edges = [
        # Company-level acquisition edge
        {
            "subject_type":     "company",
            "subject_id":       acquired_id,
            "predicate":        "ACQUIRED",
            "object_type":      "company",
            "object_id":        acquirer_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        }
    ]

    for drug_id in drug_ids:
        # Drug originated in acquired company
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "ORIGINATED_BY",
            "object_type":      "company",
            "object_id":        acquired_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })
        # Drug now controlled by acquirer
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "CONTROLLED_BY",
            "object_type":      "company",
            "object_id":        acquirer_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })

    if dry_run:
        print(f"  [DRY RUN] Would write {len(edges)} acquisition ownership_edges (deal_id={deal_id})")
        for e in edges:
            print(f"    {e['subject_id']} -{e['predicate']}→ {e['object_id']}")
        return len(edges)

    ok = 0
    for edge in edges:
        try:
            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/ownership_edges",
                headers={**_sb_headers, "Prefer": "resolution=ignore-duplicates,return=representation"},
                json=edge,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                ok += 1
            else:
                print(f"  ⚠ Edge {edge['subject_id']}/{edge['predicate']}: {resp.status_code} {resp.text[:150]}")
        except Exception as e:
            print(f"  ❌ Edge write error: {e}")

    print(f"  ✓ {ok}/{len(edges)} acquisition ownership_edges written (deal_id={deal_id})")
    return ok


def write_license_edges(
    deal_id: int,
    licensor_id: str,
    licensee_id: str,
    drug_ids: list[str],
    source_url: str | None = None,
    dry_run: bool = False,
) -> int:
    """
    Write ownership_edges for a licensing deal with deal_id FK set.
    Used for in-licensing (licensee receives rights from licensor).
    """
    edges = []
    for drug_id in drug_ids:
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "ORIGINATED_BY",
            "object_type":      "company",
            "object_id":        licensor_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "LICENSED_IN",
            "object_type":      "company",
            "object_id":        licensee_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })
        edges.append({
            "subject_type":     "drug",
            "subject_id":       drug_id,
            "predicate":        "LICENSED_FROM",
            "object_type":      "company",
            "object_id":        licensor_id,
            "deal_id":          deal_id,
            "confidence_level": "confirmed",
            "source_url":       source_url,
            "source_type":      "press_release",
            "status":           "active",
            "created_by":       "company_intake",
        })

    if dry_run:
        print(f"  [DRY RUN] Would write {len(edges)} license ownership_edges (deal_id={deal_id})")
        return len(edges)

    ok = 0
    for edge in edges:
        try:
            resp = requests.post(
                f"{SUPABASE_URL}/rest/v1/ownership_edges",
                headers={**_sb_headers, "Prefer": "resolution=ignore-duplicates,return=representation"},
                json=edge,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                ok += 1
            else:
                print(f"  ⚠ Edge {edge['subject_id']}/{edge['predicate']}: {resp.status_code} {resp.text[:150]}")
        except Exception as e:
            print(f"  ❌ Edge write error: {e}")

    print(f"  ✓ {ok}/{len(edges)} license ownership_edges written (deal_id={deal_id})")
    return ok


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH CONSISTENCY — ACTIVE_IN EDGE WRITER
# ══════════════════════════════════════════════════════════════════════════════
#
# Rule (v29, 2026-05-24): Every company_areas write must be paired with a
# corresponding entity_edges ACTIVE_IN row so the graph can answer
# "who is active in [area]?" as a single predicate lookup.
#
# This function is called by approve_discovery.py immediately after each
# sb_upsert("company_areas", ...) call.
#
# Idempotent: uses resolution=ignore-duplicates so re-running is safe.

def write_active_in_edge(
    company_id: str,
    area_id: str,
    dry_run: bool = False,
    created_by: str = "approve_discovery",
) -> bool:
    """
    Write a single entity_edges ACTIVE_IN row for company → area.
    Returns True if written (or dry-run), False on error.

    Idempotent — safe to call even if the edge already exists.
    """
    edge = {
        "subject_type":      "company",
        "subject_id":        company_id,
        "predicate":         "ACTIVE_IN",
        "object_type":       "area",
        "object_id":         area_id,
        "confidence_level":  "confirmed",
        "generation_method": "deterministic",
        "rationale":         "Derived from company_areas table",
        "status":            "active",
        "created_by":        created_by,
    }

    if dry_run:
        print(f"  [DRY RUN] Would write ACTIVE_IN edge: {company_id} → {area_id}")
        return True

    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/entity_edges",
            headers={**_sb_headers, "Prefer": "resolution=ignore-duplicates,return=minimal"},
            json=edge,
            timeout=10,
        )
        if resp.status_code in (200, 201):
            print(f"  + entity_edges ACTIVE_IN: {company_id} → {area_id}")
            return True
        else:
            print(f"  ⚠ ACTIVE_IN edge {company_id}/{area_id}: {resp.status_code} {resp.text[:150]}")
            return False
    except Exception as e:
        print(f"  ❌ ACTIVE_IN edge write error ({company_id}/{area_id}): {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# RUN ENTRY POINTS — build initial state, invoke the LangGraph pipeline
# ══════════════════════════════════════════════════════════════════════════════

def _build_state(company_name: str, mode: str, run_prefix: str, **opts) -> "IntakeState":
    from pipeline.company_intake.state import IntakeState

    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    slug = company_name.lower().replace(" ", "_").replace("&", "").replace("/", "_")
    run_id = f"{run_prefix}_{slug}_{ts}"

    return IntakeState(
        company_name=company_name,
        mode=mode,
        run_id=run_id,
        supabase_url=SUPABASE_URL,
        supabase_key=SUPABASE_KEY,
        **opts,
    )


def run_intake(company_name: str, dry_run: bool = False, verbose: bool = False, force: bool = False):
    """Full intake workflow for a single company name."""
    from pipeline.company_intake.graph import build_intake_graph

    state = _build_state(company_name, "intake", "intake",
                         dry_run=dry_run, verbose=verbose, force=force)

    print()
    print(f"Company Intake — '{company_name}'")
    print(f"Run ID: {state.run_id}  |  dry_run={dry_run}")
    print("─" * 55)

    build_intake_graph().invoke(state)


def run_reaudit(company_name: str, dry_run: bool = False, verbose: bool = False) -> None:
    """
    Re-audit mode: research a known company's pipeline and diff against DB.
    Any drugs found in the live research but absent from the DB are pushed to
    discovery_queue with source='re_audit' for human review.

    Usage:
        python scripts/company_intake.py --company "UCB" --re-audit
        python scripts/company_intake.py --company "Candid Therapeutics" --re-audit --dry-run
    """
    from pipeline.company_intake.graph import build_intake_graph

    state = _build_state(company_name, "reaudit", "reaudit",
                         dry_run=dry_run, verbose=verbose)

    print()
    print(f"Pipeline Re-Audit — '{company_name}'")
    print(f"Run ID: {state.run_id}  |  dry_run={dry_run}")
    print("─" * 55)

    build_intake_graph().invoke(state)


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Company-First Discovery Engine — research a company and route it to discovery_queue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/company_intake.py --company "Akeso"
  python scripts/company_intake.py --company "Hengrui Medicine" --verbose
  python scripts/company_intake.py --company "Zenas BioPharma" --dry-run
  python scripts/company_intake.py --company "AbbVie" --force       # re-research existing
  python scripts/company_intake.py --company "UCB" --re-audit       # diff live pipeline vs DB
  python scripts/company_intake.py --company "Candid" --re-audit --dry-run
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
