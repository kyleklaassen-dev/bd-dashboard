#!/usr/bin/env python3
"""
Meridian Human Queue Builder — Tier 5 Meta Agent
==================================================
Phase F4 in the Weekend Sprint. Builds Kyle's prioritized review queue
in the feedback UI. Determines WHICH enriched fields Kyle should review
first, given limited time.

PRIORITY ALGORITHM (score each enriched_field_log entry):
  Base:    50
  +30      if drug.overlap IN ('Direct', 'Adjacent')
  +20      if field_name IN ('bd_angle', 'risk_summary', 'overlap', 'stage', 'ailux_angle')
  +15      if model_confidence < 0.6
  +10      if was_changed = true (model changed something)
  -10      if field_name IN ('source_citation', 'notes', 'description')
  +25      if drug.stage IN ('phase_2', 'phase_3')
  -5       per day since enriched_at (max -50)
  +20      if drug in catalyst_calendar with event within 6 months

OUTPUT:
  - Updates enriched_field_log with review_priority_score and review_queue_position
  - Writes summary to weekend_sprint_log
  - Auto-promotes stale pending labels to 'confirmed' if applicable

RUNS AS: Phase F4 in weekend_sprint.py

USAGE (standalone):
  python scripts/human_queue_builder.py
  python scripts/human_queue_builder.py --dry-run
  python scripts/human_queue_builder.py --limit 100
"""

import os
import sys
import json
import time
import datetime
import argparse
from typing import Optional, List, Dict, Tuple

import requests

# ── Path setup ───────────────────────────────────────────────────────────────
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT    = os.path.dirname(_SCRIPTS_DIR)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# ── Credentials ──────────────────────────────────────────────────────────────

def _read_cred(filename: str) -> str:
    for base in [_REPO_ROOT, _SCRIPTS_DIR]:
        path = os.path.join(base, filename)
        if os.path.exists(path):
            return open(path).read().strip()
    return ""


SUPABASE_URL = (
    os.environ.get("SUPABASE_URL")
    or _read_cred(".supabase_url")
    or "https://tghntyofptvfhmtchwcv.supabase.co"
)
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or _read_cred(".supabase_service_key")
)

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_KEY not set and .supabase_service_key not found")
    sys.exit(1)

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}
SB_UPSERT_HEADERS = {
    **SB_HEADERS,
    "Prefer": "resolution=merge-duplicates,return=minimal",
}

NOW_ISO  = datetime.datetime.utcnow().isoformat()
NOW_DT   = datetime.datetime.utcnow()
TODAY    = NOW_DT.strftime("%Y-%m-%d")
# DRY_RUN: mutable container + accessor (not a bare global) so run()'s setting in the
# orchestrator reaches the sb_* writers here across the §3 module split.
_RUNTIME = {"dry_run": False}
def set_dry_run(value: bool) -> None:
    _RUNTIME["dry_run"] = bool(value)
def is_dry_run() -> bool:
    return _RUNTIME["dry_run"]
RUN_ID   = f"hqb_{NOW_DT.strftime('%Y%m%d_%H%M%S')}"

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str, indent: int = 0):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {'  ' * indent}{msg}", flush=True)


# ── Supabase helpers ──────────────────────────────────────────────────────────

def sb_get(table: str, params: dict = None) -> List[dict]:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.get(url, headers=SB_HEADERS, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def sb_post(table: str, data: dict) -> dict:
    if is_dry_run():
        log(f"  [DRY-RUN] POST {table}: {json.dumps(data)[:120]}", indent=2)
        return data
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.post(url, headers=SB_UPSERT_HEADERS, json=data, timeout=30)
    r.raise_for_status()
    result = r.json()
    return result[0] if isinstance(result, list) and result else {}


def sb_patch(table: str, filters: dict, data: dict) -> int:
    if is_dry_run():
        log(f"  [DRY-RUN] PATCH {table} WHERE {filters}: {list(data.keys())}", indent=2)
        return 0
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    params = {k: f"eq.{v}" for k, v in filters.items()}
    r = requests.patch(url, headers=SB_HEADERS, params=params, json=data, timeout=30)
    r.raise_for_status()
    result = r.json()
    return len(result) if isinstance(result, list) else 1


def sb_upsert(table: str, rows: List[dict]) -> int:
    if is_dry_run() or not rows:
        if is_dry_run():
            log(f"  [DRY-RUN] UPSERT {len(rows)} rows into {table}", indent=2)
        return len(rows)
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.post(url, headers=SB_UPSERT_HEADERS, json=rows, timeout=60)
    r.raise_for_status()
    return len(rows)


def table_exists(tname: str) -> bool:
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{tname}",
            headers=SB_HEADERS,
            params={"limit": "1"},
            timeout=10,
        )
        return r.status_code != 404
    except Exception:
        return False


