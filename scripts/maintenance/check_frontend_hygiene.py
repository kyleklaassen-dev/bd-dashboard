#!/usr/bin/env python3
"""
check_frontend_hygiene.py — durable guard for the frontend org work (Domain H).

CI is otherwise Python-only; nothing stopped app.js from growing or the consolidated
helpers from being re-forked. This adds two cheap, durable ratchets:

  1. SIZE RATCHET — large JS files may only shrink. app.js is the monolith we're
     re-extracting (Domain A2); this budget must be *lowered* as modules are pulled,
     so it can never creep back up. Everything else is capped to block new monoliths.
  2. CANONICAL-SOURCE guard — the shared helpers must exist where the modules expect
     them (core.js AREA_LABELS_SHORT, ui.js window.MUI). Catches an accidental removal
     that would silently break briefing/watch/reads which now depend on them.

Usage: python scripts/maintenance/check_frontend_hygiene.py [--ci]
  (exit 1 on any violation; report-only without --ci)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JS = os.path.join(ROOT, "assets", "js")

# Shrink-only budgets. LOWER these as Domain A2 extracts modules from app.js.
# A file may be at or below its budget, never above.
SIZE_BUDGET = {
    "app.js": 10730,   # the monolith — re-extraction target; lower per A2 PR
    "core.js": 2228,
}
GENERAL_CAP = 2000     # any other assets/js file must stay under this (no new monoliths)

# Canonical shared sources the feature modules depend on (file -> required substring).
CANONICAL = {
    "core.js": "AREA_LABELS_SHORT",
    "ui.js": "window.MUI",
}


def main() -> int:
    ci = "--ci" in sys.argv
    problems = []

    for fn in sorted(os.listdir(JS)):
        if not fn.endswith(".js"):
            continue
        path = os.path.join(JS, fn)
        n = sum(1 for _ in open(path, encoding="utf-8", errors="replace"))
        budget = SIZE_BUDGET.get(fn, GENERAL_CAP)
        flag = "" if n <= budget else f"  ✗ OVER (budget {budget})"
        if flag:
            problems.append(f"{fn}: {n} lines{flag}")
        print(f"  {n:6d}  {fn}{flag}")

    print("\nCanonical shared sources:")
    for fn, needle in CANONICAL.items():
        path = os.path.join(JS, fn)
        ok = os.path.exists(path) and needle in open(path, encoding="utf-8", errors="replace").read()
        print(f"  {'ok ' if ok else '✗  '} {fn} defines {needle}")
        if not ok:
            problems.append(f"{fn} is missing canonical source: {needle}")

    if problems:
        print("\n✗ frontend hygiene: " + str(len(problems)) + " problem(s)")
        for p in problems:
            print("   - " + p)
        if ci:
            print("\n[ci] FAIL — fix the above (or LOWER a size budget after extracting from a file).")
            return 1
        print("\n(report only — pass --ci to fail the build)")
        return 0
    print("\n✓ frontend hygiene clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
