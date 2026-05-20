"""
identity_health_check.py — Identity Resolution Health Report

Runs a quick status check on the canonical drug identity layer.
Print-friendly output; safe to run any time (read-only).

Uses SUPABASE_URL + SUPABASE_SERVICE_KEY — same credentials as the enrichment
pipeline; no separate PAT required.

USAGE:
    python scripts/identity_health_check.py
    python scripts/identity_health_check.py --fail-on-orphans
    python scripts/identity_health_check.py --fail-on-fuzzy-pending
    python scripts/identity_health_check.py --fail-on-orphans --fail-on-fuzzy-pending

    # Or with explicit credentials:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python scripts/identity_health_check.py
"""

import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timezone

from supabase import create_client


# ── Credentials ───────────────────────────────────────────────────────────────

def get_supabase():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not url or not key:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        workspace  = os.path.dirname(script_dir)
        if not url:
            try:
                with open(os.path.join(workspace, ".supabase_url")) as f:
                    url = f.read().strip()
            except FileNotFoundError:
                pass
        if not key:
            try:
                with open(os.path.join(workspace, ".supabase_service_key")) as f:
                    key = f.read().strip()
            except FileNotFoundError:
                pass

    if not url or not key:
        raise SystemExit(
            "ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set "
            "(env vars or .supabase_url / .supabase_service_key files)."
        )

    return create_client(url, key)


# ── Health check ──────────────────────────────────────────────────────────────

