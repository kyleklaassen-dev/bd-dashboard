#!/usr/bin/env python3
"""
flywheel_phase2.py — Fine-Tuning Flywheel Phase 2
==================================================
Builds on Phase 1 (extract_fine_tune_signal.py) to:

1. DRIFT MONITOR (G3): detect confirmed values that have changed since Kyle approved them
2. AUTO-RESTORE: patch any drifted fields back to Kyle's confirmed values
3. TRAINING JSONL (G14): generate prompt→response pairs for LLM fine-tuning

Runs weekly (or on demand) to keep enrichment quality anchored to
Kyle's confirmed ground truth.

Usage:
  python3 scripts/flywheel_phase2.py                    # full run: detect + restore + export
  python3 scripts/flywheel_phase2.py --detect-only      # just report drift, no writes
  python3 scripts/flywheel_phase2.py --export-only      # just build training JSONL
  python3 scripts/flywheel_phase2.py --entity-type drug

Output files:
  output/drift_report_YYYY-MM-DD.json   — drift summary
  output/training_pairs_YYYY-MM-DD.jsonl — fine-tuning pairs
"""

import os, sys, json, argparse, datetime, re
from typing import Optional
import requests

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DATA_DIR = os.path.join(_REPO, "data")
_OUTPUT_DIR = os.path.join(_REPO, "output")
os.makedirs(_OUTPUT_DIR, exist_ok=True)

def _key(f):
    p = os.path.join(_REPO, f)
    return open(p).read().strip() if os.path.exists(p) else None

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://tghntyofptvfhmtchwcv.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or _key(".supabase_service_key") or ""
if not SUPABASE_KEY: print("ERROR: no SUPABASE_SERVICE_KEY"); sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
SB_H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
TODAY = datetime.date.today().isoformat()
NOW = datetime.datetime.utcnow().isoformat()

RESTORABLE_FIELDS = {
    "drug": {
        "ailux_angle", "drug_summary", "source_url", "differentiation_thesis",
        "patient_benefit_simplified", "unmet_need_addressed", "why_it_matters",
        "mechanism", "target", "indication_short"
    },
    "partnership": {"source_url", "partnership_verified"},
    "deal": {"source_url", "total_usd_m"}
}


def sb_get(table, params, limit=500):
    params = {**params, "limit": str(limit)}
    r = requests.get(f"{BASE}/{table}", headers=SB_H, params=params, timeout=20)
    return r.json() if r.status_code == 200 else []


def sb_patch(table, params, payload):
    r = requests.patch(f"{BASE}/{table}", headers=SB_H, params=params, json=payload, timeout=20)
    return r.status_code in (200, 204)


def get_current_value(entity_type: str, entity_id: str, field: str) -> Optional[str]:
    """Fetch the current DB value of a specific field for an entity."""
    raw_id = entity_id.split(":")[-1] if ":" in entity_id else entity_id

    table_map = {
        "drug": ("drugs", "id"),
        "partnership": ("company_partnerships", "id"),
        "deal": ("deals", "id"),
    }
    if entity_type not in table_map:
        return None

    table, id_col = table_map[entity_type]
    rows = sb_get(table, {id_col: f"eq.{raw_id}", "select": field, "limit": "1"})
    if rows and isinstance(rows, list):
        return str(rows[0].get(field) or "")
    return None


def restore_value(entity_type: str, entity_id: str, field: str, value: str) -> bool:
    """Restore a confirmed value to the DB."""
    raw_id = entity_id.split(":")[-1] if ":" in entity_id else entity_id
    table_map = {"drug": ("drugs","id"), "partnership": ("company_partnerships","id"), "deal": ("deals","id")}
    if entity_type not in table_map: return False
    table, id_col = table_map[entity_type]
    return sb_patch(table, {id_col: f"eq.{raw_id}"}, {field: value, "updated_at": NOW})


def build_training_pair(review: dict, entity_context: dict) -> Optional[dict]:
    """Build a prompt→response pair for fine-tuning."""
    entity_type = review.get("entity_type","")
    field = review.get("field_name","")
    confirmed = review.get("field_value","")

    if not confirmed or not field: return None
    if entity_type != "drug": return None  # focus on drug enrichments for now

    name = entity_context.get("name") or entity_context.get("id","unknown")
    stage = entity_context.get("stage","unknown stage")
    target = entity_context.get("target","")
    company = entity_context.get("company_id","")

    # Build a realistic enrichment prompt
    prompt = f"""Research the pharmaceutical drug "{name}" for the Meridian BD intelligence platform.
Context: stage={stage}, target={target}, company={company}

Provide the field "{field}" as a concise, accurate value for this drug.
Respond with ONLY the field value, no JSON wrapper, no labels."""

    return {
        "type": "fine_tune",
        "entity_type": entity_type,
        "entity_id": review.get("entity_id",""),
        "field": field,
        "prompt": prompt,
        "response": confirmed,
        "source": "kyle_confirmed",
        "session": review.get("session_id",""),
        "date": TODAY,
    }


