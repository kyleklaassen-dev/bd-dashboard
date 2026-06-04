#!/usr/bin/env python3
"""
compute_landscape_scores.py
Computes landscape_dependency_score and sub-component scores for
competitive_landscapes rows where LDS is NULL.

Formula (verified against igf1r canonical):
  LDS = drug_coverage_score * 35
      + relationship_coverage_score * 25
      + catalyst_coverage_score * 20
      + source_validation_score * 15
      - staleness_penalty * 5

Sub-component computation:
  drug_coverage_score:
      (drugs in DCS for this area with source_url) / (drugs in DCS for this area)
      Capped at 1.0. If expected_drug_count is set and > actual, uses that as denominator.

  relationship_coverage_score:
      (drugs in area with at least 1 deal or partnership) / (drugs in DCS for area)

  catalyst_coverage_score:
      (drugs in area with at least 1 catalyst) / (expected_catalyst_count or actual with catalysts * 1.2)

  source_validation_score:
      (drugs in DCS area with source_url not null) / (drugs in DCS area)

  staleness_penalty:
      0.0 if all drugs synced within 60 days
      0.5 if avg last_synced > 60 days ago
      1.0 if avg last_synced > 120 days ago (or null)

Usage:
  python3 scripts/compute_landscape_scores.py
  python3 scripts/compute_landscape_scores.py --dry-run
  python3 scripts/compute_landscape_scores.py --area ibd
"""

import os, sys, json, argparse, datetime, math
from typing import Optional
import requests

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# This module prints progress directly; the LDS-feedback step calls log(),
# so alias it to print to keep a single output path (fixes NameError crash).
log = print

def _key(f):
    p = os.path.join(_REPO, f)
    return open(p).read().strip() if os.path.exists(p) else None

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://tghntyofptvfhmtchwcv.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or _key(".supabase_service_key") or ""
if not SUPABASE_KEY: print("ERROR: no SUPABASE_SERVICE_KEY"); sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
SB_H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"}
NOW = datetime.datetime.utcnow()
NOW_ISO = NOW.isoformat()


def sb_get(table, params):
    try:
        r = requests.get(f"{BASE}/{table}", headers=SB_H, params=params, timeout=20)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        print(f"  [sb_get {table}] {e}"); return []


def sb_patch(table, params, payload):
    try:
        r = requests.patch(f"{BASE}/{table}", headers=SB_H, params=params, json=payload, timeout=20)
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"  [sb_patch {table}] {e}"); return False


def staleness_score(drugs: list) -> float:
    """Returns staleness_penalty 0.0–1.0 based on last_synced_date."""
    dates = []
    for d in drugs:
        raw = d.get("last_synced_date")
        if raw:
            try:
                dt = datetime.datetime.fromisoformat(str(raw)[:10])
                dates.append((NOW - dt).days)
            except Exception:
                pass
    if not dates:
        return 1.0  # no sync data → max staleness
    avg_days = sum(dates) / len(dates)
    if avg_days <= 60:
        return 0.0
    elif avg_days <= 120:
        return round((avg_days - 60) / 60 * 0.5, 3)
    else:
        return min(1.0, round(0.5 + (avg_days - 120) / 120 * 0.5, 3))


