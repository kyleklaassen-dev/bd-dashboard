#!/usr/bin/env python3
"""
Trial-registry write for ct_gov_sync (§3 split): update_trial_registries. Routes
through the shared sb_upsert. Extracted verbatim.
"""

from meridian.ingestion.ctgov.common import sb_upsert, NOW_ISO


def update_trial_registries(drug_id: str, synced_ncts: list[str],
                             dry_run: bool = False) -> None:
    """
    Update trial_registries.ct_gov row after a drug is synced.
    Called from sync_drug() so the table stays current after every run.
    """
    if dry_run:
        return
    status = "found" if synced_ncts else "not_found"
    row = {
        "drug_id":          drug_id,
        "registry_name":    "ct_gov",
        "registry_id":      None,
        "registry_url":     None,
        "search_status":    status,
        "trial_count":      len(synced_ncts),
        "last_searched_at": NOW_ISO,
        "verified_by":      "ct_gov_sync",
        "notes":            (f"{len(synced_ncts)} trial(s) found" if synced_ncts
                             else "Searched; no trials found on CT.gov"),
        "updated_at":       NOW_ISO,
    }
    sb_upsert("trial_registries", [row], on_conflict="drug_id,registry_name")
