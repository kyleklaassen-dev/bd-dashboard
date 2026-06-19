#!/usr/bin/env python3
"""
BD Platform — COMPETES_WITH Edge Seeder
========================================
Phase 1 of the relationship-completeness sprint (2026-05-24).

PURPOSE
-------
Seeds drug → COMPETES_WITH → drug edges into entity_edges using only
deterministic rules — no LLM reasoning, no inference.

RULE (first version)
--------------------
Two drugs COMPETES_WITH each other in area A when ALL of:
  1. Both have drug_area_scores.overlap = 'Direct' for area A
  2. Both share the same normalized_target (see TARGET_ALIASES below)
  3. Neither drug has status = 'Terminated'
  4. Both have a drug_areas row for area A (active in the area)

Edges are bidirectional: A→B AND B→A are both inserted so that
"WHERE subject_id=X AND predicate='COMPETES_WITH'" returns all competitors.

SCOPE RULES
-----------
• Bispecifics (targets containing '×' or '+') get their own target class
  and are NOT automatically cross-classified against monospecifics.
  Reason: TL1A×IL-23 vs TL1A-mono might compete, but that requires clinical
  judgment. Document as "uncertain" — human-reviewed in next pass.
• Drugs in multiple areas may generate edges in each area independently.

UNCERTAIN CASES (printed; NOT inserted)
----------------------------------------
Cases that need human review before COMPETES_WITH assignment:
  a) Bispecific vs monospecific with shared component target
  b) Same area, different overlap tier (one Direct, one Adjacent) — skipped by rule
  c) Target text present but not in alias map → flagged as unmapped

USAGE
-----
  # Dry run: print proposed edges only, insert nothing
  python scripts/seed_competes_with.py --dry-run

  # Run the migration against the live DB (apply entity_edges DDL + insert edges)
  python scripts/seed_competes_with.py --apply

  # Apply + run validation suite afterwards
  python scripts/seed_competes_with.py --apply --validate

ENVIRONMENT
-----------
  SUPABASE_URL, SUPABASE_SERVICE_KEY

DEPENDS ON
----------
  Migration v26_entity_edges.sql must have been applied first (or use --apply-migration).
"""

import os
import sys
import json
import datetime
import argparse
import urllib.request
import urllib.error
import ssl
from collections import defaultdict
from itertools import combinations
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from src.meridian.database.edge_writer import EdgeWriter  # governed single-writer for entity_edges

# ══════════════════════════════════════════════════════════════════════════════
# CREDENTIALS
# ══════════════════════════════════════════════════════════════════════════════

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.", file=sys.stderr)
    sys.exit(1)

ctx = ssl.create_default_context()
NOW_ISO = datetime.datetime.utcnow().isoformat() + "Z"

# ══════════════════════════════════════════════════════════════════════════════
# TARGET NORMALIZATION  → competes_targets.py (§3 split: pure data + normalizers)
# ══════════════════════════════════════════════════════════════════════════════
from competes_targets import TARGET_ALIASES, normalize_target, is_bispecific_target



# ══════════════════════════════════════════════════════════════════════════════
# SUPABASE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _headers(extra: dict | None = None):
    h = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }
    if extra:
        h.update(extra)
    return h


def sb_get(table: str, params: dict, limit: int = 2000) -> list:
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{SUPABASE_URL}/rest/v1/{table}?{qs}&limit={limit}"
    req = urllib.request.Request(url, headers=_headers({"Range": f"0-{limit-1}"}))
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", errors="replace")
        print(f"  [ERROR] GET {table}: {e.code} — {body}", file=sys.stderr)
        return []


def sb_post(table: str, payload: dict | list, upsert: bool = False) -> dict | list | None:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    prefer = "resolution=merge-duplicates,return=representation" if upsert else "return=representation"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                  headers=_headers({"Prefer": prefer}))
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()[:400].decode("utf-8", errors="replace")
        print(f"  [ERROR] POST {table}: {e.code} — {body}", file=sys.stderr)
        return None


