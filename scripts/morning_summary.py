#!/usr/bin/env python3
"""
Meridian Morning Summary
Runs at 7 AM ET (11:00 UTC) daily via GitHub Actions.
Queries Supabase for overnight changes and writes a plain-text summary to
meridian_overnight_summary.txt in the repo root.
"""

import os
import json
import datetime
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}

WINDOW_HOURS = 12  # overnight window


def sb_get(table, params=None):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=SB_HEADERS,
        params=params or {},
        timeout=15,
    )
    if r.status_code != 200:
        print(f"  [WARN] {table} query failed: {r.status_code} {r.text[:200]}")
        return []
    return r.json()


def utc_now():
    return datetime.datetime.utcnow()


def since_str(hours=WINDOW_HOURS):
    cutoff = utc_now() - datetime.timedelta(hours=hours)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")


# ── 1. Enrichment runs since last night ─────────────────────────────────────
def fetch_enrichment_runs():
    cutoff = since_str()
    rows = sb_get("enrichment_runs", {
        "select": "id,started_at,completed_at,status,area_id,company_ids,drug_ids,model_used,summary",
        "started_at": f"gte.{cutoff}",
        "order": "started_at.asc",
    })
    return rows


# ── 2. Field changes since last night ────────────────────────────────────────
def fetch_field_changes():
    cutoff = since_str()
    rows = sb_get("field_change_audit", {
        "select": "table_name,entity_id,entity_type,field_name,old_value,new_value,changed_at,changed_by,change_source",
        "changed_at": f"gte.{cutoff}",
        "order": "changed_at.asc",
        "limit": 500,
    })
    return rows


# ── 3. Open governance violations ────────────────────────────────────────────
def fetch_governance_violations():
    rows = sb_get("governance_violations", {
        "select": "id,table_name,row_id,rule_name,description,detected_at",
        "resolved": "eq.false",
        "order": "detected_at.desc",
        "limit": 50,
    })
    return rows


# ── 4. Validation alerts (fail/warning) ─────────────────────────────────────
def fetch_validation_alerts():
    # Actual columns: check_status, check_type, details, updated_at
    # (not result_type, rule_name, detail, checked_at)
    rows = sb_get("drug_validation_results", {
        "select": "drug_id,check_status,check_type,details,notes,updated_at",
        "check_status": "in.(fail,warning)",
        "order": "updated_at.desc",
        "limit": 100,
    })
    return rows


# ── Resolve entity name for display ─────────────────────────────────────────
def _entity_label(row):
    etype = row.get("entity_type") or row.get("table_name") or "?"
    eid = row.get("entity_id") or "?"
    return f"{etype}/{eid}"


