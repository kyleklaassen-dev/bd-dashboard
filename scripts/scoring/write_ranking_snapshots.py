#!/usr/bin/env python3
"""
write_ranking_snapshots.py — Record next_gen_rankings daily snapshot.

Called by the enrichment pipeline AFTER drug_competitive_scores are updated.
The browser never writes to this table — it only reads.
This script captures: entity_id, area_id, rank_position, total_score, stage, 
competitive_relevance, is_ailux for all next-gen bispecific programs.

Usage:
  python3 scripts/write_ranking_snapshots.py [--area tl1a] [--dry-run]

GitHub Actions: add as a step after company-enrichment.yml completes.
"""

import os, sys, argparse, datetime

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _common import load_credentials  # noqa: E402
import _db                              # noqa: E402

SUPABASE_URL, SUPABASE_KEY, _ = load_credentials(require_anthropic=False)
_db.init_db(SUPABASE_URL, SUPABASE_KEY)

NEXT_GEN_AREAS = ["tl1a", "ibd", "fcrn"]

STAGE_W = {
    "approved": 10, "approved_us": 10, "approved_eu": 10,
    "bla_under_review": 9.5, "Phase 3": 9, "Phase 2/3": 8.5,
    "Phase 2": 8, "Phase 1/2": 7, "Phase 1": 6,
    "IND filed": 4, "IND-enabling": 2.5, "Preclinical": 1, "Terminated": 0,
}

AILUX_DEV_SC = {
    "approved": 50, "approved_us": 50, "bla_under_review": 45,
    "Phase 3": 40, "Phase 2/3": 37, "Phase 2": 35, "Phase 1": 20,
    "IND filed": 12, "IND-enabling": 7, "Preclinical": 3,
}

def sb_get(table, params=None):
    p = dict(params or {})
    p.setdefault("limit", "1000")
    return _db.sb_get(table, p)

def sb_upsert(table, rows):
    """_db.sb_upsert returns the upserted rows (or [] on failure); translate
    to an HTTP-status-like int since the call site just prints it informationally."""
    result = _db.sb_upsert(table, rows)
    return 200 if (result or not rows) else None


def compute_rankings(area_id, dry_run=False):
    print(f"\n=== {area_id} rankings ===")
    today = datetime.date.today().isoformat()

    # Fetch drug_competitive_scores for this area (Next Gen drugs only)
    scores = sb_get("drug_competitive_scores", {
        "context_id": f"eq.{area_id}",
        "cls": "eq.Next%20Gen",
        "select": "drug_id,total_competition_score,competitive_relevance",
    })
    if not scores:
        print(f"  No Next Gen scores for {area_id}")
        return 0

    # Fetch drug stages
    drug_ids = list({s["drug_id"] for s in scores})
    drugs_raw = sb_get("drugs", {
        "id": f"in.({','.join(drug_ids)})",
        "select": "id,stage,company_id,name",
    })
    stage_map = {d["id"]: d["stage"] for d in drugs_raw}
    company_map = {d["id"]: d["company_id"] for d in drugs_raw}
    name_map = {d["id"]: d["name"] for d in drugs_raw}

    # Compute composite score: 70% enrichment score + 30% stage signal
    def composite(s):
        db_score = s.get("total_competition_score") or 0
        stage = stage_map.get(s["drug_id"], "Preclinical")
        is_ailux = company_map.get(s["drug_id"]) == "ailux"
        if is_ailux:
            return AILUX_DEV_SC.get(stage, 3)
        return (db_score * 0.7) + ((STAGE_W.get(stage, 1)) * 0.3)

    candidates = sorted(scores, key=lambda s: -composite(s))

    snapshot_rows = []
    for rank, s in enumerate(candidates, 1):
        drug_id = s["drug_id"]
        stage = stage_map.get(drug_id, "Preclinical")
        is_ailux = company_map.get(drug_id) == "ailux"
        sc = composite(s)
        snapshot_rows.append({
            "entity_id":       company_map.get(drug_id, drug_id),
            "entity_name":     name_map.get(drug_id, drug_id),
            "area_id":         area_id,
            "rank_position":   rank,
            "total_score":     round(sc, 2),
            "stage":           stage,
            "competitive_relev": s.get("competitive_relevance"),
            "is_ailux":        is_ailux,
            "snapshot_date":   today,
        })
        print(f"  #{rank:2} {name_map.get(drug_id, drug_id):25} score={sc:.1f}  stage={stage}")

    if dry_run:
        print(f"  DRY RUN — {len(snapshot_rows)} rows not written")
    else:
        status = sb_upsert("next_gen_rankings", snapshot_rows)
        print(f"  Wrote {len(snapshot_rows)} rows → {status}")

    return len(snapshot_rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", default=None, help="Specific area (tl1a/ibd/fcrn)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    areas = [args.area] if args.area else NEXT_GEN_AREAS
    total = 0
    for area in areas:
        total += compute_rankings(area, dry_run=args.dry_run)
    print(f"\nDone. {total} ranking rows {'(dry run)' if args.dry_run else 'written'}.")


if __name__ == "__main__":
    main()
