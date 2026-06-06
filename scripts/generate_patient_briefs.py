#!/usr/bin/env python3
"""
generate_patient_briefs.py — batch driver for the Meridian Patient Brief layer
------------------------------------------------------------------------------
Generates the cited patient brief + Meridian Patient Analysis for every indication
in indication_patient_intelligence (or a subset). Designed for CI (no 44s limit).

Run:
  python3 scripts/generate_patient_briefs.py --all
  python3 scripts/generate_patient_briefs.py --indications "Ulcerative Colitis,Crohn's Disease"
"""
import os, sys, argparse, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import narrative_gen as ng

HERE = os.path.dirname(os.path.abspath(__file__))


def run(name):
    r = subprocess.run([sys.executable, "scripts/patient_narrative.py", "--indication", name,
                        "--section", "both"], cwd=os.path.dirname(HERE), capture_output=True, text=True)
    ok = r.stdout.count("wrote indication/")
    tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
    print(f"  {name[:40]:40} → {ok} sections written  {tail[0][:50]}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true"); g.add_argument("--indications")
    args = ap.parse_args()

    if args.indications:
        names = [s.strip() for s in args.indications.split(",") if s.strip()]
    else:
        names = sorted({r["indication_name"] for r in
                        ng.get("indication_patient_intelligence?select=indication_name")
                        if r.get("indication_name")})
    print(f"Patient briefs — {len(names)} indication(s)\n")
    total = 0
    for n in names:
        total += run(n)
    print(f"\ndone: {total} sections written across {len(names)} indications.")


if __name__ == "__main__":
    main()
