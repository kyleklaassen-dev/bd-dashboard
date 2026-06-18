#!/usr/bin/env python3
"""Entity-context loader (§3 research_intelligence split)."""

from __future__ import annotations

from typing import Any

from meridian.scoring.research_intel.common import _sb_get


# ──────────────────────────────────────────────────────────────────────────────
# STEP 0 — LOAD ENTITY CONTEXT
# ──────────────────────────────────────────────────────────────────────────────

def load_entity_context(
    entity_id: str,
    area_id: str,
    sb_url: str,
    sb_key: str,
) -> dict:
    """
    Load all research data for one entity from Supabase.

    Returns a context dict with keys:
      entity_id, area_id,
      drugs          — list of drug rows (drug_id, drug_name, stage, mechanism,
                        target, discovery_status, confidence_score,
                        differentiation_thesis, trial_data_status, vs_competitor,
                        results_summary, aliases, completeness_score, ...)
      trials         — list of trial rows joined through drugs
      catalysts      — list of catalyst rows for drugs in this entity
      company        — single company row (company_id, company_name, ...)
      profile        — single company_profiles row
      deals          — list of deal rows for this entity
    """
    ctx: dict = {
        "entity_id": entity_id,
        "area_id": area_id,
        "drugs": [],
        "trials": [],
        "catalysts": [],
        "company": None,
        "profile": None,
        "deals": [],
    }

    # -- Drugs for this entity (area_id is in drug_areas junction, not on drugs directly)
    drugs = _sb_get(sb_url, sb_key, "drugs", {
        "entity_id": f"eq.{entity_id}",
        "select": "*",
    })
    ctx["drugs"] = drugs

    if not drugs:
        # Try to find by company + area even if entity_id not set yet
        return ctx

    drug_ids = [d["id"] for d in drugs]
    drug_ids_filter = "in.(" + ",".join(drug_ids) + ")"

    # Collect canonical_drug_ids for this entity's drugs — used to broaden
    # trial/deal lookups so cross-drug-row records are captured correctly.
    canonical_ids: list[str] = list({
        d["canonical_drug_id"] for d in drugs if d.get("canonical_drug_id")
    })

    # -- Trials linked to these drugs (by drug_id)
    trials = _sb_get(sb_url, sb_key, "trials", {
        "drug_id": drug_ids_filter,
        "select": "*",
    })
    # Also fetch trials by canonical_drug_id to catch records written by
    # ct_gov_sync that reference a different drug row sharing the same canonical.
    if canonical_ids:
        canon_filter = "in.(" + ",".join(canonical_ids) + ")"
        canon_trials = _sb_get(sb_url, sb_key, "trials", {
            "canonical_drug_id": canon_filter,
            "select": "*",
        })
        seen_trial_ids = {t["id"] for t in trials}
        for t in canon_trials:
            if t["id"] not in seen_trial_ids:
                trials.append(t)
                seen_trial_ids.add(t["id"])
    ctx["trials"] = trials

    # -- Catalysts for these drugs
    catalysts = _sb_get(sb_url, sb_key, "catalysts", {
        "drug_id": drug_ids_filter,
        "select": "*",
    })
    ctx["catalysts"] = catalysts

    # -- Company from first drug
    company_id = drugs[0].get("company_id") if drugs else None
    if company_id:
        companies = _sb_get(sb_url, sb_key, "companies", {
            "id": f"eq.{company_id}",   # companies PK is 'id', not 'company_id'
            "select": "*",
            "limit": "1",
        })
        ctx["company"] = companies[0] if companies else None

        profiles = _sb_get(sb_url, sb_key, "company_profiles", {
            "company_id": f"eq.{company_id}",
            "select": "*",
            "limit": "1",
        })
        ctx["profile"] = profiles[0] if profiles else None

    # -- Deals for this entity (by entity_id)
    deals: list[dict] = []
    if entity_id:
        deals = _sb_get(sb_url, sb_key, "deals", {
            "entity_id": f"eq.{entity_id}",
            "select": "*",
        })
    # Also fetch deals by canonical_drug_id to capture deals written by
    # company_enrichment that may reference the canonical program directly.
    if canonical_ids:
        canon_filter = "in.(" + ",".join(canonical_ids) + ")"
        canon_deals = _sb_get(sb_url, sb_key, "deals", {
            "canonical_drug_id": canon_filter,
            "select": "*",
        })
        seen_deal_ids = {d["id"] for d in deals}
        for d in canon_deals:
            if d["id"] not in seen_deal_ids:
                deals.append(d)
                seen_deal_ids.add(d["id"])
    ctx["deals"] = deals

    return ctx
