"""
catalog_backfill.py — Migrate DRUGS_ALL static array → Supabase drugs table

Reads the DRUGS_ALL JavaScript array directly from index.html, maps each entry
to the drugs table schema, resolves company names via CompanyIdentityResolver,
and upserts all records with data_source='catalog'.

These records are only queried by the Drugs-to-Know tab; they do NOT appear
in Pharma Landscape (which uses drug_areas, not all drugs).

USAGE:
    python scripts/catalog_backfill.py --dry-run   # preview
    python scripts/catalog_backfill.py             # live upsert
"""

import argparse
import json
import os
import re
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from company_identity_resolver import CompanyIdentityResolver, get_credentials


# ── Slugify helper ────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert a drug name to a safe lowercase slug for use as a Supabase ID."""
    import unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text[:80]


# ── Extract DRUGS_ALL from index.html ────────────────────────────────────────

def extract_drugs_all(html_path: str) -> list[dict]:
    """
    Parse the DRUGS_ALL JavaScript array from index.html.
    Returns a list of dicts with the JS object fields.
    """
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find const DRUGS_ALL = [ ... ];
    start = content.find("const DRUGS_ALL = [")
    if start == -1:
        raise RuntimeError("DRUGS_ALL not found in index.html")

    # Find matching bracket close
    bracket_start = content.index("[", start)
    depth = 0
    pos = bracket_start
    while pos < len(content):
        if content[pos] == "[":
            depth += 1
        elif content[pos] == "]":
            depth -= 1
            if depth == 0:
                break
        pos += 1

    array_str = content[bracket_start : pos + 1]

    # Convert JS object syntax to JSON:
    # 1. Replace single-quoted strings → double-quoted
    # 2. Add quotes around unquoted keys
    # 3. Handle trailing commas
    # 4. Handle unicode escapes (α etc.) — already valid JSON

    # Quote bare keys: {id:1, → {"id":1,
    json_str = re.sub(r"(\{|,)\s*([a-zA-Z_]\w*)\s*:", r'\1"\2":', array_str)

    # Trailing comma before } or ] (invalid JSON)
    json_str = re.sub(r",\s*([\}\]])", r"\1", json_str)

    # Remove JS // comments (inline)
    json_str = re.sub(r"//[^\n]*", "", json_str)

    try:
        drugs = json.loads(json_str)
    except json.JSONDecodeError as e:
        # Debug: show context around error
        col = e.colno - 1
        snippet = json_str[max(0, col - 50): col + 50]
        raise RuntimeError(f"JSON parse error at col {e.colno}: ...{snippet!r}...") from e

    return drugs


# ── Company resolution ────────────────────────────────────────────────────────

def resolve_company(company_str: str, resolver: CompanyIdentityResolver) -> str | None:
    """
    Resolve a DRUGS_ALL company string to a Supabase company_id.
    Handles multi-company strings like "Sanofi/Regeneron", "J&J/Legend Biotech".
    Returns the first resolvable company_id.
    """
    if not company_str:
        return None

    # Split on common separators
    parts = re.split(r"[/,&]|\s+and\s+", company_str, flags=re.IGNORECASE)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Skip "ex-" prefixes
        part = re.sub(r"^ex-", "", part, flags=re.IGNORECASE).strip()
        cid = resolver.resolve(part, source="catalog_backfill")
        if cid:
            return cid
    return None


# ── Field mapping ─────────────────────────────────────────────────────────────

STAGE_DISPLAY_MAP = {
    "Approved":     "Approved",
    "Phase 3":      "Phase 3",
    "Phase 2":      "Phase 2",
    "Phase 1":      "Phase 1",
    "Preclinical":  "Preclinical",
    "Research":     "Preclinical",
}

STAGE_SORT = {
    "Approved": 0, "Phase 3": 1, "Phase 2": 2,
    "Phase 1": 3, "Preclinical": 4, "Research": 5,
}


