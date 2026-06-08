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

import json, os, sys, datetime, math

import requests

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _common import load_credentials, sb_headers  # noqa: E402
import _db                                          # noqa: E402

DRY_RUN  = "--dry-run" in sys.argv
NOW      = datetime.datetime.utcnow()

# Optional: --landscape-id N to restrict
FILTER_ID = None
for i, arg in enumerate(sys.argv):
    if arg == "--landscape-id" and i + 1 < len(sys.argv):
        FILTER_ID = int(sys.argv[i + 1])

SB_URL, SUPABASE_KEY, _ = load_credentials(require_anthropic=False)
_db.init_db(SB_URL, SUPABASE_KEY)

HEADERS_INSERT = {**sb_headers(SUPABASE_KEY),
                  "Prefer": "resolution=ignore-duplicates,return=representation"}


def get(table, params, limit=1000):
    p = {**params, "limit": str(limit)}
    return _db.sb_get(table, p)


def patch(table, filters, updates):
    if DRY_RUN:
        return True
    return _db.sb_patch(table, updates, filters)


def insert(table, rows):
    """coverage_computation_log writes use skip-on-conflict (ignore-duplicates)
    — a strategy _db.sb_upsert (merge-duplicates only) doesn't support, so this
    stays a direct request with the ignore-duplicates Prefer header."""
    if DRY_RUN or not rows:
        return len(rows)
    try:
        r = requests.post(f"{SB_URL}/rest/v1/{table}", headers=HEADERS_INSERT,
                          json=rows if isinstance(rows, list) else [rows], timeout=30)
        if r.status_code in (200, 201):
            result = r.json()
            return len(result) if result else len(rows)
        print(f"  INSERT {table} HTTP {r.status_code}: {r.text[:300]}")
        return 0
    except Exception as e:
        print(f"  INSERT {table} error: {e}")
        return 0


def section(title):
    print(f"\n{'═'*60}\n  {title}\n{'═'*60}")


# ─────────────────────────────────────────────────────────────────
# Data fetchers
# ─────────────────────────────────────────────────────────────────

def fetch_landscape_drug_ids(landscape_id):
    """
    Get the set of drug_ids relevant to a landscape.
    Source: landscape_expected_competitors (confirmed drug_ids)
    + drugs in drug_areas that match the landscape's area.
    """
    # From expected competitors (drug_id may be null for Tier 3)
    lec_rows = get("landscape_expected_competitors", {
        "landscape_id": f"eq.{landscape_id}",
        "select":       "drug_id,drug_name,tier,confirmed,tier3_weight",
    })

    # Also get all drugs in the relevant areas from drug_areas
    # We'll resolve area_ids from the landscape row
    return lec_rows


def compute_drug_coverage(lec_rows, expected_drug_count):
    """
    drug_coverage_score = sum of weights for captured drugs / expected_drug_count
    - Tier 1/2 confirmed=TRUE:  weight 1.0
    - Tier 3 confirmed=TRUE:    weight tier3_weight (0.5)
    - confirmed=FALSE:          weight 0.0
    """
    if not expected_drug_count:
        return 0.0, {}

    numerator = 0.0
    details = {"confirmed": [], "missing": [], "tier3_pending": []}

    for row in lec_rows:
        if row["confirmed"]:
            w = float(row["tier3_weight"])
            numerator += w
            details["confirmed"].append(row["drug_name"])
        else:
            if row["tier"] == 3:
                details["tier3_pending"].append(row["drug_name"])
            else:
                details["missing"].append(row["drug_name"])

    score = min(numerator / expected_drug_count, 1.0)
    return score, details


def compute_relationship_coverage(landscape_id, expected_relationship_count):
    """
    relationship_coverage_score = active edges in scope / expected_relationship_count
    Queries entity_edges where scope_area_id matches areas for this landscape.
    """
    if not expected_relationship_count:
        return 0.0, {}

    # Get edges scoped to igf1r or ted (TED landscape areas)
    # Use scope_area_id = igf1r as primary; also catch TED-scoped edges
    edges_igf1r = get("entity_edges", {
        "scope_area_id": "eq.igf1r",
        "status":        "eq.active",
        "select":        "subject_id,predicate,object_id,staleness_status",
    })
    edges_ted = get("entity_edges", {
        "scope_area_id": "eq.ted",
        "status":        "eq.active",
        "select":        "subject_id,predicate,object_id,staleness_status",
    })

    # Deduplicate by (subject,predicate,object)
    seen = set()
    all_edges = []
    for e in edges_igf1r + edges_ted:
        key = (e["subject_id"], e["predicate"], e["object_id"])
        if key not in seen:
            seen.add(key)
            all_edges.append(e)

    captured = len(all_edges)
    score = min(captured / expected_relationship_count, 1.0)
    details = {
        "captured": captured,
        "expected": expected_relationship_count,
        "edges": [f"{e['subject_id']} {e['predicate']} {e['object_id']}" for e in all_edges],
    }
    return score, details


