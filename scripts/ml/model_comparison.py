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


# ══════════════════════════════════════════════════════════════════════════
# ANALYSIS — compute accuracy metrics
# ══════════════════════════════════════════════════════════════════════════

def load_validation_results() -> list:
    """
    Load all model_validation_results WHERE is_correct IS NOT NULL.
    Also joins enrichment_runs via enrichment_run_id to get script_name.
    """
    rows = sb_get("model_validation_results", {
        "is_correct": "not.is.null",
        "select":     "*",
        "limit":      "10000",
    })
    if not rows:
        print("[load_validation_results] No validated results found.")
    return rows


def enrich_with_run_metadata(rows: list) -> list:
    """
    Fetch enrichment_runs rows for all run IDs present in validation results,
    then attach script_name to each result row.
    """
    run_ids = list({r["enrichment_run_id"] for r in rows if r.get("enrichment_run_id")})
    if not run_ids:
        return rows

    # Supabase IN filter
    run_rows = sb_get("enrichment_runs", {
        "id":     f"in.({','.join(run_ids)})",
        "select": "id,script_name,model_name,prompt_version",
    })
    run_meta = {r["id"]: r for r in run_rows}

    for row in rows:
        meta = run_meta.get(row.get("enrichment_run_id"), {})
        row.setdefault("_script_name",    meta.get("script_name", "unknown"))
        row.setdefault("_prompt_version", meta.get("prompt_version", "unknown"))
        # model_name may already be on the result row; fall back to run metadata
        if not row.get("model_name"):
            row["model_name"] = meta.get("model_name", "unknown")

    return rows


def compute_accuracy_metrics(rows: list) -> dict:
    """
    Group by (model_name, field_name, script_name) and compute:
      - total validations
      - correct count
      - accuracy_rate (0-1)
      - error_rate (0-1)
      - error_type breakdown: counts per error_type
      - most_common_error_type

    Returns a dict keyed by (model_name, field_name, script_name).
    """
    # bucket[key] = {"correct": int, "total": int, "errors": defaultdict(int)}
    buckets: dict = {}

    for row in rows:
        model      = row.get("model_name") or "unknown"
        field      = row.get("field_name") or "unknown"
        script     = row.get("_script_name") or "unknown"
        is_correct = row.get("is_correct")
        error_type = row.get("error_type") or "none"

        key = (model, field, script)
        if key not in buckets:
            buckets[key] = {"correct": 0, "total": 0, "errors": defaultdict(int)}

        b = buckets[key]
        b["total"] += 1
        if is_correct:
            b["correct"] += 1
        else:
            b["errors"][error_type] += 1

    results = {}
    for (model, field, script), b in buckets.items():
        total   = b["total"]
        correct = b["correct"]
        errors  = dict(b["errors"])
        acc     = correct / total if total > 0 else None
        err_r   = (total - correct) / total if total > 0 else None
        most_common_err = max(errors, key=errors.get) if errors else None

        results[(model, field, script)] = {
            "model_name":          model,
            "field_name":          field,
            "script_name":         script,
            "total_validations":   total,
            "correct_count":       correct,
            "accuracy_rate":       round(acc, 4) if acc is not None else None,
            "error_rate":          round(err_r, 4) if err_r is not None else None,
            "error_type_counts":   errors,
            "most_common_error_type": most_common_err,
        }

    return results


def field_error_type_analysis(rows: list) -> dict:
    """
    Per field_name: which error_type is most prevalent?
    Returns: {field_name: {error_type: count, ...}, ...}
    """
    field_errors: dict = defaultdict(lambda: defaultdict(int))
    for row in rows:
        if row.get("is_correct") is False:
            field  = row.get("field_name") or "unknown"
            etype  = row.get("error_type") or "none"
            field_errors[field][etype] += 1

    return {
        field: dict(counts)
        for field, counts in field_errors.items()
    }


def identify_hallucination_fields(rows: list) -> list:
    """
    Returns field names ranked by hallucination rate (hallucination count / total errors).
    Only fields with >=3 total errors included to reduce noise.
    """
    field_totals:  dict = defaultdict(int)
    field_halluc:  dict = defaultdict(int)

    for row in rows:
        if row.get("is_correct") is False:
            field = row.get("field_name") or "unknown"
            etype = row.get("error_type") or "none"
            field_totals[field] += 1
            if etype == "hallucination":
                field_halluc[field] += 1

    ranked = []
    for field, total_errors in field_totals.items():
        if total_errors < 3:
            continue
        halluc_count = field_halluc.get(field, 0)
        halluc_rate  = halluc_count / total_errors
        ranked.append({
            "field_name":       field,
            "hallucination_count": halluc_count,
            "total_errors":     total_errors,
            "hallucination_rate": round(halluc_rate, 4),
        })

    ranked.sort(key=lambda x: x["hallucination_rate"], reverse=True)
    return ranked


