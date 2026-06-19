#!/usr/bin/env python3
"""
Ailux BD Platform — Model Comparison Engine
============================================
Phase 4.1 — Trusted Intelligence Framework, System #3

PURPOSE:
  1. Analyse model_validation_results to compute per-model/per-field accuracy.
  2. Identify which field types have the highest hallucination or stale_assumption rate.
  3. Flag prompts whose accuracy < 80% on any field type for review.
  4. Output a structured report: model_comparison_report.json.
  5. Provide log_enrichment_run() for use by company_enrichment.py and other scripts.

USAGE:
  python scripts/model_comparison.py                    # full report
  python scripts/model_comparison.py --output /tmp/     # custom output directory

ENVIRONMENT:
  SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import os
import json
import datetime
import argparse
from collections import defaultdict
from typing import Optional

import requests


# ══════════════════════════════════════════════════════════════════════════
# CREDENTIALS
# ══════════════════════════════════════════════════════════════════════════

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}

NOW_ISO = datetime.datetime.utcnow().isoformat()


# ══════════════════════════════════════════════════════════════════════════
# SUPABASE HELPERS
# ══════════════════════════════════════════════════════════════════════════

def sb_get(table: str, params: dict) -> list:
    """Fetch rows from a Supabase table."""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=SB_HEADERS,
            params=params,
            timeout=30,
        )
        if r.status_code == 200:
            return r.json() or []
        print(f"[sb_get {table}] HTTP {r.status_code}: {r.text[:200]}")
        return []
    except Exception as e:
        print(f"[sb_get {table}] {e}")
        return []


def sb_insert(table: str, record: dict) -> Optional[dict]:
    """Insert a single row, return the created row or None."""
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=SB_HEADERS,
            json=record,
            timeout=15,
        )
        if r.status_code in (200, 201):
            data = r.json()
            return data[0] if isinstance(data, list) and data else data
        print(f"[sb_insert {table}] HTTP {r.status_code}: {r.text[:300]}")
        return None
    except Exception as e:
        print(f"[sb_insert {table}] {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC API — log_enrichment_run
# ══════════════════════════════════════════════════════════════════════════

def log_enrichment_run(
    script_name: str,
    model_name: str,
    prompt_version: str,
    entity_type: str,
    entities_processed: int = 0,
    notes: str = "",
    # v59 trajectory capture fields
    prompt_snapshot: str = "",
    entity_id: str = "",
    skill_name: str = "",
    # v60 run classification fields
    model_version: str = "claude-sonnet-4-6",
    run_type: str = "scheduled",
) -> Optional[str]:
    """
    Create an enrichment_runs record in Supabase.

    Returns the run_id (UUID string) for use in subsequent enriched_field_log inserts,
    or None if the insert failed (caller should continue without tracking).

    Args:
      script_name        — 'company_enrichment.py' | 'molecule_enrichment.py' | etc.
      model_name         — 'claude-sonnet-4-6' | 'gpt-4o' | 'human' | etc.
      prompt_version     — version string from prompt_versions table, e.g. 'v1.2'
      entity_type        — 'drug' | 'company' | 'relationship'
      entities_processed — how many entities will be (or were) enriched in this run
      notes              — optional free-text context
      prompt_snapshot    — v59: first ~5000 chars of the system prompt (for fine-tuning)
      entity_id          — v59: drug/company ID being enriched (for single-entity runs)
      skill_name         — v59: 'enrich_drug' | 'company_enrich' | etc.
      model_version      — v60: explicit model version string, e.g. 'claude-sonnet-4-6'
      run_type           — v60: 'scheduled' | 'manual' | 'correction' | 'weekend_sprint' | 'validation'

    Usage in enrichment scripts:
      from model_comparison import log_enrichment_run
      run_id = log_enrichment_run('company_enrichment.py', 'claude-sonnet-4-6', 'v1.0', 'company',
                                  model_version='claude-sonnet-4-6', run_type='scheduled')
      # ... do enrichment ...
      # pass run_id to drug/company patch payloads as last_enrichment_run_id
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[log_enrichment_run] SUPABASE_URL or SUPABASE_SERVICE_KEY not set — skipping run log")
        return None

    record = {
        "script_name":       script_name,
        "model_name":        model_name,
        "prompt_version":    prompt_version,
        "entity_type":       entity_type,
        "entities_processed": entities_processed,
        "run_date":          NOW_ISO,
        "notes":             notes or None,
        # v59 trajectory capture
        "fine_tune_eligible": True,
        # v60 run classification
        "model_version":     model_version,
        "run_type":          run_type,
    }
    if prompt_snapshot:
        record["prompt_snapshot"] = prompt_snapshot[:5000]
    if entity_id:
        record["entity_id"] = entity_id
    if skill_name:
        record["skill_name"] = skill_name

    result = sb_insert("enrichment_runs", record)
    if result and result.get("id"):
        run_id = result["id"]
        print(f"[log_enrichment_run] run_id={run_id} ({script_name} / {model_name} / {prompt_version})")
        return run_id
    print("[log_enrichment_run] Insert failed — continuing without run tracking")
    return None


