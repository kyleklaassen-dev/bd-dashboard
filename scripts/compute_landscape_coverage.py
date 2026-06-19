#!/usr/bin/env python3
"""
compute_landscape_coverage.py
Derives the landscape_dependency_score and all sub-scores for every row
in competitive_landscapes that has expected_drug_count set.

Formula:
  landscape_dependency_score (0–100) =
      0.35 × drug_coverage_score         (drug% of expected)
    + 0.25 × relationship_coverage_score (edges captured / expected)
    + 0.20 × catalyst_coverage_score     (catalyst% of expected)
    + 0.15 × source_validation_score     (sourced rows / total)
    − 0.05 × staleness_penalty           (stale rows / total)

  Each sub-score is 0.0–1.0 before weighting.
  Final score is ×100 (stored as NUMERIC(5,2)).

Run:
  python3 scripts/compute_landscape_coverage.py [--dry-run] [--landscape-id N]

Options:
  --dry-run        Print scores without writing to DB
  --landscape-id N Compute only for landscape id N (default: all)
"""

import json, os, sys, urllib.request, urllib.error, urllib.parse, datetime, math

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SB_URL   = "https://tghntyofptvfhmtchwcv.supabase.co"
DRY_RUN  = "--dry-run" in sys.argv
NOW      = datetime.datetime.utcnow()

# Optional: --landscape-id N to restrict
FILTER_ID = None
for i, arg in enumerate(sys.argv):
    if arg == "--landscape-id" and i + 1 < len(sys.argv):
        FILTER_ID = int(sys.argv[i + 1])

# ── §3 split: IO/creds → landscape_coverage_base, metrics → landscape_coverage_metrics ──
from landscape_coverage_base import get, patch, insert, section
from landscape_coverage_metrics import (
    fetch_landscape_drug_ids, compute_drug_coverage, compute_relationship_coverage,
    compute_catalyst_coverage, compute_source_validation, compute_staleness_penalty,
)


# ─────────────────────────────────────────────────────────────────
# Main compute loop
# ─────────────────────────────────────────────────────────────────

section("FETCHING LANDSCAPES")

params = {"select": "id,disease_name,target_pair,expected_drug_count,expected_relationship_count,expected_catalyst_count,landscape_dependency_score"}
if FILTER_ID:
    params["id"] = f"eq.{FILTER_ID}"
else:
    params["expected_drug_count"] = "not.is.null"

landscapes = get("competitive_landscapes", params)
print(f"  Found {len(landscapes)} landscape(s) to compute")

if not landscapes:
    print("  No landscapes with expected_drug_count set. Run seed_ted_expected_competitors.py first.")
    sys.exit(0)

results = []

