#!/usr/bin/env python3
"""Staged writer-enforcement rollout — runs in GitHub Actions (no local machine needed).

Phase-2 step 2: drugs enforcement is already live. This gates enabling the
companies + catalysts triggers on PROOF that the overnight cron still wrote `drugs`
successfully THROUGH the drugs trigger (i.e. the Single Writer boundary didn't break
legitimate writes).

Logic each run:
  1. Idempotent: if companies + catalysts triggers already exist -> done, exit 0.
  2. Health (all must hold):
       - drugs row count >= DRUGS_FLOOR
       - >= FRESH_MIN drug rows changed in the last FRESH_HOURS h (field_change_audit)
         => overnight writes flowed through the drugs trigger
       - governance_violations unresolved <= GOV_MAX
  3. Healthy  -> apply migrations/PROPOSED_writer_enforcement_companies_catalysts.sql,
                 then verify each boundary (headerless REST write -> 400; correct
                 X-Meridian-Actor -> 204) on a no-op same-value PATCH. exit 0.
  4. Unhealthy/verify-fail -> print diagnostics, exit 1 (workflow fails -> notify).
     Does NOT auto-drop drugs enforcement (ambiguous signal); a human/dispatch rolls
     back via the one-liner in the migration header if needed.

Env: SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_PAT. Local fallback: reads the
.supabase_* files in the repo root if the env vars are unset.
Flags: --dry-run (health + plan only, never applies).
"""
import json
import os
import pathlib
import sys
import urllib.request
import urllib.parse

REPO = pathlib.Path(__file__).resolve().parents[2]
SQL_FILE = REPO / "migrations" / "PROPOSED_writer_enforcement_companies_catalysts.sql"

DRUGS_FLOOR = 150
FRESH_HOURS = 14
FRESH_MIN = 50
GOV_MAX = 30
UA = "meridian-pipeline/1.0 (+github-actions)"


def _cred(env_name, file_name):
    v = os.environ.get(env_name)
    if v:
        return v.strip()
    f = REPO / file_name
    if f.exists():
        return f.read_text().strip()
    raise SystemExit(f"missing credential: env {env_name} or file {file_name}")


SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "https://tghntyofptvfhmtchwcv.supabase.co").strip()
REF = SUPABASE_URL.replace("https://", "").split(".supabase.co")[0]
SERVICE_KEY = _cred("SUPABASE_SERVICE_KEY", ".supabase_service_key")
PAT = _cred("SUPABASE_PAT", ".supabase_pat")


def mgmt(sql):
    """Run SQL via the Management API (direct SQL => request.headers NULL => trigger-exempt)."""
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=json.dumps({"query": sql}).encode(),
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json", "User-Agent": UA},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def rest_patch(table, where, body, actor=None):
    """REST PATCH (goes through the enforcement trigger). Returns HTTP status code."""
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
        "User-Agent": UA,
    }
    if actor:
        headers["X-Meridian-Actor"] = actor
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}?{where}",
        data=json.dumps(body).encode(), headers=headers, method="PATCH",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.request.HTTPError as e:
        return e.code


def scalar(sql):
    rows = mgmt(sql)
    return list(rows[0].values())[0] if rows else None


def triggers_present():
    rows = mgmt(
        "select tgname from pg_trigger where tgname in "
        "('trg_enforce_single_writer_companies','trg_enforce_single_writer_catalysts');"
    )
    names = {r["tgname"] for r in rows}
    return {"companies": "trg_enforce_single_writer_companies" in names,
            "catalysts": "trg_enforce_single_writer_catalysts" in names}


def health():
    drugs_n = scalar("select count(*) from drugs;")
    fresh = scalar(
        f"select count(*) from field_change_audit where table_name='drugs' "
        f"and changed_at >= now() - interval '{FRESH_HOURS} hours';"
    )
    gov = scalar("select count(*) from governance_violations where resolved = false;")
    checks = {
        "drugs_count": (drugs_n, drugs_n is not None and drugs_n >= DRUGS_FLOOR, f">= {DRUGS_FLOOR}"),
        "fresh_drug_writes": (fresh, fresh is not None and fresh >= FRESH_MIN, f">= {FRESH_MIN} in {FRESH_HOURS}h"),
        "governance_unresolved": (gov, gov is not None and gov <= GOV_MAX, f"<= {GOV_MAX}"),
    }
    return checks, all(ok for _, ok, _ in checks.values())


def verify_boundary(table, actor):
    """No-op same-value PATCH on one row: headerless -> 400, correct actor -> 204."""
    row = mgmt(f"select id from {table} limit 1;")
    if not row:
        raise SystemExit(f"verify: no rows in {table}")
    rid = row[0]["id"]
    where = f"id=eq.{urllib.parse.quote(str(rid))}"
    # field that exists on both tables and is safe to set to itself: use a no-op via the PK
    # PATCH the PK to its own value (no data change) just to trip the BEFORE UPDATE trigger.
    blocked = rest_patch(table, where, {"id": rid})              # no header
    allowed = rest_patch(table, where, {"id": rid}, actor=actor)  # correct writer
    ok = blocked == 400 and allowed in (200, 204)
    print(f"  verify {table}: headerless={blocked} (want 400), {actor}={allowed} (want 204) -> {'OK' if ok else 'FAIL'}")
    return ok


def main():
    dry = "--dry-run" in sys.argv[1:]
    print(f"Project: {REF}  | dry_run={dry}")

    present = triggers_present()
    if present["companies"] and present["catalysts"]:
        print("Already enabled: companies + catalysts triggers present. Nothing to do.")
        return 0
    print(f"Trigger state: {present}")

    checks, healthy = health()
    print("Health checks:")
    for name, (val, ok, want) in checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name} = {val}  (want {want})")

    if not healthy:
        print("NOT HEALTHY — overnight drugs cycle did not prove clean. NOT enabling companies/catalysts.")
        print("If drugs enforcement is the cause, roll back via the one-liner in "
              "migrations/APPLIED_2026-06-19_writer_enforcement_drugs.sql.")
        return 1

    if dry:
        print("DRY RUN — healthy; would apply companies + catalysts triggers and verify. Not applying.")
        return 0

    print("Healthy. Applying companies + catalysts enforcement…")
    mgmt(SQL_FILE.read_text())
    after = triggers_present()
    if not (after["companies"] and after["catalysts"]):
        print(f"ERROR: triggers not present after apply: {after}")
        return 1

    ok_c = verify_boundary("companies", "CompanyWriter")
    ok_k = verify_boundary("catalysts", "CatalystWriter")
    if not (ok_c and ok_k):
        print("Boundary verification FAILED — rolling back companies/catalysts.")
        mgmt("DROP TRIGGER IF EXISTS trg_enforce_single_writer_companies ON companies;"
             "DROP TRIGGER IF EXISTS trg_enforce_single_writer_catalysts ON catalysts;")
        return 1

    print("SUCCESS: companies + catalysts enforcement live and verified. "
          "Phase-2 single-writer boundary now covers all 3 core tables.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