def compute_for_area(landscape: dict, dry_run: bool = False) -> dict:
    area_id = landscape["area_id"]
    print(f"\n=== {area_id} / {landscape.get('target_pair','?')} ===")

    # ── Fetch drugs in this area from DCS ────────────────────────────────────
    # Use the most specific context available for this area
    ctx_map = {
        "ibd":        [("indication", "uc"), ("indication", "cd")],
        "tl1a":       [("target", "tl1a")],
        "fcrn":       [("target", "fcrn")],
        "atopy":      [("strategic_view", "atopy")],
        "il4ra":      [("target", "il4ra")],
        "tslp":       [("target", "tslp")],
        "igf1r":      [("target", "igf1r")],
        "ted":        [("indication", "ted")],
        "autoimmune": [("strategic_view", "autoimmune")],
        "tcell":      [("platform_view", "tcell")],
        "respiratory":[("strategic_view", "respiratory")],
    }
    contexts = ctx_map.get(area_id, [("strategic_view", area_id)])

    dcs_drug_ids = set()
    for ctx_type, ctx_id in contexts:
        rows = sb_get("drug_competitive_scores", {
            "context_type": f"eq.{ctx_type}",
            "context_id":   f"eq.{ctx_id}",
            "select": "drug_id",
            "limit": "200",
        })
        dcs_drug_ids |= {r["drug_id"] for r in rows}

    if not dcs_drug_ids:
        print(f"  WARNING: no DCS rows found for {area_id}")
        return {}

    print(f"  DCS drug count: {len(dcs_drug_ids)}")

    # ── Fetch drug details ────────────────────────────────────────────────────
    drug_ids_list = list(dcs_drug_ids)
    # Supabase: use `in.(a,b,c)` syntax
    ids_param = "(" + ",".join(drug_ids_list) + ")"
    drugs = sb_get("drugs", {
        "id": f"in.{ids_param}",
        "select": "id,source_url,last_synced_date",
        "limit": "200",
    })

    total = len(drugs)
    if total == 0:
        print("  WARNING: no drug rows returned"); return {}

    # ── Sub-component 1: drug_coverage_score ─────────────────────────────────
    expected_drug = landscape.get("expected_drug_count") or total
    actual_drug = landscape.get("drug_count") or total
    drug_coverage = min(1.0, round(actual_drug / max(expected_drug, 1), 4))
    print(f"  drug_coverage: {actual_drug}/{expected_drug} = {drug_coverage}")

    # ── Sub-component 2: source_validation_score ─────────────────────────────
    with_source = sum(1 for d in drugs if d.get("source_url"))
    source_validation = round(with_source / total, 4)
    print(f"  source_validation: {with_source}/{total} = {source_validation}")

    # ── Sub-component 3: relationship_coverage_score ─────────────────────────
    # Drugs in this area that have at least 1 deal row
    drug_deals = set()
    for chunk_start in range(0, len(drug_ids_list), 50):
        chunk = drug_ids_list[chunk_start:chunk_start+50]
        ids_chunk = "(" + ",".join(chunk) + ")"
        deal_rows = sb_get("deals", {
            "drug_id": f"in.{ids_chunk}",
            "select": "drug_id",
            "limit": "200",
        })
        drug_deals |= {r["drug_id"] for r in deal_rows}
    drugs_with_deals = len(drug_deals & dcs_drug_ids)
    expected_rel = landscape.get("expected_relationship_count") or max(int(total * 0.6), 1)
    rel_coverage = min(1.0, round(drugs_with_deals / expected_rel, 4))
    print(f"  relationship_coverage: {drugs_with_deals} drugs with deals / expected_rel={expected_rel} = {rel_coverage}")

    # ── Sub-component 4: catalyst_coverage_score ─────────────────────────────
    drug_catalysts = set()
    for chunk_start in range(0, len(drug_ids_list), 50):
        chunk = drug_ids_list[chunk_start:chunk_start+50]
        ids_chunk = "(" + ",".join(chunk) + ")"
        cat_rows = sb_get("catalysts", {
            "drug_id": f"in.{ids_chunk}",
            "select": "drug_id",
            "limit": "200",
        })
        drug_catalysts |= {r["drug_id"] for r in cat_rows}
    drugs_with_cats = len(drug_catalysts & dcs_drug_ids)
    expected_cat = landscape.get("expected_catalyst_count") or max(int(total * 0.7), 1)
    cat_coverage = min(1.0, round(drugs_with_cats / expected_cat, 4))
    print(f"  catalyst_coverage: {drugs_with_cats} drugs with catalysts / expected_cat={expected_cat} = {cat_coverage}")

    # ── Sub-component 5: staleness_penalty ───────────────────────────────────
    staleness = staleness_score(drugs)
    print(f"  staleness_penalty: {staleness}")

    # ── Compute LDS ──────────────────────────────────────────────────────────
    lds = round(
        drug_coverage     * 35
        + rel_coverage    * 25
        + cat_coverage    * 20
        + source_validation * 15
        - staleness       * 5,
        2
    )
    print(f"  LDS = {drug_coverage}×35 + {rel_coverage}×25 + {cat_coverage}×20 + {source_validation}×15 - {staleness}×5 = {lds}")

    result = {
        "drug_coverage_score":         drug_coverage,
        "relationship_coverage_score": rel_coverage,
        "catalyst_coverage_score":     cat_coverage,
        "source_validation_score":     source_validation,
        "staleness_penalty":           staleness,
        "landscape_dependency_score":  lds,
        "expected_drug_count":         expected_drug,
        "expected_relationship_count": expected_rel,
        "expected_catalyst_count":     expected_cat,
        "drug_count":                  actual_drug,
        "coverage_computed_at":        NOW_ISO,
    }

    if not dry_run:
        ok = sb_patch("competitive_landscapes",
                      {"area_id": f"eq.{area_id}"},
                      result)
        print(f"  {'✓ written' if ok else '✗ write failed'}")
    else:
        print("  DRY RUN — not writing")

    return result