for landscape in landscapes:
    lid   = landscape["id"]
    lname = f"{landscape['disease_name']} × {landscape['target_pair']}"

    section(f"COMPUTING: {lname} (id={lid})")

    # Resolve area_ids for this landscape
    # For TED × IGF-1R_TSHR → areas are igf1r + ted
    # For future landscapes, could derive from target_pair
    # v1: hardcode TED → igf1r + ted; generalize later
    AREA_IDS = ["igf1r", "ted"]

    # 1. Expected competitor rows
    lec_rows = fetch_landscape_drug_ids(lid)
    confirmed_drug_ids = {r["drug_id"] for r in lec_rows if r["confirmed"] and r["drug_id"]}
    print(f"  Expected competitor rows: {len(lec_rows)}")
    print(f"  Confirmed drug_ids:       {confirmed_drug_ids}")

    # 2. Drug coverage
    d_score, d_detail = compute_drug_coverage(lec_rows, landscape["expected_drug_count"])
    print(f"\n  [1] Drug coverage:")
    print(f"      confirmed: {d_detail.get('confirmed', [])}")
    print(f"      missing:   {d_detail.get('missing', [])}")
    print(f"      tier3_pending: {d_detail.get('tier3_pending', [])}")
    print(f"      score = {d_score:.4f}")

    # 3. Relationship coverage
    r_score, r_detail = compute_relationship_coverage(lid, landscape["expected_relationship_count"])
    print(f"\n  [2] Relationship coverage:")
    for e in r_detail.get("edges", []):
        print(f"      {e}")
    print(f"      captured={r_detail.get('captured')}/{r_detail.get('expected')}  score={r_score:.4f}")

    # 4. Catalyst coverage
    c_score, c_detail = compute_catalyst_coverage(AREA_IDS, landscape["expected_catalyst_count"])
    print(f"\n  [3] Catalyst coverage:")
    print(f"      captured={c_detail.get('captured')}/{c_detail.get('expected')}  score={c_score:.4f}")

    # 5. Source validation
    s_score, s_detail = compute_source_validation(confirmed_drug_ids)
    print(f"\n  [4] Source validation:")
    print(f"      sourced={s_detail.get('sourced')}/{s_detail.get('total')}  score={s_score:.4f}")
    if s_detail.get("unsourced_drugs"):
        print(f"      unsourced drugs: {s_detail['unsourced_drugs']}")

    # 6. Staleness penalty
    p_score, p_detail = compute_staleness_penalty(lid, confirmed_drug_ids)
    print(f"\n  [5] Staleness penalty:")
    print(f"      stale={p_detail.get('stale')}/{p_detail.get('total')}  penalty={p_score:.4f}")
    for item in p_detail.get("stale_items", []):
        print(f"      ⚠️  {item}")

    # ── Apply formula ──────────────────────────────────────────
    raw_score = (
          0.35 * d_score
        + 0.25 * r_score
        + 0.20 * c_score
        + 0.15 * s_score
        - 0.05 * p_score
    )
    final_score = round(min(max(raw_score, 0.0), 1.0) * 100, 2)

    breakdown = {
        "drug_coverage":         {"score": round(d_score, 4), "weight": 0.35, "contribution": round(0.35 * d_score, 4), "detail": d_detail},
        "relationship_coverage": {"score": round(r_score, 4), "weight": 0.25, "contribution": round(0.25 * r_score, 4), "detail": r_detail},
        "catalyst_coverage":     {"score": round(c_score, 4), "weight": 0.20, "contribution": round(0.20 * c_score, 4), "detail": c_detail},
        "source_validation":     {"score": round(s_score, 4), "weight": 0.15, "contribution": round(0.15 * s_score, 4), "detail": s_detail},
        "staleness_penalty":     {"score": round(p_score, 4), "weight": -0.05, "contribution": round(-0.05 * p_score, 4), "detail": p_detail},
        "formula": "0.35×drug + 0.25×relationship + 0.20×catalyst + 0.15×source − 0.05×staleness",
    }

    print(f"\n  {'─'*50}")
    print(f"  FORMULA RESULT:")
    print(f"    0.35 × {d_score:.4f} = {0.35*d_score:.4f}  (drug coverage)")
    print(f"    0.25 × {r_score:.4f} = {0.25*r_score:.4f}  (relationship coverage)")
    print(f"    0.20 × {c_score:.4f} = {0.20*c_score:.4f}  (catalyst coverage)")
    print(f"    0.15 × {s_score:.4f} = {0.15*s_score:.4f}  (source validation)")
    print(f"   −0.05 × {p_score:.4f} = {-0.05*p_score:.4f}  (staleness penalty)")
    print(f"    {'─'*30}")
    print(f"    raw score:        {raw_score:.4f}")
    print(f"    FINAL SCORE:      {final_score:.2f} / 100")
    prior_score = landscape.get("landscape_dependency_score")
    delta = round(final_score - float(prior_score), 2) if prior_score else None
    print(f"    prior score:      {prior_score or 'not set (first run)'}")
    if delta is not None:
        sign = "+" if delta >= 0 else ""
        print(f"    delta:            {sign}{delta}")

    results.append({
        "landscape_id":             lid,
        "landscape_name":           lname,
        "final_score":              final_score,
        "prior_score":              float(prior_score) if prior_score else None,
        "delta":                    delta,
        "drug_coverage_score":      round(d_score, 4),
        "relationship_coverage_score": round(r_score, 4),
        "catalyst_coverage_score":  round(c_score, 4),
        "source_validation_score":  round(s_score, 4),
        "staleness_penalty":        round(p_score, 4),
        "breakdown":                breakdown,
        # raw counts for log
        "captured_drug_count":      sum(1 for r in lec_rows if r["confirmed"]),
        "expected_drug_count":      landscape["expected_drug_count"],
        "captured_relationship_count": r_detail.get("captured", 0),
        "expected_relationship_count": landscape["expected_relationship_count"],
        "captured_catalyst_count":  c_detail.get("captured", 0),
        "expected_catalyst_count":  landscape["expected_catalyst_count"],
        "sourced_row_count":        s_detail.get("sourced", 0),
        "total_row_count":          s_detail.get("total", 0),
        "stale_row_count":          p_detail.get("stale", 0),
    })


