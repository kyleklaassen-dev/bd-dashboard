#!/usr/bin/env python3
"""
Rescore completeness for companies whose completeness_score is NULL.
Runs the same scoring logic as company_enrichment.py but reads current
DB state without re-enriching any content.

Usage:
  python scripts/rescore_completeness.py --area tl1a
  python scripts/rescore_completeness.py --area tl1a --company abbvie
  python scripts/rescore_completeness.py --all       # all areas
"""

import os, sys, argparse, datetime

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from _common import load_credentials  # noqa: E402
import _db                              # noqa: E402

SUPABASE_URL, SUPABASE_KEY, _ = load_credentials(require_anthropic=False)
_db.init_db(SUPABASE_URL, SUPABASE_KEY)

NOW_ISO = datetime.datetime.utcnow().isoformat() + "Z"

# ── Supabase helpers ──────────────────────────────────────────────────────────

def sb_get(table, params=""):
    """Local call sites pass a 'k=v&k2=v2' query-string fragment; split it
    and delegate to _db.sb_get's (table, params) interface."""
    p = dict(kv.split("=", 1) for kv in params.split("&")) if params else {}
    p.setdefault("limit", "500")
    return _db.sb_get(table, p)

def sb_patch(table, payload, filters):
    return _db.sb_patch(table, payload, filters)

# ── Scoring logic (mirrors _score_company_completeness in company_enrichment.py) ──

LATE_STAGE_KEYS = {"Phase 2", "Phase 2/Phase 3", "Phase 3", "Approved"}

def score_from_db_state(profile: dict, drugs: list, catalysts: list) -> dict:
    """
    Compute completeness score from current DB state (no enrichment data).
    Mirrors _score_company_completeness() but works entirely from live rows.
    """
    score = 0
    missing = []

    pi         = profile.get("platform_intelligence") or {}
    bi         = profile.get("bd_intelligence")       or {}
    key_risk   = (profile.get("key_risk")       or "").strip()
    why_matters= (profile.get("why_it_matters") or "").strip()

    # 1. platform_intelligence (20 pts)
    pi_has_content = bool(
        pi.get("facts") or pi.get("direction") or pi.get("assessment")
    ) if isinstance(pi, dict) else bool(pi)
    if pi_has_content:
        score += 20
    else:
        missing.append("company_profiles.platform_intelligence")

    # 2. bd_intelligence (20 pts)
    bi_has_content = bool(
        bi.get("transactions") or bi.get("assessment") or bi.get("profile")
    ) if isinstance(bi, dict) else bool(bi)
    if bi_has_content:
        score += 20
    else:
        missing.append("company_profiles.bd_intelligence")

    # 3–5. Drug-level fields
    all_have_summary   = bool(drugs)
    all_have_mechanism = bool(drugs)
    late_stage_drugs   = []

    for drug in drugs:
        did             = drug.get("id", "")
        drug_summary    = (drug.get("drug_summary")    or "").strip()
        mechanism_detail= (drug.get("mechanism_detail") or "").strip()
        stage           = drug.get("stage") or ""

        if not drug_summary:
            all_have_summary = False
            missing.append(f"drugs.drug_summary[{did}]")
        if not mechanism_detail:
            all_have_mechanism = False
            missing.append(f"drugs.mechanism_detail[{did}]")
        if any(p in stage for p in LATE_STAGE_KEYS):
            late_stage_drugs.append(drug)

    # 3. drug_summary (15 pts)
    if all_have_summary:
        score += 15

    # 4. key_data for Phase 2+ (10 pts)
    if late_stage_drugs:
        all_have_key_data = True
        for drug in late_stage_drugs:
            did      = drug.get("id", "")
            key_data = (drug.get("key_data") or "").strip()
            if not key_data:
                all_have_key_data = False
                missing.append(f"drugs.key_data[{did}]")
        if all_have_key_data:
            score += 10
    else:
        score += 10  # no late-stage drugs

    # 5. mechanism_detail (10 pts)
    if all_have_mechanism:
        score += 10

    # 6. Catalyst with source_url (10 pts)
    if any(c.get("source_url") for c in catalysts):
        score += 10
    else:
        missing.append("catalysts.source_url")

    # 7. key_risk + why_it_matters (10 pts)
    if key_risk and why_matters:
        score += 10
    else:
        if not key_risk:
            missing.append("company_profiles.key_risk")
        if not why_matters:
            missing.append("company_profiles.why_it_matters")

    # 8. overlap_rationale for Direct drugs (5 pts)
    direct_drugs = [d for d in drugs if d.get("overlap") == "Direct"]
    if direct_drugs:
        all_have_rationale = all(
            bool((d.get("overlap_rationale") or "").strip()) for d in direct_drugs
        )
        if all_have_rationale:
            score += 5
        else:
            for d in direct_drugs:
                if not (d.get("overlap_rationale") or "").strip():
                    missing.append(f"drugs.overlap_rationale[{d.get('id','')}]")
    else:
        score += 5

    # 9. Molecule-level fields (tracked only, no score impact)
    MOL_DESIRED = ["epitope", "affinity_kd", "fc_engineering", "lowest_active_dose"]
    mol_intel_rows = {}
    try:
        # molecule_intelligence may be embedded in drug rows or a separate table
        # For now, check drugs for these fields directly
        pass
    except Exception:
        pass

    tier = "strong" if score >= 70 else ("partial" if score >= 40 else "thin")
    return {"score": score, "tier": tier, "missing": list(dict.fromkeys(missing))}


