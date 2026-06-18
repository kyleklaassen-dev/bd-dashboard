#!/usr/bin/env python3
"""
acquisition_scorer.py
---------------------
Phase 3 Predictive Intelligence Layer for the Meridian BD Platform.

Computes an acquisition probability score (0-100) and BD priority rating
for every tracked company, answering: "Should Ailux be in active conversations
with this company RIGHT NOW?"

Five scoring dimensions (20 pts each):
  D1 Strategic Overlap   — how directly does their pipeline compete with Ailux?
  D2 BD Timing Urgency   — upcoming catalysts creating deal pressure
  D3 Platform Value      — engineering / modality capabilities Ailux could acquire
  D4 Deal Feasibility    — size + structure that makes a deal achievable
  D5 Ailux Window        — differentiation + constraint logic (AbbVie rule etc.)

BD Priority Ratings:
  85-100 → CALL NOW
  70-84  → PRIORITY
  55-69  → WATCH
  40-54  → MONITOR
  <40    → HOLD

Hard constraints:
  - AbbVie: capped at WATCH until ABBV-701 Phase 1 readout (Oct 2026)
  - Any company with status='acquired': forced to HOLD
  - Ailux itself: excluded from scoring

Run:
  python3 src/meridian/scoring/acquisition_scorer.py [--dry-run] [--top N]

Outputs:
  - Console: top 20 ranked companies with full dimension breakdown
  - Supabase: upserts to company_strategic_views (view_type='acquisition_target')
  - Local JSON: outputs/acquisition_probability_scores.json
  - GitHub: commits this script to kyleklaassen-dev/bd-dashboard
"""

import json
import os
import sys
import argparse
import base64
import urllib.request
import urllib.error
from datetime import datetime, date
from collections import defaultdict

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# ── §3 SPLIT — base + data/scoring/write now in meridian.scoring.acquisition.* ──
from meridian.scoring.acquisition.common import (
    RUN_ID, TODAY_STR, get,
)
from meridian.scoring.acquisition.data import fetch_all_data, build_indexes
from meridian.scoring.acquisition.scoring import score_company
from meridian.scoring.acquisition.write import write_to_supabase, write_json, commit_to_github


def print_report(results, top_n=20):
    clean = [r for r in results if r is not None]
    ranked = sorted(clean, key=lambda r: r["total_score"], reverse=True)

    call_now = [r for r in ranked if r["bd_priority"] == "CALL NOW"]
    priority = [r for r in ranked if r["bd_priority"] == "PRIORITY"]
    watch = [r for r in ranked if r["bd_priority"] == "WATCH"]
    monitor = [r for r in ranked if r["bd_priority"] == "MONITOR"]
    hold = [r for r in ranked if r["bd_priority"] == "HOLD"]

    W = 120
    print("\n" + "=" * W)
    print("MERIDIAN BD PLATFORM — ACQUISITION PROBABILITY SCORES")
    print(f"Phase 3 Predictive Intelligence Layer  |  Run: {RUN_ID}  |  Date: {TODAY_STR}")
    print("=" * W)

    print(f"\n{'RATING':<12} {'COMPANY':<32} {'TOTAL':<7} {'D1':<5} {'D2':<5} {'D3':<5} {'D4':<5} {'D5':<5}")
    print("-" * W)

    for i, r in enumerate(ranked[:top_n], 1):
        constraint = " [CONSTRAINED]" if r.get("constraint_note") else ""
        print(
            f"[{r['bd_priority']:<9}] "
            f"{r['company_name']:<32} "
            f"{r['total_score']:<7} "
            f"{r['dim1_overlap']:<5} "
            f"{r['dim2_timing']:<5} "
            f"{r['dim3_platform']:<5} "
            f"{r['dim4_feasibility']:<5} "
            f"{r['dim5_window']:<5}"
            f"{constraint}"
        )

    # CALL NOW detail section
    if call_now:
        print("\n" + "=" * W)
        print(f"CALL NOW COMPANIES ({len(call_now)} companies) — detailed reasoning")
        print("=" * W)
        for r in call_now:
            print(f"\n  {r['company_name'].upper()} (score: {r['total_score']}/100)")
            print(f"    D1 Overlap    [{r['dim1_overlap']:>2}/20]: {r['dim1_reason']}")
            print(f"    D2 Timing     [{r['dim2_timing']:>2}/20]: {r['dim2_reason']}")
            print(f"    D3 Platform   [{r['dim3_platform']:>2}/20]: {r['dim3_reason']}")
            print(f"    D4 Feasibility[{r['dim4_feasibility']:>2}/20]: {r['dim4_reason']}")
            print(f"    D5 Window     [{r['dim5_window']:>2}/20]: {r['dim5_reason']}")
            if r.get("constraint_note"):
                print(f"    CONSTRAINT: {r['constraint_note']}")
    else:
        print("\n  No companies reached CALL NOW threshold.")

    # PRIORITY detail section
    if priority:
        print("\n" + "=" * W)
        print(f"PRIORITY COMPANIES ({len(priority)} companies)")
        print("=" * W)
        for r in priority:
            print(f"  {r['company_name']:<32} score={r['total_score']}  "
                  f"D1={r['dim1_overlap']} D2={r['dim2_timing']} "
                  f"D3={r['dim3_platform']} D4={r['dim4_feasibility']} D5={r['dim5_window']}")

    # Constraints applied
    constrained = [r for r in clean if r.get("constraint_note")]
    if constrained:
        print("\n" + "=" * W)
        print(f"TIMING CONSTRAINTS APPLIED ({len(constrained)} companies)")
        print("=" * W)
        for r in constrained:
            print(f"  {r['company_name']}: {r['constraint_note'][:120]}")

    # Distribution
    print("\n" + "=" * W)
    print("BD PRIORITY DISTRIBUTION")
    print("=" * W)
    dist = [
        ("CALL NOW", call_now),
        ("PRIORITY", priority),
        ("WATCH", watch),
        ("MONITOR", monitor),
        ("HOLD", hold),
    ]
    for label, group in dist:
        bar = "#" * len(group)
        names = ", ".join(r["company_name"] for r in group[:5])
        if len(group) > 5:
            names += f", +{len(group)-5} more"
        print(f"  {label:<10} {bar:<30} ({len(group):>3}) — {names}")

    print(f"\nTotal scored: {len(clean)}  |  Excluded (Ailux): {len([r for r in results if r is None])}")
    print(f"Run ID: {RUN_ID}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Meridian Phase 3: Acquisition Probability Scorer"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute scores but do not write to Supabase or GitHub")
    parser.add_argument("--top", type=int, default=20,
                        help="How many companies to show in the report (default: 20)")
    args = parser.parse_args()

    data = fetch_all_data()
    idx = build_indexes(data)

    print("[3/6] Computing acquisition probability scores...")
    results = []
    for company in data["companies"]:
        result = score_company(company, idx)
        results.append(result)

    scored = [r for r in results if r is not None]
    print(f"  Scored {len(scored)} companies ({len(results)-len(scored)} excluded)")

    if not args.dry_run:
        write_to_supabase(results, dry_run=False)
    else:
        print("[4/6] [DRY RUN] Skipping Supabase write")

    write_json(results)

    if not args.dry_run:
        commit_to_github()
    else:
        print("[6/6] [DRY RUN] Skipping GitHub commit")

    print_report(results, top_n=args.top)


if __name__ == "__main__":
    main()