def identify_stale_assumption_fields(rows: list) -> list:
    """
    Returns field names ranked by stale_assumption rate.
    """
    field_totals: dict = defaultdict(int)
    field_stale:  dict = defaultdict(int)

    for row in rows:
        if row.get("is_correct") is False:
            field = row.get("field_name") or "unknown"
            etype = row.get("error_type") or "none"
            field_totals[field] += 1
            if etype == "stale_assumption":
                field_stale[field] += 1

    ranked = []
    for field, total_errors in field_totals.items():
        if total_errors < 3:
            continue
        stale_count = field_stale.get(field, 0)
        stale_rate  = stale_count / total_errors
        ranked.append({
            "field_name":      field,
            "stale_count":     stale_count,
            "total_errors":    total_errors,
            "stale_rate":      round(stale_rate, 4),
        })

    ranked.sort(key=lambda x: x["stale_rate"], reverse=True)
    return ranked


def flag_low_accuracy_prompts(metrics: dict, threshold: float = 0.80) -> list:
    """
    Returns (script_name, field_name, model_name) triples where accuracy_rate < threshold,
    with >= 5 total validations (to avoid flagging on tiny samples).
    Sorted worst accuracy first.
    """
    flagged = []
    for key, m in metrics.items():
        acc   = m.get("accuracy_rate")
        total = m.get("total_validations", 0)
        if acc is not None and acc < threshold and total >= 5:
            flagged.append({
                "script_name":       m["script_name"],
                "model_name":        m["model_name"],
                "field_name":        m["field_name"],
                "accuracy_rate":     acc,
                "total_validations": total,
                "most_common_error": m.get("most_common_error_type"),
                "recommendation":    (
                    f"Accuracy {acc:.0%} < {threshold:.0%} threshold. "
                    f"Review enrichment prompt in {m['script_name']} for '{m['field_name']}' fields. "
                    f"Primary error: {m.get('most_common_error_type', 'unknown')}."
                ),
            })

    flagged.sort(key=lambda x: x["accuracy_rate"])
    return flagged


# ══════════════════════════════════════════════════════════════════════════
# REPORT GENERATION
# ══════════════════════════════════════════════════════════════════════════

def build_report(output_dir: str = ".") -> dict:
    """
    Full pipeline: load → enrich → analyse → write report.
    Returns the report dict.
    """
    print("Loading validation results...")
    rows = load_validation_results()

    if not rows:
        report = {
            "generated_at": NOW_ISO,
            "status": "no_data",
            "message": (
                "No validated results in model_validation_results yet. "
                "Run enrichment and validate some outputs first."
            ),
            "metrics": [],
            "hallucination_risk_fields": [],
            "stale_assumption_risk_fields": [],
            "prompts_flagged_for_review": [],
            "field_error_breakdown": {},
        }
    else:
        print(f"  {len(rows)} validated results loaded")
        rows = enrich_with_run_metadata(rows)

        metrics      = compute_accuracy_metrics(rows)
        field_errors = field_error_type_analysis(rows)
        halluc_rank  = identify_hallucination_fields(rows)
        stale_rank   = identify_stale_assumption_fields(rows)
        flagged      = flag_low_accuracy_prompts(metrics, threshold=0.80)

        # Overall summary stats
        total_validations = len(rows)
        correct_count     = sum(1 for r in rows if r.get("is_correct") is True)
        overall_accuracy  = correct_count / total_validations if total_validations > 0 else None

        report = {
            "generated_at":      NOW_ISO,
            "status":            "ok",
            "summary": {
                "total_validations":   total_validations,
                "correct_count":       correct_count,
                "overall_accuracy":    round(overall_accuracy, 4) if overall_accuracy is not None else None,
                "models_evaluated":    list({m["model_name"] for m in metrics.values()}),
                "fields_evaluated":    list({m["field_name"] for m in metrics.values()}),
                "scripts_evaluated":   list({m["script_name"] for m in metrics.values()}),
            },
            "metrics": list(metrics.values()),
            "hallucination_risk_fields": halluc_rank,
            "stale_assumption_risk_fields": stale_rank,
            "prompts_flagged_for_review": flagged,
            "field_error_breakdown": field_errors,
        }

    out_path = os.path.join(output_dir, "model_comparison_report.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Report written → {out_path}")

    # Summary to stdout
    if report.get("status") == "ok":
        s = report["summary"]
        print(f"\n=== Model Comparison Report ===")
        print(f"Total validations: {s['total_validations']}")
        print(f"Overall accuracy:  {s['overall_accuracy']:.1%}" if s['overall_accuracy'] else "Overall accuracy:  N/A")
        print(f"Models: {', '.join(s['models_evaluated'])}")
        if report["prompts_flagged_for_review"]:
            print(f"\nFLAGGED PROMPTS ({len(report['prompts_flagged_for_review'])}):")
            for f_ in report["prompts_flagged_for_review"]:
                print(f"  {f_['script_name']} / {f_['field_name']}: {f_['accuracy_rate']:.1%} ({f_['total_validations']} validations)")
        if report["hallucination_risk_fields"]:
            print(f"\nHIGHEST HALLUCINATION RISK:")
            for h in report["hallucination_risk_fields"][:5]:
                print(f"  {h['field_name']}: {h['hallucination_rate']:.1%} hallucination rate ({h['hallucination_count']}/{h['total_errors']} errors)")
    else:
        print(f"\nStatus: {report['status']} — {report.get('message', '')}")

    return report


# ══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Meridian Model Comparison Engine")
    parser.add_argument(
        "--output",
        default=".",
        help="Output directory for model_comparison_report.json (default: current dir)",
    )
    args = parser.parse_args()
    build_report(output_dir=args.output)
