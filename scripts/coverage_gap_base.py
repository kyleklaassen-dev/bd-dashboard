#!/usr/bin/env python3
"""
Meridian Coverage Gap Finder — Tier 4 QA Agent
================================================
Phase A6 (extended) in the Weekend Sprint. Identifies what's missing —
drugs, companies, and relationships that SHOULD be in the database but aren't.

GAP TYPES:
  1. Low coverage_score drugs (<40) — add to research_queue
  2. Missing molecule_intelligence rows
  3. Missing drug_indications rows
  4. Missing catalyst_calendar for Phase 2/3 drugs
  5. Missing company_partnerships rows when deal exists
  6. Phantom companies (no drugs, no partnerships)
  7. entity_relationships with verification_needed=true
  8. Direct/Adjacent overlap drugs with null bd_angle (P0 priority)
  9. Phase 2/3 drugs with null risk_summary (P1 gap)

OUTPUT:
  Writes to research_queue table.
  Returns summary dict {gap_type: count}.

RUNS AS: Phase A6 in weekend_sprint.py (replaces/extends the existing A6 backlog scan)

USAGE (standalone):
  python scripts/coverage_gap_finder.py
  python scripts/coverage_gap_finder.py --dry-run
  python scripts/coverage_gap_finder.py --gap bd_angle
"""

import os
import sys
import json
import time
import datetime
import argparse
from typing import Optional, List, Dict, Set
from collections import defaultdict

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
TODAY    = datetime.datetime.utcnow().strftime("%Y-%m-%d")
# DRY_RUN: mutable container + accessor (not a bare global) so run()'s setting in the
# orchestrator reaches sb_post/sb_upsert here across the §3 module split.
_RUNTIME = {"dry_run": False}
def set_dry_run(value: bool) -> None:
    _RUNTIME["dry_run"] = bool(value)
def is_dry_run() -> bool:
    return _RUNTIME["dry_run"]
RUN_ID   = f"cgf_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

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


# ── Priority constants ────────────────────────────────────────────────────────

PRIORITY_P0 = "P0"   # BD-critical, blocks analysis
PRIORITY_P1 = "P1"   # High value, enrichment needed soon
PRIORITY_P2 = "P2"   # Medium value
PRIORITY_P3 = "P3"   # Low priority, background

CLINICAL_STAGES = {"phase_2", "phase_3", "phase2", "phase3", "phase 2", "phase 3",
                   "phase ii", "phase iii", "phase2/3", "phase 2/3"}


def is_clinical(stage: str) -> bool:
    return (stage or "").lower().replace("-", " ").replace("_", " ") in CLINICAL_STAGES


def write_queue_item(
    entity_type: str,
    entity_id: str,
    gap_type: str,
    priority: str,
    reason: str,
) -> Dict:
    """Write a gap item to research_queue."""
    row = {
        "entity_type": entity_type,
        "entity_id":   str(entity_id),
        "gap_type":    gap_type,
        "priority":    priority,
        "reason":      reason[:500],
        "detected_at": NOW_ISO,
        "source":      "coverage_gap_finder",
        "run_id":      RUN_ID,
        "status":      "pending",
    }
    if table_exists("research_queue"):
        try:
            sb_post("research_queue", row)
        except Exception as e:
            log(f"  research_queue write failed: {e}", indent=3)
    return row
