#!/usr/bin/env python3
"""
Abstract fetcher pipeline — entrypoint.

This is the only file the GitHub Actions workflow calls. It owns:
  - Argument parsing (--drug, --preprints, --dry-run, --verbose)
  - Default mode: drug sweep then preprint monitor (what scheduled runs need)
  - --drug name: single drug only
  - --preprints: preprint monitor only
  - Summary output and exit code

Run:
  python -m scripts.abstracts.fetch_abstracts
  python -m scripts.abstracts.fetch_abstracts --drug tulisokibart
  python -m scripts.abstracts.fetch_abstracts --preprints
  python -m scripts.abstracts.fetch_abstracts --dry-run
"""
import argparse
import sys

from . import drug_abstracts, preprint_monitor
from .repositories import drug_repository as drug_repo


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Meridian abstract fetcher pipeline")
    ap.add_argument("--drug",      help="Fetch abstracts for a specific drug name only")
    ap.add_argument("--preprints", action="store_true",
                    help="Run preprint monitor only")
    ap.add_argument("--dry-run",   action="store_true",
                    help="Fetch but do not write to Supabase")
    ap.add_argument("--verbose",   action="store_true")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    dry_run = args.dry_run
    mode = "[dry-run]" if dry_run else "[apply]"

    print(f"=== Meridian Abstract Fetcher {mode} ===")

    errors: list[str] = []

    # ── Preprints-only mode ───────────────────────────────────────────────────
    if args.preprints:
        print("\n--- Preprint monitor ---")
        result = preprint_monitor.collect(dry_run=dry_run)
        if not result.ok:
            print(f"  ERROR: {result.error}", file=sys.stderr)
            errors.append(result.error)
        _print_summary(total_drug=0, total_preprints=result.written, dry_run=dry_run)
        return 1 if errors else 0

    # ── Single-drug mode ──────────────────────────────────────────────────────
    if args.drug:
        print(f"\n--- Single drug: {args.drug} ---")
        drugs = drug_repo.find_by_name(args.drug)
        if not drugs:
            print(f"No drug found matching '{args.drug}'")
            return 1
        total = 0
        for drug in drugs:
            dr = drug_abstracts.collect_for_drug(drug, dry_run=dry_run, verbose=args.verbose)
            verb = "[dry-run] would write" if dry_run else "wrote"
            print(f"  {drug.get('name', '')}: {verb} {dr.written} documents")
            total += dr.written
        _print_summary(total_drug=total, total_preprints=0, dry_run=dry_run)
        return 0

    # ── Default mode: drug sweep + preprint monitor ───────────────────────────
    print("\n--- Phase 1: Drug abstract sweep (all Phase 2+ drugs) ---")
    sweep = drug_abstracts.collect_all(dry_run=dry_run, verbose=args.verbose)
    if not sweep.ok:
        print(f"  ERROR in drug sweep: {sweep.error}", file=sys.stderr)
        errors.append(sweep.error)

    if args.verbose and sweep.drug_results:
        print("\nTop drugs by abstract count:")
        top = sorted(sweep.drug_results, key=lambda r: r.written, reverse=True)[:10]
        for dr in top:
            if dr.written > 0:
                print(f"  {dr.written:3d}  {dr.drug_name}")

    print("\n--- Phase 2: Preprint monitor ---")
    preprints = preprint_monitor.collect(dry_run=dry_run)
    if not preprints.ok:
        print(f"  ERROR in preprint monitor: {preprints.error}", file=sys.stderr)
        errors.append(preprints.error)

    _print_summary(
        total_drug=sweep.total_written,
        total_preprints=preprints.written,
        dry_run=dry_run,
    )
    return 1 if errors else 0


def _print_summary(total_drug: int, total_preprints: int, dry_run: bool) -> None:
    verb = "would write" if dry_run else "wrote"
    print(f"\n=== Summary: {verb} {total_drug} drug abstracts, {total_preprints} preprints ===")


if __name__ == "__main__":
    sys.exit(main())
