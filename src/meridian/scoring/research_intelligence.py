"""
research_intelligence.py — BD Platform Intelligence Layer
==========================================================

PURPOSE
-------
This module turns the BD platform from a passive database into a guided
research system. For every Strategic Competitive Entity it answers:
  • What do we know?          → score_entity_completeness()
  • What is missing?          → missing_fields / missing_stages in score result
  • What changed?             → check_research_triggers()
  • What should happen next?  → get_next_best_action()
  • Why does this matter?     → priority_score + strategic_importance

ARCHITECTURE
------------
  load_entity_context()          — pull all data for one entity from Supabase
                                    (trials + deals fetched by drug_id AND canonical_drug_id)
  _group_drugs_by_canonical()    — group drug rows by canonical_drug_id for unified scoring
  _merge_drug_rows()             — merge sibling drug rows into one best-values representative
  score_entity_completeness()    — 0–100 score across 6 weighted research stages
                                    (Stages 2 + 3 score per canonical program, not per DB row)
  get_next_best_action()         — priority-ordered decision tree → plain-English action
  check_research_triggers()      — detect conditions that require downstream updates
  calculate_priority_score()     — urgency integer (0–200) with human reason
  upsert_research_queue()        — write result to research_queue + stamp drugs rows
  run_intelligence_audit()       — main entry point; loops all entities for an area

STAGE WEIGHTS (must sum to 100)
  Stage 1 — Entity Discovery          10
  Stage 2 — Drug Mapping              15
  Stage 3 — Trial Intelligence        20
  Stage 4 — Catalyst Engine           15
  Stage 5 — Strategic Positioning     25
  Stage 6 — Deal Intelligence         15

COMPLETENESS TIERS
  thin    → score <  40  (entity barely started)
  partial → score 40–69  (entity in progress)
  strong  → score >= 70  (entity well-researched)

USAGE
-----
  python scripts/research_intelligence.py --area tl1a
  python scripts/research_intelligence.py --area tl1a --entity ailux
  python scripts/research_intelligence.py --area all
  python scripts/research_intelligence.py --area tl1a --dry-run

DEPENDENCIES
------------
  pip install requests
  Env:  SUPABASE_URL, SUPABASE_SERVICE_KEY
  OR:   .supabase_service_key file in working directory (runtime fallback)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import requests


# ── §3 SPLIT — base + feature modules now in meridian.scoring.research_intel.* ──
from meridian.scoring.research_intel.common import (
    _get_supabase_creds, _sb_get, _sb_patch, _group_drugs_by_canonical, _merge_drug_rows, ALL_AREAS,
)
from meridian.scoring.research_intel.context import load_entity_context
from meridian.scoring.research_intel.scoring import score_entity_completeness
from meridian.scoring.research_intel.triggers import get_next_best_action, check_research_triggers
from meridian.scoring.research_intel.queue import calculate_priority_score, upsert_research_queue


# ──────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

def run_intelligence_audit(
    area_id: str,
    entity_filter: str | None = None,
    dry_run: bool = False,
) -> None:
    """
    Run the full intelligence audit for one area.

    For each entity in the area:
      1. Load context from Supabase
      2. Score completeness
      3. Detect triggers
      4. Determine next best action
      5. Calculate priority score
      6. Upsert research_queue + stamp drugs

    Prints a summary table on completion.
    """
    sb_url, sb_key = _get_supabase_creds()

    print(f"\n{'═'*60}")
    print(f"  Intelligence Audit — area: {area_id}")
    if dry_run:
        print("  DRY RUN — no writes to Supabase")
    print(f"{'═'*60}")

    # Discover all drug_ids for this area via the drug_areas junction table
    area_rows = _sb_get(sb_url, sb_key, "drug_areas", {
        "area_id": f"eq.{area_id}",
        "select": "drug_id",
    })
    if not area_rows:
        print("  No drug_areas rows found for this area.")
        return

    area_drug_ids = [r["drug_id"] for r in area_rows]
    drug_id_filter = "in.(" + ",".join(area_drug_ids) + ")"

    params: dict = {
        "id": drug_id_filter,
        "select": "entity_id,id,name,company_id",
    }
    if entity_filter:
        params["entity_id"] = f"ilike.%{entity_filter}%"

    all_drugs = _sb_get(sb_url, sb_key, "drugs", params)

    # Group by entity_id; entities without entity_id get a fallback key
    entity_map: dict[str, list] = {}
    for d in all_drugs:
        # drugs table uses 'id' as primary key, not 'drug_id'
        eid = d.get("entity_id") or f"__no_entity__{d['id']}"
        entity_map.setdefault(eid, []).append(d)

    if not entity_map:
        print("  No entities found for this area.")
        return

    print(f"  Entities to audit: {len(entity_map)}\n")

    results = []
    for entity_id, entity_drugs in entity_map.items():
        real_entity_id = entity_id if not entity_id.startswith("__no_entity__") else entity_drugs[0]["id"]
        drug_names = ", ".join(d.get("name", "?") for d in entity_drugs[:2])
        print(f"  ── {real_entity_id} ({drug_names})")

        try:
            ctx = load_entity_context(real_entity_id, area_id, sb_url, sb_key)

            score_result = score_entity_completeness(ctx)
            triggers = check_research_triggers(ctx)
            next_action = get_next_best_action(ctx, score_result)
            priority_score, reason = calculate_priority_score(ctx, score_result, triggers)

            upsert_research_queue(
                ctx=ctx,
                score_result=score_result,
                triggers=triggers,
                next_action=next_action,
                priority_score=priority_score,
                reason=reason,
                dry_run=dry_run,
                sb_url=sb_url,
                sb_key=sb_key,
            )

            results.append({
                "entity_id": real_entity_id,
                "score": score_result["completeness_score"],
                "tier": score_result["completeness_tier"],
                "priority": priority_score,
                "triggers": len(triggers),
                "action": next_action[:60],
            })

            print(
                f"     score={score_result['completeness_score']:3d} "
                f"tier={score_result['completeness_tier']:<8s} "
                f"priority={priority_score:3d} "
                f"triggers={len(triggers)} "
                f"→ {next_action[:55]}"
            )

        except Exception as e:
            print(f"     ERROR: {e}")
            results.append({"entity_id": real_entity_id, "error": str(e)})

    # Summary
    scored = [r for r in results if "score" in r]
    print(f"\n{'─'*60}")
    print(f"  Audit complete. {len(scored)}/{len(results)} entities scored.")
    if scored:
        avg = sum(r["score"] for r in scored) / len(scored)
        top = sorted(scored, key=lambda r: r["priority"], reverse=True)[:3]
        print(f"  Average completeness: {avg:.1f}")
        print(f"  Top priorities:")
        for r in top:
            print(f"    [{r['priority']:3d}] {r['entity_id']} — {r['action']}")
    print(f"{'═'*60}\n")


def rescore_molecule(
    drug_id: str,
    area_id: str,
    dry_run: bool = False,
) -> None:
    """
    Re-score completeness for the company that owns drug_id in area_id.

    Called after manual curation of molecule_intelligence to ensure:
      - company_profiles.completeness_score reflects the updated molecule data
      - company_profiles.missing_fields drops any molecule fields now populated
      - research_queue entry is updated (priority_score + next_best_action)

    Does NOT re-run Claude enrichment. Only re-reads the current DB state
    and recalculates scores.
    """
    sb_url, sb_key = _get_supabase_creds()

    print(f"\n{'═'*60}")
    print(f"  Rescore Molecule — drug: {drug_id} / area: {area_id}")
    if dry_run:
        print("  DRY RUN — no writes to Supabase")
    print(f"{'═'*60}")

    # 1. Find which company owns this drug in this area
    drug_rows = _sb_get(sb_url, sb_key, "drugs", {
        "id": f"eq.{drug_id}",
        "select": "id,name,company_id,entity_id,stage,canonical_drug_id",
    })
    if not drug_rows:
        print(f"  ✗ Drug '{drug_id}' not found in drugs table.")
        return
    drug = drug_rows[0]
    company_id = drug.get("company_id") or drug.get("entity_id") or drug_id
    entity_id  = drug.get("entity_id") or company_id
    print(f"  Drug: {drug['name']} | Company: {company_id} | Entity: {entity_id}")

    # 2. Load full entity context (same as run_intelligence_audit)
    ctx = load_entity_context(
        entity_id=entity_id,
        area_id=area_id,
        sb_url=sb_url,
        sb_key=sb_key,
    )
    if not ctx:
        print(f"  ✗ Could not load context for entity '{entity_id}'")
        return

    # 3. Load current molecule_intelligence for this drug (post-curation state)
    mol_rows = _sb_get(sb_url, sb_key, "molecule_intelligence", {
        "drug_id": f"eq.{drug_id}",
        "select": "*",
    })
    mol = mol_rows[0] if mol_rows else {}

    # Inject current molecule data into ctx so scoring sees it
    # Build a synthetic molecule_updates entry from the current DB row
    if mol:
        ctx["molecule_intelligence"] = mol
        print(f"  Molecule row found: format={mol.get('format')} "
              f"modality={mol.get('modality')} "
              f"field_status={mol.get('field_status')}")
    else:
        print(f"  No molecule_intelligence row found for {drug_id}")

    # 4. Score completeness using existing scoring infrastructure
    score_result = score_entity_completeness(ctx)
    completeness_score = score_result.get("completeness_score", 0)
    completeness_tier  = score_result.get("completeness_tier", "thin")
    missing_fields     = score_result.get("missing_fields") or []
    next_action        = get_next_best_action(ctx, score_result)

    # Add molecule-specific missing fields to the list
    MOL_REQUIRED = ["format", "modality", "differentiation_claim"]
    MOL_DESIRED  = ["epitope", "affinity_kd", "fc_engineering", "lowest_active_dose"]
    field_status = mol.get("field_status") or {}
    for field in MOL_REQUIRED:
        val = mol.get(field) or ""
        if not val or not str(val).strip():
            mf = f"molecule_intelligence.{field}[{drug_id}]"
            if mf not in missing_fields:
                missing_fields.append(mf)
    for field in MOL_DESIRED:
        if field_status.get(field) == "unknown" or (field not in field_status and not mol.get(field)):
            mf = f"molecule_intelligence.{field}[{drug_id}]"
            if mf not in missing_fields:
                missing_fields.append(mf)

    print(f"  Score: {completeness_score}/100 ({completeness_tier}) | "
          f"{len(missing_fields)} missing field(s)")
    if missing_fields:
        mol_missing = [f for f in missing_fields if "molecule_intelligence" in f]
        other_missing = [f for f in missing_fields if "molecule_intelligence" not in f]
        if mol_missing:
            print(f"  Molecule gaps: {mol_missing}")
        if other_missing:
            print(f"  Other gaps:   {other_missing[:5]}")
    print(f"  Next action: {next_action}")

    if dry_run:
        print("  [dry-run] No writes.")
        return

    # 5. Patch company_profiles
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    profile_patch = {
        "completeness_score":      completeness_score,
        "missing_fields":          missing_fields,
        "completeness_checked_at": now_iso,
    }
    # Find the company_profiles row for this entity × area
    cp_rows = _sb_get(sb_url, sb_key, "company_profiles", {
        "company_id": f"eq.{company_id}",
        "area_id":    f"eq.{area_id}",
        "select":     "company_id",
    })
    if cp_rows:
        _sb_patch(sb_url, sb_key, "company_profiles",
                  {"company_id": company_id, "area_id": area_id},
                  profile_patch)
        print(f"  ✓ company_profiles updated: score={completeness_score} "
              f"missing={len(missing_fields)}")
    else:
        print(f"  ⚠ No company_profiles row for {company_id}/{area_id} — skipping patch")

    # 6. Update research_queue
    priority_score = int(completeness_score * 0.6 + (
        30 if completeness_tier == "thin" else (20 if completeness_tier == "partial" else 10)
    ))
    rq_rows = _sb_get(sb_url, sb_key, "research_queue", {
        "entity_id": f"eq.{entity_id}",
        "area_id":   f"eq.{area_id}",
        "select":    "entity_id",
    })
    rq_patch = {
        "priority_score":        priority_score,
        "completeness_score":    completeness_score,
        "completeness_tier":     completeness_tier,
        "next_best_action":      next_action,
        "missing_fields":        missing_fields,
    }
    if rq_rows:
        _sb_patch(sb_url, sb_key, "research_queue",
                  {"entity_id": entity_id, "area_id": area_id},
                  rq_patch)
        print(f"  ✓ research_queue updated: priority={priority_score}")
    else:
        print(f"  ⚠ No research_queue row for {entity_id}/{area_id} — not updated")

    print(f"{'═'*60}\n")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="BD Platform — Research Intelligence Audit"
    )
    parser.add_argument(
        "--area",
        default="",
        help="Disease area to audit (tl1a | tslp | il4ra | fcrn | igf1r | tcell | all). "
             "Required for audit mode; optional for --rescore-molecule if area can be inferred.",
    )
    parser.add_argument(
        "--entity",
        default="",
        help="Optional: filter by entity_id substring",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and score but do not write to Supabase",
    )
    parser.add_argument(
        "--rescore-molecule",
        default="",
        metavar="DRUG_ID",
        help="Re-score completeness for the company owning DRUG_ID after manual curation. "
             "Updates company_profiles.completeness_score and research_queue. "
             "Requires --area. Example: --rescore-molecule tulisokibart --area tl1a",
    )
    args = parser.parse_args()

    if args.rescore_molecule:
        # Rescore a single molecule after manual curation
        if not args.area:
            print("ERROR: --area is required with --rescore-molecule")
            sys.exit(1)
        rescore_molecule(
            drug_id=args.rescore_molecule,
            area_id=args.area,
            dry_run=args.dry_run,
        )
    else:
        # Standard intelligence audit
        if not args.area:
            print("ERROR: --area is required for audit mode")
            sys.exit(1)
        areas = ALL_AREAS if args.area == "all" else [args.area]
        for area in areas:
            run_intelligence_audit(
                area_id=area,
                entity_filter=args.entity or None,
                dry_run=args.dry_run,
            )

    sys.exit(0)
