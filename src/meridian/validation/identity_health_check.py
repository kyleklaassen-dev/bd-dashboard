"""
identity_health_check.py — Identity Resolution Health Report

Runs a quick status check on the canonical drug identity layer.
Print-friendly output; safe to run any time (read-only).

Uses SUPABASE_URL + SUPABASE_SERVICE_KEY — same credentials as the enrichment
pipeline; no separate PAT required.

USAGE:
    python src/meridian/validation/identity_health_check.py
    python src/meridian/validation/identity_health_check.py --fail-on-orphans
    python src/meridian/validation/identity_health_check.py --fail-on-fuzzy-pending
    python src/meridian/validation/identity_health_check.py --fail-on-orphans --fail-on-fuzzy-pending
    python src/meridian/validation/identity_health_check.py --repair-profiles
    python src/meridian/validation/identity_health_check.py --fail-on-profile-orphans

    # Or with explicit credentials:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python src/meridian/validation/identity_health_check.py
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
        workspace  = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
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

# ── Profile / area reconciliation ────────────────────────────────────────────

def reconcile_profiles_areas(sb, dry_run: bool = False) -> list:
    """
    Ensure every company_profiles row has a matching company_areas entry.

    Orphaned profiles arise when company_enrichment.py writes a profile for an
    (company_id, area_id) pair that has no corresponding company_areas row.
    This creates silent gaps: enrichment data exists but the company never appears
    in area-scoped queries that join through company_areas.

    Returns the list of orphaned (company_id, area_id) dicts found.
    Inserts the missing company_areas rows unless dry_run=True.
    """
    profiles = sb.table("company_profiles").select("company_id,area_id").execute().data
    areas    = sb.table("company_areas").select("company_id,area_id").execute().data
    areas_set = {(r["company_id"], r["area_id"]) for r in areas}

    orphaned = [p for p in profiles if (p["company_id"], p["area_id"]) not in areas_set]

    for p in orphaned:
        if not dry_run:
            sb.table("company_areas").upsert({
                "company_id": p["company_id"],
                "area_id":    p["area_id"],
            }).execute()

    return orphaned


# ── Health check ──────────────────────────────────────────────────────────────

def health_check(
    sb,
    fail_on_orphans: bool = False,
    fail_on_fuzzy_pending: bool = False,
    fail_on_profile_orphans: bool = False,
    repair_profiles: bool = False,
) -> int:
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

    # ── 8. company_profiles ↔ company_areas sync ─────────────
    profile_orphans = reconcile_profiles_areas(sb, dry_run=not repair_profiles)
    n_profile_orphans = len(profile_orphans)
    profile_status = "✅" if n_profile_orphans == 0 else ("🔧" if repair_profiles else "⚠️ ")
    print(f"\n  company_profiles ↔ company_areas Sync {profile_status}")
    print(f"    Orphaned profiles: {n_profile_orphans}  (target: 0)")
    if n_profile_orphans > 0 and not repair_profiles:
        print(f"    (run with --repair-profiles to insert missing company_areas rows)")
    elif n_profile_orphans > 0 and repair_profiles:
        print(f"    Repaired {n_profile_orphans} missing company_areas row(s)")
    if n_profile_orphans > 0:
        for p in profile_orphans[:10]:
            print(f"      company_id={p['company_id']}  area_id={p['area_id']}")
        if n_profile_orphans > 10:
            print(f"      ... and {n_profile_orphans - 10} more")

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
    if n_profile_orphans > 0 and not repair_profiles:
        issues.append(
            f"{n_profile_orphans} company_profiles row(s) with no matching company_areas entry"
            " — run with --repair-profiles"
        )

    # ── CI failure conditions ─────────────────────────────────
    exit_code = 0
    if fail_on_orphans and orphans > 0:
        issues.append(f"[CI FAIL] --fail-on-orphans: {orphans} orphaned records found")
        exit_code = 1
    if fail_on_fuzzy_pending and pending > 0:
        issues.append(f"[CI FAIL] --fail-on-fuzzy-pending: {pending} fuzzy review(s) pending")
        exit_code = 1
    if fail_on_profile_orphans and n_profile_orphans > 0:
        issues.append(f"[CI FAIL] --fail-on-profile-orphans: {n_profile_orphans} unsynced profile(s)")
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
    parser.add_argument("--fail-on-profile-orphans", action="store_true",
                        help="Exit 1 if company_profiles rows exist with no matching company_areas")
    parser.add_argument("--repair-profiles", action="store_true",
                        help="Insert missing company_areas rows for orphaned company_profiles")
    args = parser.parse_args()

    sb   = get_supabase()
    code = health_check(
        sb,
        fail_on_orphans=args.fail_on_orphans,
        fail_on_fuzzy_pending=args.fail_on_fuzzy_pending,
        fail_on_profile_orphans=args.fail_on_profile_orphans,
        repair_profiles=args.repair_profiles,
    )
    sys.exit(code)
