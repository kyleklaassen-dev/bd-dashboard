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
# TARGET NORMALIZATION
# ══════════════════════════════════════════════════════════════════════════════

# Maps raw drug.target text values → canonical target IDs.
# Conservative: only exact/near-exact synonyms. No biological inference.
# Bispecifics (containing × or /) are kept as-is after lowercasing.
TARGET_ALIASES: dict[str, str] = {
    # TL1A / TNFSF15
    "tl1a":                 "tl1a",
    "tnfsf15":              "tl1a",
    "tl1a/tnfsf15":         "tl1a",
    "tnfsf15 (tl1a)":       "tl1a",
    "tl1a (tnfsf15)":       "tl1a",

    # IL-23 p19 subunit
    "il-23p19":             "il23p19",
    "il23p19":              "il23p19",
    "il-23":                "il23p19",
    "il23":                 "il23p19",
    "il-23 (p19)":          "il23p19",

    # FcRn / neonatal Fc receptor
    "fcrn":                 "fcrn",
    "fcgrt":                "fcrn",
    "neonatal fc receptor": "fcrn",
    "neonatal fcrn":        "fcrn",
    "fc receptor":          "fcrn",  # loose but common
    "fcrn (fcgrt)":         "fcrn",

    # TSLP
    "tslp":                 "tslp",
    "thymic stromal lymphopoietin": "tslp",

    # IL-4 receptor alpha
    "il-4rα":               "il4ra",
    "il-4ra":               "il4ra",
    "il4ra":                "il4ra",
    "il4r":                 "il4ra",
    "il-4r":                "il4ra",
    "il-4rα/il-13rα1":      "il4ra",  # dupilumab mechanism; keep as il4ra for competition
    "il4rα":                "il4ra",

    # IL-33
    "il-33":                "il33",
    "il33":                 "il33",

    # IGF-1R
    "igf-1r":               "igf1r",
    "igf1r":                "igf1r",
    "igf1":                 "igf1r",
    "igfr":                 "igf1r",

    # BCMA / TNFRSF17
    "bcma":                 "bcma",
    "tnfrsf17":             "bcma",
    "bcma (tnfrsf17)":      "bcma",

    # IL-13
    "il-13":                "il13",
    "il13":                 "il13",

    # IL-31RA
    "il-31ra":              "il31ra",
    "il31ra":               "il31ra",

    # IL-5 / IL-5Rα
    "il-5":                 "il5",
    "il5":                  "il5",
    "il-5rα":               "il5ra",
    "il-5ra":               "il5ra",
    "il5ra":                "il5ra",

    # OX40 / OX40L
    "ox40l":                "ox40l",
    "ox40":                 "ox40",

    # CD19 (standalone — not bispecific)
    "cd19":                 "cd19",

    # T-cell engager bispecifics (each target pair is its own class)
    "bcma × cd3":           "bcma_cd3",
    "bcma×cd3":             "bcma_cd3",
    "bcmaXcd3":             "bcma_cd3",
    "bcma × cd19 × cd3":    "bcma_cd19_cd3",
    "cd19×bcma×cd3":        "bcma_cd19_cd3",
    "cd19 × cd3":           "cd19_cd3",
    "cd19×cd3":             "cd19_cd3",
    "cd3×cd19":             "cd19_cd3",
    "cd20 × cd3":           "cd20_cd3",
    "cd20×cd3":             "cd20_cd3",
    "cd19 × cd20 × cd3":    "cd19_cd20_cd3",

    # TL1A bispecifics (each gets own class — do NOT auto-compete with monospecifics)
    "tl1a × il-23p19":      "tl1a_il23p19",
    "tl1a×il-23p19":        "tl1a_il23p19",
    "tl1a×il23p19":         "tl1a_il23p19",
    "tl1a/il-23":           "tl1a_il23p19",
    "tl1a×il-23":           "tl1a_il23p19",
    "il-23p19 × tl1a":      "tl1a_il23p19",  # canonical direction
    "tl1a×il-23p19×α4β7":   "tl1a_il23p19_a4b7",
    "tl1a×il-12/23p40":     "tl1a_il12_23p40",
    "il-23p40 × tl1a":      "tl1a_il12_23p40",

    # TSLP bispecifics
    "tslp×il-13":           "tslp_il13",
    "tslp×il-33":           "tslp_il33",

    # IL-4Rα bispecifics
    "il-4rα×ox40l":         "il4ra_ox40l",
    "il-4rα×tslp":          "il4ra_tslp",

    # Other
    "pd-1 × vegf":          "pd1_vegf",
    "pd-1×vegf":            "pd1_vegf",
    "pd-1/vegf":            "pd1_vegf",
    "pd-1×ctla-4":          "pd1_ctla4",
}