def main():
    parser = argparse.ArgumentParser(description="Compute landscape_dependency_score for all areas")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--area", help="Limit to one area_id")
    parser.add_argument("--all", action="store_true", help="Recompute all areas, not just null ones")
    args = parser.parse_args()

    # Fetch landscapes needing computation
    params = {"select": "*", "limit": "20"}
    if args.area:
        params["area_id"] = f"eq.{args.area}"
    elif not args.all:
        params["landscape_dependency_score"] = "is.null"

    landscapes = sb_get("competitive_landscapes", params)
    print(f"Found {len(landscapes)} landscape(s) needing LDS computation")

    results = {}
    for landscape in landscapes:
        r = compute_for_area(landscape, dry_run=args.dry_run)
        if r:
            results[landscape["area_id"]] = r["landscape_dependency_score"]

    print(f"\n=== Done ===")
    for area, lds in sorted(results.items()):
        print(f"  {area}: LDS={lds}")

    # ── N4 fix: LDS → enrichment priority feedback ────────────────────────────
    # Areas with low LDS (rel_coverage below 0.5) get a +15 priority boost
    # in the research_queue for their companies/drugs so the next enrichment
    # run focuses more effort on gap-filling for weak areas.
    if not args.dry_run and results:
        _apply_lds_priority_feedback(results)


def _apply_lds_priority_feedback(results: dict):
    """N4: Boost research_queue priority for companies in low-LDS areas."""
    # Areas with LDS below 75 get boosted; below 60 get max boost
    LOW_THRESHOLD = 75
    BOOST_MEDIUM = 8   # LDS 60-75
    BOOST_HIGH = 15    # LDS < 60

    boosted_total = 0
    for area_id, lds in results.items():
        if lds >= LOW_THRESHOLD:
            continue
        boost = BOOST_HIGH if lds < 60 else BOOST_MEDIUM

        # Find companies in this area's research_queue and boost priority
        try:
            r = requests.get(f"{BASE}/research_queue",
                headers=SB_H,
                params={"area_id": f"eq.{area_id}",
                        "select": "id,priority_score",
                        "assigned_status": "eq.pending",
                        "limit": "50"},
                timeout=15)
            rows = r.json() if r.status_code == 200 else []
            for row in rows:
                current = row.get("priority_score") or 0
                new_score = min(100, current + boost)
                requests.patch(f"{BASE}/research_queue",
                    headers={**SB_H, "Prefer": "return=minimal"},
                    params={"id": f"eq.{row['id']}"},
                    json={"priority_score": new_score},
                    timeout=10)
                boosted_total += 1
        except Exception as e:
            log(f"  [LDS feedback warn] {area_id}: {e}")

    if boosted_total:
        log(f"N4 LDS feedback: boosted {boosted_total} queue items for low-LDS areas")
    else:
        log("N4 LDS feedback: no pending queue items in low-LDS areas (queue may be empty)")


if __name__ == "__main__":
    main()
