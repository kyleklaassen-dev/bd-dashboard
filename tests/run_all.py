#!/usr/bin/env python3
"""
Run all read-only database regression suites (CLAUDE.md session-start step 3).
Safe to run any time — every test is dry-run / read-only.

    SUPABASE_SERVICE_KEY=... python3 tests/run_all.py
"""
import subprocess, sys, pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
SUITES = [
    BASE / "tests" / "database" / "test_drug_writer.py",
    BASE / "tests" / "database" / "test_writers.py",
]

def main():
    total_fail = 0
    for s in SUITES:
        if not s.exists():
            print(f"SKIP (missing): {s.name}"); continue
        print(f"\n=== {s.relative_to(BASE)} ===")
        r = subprocess.run([sys.executable, str(s)])
        total_fail += (r.returncode != 0)
    print("\n" + ("ALL SUITES GREEN" if total_fail == 0 else f"{total_fail} SUITE(S) FAILED"))
    sys.exit(1 if total_fail else 0)

if __name__ == "__main__":
    main()