def normalize_target(raw: str) -> tuple[str, bool]:
    """
    Returns (canonical_target_id, is_in_alias_map).
    If not in alias map, returns (lowercased_raw, False) — caller decides how to handle.
    """
    if not raw:
        return ("", False)
    cleaned = raw.strip().lower()
    # Replace unicode × with x for lookup
    cleaned = cleaned.replace("×", "×")  # keep canonical form
    canonical = TARGET_ALIASES.get(cleaned)
    if canonical:
        return (canonical, True)
    # Try without spaces
    no_space = cleaned.replace(" ", "")
    canonical = TARGET_ALIASES.get(no_space)
    if canonical:
        return (canonical, True)
    return (cleaned, False)


def is_bispecific_target(canonical: str) -> bool:
    """Returns True if the canonical target represents a bispecific or multi-target."""
    return "_" in canonical or "×" in canonical or "/" in canonical


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


def group_by_area_target(das_rows: list[dict], drug_lookup: dict) -> tuple[dict, list]:
    """
    Groups Direct drugs by (area_id, canonical_target).
    Returns:
      groups:    {(area_id, canonical_target): [drug_dict, ...]}
      uncertain: list of uncertain-case descriptions
    """
    groups: dict[tuple, list] = defaultdict(list)
    uncertain: list[dict] = []

    for row in das_rows:
        drug_id = row["drug_id"]
        area_id = row["area_id"]
        drug = drug_lookup.get(drug_id)

        if not drug:
            uncertain.append({
                "case":    "drug_not_found",
                "drug_id": drug_id,
                "area_id": area_id,
                "note":    "drug_id in drug_area_scores has no matching drugs row",
            })
            continue

        # Skip terminated drugs — they competed historically but not now
        if drug["stage"] in ("terminated", "discontinued"):
            continue

        canon = drug["canonical_target"]
        mapped = drug["target_is_mapped"]

        if not canon:
            uncertain.append({
                "case":    "missing_target",
                "drug_id": drug_id,
                "area_id": area_id,
                "name":    drug["name"],
                "note":    "drug.target is null or empty — cannot assign COMPETES_WITH",
            })
            continue

        if not mapped:
            uncertain.append({
                "case":    "unmapped_target",
                "drug_id": drug_id,
                "area_id": area_id,
                "name":    drug["name"],
                "raw_target": drug["target"],
                "note":    f"target '{drug['target']}' not in TARGET_ALIASES — needs manual review",
            })
            # Still group by canonical (lowercased raw) so we can surface pairs
            # but we'll flag the resulting edges as uncertain

        groups[(area_id, canon)].append({
            "drug_id":          drug_id,
            "name":             drug["name"],
            "target":           drug["target"],
            "canonical_target": canon,
            "target_is_mapped": mapped,
            "area_id":          area_id,
            "status":           drug["status"],
        })

    return dict(groups), uncertain