def health_check(sb, fail_on_orphans: bool = False, fail_on_fuzzy_pending: bool = False) -> int:
    """Run the health check. Returns exit code: 0 = healthy, 1 = failure condition triggered."""
    print("═" * 58)
    print("  Identity Resolution Health Check")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("═" * 58)

    # ── 1. Drug identity coverage ─────────────────────────────
    drug_rows = sb.table("drugs").select(
        "canonical_drug_id, identity_confidence, identity_method"
    ).execute().data

    total_drugs     = len(drug_rows)
    resolved_rows   = [r for r in drug_rows if r.get("canonical_drug_id")]
    resolved        = len(resolved_rows)
    unresolved_count = total_drugs - resolved
    resolved_pct    = round(resolved / total_drugs * 100, 1) if total_drugs > 0 else 0.0

    status = "✅" if resolved_pct == 100 else ("⚠️ " if resolved_pct >= 80 else "❌")
    print(f"\n  Drug Identity Coverage {status}")
    print(f"    Total drugs      : {total_drugs}")
    print(f"    Resolved         : {resolved}")
    print(f"    Unresolved       : {unresolved_count}")
    print(f"    Coverage         : {resolved_pct}%  (target: 100%)")

    # ── 2. Identity confidence distribution ──────────────────
    high   = sum(1 for r in resolved_rows if (r.get("identity_confidence") or 0) >= 85)
    medium = sum(1 for r in resolved_rows if 70 <= (r.get("identity_confidence") or 0) < 85)
    low    = sum(1 for r in resolved_rows if (r.get("identity_confidence") or 0) < 70)
    high_pct = round(high / resolved * 100, 1) if resolved > 0 else 0.0

    conf_status = "✅" if high_pct >= 95 else ("⚠️ " if high_pct >= 80 else "❌")
    print(f"\n  Identity Confidence {conf_status}")
    print(f"    High (≥85)       : {high}  ({high_pct}%  — target: 95%)")
    print(f"    Medium (70–84)   : {medium}")
    print(f"    Low (<70)        : {low}")

    # ── 3. Resolution method breakdown ───────────────────────
    method_counts = Counter(r.get("identity_method") or "unknown" for r in resolved_rows)
    if method_counts:
        print(f"\n  Resolution Methods")
        for method, count in sorted(method_counts.items(), key=lambda x: -x[1]):
            print(f"    {method:<18}: {count}")

    # ── 4. Canonical drug table ───────────────────────────────
    canon_rows = sb.table("canonical_drugs").select(
        "canonical_id, is_active, merged_into"
    ).execute().data

    active = sum(1 for r in canon_rows if r.get("is_active") is True)
    merged = sum(1 for r in canon_rows if r.get("merged_into") is not None)
    print(f"\n  Canonical Drug Table")
    print(f"    Active canonicals: {active}")
    print(f"    Merged/retired   : {merged}")

    # ── 5. Alias table ────────────────────────────────────────
    alias_rows = sb.table("drug_aliases").select("canonical_id").execute().data
    total_aliases      = len(alias_rows)
    drugs_with_aliases = len(set(r["canonical_id"] for r in alias_rows if r.get("canonical_id")))
    print(f"\n  Alias Coverage")
    print(f"    Total aliases    : {total_aliases}")
    print(f"    Drugs with aliases: {drugs_with_aliases}")

    # ── 6. Fuzzy review flags (need human attention) ─────────
    fuzzy_rows = (
        sb.table("identity_audit_log")
        .select("related_id, canonical_id, new_value, performed_at")
        .eq("operation", "flag_review")
        .order("performed_at", desc=True)
        .execute()
        .data
    )
    pending = len(fuzzy_rows)
    review_status = "✅" if pending == 0 else "⚠️ "
    print(f"\n  Fuzzy Review Queue {review_status}")
    print(f"    Pending reviews  : {pending}  (target: 0 — merge or dismiss manually)")
    if pending > 0:
        print(f"\n    Top pending ({min(pending, 10)} shown):")
        for row in fuzzy_rows[:10]:
            ratio = (row.get("new_value") or {}).get("fuzzy_ratio", "?")
            print(f"      '{row.get('related_id')}' ~ {row.get('canonical_id')}  ratio={ratio}")

    # ── 7. Orphaned drugs (broken FK) ────────────────────────
    drug_canon_ids  = {r["canonical_drug_id"] for r in drug_rows if r.get("canonical_drug_id")}
    valid_canon_ids = {r["canonical_id"] for r in canon_rows if r.get("canonical_id")}
    orphans         = len(drug_canon_ids - valid_canon_ids)
    orphan_status   = "✅" if orphans == 0 else "❌"
    print(f"\n  Orphaned Records {orphan_status}")
    print(f"    Broken FK refs   : {orphans}  (target: 0)")

    # ── Summary ───────────────────────────────────────────────
    issues: list[str] = []
    if resolved_pct < 100:
        issues.append(
            f"{unresolved_count} drug{'' if unresolved_count == 1 else 's'} unresolved "
            "— run one_time_migration.py"
        )
    if high_pct < 95:
        issues.append("confidence <95% threshold — review low-confidence resolutions")
    if pending > 0:
        issues.append(f"{pending} fuzzy matches awaiting human review")
    if orphans > 0:
        issues.append(f"{orphans} orphaned drug records — broken canonical_drug_id FK")

    # ── CI failure conditions ─────────────────────────────────
    exit_code = 0
    if fail_on_orphans and orphans > 0:
        issues.append(f"[CI FAIL] --fail-on-orphans: {orphans} orphaned records found")
        exit_code = 1
    if fail_on_fuzzy_pending and pending > 0:
        issues.append(f"[CI FAIL] --fail-on-fuzzy-pending: {pending} fuzzy review(s) pending")
        exit_code = 1

    print(f"\n{'═' * 58}")
    if not issues:
        print("  ✅  All checks passed — identity layer healthy")
    else:
        ci_issues   = [i for i in issues if i.startswith("[CI FAIL]")]
        warn_issues = [i for i in issues if not i.startswith("[CI FAIL]")]
        if warn_issues:
            print(f"  ⚠️   {len(warn_issues)} issue(s) to address:")
            for issue in warn_issues:
                print(f"      • {issue}")
        if ci_issues:
            print(f"\n  ❌  {len(ci_issues)} CI failure condition(s):")
            for issue in ci_issues:
                print(f"      • {issue.replace('[CI FAIL] ', '')}")
    print("═" * 58)
    return exit_code


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Identity layer health check")
    parser.add_argument("--fail-on-orphans", action="store_true",
                        help="Exit 1 if any orphaned drug records are found")
    parser.add_argument("--fail-on-fuzzy-pending", action="store_true",
                        help="Exit 1 if any fuzzy-match reviews are pending")
    args = parser.parse_args()

    sb   = get_supabase()
    code = health_check(sb, fail_on_orphans=args.fail_on_orphans,
                        fail_on_fuzzy_pending=args.fail_on_fuzzy_pending)
    sys.exit(code)