# ── Format summary ────────────────────────────────────────────────────────────
def format_summary(runs, changes, violations, alerts, date_str):
    lines = []
    lines.append(f"=== MERIDIAN OVERNIGHT SUMMARY — {date_str} ===")
    lines.append(f"Window: last {WINDOW_HOURS} hours (since {since_str()})")
    lines.append("")

    # ── Enrichment runs ──────────────────────────────────────────────────────
    completed_runs = [r for r in runs if r.get("status") == "completed"]
    failed_runs    = [r for r in runs if r.get("status") == "failed"]
    partial_runs   = [r for r in runs if r.get("status") == "partial"]
    running_runs   = [r for r in runs if r.get("status") == "running"]

    lines.append(f"ENRICHMENT RUNS: {len(runs)} total "
                 f"({len(completed_runs)} completed, {len(failed_runs)} failed, "
                 f"{len(partial_runs)} partial, {len(running_runs)} still running)")

    total_fields_updated = 0
    for run in runs:
        area = run.get("area_id") or "general"
        status = run.get("status") or "?"
        model = run.get("model_used") or "unknown model"
        started = (run.get("started_at") or "")[:16].replace("T", " ")
        company_ids = run.get("company_ids") or []
        drug_ids    = run.get("drug_ids") or []
        summary     = run.get("summary") or {}
        fields_upd  = summary.get("fields_updated") or 0
        total_fields_updated += fields_upd
        co_list = ", ".join(company_ids[:8]) + ("…" if len(company_ids) > 8 else "")
        lines.append(f"  [{status.upper()}] {started} UTC  area={area}  model={model}")
        if company_ids:
            lines.append(f"    Companies: {co_list}")
        if drug_ids:
            drug_list = ", ".join(drug_ids[:8]) + ("…" if len(drug_ids) > 8 else "")
            lines.append(f"    Drugs:     {drug_list}")
        if fields_upd:
            lines.append(f"    Fields updated: {fields_upd}")

    if not runs:
        lines.append("  (no enrichment runs in window)")
    lines.append("")

    # ── What changed ─────────────────────────────────────────────────────────
    lines.append(f"WHAT CHANGED: {len(changes)} field-level changes")

    # Group by entity
    entity_changes: dict = {}
    for ch in changes:
        key = (ch.get("table_name"), ch.get("entity_id"))
        entity_changes.setdefault(key, []).append(ch)

    change_count = 0
    for (tname, eid), ch_list in list(entity_changes.items())[:40]:
        etype = ch_list[0].get("entity_type") or tname or "?"
        lines.append(f"  {etype}/{eid}:")
        for ch in ch_list[:10]:
            field   = ch.get("field_name") or "?"
            old_val = (ch.get("old_value") or "null")[:80]
            new_val = (ch.get("new_value") or "null")[:80]
            by      = ch.get("changed_by") or ch.get("change_source") or "unknown"
            lines.append(f"    {field}")
            lines.append(f"      Was: {old_val}")
            lines.append(f"      Now: {new_val}  [{by}]")
        if len(ch_list) > 10:
            lines.append(f"    … and {len(ch_list) - 10} more field(s)")
        change_count += 1

    if len(entity_changes) > 40:
        lines.append(f"  … and {len(entity_changes) - 40} more entities changed")

    if not changes:
        lines.append("  (no field changes recorded in window)")
    lines.append("")

    # ── Validation alerts ────────────────────────────────────────────────────
    fail_count    = sum(1 for a in alerts if a.get("check_status") == "fail")
    warning_count = sum(1 for a in alerts if a.get("check_status") == "warning")
    lines.append(f"VALIDATION ALERTS: {len(alerts)} open "
                 f"({fail_count} fail, {warning_count} warning)")
    for alert in alerts[:30]:
        drug_id = alert.get("drug_id") or "?"
        rtype   = (alert.get("check_status") or "?").upper()
        rule    = alert.get("check_type") or "?"
        detail  = (alert.get("notes") or (json.dumps(alert.get("details")) if alert.get("details") else "") or "")[:120]
        lines.append(f"  [{rtype}] {drug_id} — {rule}: {detail}")
    if len(alerts) > 30:
        lines.append(f"  … and {len(alerts) - 30} more")
    if not alerts:
        lines.append("  (no validation alerts)")
    lines.append("")

    # ── Governance violations ────────────────────────────────────────────────
    lines.append(f"GOVERNANCE FLAGS: {len(violations)} unresolved")
    for v in violations[:20]:
        etype   = v.get("table_name") or "?"
        eid     = v.get("row_id") or "?"
        rule    = v.get("rule_name") or "?"
        detail  = (v.get("description") or "")[:120]
        created = (v.get("detected_at") or "")[:10]
        lines.append(f"  {etype}/{eid} — {rule} ({created}): {detail}")
    if len(violations) > 20:
        lines.append(f"  … and {len(violations) - 20} more")
    if not violations:
        lines.append("  (no open governance violations)")
    lines.append("")

    lines.append("=== END OF SUMMARY ===")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    now = utc_now()
    date_str = now.strftime("%Y-%m-%d %H:%M UTC")
    print(f"[morning_summary] Running at {date_str}")

    print("[morning_summary] Fetching enrichment runs…")
    runs = fetch_enrichment_runs()
    print(f"  {len(runs)} runs found")

    print("[morning_summary] Fetching field changes…")
    changes = fetch_field_changes()
    print(f"  {len(changes)} changes found")

    print("[morning_summary] Fetching governance violations…")
    violations = fetch_governance_violations()
    print(f"  {len(violations)} open violations")

    print("[morning_summary] Fetching validation alerts…")
    alerts = fetch_validation_alerts()
    print(f"  {len(alerts)} alerts")

    summary = format_summary(runs, changes, violations, alerts, date_str)

    # Determine output path — always write to repo root regardless of cwd
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root  = os.path.dirname(script_dir)
    out_path   = os.path.join(repo_root, "meridian_overnight_summary.txt")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(summary)

    print(f"[morning_summary] Summary written to {out_path}")
    print()
    print(summary)
