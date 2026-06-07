#!/usr/bin/env python3
"""
backfill_bd_angle.py
Fills company_profiles.bd_angle for rows where it is NULL.

All 78 missing profiles already have key_risk + why_it_matters populated,
so this script uses those fields + the company's drugs in the area as context
to generate a focused bd_angle paragraph via Claude.

bd_angle format (from populated examples):
  2-3 sentences. The primary BD opportunity or strategy for Ailux relative to
  this company×area combination — licensing window, partner potential, acquirer
  signal, pricing benchmark, or competitive threat framing. Specific, not generic.

Usage:
  python3 scripts/backfill_bd_angle.py            # all 78 missing
  python3 scripts/backfill_bd_angle.py --limit 10  # first 10
  python3 scripts/backfill_bd_angle.py --dry-run   # print without writing
"""

import os, sys, json, time, argparse, re
from typing import Optional

from _common import load_credentials
import _db
import ai.client as ai_client
from ai.client import PromptConfig

_url, _key, _ak = load_credentials()
_db.init_db(_url, _key)
ai_client.setup(_ak)

NOW = _db.now_iso()

AREA_LABELS = {
    "ibd":         "IBD (UC/CD)",
    "tl1a":        "TL1A (IBD)",
    "atopy":       "Atopy (AD/asthma)",
    "il4ra":       "IL-4Rα (atopy)",
    "tslp":        "TSLP (respiratory/atopy)",
    "respiratory": "Respiratory (COPD/asthma/IPF)",
    "fcrn":        "FcRn (autoantibody diseases)",
    "autoimmune":  "Autoimmune (B cell / TCE platform)",
    "tcell":       "T cell engager (autoimmune/oncology)",
    "igf1r":       "IGF-1R (TED)",
    "ted":         "Thyroid Eye Disease (TED)",
}

AILUX_CONTEXT = """Ailux Biotherapeutics is developing ALX001 (TL1A×IL-23p19 bispecific, preclinical/IND-enabling),
ALX002 (CD19×BCMA T cell engager, preclinical), and ALX005 (FcRn×Albumin bispecific, preclinical).
Primary focus: IBD (UC/CD) with ALX001. Chinese biotech, Shanghai R&D.
BD objective: identify partners, acquirers, licensing benchmarks, and competitive windows."""

_BD_ANGLE_CFG = PromptConfig(
    name="bd_angle",
    system="",
    model="claude-sonnet-4-6",
    max_tokens=300,
)


def get_company_drugs(company_id: str, area_id: str) -> list:
    """Get drugs for this company in this area via drug_competitive_scores."""
    dcs_rows = _db.sb_get("drug_competitive_scores", {
        "context_id": f"eq.{area_id}",
        "select": "drug_id",
        "limit": "20",
    })
    drug_ids = [r["drug_id"] for r in dcs_rows]
    if not drug_ids:
        return []

    drugs = _db.sb_get("drugs", {
        "company_id": f"eq.{company_id}",
        "select": "id,name,stage,target,mechanism,overlap,indication_short",
        "limit": "15",
    })
    return drugs


def generate_bd_angle(company_id: str, area_id: str, profile: dict, drugs: list) -> Optional[str]:
    area_label = AREA_LABELS.get(area_id, area_id)
    key_risk = profile.get("key_risk") or ""
    why_it_matters = profile.get("why_it_matters") or ""

    drug_lines = []
    for d in drugs[:8]:
        line = f"  - {d.get('name','?')} ({d.get('stage','?')}): target={d.get('target','?')}, overlap={d.get('overlap','?')}"
        if d.get("indication_short"):
            line += f", indication={d['indication_short']}"
        drug_lines.append(line)
    drugs_block = "\n".join(drug_lines) if drug_lines else "  (no drugs in DB for this company×area)"

    prompt = f"""You are writing a bd_angle field for the Meridian BD intelligence platform used by Ailux Biotherapeutics.

Ailux context: {AILUX_CONTEXT}

Company: {company_id}
Disease area: {area_label}

Company's drugs in this area:
{drugs_block}

Existing profile context:
  key_risk: {key_risk[:300]}
  why_it_matters: {why_it_matters[:300]}

Write a bd_angle paragraph (2-4 sentences) that answers:
"What is the primary BD opportunity or strategic consideration for Ailux relative to {company_id} in {area_label}?"

This should be one of:
- A licensing window (when/why Ailux could license from or to this company)
- A partner/acquirer signal (why this company might want to partner with or acquire Ailux)
- A pricing/valuation benchmark (what deal benchmarks this company sets)
- A competitive threat framing (how Ailux should position vs. this company's program)
- A geographic or platform synergy angle

Be specific. Use the drug data and risk/why_it_matters context. No generic statements.
Return ONLY the bd_angle text — no JSON, no labels, no markdown. Plain prose, 2-4 sentences."""

    try:
        text = ai_client.run_text(_BD_ANGLE_CFG, prompt)
        text = text.strip()
        if text.startswith("{") or len(text) < 30:
            return None
        return text
    except Exception as e:
        print(f"  [Claude error] {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Backfill company_profiles.bd_angle")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--area", help="Limit to one area_id")
    args = parser.parse_args()

    params = {
        "bd_angle": "is.null",
        "select": "company_id,area_id,key_risk,why_it_matters",
        "order": "area_id.asc,company_id.asc",
        "limit": str(args.limit),
    }
    if args.area:
        params["area_id"] = f"eq.{args.area}"

    profiles = _db.sb_get("company_profiles", params)
    print(f"\nFound {len(profiles)} profiles with null bd_angle (limit={args.limit})")
    if args.dry_run:
        print("DRY RUN — no writes\n")

    success = 0
    for i, profile in enumerate(profiles, 1):
        company_id = profile["company_id"]
        area_id    = profile["area_id"]
        print(f"\n[{i}/{len(profiles)}] {company_id} / {area_id}")

        drugs = get_company_drugs(company_id, area_id)
        print(f"  drugs: {len(drugs)} found")

        bd_angle = generate_bd_angle(company_id, area_id, profile, drugs)
        if not bd_angle:
            print("  ✗ no output generated")
            time.sleep(1)
            continue

        print(f"  bd_angle: {bd_angle[:120]}...")

        if not args.dry_run:
            ok = _db.sb_patch(
                "company_profiles",
                {"bd_angle": bd_angle, "updated_at": NOW},
                {"company_id": f"eq.{company_id}", "area_id": f"eq.{area_id}"},
            )
            print(f"  {'✓ written' if ok else '✗ write failed'}")
            if ok:
                success += 1
        else:
            success += 1

        time.sleep(1.5)  # rate limit

    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Done: {success}/{len(profiles)} bd_angles {'generated' if args.dry_run else 'written'}")


if __name__ == "__main__":
    main()
