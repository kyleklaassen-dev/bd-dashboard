#!/usr/bin/env python3
"""Persist results to Supabase + JSON + GitHub (§3 acquisition_scorer split)."""

import json
import base64
import urllib.request
import urllib.error
from datetime import datetime

from meridian.scoring.acquisition.common import (
    _request, post, GITHUB_TOKEN, OUTPUTS_DIR, REPO, RUN_ID, TODAY_STR,
)


def _delete_acquisition_target_rows():
    """Delete all existing acquisition_target rows so we can insert fresh ones."""
    return _request(
        "DELETE",
        "company_strategic_views?view_type=eq.acquisition_target",
    )


def write_to_supabase(results, dry_run=False):
    print("[4/6] Writing scores to Supabase (company_strategic_views)...")

    if dry_run:
        print(f"  [DRY RUN] Would write {len([r for r in results if r])} rows")
        return 0

    # Delete existing acquisition_target rows, then insert fresh set
    _delete_acquisition_target_rows()
    print("  Cleared existing acquisition_target rows")

    rows_to_insert = []
    for r in results:
        if r is None:
            continue

        cid = r["company_id"]
        priority = r["bd_priority"]
        total = r["total_score"]

        # Build a clean summary string
        summary_parts = [
            f"D1 Overlap: {r['dim1_overlap']}/20 — {r['dim1_reason']}",
            f"D2 Timing: {r['dim2_timing']}/20 — {r['dim2_reason']}",
            f"D3 Platform: {r['dim3_platform']}/20 — {r['dim3_reason']}",
            f"D4 Feasibility: {r['dim4_feasibility']}/20 — {r['dim4_reason']}",
            f"D5 Window: {r['dim5_window']}/20 — {r['dim5_reason']}",
        ]
        if r.get("constraint_note"):
            summary_parts.append(f"CONSTRAINT: {r['constraint_note']}")

        summary = " | ".join(summary_parts)

        rows_to_insert.append({
            "company_id": cid,
            "view_type": "acquisition_target",
            "summary": summary[:2000],  # safety trim
            "strategic_score": total,
            "ailux_relevance": (
                f"BD Priority: {priority} (score {total}/100). "
                f"D1={r['dim1_overlap']} D2={r['dim2_timing']} "
                f"D3={r['dim3_platform']} D4={r['dim4_feasibility']} "
                f"D5={r['dim5_window']}"
            ),
            "enrichment_run_id": None,
            "confidence_source": "model",
            "updated_at": datetime.utcnow().isoformat(),
        })

    # Batch insert in chunks of 50
    written = 0
    chunk_size = 50
    for i in range(0, len(rows_to_insert), chunk_size):
        chunk = rows_to_insert[i:i + chunk_size]
        post("company_strategic_views", chunk, prefer="return=minimal")
        written += len(chunk)

    print(f"  Wrote {written} acquisition_target rows to company_strategic_views")
    return written


# ---------------------------------------------------------------------------
# Step 5: Write to local JSON
# ---------------------------------------------------------------------------


def write_json(results):
    output_path = os.path.join(OUTPUTS_DIR, "acquisition_probability_scores.json")
    clean = [r for r in results if r is not None]
    payload = {
        "run_id": RUN_ID,
        "generated_at": datetime.utcnow().isoformat(),
        "total_companies_scored": len(clean),
        "scoring_date": TODAY_STR,
        "scores": clean,
    }
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[5/6] JSON written: {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Step 6: GitHub commit
# ---------------------------------------------------------------------------


def commit_to_github(dry_run=False):
    if dry_run:
        print("[6/6] [DRY RUN] Skipping GitHub commit")
        return

    print("[6/6] Committing to GitHub...")
    token = GITHUB_TOKEN
    api_url = f"https://api.github.com/repos/{REPO}/contents/src/meridian/scoring/acquisition_scorer.py"

    with open(os.path.abspath(__file__), "rb") as f:
        content = f.read()
    encoded = base64.b64encode(content).decode()

    # Get existing SHA
    sha = None
    req_get = urllib.request.Request(
        api_url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
    )
    try:
        with urllib.request.urlopen(req_get) as resp:
            sha = json.loads(resp.read()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"  GitHub GET warning: {e.code}", file=sys.stderr)

    payload = {
        "message": (
            f"feat: acquisition_scorer.py — Phase 3 BD probability scores "
            f"for 121 companies [{RUN_ID}]"
        ),
        "content": encoded,
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha

    req_put = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req_put) as resp:
            result = json.loads(resp.read())
            sha_short = result.get("commit", {}).get("sha", "")[:12]
            print(f"  GitHub: committed {sha_short}...")
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  GitHub commit failed: {e.code} — {err[:200]}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