def update_enrichment_run(
    run_id: str,
    fields_set: int = 0,
    run_duration_seconds: float = 0.0,
    error_count: int = 0,
    companies_processed: int = 0,
    drugs_processed: int = 0,
    areas_processed: Optional[list] = None,
    summary_json: Optional[dict] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> bool:
    """
    Patch an enrichment_run row after the batch completes.
    Sets status='completed' and completed_at to mark the run as done.
    Call at the end of run_intelligence_pipeline() with totals.

    Args:
      fields_set             — total fields written (legacy counter)
      run_duration_seconds   — wall-clock seconds for the full run
      error_count            — number of company enrichment failures
      companies_processed    — how many company entities were enriched
      drugs_processed        — how many drug rows were touched
      areas_processed        — list of area_ids covered by this run
      summary_json           — structured change summary (see build_enrichment_summary)
    """
    if not run_id:
        return False
    try:
        payload: dict = {
            "fields_set":            fields_set,
            "run_duration_seconds":  round(run_duration_seconds, 2),
            "error_count":           error_count,
            # Mark run complete so it doesn't stay stuck in 'running'
            "status":                "completed",
            "completed_at":          datetime.datetime.utcnow().isoformat(),
        }
        if companies_processed:
            payload["companies_processed"] = companies_processed
        if drugs_processed:
            payload["drugs_processed"] = drugs_processed
        if areas_processed:
            payload["areas_processed"] = areas_processed
        if summary_json:
            payload["summary_json"] = summary_json
        if prompt_tokens or completion_tokens:
            payload["prompt_tokens"]     = prompt_tokens
            payload["completion_tokens"] = completion_tokens
            payload["total_tokens_used"] = prompt_tokens + completion_tokens
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/enrichment_runs",
            headers=SB_HEADERS,
            params={"id": f"eq.{run_id}"},
            json=payload,
            timeout=10,
        )
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"[update_enrichment_run] {e}")
        return False


def patch_enrichment_run(run_id: str, patch: dict) -> bool:
    """
    Patch arbitrary fields on an enrichment_run row.

    Used by company_enrichment.py to store v59 trajectory capture fields
    (raw_llm_response, schema_valid, fields_attempted, fields_changed,
    fields_confirmed, fields_failed, correction_count) after each enrichment.

    All patch failures are non-fatal — enrichment continues regardless.
    """
    if not run_id or not patch:
        return False
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/enrichment_runs",
            headers=SB_HEADERS,
            params={"id": f"eq.{run_id}"},
            json=patch,
            timeout=10,
        )
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"[patch_enrichment_run] {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════
# v65 ENRICHMENT SUMMARY — build_enrichment_summary
# ══════════════════════════════════════════════════════════════════════════

