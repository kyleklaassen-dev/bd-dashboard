import sys as _sys, pathlib as _pl
for _p in _pl.Path(__file__).resolve().parents:
    if (_p / 'meridian' / 'database').is_dir(): _sys.path.insert(0, str(_p)); break
    if (_p / 'src' / 'meridian' / 'database').is_dir(): _sys.path.insert(0, str(_p / 'src')); break
from meridian.database.edge_writer import EdgeWriter
#!/usr/bin/env python3
"""
BD Platform — Target Normalization Seeder
==========================================
Phase 2 of the relationship-completeness sprint (2026-05-24).

PURPOSE
-------
Normalizes drugs.target free-text into queryable target nodes:
  1. Seeds the `targets` table with canonical entries + metadata
  2. Parses each drug's target field → writes `drug_targets` junction rows
  3. Writes drug → TARGETS → target edges to `entity_edges` for graph queries
  4. Adds validation test: every area-linked drug must have ≥1 drug_targets row

PARSING LOGIC
-------------
• Monospecific drug:   drugs.target = 'TL1A'    → 1 drug_targets row (role='primary')
• Bispecific drug:     drugs.target = 'TL1A×IL-23p19'
                       → 2 drug_targets rows (role='component' for each)
• Bispecific notation: '×' or '+' or ' + ' as separator
• Combination product (is_combo=true): separate drugs; drug-level target is the
  primary target; combo context is in combination_label (not parsed here)

NOT PARSED (logged as uncertain):
• Targets with 'or' in the text (ambiguous: 'IL-23p19 + IL-1α/β or TL1A')
• Targets with 'vs' in the text (narrative, not target: 'IL-23p19 vs α4β7 integrin')
• Free-text mechanism descriptions (e.g. 'PHD1/HIF-1α')

USAGE
-----
  python scripts/seed_targets.py --dry-run           # print, insert nothing
  python scripts/seed_targets.py --apply             # seed targets + drug_targets
  python scripts/seed_targets.py --apply-migration   # run v27 DDL first, then seed
  python scripts/seed_targets.py --apply --validate  # run validation suite after

ENVIRONMENT
-----------
  SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import os, sys, json, datetime, argparse, urllib.request, urllib.error, ssl
from collections import defaultdict

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.", file=sys.stderr)
    sys.exit(1)

ctx = ssl.create_default_context()
NOW_ISO = datetime.datetime.utcnow().isoformat() + "Z"


# ══════════════════════════════════════════════════════════════════════════════
# CANONICAL TARGET CATALOG  → seed_targets_data.py (§3 split: pure data)
# ══════════════════════════════════════════════════════════════════════════════
from seed_targets_data import (
    CANONICAL_TARGETS, BISPECIFIC_COMPONENTS, TARGET_TEXT_TO_ID, UNCERTAIN_PATTERNS,
)


# ══════════════════════════════════════════════════════════════════════════════
# SUPABASE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _hdrs():
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }

def sb_get(table, params, limit=1000):
    """Paginate through all matching rows."""
    all_rows, offset, PAGE = [], 0, min(limit, 500)
    while True:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{SUPABASE_URL}/rest/v1/{table}?{qs}&limit={PAGE}&offset={offset}"
        req = urllib.request.Request(url, headers=_hdrs())
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                batch = json.loads(r.read())
                all_rows.extend(batch)
                if len(batch) < PAGE or len(all_rows) >= limit:
                    break
                offset += PAGE
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", errors="replace")
            print(f"  [ERROR] GET {table}: {e.code} — {body}", file=sys.stderr)
            break
    return all_rows[:limit]

def sb_post(table, payload, upsert=True):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    prefer = "resolution=merge-duplicates,return=representation" if upsert else "return=representation"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST",
          headers={**_hdrs(), "Prefer": prefer})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()[:400].decode("utf-8", errors="replace")
        print(f"  [ERROR] POST {table}: {e.code} — {body}", file=sys.stderr)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# PARSING LOGIC
# ══════════════════════════════════════════════════════════════════════════════

def parse_target_text(raw: str) -> tuple[str | None, str, bool]:
    """
    Parse drugs.target text → (canonical_target_id, note, is_uncertain).
    Returns (None, reason, True) for uncertain cases.
    """
    if not raw or not raw.strip():
        return (None, "empty target field", True)

    cleaned = raw.strip().lower()

    # Flag uncertain patterns before lookup
    for pattern in UNCERTAIN_PATTERNS:
        if pattern in cleaned:
            return (None, f"uncertain notation: '{raw}'", True)

    # Direct lookup
    canon = TARGET_TEXT_TO_ID.get(cleaned)
    if canon:
        return (canon, "", False)

    # No-space variant
    no_space = cleaned.replace(" ", "")
    canon = TARGET_TEXT_TO_ID.get(no_space)
    if canon:
        return (canon, "", False)

    return (None, f"unmapped target: '{raw}'", True)


def build_drug_target_rows(drug_id: str, canonical_id: str) -> list[dict]:
    """
    Given a drug and its canonical target ID, return all drug_targets rows to insert.
    For bispecifics, also inserts component target rows.
    """
    rows = []
    is_bispecific = canonical_id in BISPECIFIC_COMPONENTS

    # Always insert the top-level canonical target row
    rows.append({
        "drug_id":         drug_id,
        "target_id":       canonical_id,
        "role":            "component" if is_bispecific else "primary",
        "confidence_level": "confirmed",
        "derived_from":    "drugs.target",
        "created_by":      "seed_targets.py",
    })

    # For bispecifics, also insert component targets (if they exist as canonical targets)
    if is_bispecific:
        target_ids = {t["id"] for t in CANONICAL_TARGETS}
        for component_id in BISPECIFIC_COMPONENTS[canonical_id]:
            if component_id in target_ids:
                rows.append({
                    "drug_id":         drug_id,
                    "target_id":       component_id,
                    "role":            "component",
                    "confidence_level": "confirmed",
                    "derived_from":    "drugs.target",
                    "created_by":      "seed_targets.py",
                })

    return rows


def build_entity_edge_rows(drug_id: str, canonical_id: str) -> list[dict]:
    """Build entity_edges TARGETS rows for the drug→target relationship."""
    edges = []
    is_bispecific = canonical_id in BISPECIFIC_COMPONENTS

    # Top-level target edge
    edges.append({
        "subject_type":     "drug",
        "subject_id":       drug_id,
        "predicate":        "TARGETS",
        "object_type":      "target",
        "object_id":        canonical_id,
        "confidence_level": "confirmed",
        "generation_method": "deterministic",
        "rationale":        f"Parsed from drugs.target field by seed_targets.py {NOW_ISO[:10]}",
        "status":           "active",
        "created_by":       "seed_targets.py",
    })

    # Component target edges for bispecifics
    if is_bispecific:
        target_ids = {t["id"] for t in CANONICAL_TARGETS}
        for component_id in BISPECIFIC_COMPONENTS[canonical_id]:
            if component_id in target_ids:
                edges.append({
                    "subject_type":     "drug",
                    "subject_id":       drug_id,
                    "predicate":        "TARGETS",
                    "object_type":      "target",
                    "object_id":        component_id,
                    "confidence_level": "confirmed",
                    "generation_method": "deterministic",
                    "rationale":        f"Component target of {canonical_id}; derived by seed_targets.py {NOW_ISO[:10]}",
                    "status":           "active",
                    "created_by":       "seed_targets.py",
                })

    return edges


# ══════════════════════════════════════════════════════════════════════════════
# APPLY MIGRATION
# ══════════════════════════════════════════════════════════════════════════════

def apply_migration(project_id: str, pat: str) -> bool:
    migration_path = os.path.join(os.path.dirname(__file__), "..", "migrations", "v27_targets.sql")
    if not os.path.exists(migration_path):
        print(f"  [ERROR] Not found: {migration_path}", file=sys.stderr)
        return False
    with open(migration_path) as f:
        sql = f.read()

    statements = []
    current = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        current.append(line)
        if stripped.endswith(";"):
            stmt = " ".join(current).strip().rstrip(";")
            if stmt:
                statements.append(stmt)
            current = []

    api_url = f"https://api.supabase.com/v1/projects/{project_id}/database/query"
    success = 0
    for stmt in statements:
        payload = json.dumps({"query": stmt + ";"}).encode()
        req = urllib.request.Request(api_url, data=payload, method="POST", headers={
            "Authorization": f"Bearer {pat}", "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                success += 1
                print(f"  ✓ {stmt[:80].replace(chr(10),' ')}...")
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", errors="replace")
            if "already exists" in body.lower():
                print(f"  ⚠ Already exists: {stmt[:60]}...")
                success += 1
            else:
                print(f"  ✗ FAILED: {stmt[:60]}...\n    {e.code} — {body}", file=sys.stderr)
                return False
    print(f"  Migration: {success} statements applied.")
    return True


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Seed targets table + drug_targets junction.")
    parser.add_argument("--dry-run",         action="store_true")
    parser.add_argument("--apply",           action="store_true")
    parser.add_argument("--apply-migration", action="store_true")
    parser.add_argument("--validate",        action="store_true")
    parser.add_argument("--project-id",      default="tghntyofptvfhmtchwcv")
    parser.add_argument("--pat-file",        default=".supabase_pat")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Specify --dry-run or --apply."); parser.print_help(); sys.exit(0)

    # ── Optional: apply migration DDL ─────────────────────────────────────────
    if args.apply_migration:
        pat_path = os.path.join(os.path.dirname(__file__), "..", args.pat_file)
        if not os.path.exists(pat_path):
            print(f"PAT file not found: {pat_path}", file=sys.stderr); sys.exit(1)
        with open(pat_path) as f:
            pat = f.read().strip()
        print("Applying migration v27...")
        if not apply_migration(args.project_id, pat):
            print("Migration failed."); sys.exit(1)

    # ── Fetch all drugs ────────────────────────────────────────────────────────
    drugs = sb_get("drugs", {"select": "id,name,target,stage"}, limit=1000)
    print(f"Drugs fetched: {len(drugs)}")

    # ── Parse drug targets ─────────────────────────────────────────────────────
    drug_target_rows = []
    entity_edge_rows = []
    uncertain = []

    for d in drugs:
        drug_id = d["id"]
        raw_target = (d.get("target") or "").strip()
        if not raw_target:
            continue

        canon, note, is_uncertain = parse_target_text(raw_target)
        if is_uncertain:
            uncertain.append({"drug_id": drug_id, "name": d.get("name","?"),
                               "raw_target": raw_target, "note": note})
            continue

        drug_target_rows.extend(build_drug_target_rows(drug_id, canon))
        entity_edge_rows.extend(build_entity_edge_rows(drug_id, canon))

    print(f"\n--- Audit ---")
    print(f"  Drug-target rows to insert:   {len(drug_target_rows)}")
    print(f"  Entity edge rows (TARGETS):   {len(entity_edge_rows)}")
    print(f"  Uncertain (not inserting):    {len(uncertain)}")

    if uncertain:
        print(f"\n  Uncertain cases:")
        for uc in uncertain:
            print(f"    {uc['drug_id']:35s} raw='{uc['raw_target']}'  — {uc['note']}")

    if args.dry_run:
        print("\n[DRY RUN] No rows inserted.")
        return

    # ── Insert targets catalog ─────────────────────────────────────────────────
    # DB uses `label` (not `name`) as the display column; `full_name` for expanded form.
    # Transform CANONICAL_TARGETS to match actual schema before inserting.
    targets_for_db = []
    for t in CANONICAL_TARGETS:
        row = dict(t)
        if "name" in row and "label" not in row:
            row["label"] = row.pop("name")
        targets_for_db.append(row)

    print(f"\nInserting {len(targets_for_db)} canonical targets...")
    result = sb_post("targets", targets_for_db)
    if result is None:
        print("  [ERROR] Failed to insert targets."); sys.exit(1)
    print(f"  ✓ {len(result) if isinstance(result,list) else 1} targets upserted (new; dupes ignored)")

    # ── Insert drug_targets rows ────────────────────────────────────────────────
    print(f"\nInserting {len(drug_target_rows)} drug_targets rows...")
    BATCH = 100
    inserted_dt = 0
    for i in range(0, len(drug_target_rows), BATCH):
        batch = drug_target_rows[i:i+BATCH]
        result = sb_post("drug_targets", batch)
        if result is None:
            print(f"  [ERROR] Batch {i//BATCH+1} failed."); sys.exit(1)
        count = len(result) if isinstance(result,list) else 1
        inserted_dt += count
        print(f"  ✓ Batch {i//BATCH+1}: {count} rows (total {inserted_dt})")

    # ── Insert entity_edges TARGETS rows ───────────────────────────────────────
    print(f"\nInserting {len(entity_edge_rows)} entity_edges TARGETS rows...")
    inserted_ee = 0
    inserted_ee = EdgeWriter(verify_endpoints=False).write(entity_edge_rows).get("written", 0)
    print(f"  ✓ {inserted_ee} entity_edges TARGETS rows via EdgeWriter")

    # ── Insert validation test ─────────────────────────────────────────────────
    print(f"\nInserting validation tests...")
    tests = [
        {
            "test_name":         "drug_has_target_node — area-linked drugs must have ≥1 drug_targets row",
            "test_type":         "count_check",
            "entity_type":       "drug",
            "entity_id":         "system",
            "field_name":        "drug_targets_coverage",
            "expected_value":    "0",
            "expected_operator": "eq",
            "priority":          "P2",
            "notes":             "Counts drugs in drug_areas with zero drug_targets rows. Expected = 0.",
        }
    ]
    result = sb_post("validation_tests", tests)
    if result:
        print(f"  ✓ Validation test inserted")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n═══════════════════════════════════════")
    print(f"Target normalization complete — {NOW_ISO[:10]}")
    print(f"  Canonical targets seeded:   {len(CANONICAL_TARGETS)}")
    print(f"  drug_targets rows inserted: {inserted_dt}")
    print(f"  entity_edges TARGETS:       {inserted_ee}")
    print(f"  Uncertain cases:            {len(uncertain)}")
    print(f"═══════════════════════════════════════")

    if args.validate:
        import subprocess
        print("\nRunning validation suite...")
        subprocess.run([sys.executable,
                        os.path.join(os.path.dirname(__file__), "validate_ground_truth.py")])


if __name__ == "__main__":
    main()
