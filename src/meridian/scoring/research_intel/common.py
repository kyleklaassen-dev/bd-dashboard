#!/usr/bin/env python3
"""Shared base for the research_intelligence split (§3): creds, Supabase I/O, utils, constants."""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from typing import Any

import requests


# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

STAGE_WEIGHTS: dict[str, int] = {
    "stage1_entity_discovery":   10,
    "stage2_drug_mapping":       15,
    "stage3_trial_intelligence": 20,
    "stage4_catalyst_engine":    15,
    "stage5_strategic_position": 25,
    "stage6_deal_intelligence":  15,
}

TIER_THRESHOLDS = {"thin": 40, "partial": 70}  # <40 thin, 40–69 partial, >=70 strong

TRIGGER_TYPES = {
    "trial_phase_ahead_of_drug_stage":    "Trial phase is more advanced than the mapped drug stage",
    "trial_pcd_without_catalyst":         "Trial has a primary completion date but no catalyst generated",
    "completed_trial_without_results":    "Trial status is completed but no results text on associated drug",
    "catalyst_date_passed_unresolved":    "Catalyst expected date has passed with no resolution/outcome",
    "profile_stale":                      "Company profile not enriched in >30 days",
    "new_deal_since_enrichment":          "A new deal exists with a created_at newer than company's last enrichment",
    "strategic_entity_missing_vs_ailux":  "Entity is strategic but vs_ailux field is empty on company profile",
}

# Drug stage → numeric rank for phase comparison
DRUG_STAGE_RANK: dict[str, int] = {
    "preclinical": 1,
    "phase 1": 2, "phase1": 2,
    "phase 1/2": 3, "phase1/2": 3,
    "phase 2": 4, "phase2": 4,
    "phase 2/3": 5, "phase2/3": 5,
    "phase 3": 6, "phase3": 6,
    "approved": 7,
}

TRIAL_PHASE_RANK: dict[str, int] = {
    "phase 1": 2, "phase1": 2,
    "phase 1/phase 2": 3,
    "phase 2": 4, "phase2": 4,
    "phase 2/phase 3": 5,
    "phase 3": 6, "phase3": 6,
    "phase 4": 7,
}

ALL_AREAS = ["tl1a", "tslp", "il4ra", "fcrn", "igf1r", "tcell"]


# ──────────────────────────────────────────────────────────────────────────────
# SUPABASE CLIENT
# ──────────────────────────────────────────────────────────────────────────────

def _get_supabase_creds() -> tuple[str, str]:
    """Return (url, service_key) from env or .supabase_service_key file."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not key:
        try:
            with open(".supabase_service_key") as f:
                key = f.read().strip()
        except FileNotFoundError:
            pass
    if not url or not key:
        raise RuntimeError(
            "Supabase credentials not found. Set SUPABASE_URL + SUPABASE_SERVICE_KEY "
            "or provide .supabase_service_key file."
        )
    return url, key


def _sb_get(url: str, key: str, table: str, params: dict) -> list[dict]:
    """GET rows from a Supabase table via PostgREST."""
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    resp = requests.get(f"{url}/rest/v1/{table}", headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _sb_upsert(url: str, key: str, table: str, data: dict | list) -> None:
    """Upsert one or more rows into a Supabase table."""
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    payload = data if isinstance(data, list) else [data]
    resp = requests.post(
        f"{url}/rest/v1/{table}", headers=headers, json=payload, timeout=30
    )
    resp.raise_for_status()


def _sb_patch(url: str, key: str, table: str, match: dict, data: dict) -> None:
    """PATCH rows matching `match` with `data`."""
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    params = {k: f"eq.{v}" for k, v in match.items()}
    resp = requests.patch(
        f"{url}/rest/v1/{table}", headers=headers, params=params, json=data, timeout=30
    )
    resp.raise_for_status()


# ──────────────────────────────────────────────────────────────────────────────
# HELPER
# ──────────────────────────────────────────────────────────────────────────────

def _nonempty(val: Any) -> bool:
    """Return True if val is meaningfully populated (not None, '', [], {})."""
    if val is None:
        return False
    if isinstance(val, str):
        return val.strip() != ""
    if isinstance(val, (list, dict)):
        return len(val) > 0
    return True  # numbers, booleans, etc.


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────────────────
# CANONICAL GROUPING HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _group_drugs_by_canonical(drugs: list[dict]) -> list[list[dict]]:
    """
    Group drug rows by canonical_drug_id.
    Drugs without a canonical_drug_id each form their own single-item group.
    Returns a list of groups (each group = list of drug rows sharing one canonical).
    """
    canon_groups: dict[str, list[dict]] = {}
    ungrouped: list[list[dict]] = []
    for d in drugs:
        cid = d.get("canonical_drug_id")
        if cid:
            canon_groups.setdefault(cid, []).append(d)
        else:
            ungrouped.append([d])
    return list(canon_groups.values()) + ungrouped


def _merge_drug_rows(rows: list[dict]) -> dict:
    """
    Merge multiple drug rows sharing the same canonical_drug_id into one
    representative row, using the most-populated value for each text field.

    Attaches:
      _all_drug_ids  — list of all constituent drug.id values (for trial/catalyst lookups)
    """
    if len(rows) == 1:
        merged = dict(rows[0])
        merged["_all_drug_ids"] = [rows[0]["id"]]
        return merged

    merged = dict(rows[0])
    TEXT_FIELDS = [
        "mechanism", "target", "stage", "differentiation_thesis",
        "results_summary", "vs_competitor", "drug_class", "name",
    ]
    for field in TEXT_FIELDS:
        best = max((r.get(field) or "" for r in rows), key=len)
        if best:
            merged[field] = best

    # Numeric: take max confidence score across all rows
    merged["confidence_score"] = max((r.get("confidence_score") or 0) for r in rows)

    # canonical_drug_id: take any populated value (all rows should share it)
    merged["canonical_drug_id"] = next(
        (r.get("canonical_drug_id") for r in rows if r.get("canonical_drug_id")), None
    )

    # trial_data_status: 'missing' only if EVERY row explicitly says 'missing'
    # (None/unset rows are treated as non-missing, so [None, "missing"] → not missing)
    statuses = [r.get("trial_data_status") for r in rows]
    if statuses and all(s == "missing" for s in statuses):
        merged["trial_data_status"] = "missing"
    else:
        merged["trial_data_status"] = next(
            (s for s in statuses if s and s != "missing"),
            statuses[0] if statuses else None,
        )

    # Keep all constituent IDs for downstream trial/catalyst lookups
    merged["_all_drug_ids"] = [r["id"] for r in rows]
    return merged
