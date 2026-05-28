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

    Usage in enrichment scripts:
      from model_comparison import log_enrichment_run
      run_id = log_enrichment_run('company_enrichment.py', 'claude-sonnet-4-6', 'v1.0', 'company')
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
    }
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
) -> bool:
    """
    Patch an enrichment_run row after the batch completes.
    Call at the end of run_intelligence_pipeline() with totals.
    """
    if not run_id:
        return False
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/enrichment_runs",
            headers=SB_HEADERS,
            params={"id": f"eq.{run_id}"},
            json={
                "fields_set":            fields_set,
                "run_duration_seconds":  round(run_duration_seconds, 2),
                "error_count":           error_count,
            },
            timeout=10,
        )
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"[update_enrichment_run] {e}")
        return False


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
