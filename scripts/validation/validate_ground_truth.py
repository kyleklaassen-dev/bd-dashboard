#!/usr/bin/env python3
"""
BD Platform — Ground Truth Validation Runner
=============================================
Runs all validation_tests against live Supabase data and reports pass/fail.
Designed to run after enrichment sessions to catch regressions.

Usage:
  python scripts/validate_ground_truth.py                    # all tests
  python scripts/validate_ground_truth.py --area tl1a        # TL1A tests only
  python scripts/validate_ground_truth.py --priority P1      # P1 blockers only
  python scripts/validate_ground_truth.py --type overlap_check
  python scripts/validate_ground_truth.py --fail-only        # show only failures
  python scripts/validate_ground_truth.py --write-results    # persist results to DB

Output:
  Console: colored pass/fail table
  Return code: 0 if all P1 tests pass, 1 if any P1 test fails
"""

import os, sys, json, argparse, datetime
from collections import defaultdict

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _common import load_credentials  # noqa: E402
import _db                             # noqa: E402

SUPABASE_URL, SUPABASE_KEY, _ = load_credentials(require_anthropic=False)
_db.init_db(SUPABASE_URL, SUPABASE_KEY)

NOW_ISO = datetime.datetime.utcnow().isoformat() + "Z"

# ANSI colors
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"


# ── Supabase helpers ──────────────────────────────────────────────────────────

def sb_get(table, params=None):
    """Caller's Range: 0-999 cap is reproduced as a default 'limit' (preserving
    any caller-specified limit) since _db.sb_get uses query params, not Range."""
    p = dict(params or {})
    p.setdefault("limit", "1000")
    return _db.sb_get(table, p)


sb_patch = _db.sb_patch


# ── Test evaluation ───────────────────────────────────────────────────────────

def evaluate_operator(actual: str, expected: str, operator: str) -> bool:
    """Apply the comparison operator. actual and expected are both strings."""
    if operator == "eq":
        return (actual or "").lower() == (expected or "").lower()
    elif operator == "ne":
        return (actual or "").lower() != (expected or "").lower()
    elif operator == "not_null":
        return bool(actual and actual.strip() and actual.lower() not in ("null", "none", ""))
    elif operator == "is_null":
        return not bool(actual and actual.strip() and actual.lower() not in ("null", "none", ""))
    elif operator == "contains":
        return (expected or "").lower() in (actual or "").lower()
    elif operator == "not_contains":
        return (expected or "").lower() not in (actual or "").lower()
    elif operator == "gte":
        try:
            return float(actual or 0) >= float(expected or 0)
        except ValueError:
            return False
    elif operator == "lte":
        try:
            return float(actual or 0) <= float(expected or 0)
        except ValueError:
            return False
    return False


