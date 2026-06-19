#!/usr/bin/env python3
"""
compute_coverage.py — Meridian Coverage Framework
Computes per-company, per-area coverage scores across 9 diagnostic dimensions.

Usage:
  python3 src/meridian/scoring/compute_coverage.py
  python3 src/meridian/scoring/compute_coverage.py --dry-run
  python3 src/meridian/scoring/compute_coverage.py --company ucb
  python3 src/meridian/scoring/compute_coverage.py --area tl1a

Output:
  - Writes coverage_scores rows to Supabase (upsert by entity_id/area_id)
  - Prints CLI summary: platform average, lowest 10, recommended actions

Coverage dimensions:
  1. target_mapping_score     — % area-linked drugs with drug_targets rows
  2. ownership_coverage_score — % licensed-in drugs with ownership_edges
  3. source_coverage_score    — % drug_area_scores rows with source_url
  4. confidence_coverage_score— % drug_area_scores with non-null confidence_level
  5. enrichment_recency_score — recency of company_profiles.last_enriched_at
  6. deal_linkage_score       — % acquisition/license edges with deal_id
  7. molecule_intelligence_score — % drugs with molecule_intelligence rows
  8. catalyst_coverage_score  — % clinical-stage drugs with ≥1 future catalyst
  9. profile_completeness_score — % expected company_profiles fields present

Each score is 0–100. Overall = weighted average.
"""

import os
import sys
import json
import time
import uuid
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from collections import defaultdict

SCORE_VERSION = "1.2"  # v1.2: source_coverage denominator = confirmed+supported only (not inferred/null)

SB_URL = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SB_KEY:
    key_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".supabase_service_key")
    if os.path.exists(key_file):
        with open(key_file) as f:
            SB_KEY = f.read().strip()

if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_KEY not set")
    sys.exit(1)


def sb_get(path, limit=2000):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Range": f"0-{limit - 1}"
        }
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def sb_upsert(table, rows, on_conflict=None):
    """Upsert rows into table. on_conflict specifies the conflict target columns."""
    if not rows:
        return []
    url = f"{SB_URL}/rest/v1/{table}"
    if on_conflict:
        url += f"?on_conflict={on_conflict}"
    payload = json.dumps(rows).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation"
        }
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  Upsert error HTTP {e.code}: {err[:200]}")
        return []


# ── Data loading ─────────────────────────────────────────────────────────────

def load_data():
    print("Loading data from Supabase...")

    company_areas = sb_get("company_areas?select=company_id,area_id&order=company_id,area_id")
    print(f"  company_areas: {len(company_areas)}")

    drugs = sb_get("drugs?select=id,company_id,stage,partner_company,catalog_category&order=id")
    print(f"  drugs: {len(drugs)}")

    drug_areas = sb_get("drug_areas?select=drug_id,area_id")
    print(f"  drug_areas: {len(drug_areas)}")

    drug_targets = sb_get("drug_targets?role=eq.primary&select=drug_id,target_id")
    print(f"  drug_targets (primary): {len(drug_targets)}")

    drug_area_scores = sb_get("drug_area_scores?select=drug_id,area_id,confidence_level,source_url,overlap")
    print(f"  drug_area_scores: {len(drug_area_scores)}")

    ownership_edges = sb_get("ownership_edges?select=subject_id,object_id,predicate,deal_id,status")
    print(f"  ownership_edges: {len(ownership_edges)}")

    molecule_intel = sb_get("molecule_intelligence?select=drug_id,canonical_drug_id,last_enriched_at")
    print(f"  molecule_intelligence: {len(molecule_intel)}")

    catalysts = sb_get(
        "catalysts?resolved=eq.false"
        "&select=drug_id,area_id,catalyst_date"
        "&order=catalyst_date"
    )
    print(f"  catalysts (unresolved): {len(catalysts)}")

    company_profiles = sb_get(
        "company_profiles?select=company_id,area_id,platform_summary,bd_summary,"
        "key_risk,risk_summary,bd_angle,vs_ailux,last_enriched_at,completeness_score"
    )
    print(f"  company_profiles: {len(company_profiles)}")

    return {
        "company_areas": company_areas,
        "drugs": {d["id"]: d for d in drugs},
        "drug_areas": drug_areas,
        "drug_targets": drug_targets,
        "drug_area_scores": drug_area_scores,
        "ownership_edges": ownership_edges,
        "molecule_intel": molecule_intel,
        "catalysts": catalysts,
        "company_profiles": company_profiles,
    }


