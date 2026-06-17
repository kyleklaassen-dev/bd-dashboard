#!/usr/bin/env python3
"""
pipeline_health.py — Workflow health monitor (the missing backbone)
===================================================================
Polls the GitHub Actions API for every workflow in the dashboard repo,
records each workflow's latest run into `pipeline_runs` (history via run_id),
computes a health summary, and stamps `system_status.last_health_at` +
`health_summary` so the dashboard can surface "N pipelines healthy / M failing".

This closes the monitoring gap: before this, a workflow could fail every day
unnoticed (the Meridian Writer did). Now every run outcome is logged and the
failing/never-run set is one query away.

Env:
  GITHUB_TOKEN          (or .github_token file)  — actions:read on the repo
  SUPABASE_SERVICE_KEY  (or .supabase_service_key)
  GITHUB_REPO           default kyleklaassen-dev/bd-dashboard

Usage:
  python3 scripts/pipeline_health.py            # poll, write, summarize
  python3 scripts/pipeline_health.py --dry-run  # poll + print only, no writes
"""
import os, sys, json, argparse, datetime
import requests

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
def _f(name):
    p = os.path.join(_REPO_DIR, name)
    return open(p).read().strip() if os.path.exists(p) else ""

GH_TOKEN = os.environ.get("GITHUB_TOKEN") or _f(".github_token")
GH_REPO  = os.environ.get("GITHUB_REPO", "kyleklaassen-dev/bd-dashboard")
SB_URL   = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
SB_KEY   = os.environ.get("SUPABASE_SERVICE_KEY") or _f(".supabase_service_key")

GH_H = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github+json"}
SB_H = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}

# Workflows that are one-shot migrations / intentionally manual — excluded from "failing" health.
IGNORE = {"Apply SQL Migration", "Apply Drug Sources Migration (v37, one-shot)",
          "Evening Research Update (RETIRED)",
          ".github/workflows/apply-migration.yml",
          ".github/workflows/apply-drug-sources-migration.yml"}


def _ignored(name):
    return name in IGNORE or ("migration" in name.lower() and name.startswith(".github/"))


def gh(url, **params):
    r = requests.get(url, headers=GH_H, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def latest_runs():
    wfs = gh(f"https://api.github.com/repos/{GH_REPO}/actions/workflows", per_page=100)["workflows"]
    out = []
    for w in wfs:
        runs = gh(w["url"] + "/runs", per_page=1).get("workflow_runs", [])
        if runs:
            r = runs[0]
            out.append({
                "workflow_name": w["name"], "workflow_id": w["id"], "run_id": r["id"],
                "status": r.get("status"), "conclusion": r.get("conclusion"),
                "event": r.get("event"), "run_started_at": r.get("run_started_at") or r.get("created_at"),
                "run_html_url": r.get("html_url"),
                "is_healthy": r.get("conclusion") == "success",
            })
        else:
            out.append({
                "workflow_name": w["name"], "workflow_id": w["id"], "run_id": None,
                "status": "never_run", "conclusion": None, "event": None,
                "run_started_at": None, "run_html_url": w.get("html_url"), "is_healthy": False,
            })
    return out


def upsert_runs(rows):
    have = [r for r in rows if r["run_id"] is not None]
    if not have:
        return
    r = requests.post(f"{SB_URL}/rest/v1/pipeline_runs?on_conflict=run_id",
                      headers={**SB_H, "Prefer": "resolution=merge-duplicates,return=minimal"},
                      json=have, timeout=30)
    if r.status_code not in (200, 201, 204):
        print(f"  pipeline_runs upsert HTTP {r.status_code}: {r.text[:200]}")


def stamp_health(summary):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    requests.patch(f"{SB_URL}/rest/v1/system_status", headers={**SB_H, "Prefer": "return=minimal"},
                   params={"id": "eq.1"},
                   json={"last_health_at": now, "health_summary": summary[:500],
                         "last_pipeline_label": "health_monitor", "updated_at": now}, timeout=15)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fail-on-red", action="store_true",
                    help="Exit non-zero if any active workflow is failing (turns this job red as an alert)")
    args = ap.parse_args()

    rows = latest_runs()
    active = [r for r in rows if not _ignored(r["workflow_name"])]
    failing = [r for r in active if r["status"] != "never_run" and not r["is_healthy"]
               and r["conclusion"] not in ("skipped", "cancelled", None)]
    never = [r for r in active if r["status"] == "never_run"]
    healthy = [r for r in active if r["is_healthy"]]

    summary = (f"{len(healthy)} green / {len(failing)} failing / {len(never)} never-run "
               f"of {len(active)} active workflows @ "
               f"{datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%MZ')}")
    print(summary)
    if failing:
        print("  FAILING: " + ", ".join(sorted(r["workflow_name"] for r in failing)))
    if never:
        print("  NEVER-RUN: " + ", ".join(sorted(r["workflow_name"] for r in never)))

    if args.dry_run:
        print("(dry-run — no writes)")
        return

    upsert_runs(rows)
    stamp_health(summary)
    print(f"Wrote {len([r for r in rows if r['run_id']])} run rows to pipeline_runs; stamped system_status.")
    # The monitor SUCCEEDS at its job (recording). Use --fail-on-red to also alert via a red job.
    if args.fail_on_red and failing:
        sys.exit(1)


if __name__ == "__main__":
    main()