# ─────────────────────────────────────────────────────────────────
# Write results to DB
# ─────────────────────────────────────────────────────────────────

section("WRITING RESULTS TO DB" if not DRY_RUN else "DRY RUN — RESULTS NOT WRITTEN")

for r in results:
    lid = r["landscape_id"]

    if DRY_RUN:
        print(f"  [DRY RUN] Would write {r['final_score']}/100 to landscape id={lid}")
        continue

    # Update competitive_landscapes
    ok = patch(
        "competitive_landscapes",
        {"id": f"eq.{lid}"},
        {
            "drug_coverage_score":          r["drug_coverage_score"],
            "relationship_coverage_score":  r["relationship_coverage_score"],
            "catalyst_coverage_score":      r["catalyst_coverage_score"],
            "source_validation_score":      r["source_validation_score"],
            "staleness_penalty":            r["staleness_penalty"],
            "landscape_dependency_score":   r["final_score"],
            "coverage_breakdown":           json.dumps(r["breakdown"]),
            "coverage_computed_at":         NOW.isoformat(),
        },
    )
    if ok:
        print(f"  ✅  landscape id={lid}: landscape_dependency_score={r['final_score']}")
    else:
        print(f"  ❌  Failed to write landscape id={lid}")
        continue

    # Insert into coverage_computation_log
    log_row = {
        "landscape_id":                 lid,
        "computed_at":                  NOW.isoformat(),
        "captured_drug_count":          r["captured_drug_count"],
        "expected_drug_count":          r["expected_drug_count"],
        "captured_relationship_count":  r["captured_relationship_count"],
        "expected_relationship_count":  r["expected_relationship_count"],
        "captured_catalyst_count":      r["captured_catalyst_count"],
        "expected_catalyst_count":      r["expected_catalyst_count"],
        "sourced_row_count":            r["sourced_row_count"],
        "total_row_count":              r["total_row_count"],
        "stale_row_count":              r["stale_row_count"],
        "drug_coverage_score":          r["drug_coverage_score"],
        "relationship_coverage_score":  r["relationship_coverage_score"],
        "catalyst_coverage_score":      r["catalyst_coverage_score"],
        "source_validation_score":      r["source_validation_score"],
        "staleness_penalty":            r["staleness_penalty"],
        "landscape_dependency_score":   r["final_score"],
        "coverage_breakdown":           json.dumps(r["breakdown"]),
        "prior_score":                  r["prior_score"],
        "score_delta":                  r["delta"],
        "notes":                        "v32 initial compute run",
    }
    n = insert("coverage_computation_log", [log_row])
    if n:
        print(f"  ✅  coverage_computation_log: 1 row written")


# ─────────────────────────────────────────────────────────────────
# Final summary
# ─────────────────────────────────────────────────────────────────

section("SUMMARY")
print(f"  {'Landscape':<40} {'Score':>7}  {'vs self-reported':>16}  {'Delta':>7}")
print(f"  {'─'*40} {'─'*7}  {'─'*16}  {'─'*7}")
for r in results:
    delta_str = f"{r['delta']:+.2f}" if r["delta"] is not None else "  n/a"
    prior_str = f"was {r['prior_score']:.1f}" if r["prior_score"] else "  (first run)"
    print(f"  {r['landscape_name']:<40} {r['final_score']:>6.2f}  {prior_str:>16}  {delta_str:>7}")

if DRY_RUN:
    print(f"\n  [DRY RUN] No data written. Remove --dry-run to apply.")
else:
    print(f"\n  ✅  Done. landscape_dependency_score replaces landscape_completeness_score.")
    print(f"       Run again after any seed/enrichment to see score movement.")

print(f"\n{'═'*60}")