def build_indexes(data):
    """Pre-build lookup maps to avoid O(n²) loops."""
    idx = {}

    # drug_id → {area_ids}
    idx["drug_to_areas"] = defaultdict(set)
    for row in data["drug_areas"]:
        idx["drug_to_areas"][row["drug_id"]].add(row["area_id"])

    # (area_id) → {drug_ids}
    idx["area_to_drugs"] = defaultdict(set)
    for row in data["drug_areas"]:
        idx["area_to_drugs"][row["area_id"]].add(row["drug_id"])

    # company_id → {drug_ids} (from drugs.company_id)
    idx["company_to_drugs"] = defaultdict(set)
    for drug_id, drug in data["drugs"].items():
        if drug.get("company_id"):
            idx["company_to_drugs"][drug["company_id"]].add(drug_id)

    # drug_ids with primary targets
    idx["drugs_with_targets"] = {row["drug_id"] for row in data["drug_targets"]}

    # drug_id → ownership_edge predicates present
    idx["drug_ownership_predicates"] = defaultdict(set)
    for edge in data["ownership_edges"]:
        idx["drug_ownership_predicates"][edge["subject_id"]].add(edge["predicate"])

    # company_id → ownership_edges involving acquisitions/licenses
    idx["company_acquisition_edges"] = defaultdict(list)
    for edge in data["ownership_edges"]:
        if edge["predicate"] in ("ACQUIRED", "LICENSED_IN", "LICENSED_FROM", "ORIGINATED_BY"):
            for company_key in (edge["subject_id"], edge["object_id"]):
                idx["company_acquisition_edges"][company_key].append(edge)

    # (drug_id, area_id) → drug_area_scores row
    idx["das_by_drug_area"] = {}
    for row in data["drug_area_scores"]:
        key = (row["drug_id"], row["area_id"])
        idx["das_by_drug_area"][key] = row

    # drug_id → has molecule_intelligence
    idx["drugs_with_mi"] = set()
    for row in data["molecule_intel"]:
        for fld in ("drug_id", "canonical_drug_id"):
            if row.get(fld):
                idx["drugs_with_mi"].add(row[fld])

    # (drug_id, area_id) → has future catalyst
    idx["drugs_with_catalyst"] = set()
    now = datetime.now(timezone.utc).date()
    for row in data["catalysts"]:
        if row.get("drug_id") and row.get("area_id"):
            idx["drugs_with_catalyst"].add((row["drug_id"], row["area_id"]))

    # (company_id, area_id) → company_profiles row
    idx["profiles"] = {}
    for row in data["company_profiles"]:
        key = (row["company_id"], row.get("area_id"))
        idx["profiles"][key] = row

    return idx


# ── Dimension scorers ─────────────────────────────────────────────────────────

def get_area_drugs_for_company(company_id, area_id, idx):
    """Return set of drug_ids that belong to company_id AND are in area_id."""
    company_drugs = idx["company_to_drugs"].get(company_id, set())
    area_drugs = idx["area_to_drugs"].get(area_id, set())
    return company_drugs & area_drugs



