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

# Second class of bypass the sb_* scan misses: raw REST writes through generic
# helpers, e.g.  _req("PATCH", f"drugs?id=eq.{x}", …)  ·  rest(f"catalysts?…","PATCH")
#                patch(f"companies?id=eq.{c}", …)      ·  requests.patch(".../drugs?…")
# A core-table REST path that carries a query (`?`) is a targeted write/read; we
# flag it only when a write method/helper appears within a small window.
_REST_PATH = re.compile(r"['\"]/?(?:rest/v1/)?(" + "|".join(CORE) + r")\?")
_WRITE_NEAR = re.compile(
    r'"(?:PATCH|POST|PUT|DELETE)"'           # quoted HTTP method (rest/_req style)
    r"|\b(?:patch|post|put)\s*\("            # patch(/post( helper call
    r"|\.(?:patch|post|put|delete)\s*\("     # requests.patch( etc.
)
_READ_NEAR = re.compile(r'\bsb_get\b|select=|"GET"|\bget\(\s*f?["\']')  # REST reads only

SCAN_DIRS = ("src", "scripts")
# never count historical code
SKIP_HINTS = ("/archive/", "/one_off/", "/deprecated/", "/__pycache__/")

# ── BASELINE: known pre-existing bypasses (debt). New bypasses must NOT land in
#    any file outside this set. Shrink this list as sites are migrated. ─────────
#
# 2026-06-18: all 17 real field-update bypasses (16 drugs, 1 companies) were
# migrated onto update_drug() / update_company() (meridian.database). The single
# remaining match is a FALSE POSITIVE — the `sb_upsert('catalysts', ...)` text in
# the docstring of `_catalyst_upsert`, which is itself the sanctioned CatalystWriter
# drop-in. Real direct-write debt is now ZERO.
BASELINE_FILES = {
    "src/meridian/enrichment/company/common.py",  # docstring of _catalyst_upsert (not a real write)
}

# ── Root-cause ratchet: ad-hoc write helpers. Each local sb_*/rest/_req that does
#    raw REST writes (instead of the shared client/Writers) is a place a future
#    core-table bypass can hide. The count only ever goes DOWN: new ones fail CI.
#    Drive toward 0 by consolidating onto meridian.database. (Shared by the health
#    scoreboard so the two never use different definitions — see lesson: one
#    source of truth.)
HELPER_BASELINE = 46
_HELPER_DEF = re.compile(
    r"^\s*def (sb_patch|sb_post|sb_upsert|sb_insert|sb_delete|sb_write|rest|_req)\("
)


def write_helper_files():
    """Repo-relative paths of files that define their own ad-hoc REST write helper."""
    out = []
    for d in SCAN_DIRS:
        for f in (REPO_ROOT / d).rglob("*.py"):
            rel = str(f.relative_to(REPO_ROOT))
            if any(h in "/" + rel for h in SKIP_HINTS):
                continue
            if rel.replace("\\", "/").endswith("database/client.py"):
                continue  # THE sanctioned shared client — its helpers are the target
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if any(_HELPER_DEF.search(ln) for ln in txt.splitlines()):
                out.append(rel)
    return sorted(out)


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
            def _allowed(table):
                wf = CORE[table][0]
                return wf in f.name or "database/" in rel.replace("\\", "/")

            seen = set()
            # pass 1 — sb_*/client write calls with a literal core table
            for m in _CALL.finditer(txt):
                table = m.group(1)
                if table not in CORE or _allowed(table):
                    continue
                line = txt.count("\n", 0, m.start()) + 1
                seen.add((table, line))
                snippet = txt[m.start():m.start() + 60].splitlines()[0]
                out.append((table, rel, line, snippet.strip()))
            # pass 2 — raw REST writes (f-string path + a write method nearby)
            for m in _REST_PATH.finditer(txt):
                table = m.group(1)
                if _allowed(table):
                    continue
                window = txt[max(0, m.start() - 120): m.start() + 80]
                if not _WRITE_NEAR.search(window) or _READ_NEAR.search(window):
                    continue
                line = txt.count("\n", 0, m.start()) + 1
                if (table, line) in seen:
                    continue
                snippet = txt[m.start():m.start() + 60].splitlines()[0]
                out.append((table, rel, line, "REST: " + snippet.strip()))
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

    # root-cause ratchet
    helpers = write_helper_files()
    grew = len(helpers) - HELPER_BASELINE
    print(f"ad-hoc write-helper files: {len(helpers)} (baseline {HELPER_BASELINE}; "
          f"{'+' + str(grew) + ' NEW — must consolidate, not add' if grew > 0 else 'ok, ≤ baseline'})")

    fail = False
    if args.strict and rows:
        print("\n[strict] FAIL — core tables must be written only through their Writer.")
        fail = True
    if args.ci and new:
        print("\n[ci] FAIL — a NEW direct write to a core table was added. Route it "
              "through the table's Writer (e.g. DrugWriter().update_fields(id, fields)).")
        fail = True
    if args.ci and grew > 0:
        print("\n[ci] FAIL — a NEW ad-hoc write helper was added. Use the shared "
              "meridian.database client/Writers instead; the count only goes down.")
        fail = True
    if not args.strict and not args.ci:
        print("\n(report only — pass --ci to fail on new bypasses/helpers, --strict for all)")
    print("FAIL" if fail else "OK")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