def compute_catalyst_coverage(area_ids, expected_catalyst_count):
    """
    catalyst_coverage_score = TED-relevant catalysts / expected_catalyst_count
    Counts catalysts with area_id in landscape areas + status pending/met.
    """
    if not expected_catalyst_count:
        return 0.0, {}

    catalysts = []
    for area_id in area_ids:
        rows = get("catalysts", {
            "area_id":         f"eq.{area_id}",
            "catalyst_status": "in.(pending,met)",
            "select":          "id,label,area_id,catalyst_status,catalyst_date",
        })
        catalysts.extend(rows)

    # Deduplicate by id
    seen_ids = set()
    unique_cats = []
    for c in catalysts:
        if c["id"] not in seen_ids:
            seen_ids.add(c["id"])
            unique_cats.append(c)

    captured = len(unique_cats)
    score = min(captured / expected_catalyst_count, 1.0)
    details = {
        "captured": captured,
        "expected": expected_catalyst_count,
        "note": f"Catalysts in areas {area_ids} with status in (pending,met)",
    }
    return score, details


def compute_source_validation(drug_ids_in_scope):
    """
    source_validation_score = sourced drug_area_scores rows / total
    'sourced' = source_url IS NOT NULL AND confidence_level IN (confirmed, supported)
    Scope: drug_area_scores rows where drug_id is in the landscape's drug set.
    """
    if not drug_ids_in_scope:
        return 0.0, {}

    id_list = ",".join(drug_ids_in_scope)
    all_rows = get("drug_area_scores", {
        "drug_id": f"in.({id_list})",
        "select":  "drug_id,area_id,source_url,confidence_level",
    })

    total = len(all_rows)
    if not total:
        return 0.0, {"total": 0, "sourced": 0}

    sourced = sum(
        1 for r in all_rows
        if r.get("source_url") and r.get("confidence_level") in ("confirmed", "supported")
    )
    score = sourced / total
    details = {
        "total":   total,
        "sourced": sourced,
        "unsourced_drugs": [
            r["drug_id"] for r in all_rows
            if not (r.get("source_url") and r.get("confidence_level") in ("confirmed", "supported"))
        ],
    }
    return score, details


def compute_staleness_penalty(landscape_id, drug_ids_in_scope):
    """
    staleness_penalty = stale items / total items tracked
    Sources: entity_edges (scope igf1r/ted) + mechanism_status (TED) + geographic_approvals (TED)
    'stale' = staleness_status IN (stale, needs_revalidation)
    """
    stale_items = []
    total_items = []

    # entity_edges
    for area in ["igf1r", "ted"]:
        rows = get("entity_edges", {
            "scope_area_id": f"eq.{area}",
            "status":        "eq.active",
            "select":        "subject_id,predicate,object_id,staleness_status",
        })
        for r in rows:
            key = f"edge:{r['subject_id']}.{r['predicate']}.{r['object_id']}"
            total_items.append(key)
            if r.get("staleness_status") in ("stale", "needs_revalidation"):
                stale_items.append(key)

    # mechanism_status (TED indication)
    mech_rows = get("mechanism_status", {
        "indication": "eq.TED",
        "select":     "target_name,indication,staleness_status",
    })
    for r in mech_rows:
        key = f"mechanism:{r['target_name']}×{r['indication']}"
        total_items.append(key)
        if r.get("staleness_status") in ("stale", "needs_revalidation"):
            stale_items.append(key)

    # geographic_approvals (TED)
    geo_rows = get("geographic_approvals", {
        "indication": "eq.TED",
        "select":     "drug_name,geography,staleness_status",
    })
    for r in geo_rows:
        key = f"geo:{r['drug_name']}×{r['geography']}"
        total_items.append(key)
        if r.get("staleness_status") in ("stale", "needs_revalidation"):
            stale_items.append(key)

    total = len(set(total_items))  # deduplicate
    stale = len(set(stale_items))

    if not total:
        return 0.0, {}

    penalty = stale / total
    details = {
        "stale":  stale,
        "total":  total,
        "stale_items": list(set(stale_items)),
    }
    return penalty, details


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