def generate_edge_pairs(groups: dict) -> tuple[list, list]:
    """
    For each group with ≥2 drugs, generate bidirectional COMPETES_WITH pairs.
    Returns:
      safe_edges:      pairs where both drugs have mapped targets
      uncertain_edges: pairs where ≥1 drug has an unmapped target
    """
    safe_edges: list[dict] = []
    uncertain_edges: list[dict] = []

    for (area_id, canon), drugs_in_group in groups.items():
        if len(drugs_in_group) < 2:
            continue

        # Check if any drug in the group has a bispecific target
        has_bispecific = any(is_bispecific_target(d["canonical_target"]) for d in drugs_in_group)

        for d_a, d_b in combinations(drugs_in_group, 2):
            all_mapped = d_a["target_is_mapped"] and d_b["target_is_mapped"]

            rationale = (
                f"Both drugs are 'Direct' competitors in area '{area_id}' with "
                f"shared normalized target '{canon}'. "
                f"Generated deterministically by seed_competes_with.py on {NOW_ISO[:10]}."
            )

            edge_pair = [
                # Forward
                {
                    "subject_type":     "drug",
                    "subject_id":       d_a["drug_id"],
                    "predicate":        "COMPETES_WITH",
                    "object_type":      "drug",
                    "object_id":        d_b["drug_id"],
                    "scope_area_id":    area_id,
                    "confidence_level": "supported" if all_mapped else "inferred",
                    "generation_method": "deterministic",
                    "rationale":        rationale,
                    "status":           "active",
                    "created_by":       "seed_competes_with.py",
                    "notes":            None if all_mapped else f"⚠ target '{d_a['target']}' or '{d_b['target']}' not in alias map",
                },
                # Reverse (symmetric)
                {
                    "subject_type":     "drug",
                    "subject_id":       d_b["drug_id"],
                    "predicate":        "COMPETES_WITH",
                    "object_type":      "drug",
                    "object_id":        d_a["drug_id"],
                    "scope_area_id":    area_id,
                    "confidence_level": "supported" if all_mapped else "inferred",
                    "generation_method": "deterministic",
                    "rationale":        rationale,
                    "status":           "active",
                    "created_by":       "seed_competes_with.py",
                    "notes":            None if all_mapped else f"⚠ target '{d_b['target']}' or '{d_a['target']}' not in alias map",
                },
            ]

            if all_mapped:
                safe_edges.extend(edge_pair)
            else:
                uncertain_edges.extend(edge_pair)

    return safe_edges, uncertain_edges


# ══════════════════════════════════════════════════════════════════════════════
# VALIDATION TEST GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def build_validation_tests(safe_edges: list[dict]) -> list[dict]:
    """
    For each unique drug pair, generate one 'competes_with_edge_exists' validation test.
    Uses the A→B direction (not both) to avoid duplicates.
    """
    seen_pairs: set[tuple] = set()
    tests: list[dict] = []

    for edge in safe_edges:
        if edge["subject_id"] < edge["object_id"]:  # canonical ordering
            pair = (edge["subject_id"], edge["object_id"], edge["scope_area_id"])
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            tests.append({
                "test_name":       f"competes_with — {edge['subject_id']} vs {edge['object_id']} ({edge['scope_area_id']})",
                "test_type":       "competes_with_edge_exists",
                "entity_type":     "drug",
                "entity_id":       edge["subject_id"],
                "field_name":      "competitor",
                "expected_value":  edge["object_id"],
                "expected_operator": "eq",
                "area_id":         edge["scope_area_id"],
                "priority":        "P2",
                "notes":           f"COMPETES_WITH edge must exist between {edge['subject_id']} and {edge['object_id']} in area {edge['scope_area_id']}",
            })

    return tests


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
    migration_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "migrations", "v26_entity_edges.sql")
    )
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
        # Batch in groups of 100
        inserted_total = 0
        BATCH = 100
        for i in range(0, len(edges_to_insert), BATCH):
            batch = edges_to_insert[i:i+BATCH]
            result = sb_post("entity_edges", batch, upsert=True)
            if result is None:
                print(f"  [ERROR] Batch {i//BATCH + 1} failed.", file=sys.stderr)
                sys.exit(1)
            inserted_total += len(result) if isinstance(result, list) else 1
            print(f"  ✓ Batch {i//BATCH + 1}: inserted {len(result) if isinstance(result, list) else 1} edges")

        print(f"\n✅ Total edges inserted: {inserted_total}")
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
