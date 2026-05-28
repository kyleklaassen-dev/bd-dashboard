#!/usr/bin/env python3
"""
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
DRY_RUN  = False
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
    if DRY_RUN:
        log(f"  [DRY-RUN] POST {table}: {json.dumps(data)[:100]}", indent=2)
        return data
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.post(url, headers=SB_UPSERT_HEADERS, json=data, timeout=30)
    r.raise_for_status()
    result = r.json()
    return result[0] if isinstance(result, list) and result else {}


def sb_upsert(table: str, rows: List[dict]) -> int:
    if DRY_RUN or not rows:
        if DRY_RUN:
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


# ── Check 1: Drug stage vs trial_registries ───────────────────────────────────

def check_stage_vs_trials() -> Dict:
    log("Check 1: Drug stage vs trial_registries phase", indent=1)
    results = {"checked": 0, "contradictions": 0}

    if not table_exists("trial_registries"):
        log("  trial_registries not found — skipping", indent=2)
        return {"skipped": "table_missing"}

    try:
        # Load trial registry data with drug_id and phase
        reg_rows = sb_get("trial_registries", {
            "select": "id,drug_id,phase,status",
            "limit": "500",
        })
        # Index: drug_id → [phases]
        trial_phases: Dict[str, List[str]] = defaultdict(list)
        for r in reg_rows:
            did = r.get("drug_id")
            phase = r.get("phase")
            if did and phase:
                trial_phases[did].append(phase.lower())

        # Load drugs
        drugs = sb_get("drugs", {
            "select": "id,name,stage",
            "limit": "500",
        })

        for drug in drugs:
            did = drug["id"]
            drug_stage = normalize_stage(drug.get("stage") or "")
            trial_ps = trial_phases.get(did)
            if not trial_ps or not drug_stage:
                continue

            results["checked"] += 1

            # Find most advanced trial phase
            max_trial_rank = max((stage_rank(tp) for tp in trial_ps), default=-1)
            drug_rank = stage_rank(drug_stage)

            # Contradiction: trial shows higher phase than drug record
            # (allow ±1 difference as noise)
            if max_trial_rank > drug_rank + 1 and max_trial_rank >= 0:
                best_trial_phase = max(trial_ps, key=lambda p: stage_rank(p))
                log(
                    f"  MISMATCH: {drug.get('name')} — "
                    f"drugs.stage={drug.get('stage')} but "
                    f"trial shows phase={best_trial_phase}",
                    indent=2
                )
                write_contradiction_typed(
                    entity_id=did,
                    entity_type="drug",
                    field_name="stage",
                    value_a=drug.get("stage"),
                    value_b=best_trial_phase,
                    contradiction_type="stage_vs_trial",
                    severity="warning",
                )
                results["contradictions"] += 1

    except Exception as e:
        log(f"  Stage vs trial check failed: {e}", indent=2)

    log(f"  Checked: {results['checked']}, contradictions: {results['contradictions']}", indent=2)
    return results


# ── Check 2: Brand name without approval ──────────────────────────────────────

def check_brand_name_without_approval() -> Dict:
    log("Check 2: Brand name without approval stage", indent=1)
    results = {"checked": 0, "contradictions": 0}

    try:
        branded = sb_get("drugs", {
            "select": "id,name,brand_name,stage",
            "brand_name": "not.is.null",
            "limit": "200",
        })
        results["checked"] = len(branded)
        for drug in branded:
            stage = (drug.get("stage") or "").lower()
            brand = drug.get("brand_name") or ""
            # Skip if brand_name is a dash placeholder
            if brand.strip() in ("—", "-", "–", ""):
                continue
            if stage not in VALID_APPROVED:
                log(
                    f"  VIOLATION: {drug.get('name')} has brand_name='{brand}' "
                    f"but stage='{stage}' (must be approved)",
                    indent=2
                )
                write_contradiction_typed(
                    entity_id=drug["id"],
                    entity_type="drug",
                    field_name="brand_name+stage",
                    value_a=brand,
                    value_b=stage,
                    contradiction_type="brand_name_without_approval",
                    severity="critical",
                )
                write_gov_violation(
                    "brand_name_implies_approved",
                    "drug",
                    drug["id"],
                    f"brand_name='{brand}' but stage='{stage}' — brand name implies approved"
                )
                results["contradictions"] += 1
    except Exception as e:
        log(f"  Brand name check failed: {e}", indent=2)

    log(f"  Checked: {results['checked']}, contradictions: {results['contradictions']}", indent=2)
    return results


# ── Check 3: company_id originator rule ──────────────────────────────────────

def check_company_id_originator() -> Dict:
    log("Check 3: company_id originator rule", indent=1)
    results = {"checked": 0, "potential_violations": 0}

    try:
        # Load deals with drug_name and company references
        deals = sb_get("deals", {
            "select": "id,drug_name,company_id,partner_company,deal_type",
            "limit": "300",
        })

        # Load drugs indexed by name
        drugs = sb_get("drugs", {
            "select": "id,name,company_id",
            "limit": "500",
        })
        drug_by_name: Dict[str, dict] = {}
        for d in drugs:
            n = (d.get("name") or "").lower().strip()
            if n:
                drug_by_name[n] = d

        results["checked"] = len(deals)

        for deal in deals:
            drug_name = (deal.get("drug_name") or "").lower().strip()
            deal_company_id = deal.get("company_id") or ""

            # Find matching drug
            drug = drug_by_name.get(drug_name)
            if not drug:
                continue

            drug_company_id = drug.get("company_id") or ""

            # Contradiction: deal.company_id differs from drug.company_id
            # and there's no obvious licensing relationship implied
            if (
                deal_company_id
                and drug_company_id
                and deal_company_id.lower() != drug_company_id.lower()
                and deal.get("deal_type") not in ("licensing", "sublicensing", "option")
            ):
                log(
                    f"  POTENTIAL VIOLATION: deal for '{deal.get('drug_name')}' — "
                    f"deal.company_id={deal_company_id} but drug.company_id={drug_company_id}",
                    indent=2
                )
                write_contradiction_typed(
                    entity_id=drug["id"],
                    entity_type="drug",
                    field_name="company_id",
                    value_a=f"{drug_company_id} (drug) vs {deal_company_id} (deal {deal['id']})",
                    value_b=deal_company_id,
                    contradiction_type="company_id_originator_mismatch",
                    severity="warning",
                )
                results["potential_violations"] += 1

    except Exception as e:
        log(f"  company_id originator check failed: {e}", indent=2)

    log(f"  Checked: {results['checked']}, potential violations: {results['potential_violations']}", indent=2)
    return results


# ── Check 4: Duplicate entity detection ──────────────────────────────────────

def check_duplicate_entities() -> Dict:
    log("Check 4: Duplicate entity detection (>85% name similarity)", indent=1)
    results = {"drug_pairs": 0, "company_pairs": 0}
    THRESHOLD = 0.85

    def find_near_duplicates(records: List[dict], id_field: str, name_field: str,
                             threshold: float, entity_type: str) -> int:
        pairs_found = 0
        items = [
            (str(r[id_field]), (r.get(name_field) or "").lower().strip())
            for r in records if r.get(name_field)
        ]
        for i, (id1, n1) in enumerate(items):
            if not n1:
                continue
            for id2, n2 in items[i + 1:]:
                if not n2 or id1 == id2:
                    continue
                ratio = difflib.SequenceMatcher(None, n1, n2).ratio()
                if ratio >= threshold and n1 != n2:
                    log(
                        f"  DUPLICATE CANDIDATE: {entity_type} '{n1}' ↔ '{n2}' "
                        f"(similarity={ratio:.2f})",
                        indent=2
                    )
                    write_contradiction_typed(
                        entity_id=id1,
                        entity_type=entity_type,
                        field_name="name",
                        value_a=n1,
                        value_b=f"possible_duplicate:{id2}:{n2}",
                        contradiction_type="duplicate_entity",
                        severity="warning",
                        resolution="needs_review",
                    )
                    pairs_found += 1
        return pairs_found

    try:
        drugs = sb_get("drugs", {"select": "id,name", "limit": "500"})
        results["drug_pairs"] = find_near_duplicates(
            drugs, "id", "name", THRESHOLD, "drug"
        )
        log(f"  Drug duplicate candidates: {results['drug_pairs']}", indent=2)
    except Exception as e:
        log(f"  Drug duplicate check failed: {e}", indent=2)

    try:
        companies = sb_get("companies", {"select": "id,name", "limit": "500"})
        results["company_pairs"] = find_near_duplicates(
            companies, "id", "name", THRESHOLD, "company"
        )
        log(f"  Company duplicate candidates: {results['company_pairs']}", indent=2)
    except Exception as e:
        log(f"  Company duplicate check failed: {e}", indent=2)

    return results


# ── Check 5: Deal attribution gap ─────────────────────────────────────────────

def check_deal_attribution() -> Dict:
    log("Check 5: Deal attribution — missing partnership rows", indent=1)
    results = {"deals_checked": 0, "gaps": 0}

    try:
        deals = sb_get("deals", {
            "select": "id,drug_name,company_id,partner_company",
            "limit": "300",
        })
        results["deals_checked"] = len(deals)

        # Load all partnerships indexed by company pair
        partnerships = sb_get("company_partnerships", {
            "select": "id,company_id,partner_company_id",
            "limit": "1000",
        })
        partner_pairs: Set[tuple] = set()
        for p in partnerships:
            a = (p.get("company_id") or "").lower()
            b = (p.get("partner_company_id") or "").lower()
            if a and b:
                partner_pairs.add((a, b))
                partner_pairs.add((b, a))

        # Load companies (to resolve partner_company name → id)
        companies = sb_get("companies", {"select": "id,name", "limit": "500"})
        co_by_name: Dict[str, str] = {}
        co_by_id: Dict[str, str] = {}
        for c in companies:
            n = (c.get("name") or "").lower().strip()
            co_by_name[n] = c["id"]
            co_by_id[c["id"]] = n

        for deal in deals:
            company_id = (deal.get("company_id") or "").lower()
            partner_name = (deal.get("partner_company") or "").lower()
            if not company_id or not partner_name:
                continue

            # Try to resolve partner name to ID
            partner_id = co_by_name.get(partner_name)
            if not partner_id:
                # Try fuzzy match
                for cname, cid in co_by_name.items():
                    ratio = difflib.SequenceMatcher(None, partner_name, cname).ratio()
                    if ratio > 0.85:
                        partner_id = cid
                        break

            if not partner_id:
                continue  # Can't verify without ID

            # Check if partnership row exists
            if (company_id, partner_id.lower()) not in partner_pairs:
                log(
                    f"  GAP: Deal '{deal.get('drug_name')}' involves "
                    f"{company_id} ↔ {partner_name} "
                    f"but no company_partnerships row found",
                    indent=2
                )
                write_contradiction_typed(
                    entity_id=str(deal["id"]),
                    entity_type="deal",
                    field_name="company_partnerships",
                    value_a=f"{company_id} deal_type={deal.get('deal_type')}",
                    value_b=f"partner={partner_id} has no partnership row",
                    contradiction_type="deal_missing_partnership_row",
                    severity="info",
                )
                results["gaps"] += 1

    except Exception as e:
        log(f"  Deal attribution check failed: {e}", indent=2)

    log(f"  Deals checked: {results['deals_checked']}, gaps: {results['gaps']}", indent=2)
    return results


# ── Check 6: Stage history contradiction ─────────────────────────────────────

def check_stage_history() -> Dict:
    log("Check 6: Stage history chain validation", indent=1)
    results = {"checked": 0, "contradictions": 0}

    if not table_exists("drug_stage_history"):
        log("  drug_stage_history not found — skipping", indent=2)
        return {"skipped": "table_missing"}

    try:
        # Get stage history ordered by recorded_at
        history = sb_get("drug_stage_history", {
            "select": "drug_id,stage,recorded_at",
            "limit": "500",
            "order": "recorded_at.asc",
        })
        # Group by drug_id
        drug_history: Dict[str, List[dict]] = defaultdict(list)
        for h in history:
            did = h.get("drug_id")
            if did:
                drug_history[did].append(h)

        # Load current stages
        drugs = sb_get("drugs", {"select": "id,name,stage", "limit": "500"})
        drug_current: Dict[str, dict] = {d["id"]: d for d in drugs}

        for drug_id, hist_rows in drug_history.items():
            if not hist_rows:
                continue

            # Most recent history entry
            latest_hist_stage = hist_rows[-1].get("stage") or ""
            current_drug = drug_current.get(drug_id)
            if not current_drug:
                continue

            current_stage = current_drug.get("stage") or ""
            results["checked"] += 1

            # If current stage doesn't match latest history — contradiction
            if (
                latest_hist_stage
                and current_stage
                and normalize_stage(latest_hist_stage) != normalize_stage(current_stage)
            ):
                log(
                    f"  HISTORY MISMATCH: {current_drug.get('name')} — "
                    f"history_latest={latest_hist_stage} != current={current_stage}",
                    indent=2
                )
                write_contradiction_typed(
                    entity_id=drug_id,
                    entity_type="drug",
                    field_name="stage",
                    value_a=current_stage,
                    value_b=f"history_latest:{latest_hist_stage}",
                    contradiction_type="stage_history_contradiction",
                    severity="warning",
                )
                results["contradictions"] += 1

            # Also check for regressions in the history chain itself
            for j in range(1, len(hist_rows)):
                prev = stage_rank(hist_rows[j - 1].get("stage") or "")
                curr = stage_rank(hist_rows[j].get("stage") or "")
                if curr < prev - 1 and prev >= 0 and curr >= 0:
                    log(
                        f"  REGRESSION in history: {current_drug.get('name')} "
                        f"{hist_rows[j-1].get('stage')} → {hist_rows[j].get('stage')}",
                        indent=2
                    )
                    write_contradiction_typed(
                        entity_id=drug_id,
                        entity_type="drug",
                        field_name="stage_history_chain",
                        value_a=hist_rows[j - 1].get("stage"),
                        value_b=f"regression_to:{hist_rows[j].get('stage')}",
                        contradiction_type="stage_history_regression",
                        severity="warning",
                    )
                    results["contradictions"] += 1

    except Exception as e:
        log(f"  Stage history check failed: {e}", indent=2)

    log(f"  Checked: {results['checked']}, contradictions: {results['contradictions']}", indent=2)
    return results


# ── Check 7: entity_relationships bidirectional symmetry ─────────────────────

def check_relationship_symmetry() -> Dict:
    log("Check 7: entity_relationships bidirectional symmetry", indent=1)
    results = {"checked": 0, "missing_symmetric": 0}

    if not table_exists("entity_relationships"):
        log("  entity_relationships not found — skipping", indent=2)
        return {"skipped": "table_missing"}

    SYMMETRIC_TYPES = {"competes_with", "similar_to", "overlaps_with"}

    try:
        rels = sb_get("entity_relationships", {
            "select": "id,entity_id_a,entity_id_b,relationship_type",
            "limit": "500",
        })
        results["checked"] = len(rels)

        # Build set of (a, b, type) for quick lookup
        rel_set: Set[tuple] = set()
        for r in rels:
            a = str(r.get("entity_id_a") or "")
            b = str(r.get("entity_id_b") or "")
            t = (r.get("relationship_type") or "").lower()
            if a and b and t:
                rel_set.add((a, b, t))

        # Check symmetric types
        for r in rels:
            rel_type = (r.get("relationship_type") or "").lower()
            if rel_type not in SYMMETRIC_TYPES:
                continue
            a = str(r.get("entity_id_a") or "")
            b = str(r.get("entity_id_b") or "")
            if not a or not b:
                continue
            # Check if reverse exists
            if (b, a, rel_type) not in rel_set:
                log(
                    f"  ASYMMETRIC: {a} —[{rel_type}]→ {b} "
                    f"but reverse not found",
                    indent=2
                )
                write_contradiction_typed(
                    entity_id=a,
                    entity_type="entity_relationship",
                    field_name="relationship_type",
                    value_a=f"{a} {rel_type} {b}",
                    value_b=f"missing_reverse:{b} {rel_type} {a}",
                    contradiction_type="relationship_asymmetry",
                    severity="info",
                )
                results["missing_symmetric"] += 1

    except Exception as e:
        log(f"  Relationship symmetry check failed: {e}", indent=2)

    log(f"  Checked: {results['checked']}, missing symmetric: {results['missing_symmetric']}", indent=2)
    return results


# ── Check 8: molecule_intelligence vs drugs table ─────────────────────────────

def check_molecule_vs_drug_stage() -> Dict:
    log("Check 8: molecule_intelligence vs drugs.stage", indent=1)
    results = {"checked": 0, "mismatches": 0}

    if not table_exists("molecule_intelligence"):
        log("  molecule_intelligence not found — skipping", indent=2)
        return {"skipped": "table_missing"}

    try:
        mol_rows = sb_get("molecule_intelligence", {
            "select": "id,drug_id,development_stage",
            "development_stage": "not.is.null",
            "limit": "300",
        })

        drugs = sb_get("drugs", {"select": "id,name,stage", "limit": "500"})
        drug_map: Dict[str, dict] = {d["id"]: d for d in drugs}

        for mol in mol_rows:
            drug_id = mol.get("drug_id")
            if not drug_id:
                continue
            drug = drug_map.get(drug_id)
            if not drug:
                continue

            mol_stage = normalize_stage(mol.get("development_stage") or "")
            drug_stage = normalize_stage(drug.get("stage") or "")
            results["checked"] += 1

            mol_rank = stage_rank(mol_stage)
            drug_rank = stage_rank(drug_stage)

            # Flag if both are non-empty and differ by more than 1 rank
            if mol_stage and drug_stage and abs(mol_rank - drug_rank) > 1:
                log(
                    f"  MISMATCH: {drug.get('name')} — "
                    f"molecule_intelligence.development_stage={mol.get('development_stage')} "
                    f"vs drugs.stage={drug.get('stage')}",
                    indent=2
                )
                write_contradiction_typed(
                    entity_id=drug_id,
                    entity_type="drug",
                    field_name="development_stage",
                    value_a=drug.get("stage"),
                    value_b=f"molecule_intelligence:{mol.get('development_stage')}",
                    contradiction_type="molecule_vs_drug_stage",
                    severity="warning",
                )
                results["mismatches"] += 1

    except Exception as e:
        log(f"  Molecule vs drug stage check failed: {e}", indent=2)

    log(f"  Checked: {results['checked']}, mismatches: {results['mismatches']}", indent=2)
    return results


# ── Main entry point ──────────────────────────────────────────────────────────

CHECKS = {
    "stage_mismatch":         check_stage_vs_trials,
    "brand_name":             check_brand_name_without_approval,
    "company_id_originator":  check_company_id_originator,
    "duplicate_entities":     check_duplicate_entities,
    "deal_attribution":       check_deal_attribution,
    "stage_history":          check_stage_history,
    "relationship_symmetry":  check_relationship_symmetry,
    "molecule_vs_drug":       check_molecule_vs_drug_stage,
}


def run(dry_run: bool = False, check_type: str = None) -> Dict:
    global DRY_RUN
    DRY_RUN = dry_run

    log("Consistency Checker — Tier 4 QA Agent")
    log(f"Run ID: {RUN_ID}")
    log(f"Dry-run: {DRY_RUN}")

    # Ensure table
    log("Ensuring agent_disagreements table exists", indent=1)
    if not DRY_RUN:
        ensure_agent_disagreements_table()

    # Run checks
    checks_to_run = (
        {check_type: CHECKS[check_type]}
        if check_type and check_type in CHECKS
        else CHECKS
    )

    all_results = {}
    total_contradictions = 0

    for name, fn in checks_to_run.items():
        try:
            result = fn()
            all_results[name] = result
            # Sum contradictions
            for key in ["contradictions", "potential_violations", "drug_pairs",
                        "company_pairs", "gaps", "missing_symmetric", "mismatches"]:
                total_contradictions += result.get(key, 0)
        except Exception as e:
            log(f"  Check '{name}' raised exception: {e}", indent=2)
            all_results[name] = {"error": str(e)}

    log("=" * 60)
    log(f"Consistency Check Complete")
    log(f"  Total contradictions found: {total_contradictions}")
    for name, result in all_results.items():
        log(f"  {name}: {result}", indent=1)

    all_results["total_contradictions"] = total_contradictions
    return all_results


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Meridian Consistency Checker — find data contradictions"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Run without writing to Supabase")
    parser.add_argument("--type", default=None,
                        choices=list(CHECKS.keys()),
                        help="Run only one check type")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run, check_type=args.type)
    print(json.dumps(result, indent=2, default=str))
