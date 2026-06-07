#!/usr/bin/env python3
"""
Evidence source backfill pipeline — entrypoint.

This is the only file the GitHub Actions workflow calls. It owns:
  - Argument parsing (--areas, --dry-run, --limit, --max-pubs)
  - Phase 1: drug evidence loop (areas sequential, failures isolated)
  - Phase 2: patient evidence pass (runs after all areas finish)
  - Summary output and exit code

Run:
  python scripts/evidence/backfill_sources.py --areas "tl1a il23p19" --dry-run
  python scripts/evidence/backfill_sources.py --areas "tl1a" --apply
"""
import argparse
import sys

from .config import DEFAULT_AREAS
from . import drug_evidence, patient_evidence


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Evidence source backfill pipeline")
    ap.add_argument(
        "--areas",
        default=" ".join(DEFAULT_AREAS),
        help="Space-separated drug areas (default: core immunology set)",
    )
    ap.add_argument("--dry-run", action="store_true",
                    help="Fetch but do not write to Supabase")
    ap.add_argument("--limit", type=int, default=0,
                    help="Limit drugs per area (0 = all, useful for testing)")
    ap.add_argument("--max-pubs", type=int, default=3,
                    help="Max Europe PMC publications per drug (default: 3)")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    areas = [a.strip() for a in args.areas.split() if a.strip()]
    dry_run = args.dry_run
    mode = "[dry-run]" if dry_run else "[apply]"

    print(f"=== Evidence source backfill {mode} ===")
    print(f"Areas: {' '.join(areas)}")
    print()

    # ── Phase 1: Drug evidence ────────────────────────────────────────────────
    print("--- Phase 1: Drug evidence (CT.gov + Europe PMC) ---")
    area_errors: list[str] = []
    total_drug_sources = 0

    for area in areas:
        print(f">> area: {area}")
        try:
            result = drug_evidence.collect_for_area(
                area,
                limit=args.limit,
                max_pubs=args.max_pubs,
                dry_run=dry_run,
            )
            if not result.ok:
                raise RuntimeError(result.error)

            for dr in result.drug_results:
                if dr.total > 0:
                    print(
                        f"  {dr.drug_id}: +{dr.total} sources "
                        f"({dr.ctgov_added} ct.gov, {dr.pubs_added} pubs)"
                    )

            total_drug_sources += result.total_sources
            print(
                f"  area {area}: {result.drugs_with_new_sources} drugs "
                f"gained sources (+{result.total_sources} total)"
            )

        except Exception as e:
            msg = f"area {area} failed: {e}"
            print(f"  ERROR: {msg}", file=sys.stderr)
            area_errors.append(msg)
            # Continue — one area failure must not stop the rest

    print()

    # ── Phase 2: Patient evidence ─────────────────────────────────────────────
    print("--- Phase 2: Patient / epidemiology evidence (Europe PMC) ---")
    patient_error = ""
    try:
        result = patient_evidence.collect_all(dry_run=dry_run)
        if not result.ok:
            raise RuntimeError(result.error)

        for rr in result.row_results:
            if rr.urls_added > 0:
                print(f"  {rr.indication_name}: +{rr.urls_added} source(s)")

        print(f"  sourced: {result.sourced} indication rows")
        if result.skipped_aggregates:
            print(
                f"  skipped {len(result.skipped_aggregates)} analytical aggregates "
                f"(not single diseases): {', '.join(result.skipped_aggregates)}"
            )
        if result.no_hits_names:
            print(f"  no EPMC hit for: {', '.join(result.no_hits_names)}")

    except Exception as e:
        patient_error = str(e)
        print(f"  ERROR: patient evidence failed: {patient_error}", file=sys.stderr)

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=== Summary ===")
    verb = "would add" if dry_run else "added"
    print(f"Drug sources: {verb} {total_drug_sources} across {len(areas)} area(s)")
    if area_errors:
        print(f"Area errors ({len(area_errors)}): {'; '.join(area_errors)}")
    if patient_error:
        print(f"Patient evidence error: {patient_error}")

    failed = bool(area_errors) or bool(patient_error)
    print(f"Status: {'PARTIAL FAILURE' if failed else 'OK'}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