def main():
    parser = argparse.ArgumentParser(description="Flywheel Phase 2: drift monitor + training data")
    parser.add_argument("--detect-only", action="store_true", help="Report drift without writing")
    parser.add_argument("--export-only", action="store_true", help="Only build training JSONL")
    parser.add_argument("--entity-type", default=None)
    args = parser.parse_args()

    # ── Fetch all confirmed reviews ──────────────────────────────────────────
    params = {"fine_tune_use": "eq.true", "select": "*"}
    if args.entity_type:
        params["entity_type"] = f"eq.{args.entity_type}"
    reviews = sb_get("kyle_reviews", params, limit=500)
    print(f"Loaded {len(reviews)} confirmed kyle_reviews")

    # ── Drift detection ───────────────────────────────────────────────────────
    drift_report = {"date": TODAY, "total": len(reviews), "drifted": [], "restored": [], "matched": [], "no_value": []}
    training_pairs = []
    restored_count = 0

    for rev in reviews:
        entity_type = rev.get("entity_type","")
        entity_id = rev.get("entity_id","")
        field = rev.get("field_name","")
        confirmed = str(rev.get("field_value","") or "").strip()

        if not confirmed or confirmed.startswith("[WARNING]") or confirmed.startswith("[NEEDS_REVIEW]"):
            drift_report["no_value"].append({"entity_id": entity_id, "field": field})
            continue

        if args.export_only:
            # Fetch context for training pair
            raw_id = entity_id.split(":")[-1] if ":" in entity_id else entity_id
            ctx_rows = sb_get("drugs", {"id": f"eq.{raw_id}", "select": "id,name,stage,target,company_id"})
            ctx = ctx_rows[0] if ctx_rows else {"id": raw_id}
            pair = build_training_pair(rev, ctx)
            if pair: training_pairs.append(pair)
            continue

        current = get_current_value(entity_type, entity_id, field)
        if current is None:
            drift_report["no_value"].append({"entity_id": entity_id, "field": field})
            continue

        # Compare
        if not current:
            status = "empty"
        elif current.strip() == confirmed:
            drift_report["matched"].append({"entity_id": entity_id, "field": field})
            status = "match"
        elif confirmed[:60] in current or current[:60] in confirmed:
            status = "partial"
        else:
            status = "drifted"

        if status in ("drifted", "empty"):
            drift_report["drifted"].append({
                "entity_id": entity_id, "entity_type": entity_type, "field": field,
                "status": status,
                "confirmed_preview": confirmed[:100],
                "current_preview": current[:100],
            })

            # Auto-restore if field is in restorable set
            restorable = RESTORABLE_FIELDS.get(entity_type, set())
            if field in restorable and not args.detect_only:
                ok = restore_value(entity_type, entity_id, field, confirmed)
                if ok:
                    drift_report["restored"].append({"entity_id": entity_id, "field": field})
                    restored_count += 1
                    print(f"  🔧 Restored {entity_id}.{field}")

        # Always build training pair
        raw_id = entity_id.split(":")[-1] if ":" in entity_id else entity_id
        ctx_rows = sb_get("drugs", {"id": f"eq.{raw_id}", "select": "id,name,stage,target,company_id"})
        ctx = ctx_rows[0] if ctx_rows else {"id": raw_id}
        pair = build_training_pair(rev, ctx)
        if pair: training_pairs.append(pair)

    # ── Write outputs ─────────────────────────────────────────────────────────
    drift_path = os.path.join(_OUTPUT_DIR, f"drift_report_{TODAY}.json")
    with open(drift_path, "w") as f:
        json.dump(drift_report, f, indent=2)

    train_path = os.path.join(_OUTPUT_DIR, f"training_pairs_{TODAY}.jsonl")
    with open(train_path, "w") as f:
        for pair in training_pairs:
            f.write(json.dumps(pair) + "\n")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"FLYWHEEL PHASE 2 SUMMARY — {TODAY}")
    print(f"{'='*50}")
    print(f"  Reviews processed:     {len(reviews)}")
    print(f"  Matched (no drift):    {len(drift_report['matched'])}")
    print(f"  Drifted (changed):     {len([d for d in drift_report['drifted'] if d['status']=='drifted'])}")
    print(f"  Empty (regressed):     {len([d for d in drift_report['drifted'] if d['status']=='empty'])}")
    print(f"  Restored:              {restored_count}")
    print(f"  Training pairs:        {len(training_pairs)}")
    print(f"\n  Drift report:  {drift_path}")
    print(f"  Training data: {train_path}")

    if drift_report["drifted"]:
        print(f"\n  ⚠ {len(drift_report['drifted'])} drifted fields:")
        for d in drift_report["drifted"][:8]:
            print(f"    {d['entity_id']} .{d['field']}: {d['status']}")


if __name__ == "__main__":
    main()
