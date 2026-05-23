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
import datetime
import urllib.request
import urllib.parse

import anthropic

# ── Credentials ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SUPABASE_URL      = os.environ["SUPABASE_URL"]
SUPABASE_KEY      = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

NOW_ISO = datetime.datetime.utcnow().isoformat() + "Z"

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}


# ── Supabase helpers ──────────────────────────────────────────────────────────

def sb_get(table: str, params: dict) -> list:
    qs = urllib.parse.urlencode(params)
    url = f"{SUPABASE_URL}/rest/v1/{table}?{qs}"
    req = urllib.request.Request(url, headers=SB_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def sb_upsert(table: str, record: dict) -> bool:
    """Insert or update via POST with on-conflict merge."""
    headers = {**SB_HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"}
    body = json.dumps(record).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status in (200, 201)
    except urllib.error.HTTPError as e:
        print(f"  [sb_upsert {table}] {e.code}: {e.read().decode()[:200]}")
        return False


# ── Prompt ────────────────────────────────────────────────────────────────────

SYSTEM = (
    "You are a pharmaceutical business development analyst. "
    "You produce concise, accurate intelligence summaries for a BD platform. "
    "Respond ONLY with valid JSON — no markdown fences, no preamble."
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


# ── Main ──────────────────────────────────────────────────────────────────────

def enrich(company_id: str, area_id: str, dry_run: bool = False):
    print(f"[quick_profiles_enrich] {company_id} / {area_id}")

    # 1. Fetch drugs in this area for this company
    drug_area_rows = sb_get("drug_areas", {
        "area_id": f"eq.{area_id}",
        "select":  "drug_id",
    })
    drug_ids = [r["drug_id"] for r in drug_area_rows]

    drugs = []
    if drug_ids:
        chunk_ids = "(" + ",".join(drug_ids) + ")"
        all_drugs = sb_get("drugs", {
            "company_id": f"eq.{company_id}",
            "id":         f"in.{chunk_ids}",
            "select":     "id,display_name,target,stage,overlap,drug_summary,overlap_rationale",
        })
        drugs = all_drugs

    # 2. Fetch deals for this company×area
    deals = sb_get("deals", {
        "company_id": f"eq.{company_id}",
        "area_id":    f"eq.{area_id}",
        "select":     "from_company,to_company,deal_type,upfront_usd_m,total_usd_m,headline",
        "limit":      "10",
    })

    # 3. Fetch existing profile (if any)
    existing_rows = sb_get("company_profiles", {
        "company_id": f"eq.{company_id}",
        "area_id":    f"eq.{area_id}",
        "select":     "platform_summary,bd_summary,key_risk,why_it_matters,vs_ailux",
    })
    existing = existing_rows[0] if existing_rows else None

    print(f"  {len(drugs)} drugs | {len(deals)} deals | existing={'yes' if existing else 'no'}")

    # 4. Build prompt and call Claude
    prompt = build_prompt(company_id, area_id, drugs, deals, existing)
    print(f"  Prompt: ~{len(prompt.split())} words → calling claude-haiku-4-5-20251001")

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )
    text = resp.content[0].text.strip()
    cost = (resp.usage.input_tokens / 1e6 * 0.8 +
            resp.usage.output_tokens / 1e6 * 4.0)
    print(f"  {resp.usage.input_tokens}in / {resp.usage.output_tokens}out "
          f"(${cost:.4f}) stop={resp.stop_reason}")

    # 5. Parse response
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        # Try stripping markdown fences
        cleaned = text
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        try:
            data = json.loads(cleaned.strip())
        except Exception:
            print(f"  Parse error: {e}")
            print(f"  Raw: {text[:300]}")
            return False

    print(f"  Keys: {list(data.keys())}")

    if dry_run:
        print("  [dry-run] Would write:")
        for k, v in data.items():
            print(f"    {k}: {str(v)[:120]}")
        return True

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

    ok = sb_upsert("company_profiles", record)
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