def run_test(test: dict, cache: dict) -> tuple[str, str, str]:
    """
    Run a single test. Returns (result, actual_value, error_msg).
    result: "pass" | "fail" | "skip" | "error"
    """
    test_type = test["test_type"]
    entity_id = test["entity_id"]
    area_id   = test.get("area_id") or ""
    field     = test.get("field_name")
    expected  = test["expected_value"]
    operator  = test.get("expected_operator", "eq")

    try:
        if test_type == "overlap_check":
            # Check drugs table first, then drug_area_scores (area-specific override)
            cache_key = f"drug_area_scores:{area_id}"
            if cache_key not in cache:
                cache[cache_key] = sb_get("drug_area_scores", {"area_id": f"eq.{area_id}", "select": "drug_id,overlap"})
            # Also check drugs table directly — include stage+display_name+target so all test types reuse this cache
            if "drugs_all" not in cache:
                cache["drugs_all"] = sb_get("drugs", {"select": "id,name,overlap,stage,company_id,display_name,target,catalog_category"})

            # Find by drug_id in area scores first
            das = cache[cache_key]
            das_match = next((d for d in das if d.get("drug_id","").lower() == entity_id.lower()), None)
            if das_match:
                actual = das_match.get("overlap") or ""
            else:
                # Fall back to drugs table — check by id or name
                drugs = cache["drugs_all"]
                drug  = next((d for d in drugs
                              if d.get("id","").lower() == entity_id.lower()
                              or d.get("name","").lower() == entity_id.lower()), None)
                actual = (drug.get("overlap") or "") if drug else ""
                if not drug:
                    return "error", "", f"Drug '{entity_id}' not found in drugs table or drug_area_scores"

            passed = evaluate_operator(actual, expected, operator)
            return ("pass" if passed else "fail"), actual, ""

        elif test_type == "company_visible":
            # Check that company exists in company_areas for this area
            cache_key = f"company_areas:{area_id}"
            if cache_key not in cache:
                cache[cache_key] = sb_get("company_areas",
                                          {"area_id": f"eq.{area_id}", "select": "company_id"})
            # Handle compound entity_id format "company:area" — extract company part only
            check_company_id = entity_id.split(":")[0] if ":" in entity_id else entity_id
            matches = [r for r in cache[cache_key]
                       if r.get("company_id","").lower() == check_company_id.lower()]
            actual = "true" if matches else "false"
            passed = evaluate_operator(actual, expected, operator)
            return ("pass" if passed else "fail"), actual, ""

        elif test_type == "field_present":
            # Check a field in company_profiles
            cache_key = f"profiles:{area_id}"
            if cache_key not in cache:
                cache[cache_key] = sb_get("company_profiles",
                                          {"area_id": f"eq.{area_id}",
                                           "select": "company_id,key_risk,why_it_matters,bd_summary,vs_ailux,platform_summary,completeness_score,last_enriched_at"})
            profile = next((p for p in cache[cache_key]
                            if p.get("company_id","").lower() == entity_id.lower()), None)
            if not profile:
                return "error", "", f"No profile for {entity_id}/{area_id}"
            actual = str(profile.get(field) or "")
            passed = evaluate_operator(actual, expected, operator)
            return ("pass" if passed else "fail"), actual[:80], ""

        elif test_type in ("drug_exists", "not_hallucinated"):
            # Check that a drug with this ID or name exists (or doesn't)
            if "drugs_all" not in cache:
                cache["drugs_all"] = sb_get("drugs", {"select": "id,name,overlap,stage,company_id,display_name,target,catalog_category"})
            drug = next((d for d in cache["drugs_all"]
                         if d.get("id","").lower() == entity_id.lower()
                         or d.get("name","").lower() == entity_id.lower()), None)
            actual = "exists" if drug else "not_found"
            if test_type == "drug_exists":
                passed = actual == "exists"
            else:  # not_hallucinated
                passed = actual == "not_found"
            return ("pass" if passed else "fail"), actual, ""

        elif test_type == "stage_check":
            if "drugs_all" not in cache:
                cache["drugs_all"] = sb_get("drugs", {"select": "id,name,overlap,stage,company_id,display_name,target,catalog_category"})
            drug = next((d for d in cache["drugs_all"]
                         if d.get("id","").lower() == entity_id.lower()
                         or d.get("name","").lower() == entity_id.lower()), None)
            if not drug:
                return "error", "", f"Drug '{entity_id}' not found"
            actual = drug.get("stage") or ""
            passed = evaluate_operator(actual, expected, operator)
            return ("pass" if passed else "fail"), actual, ""

        elif test_type == "company_check":
            # Two modes:
            # 1. entity_type='company' + field_name set → check companies table field directly
            # 2. entity_type='drug' (default) → verify a drug belongs to a specific company
            _entity_type = test.get("entity_type") or "drug"
            if _entity_type == "company" and field:
                # Direct company field check (e.g. status, hq_country)
                if "companies_all" not in cache:
                    cache["companies_all"] = sb_get("companies",
                        {"select": "id,name,status,hq_country,parent_company_id"})
                company = next((c for c in cache["companies_all"]
                                if c.get("id","").lower() == entity_id.lower()), None)
                if not company:
                    return "error", "", f"Company '{entity_id}' not found"
                actual = str(company.get(field) or "")
                passed = evaluate_operator(actual, expected, operator)
                return ("pass" if passed else "fail"), actual, ""
            else:
                # Drug ownership check
                if "drugs_all" not in cache:
                    cache["drugs_all"] = sb_get("drugs", {"select": "id,name,overlap,stage,company_id,display_name,target,catalog_category"})
                drug = next((d for d in cache["drugs_all"]
                             if d.get("id","").lower() == entity_id.lower()
                             or d.get("name","").lower() == entity_id.lower()), None)
                if not drug:
                    return "error", "", f"Drug '{entity_id}' not found"
                actual = drug.get("company_id") or ""
                passed = evaluate_operator(actual, expected, operator)
                return ("pass" if passed else "fail"), actual, ""

        elif test_type == "display_name_check":
            # Verify a drug's display_name contains (or doesn't contain) a given string.
            # Use field_name to pick which field to inspect (default: display_name).
            # Use expected_operator = "not_contains" to assert a string must NOT appear.
            # Example use case: lq080 display_name must not contain "ZW191".
            if "drugs_all" not in cache:
                cache["drugs_all"] = sb_get("drugs", {"select": "id,name,overlap,stage,company_id,display_name,target,catalog_category"})
            drug = next((d for d in cache["drugs_all"]
                         if d.get("id","").lower() == entity_id.lower()
                         or d.get("name","").lower() == entity_id.lower()), None)
            if not drug:
                return "error", "", f"Drug '{entity_id}' not found"
            check_field = field or "display_name"
            actual = str(drug.get(check_field) or "")
            passed = evaluate_operator(actual, expected, operator)
            # Show a truncated version of the actual value
            display_actual = actual[:80] if actual else "(empty)"
            return ("pass" if passed else "fail"), display_actual, ""

        elif test_type == "catalog_visibility":
            # Verify a drug has catalog_category set (is visible in Drugs to Know tab).
            # Core invariant: any drug with drug_areas entries MUST have catalog_category != null.
            # expected_value = the expected category string, or use operator "not_null" to just assert non-null.
            if "drugs_all" not in cache:
                cache["drugs_all"] = sb_get("drugs", {"select": "id,name,overlap,stage,company_id,display_name,target,catalog_category"})
            drug = next((d for d in cache["drugs_all"]
                         if d.get("id","").lower() == entity_id.lower()
                         or d.get("name","").lower() == entity_id.lower()), None)
            if not drug:
                return "error", "", f"Drug '{entity_id}' not found"
            actual = str(drug.get("catalog_category") or "")
            # Special handling: operator "not_null" passes when catalog_category is non-empty
            if operator == "not_null":
                passed = bool(actual and actual.strip() and actual.lower() not in ("null", "none", ""))
            else:
                passed = evaluate_operator(actual, expected, operator)
            return ("pass" if passed else "fail"), actual or "(null)", ""

        elif test_type == "drug_area_interpretation_check":
            # Rule E2: If drug_areas exists for drug×area, drug_area_scores must also exist.
            # drug_areas   = area membership (drug appears in that area tab)
            # drug_area_scores = area-specific interpretation (overlap, confidence, rationale)
            # A drug should not appear in an area without interpretation.
            # entity_id = "drug_id:area_id"
            if ":" not in entity_id:
                return "error", "", f"drug_area_interpretation_check requires entity_id='drug_id:area_id', got '{entity_id}'"
            drug_id_check, area_id_check = entity_id.split(":", 1)
            if "drug_area_scores_all" not in cache:
                cache["drug_area_scores_all"] = sb_get("drug_area_scores", {"select": "drug_id,area_id"})
            exists = any(
                r.get("drug_id") == drug_id_check and r.get("area_id") == area_id_check
                for r in cache["drug_area_scores_all"]
            )
            actual = "true" if exists else "false"
            passed = evaluate_operator(actual, expected, operator)
            return ("pass" if passed else "fail"), actual, ""

        elif test_type == "drug_area_score_check":
            # Rule E4: If drug_area_scores exists for drug×area, drug_areas must also exist.
            # drug_area_scores = area-specific interpretation (overlap, confidence, source)
            # drug_areas       = area membership (the drug appears in that area tab)
            # A score must not exist without membership.
            # entity_id = "drug_id:area_id"
            if ":" not in entity_id:
                return "error", "", f"drug_area_score_check requires entity_id='drug_id:area_id', got '{entity_id}'"
            drug_id_check, area_id_check = entity_id.split(":", 1)
            if "drug_areas_all" not in cache:
                cache["drug_areas_all"] = sb_get("drug_areas", {"select": "drug_id,area_id"})
            exists = any(
                r.get("drug_id") == drug_id_check and r.get("area_id") == area_id_check
                for r in cache["drug_areas_all"]
            )
            actual = "true" if exists else "false"
            passed = evaluate_operator(actual, expected, operator)
            return ("pass" if passed else "fail"), actual, ""

        elif test_type == "drug_identity_check":
            # Rule E5: If a drug has a drug_areas row, its core identity fields must be complete.
            # Required fields: display_name (or name), company_id, target, stage,
            #                  catalog_category, canonical_drug_id (where applicable)
            # entity_id = drug_id
            # field_name = which identity field to check
            # operator   = "not_null" (default) to assert non-empty value
            if "drugs_identity" not in cache:
                cache["drugs_identity"] = sb_get("drugs", {
                    "select": "id,name,display_name,company_id,target,stage,catalog_category,canonical_drug_id,modality"
                })
            drug = next((d for d in cache["drugs_identity"]
                         if d.get("id", "").lower() == entity_id.lower()), None)
            if not drug:
                return "error", "", f"Drug '{entity_id}' not found in drugs table"
            check_field = field or "display_name"
            # Special case: display_name — accept either display_name or name as fallback
            if check_field == "display_name":
                actual = str(drug.get("display_name") or drug.get("name") or "")
            else:
                actual = str(drug.get(check_field) or "")
            if operator == "not_null":
                passed = bool(actual and actual.strip() and actual.lower() not in ("null", "none", ""))
            else:
                passed = evaluate_operator(actual, expected, operator)
            return ("pass" if passed else "fail"), actual[:80] or "(null)", ""

        elif test_type == "company_area_check":
            # Rule E3: If a company_profiles row exists for company×area,
            # then company_areas must also have a row for that pair.
            # Also used as a standalone check: entity_id = "company_id:area_id".
            # Splits entity_id on ":" to get company_id and area_id.
            # expected_value should be "true" and operator "eq".
            if ":" not in entity_id:
                return "error", "", f"company_area_check requires entity_id='company_id:area_id', got '{entity_id}'"
            co_id, area_id_check = entity_id.split(":", 1)
            if "company_areas_all" not in cache:
                cache["company_areas_all"] = sb_get("company_areas", {"select": "company_id,area_id"})
            exists = any(
                r.get("company_id") == co_id and r.get("area_id") == area_id_check
                for r in cache["company_areas_all"]
            )
            actual = "true" if exists else "false"
            passed = evaluate_operator(actual, expected, operator)
            return ("pass" if passed else "fail"), actual, ""

        elif test_type == "intel_attribution_check":
            # Checks that intel rows linked via intel_companies have primary_company_id set.
            # entity_id is ignored (global check). expected_value = "0" (zero orphans).
            if "intel_attribution" not in cache:
                ic_rows = sb_get("intel_companies", {"select": "intel_id", "limit": "2000"})
                ic_ids  = {str(r["intel_id"]) for r in ic_rows}
                intel_rows = sb_get("intel", {"select": "id,primary_company_id", "limit": "2000"})
                orphans = sum(
                    1 for r in intel_rows
                    if str(r["id"]) in ic_ids and not r.get("primary_company_id")
                )
                cache["intel_attribution"] = orphans
            actual = str(cache["intel_attribution"])
            passed = evaluate_operator(actual, expected, operator)
            return ("pass" if passed else "fail"), actual, ""

        elif test_type == "confidence_requires_source":
            # E6: Any drug_area_scores row with confidence_level='confirmed' must have
            # source_url populated. entity_id is ignored (global constraint check).
            # expected_value='0', operator='eq' → zero violations is passing.
            if "das_confidence_violations" not in cache:
                das_rows = sb_get("drug_area_scores", {
                    "select":            "drug_id,area_id,confidence_level,source_url",
                    "confidence_level":  "eq.confirmed",
                    "limit":             "2000",
                })
                violations = [r for r in das_rows if not (r.get("source_url") or "").strip()]
                cache["das_confidence_violations"] = violations
            violations = cache["das_confidence_violations"]
            count  = len(violations)
            actual = str(count)
            passed = evaluate_operator(actual, expected, operator)
            if violations and not passed:
                sample     = violations[:3]
                sample_str = "; ".join(f"{r['drug_id']}×{r['area_id']}" for r in sample)
                suffix     = f" (e.g. {sample_str})" if sample_str else ""
                return "fail", f"{actual} violations{suffix}", ""
            return ("pass" if passed else "fail"), actual, ""

        elif test_type == "source_url_integrity":
            # E10: Checks that no confirmed/supported source_url in drug_area_scores resolves
            # to a broken URL (as tracked in source_verifications).
            # Requires audit_sources.py to have been run first (populates source_verifications).
            # entity_id='system', expected_value='0', operator='eq' → zero broken-verified rows.
            if "source_url_integrity_violations" not in cache:
                # Pull drug_area_scores rows that have a source_url and meaningful confidence
                das_rows = sb_get("drug_area_scores", {
                    "select":           "drug_id,area_id,confidence_level,source_url",
                    "confidence_level": "in.(confirmed,supported)",
                    "source_url":       "not.is.null",
                    "limit":            "2000",
                })
                # Pull broken URLs from source_verifications (if table exists)
                try:
                    broken_rows = sb_get("source_verifications", {
                        "select":        "url,source_status",
                        "source_status": "in.(broken,timeout)",
                        "limit":         "2000",
                    })
                    broken_set = {r["url"] for r in broken_rows}
                except Exception:
                    broken_set = set()  # table may not exist yet — skip
                violations = [r for r in das_rows if (r.get("source_url") or "") in broken_set]
                cache["source_url_integrity_violations"] = violations
            violations = cache["source_url_integrity_violations"]
            count  = len(violations)
            actual = str(count)
            passed = evaluate_operator(actual, expected, operator)
            if violations and not passed:
                sample     = violations[:3]
                sample_str = "; ".join(
                    f"{r['drug_id']}×{r['area_id']} ({r['confidence_level']})" for r in sample
                )
                return "fail", f"{actual} broken confirmed/supported sources ({sample_str})", ""
            return ("pass" if passed else "fail"), actual, ""

        elif test_type == "competes_with_edge_exists":
            # E9: Verifies that a COMPETES_WITH edge exists in entity_edges for the given drug pair.
            # entity_id     = subject drug_id
            # expected_value = object drug_id (the competitor)
            # area_id        = scope_area_id (optional — empty means any area)
            # operator       = "eq" (edge exists) or "neq" (edge must NOT exist)
            if "entity_edges_compete" not in cache:
                cache["entity_edges_compete"] = sb_get("entity_edges", {
                    "select":    "subject_id,object_id,scope_area_id,status",
                    "predicate": "eq.COMPETES_WITH",
                    "status":    "eq.active",
                })
            edges = cache["entity_edges_compete"]
            if area_id:
                match = any(
                    e["subject_id"] == entity_id
                    and e["object_id"] == expected
                    and (e.get("scope_area_id") or "") == area_id
                    for e in edges
                )
            else:
                match = any(
                    e["subject_id"] == entity_id and e["object_id"] == expected
                    for e in edges
                )
            actual = "exists" if match else "not_found"
            if operator in ("eq", "not_null"):
                passed = match
            elif operator == "neq":
                passed = not match
            else:
                passed = match
            return ("pass" if passed else "fail"), actual, ""

        else:
            return "skip", "", f"Unknown test_type: {test_type}"

    except Exception as e:
        return "error", "", str(e)[:120]


