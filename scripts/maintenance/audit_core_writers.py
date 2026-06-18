#!/usr/bin/env python3
"""
audit_core_writers.py — enforce the Single Writer Pattern in CI.

The Constitution / STABILIZATION_PLAN north star: each core entity has exactly ONE
sanctioned write path (its Writer). "Single writer" is only real once something
*checks* it. The earlier manual audit only looked for `sb_upsert('drugs')` and so
reported "drugs: 0 direct writes" — but it never saw `sb_patch('drugs', ...)`
(field updates), of which there are many. This script closes that blind spot: it
flags EVERY write verb (upsert/insert/post/patch/update/delete) against a core
table from anywhere except that table's Writer.

It is a RATCHET, not a big-bang: the known pre-existing sites are baselined in
BASELINE_FILES below, so CI stays green today, but any NEW file that writes a core
table directly fails the check. As the baselined files are migrated onto the
Writers, delete them from BASELINE_FILES to lock in the progress.

Usage:
  python scripts/maintenance/audit_core_writers.py          # full report (exit 0)
  python scripts/maintenance/audit_core_writers.py --ci     # fail on NEW bypasses only
  python scripts/maintenance/audit_core_writers.py --strict # fail on ANY bypass (incl baseline)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# core table -> (its Writer's filename, Writer class) — the ONLY sanctioned writer
CORE = {
    "drugs": ("drug_writer.py", "DrugWriter"),
    "companies": ("company_writer.py", "CompanyWriter"),
    "catalysts": ("catalyst_writer.py", "CatalystWriter"),
    # entity_edges intentionally omitted: the plan grandfathers the deterministic
    # edge seeders (DB UNIQUE constraint makes them idempotent); EdgeWriter is for
    # NEW edge code only. Add it here once those seeders are migrated.
}

WRITE_VERBS = (
    "sb_upsert", "sb_insert", "sb_insert_new", "sb_insert_mol_intel",
    "sb_post", "sb_post_rows", "sb_post_single", "sb_patch", "sb_patch_row",
    "sb_patch_filter", "sb_write", "sb_update_where", "sb_delete",
    "sb_delete_by_drug_id", "insert", "update", "delete",
)
# Bake the core table names in as literals so the regex fails fast on any other
# table (avoids the catastrophic backtracking an open `[a-z_]+` capture caused).
_CALL = re.compile(
    r"\b(?:" + "|".join(WRITE_VERBS) + r")\(\s*f?['\"](" +
    "|".join(CORE) + r")['\"]"
)

SCAN_DIRS = ("src", "scripts")
# never count historical code
SKIP_HINTS = ("/archive/", "/one_off/", "/deprecated/", "/__pycache__/")

# ── BASELINE: known pre-existing bypasses (debt). New bypasses must NOT land in
#    any file outside this set. Shrink this list as sites are migrated. ─────────
BASELINE_FILES = {
    "scripts/drug_enrichment.py",
    "scripts/weekend_sprint.py",
    "src/meridian/enrichment/company/assessment.py",
    "src/meridian/enrichment/company/common.py",
    "src/meridian/enrichment/company_enrichment.py",
    "src/meridian/identity/process_queue_item.py",
    "src/meridian/ingestion/ct_gov_sync.py",
    "src/meridian/ingestion/ctgov/validate.py",
    "src/meridian/products/execute_intel_actions.py",
    "src/meridian/validation/conflict_detector.py",
    "src/meridian/validation/validation_research.py",
}


def find_bypasses():
    """Return list of (table, relpath, line, verb_call_snippet)."""
    out = []
    for d in SCAN_DIRS:
        for f in (REPO_ROOT / d).rglob("*.py"):
            rel = str(f.relative_to(REPO_ROOT))
            if f.name == Path(__file__).name:   # don't flag our own docstring examples
                continue
            if any(h in "/" + rel for h in SKIP_HINTS):
                continue
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not any(t in txt for t in CORE):   # fast skip: no core table mentioned
                continue
            for m in _CALL.finditer(txt):
                table = m.group(1)
                if table not in CORE:
                    continue
                writer_file = CORE[table][0]
                # the Writer itself and the shared database/ package are allowed
                if writer_file in f.name or "database/" in rel.replace("\\", "/"):
                    continue
                line = txt.count("\n", 0, m.start()) + 1
                snippet = txt[m.start():m.start() + 60].splitlines()[0]
                out.append((table, rel, line, snippet.strip()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ci", action="store_true",
                    help="exit non-zero only if a NEW (non-baselined) bypass exists")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if ANY bypass exists (incl. baselined debt)")
    args = ap.parse_args()

    rows = find_bypasses()
    by_table: dict[str, list] = {}
    for t, rel, ln, snip in rows:
        by_table.setdefault(t, []).append((rel, ln, snip))

    new = [(t, rel, ln, snip) for (t, rel, ln, snip) in rows
           if rel not in BASELINE_FILES]
    baselined = [(t, rel, ln, snip) for (t, rel, ln, snip) in rows
                 if rel in BASELINE_FILES]

    print("=" * 72)
    print("Core-table write audit — Single Writer Pattern")
    print("=" * 72)
    for t in CORE:
        hits = by_table.get(t, [])
        print(f"\n{t}  ({CORE[t][1]} is the only sanctioned writer)  — {len(hits)} direct write(s)")
        for rel, ln, snip in sorted(hits):
            mark = "  " if rel in BASELINE_FILES else "NEW "
            print(f"  {mark}{rel}:{ln}   {snip}")

    print("\n" + "-" * 72)
    print(f"baselined debt: {len(baselined)} site(s) in {len(BASELINE_FILES)} known files")
    print(f"NEW bypasses (outside baseline): {len(new)}")

    if args.strict and rows:
        print("\n[strict] FAIL — core tables must be written only through their Writer.")
        return 1
    if args.ci and new:
        print("\n[ci] FAIL — a NEW direct write to a core table was added. Route it "
              "through the table's Writer (e.g. DrugWriter().update_fields(id, fields)).")
        return 1
    if not args.strict and not args.ci:
        print("\n(report only — pass --ci to fail on new bypasses, --strict for all)")
    print("OK" if not (args.strict and rows) and not (args.ci and new) else "FAIL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
