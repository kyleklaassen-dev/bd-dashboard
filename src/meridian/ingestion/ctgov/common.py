#!/usr/bin/env python3
"""
Shared base for the ct_gov_sync split (§3): credentials, CT.gov/Supabase constants,
and the Supabase I/O helpers (log, sb_get, sb_upsert, sb_patch). Bottom of the
dependency star — the ctgov.* submodules import from here; nothing here imports them.
"""

import os
import datetime

import requests


# repo root: this file is src/meridian/ingestion/ctgov/common.py → 5 dirnames up.
_WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


def _read_key(env, filename, default=""):
    """Credential read, tolerant for CI/tests: env var first, then the repo-root file,
    then default (never raises) so PURE submodules (e.g. ctgov.map) import test-clean."""
    if os.environ.get(env, "").strip():
        return os.environ[env].strip()
    try:
        with open(os.path.join(_WORKSPACE, filename)) as f:
            return f.read().strip()
    except FileNotFoundError:
        return default


SUPABASE_URL = _read_key("SUPABASE_URL", ".supabase_url", "https://tghntyofptvfhmtchwcv.supabase.co")
SUPABASE_KEY = _read_key("SUPABASE_SERVICE_KEY", ".supabase_service_key")
CT_GOV_BASE  = "https://clinicaltrials.gov/api/v2"
TODAY        = datetime.datetime.utcnow().strftime("%Y-%m-%d")
NOW_ISO      = datetime.datetime.utcnow().isoformat()

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}
SB_UPSERT_HEADERS = {
    **SB_HEADERS,
    "Prefer": "resolution=merge-duplicates,return=representation",
}

# CT.gov status → our normalized status
CT_STATUS_MAP = {
    "RECRUITING":              "Recruiting",
    "ACTIVE_NOT_RECRUITING":   "Active, not recruiting",
    "COMPLETED":               "Completed",
    "TERMINATED":              "Terminated",
    "WITHDRAWN":               "Withdrawn",
    "NOT_YET_RECRUITING":      "Not yet recruiting",
    "ENROLLING_BY_INVITATION": "Enrolling by invitation",
    "APPROVED_FOR_MARKETING":  "Approved",
    "UNKNOWN":                 "Unknown",
}

# CT.gov phase codes → our display strings
CT_PHASE_MAP = {
    "PHASE1":        "Phase 1",
    "PHASE2":        "Phase 2",
    "PHASE3":        "Phase 3",
    "PHASE1_PHASE2": "Phase 1/2",
    "PHASE2_PHASE3": "Phase 2/3",
    "EARLY_PHASE1":  "Pre-IND",
    "NA":            "N/A",
}

# Stage rank for determining "most advanced" trial per drug
STAGE_RANK = {
    "Approved":    9,
    "Phase 3":     7,
    "Phase 2/3":   6,
    "Phase 2":     5,
    "Phase 1/2":   4,
    "Phase 1":     3,
    "Pre-IND":     2,
    "Preclinical": 1,
}


# ══════════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════════

def log(msg: str, indent: int = 0):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    prefix = "  " * indent
    print(f"[ct_gov {ts}] {prefix}{msg}", flush=True)


# ══════════════════════════════════════════════════════════════════════════
# SUPABASE HELPERS
# ══════════════════════════════════════════════════════════════════════════

def sb_get(table: str, params: dict) -> list:
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=SB_HEADERS, params=params, timeout=15
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"[sb_get {table}] {e}", indent=1)
        return []


def sb_upsert(table: str, records: list | dict,
              on_conflict: str | None = None) -> list:
    """
    Upsert records into a Supabase table.

    on_conflict: comma-separated column names for conflict target (e.g.
    'drug_id,check_type'). Required when the table has a non-PK unique
    constraint that should drive ON CONFLICT resolution. If omitted,
    PostgREST defaults to the primary key.
    """
    if isinstance(records, dict):
        records = [records]
    if not records:
        return []
    url    = f"{SUPABASE_URL}/rest/v1/{table}"
    params = {"on_conflict": on_conflict} if on_conflict else {}
    try:
        r = requests.post(url, headers=SB_UPSERT_HEADERS,
                          params=params, json=records, timeout=15)
        if r.status_code not in (200, 201):
            log(f"[sb_upsert {table}] {r.status_code}: {r.text[:200]}", indent=1)
            return []
        return r.json()
    except Exception as e:
        log(f"[sb_upsert {table}] {e}", indent=1)
        return []


def sb_patch(table: str, record: dict, match_params: dict) -> bool:
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=SB_HEADERS, params=match_params, json=record, timeout=15
        )
        return r.status_code in (200, 204)
    except Exception as e:
        log(f"[sb_patch {table}] {e}", indent=1)
        return False
