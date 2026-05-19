"""
identity_health_check.py — Identity Resolution Health Report

Runs a quick status check on the canonical drug identity layer.
Print-friendly output; safe to run any time (read-only).

USAGE:
    python scripts/identity_health_check.py

    # Or with explicit credentials:
    SUPABASE_URL=... SUPABASE_PAT=... python scripts/identity_health_check.py
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone


def run_sql(pat: str, query: str) -> list[dict]:
    resp = requests.post(
        "https://api.supabase.com/v1/projects/tghntyofptvfhmtchwcv/database/query",
        headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json"},
        json={"query": query},
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Query failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json()


def health_check(pat: str):
    print("═" * 58)
    print("  Identity Resolution Health Check")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("═" * 58)

    # ── 1. Drug identity coverage ─────────────────────────────
    rows = run_sql(pat, """
        SELECT
            COUNT(*)                                          AS total_drugs,
            COUNT(canonical_drug_id)                          AS resolved,
            COUNT(*) - COUNT(canonical_drug_id)               AS unresolved,
            ROUND(
                COUNT(canonical_drug_id)::numeric / NULLIF(COUNT(*),0) * 100, 1
            )                                                 AS pct_resolved
        FROM drugs
    """)
    r = rows[0]
    resolved_pct = float(r["pct_resolved"] or 0)
    status = "✅" if resolved_pct == 100 else ("⚠️ " if resolved_pct >= 80 else "❌")
    print(f"\n  Drug Identity Coverage {status}")
    print(f"    Total drugs      : {r['total_drugs']}")
    print(f"    Resolved         : {r['resolved']}")
    print(f"    Unresolved       : {r['unresolved']}")
    print(f"    Coverage         : {resolved_pct}%  (target: 100%)")

    # ── 2. Identity confidence distribution ──────────────────
    rows = run_sql(pat, """
        SELECT
            COUNT(*) FILTER (WHERE identity_confidence >= 85)  AS high_confidence,
            COUNT(*) FILTER (WHERE identity_confidence BETWEEN 70 AND 84) AS medium,
            COUNT(*) FILTER (WHERE identity_confidence < 70)   AS low_confidence,
            COUNT(*) FILTER (WHERE canonical_drug_id IS NOT NULL) AS total_resolved
        FROM drugs
    """)
    r = rows[0]
    total_res = int(r["total_resolved"] or 0)
    high = int(r["high_confidence"] or 0)
    high_pct = round(high / total_res * 100, 1) if total_res > 0 else 0
    conf_status = "✅" if high_pct >= 95 else ("⚠️ " if high_pct >= 80 else "❌")
    print(f"\n  Identity Confidence {conf_status}")
    print(f"    High (≥85)       : {high}  ({high_pct}%  — target: 95%)")
    print(f"    Medium (70–84)   : {r['medium']}")
    print(f"    Low (<70)        : {r['low_confidence']}")

    # ── 3. Resolution method breakdown ───────────────────────
    rows = run_sql(pat, """
        SELECT identity_method, COUNT(*) AS count
        FROM drugs
        WHERE canonical_drug_id IS NOT NULL
        GROUP BY identity_method
        ORDER BY count DESC
    """)
    if rows:
        print(f"\n  Resolution Methods")
        for row in rows:
            method = row["identity_method"] or "unknown"
            print(f"    {method:<18}: {row['count']}")

    # ── 4. Canonical drug table ───────────────────────────────
    rows = run_sql(pat, """
        SELECT
            COUNT(*) FILTER (WHERE is_active = TRUE)   AS active,
            COUNT(*) FILTER (WHERE is_active = FALSE)  AS inactive,
            COUNT(*) FILTER (WHERE merged_into IS NOT NULL) AS merged
        FROM canonical_drugs
    """)
    r = rows[0]
    print(f"\n  Canonical Drug Table")
    print(f"    Active canonicals: {r['active']}")
    print(f"    Merged/retired   : {r['merged']}")

    # ── 5. Alias table ────────────────────────────────────────
    rows = run_sql(pat, """
        SELECT COUNT(*) AS total_aliases,
               COUNT(DISTINCT canonical_id) AS drugs_with_aliases
        FROM drug_aliases
    """)
    r = rows[0]
    print(f"\n  Alias Coverage")
    print(f"    Total aliases    : {r['total_aliases']}")
    print(f"    Drugs with aliases: {r['drugs_with_aliases']}")

    # ── 6. Fuzzy review flags (need human attention) ─────────
    rows = run_sql(pat, """
        SELECT COUNT(*) AS pending_reviews
        FROM identity_audit_log
        WHERE operation = 'flag_review'
    """)
    r = rows[0]
    pending = int(r["pending_reviews"] or 0)
    review_status = "✅" if pending == 0 else "⚠️ "
    print(f"\n  Fuzzy Review Queue {review_status}")
    print(f"    Pending reviews  : {pending}  (target: 0 — merge or dismiss manually)")

    if pending > 0:
        rows = run_sql(pat, """
            SELECT related_id AS input_name,
                   canonical_id AS near_match,
                   new_value->>'fuzzy_ratio' AS ratio,
                   performed_at
            FROM identity_audit_log
            WHERE operation = 'flag_review'
            ORDER BY performed_at DESC
            LIMIT 10
        """)
        print(f"\n    Top pending ({min(pending, 10)} shown):")
        for row in rows:
            print(f"      '{row['input_name']}' ~ {row['near_match']}  ratio={row['ratio']}")

    # ── 7. Orphaned drugs (broken FK) ────────────────────────
    rows = run_sql(pat, """
        SELECT COUNT(*) AS orphans
        FROM drugs d
        LEFT JOIN canonical_drugs c ON d.canonical_drug_id = c.canonical_id
        WHERE d.canonical_drug_id IS NOT NULL
          AND c.canonical_id IS NULL
    """)
    r = rows[0]
    orphans = int(r["orphans"] or 0)
    orphan_status = "✅" if orphans == 0 else "❌"
    print(f"\n  Orphaned Records {orphan_status}")
    print(f"    Broken FK refs   : {orphans}  (target: 0)")

    # ── Summary ───────────────────────────────────────────────
    issues = []
    if resolved_pct < 100:
        issues.append(f"{int(r['orphans'] if False else 0)} drugs unresolved — run one_time_migration.py")
    if high_pct < 95:
        issues.append(f"confidence <95% threshold — review low-confidence resolutions")
    if pending > 0:
        issues.append(f"{pending} fuzzy matches awaiting human review")
    if orphans > 0:
        issues.append(f"{orphans} orphaned drug records — broken canonical_drug_id FK")

    print(f"\n{'═' * 58}")
    if not issues:
        print("  ✅  All checks passed — identity layer healthy")
    else:
        print(f"  ⚠️   {len(issues)} issue(s) to address:")
        for issue in issues:
            print(f"      • {issue}")
    print("═" * 58)


if __name__ == "__main__":
    # Credentials: env vars first, then workspace files
    pat = os.environ.get("SUPABASE_PAT", "")
    if not pat:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        workspace = os.path.dirname(script_dir)
        try:
            with open(os.path.join(workspace, ".supabase_pat")) as f:
                pat = f.read().strip()
        except FileNotFoundError:
            raise SystemExit(
                "ERROR: SUPABASE_PAT env var not set and .supabase_pat file not found."
            )

    health_check(pat)
