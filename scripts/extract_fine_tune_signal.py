#!/usr/bin/env python3
"""
extract_fine_tune_signal.py
Meridian Fine-Tuning Flywheel — Phase 1: Signal Extraction

Reads kyle_reviews (where fine_tune_use=True) and produces structured
training examples for enrichment quality improvement.

Current signal (109 records, all action=confirmed):
  - 89 drug field confirmations
  - 19 partnership confirmations
  - 1 deal confirmation

Output: fine_tune_signal.jsonl — one JSON object per review, format:
  {
    "entity_type": "drug",
    "entity_id": "tulisokibart",
    "field_name": "mechanism",
    "confirmed_value": "...",
    "entity_context": {...},  # full entity record at time of review
    "enrichment_prompt_hint": "...",
    "quality_signal": "confirmed",
    "session_id": "..."
  }

Usage:
  python3 scripts/extract_fine_tune_signal.py
  python3 scripts/extract_fine_tune_signal.py --output /path/to/output.jsonl
  python3 scripts/extract_fine_tune_signal.py --entity-type drug

Next steps (Phase 2, not yet built):
  - Compare confirmed values against current DB values to detect drift
  - Flag fields where DB value has drifted from confirmed value
  - Generate correction prompts for model improvement
  - Build negative examples by tracking rejected enrichments
"""

import os, sys, json, argparse, datetime
import requests

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _key(f):
    p = os.path.join(_REPO, f)
    return open(p).read().strip() if os.path.exists(p) else None

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://tghntyofptvfhmtchwcv.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or _key(".supabase_service_key") or ""
if not SUPABASE_KEY:
    print("ERROR: no SUPABASE_SERVICE_KEY"); sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
SB_H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


def sb_get(table, params, limit=500):
    params = {**params, "limit": str(limit)}
    r = requests.get(f"{BASE}/{table}", headers=SB_H, params=params, timeout=20)
    return r.json() if r.status_code == 200 else []


def resolve_entity(entity_type: str, entity_id: str) -> dict:
    """Fetch the full entity record for context."""
    # entity_id format: "table:id_value" or just "id_value"
    raw_id = entity_id.split(":")[-1] if ":" in entity_id else entity_id

    if entity_type == "drug":
        rows = sb_get("drugs", {"id": f"eq.{raw_id}",
            "select": "id,name,target,mechanism,stage,company_id,overlap,ailux_angle,drug_summary,indication_short"})
        return rows[0] if rows else {"id": raw_id}

    elif entity_type == "partnership":
        rows = sb_get("company_partnerships", {"id": f"eq.{raw_id}",
            "select": "id,company_id,partner_company_id,deal_type,partnership_verified,source_url"})
        return rows[0] if rows else {"id": raw_id}

    elif entity_type == "deal":
        rows = sb_get("deals", {"id": f"eq.{raw_id}",
            "select": "id,headline,drug_id,from_company,to_company,deal_type,total_usd_m,source_url"})
        return rows[0] if rows else {"id": raw_id}

    return {"id": raw_id}


def build_enrichment_prompt_hint(entity_type: str, entity_context: dict, field_name: str) -> str:
    """Generate a hint about what enrichment task this training example came from."""
    if entity_type == "drug":
        name = entity_context.get("name") or entity_context.get("id", "unknown")
        stage = entity_context.get("stage", "unknown stage")
        return (f"Enrich {field_name} for {name} ({stage}) — "
                f"target: {entity_context.get('target', '?')}, "
                f"company: {entity_context.get('company_id', '?')}")
    elif entity_type == "partnership":
        return (f"Verify {field_name} for partnership "
                f"{entity_context.get('company_id', '?')} ↔ "
                f"{entity_context.get('partner_company_id', '?')}")
    elif entity_type == "deal":
        return f"Verify {field_name} for deal: {entity_context.get('headline', '?')[:80]}"
    return f"Enrich {field_name} for {entity_type} {entity_context.get('id', '?')}"


def detect_value_drift(entity_type: str, entity_context: dict,
                        field_name: str, confirmed_value: str) -> dict:
    """Check if current DB value matches the confirmed value."""
    current_value = str(entity_context.get(field_name) or "")
    confirmed_clean = str(confirmed_value or "").strip()
    current_clean = current_value.strip()

    if not confirmed_clean:
        return {"status": "no_confirmed_value"}
    if not current_clean:
        return {"status": "current_empty", "drift": True}
    if current_clean == confirmed_clean:
        return {"status": "match"}
    # Check for approximate match (confirmed value is substring of current or vice versa)
    if confirmed_clean[:50] in current_clean or current_clean[:50] in confirmed_clean:
        return {"status": "partial_match"}
    return {"status": "drifted", "drift": True,
            "confirmed_preview": confirmed_clean[:100],
            "current_preview": current_clean[:100]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    parser.add_argument("--entity-type", default=None)
    parser.add_argument("--drift-only", action="store_true",
                        help="Only output records where value has drifted from confirmed")
    args = parser.parse_args()

    output_path = args.output or os.path.join(
        _REPO, f"output/fine_tune_signal_{datetime.date.today()}.jsonl")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Fetch all kyle_reviews with fine_tune_use=True
    params = {"fine_tune_use": "eq.true", "select": "*"}
    if args.entity_type:
        params["entity_type"] = f"eq.{args.entity_type}"

    reviews = sb_get("kyle_reviews", params, limit=500)
    print(f"Found {len(reviews)} kyle_reviews with fine_tune_use=True")

    records = []
    drift_count = 0

    for rev in reviews:
        entity_type = rev.get("entity_type", "unknown")
        entity_id   = rev.get("entity_id", "")
        field_name  = rev.get("field_name", "")
        field_value = rev.get("field_value", "")
        action      = rev.get("action", "")
        notes       = rev.get("notes", "")
        session_id  = rev.get("session_id", "")

        # Resolve entity for context
        context = resolve_entity(entity_type, entity_id)
        prompt_hint = build_enrichment_prompt_hint(entity_type, context, field_name)
        drift = detect_value_drift(entity_type, context, field_name, field_value)

        if drift.get("drift"):
            drift_count += 1

        record = {
            "entity_type":          entity_type,
            "entity_id":            entity_id,
            "field_name":           field_name,
            "confirmed_value":      field_value,
            "quality_signal":       action,
            "enrichment_prompt_hint": prompt_hint,
            "entity_context":       context,
            "drift_check":          drift,
            "notes":                notes,
            "session_id":           session_id,
            "reviewed_at":          rev.get("reviewed_at"),
        }

        if args.drift_only and not drift.get("drift"):
            continue

        records.append(record)

    # Write output
    with open(output_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    print(f"\nWrote {len(records)} training examples to: {output_path}")
    print(f"Drift detected: {drift_count}/{len(reviews)} records")

    # Summary stats
    from collections import Counter
    by_type   = Counter(r["entity_type"] for r in records)
    by_field  = Counter(r["field_name"] for r in records)
    by_drift  = Counter(r["drift_check"]["status"] for r in records)

    print(f"\nBy entity_type: {dict(by_type)}")
    print(f"Top fields: {dict(by_field.most_common(10))}")
    print(f"Drift status: {dict(by_drift)}")
    print(f"\nPhase 2 TODO: build negative examples + prompt→response format for LLM fine-tuning")


if __name__ == "__main__":
    main()
