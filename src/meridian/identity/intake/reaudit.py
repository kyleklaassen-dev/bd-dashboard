#!/usr/bin/env python3
"""
intake/reaudit.py — Pipeline re-audit half of the Company-First Discovery Engine (§3 split).

Extracted verbatim from company_intake.py: research a *known* company's live
pipeline and diff it against the DB, pushing any drugs found live but absent
from Meridian into discovery_queue with source='re_audit' for human review.

Public entrypoint: run_reaudit() (called by company_intake's CLI --re-audit).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import requests

from meridian.identity.intake.common import SUPABASE_URL, _sb_headers, ACTIVE_AREAS
from meridian.identity.intake.research import (
    resolve_identity, research_company, get_relevant_areas,
)


def _get_db_drugs_for_company(company_id: str) -> list[str]:
    """
    Return normalised drug name tokens for all drugs owned or originated by company_id.
    Checks both company_id column and current_owner_company_id (for acquired companies).
    """
    try:
        # Direct company_id
        r1 = requests.get(
            f"{SUPABASE_URL}/rest/v1/drugs",
            headers=_sb_headers,
            params={"company_id": f"eq.{company_id}", "select": "id,name,aliases", "limit": "200"},
            timeout=10,
        )
        # current_owner (acquired drugs)
        r2 = requests.get(
            f"{SUPABASE_URL}/rest/v1/drugs",
            headers=_sb_headers,
            params={"current_owner_company_id": f"eq.{company_id}", "select": "id,name,aliases", "limit": "200"},
            timeout=10,
        )
        rows = []
        if r1.status_code == 200:
            rows += r1.json()
        if r2.status_code == 200:
            rows += r2.json()

        # Deduplicate by id
        seen = set()
        unique = []
        for r in rows:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)

        # Build a flat set of tokens: drug_id + name words + aliases
        tokens = set()
        for row in unique:
            tokens.add(row["id"].lower())
            for word in row.get("name", "").lower().split():
                if len(word) >= 4:
                    tokens.add(word)
            for alias in (row.get("aliases") or []):
                tokens.add(alias.lower())
                # Also add the base identifier stripped of hyphens/dashes
                tokens.add(alias.lower().replace("-", "").replace(" ", ""))

        return list(tokens), unique
    except Exception as e:
        print(f"  ⚠️  Could not fetch DB drugs: {e}")
        return [], []


def _drug_already_in_db(drug_name: str, db_tokens: list[str]) -> bool:
    """
    Fuzzy match: is this pipeline drug already captured in the DB?
    Checks cleaned drug name against the flat token set.
    """
    name_clean = drug_name.lower().replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    name_words = [w for w in drug_name.lower().split() if len(w) >= 4]

    # Direct substring match on cleaned name
    for token in db_tokens:
        token_clean = token.replace("-", "").replace(" ", "")
        if name_clean == token_clean or name_clean in token_clean or token_clean in name_clean:
            return True

    # Word-level match (any long word in the drug name hits a DB token)
    for word in name_words:
        if word in db_tokens:
            return True

    return False


def run_reaudit(company_name: str, dry_run: bool = False, verbose: bool = False) -> None:
    """
    Re-audit mode: research a known company's pipeline and diff against DB.
    Any drugs found in the live research but absent from the DB are pushed to
    discovery_queue with source='re_audit' for human review.

    Usage:
        python -m meridian.identity.company_intake --company "UCB" --re-audit
        python -m meridian.identity.company_intake --company "Candid Therapeutics" --re-audit --dry-run
    """
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    slug = company_name.lower().replace(" ", "_").replace("&", "").replace("/", "_")
    run_id = f"reaudit_{slug}_{ts}"

    print()
    print(f"Pipeline Re-Audit — '{company_name}'")
    print(f"Run ID: {run_id}  |  dry_run={dry_run}")
    print("─" * 55)

    # ── Step 1: Resolve company identity ─────────────────────────────────────
    print("\n[1/4] Resolving company identity...")
    resolution = resolve_identity(company_name, dry_run=False)
    rtype = resolution["resolution_type"]

    if rtype not in ("resolved_existing", "alias_match"):
        print(f"  ❌ Company not found in Meridian (type={rtype}).")
        print(f"     Re-audit requires an existing company. Use --company with a known company_id.")
        print(f"     To add a new company, run without --re-audit.")
        return

    company_id = resolution["company_id"]
    print(f"  ✅ Resolved: {company_id}")

    # ── Step 2: Load existing DB drugs ───────────────────────────────────────
    print("\n[2/4] Loading existing DB drugs for this company...")
    db_tokens, db_drugs = _get_db_drugs_for_company(company_id)
    print(f"  DB drugs: {len(db_drugs)} rows ({len(db_tokens)} name tokens)")
    if verbose and db_drugs:
        for d in db_drugs:
            print(f"    • {d['id']:30} {d.get('name', '')}")

    # ── Step 3: Research live pipeline ───────────────────────────────────────
    print("\n[3/4] Researching live pipeline via Claude...")
    _active_model = os.environ.get("INTAKE_MODEL", "claude-sonnet-4-6")
    if not dry_run and "haiku" in _active_model.lower():
        print(f"  ❌ Model tier error: INTAKE_MODEL='{_active_model}' cannot be used for live writes.")
        print(f"     Set INTAKE_MODEL=claude-sonnet-4-6 for re-audit live runs.")
        return

    research = research_company(company_name, verbose=verbose)
    if not research:
        print("  ❌ Research failed.")
        return

    pipeline = research.get("pipeline", [])
    print(f"  Pipeline found: {len(pipeline)} drug(s)")
    if verbose:
        for d in pipeline:
            print(f"    • {d.get('drug_name', '?'):35} {d.get('stage', '?'):12} {d.get('target', '?')}")

    # ── Step 4: Diff and write gaps ───────────────────────────────────────────
    print("\n[4/4] Diffing pipeline against DB...")
    new_drugs  = []
    seen_drugs = []

    for drug in pipeline:
        drug_name = drug.get("drug_name", "")
        if not drug_name:
            continue
        if _drug_already_in_db(drug_name, db_tokens):
            seen_drugs.append(drug_name)
            print(f"  ✓  {drug_name} — already in DB")
        else:
            new_drugs.append(drug)
            print(f"  ✦  {drug_name} — NOT in DB  [{drug.get('stage','?')} | {drug.get('target','?')}]")

    print(f"\n  Summary: {len(seen_drugs)} already in DB, {len(new_drugs)} new gap(s) found")

    if not new_drugs:
        print("  ✅ No gaps — DB matches live pipeline.")
        return

    # Write new drugs to discovery_queue with source='re_audit'
    written = 0
    for drug in new_drugs:
        drug_name = drug.get("drug_name", "unknown")
        target    = drug.get("target", "")
        stage     = drug.get("stage", "")
        mechanism = drug.get("mechanism", "")

        # Score area relevance for this specific drug using its target/indication text
        drug_text = f"{target} {mechanism} {drug.get('indication', '')}".lower()

        relevant_areas = []
        for area_id, area_info in ACTIVE_AREAS.items():
            area_keywords = [k.lower() for k in area_info["keywords"]]
            if any(kw in drug_text for kw in area_keywords):
                relevant_areas.append(area_id)

        # If no keyword match, fall back to the company's existing areas
        if not relevant_areas:
            relevant_areas = [a["area_id"] for a in get_relevant_areas(research)][:2]

        for area_id in relevant_areas:
            row = {
                "company_name":            company_name,
                "company_id_suggested":    company_id,
                "drug_name":               drug_name,
                "target":                  target,
                "stage":                   stage,
                "modality":                drug.get("modality"),
                "entity_type":             "molecule",
                "area_id":                 area_id,
                "overlap":                 "Adjacent",
                "competition_layer":       2,
                "confidence_score":        70,
                "relevance_score":         5,
                "relevance_rationale":     f"Re-audit: '{drug_name}' found on live pipeline page but absent from Meridian DB.",
                "reason":                  f"Re-audit gap: {drug_name} ({stage}, {target}) — not in Meridian for {area_id}.",
                "source":                  "re_audit",
                "suggested_dest":          "update_company",
                "discovered_by":           "company_intake_reaudit",
                "status":                  "pending",
                "discovery_run_id":        run_id,
                "relationship_type":       "pipeline",
                "relationship_confidence": "medium",
                "why_discovered":          (
                    f"Re-audit of {company_name} pipeline: '{drug_name}' appears on live pipeline page "
                    f"but has no corresponding drugs row in Meridian. Stage: {stage}. Target: {target}. "
                    f"Mechanism: {mechanism}. Review and promote via drug_intake.py if confirmed."
                ),
            }

            if dry_run:
                print(f"  [DRY RUN] Would queue: {drug_name} → {area_id}")
                written += 1
                continue

            try:
                resp = requests.post(
                    f"{SUPABASE_URL}/rest/v1/discovery_queue",
                    headers=_sb_headers,
                    json=row,
                    timeout=10,
                )
                if resp.status_code in (200, 201):
                    print(f"  ✅ Queued: {drug_name} → {area_id} (re_audit)")
                    written += 1
                else:
                    print(f"  ⚠️  Queue write failed ({resp.status_code}): {resp.text[:200]}")
            except Exception as e:
                print(f"  ❌ Queue write error: {e}")

    print(f"\n{'[DRY RUN] Would write' if dry_run else 'Written'}: {written} discovery_queue row(s) (source=re_audit)")
    if not dry_run and written:
        print("  → Review in Meridian → Discovery Queue tab, filter source=re_audit.")
        print("  → Promote each gap via: python scripts/drug_intake.py --drug '<drug_name>' --company '<company>'")