# ── Scoring constants + sub-score functions → coverage_scoring.py (§3 split: pure) ──
from meridian.scoring.coverage_scoring import (
    STALE_DAYS, VERY_STALE_DAYS, CLINICAL_STAGES, ACTIVE_STAGES, WEIGHTS,
    score_target_mapping, score_ownership_coverage, score_source_coverage,
    score_confidence_coverage, score_enrichment_recency, score_deal_linkage,
    score_molecule_intelligence, score_catalyst_coverage, score_profile_completeness,
    compute_overall, build_recommendations,
)

# ── Main compute loop ─────────────────────────────────────────────────────────

def compute_all(data, idx, filter_company=None, filter_area=None, dry_run=False):
    company_areas = data["company_areas"]
    if filter_company:
        company_areas = [r for r in company_areas if r["company_id"] == filter_company]
    if filter_area:
        company_areas = [r for r in company_areas if r["area_id"] == filter_area]

    print(f"\nComputing coverage for {len(company_areas)} company/area pairs...")

    results = []
    for ca in company_areas:
        company_id = ca["company_id"]
        area_id = ca["area_id"]
        entity_id = f"{company_id}:{area_id}"

        drugs = get_area_drugs_for_company(company_id, area_id, idx)

        # Compute all dimensions
        tm_score, tm_missing, tm_actions   = score_target_mapping(drugs, idx)
        ow_score, ow_missing, ow_actions   = score_ownership_coverage(company_id, area_id, drugs, data, idx)
        src_score, src_missing, src_actions = score_source_coverage(drugs, area_id, idx)
        conf_score, conf_missing, conf_actions = score_confidence_coverage(drugs, area_id, idx)
        rec_score, rec_missing, rec_actions = score_enrichment_recency(company_id, area_id, idx)
        dl_score, dl_missing, dl_actions   = score_deal_linkage(company_id, idx)
        mi_score, mi_missing, mi_actions   = score_molecule_intelligence(drugs, idx)
        cat_score, cat_missing, cat_actions = score_catalyst_coverage(drugs, area_id, data, idx)
        prof_score, prof_missing, prof_actions = score_profile_completeness(company_id, area_id, idx)

        scores = {
            "target_mapping_score":        tm_score,
            "ownership_coverage_score":    ow_score,
            "source_coverage_score":       src_score,
            "confidence_coverage_score":   conf_score,
            "enrichment_recency_score":    rec_score,
            "deal_linkage_score":          dl_score,
            "molecule_intelligence_score": mi_score,
            "catalyst_coverage_score":     cat_score,
            "profile_completeness_score":  prof_score,
        }
        overall = compute_overall(scores)

        missing_map = {
            "target_mapping":        tm_missing[:10],
            "ownership":             ow_missing[:10],
            "source_coverage":       src_missing[:10],
            "confidence":            conf_missing[:10],
            "enrichment_recency":    rec_missing[:3],
            "deal_linkage":          dl_missing[:10],
            "molecule_intelligence": mi_missing[:10],
            "catalyst":              cat_missing[:10],
            "profile_fields":        prof_missing,
        }
        all_actions = (
            tm_actions + ow_actions + src_actions + conf_actions +
            rec_actions + dl_actions + mi_actions + cat_actions + prof_actions
        )
        rec_actions_final = build_recommendations(scores, missing_map) or all_actions

        row = {
            "entity_type":              "company",
            "entity_id":                entity_id,
            "company_id":               company_id,
            "area_id":                  area_id,
            "overall_score":            overall,
            **scores,
            "missing_items_json":       missing_map,
            "recommended_actions_json": rec_actions_final,
            "computed_at":              datetime.now(timezone.utc).isoformat(),
            "score_version":            SCORE_VERSION,
        }
        results.append(row)

    # Sort by overall score
    results.sort(key=lambda r: r["overall_score"] or 0)

    if not dry_run:
        print(f"\nWriting {len(results)} coverage_scores rows...")
        BATCH = 50
        written = 0
        for i in range(0, len(results), BATCH):
            batch = results[i:i+BATCH]
            # on_conflict targets the UNIQUE(entity_id, area_id) constraint
            out = sb_upsert("coverage_scores", batch, on_conflict="entity_id,area_id")
            written += len(out)
        print(f"  Written: {written}")
    else:
        print(f"\n[DRY RUN] Would write {len(results)} rows (skipped)")

    return results