def build_enrichment_summary(run_id: str) -> Optional[dict]:
    """
    Query enriched_field_log for all rows tied to run_id and build a
    structured summary dict. PATCHes enrichment_runs.summary_json.

    Returns the summary dict, or None on failure.

    Summary shape:
      {
        "total_changes": N,
        "companies_changed": ["abbvie", ...],           # up to 20
        "fields_changed_most": [["field_name", count]], # top 10
        "editorial_changes": {                          # drug_summary / ailux_angle / risk_summary
          "drug_summary": ["drugA", ...],
          "ailux_angle":  ["drugB", ...],
          "risk_summary": ["drugC", ...],
        },
        "by_company": {                                 # up to 20 companies
          "abbvie": {
            "fields_changed": ["overlap", "drug_summary"],
            "change_count": 2,
          }
        }
      }
    """
    if not run_id or not SUPABASE_URL:
        return None

    # Pull all enriched_field_log rows for this run
    try:
        rows = sb_get(
            "enriched_field_log",
            {
                "enrichment_run_id": f"eq.{run_id}",
                "select": "entity_id,entity_type,field_name,old_value,enriched_value",
                "limit": "2000",
            },
        )
    except Exception as e:
        print(f"[build_enrichment_summary] fetch error: {e}")
        return None

    if not rows:
        return {"total_changes": 0, "companies_changed": [], "fields_changed_most": [], "editorial_changes": {}, "by_company": {}}

    # Only count rows where something actually changed
    changed = [r for r in rows if r.get("old_value") != r.get("enriched_value")]

    from collections import Counter
    field_counter: Counter = Counter()
    by_entity: dict = {}
    editorial: dict = {"drug_summary": [], "ailux_angle": [], "risk_summary": []}

    for row in changed:
        eid   = row.get("entity_id") or "unknown"
        fname = row.get("field_name") or "unknown"
        field_counter[fname] += 1

        if eid not in by_entity:
            by_entity[eid] = {"fields_changed": [], "change_count": 0}
        by_entity[eid]["fields_changed"].append(fname)
        by_entity[eid]["change_count"] += 1

        if fname in editorial:
            editorial[fname].append(eid)

    # Trim to top 20 companies by change_count
    top_companies = sorted(by_entity.keys(), key=lambda k: by_entity[k]["change_count"], reverse=True)[:20]
    by_company_trimmed = {k: by_entity[k] for k in top_companies}

    summary = {
        "total_changes":      len(changed),
        "companies_changed":  top_companies,
        "fields_changed_most": field_counter.most_common(10),
        "editorial_changes":  {k: v for k, v in editorial.items() if v},
        "by_company":         by_company_trimmed,
    }

    # Patch the enrichment_runs row
    patch_enrichment_run(run_id, {"summary_json": summary})
    print(f"[build_enrichment_summary] run_id={run_id[:8]}... | {len(changed)} changes across {len(by_entity)} entities")
    return summary


# ══════════════════════════════════════════════════════════════════════════
# v63 SECURITY CAMERA — set_audit_session_vars
# ══════════════════════════════════════════════════════════════════════════

def set_audit_session_vars(
    changed_by: str,
    run_id: Optional[str] = None,
    change_source: str = "enrichment_agent",
    change_reason: str = "",
    session_id: str = "",
    migration_file: str = "",
    migration_version: str = "",
) -> str:
    """
    Build the SET LOCAL SQL block that enrichment scripts should prepend to
    any UPDATE query so the field_change_audit trigger captures correct attribution.

    Returns a SQL string of SET LOCAL statements — include at the start of any
    transaction or use in a combined SQL block with your UPDATE.

    Usage in enrichment scripts:
        from model_comparison import set_audit_session_vars
        audit_vars = set_audit_session_vars(
            changed_by='company_enrichment_agent',
            run_id=run_id,
            change_source='enrichment_agent',
            change_reason='nightly enrichment run',
            session_id=os.environ.get('GITHUB_RUN_ID', ''),
        )
        # Then prepend audit_vars to any UPDATE SQL:
        full_sql = audit_vars + "\\n" + your_update_sql

    PostgreSQL session variables set:
        app.changed_by          — script/agent name
        app.change_source       — one of: enrichment_agent, weekend_sprint,
                                  manual_edit, migration, kyle_correction,
                                  trigger, unknown
        app.enrichment_run_id   — UUID of the enrichment_runs row (if available)
        app.session_id          — GitHub Actions run ID or session identifier
        app.change_reason       — free-text reason for the change
        app.migration_file      — migration file name (if from a migration)
        app.migration_version   — migration version string (e.g. 'v63')

    Note: SET LOCAL only applies within the current transaction, which is the
    correct scope — audit vars reset automatically after each transaction.
    """
    lines = []

    def _safe(val: str) -> str:
        """Escape single quotes for SQL string literals."""
        return (val or "").replace("'", "''")

    if changed_by:
        lines.append(f"SET LOCAL app.changed_by = '{_safe(changed_by)}';")
    if change_source:
        lines.append(f"SET LOCAL app.change_source = '{_safe(change_source)}';")
    if run_id:
        lines.append(f"SET LOCAL app.enrichment_run_id = '{_safe(run_id)}';")
    if session_id:
        lines.append(f"SET LOCAL app.session_id = '{_safe(session_id)}';")
    if change_reason:
        lines.append(f"SET LOCAL app.change_reason = '{_safe(change_reason)}';")
    if migration_file:
        lines.append(f"SET LOCAL app.migration_file = '{_safe(migration_file)}';")
    if migration_version:
        lines.append(f"SET LOCAL app.migration_version = '{_safe(migration_version)}';")

    return "\n".join(lines)
