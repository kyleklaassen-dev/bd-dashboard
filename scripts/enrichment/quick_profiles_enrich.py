#!/usr/bin/env python3
"""
quick_profiles_enrich.py — Lightweight company_profiles updater.

Purpose: Enrich company_profiles (platform_summary, bd_summary, key_risk,
         why_it_matters, vs_ailux) for companies where no enrichment exists yet,
         without the full company_enrichment.py overhead.

Context passed to Claude:
  - Drug records (name, target, stage, overlap, drug_summary)
  - Deal records (partner, type, value)
  NO trials, NO catalysts, NO intel items → prompt stays ~3-4k tokens.

Typical runtime: ~10-15s per company×area (Haiku synthesis).

Usage:
  python3 quick_profiles_enrich.py --area tslp --company regeneron
  python3 quick_profiles_enrich.py --area il4ra --company regeneron
  python3 quick_profiles_enrich.py --area tslp --company lilly
"""

import os
import json
import argparse

from _common import load_credentials
import _db
import ai.client as ai_client
from ai.client import PromptConfig

_url, _key, _ak = load_credentials()
_db.init_db(_url, _key)
ai_client.setup(_ak)

NOW_ISO = _db.now_iso() + "Z"

SYSTEM = (
    "You are a pharmaceutical business development analyst. "
    "You produce concise, accurate intelligence summaries for a BD platform. "
    "Respond ONLY with valid JSON — no markdown fences, no preamble."
)

_PROFILES_CFG = PromptConfig(
    name="quick_profiles",
    system=SYSTEM,
    model="claude-haiku-4-5-20251001",
    max_tokens=2048,
)


def build_prompt(company_id: str, area_id: str,
                 drugs: list, deals: list,
                 existing: dict | None) -> str:

    drug_lines = []
    for d in drugs:
        parts = [
            d.get("display_name") or d.get("id", "?"),
            f"target={d.get('target', '?')}",
            f"stage={d.get('stage', '?')}",
            f"overlap={d.get('overlap', '?')}",
        ]
        summ = d.get("drug_summary", "")
        if summ:
            parts.append(f"summary={summ[:200]}")
        drug_lines.append(" | ".join(parts))

    deal_lines = []
    for d in deals:
        partner = d.get("to_company") or d.get("from_company") or "?"
        val = ""
        if d.get("upfront_usd_m"):
            val = f"${d['upfront_usd_m']}M upfront"
        elif d.get("total_usd_m"):
            val = f"${d['total_usd_m']}M total"
        parts = [
            partner,
            d.get("deal_type", "?"),
            val,
            d.get("headline", "")[:150],
        ]
        deal_lines.append(" | ".join(p for p in parts if p))

    existing_note = ""
    if existing and existing.get("platform_summary"):
        existing_note = (
            f"\nExisting summary (update/improve if needed):\n"
            f"  platform: {existing.get('platform_summary', '')[:300]}\n"
            f"  bd: {existing.get('bd_summary', '')[:200]}"
        )

    prompt = f"""Company: {company_id}
Disease area: {area_id}

Drugs in this area ({len(drugs)}):
{chr(10).join("  " + l for l in drug_lines) if drug_lines else "  (none)"}

Recent deals ({len(deals)}):
{chr(10).join("  " + l for l in deal_lines) if deal_lines else "  (none)"}
{existing_note}

Produce a JSON object with these exact keys — keep each field concise (1-3 sentences):
{{
  "platform_summary": "What this company is doing in the {area_id} space — key drugs, mechanisms, differentiation",
  "bd_summary": "BD angle — licensing activity, partnership patterns, deal history, openness to collaboration",
  "key_risk": "Main risk or concern for this area — competitive, clinical, regulatory, or strategic",
  "why_it_matters": "Why Ailux should pay attention — strategic importance for BD scouting",
  "vs_ailux": "How this company's {area_id} program relates to or competes with Ailux's own position"
}}

IMPORTANT:
- Use only facts from the data provided above + your training knowledge about this company.
- Never fabricate trial IDs, deal values, or partner names.
- If you are uncertain about a fact, omit it rather than guess.
- Return valid JSON only. No markdown. No extra keys.
"""
    return prompt