# ── Reporting ─────────────────────────────────────────────────────────────────

RESULT_ICONS = {"pass": f"{GREEN}✅{RESET}", "fail": f"{RED}❌{RESET}",
                "skip": f"{YELLOW}⏭ {RESET}", "error": f"{YELLOW}⚠ {RESET}"}

def print_report(results: list, fail_only: bool = False):
    # Group by test_type
    by_type = defaultdict(list)
    for r in results:
        by_type[r["test_type"]].append(r)

    total = len(results)
    passed = sum(1 for r in results if r["result"] == "pass")
    failed = sum(1 for r in results if r["result"] == "fail")
    errors = sum(1 for r in results if r["result"] in ("error", "skip"))

    p1_fails = [r for r in results if r["result"] == "fail" and r["priority"] == "P1"]

    print(f"\n{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}  BD Platform — Ground Truth Validation Report{RESET}")
    print(f"  {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{BOLD}{'='*70}{RESET}")
    print(f"\n  {GREEN}{passed}{RESET} passed  |  {RED}{failed}{RESET} failed  |  {YELLOW}{errors}{RESET} skipped/error  |  {total} total")

    if p1_fails:
        print(f"\n  {RED}{BOLD}⛔ {len(p1_fails)} P1 BLOCKER FAILURE(S){RESET}")
    else:
        print(f"\n  {GREEN}✅ All P1 tests passing{RESET}")

    for test_type, type_results in sorted(by_type.items()):
        type_fails = sum(1 for r in type_results if r["result"] == "fail")
        type_label = f"{RED}{test_type} ({type_fails} fail){RESET}" if type_fails else f"{DIM}{test_type}{RESET}"
        print(f"\n  {BOLD}{type_label}{RESET}")

        for r in sorted(type_results, key=lambda x: (x["result"] != "fail", x["priority"], x["test_name"])):
            if fail_only and r["result"] == "pass":
                continue
            icon    = RESULT_ICONS.get(r["result"], "?")
            pri     = f"[{r['priority']}]"
            name    = r["test_name"][:44]
            actual  = r.get("actual", "")
            expected= r["expected_value"]
            err     = r.get("error_msg", "")

            if r["result"] == "pass":
                print(f"    {icon} {DIM}{pri:4} {name:<44} → {actual}{RESET}")
            elif r["result"] == "fail":
                print(f"    {icon} {RED}{pri:4} {name:<44}{RESET}  expected={expected!r}  got={actual!r}")
            else:
                print(f"    {icon} {YELLOW}{pri:4} {name:<44}  {err}{RESET}")

    print(f"\n{BOLD}{'='*70}{RESET}\n")
    return failed, p1_fails


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--area",         default=None, help="Filter by area_id")
    parser.add_argument("--priority",     default=None, help="P1, P2, or P3")
    parser.add_argument("--type",         default=None, help="Test type filter")
    parser.add_argument("--fail-only",    action="store_true")
    parser.add_argument("--write-results",action="store_true",
                        help="Write pass/fail results back to validation_tests table")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_SERVICE_KEY not set", file=sys.stderr)
        sys.exit(1)

    # Load tests
    params = {"select": "*", "order": "priority.asc,test_type.asc,test_name.asc"}
    if args.area:
        params["area_id"] = f"eq.{args.area}"
    if args.priority:
        params["priority"] = f"eq.{args.priority}"
    if args.type:
        params["test_type"] = f"eq.{args.type}"

    tests = sb_get("validation_tests", params)
    if not tests:
        print("No validation tests found. Run migrations/_archive/from-migrations/v15_validation_tests.sql first.")
        sys.exit(0)

    print(f"\nLoaded {len(tests)} validation tests...")

    # Run tests (shared cache to minimize DB calls)
    cache = {}
    results = []
    for test in tests:
        result, actual, error_msg = run_test(test, cache)
        results.append({
            **test,
            "result":    result,
            "actual":    actual,
            "error_msg": error_msg,
        })
        # Progress indicator
        icon = "✅" if result == "pass" else ("❌" if result == "fail" else "⏭")
        print(f"  {icon} {test['test_name'][:60]}", end="\r", flush=True)

    print(" " * 70, end="\r")  # clear progress line

    # Print report
    failed_count, p1_fails = print_report(results, fail_only=args.fail_only)

    # Write results back to DB if requested
    if args.write_results:
        print("Writing results to validation_tests table...")
        written = 0
        for r in results:
            consecutive_failures = (r.get("consecutive_failures") or 0)
            if r["result"] == "fail":
                consecutive_failures += 1
            elif r["result"] == "pass":
                consecutive_failures = 0

            payload = {
                "last_checked_at":      NOW_ISO,
                "last_actual_value":    r.get("actual", "")[:200],
                "last_pass_fail":       r["result"],
                "consecutive_failures": consecutive_failures,
            }
            if r["result"] == "fail":
                payload["last_failure_at"] = NOW_ISO

            ok = sb_patch("validation_tests", payload, {"id": f"eq.{r['id']}"})
            if ok:
                written += 1
        print(f"  ✅ {written}/{len(results)} results written to DB")

    # Exit code: 1 if any P1 tests failed
    sys.exit(1 if p1_fails else 0)


if __name__ == "__main__":
    main()
