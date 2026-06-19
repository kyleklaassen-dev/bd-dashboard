#!/usr/bin/env python3
"""
consistency_checker.py — Tier 4 QA Agent (Phase E5 in the Weekend Sprint).

Orchestrator after the §3 split: wires the eight checks (consistency_checks_fields
+ consistency_checks_graph) over the dry-run-gated Supabase layer (consistency_base).
This stays the entrypoint weekend_sprint loads + calls run().

USAGE (standalone):
  python scripts/consistency_checker.py
  python scripts/consistency_checker.py --dry-run
  python scripts/consistency_checker.py --type stage_mismatch
"""
import argparse
import json
import os
import sys

# weekend_sprint loads this module via spec_from_file_location (Phase E5), which does
# NOT put scripts/ on sys.path — bootstrap it here so the sibling imports below resolve
# under both `python consistency_checker.py` and the dynamic _import_agent() load.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from consistency_base import log, RUN_ID, ensure_agent_disagreements_table, set_dry_run, is_dry_run
from consistency_checks_fields import (
    check_stage_vs_trials, check_brand_name_without_approval,
    check_company_id_originator, check_duplicate_entities,
)
from consistency_checks_graph import (
    check_deal_attribution, check_stage_history,
    check_relationship_symmetry, check_molecule_vs_drug_stage,
)

CHECKS = {
    "stage_mismatch":         check_stage_vs_trials,
    "brand_name":             check_brand_name_without_approval,
    "company_id_originator":  check_company_id_originator,
    "duplicate_entities":     check_duplicate_entities,
    "deal_attribution":       check_deal_attribution,
    "stage_history":          check_stage_history,
    "relationship_symmetry":  check_relationship_symmetry,
    "molecule_vs_drug":       check_molecule_vs_drug_stage,
}


def run(dry_run: bool = False, check_type: str = None) -> Dict:
    set_dry_run(dry_run)

    log("Consistency Checker — Tier 4 QA Agent")
    log(f"Run ID: {RUN_ID}")
    log(f"Dry-run: {is_dry_run()}")

    # Ensure table
    log("Ensuring agent_disagreements table exists", indent=1)
    if not is_dry_run():
        ensure_agent_disagreements_table()

    # Run checks
    checks_to_run = (
        {check_type: CHECKS[check_type]}
        if check_type and check_type in CHECKS
        else CHECKS
    )

    all_results = {}
    total_contradictions = 0

    for name, fn in checks_to_run.items():
        try:
            result = fn()
            all_results[name] = result
            # Sum contradictions
            for key in ["contradictions", "potential_violations", "drug_pairs",
                        "company_pairs", "gaps", "missing_symmetric", "mismatches"]:
                total_contradictions += result.get(key, 0)
        except Exception as e:
            log(f"  Check '{name}' raised exception: {e}", indent=2)
            all_results[name] = {"error": str(e)}

    log("=" * 60)
    log(f"Consistency Check Complete")
    log(f"  Total contradictions found: {total_contradictions}")
    for name, result in all_results.items():
        log(f"  {name}: {result}", indent=1)

    all_results["total_contradictions"] = total_contradictions
    return all_results


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Meridian Consistency Checker — find data contradictions"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Run without writing to Supabase")
    parser.add_argument("--type", default=None,
                        choices=list(CHECKS.keys()),
                        help="Run only one check type")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run, check_type=args.type)
    print(json.dumps(result, indent=2, default=str))