def enrich(company_id: str, area_id: str, dry_run: bool = False):
    print(f"[quick_profiles_enrich] {company_id} / {area_id}")

    # 1. Fetch drugs in this area for this company
    drug_area_rows = _db.sb_get("drug_areas", {
        "area_id": f"eq.{area_id}",
        "select":  "drug_id",
    })
    drug_ids = [r["drug_id"] for r in drug_area_rows]

    drugs = []
    if drug_ids:
        chunk_ids = "(" + ",".join(drug_ids) + ")"
        drugs = _db.sb_get("drugs", {
            "company_id": f"eq.{company_id}",
            "id":         f"in.{chunk_ids}",
            "select":     "id,display_name,target,stage,overlap,drug_summary,overlap_rationale",
        })

    # 2. Fetch deals for this company×area
    deals = _db.sb_get("deals", {
        "company_id": f"eq.{company_id}",
        "area_id":    f"eq.{area_id}",
        "select":     "from_company,to_company,deal_type,upfront_usd_m,total_usd_m,headline",
        "limit":      "10",
    })

    # 3. Fetch existing profile (if any)
    existing_rows = _db.sb_get("company_profiles", {
        "company_id": f"eq.{company_id}",
        "area_id":    f"eq.{area_id}",
        "select":     "platform_summary,bd_summary,key_risk,why_it_matters,vs_ailux",
    })
    existing = existing_rows[0] if existing_rows else None

    print(f"  {len(drugs)} drugs | {len(deals)} deals | existing={'yes' if existing else 'no'}")

    # 4. Build prompt and call Claude
    prompt = build_prompt(company_id, area_id, drugs, deals, existing)
    print(f"  Prompt: ~{len(prompt.split())} words → calling claude-haiku-4-5-20251001")

    result = ai_client.run_json(_PROFILES_CFG, prompt)
    if not result.ok:
        print(f"  ✗ LLM call or JSON parse failed")
        return False

    data = result.data
    cost = result.cost_usd
    print(f"  {result.tokens_in}in / {result.tokens_out}out "
          f"(${cost:.4f}) stop={result.stop_reason}")

    print(f"  Keys: {list(data.keys())}")

    if dry_run:
        print("  [dry-run] Would write:")
        for k, v in data.items():
            print(f"    {k}: {str(v)[:120]}")
        return True

    # 5. Guard E3: company_areas must exist before company_profiles
    _db.sb_upsert("company_areas", {"company_id": company_id, "area_id": area_id})
    print(f"  [E3 guard] company_areas ensured: {company_id} → {area_id}")

    # 6. Upsert into company_profiles
    record = {
        "company_id":         company_id,
        "area_id":            area_id,
        "platform_summary":   data.get("platform_summary", ""),
        "bd_summary":         data.get("bd_summary", ""),
        "key_risk":           data.get("key_risk", ""),
        "why_it_matters":     data.get("why_it_matters", ""),
        "vs_ailux":           data.get("vs_ailux", ""),
        "last_enriched_at":   NOW_ISO,
        "last_enriched_model": "claude-haiku-4-5-20251001",
        "updated_at":         NOW_ISO,
    }

    rows = _db.sb_upsert("company_profiles", record)
    ok = bool(rows)
    if ok:
        print(f"  ✓ company_profiles upserted for {company_id}/{area_id}")
    else:
        print(f"  ✗ upsert failed")

    return ok


def main():
    parser = argparse.ArgumentParser(
        description="Lightweight company_profiles enricher — no trial/intel overhead"
    )
    parser.add_argument("--area",    required=True, help="Disease area ID (e.g. tslp, il4ra)")
    parser.add_argument("--company", required=True, help="Company ID (exact match)")
    parser.add_argument("--dry-run", action="store_true", help="No Supabase writes")
    args = parser.parse_args()

    ok = enrich(args.company, args.area, dry_run=args.dry_run)
    print("Done." if ok else "FAILED.")


if __name__ == "__main__":
    main()
