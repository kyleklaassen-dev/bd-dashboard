"""
one_time_migration.py — Backfill canonical drug identity for all existing drugs

WHAT THIS DOES:
  Reads every row from the `drugs` table that does NOT yet have a canonical_drug_id,
  resolves each one through DrugIdentityResolver, and stamps:
    - drugs.canonical_drug_id
    - drugs.identity_confidence
    - drugs.identity_method

DESIGN CONSTRAINTS:
  - Fuzzy matches are flagged to identity_audit_log and a NEW canonical is created.
    No auto-merge. Human review required.
  - Exact/normalised matches share an existing canonical.
  - Idempotent: skips any drug row that already has canonical_drug_id set.
  - Dry-run mode: prints what would happen, makes no writes.

USAGE:
    # Dry run first
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python scripts/one_time_migration.py --dry-run

    # Live run
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python scripts/one_time_migration.py

    # From workspace folder (reads credential files)
    python scripts/one_time_migration.py
    python scripts/one_time_migration.py --dry-run
"""

import argparse
import os
import sys

import requests

# Allow running from repo root or scripts/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from identity_resolution import DrugIdentityResolver, _normalize_name


# ─── Drug class inference ──────────────────────────────────────────────────────

def _infer_drug_class(mechanism: str) -> str:
    """
    Infer a rough drug_class from the mechanism text.
    Returns one of the canonical drug_class values or 'other'.
    """
    if not mechanism:
        return "other"
    m = mechanism.lower()
    if "bispecific" in m or "×" in m or "x " in m:
        return "bispecific"
    if "car-t" in m or "car t" in m or "t-cell engager" in m:
        return "car_t"
    if "mirna" in m or "sirna" in m or "antisense" in m or "rna" in m:
        return "rna"
    if "gene therapy" in m or "gene editing" in m:
        return "gene_therapy"
    if "small molecule" in m or "inhibitor" in m:
        return "small_molecule"
    if "monoclonal antibody" in m or "mab" in m or "fc fragment" in m or "full mab" in m:
        return "mab"
    if "fusion" in m:
        return "fusion_protein"
    return "other"


def _infer_target(mechanism: str, drug_id: str, drug_name: str) -> str:
    """
    Infer the primary molecular target from mechanism text and drug identifiers.
    """
    if not mechanism:
        return ""
    m = mechanism.lower()
    # Order matters — check most specific first
    target_patterns = [
        ("TL1A",    ["tl1a", "tnfsf15"]),
        ("TSLP",    ["tslp", "anti-tslp"]),
        ("IL-4Rα",  ["il-4r", "il4r"]),
        ("IL-13",   ["il-13", "anti-il-13"]),
        ("IL-33",   ["il-33", "anti-il-33"]),
        ("IL-23",   ["il-23", "anti-il-23"]),
        ("IL-31Rα", ["il-31r"]),
        ("IGF1R",   ["igf1r", "igf-1r", "igf 1r"]),
        ("FcRn",    ["fcrn", "fc receptor"]),
        ("CD19",    ["cd19"]),
        ("CD3",     ["cd3"]),
    ]
    for target_name, patterns in target_patterns:
        if any(p in m for p in patterns):
            return target_name
    return ""


# ─── Main migration ────────────────────────────────────────────────────────────

