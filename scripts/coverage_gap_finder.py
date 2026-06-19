#!/usr/bin/env python3
"""
coverage_gap_finder.py — finds coverage gaps and queues them (weekend_sprint Phase A6).

Orchestrator after the §3 split: wires the nine gap checks (coverage_gap_finder_a +
coverage_gap_finder_b) over the dry-run-gated Supabase layer (coverage_gap_base).
Stays the entrypoint weekend_sprint loads + calls run().

USAGE (standalone):
  python scripts/coverage_gap_finder.py
  python scripts/coverage_gap_finder.py --dry-run
  python scripts/coverage_gap_finder.py --type low_coverage
"""
import argparse
import json
import os
import sys

# weekend_sprint loads this via spec_from_file_location (Phase A6), which does NOT put
# scripts/ on sys.path — bootstrap so the sibling imports below resolve in both paths.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from coverage_gap_base import log, RUN_ID, table_exists, set_dry_run, is_dry_run
from coverage_gap_finder_a import (
    gap_low_coverage_score, gap_missing_molecule_intelligence, gap_missing_drug_indications,
    gap_missing_catalyst_entries, gap_deals_without_partnerships,
)
from coverage_gap_finder_b import (
    gap_phantom_companies, gap_unverified_relationships, gap_null_bd_angle, gap_null_risk_summary,
)
GAP_CHECKS = {
    "low_coverage":          gap_low_coverage_score,
    "molecule_intelligence": gap_missing_molecule_intelligence,
    "drug_indications":      gap_missing_drug_indications,
    "catalyst_calendar":     gap_missing_catalyst_entries,
    "deal_partnerships":     gap_deals_without_partnerships,
    "phantom_companies":     gap_phantom_companies,
    "unverified_rels":       gap_unverified_relationships,
    "bd_angle":              gap_null_bd_angle,
    "risk_summary":          gap_null_risk_summary,
}


def run(dry_run: bool = False, gap_type: str = None) -> Dict:
    set_dry_run(dry_run)

    log("Coverage Gap Finder — Tier 4 QA Agent")
    log(f"Run ID: {RUN_ID}")
    log(f"Dry-run: {is_dry_run()}")

    # Verify research_queue table exists
    if not table_exists("research_queue"):
        log("  WARNING: research_queue table not found — gap items will be logged only", indent=1)

    checks_to_run = (
        {gap_type: GAP_CHECKS[gap_type]}
        if gap_type and gap_type in GAP_CHECKS
        else GAP_CHECKS
    )

    all_results: Dict[str, Dict] = {}
    summary: Dict[str, int] = {}

    for name, fn in checks_to_run.items():
        try:
            result = fn()
            all_results[name] = result
            summary[name] = result.get("queued", result.get("found", 0))
        except Exception as e:
            log(f"  Gap check '{name}' raised exception: {e}", indent=2)
            all_results[name] = {"error": str(e)}
            summary[name] = 0

    total_queued = sum(summary.values())

    log("=" * 60)
    log(f"Coverage Gap Finder Complete")
    log(f"  Total items queued: {total_queued}")
    for gap, count in summary.items():
        log(f"  {gap}: {count}", indent=1)

    all_results["summary"] = summary
    all_results["total_queued"] = total_queued
    return all_results


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Meridian Coverage Gap Finder — find missing data"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Run without writing to Supabase")
    parser.add_argument("--gap", default=None,
                        choices=list(GAP_CHECKS.keys()),
                        help="Run only one gap check type")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run, gap_type=args.gap)
    print(json.dumps(result, indent=2, default=str))