def build_drug_record(d: dict, company_id: str | None, company_display: str | None = None) -> dict:
    """Map a DRUGS_ALL entry to a drugs table row dict."""
    generic = (d.get("generic") or "").strip()
    brand   = (d.get("brand") or "").strip()
    name    = (d.get("name") or generic or brand or "unknown").strip()

    # Generate a stable text ID from the generic name (or full name if no generic)
    id_base = generic or re.sub(r"\s*\(.*?\)", "", name).strip()
    drug_id = slugify(id_base) or f"catalog-{d['id']}"

    stage_raw = (d.get("stage") or "Preclinical").strip()
    # Normalise stage (e.g. "Phase 2" from "Phase 2/3")
    stage = next(
        (k for k in STAGE_DISPLAY_MAP if stage_raw.startswith(k)),
        "Preclinical",
    )

    indication = (d.get("indication") or "").strip()
    # Trim to reasonable length
    indication_short = indication[:120] if indication else ""

    category = (d.get("category") or "Pipeline").strip()
    diff     = (d.get("diff") or "").strip()
    risk     = (d.get("risk") or "").strip()
    notes    = (d.get("notes") or "").strip()
    endpoints = (d.get("endpoints") or "").strip()
    trials   = (d.get("trials") or "").strip()

    # Combine risk + notes into drug_summary
    drug_summary_parts = []
    if risk:
        drug_summary_parts.append(f"Risk: {risk}")
    if notes:
        drug_summary_parts.append(notes)
    drug_summary = " | ".join(drug_summary_parts) if drug_summary_parts else None

    return {
        "id":                   drug_id,
        "name":                 generic or name,
        "display_name":         name,
        "brand_name":           brand or None,
        "company_id":           company_id,
        "target":               (d.get("target") or "").strip() or None,
        "cls":                  (d.get("cls") or "").strip() or None,
        "stage":                stage,
        "phase_display":        stage_raw,
        "indication_short":     indication_short or None,
        "differentiation_thesis": diff or None,
        "drug_summary":         drug_summary,
        "endpoints":            endpoints or None,
        "trial_names":          trials or None,
        "catalog_category":     category,
        "data_source":          "catalog",
        "overlap":              "Watch",   # default for catalog drugs; enrichment will update
        "entity_type":          "standalone",
        "company_display":      company_display or None,
    }


# ── Main backfill ─────────────────────────────────────────────────────────────

def run_catalog_backfill(sb_url: str, service_key: str, dry_run: bool = False):
    headers = {
        "apikey":        service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }

    # Find index.html
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace  = os.path.dirname(script_dir)
    html_path  = os.path.join(workspace, "index.html")

    print(f"Extracting DRUGS_ALL from {html_path}...")
    drugs = extract_drugs_all(html_path)
    print(f"  Found {len(drugs)} entries")

    print("\nInitialising CompanyIdentityResolver...")
    resolver = CompanyIdentityResolver(sb_url, service_key, dry_run=dry_run)

    results = {"inserted": 0, "skipped_existing": 0, "unresolved_co": 0, "error": 0}
    unresolved_companies: list[str] = []
    id_map: dict[int, str] = {}  # DRUGS_ALL integer id → Supabase text id

    print(f"\nProcessing {len(drugs)} drugs...\n")
    for d in drugs:
        int_id      = d.get("id")
        company_str = (d.get("company") or "").strip()

        company_id = resolve_company(company_str, resolver)
        if not company_id:
            results["unresolved_co"] += 1
            unresolved_companies.append(company_str)

        record = build_drug_record(d, company_id, company_display=company_str or None)
        id_map[int_id] = record["id"]

        co_display = company_id or f"?({company_str})"
        print(f"  [{d['id']:>3}] {record['display_name'][:45]:<45}  co={co_display:<15}  id={record['id']}")

        if dry_run:
            results["inserted"] += 1
            continue

        # Upsert — on conflict (same id), update all fields
        resp = requests.post(
            f"{sb_url}/rest/v1/drugs",
            headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=record,
        )
        if resp.status_code in (200, 201, 204):
            results["inserted"] += 1
        else:
            print(f"    ERROR {resp.status_code}: {resp.text[:200]}")
            results["error"] += 1

    # Write ID map to a JSON file for use by the frontend migration
    if not dry_run:
        id_map_path = os.path.join(workspace, "data", "drugs_all_id_map.json")
        os.makedirs(os.path.dirname(id_map_path), exist_ok=True)
        with open(id_map_path, "w") as f:
            json.dump(id_map, f, indent=2)
        print(f"\nID map saved to {id_map_path}")

    print(f"\n{'═' * 60}")
    print(f"  Catalog backfill {'(DRY RUN) ' if dry_run else ''}complete")
    print(f"  Total processed      : {len(drugs)}")
    print(f"  Upserted             : {results['inserted']}")
    print(f"  Company unresolved   : {results['unresolved_co']}")
    print(f"  Errors               : {results['error']}")
    print(f"{'═' * 60}")

    if unresolved_companies:
        unique = sorted(set(unresolved_companies))
        print(f"\n  ⚠ {len(unique)} unique company string(s) unresolved:")
        for c in unique:
            print(f"    '{c}'")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill DRUGS_ALL catalog to Supabase drugs table")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sb_url, sb_key = get_credentials()
    print(f"Supabase URL : {sb_url}")
    print(f"Dry run      : {args.dry_run}\n")
    run_catalog_backfill(sb_url, sb_key, dry_run=args.dry_run)