# ── Main ──────────────────────────────────────────────────────────────────────

def rescore_company(company_id: str, area_id: str, force: bool = False) -> bool:
    print(f"\n{'='*60}")
    print(f"  Rescoring: {company_id} / {area_id}")
    print(f"{'='*60}")

    # Fetch profile
    profiles = sb_get("company_profiles",
                       f"company_id=eq.{company_id}&area_id=eq.{area_id}")
    if not profiles:
        print(f"  ⚠ No profile row found for {company_id}/{area_id} — skipping")
        return False

    profile = profiles[0]
    current_score = profile.get("completeness_score")
    current_checked = profile.get("completeness_checked_at")

    print(f"  Current completeness_score: {current_score}")
    print(f"  Current completeness_checked_at: {current_checked}")

    if current_score is not None and not force:
        print(f"  ℹ Score already set ({current_score}) — use --force to override. Skipping.")
        return True

    # Fetch drugs
    drugs = sb_get("drugs", f"company_id=eq.{company_id}&select=id,drug_summary,mechanism_detail,stage,key_data,overlap,overlap_rationale")
    print(f"  Drugs found: {len(drugs)}")

    # Fetch catalysts
    catalysts = sb_get("catalysts", f"company_id=eq.{company_id}&area_id=eq.{area_id}&select=id,source_url")
    print(f"  Catalysts found: {len(catalysts)}")

    # Compute score
    result = score_from_db_state(profile, drugs, catalysts)
    new_score  = result["score"]
    new_missing = result["missing"]
    new_tier   = result["tier"]

    print(f"\n  Computed score: {new_score} ({new_tier})")
    if new_missing:
        print(f"  Missing fields ({len(new_missing)}):")
        for f in new_missing[:10]:
            print(f"    - {f}")
        if len(new_missing) > 10:
            print(f"    ... and {len(new_missing)-10} more")
    else:
        print("  No missing fields detected ✅")

    # Score breakdown (verbose)
    pi = profile.get("platform_intelligence") or {}
    bi = profile.get("bd_intelligence") or {}
    pi_ok = bool(pi.get("facts") or pi.get("direction") or pi.get("assessment")) if isinstance(pi, dict) else bool(pi)
    bi_ok = bool(bi.get("transactions") or bi.get("assessment") or bi.get("profile")) if isinstance(bi, dict) else bool(bi)
    print(f"\n  Breakdown:")
    print(f"    platform_intelligence present: {pi_ok} ({'+20' if pi_ok else '0'})")
    print(f"    bd_intelligence present:       {bi_ok} ({'+20' if bi_ok else '0'})")
    print(f"    key_risk present:              {bool((profile.get('key_risk') or '').strip())}")
    print(f"    why_it_matters present:        {bool((profile.get('why_it_matters') or '').strip())}")
    print(f"    catalysts with source_url:     {sum(1 for c in catalysts if c.get('source_url'))}/{len(catalysts)}")

    # Write back
    ok = sb_patch("company_profiles", {
        "completeness_score":      new_score,
        "missing_fields":          new_missing,
        "completeness_checked_at": NOW_ISO,
    }, {"company_id": f"eq.{company_id}", "area_id": f"eq.{area_id}"})

    if ok:
        print(f"\n  ✅ Written: score={new_score}, missing={len(new_missing)} fields")
    else:
        print(f"\n  ❌ Failed to write score")
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--area", default=None)
    parser.add_argument("--company", default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="Rescore even if completeness_score already set")
    parser.add_argument("--null-only", action="store_true",
                        help="Only rescore where completeness_score IS NULL (default behaviour)")
    args = parser.parse_args()

    # Determine which profiles to rescore
    if args.all:
        profiles = sb_get("company_profiles", "select=company_id,area_id,completeness_score,completeness_checked_at")
    elif args.area and args.company:
        profiles = sb_get("company_profiles",
                          f"company_id=eq.{args.company}&area_id=eq.{args.area}&select=company_id,area_id,completeness_score,completeness_checked_at")
    elif args.area:
        profiles = sb_get("company_profiles",
                          f"area_id=eq.{args.area}&select=company_id,area_id,completeness_score,completeness_checked_at")
    else:
        # Default: null scores across all areas
        profiles = sb_get("company_profiles",
                          "completeness_score=is.null&select=company_id,area_id,completeness_score,completeness_checked_at")

    if not args.force and not args.all:
        # Filter to null-only unless forced
        profiles = [p for p in profiles if p.get("completeness_score") is None]

    print(f"Found {len(profiles)} profiles to rescore")
    if not profiles:
        print("Nothing to rescore. Use --force to override existing scores.")
        return

    success = 0
    failed = 0
    for p in profiles:
        ok = rescore_company(p["company_id"], p["area_id"], force=args.force)
        if ok:
            success += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"RESCORE COMPLETE: {success} succeeded, {failed} failed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
