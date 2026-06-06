#!/usr/bin/env python3
"""
generate_area_narratives.py — batch driver for the narrative layer
------------------------------------------------------------------
Regenerates every narrative for an area in one run, so the layer scales past the
hand-made few: per-drug overview + Meridian Analysis, the target landscape, and
the per-drug trust scores. Designed to run on a schedule (GitHub Actions).

Each step regenerates from current rows, so this also IS the staleness fix:
a weekly full regen keeps every narrative current with the graph.

Run:
  python3 scripts/generate_area_narratives.py --area tl1a [--limit N] [--sections overview]
"""
import os, sys, argparse, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from narrative_gen import get  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    print("  $", " ".join(cmd[1:]))
    r = subprocess.run([sys.executable] + cmd, cwd=os.path.dirname(HERE),
                       capture_output=True, text=True)
    tail = (r.stdout or "").strip().splitlines()[-1:] or [(r.stderr or "").strip()[-160:]]
    print("    →", tail[0] if tail else "(no output)")
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sections", default="overview,intelligence")
    args = ap.parse_args()
    secs = [s for s in args.sections.split(",") if s]

    ids = sorted({r["drug_id"] for r in
                  get(f"drug_targets?target_id=eq.{args.area}&select=drug_id") if r.get("drug_id")})
    if args.limit:
        ids = ids[:args.limit]
    print(f"Batch narrative generation — area={args.area}, {len(ids)} drugs, sections={secs}\n")

    # Refresh the study-identity resolver + trial→publication crosswalk FIRST, so
    # triangulation runs against current ct.gov aliases/publications (v73).
    print("Trial-identity + publication crosswalk:")
    run(["scripts/enrich_trial_identity.py", "--area", args.area])

    ok = fail = 0
    for did in ids:
        for sec in secs:
            if run(["scripts/narrative_gen.py", "--drug-id", did, "--section", sec, "--composer", "llm"]):
                ok += 1
            else:
                fail += 1
    print(f"\nper-drug narratives: {ok} ok, {fail} failed")

    print("\nLandscape narrative:")
    run(["scripts/landscape_narrative.py", "--target", args.area])
    print("\nTrust scores:")
    run(["scripts/compute_trust_score.py", "--area", args.area, "--apply"])
    print("\nCollection queue sync:")
    run(["scripts/sync_collection_queue.py", "--area", args.area])
    print("\nbatch complete.")


if __name__ == "__main__":
    main()