# ── Scoring constants ─────────────────────────────────────────────────────────

HIGH_VALUE_FIELDS = {"bd_angle", "risk_summary", "overlap", "stage", "ailux_angle"}
LOW_VALUE_FIELDS  = {"source_citation", "notes", "description"}
HIGH_OVERLAP      = {"Direct", "Adjacent"}
CLINICAL_STAGES   = {
    "phase_2", "phase_3", "phase2", "phase3",
    "phase 2", "phase 3", "phase ii", "phase iii",
}
CATALYST_HORIZON_DAYS = 180


def normalize_stage(s: str) -> str:
    return (s or "").lower().strip().replace("_", " ").replace("-", " ")


def is_clinical(stage: str) -> bool:
    return normalize_stage(stage) in {
        "phase 2", "phase 3", "phase2", "phase3", "phase ii", "phase iii",
        "phase 2 3", "phase 2/3"
    }


def days_since(iso_ts: str) -> float:
    """Return number of days since an ISO timestamp. Returns 0 if invalid."""
    if not iso_ts:
        return 0
    try:
        ts = datetime.datetime.fromisoformat(iso_ts[:19])
        return max(0, (NOW_DT - ts).total_seconds() / 86400)
    except Exception:
        return 0


# ── Priority scoring ──────────────────────────────────────────────────────────

def compute_priority_score(
    entry: Dict,
    drug_map: Dict[str, Dict],
    catalyst_drug_ids: set,
) -> int:
    """
    Compute review priority score for a single enriched_field_log entry.
    """
    score = 50  # base

    entity_id  = entry.get("entity_id") or ""
    entity_type = (entry.get("entity_type") or "").lower()
    field_name  = (entry.get("field_name") or "").lower()

    # Look up associated drug
    drug: Dict = {}
    if entity_type == "drug":
        drug = drug_map.get(str(entity_id), {})
    elif entity_type in ("company", "company_profile"):
        # Try to find a drug for this company
        pass  # Company entries get no drug bonus

    overlap = drug.get("overlap") or ""
    stage   = drug.get("stage") or ""

    # +30 if Direct/Adjacent overlap
    if overlap in HIGH_OVERLAP:
        score += 30

    # +20 if high-value field
    if field_name in HIGH_VALUE_FIELDS:
        score += 20

    # +15 if model_confidence (or confidence_score) < 0.6
    confidence = entry.get("model_confidence") or entry.get("confidence_score")
    if confidence is not None:
        try:
            if float(confidence) < 0.6:
                score += 15
        except (TypeError, ValueError):
            pass

    # +10 if was_changed = true
    was_changed = entry.get("was_changed")
    if was_changed is True or was_changed == "true":
        score += 10

    # -10 if low-value metadata field
    if field_name in LOW_VALUE_FIELDS:
        score -= 10

    # +25 if clinical stage
    if is_clinical(stage):
        score += 25

    # -5 per day since enriched_at (max -50)
    enriched_at = entry.get("enriched_at")
    age_days = days_since(enriched_at)
    staleness_penalty = min(50, int(age_days * 5))
    score -= staleness_penalty

    # +20 if drug has upcoming catalyst within 6 months
    if str(entity_id) in catalyst_drug_ids:
        score += 20

    return max(0, score)  # floor at 0