# ── CLI report ────────────────────────────────────────────────────────────────

def print_report(results):
    if not results:
        print("No results to report.")
        return

    scores = [r["overall_score"] for r in results if r["overall_score"] is not None]
    platform_avg = round(sum(scores) / len(scores), 1) if scores else 0

    print("\n" + "=" * 70)
    print(f"  MERIDIAN COVERAGE REPORT  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    print(f"\n  Platform Coverage:  {platform_avg} / 100  ({len(results)} company/area pairs)\n")

    # Area averages
    area_totals = defaultdict(list)
    for r in results:
        if r["overall_score"] is not None:
            area_totals[r["area_id"]].append(r["overall_score"])
    print("  Coverage by Area:")
    for area, vals in sorted(area_totals.items(), key=lambda x: -sum(x[1])/len(x[1])):
        avg = round(sum(vals) / len(vals), 1)
        bar = "█" * int(avg / 5)
        print(f"    {area:20} {avg:5.1f}  {bar}")

    # Lowest 10
    print("\n" + "-" * 70)
    print("  Lowest Coverage (top 10 gaps):")
    print("-" * 70)
    for r in results[:10]:
        print(f"\n  {r['company_id']:20} / {r['area_id']:12}  Overall: {r['overall_score']}")
        dims = [
            ("target",   r.get("target_mapping_score")),
            ("source",   r.get("source_coverage_score")),
            ("recency",  r.get("enrichment_recency_score")),
            ("profile",  r.get("profile_completeness_score")),
            ("MI",       r.get("molecule_intelligence_score")),
            ("catalyst", r.get("catalyst_coverage_score")),
        ]
        dim_str = "  ".join(f"{k}={v:.0f}" for k, v in dims if v is not None)
        print(f"    Dims: {dim_str}")
        actions = r.get("recommended_actions_json", [])
        if actions:
            for a in actions[:3]:
                print(f"    → {a}")

    print("\n" + "=" * 70)

    # Dimension averages
    dim_names = [
        ("target_mapping_score",        "Target mapping"),
        ("source_coverage_score",       "Source coverage"),
        ("confidence_coverage_score",   "Confidence coverage"),
        ("enrichment_recency_score",    "Enrichment recency"),
        ("profile_completeness_score",  "Profile completeness"),
        ("molecule_intelligence_score", "Molecule intelligence"),
        ("catalyst_coverage_score",     "Catalyst coverage"),
        ("ownership_coverage_score",    "Ownership coverage"),
        ("deal_linkage_score",          "Deal linkage"),
    ]
    print("\n  Coverage by Dimension (platform average):")
    for field, label in dim_names:
        vals = [r[field] for r in results if r.get(field) is not None]
        if vals:
            avg = round(sum(vals) / len(vals), 1)
            bar = "█" * int(avg / 5)
            flag = "  ⚠" if avg < 70 else ""
            print(f"    {label:30} {avg:5.1f}  {bar}{flag}")

    print("\n" + "=" * 70 + "\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Compute Meridian coverage scores")
    parser.add_argument("--dry-run",  action="store_true", help="Compute but do not write to DB")
    parser.add_argument("--company",  type=str, help="Filter to single company_id")
    parser.add_argument("--area",     type=str, help="Filter to single area_id")
    args = parser.parse_args()

    data = load_data()
    idx  = build_indexes(data)
    results = compute_all(
        data, idx,
        filter_company=args.company,
        filter_area=args.area,
        dry_run=args.dry_run
    )
    print_report(results)

    if args.dry_run:
        print("[DRY RUN] No rows written. Pass --no-dry-run or remove flag to write.")


if __name__ == "__main__":
    main()
