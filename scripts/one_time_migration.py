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
    # Dry run first (drug canonical backfill)
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python scripts/one_time_migration.py --dry-run

    # Live run (drug canonical backfill)
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python scripts/one_time_migration.py

    # Deals company_id backfill (dry run first, then live)
    python scripts/one_time_migration.py --backfill-deals --dry-run
    python scripts/one_time_migration.py --backfill-deals

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


# ─── Deals company_id backfill ────────────────────────────────────────────────

def _build_company_map(sb_url: str, headers: dict) -> dict:
    """
    Fetch all companies and build a normalised name → company_id lookup.
    Returns a dict: normalised_name → company_id.
    Also includes ticker and common abbreviations stored as lowercase keys.
    """
    resp = requests.get(
        f"{sb_url}/rest/v1/companies",
        headers={**headers, "Prefer": ""},
        params={"select": "id,name,ticker", "limit": "500"},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch companies: {resp.status_code} {resp.text}")

    company_map: dict[str, str] = {}
    for row in resp.json():
        cid  = row.get("id", "").strip()
        name = (row.get("name") or "").strip()
        tick = (row.get("ticker") or "").strip()
        if not cid:
            continue
        # Index by normalised name (lowercase, strip punctuation)
        for variant in [name, tick]:
            if variant:
                company_map[variant.lower()] = cid
                # Also strip common suffixes for partial matching
                for suffix in [" inc", " inc.", " ltd", " ltd.", " plc", " ag",
                                " gmbh", " co.", " & co", " pharmaceuticals",
                                " pharma", " biosciences", " therapeutics"]:
                    if variant.lower().endswith(suffix):
                        company_map[variant.lower()[:-len(suffix)].strip()] = cid
    return company_map


def _resolve_company_name(name: str, company_map: dict) -> str | None:
    """
    Resolve a free-text company name to a company_id using the pre-built map.
    Strategy: exact → normalised exact → substring scan (longest match wins).
    Returns company_id or None if unresolved.
    """
    if not name:
        return None

    # 1. Exact match (case-insensitive)
    key = name.strip().lower()
    if key in company_map:
        return company_map[key]

    # 2. Strip common legal suffixes and retry
    for suffix in [" inc", " inc.", " ltd", " ltd.", " plc", " ag",
                   " gmbh", " co.", " & co", " pharmaceuticals",
                   " pharma", " biosciences", " therapeutics"]:
        if key.endswith(suffix):
            trimmed = key[:-len(suffix)].strip()
            if trimmed in company_map:
                return company_map[trimmed]

    # 3. Substring scan — company map key appears in the input name or vice versa
    #    Prefer the longest matching key to minimise false positives.
    best_key   = None
    best_len   = 0
    for map_key, cid in company_map.items():
        if len(map_key) < 4:
            continue  # skip very short keys (ticker-length) for substring scan
        if map_key in key or key in map_key:
            if len(map_key) > best_len:
                best_key = map_key
                best_len = len(map_key)
    if best_key:
        return company_map[best_key]

    return None


def backfill_deals_company_id(sb_url: str, service_key: str, dry_run: bool = False):
    """
    Find deals written by research.py (company_id IS NULL, from_company is text),
    resolve from_company → company_id via name matching, and PATCH deals rows.

    Rationale: research.py writes deals with free-text from_company/to_company and
    no company_id FK. These deals are invisible in the Company Database profile
    panel which queries deals WHERE company_id = ?. This backfill makes them visible.
    """
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    print("Building company name → id map...")
    company_map = _build_company_map(sb_url, headers)
    print(f"  {len(company_map)} name variants indexed from companies table")

    print("\nFetching deals without company_id...")
    resp = requests.get(
        f"{sb_url}/rest/v1/deals",
        headers={**headers, "Prefer": ""},
        params={
            "select": "id,from_company,to_company,deal_type,deal_date",
            "company_id": "is.null",
            "from_company": "not.is.null",
            "limit": "2000",
        },
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch deals: {resp.status_code} {resp.text}")

    deals = resp.json()
    total = len(deals)
    print(f"Found {total} deals to backfill.\n")

    if total == 0:
        print("Nothing to do — all deals already have company_id set.")
        return

    results = {"patched": 0, "unresolved": 0, "error": 0}
    unresolved_names: list[str] = []

    for i, deal in enumerate(deals, 1):
        deal_id     = deal["id"]
        from_co     = (deal.get("from_company") or "").strip()
        to_co       = (deal.get("to_company") or "").strip()
        deal_type   = deal.get("deal_type", "")
        deal_date   = deal.get("deal_date", "")

        # Primary resolution: from_company (licensor/acquirer is the BD-relevant company)
        cid = _resolve_company_name(from_co, company_map)

        # Fallback to to_company if from_company doesn't resolve
        if not cid and to_co:
            cid = _resolve_company_name(to_co, company_map)

        label = f"'{from_co}'" + (f" / '{to_co}'" if to_co and to_co != from_co else "")
        print(f"  [{i}/{total}] {label}  ({deal_type}, {deal_date})")

        if not cid:
            print(f"    → UNRESOLVED")
            results["unresolved"] += 1
            unresolved_names.append(from_co)
            continue

        print(f"    → {cid}")

        if dry_run:
            print(f"    [DRY RUN] Would PATCH deals id='{deal_id}' with company_id={cid}")
            results["patched"] += 1
        else:
            patch_resp = requests.patch(
                f"{sb_url}/rest/v1/deals",
                headers=headers,
                params={"id": f"eq.{deal_id}"},
                json={"company_id": cid},
            )
            if patch_resp.status_code not in (200, 204):
                print(f"    WARNING: PATCH failed: {patch_resp.status_code} {patch_resp.text}")
                results["error"] += 1
            else:
                results["patched"] += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print(f"  Deals company_id backfill {'(DRY RUN)' if dry_run else 'complete'}")
    print(f"  Total deals processed : {total}")
    print(f"  Successfully patched  : {results['patched']}")
    print(f"  Unresolved            : {results['unresolved']}")
    print(f"  Errors                : {results['error']}")
    print("═" * 60)

    if unresolved_names:
        unique_unresolved = sorted(set(unresolved_names))
        print(f"\n  ⚠ {len(unique_unresolved)} unique company name(s) could not be resolved:")
        for name in unique_unresolved:
            print(f"    '{name}'")
        print("\n  To fix: add these as aliases in the companies table, then re-run.")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="One-time migrations: drug canonical backfill and deals company_id backfill"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen without writing to Supabase")
    parser.add_argument("--backfill-deals", action="store_true",
                        help="Run deals.company_id backfill instead of drug canonical backfill")
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

    if args.backfill_deals:
        backfill_deals_company_id(sb_url, sb_key, dry_run=args.dry_run)
    else:
        run_backfill(sb_url, sb_key, dry_run=args.dry_run)
