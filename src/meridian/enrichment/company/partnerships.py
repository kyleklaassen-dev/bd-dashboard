#!/usr/bin/env python3
"""
Company Partnerships Writer (§3 company_enrichment split).
==========================================================
Extracted verbatim from company_enrichment.py. Writes company_partnerships rows
discovered/refined during Step 5. Self-contained leaf.
"""

from typing import Optional

from meridian.enrichment.company.common import log, sb_get, sb_post


# ══════════════════════════════════════════════════════════════════════════
# COMPANY PARTNERSHIPS WRITER
# Governance rule: company_id = lead company (licensee/deal holder)
# partner_company_name = originator/licensor (never change company_id)
# ══════════════════════════════════════════════════════════════════════════

def write_company_partnerships(company_id: str, partnerships_data: list,
                                run_id: Optional[str] = None,
                                dry_run: bool = False) -> int:
    """Write newly discovered partnerships to company_partnerships table.

    Governance: company_id = lead company. Partner = originator.
    Skips rows that already exist (dedup by company_id + partner_company_name + deal_type).
    Requires source_url per governance rule (Governance Rule 5).
    Returns count of rows written.

    Args:
      company_id:        Supabase company_id of the lead company.
      partnerships_data: list of dicts with keys:
                           partner_name, deal_type, drug_id, source_url, notes
      run_id:            enrichment_run_id for provenance stamping.
      dry_run:           if True, log but do not write.
    """
    # Verify company_partnerships table exists (may not have been migrated yet)
    try:
        _probe = sb_get("company_partnerships", {"company_id": f"eq.{company_id}", "limit": "1", "select": "id"})
    except Exception as _probe_exc:
        log(f"  company_partnerships: table probe failed — skipping writes: {_probe_exc}", indent=2)
        return 0

    VALID_DEAL_TYPES = {
        "licensing", "co-development", "option", "collaboration",
        "acquisition", "merger", "supply", "distribution", "research",
    }

    written = 0
    for p in partnerships_data:
        partner_name = (p.get("partner_name") or "").strip()
        deal_type    = (p.get("deal_type") or "collaboration").strip().lower()
        drug_id      = p.get("drug_id") or None
        source_url   = (p.get("source_url") or "").strip() or None
        notes        = p.get("notes") or None

        if not partner_name:
            log("  ⚠ company_partnerships: missing partner_name — skipped", indent=2)
            continue

        if deal_type not in VALID_DEAL_TYPES:
            log(f"  ⚠ company_partnerships: invalid deal_type '{deal_type}' — defaulting to 'collaboration'", indent=2)
            deal_type = "collaboration"

        # Governance Rule 5: source_url required for all partnership rows
        if not source_url:
            log(f"  ⚠ company_partnerships [{partner_name}]: source_url missing — "
                "set partnership_verified=false and omitting row (add source to fix)", indent=2)
            continue

        # Dedup check: skip if this (company_id, partner_name, deal_type) already exists
        existing = sb_get("company_partnerships", {
            "company_id":          f"eq.{company_id}",
            "partner_company_name": f"eq.{partner_name}",
            "deal_type":           f"eq.{deal_type}",
            "select":              "id",
            "limit":               "1",
        })
        if existing:
            log(f"  company_partnerships [{partner_name} / {deal_type}]: already exists — skipped", indent=2)
            continue

        record: dict = {
            "company_id":           company_id,
            "partner_company_name": partner_name,
            "deal_type":            deal_type,
            "partnership_verified": False,
            "source_url":           source_url,
            "is_current":           True,
        }
        if drug_id:
            record["drug_id"] = drug_id
        if notes:
            record["notes"] = notes

        # Note: enrichment_run_id not on company_partnerships schema by default;
        # write it only if the column exists (non-fatal if it doesn't).
        if run_id:
            record["enrichment_run_id"] = run_id

        if dry_run:
            log(f"  [dry] company_partnerships: would write {company_id} ↔ {partner_name} [{deal_type}]", indent=2)
            written += 1
            continue

        try:
            result = sb_post("company_partnerships", record)
            if result:
                log(f"  company_partnerships: ✓ {company_id} ↔ {partner_name} [{deal_type}]", indent=2)
                written += 1
            else:
                # Retry without enrichment_run_id in case column doesn't exist yet
                record.pop("enrichment_run_id", None)
                result2 = sb_post("company_partnerships", record)
                if result2:
                    log(f"  company_partnerships: ✓ {company_id} ↔ {partner_name} [{deal_type}] (no run_id)", indent=2)
                    written += 1
                else:
                    log(f"  company_partnerships: ✗ write failed for {partner_name}", indent=2)
        except Exception as _cp_exc:
            log(f"  company_partnerships: exception writing {partner_name}: {_cp_exc}", indent=2)

    if written:
        log(f"  → {written} company_partnership(s) written for {company_id}", indent=1)
    return written