def sb_rpc(func: str, payload: dict) -> dict | None:
    """Call a Supabase RPC / raw SQL via postgres RPC."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/{func}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                  headers=_headers())
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()[:400].decode("utf-8", errors="replace")
        print(f"  [ERROR] RPC {func}: {e.code} — {body}", file=sys.stderr)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# AUDIT — FETCH + GROUP
# ══════════════════════════════════════════════════════════════════════════════

def fetch_direct_drugs() -> dict:
    """
    Returns {drug_id: {name, target, stage, canonical_target, is_mapped}}.
    Note: drugs table uses `stage` (not `status`) for development status.
    """
    drugs = sb_get("drugs", {"select": "id,name,target,stage"})
    lookup = {}
    for d in drugs:
        canon, mapped = normalize_target(d.get("target") or "")
        lookup[d["id"]] = {
            "name":             d.get("name") or d["id"],
            "target":           (d.get("target") or "").strip(),
            "stage":            (d.get("stage") or "").lower().strip(),
            "canonical_target": canon,
            "target_is_mapped": mapped,
        }
    return lookup


def fetch_direct_das_rows() -> list[dict]:
    """Returns all drug_area_scores rows with overlap='Direct'."""
    return sb_get("drug_area_scores", {"select": "drug_id,area_id,overlap", "overlap": "eq.Direct"})


# ══════════════════════════════════════════════════════════════════════════════
# COMPETES_WITH EDGE GENERATION  → competes_edges.py (§3 split: pure transforms)
# ══════════════════════════════════════════════════════════════════════════════
from competes_edges import group_by_area_target, generate_edge_pairs, build_validation_tests



# ══════════════════════════════════════════════════════════════════════════════
# PRINTING / REPORTING
# ══════════════════════════════════════════════════════════════════════════════

def print_audit(groups: dict, safe_edges: list, uncertain_edges: list, uncertain_cases: list):
    # ANSI colors
    G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"; RESET = "\033[0m"; BOLD = "\033[1m"

    print(f"\n{BOLD}══ COMPETES_WITH Audit ══{RESET}")
    print(f"Direct drugs grouped by (area, target):")

    for (area_id, canon), drugs_in_group in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1])):
        count = len(drugs_in_group)
        color = G if count >= 2 else ""
        print(f"\n  {color}Area: {area_id:12s} | Target: {canon:25s} | {count} drug(s){RESET}")
        for d in drugs_in_group:
            mapped_badge = f"{G}✓{RESET}" if d["target_is_mapped"] else f"{Y}?{RESET}"
            print(f"    {mapped_badge} {d['drug_id']:35s} {d['name']:35s} raw_target={repr(d['target'])}")

    total_unique_pairs = len(safe_edges) // 2
    print(f"\n{BOLD}── Edge Summary ──{RESET}")
    print(f"  Safe (mapped targets, both Direct):    {G}{total_unique_pairs} unique pairs → {len(safe_edges)} directed edges{RESET}")
    print(f"  Uncertain (unmapped target):           {Y}{len(uncertain_edges)//2} unique pairs → {len(uncertain_edges)} directed edges (NOT inserted){RESET}")
    print(f"  Uncertain cases (no edges generated):  {len(uncertain_cases)}")

    if safe_edges:
        print(f"\n{BOLD}── Safe Edges to Insert ──{RESET}")
        printed_pairs: set = set()
        for e in safe_edges:
            pair = tuple(sorted([e["subject_id"], e["object_id"]])) + (e["scope_area_id"],)
            if pair not in printed_pairs:
                printed_pairs.add(pair)
                print(f"  {G}COMPETES_WITH{RESET}  {e['subject_id']:35s} ↔  {e['object_id']:35s}  [{e['scope_area_id']}]  conf={e['confidence_level']}")

    if uncertain_edges:
        print(f"\n{BOLD}{Y}── Uncertain Edges (review before inserting) ──{RESET}")
        printed_pairs = set()
        for e in uncertain_edges:
            pair = tuple(sorted([e["subject_id"], e["object_id"]])) + (e["scope_area_id"],)
            if pair not in printed_pairs:
                printed_pairs.add(pair)
                print(f"  {Y}UNCERTAIN{RESET}      {e['subject_id']:35s} ↔  {e['object_id']:35s}  [{e['scope_area_id']}]")

    if uncertain_cases:
        print(f"\n{BOLD}{Y}── Uncertain Cases (need data fix or review) ──{RESET}")
        for uc in uncertain_cases:
            print(f"  [{uc['case']}]  {uc.get('drug_id','?'):30s}  area={uc.get('area_id','?'):10s}  {uc.get('note','')}")


# ══════════════════════════════════════════════════════════════════════════════
# APPLY MIGRATION (entity_edges DDL via Supabase Management API)
# ══════════════════════════════════════════════════════════════════════════════

def apply_migration(project_id: str, pat: str) -> bool:
    """Applies v26_entity_edges.sql via Supabase Management API."""
    migration_path = os.path.join(os.path.dirname(__file__), "..", "migrations", "v26_entity_edges.sql")
    if not os.path.exists(migration_path):
        print(f"  [ERROR] Migration file not found: {migration_path}", file=sys.stderr)
        return False

    with open(migration_path) as f:
        sql = f.read()

    # Split on semicolons and apply each statement
    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]

    api_url = f"https://api.supabase.com/v1/projects/{project_id}/database/query"
    pat_ctx = ssl.create_default_context()

    success_count = 0
    for stmt in statements:
        if not stmt:
            continue
        payload = json.dumps({"query": stmt + ";"}).encode()
        req = urllib.request.Request(api_url, data=payload, method="POST",
                                      headers={
                                          "Authorization": f"Bearer {pat}",
                                          "Content-Type":  "application/json",
                                      })
        try:
            with urllib.request.urlopen(req, context=pat_ctx, timeout=30) as r:
                success_count += 1
                print(f"  ✓ Applied: {stmt[:80]}...")
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", errors="replace")
            if "already exists" in body.lower() or "duplicate" in body.lower():
                print(f"  ⚠ Already exists (skipped): {stmt[:60]}...")
                success_count += 1
            else:
                print(f"  ✗ Failed: {stmt[:60]}...\n    Error: {e.code} — {body}", file=sys.stderr)
                return False

    print(f"  Migration complete: {success_count} statements applied.")
    return True


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Seed COMPETES_WITH edges into entity_edges.")
    parser.add_argument("--dry-run",          action="store_true", help="Print proposed edges, insert nothing.")
    parser.add_argument("--apply",            action="store_true", help="Insert safe edges into entity_edges.")
    parser.add_argument("--apply-migration",  action="store_true", help="Run v26 DDL migration first, then seed.")
    parser.add_argument("--include-uncertain",action="store_true", help="Also insert uncertain edges (unmapped targets).")
    parser.add_argument("--validate",         action="store_true", help="Run validate_ground_truth.py after seeding.")
    parser.add_argument("--project-id",       default="ygjuqzfwbqjxkbplzwbk", help="Supabase project ID.")
    parser.add_argument("--pat-file",         default=".supabase_pat",   help="File containing Supabase PAT.")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Specify --dry-run to preview or --apply to insert. Add --apply-migration to run DDL first.")
        parser.print_help()
        sys.exit(0)

    # ── Optional: apply migration DDL first ───────────────────────────────────
    if args.apply_migration:
        pat_path = os.path.join(os.path.dirname(__file__), "..", args.pat_file)
        if not os.path.exists(pat_path):
            print(f"PAT file not found: {pat_path}", file=sys.stderr)
            sys.exit(1)
        with open(pat_path) as f:
            pat = f.read().strip()
        print("Applying migration v26 (entity_edges DDL)...")
        if not apply_migration(args.project_id, pat):
            print("Migration failed. Aborting.", file=sys.stderr)
            sys.exit(1)

    # ── Fetch data ─────────────────────────────────────────────────────────────
    print("Fetching Direct drugs from drug_area_scores + drugs...")
    drug_lookup   = fetch_direct_drugs()
    das_rows      = fetch_direct_das_rows()

    print(f"  {len(drug_lookup)} drugs in DB | {len(das_rows)} Direct drug_area_scores rows")

    # ── Group and generate proposed edges ─────────────────────────────────────
    groups, uncertain_cases = group_by_area_target(das_rows, drug_lookup)
    safe_edges, uncertain_edges = generate_edge_pairs(groups)

    # ── Print audit ───────────────────────────────────────────────────────────
    print_audit(groups, safe_edges, uncertain_edges, uncertain_cases)

    if args.dry_run:
        print("\n[DRY RUN] No edges were inserted.")
        return

    # ── Insert edges ───────────────────────────────────────────────────────────
    edges_to_insert = safe_edges[:]
    if args.include_uncertain:
        edges_to_insert.extend(uncertain_edges)
        print(f"\nInserting {len(edges_to_insert)} edges (safe + uncertain)...")
    else:
        print(f"\nInserting {len(edges_to_insert)} safe edges...")

    if not edges_to_insert:
        print("Nothing to insert.")
    else:
        # Route through the governed EdgeWriter: validates predicate/node-type vocab
        # and verifies BOTH endpoints exist (rejects edges to non-existent drugs →
        # this is what prevents the mk-1718/mdr-018-style phantom edges). Idempotent.
        writer = EdgeWriter(dry_run=False)
        rep = writer.write(edges_to_insert)
        inserted_total = rep["written"]
        if rep["rejected"]:
            print(f"  \u26a0 EdgeWriter rejected {len(rep['rejected'])} edge(s) (NOT written — likely orphan/invalid):")
            for r in rep["rejected"][:25]:
                print(f"      {r['edge']}: {r['errs']}")
        print(f"\n\u2705 Total edges written via EdgeWriter: {inserted_total}")
        unique_pairs = len(safe_edges) // 2
        print(f"   ({unique_pairs} unique drug pairs × 2 directed edges)")

    # ── Insert validation tests ────────────────────────────────────────────────
    tests = build_validation_tests(safe_edges)
    if tests:
        print(f"\nInserting {len(tests)} validation tests...")
        result = sb_post("validation_tests", tests, upsert=True)
        if result is None:
            print("  [ERROR] Validation test insert failed.", file=sys.stderr)
        else:
            inserted = len(result) if isinstance(result, list) else 1
            print(f"  ✓ Inserted {inserted} validation tests")
    else:
        print("No validation tests to insert.")

    # ── Optional: run validation suite ────────────────────────────────────────
    if args.validate:
        import subprocess
        print("\nRunning validation suite...")
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "validate_ground_truth.py")],
            capture_output=False
        )
        print(f"\nValidation suite exit code: {result.returncode}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n═══════════════════════════════════════════")
    print(f"COMPETES_WITH seeding complete — {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Safe edges inserted:      {len(safe_edges)}")
    print(f"  Unique competitive pairs: {len(safe_edges) // 2}")
    print(f"  Uncertain cases:          {len(uncertain_cases)}")
    print(f"  Uncertain edges skipped:  {len(uncertain_edges) // 2} pairs")
    print(f"  Validation tests added:   {len(tests)}")
    print("═══════════════════════════════════════════")


if __name__ == "__main__":
    main()