def run_backfill(sb_url: str, service_key: str, dry_run: bool = False):
    """
    Iterate all drugs without canonical_drug_id, resolve each, and PATCH the row.
    """
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    # ── Fetch all unresolved drugs ────────────────────────────────────────────
    print("Fetching drugs without canonical_drug_id...")
    resp = requests.get(
        f"{sb_url}/rest/v1/drugs",
        headers={**headers, "Prefer": ""},
        params={
            "select": "id,name,mechanism,stage",
            "canonical_drug_id": "is.null",
            "limit": "1000",
        },
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch drugs: {resp.status_code} {resp.text}")

    drugs = resp.json()
    total = len(drugs)
    print(f"Found {total} drugs to backfill.\n")

    if total == 0:
        print("Nothing to do — all drugs already have canonical_drug_id set.")
        return

    # ── Initialise resolver ───────────────────────────────────────────────────
    resolver = DrugIdentityResolver(sb_url, service_key, dry_run=dry_run)

    # ── Process each drug ─────────────────────────────────────────────────────
    results = {"exact": 0, "normalized": 0, "fuzzy_flagged": 0, "new": 0, "error": 0}

    for i, drug in enumerate(drugs, 1):
        drug_id   = drug["id"]
        drug_name = drug.get("name", "").strip()
        mechanism = drug.get("mechanism", "") or ""

        if not drug_name:
            print(f"  [{i}/{total}] SKIP {drug_id} — no name")
            results["error"] += 1
            continue

        drug_class = _infer_drug_class(mechanism)
        target     = _infer_target(mechanism, drug_id, drug_name)

        print(f"  [{i}/{total}] Resolving: '{drug_name}' (class={drug_class}, target='{target}')")

        try:
            canonical_id, confidence, method = resolver.resolve(
                drug_name,
                source="one_time_migration",
                drug_class=drug_class,
                mechanism=mechanism or None,
                target=target or None,
            )
        except Exception as e:
            print(f"    ERROR: {e}")
            results["error"] += 1
            continue

        print(f"    → {canonical_id}  confidence={confidence}  method={method}")

        # Track fuzzy flags (resolver creates a new canonical for these)
        if method == "new" and confidence == 100:
            # Could be genuinely new OR was created after a fuzzy flag
            # The audit log has the full story
            pass

        # ── PATCH drugs row ───────────────────────────────────────────────────
        if dry_run:
            print(f"    [DRY RUN] Would PATCH drugs id='{drug_id}' with "
                  f"canonical_drug_id={canonical_id}, identity_confidence={confidence}, "
                  f"identity_method={method}")
        else:
            patch_resp = requests.patch(
                f"{sb_url}/rest/v1/drugs",
                headers=headers,
                params={"id": f"eq.{drug_id}"},
                json={
                    "canonical_drug_id": canonical_id,
                    "identity_confidence": confidence,
                    "identity_method": method,
                },
            )
            if patch_resp.status_code not in (200, 204):
                print(f"    WARNING: PATCH failed for {drug_id}: "
                      f"{patch_resp.status_code} {patch_resp.text}")
                results["error"] += 1
                continue

        results[method if method in results else "new"] += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print(f"  Backfill complete {'(DRY RUN)' if dry_run else ''}")
    print(f"  Total drugs processed : {total}")
    print(f"  Exact matches         : {results['exact']}")
    print(f"  Normalised matches    : {results['normalized']}")
    print(f"  New canonicals created: {results['new']}")
    print(f"  Errors                : {results['error']}")
    print("═" * 60)

    # ── Fuzzy review report ───────────────────────────────────────────────────
    print("\nChecking for fuzzy review flags in audit log...")
    audit_resp = requests.get(
        f"{sb_url}/rest/v1/identity_audit_log",
        headers={**headers, "Prefer": ""},
        params={
            "operation": "eq.flag_review",
            "performed_by": "eq.identity_resolution.py",
            "select": "canonical_id,related_id,new_value,performed_at",
            "order": "performed_at.desc",
            "limit": "50",
        },
    )
    if audit_resp.status_code == 200:
        flags = audit_resp.json()
        if flags:
            print(f"\n  ⚠ {len(flags)} fuzzy review flag(s) require human attention:")
            for f in flags:
                nv = f.get("new_value") or {}
                print(f"    Input: '{f['related_id']}' ~ canonical {f['canonical_id']} "
                      f"(ratio={nv.get('fuzzy_ratio', '?')})")
            print("\n  Review these in Supabase: SELECT * FROM identity_audit_log "
                  "WHERE operation='flag_review' ORDER BY performed_at DESC;\n"
                  "  Then merge manually by updating drugs.canonical_drug_id if correct.")
        else:
            print("  No fuzzy review flags — all matches were exact or normalised.")
    else:
        print(f"  WARNING: could not fetch audit log: {audit_resp.status_code}")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Backfill canonical_drug_id for all existing drugs"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen without writing to Supabase")
    args = parser.parse_args()

    # Credentials: prefer env vars, fall back to workspace credential files
    sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    sb_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not sb_url or not sb_key:
        # Try reading from workspace credential files (local dev)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        workspace  = os.path.dirname(script_dir)
        try:
            with open(os.path.join(workspace, ".supabase_service_key")) as f:
                sb_key = f.read().strip()
            with open(os.path.join(workspace, ".supabase_config")) as f:
                for line in f:
                    if line.startswith("SUPABASE_URL="):
                        sb_url = line.split("=", 1)[1].strip().rstrip("/")
        except FileNotFoundError as e:
            raise SystemExit(
                f"ERROR: Could not find credentials. Set SUPABASE_URL + "
                f"SUPABASE_SERVICE_KEY env vars, or place credential files in workspace.\n{e}"
            )

    if not sb_url or not sb_key:
        raise SystemExit("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY are required.")

    print(f"Supabase URL : {sb_url}")
    print(f"Dry run      : {args.dry_run}")
    print()

    run_backfill(sb_url, sb_key, dry_run=args.dry_run)
