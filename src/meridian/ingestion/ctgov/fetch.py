#!/usr/bin/env python3
"""
ClinicalTrials.gov API v2 fetch helpers (§3 ct_gov_sync split): ct_fetch_by_nct and
ct_search_by_name. Extracted verbatim.
"""

from typing import Optional

import requests

from meridian.ingestion.ctgov.common import CT_GOV_BASE, log


def ct_fetch_by_nct(nct_id: str) -> Optional[dict]:
    """
    Fetch a single study by NCT ID from CT.gov API v2.
    Returns the raw study JSON or None on error/not found.
    """
    if not nct_id or not nct_id.startswith("NCT"):
        return None
    try:
        r = requests.get(
            f"{CT_GOV_BASE}/studies/{nct_id}",
            params={"format": "json"},
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            log(f"  NCT {nct_id}: not found on CT.gov", indent=2)
        else:
            log(f"  NCT {nct_id}: HTTP {r.status_code}", indent=2)
        return None
    except Exception as e:
        log(f"  NCT {nct_id}: fetch error — {e}", indent=2)
        return None


def ct_search_by_name(drug_name: str, indication: str = None, max_results: int = 10) -> list[dict]:
    """
    Search CT.gov by drug name + optional indication.
    Returns list of study JSON objects.
    """
    params = {
        "format":   "json",
        "pageSize": max_results,
        "query.intr": drug_name,
    }
    if indication:
        params["query.cond"] = indication
    try:
        r = requests.get(f"{CT_GOV_BASE}/studies", params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get("studies", [])
        return []
    except Exception as e:
        log(f"  Search '{drug_name}': error — {e}", indent=2)
        return []
