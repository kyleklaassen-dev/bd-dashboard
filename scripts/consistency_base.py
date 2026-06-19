#!/usr/bin/env python3
"""
consistency_base.py — shared base for the Consistency Checker (§3 split).
Meridian Consistency Checker — Tier 4 QA Agent
================================================
Phase E5 in the Weekend Sprint. Finds data contradictions across the database
— where two pieces of stored data conflict with each other.

CONTRADICTION TYPES:
  1. Drug stage vs trial_registries phase mismatch
  2. Brand name without approval stage
  3. company_id originator rule violations (drug.company_id vs deal records)
  4. Duplicate entity detection (>85% name similarity)
  5. Deal attribution gap (deal references company with no partnership row)
  6. Stage history contradiction (history chain broken)
  7. entity_relationships bidirectional symmetry check
  8. molecule_intelligence vs drugs table stage mismatch

OUTPUT:
  Writes to agent_disagreements table (create if needed).
  Writes governance_violations for governance-rule contradictions.

RUNS AS: Phase E5 in weekend_sprint.py

USAGE (standalone):
  python scripts/consistency_checker.py
  python scripts/consistency_checker.py --dry-run
  python scripts/consistency_checker.py --type stage_mismatch
"""

import os
import sys
import re
import json
import time
import datetime
import argparse
import difflib
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
# DRY_RUN lives in a mutable container + accessor (NOT a bare module global): the value
# set by run() in the orchestrator must be visible to sb_post/sb_upsert here across the
# §3 module split — a plain `global` would not cross module boundaries.
_RUNTIME = {"dry_run": False}
def set_dry_run(value: bool) -> None:
    _RUNTIME["dry_run"] = bool(value)
def is_dry_run() -> bool:
    return _RUNTIME["dry_run"]
RUN_ID   = f"cc_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

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
        log(f"  [DRY-RUN] POST {table}: {json.dumps(data)[:100]}", indent=2)
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


# ── DDL: ensure agent_disagreements table ────────────────────────────────────
# Run once manually or via Supabase SQL editor:
#
# CREATE TABLE IF NOT EXISTS agent_disagreements (
#     id BIGSERIAL PRIMARY KEY,
#     entity_id_a TEXT,
#     entity_id_b TEXT,
#     field_name TEXT NOT NULL,
#     value_a TEXT,
#     value_b TEXT,
#     contradiction_type TEXT NOT NULL,
#     severity TEXT NOT NULL CHECK (severity IN ('critical','warning','info')),
#     resolution TEXT CHECK (resolution IN (NULL,'auto_resolved','needs_review')),
#     detected_at TIMESTAMPTZ DEFAULT NOW(),
#     enrichment_run_id TEXT
# );
# CREATE INDEX IF NOT EXISTS ad_type_idx ON agent_disagreements(contradiction_type);
# CREATE INDEX IF NOT EXISTS ad_severity_idx ON agent_disagreements(severity);

AD_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS agent_disagreements (
    id BIGSERIAL PRIMARY KEY,
    entity_id_a TEXT,
    entity_id_b TEXT,
    field_name TEXT NOT NULL,
    value_a TEXT,
    value_b TEXT,
    contradiction_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('critical','warning','info')),
    resolution TEXT,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    enrichment_run_id TEXT
);
CREATE INDEX IF NOT EXISTS ad_type_idx ON agent_disagreements(contradiction_type);
CREATE INDEX IF NOT EXISTS ad_severity_idx ON agent_disagreements(severity);
"""


def ensure_agent_disagreements_table():
    if table_exists("agent_disagreements"):
        log("  agent_disagreements table: exists (using existing schema)", indent=2)
        return
    log("  agent_disagreements table: not found — attempting DDL creation", indent=2)
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=SB_HEADERS,
            json={"sql": AD_CREATE_SQL},
            timeout=30,
        )
        log(f"  agent_disagreements DDL: HTTP {r.status_code}", indent=2)
    except Exception as e:
        log(f"  agent_disagreements DDL failed (apply manually via Supabase SQL editor): {e}", indent=2)


# ── Stage normalization ───────────────────────────────────────────────────────

STAGE_ORDER = [
    "discovery", "preclinical", "ind", "phase 1", "phase 1/2", "phase 2",
    "phase 2/3", "phase 3", "nda", "bla", "approved"
]
VALID_APPROVED = {
    "approved", "approved_us", "approved_eu", "approved_china",
    "approved_us_eu", "approved_partial"
}


def stage_rank(stage_str: str) -> int:
    s = (stage_str or "").lower().replace("_", " ").replace("-", " ")
    for i, st in enumerate(STAGE_ORDER):
        if st in s:
            return i
    return -1


def normalize_stage(s: str) -> str:
    return (s or "").lower().strip().replace("_", " ").replace("-", " ")


# ── Helper: write contradiction ───────────────────────────────────────────────

def write_contradiction(
    entity_id_a: str,
    entity_id_b: str,
    field_name: str,
    value_a: str,
    value_b: str,
    contradiction_type: str,
    severity: str = "warning",
    resolution: str = None,
) -> Dict:
    """
    Write to agent_disagreements table using its actual schema:
      entity_id, entity_type, field_name, run_id_a, run_id_b,
      value_a, value_b, disagreement_score, resolution
    contradiction_type and severity are encoded into value_a prefix and
    disagreement_score (critical=1.0, warning=0.7, info=0.4).
    """
    score_map = {"critical": 1.0, "warning": 0.7, "info": 0.4}
    row = {
        "entity_id":         str(entity_id_a) if entity_id_a else "unknown",
        "entity_type":       "drug_or_company",  # will be overridden by callers
        "field_name":        field_name,
        "value_a":           f"[{contradiction_type}] {str(value_a)[:400]}" if value_a else f"[{contradiction_type}]",
        "value_b":           str(value_b)[:500] if value_b else entity_id_b or "",
        "disagreement_score": score_map.get(severity, 0.5),
        "resolution":        resolution,
    }
    if table_exists("agent_disagreements"):
        try:
            sb_post("agent_disagreements", row)
        except Exception as e:
            log(f"  write_contradiction failed: {e}", indent=3)
    return row


def write_contradiction_typed(
    entity_id: str,
    entity_type: str,
    field_name: str,
    value_a: str,
    value_b: str,
    contradiction_type: str,
    severity: str = "warning",
    resolution: str = None,
) -> Dict:
    """Typed version — uses entity_type correctly."""
    score_map = {"critical": 1.0, "warning": 0.7, "info": 0.4}
    row = {
        "entity_id":         str(entity_id) if entity_id else "unknown",
        "entity_type":       entity_type or "unknown",
        "field_name":        field_name,
        "value_a":           f"[{contradiction_type}] {str(value_a)[:400]}" if value_a else f"[{contradiction_type}]",
        "value_b":           str(value_b)[:500] if value_b else "",
        "disagreement_score": score_map.get(severity, 0.5),
        "resolution":        resolution,
    }
    if table_exists("agent_disagreements"):
        try:
            sb_post("agent_disagreements", row)
        except Exception as e:
            log(f"  write_contradiction_typed failed: {e}", indent=3)
    return row


def write_gov_violation(rule_name: str, entity_type: str, entity_id: str, message: str):
    if not table_exists("governance_violations"):
        return
    try:
        sb_post("governance_violations", {
            "rule_name":   rule_name,
            "entity_type": entity_type,
            "entity_id":   str(entity_id),
            "message":     message[:500],
            "resolved":    False,
            "created_at":  NOW_ISO,
        })
    except Exception as e:
        log(f"  write_gov_violation failed: {e}", indent=3)
