#!/usr/bin/env python3
"""
source_verify.py — Targeted source_url + confidence_level population for drug_area_scores.

Fills in source_url and confidence_level for Direct/Adjacent drug_area_scores rows
where these fields are null. Uses Claude's training knowledge (no web search) — fast,
~3-5s per drug. Processes ~8 drugs per 45s bash window.

Usage:
    # All Direct rows with null source_url (default):
    python3 scripts/source_verify.py

    # Specific drug IDs:
    python3 scripts/source_verify.py --drug-ids afimkibart duvakitug spy002

    # Specific company:
    python3 scripts/source_verify.py --company caldera

    # Specific area only:
    python3 scripts/source_verify.py --area tl1a

    # Dry run (no writes):
    python3 scripts/source_verify.py --dry-run --drug-ids afimkibart

    # Batch size (drugs per Claude call):
    python3 scripts/source_verify.py --batch-size 4
"""

import os, sys, json, time, hashlib, datetime, argparse
from typing import Optional

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from _common import load_credentials  # noqa: E402
import _db                             # noqa: E402
import ai.client as ai_client          # noqa: E402
from ai.client import PromptConfig     # noqa: E402

SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY = load_credentials()
_db.init_db(SUPABASE_URL, SUPABASE_KEY)
ai_client.setup(ANTHROPIC_API_KEY)

TODAY  = datetime.datetime.utcnow().strftime("%Y-%m-%d")
MODEL  = "claude-sonnet-4-6"

# ── Supabase helpers ──────────────────────────────────────────────────────────
sb_get = _db.sb_get


def _parse_filter_qs(filter_qs: str) -> dict:
    """Split an '&'-joined 'col=op.val' query string into a match-params dict."""
    parts = {}
    for piece in filter_qs.split("&"):
        col, _, val = piece.partition("=")
        parts[col] = val
    return parts


def sb_patch(table: str, match: str, record: dict) -> bool:
    return _db.sb_patch(table, record, _parse_filter_qs(match))

def log(msg: str):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ── Fetch candidate rows ──────────────────────────────────────────────────────
def fetch_candidates(drug_ids: list, company: str, area: str) -> list:
    """Return drug_area_scores rows with null source_url (filtered by args)."""
    params = {
        "select":    "drug_id,area_id,overlap,source_url,confidence_level",
        "source_url": "is.null",
        "overlap":   "in.(Direct,Adjacent)",
        "limit":     "200",
    }
    if area:
        params["area_id"] = f"eq.{area}"
    rows = sb_get("drug_area_scores", params)

    if drug_ids:
        rows = [r for r in rows if r["drug_id"] in drug_ids]

    if company:
        # Filter by company_id via drugs table
        drug_rows = sb_get("drugs", {
            "company_id": f"eq.{company}",
            "select":     "id",
        })
        co_drug_ids = {d["id"] for d in drug_rows}
        rows = [r for r in rows if r["drug_id"] in co_drug_ids]

    return rows

# ── Fetch drug context ────────────────────────────────────────────────────────
def fetch_drug_context(drug_id: str) -> dict:
    rows = sb_get("drugs", {
        "id":     f"eq.{drug_id}",
        "select": "id,name,display_name,target,stage,company_id,partner_company,cls",
    })
    return rows[0] if rows else {"id": drug_id}

# ── Build prompt ──────────────────────────────────────────────────────────────
SYSTEM = """You are a biopharma data quality analyst. Your job is to identify the single best
public source URL for each drug-area entry, and assign a confidence level based on how
verifiable the information is from public sources.

For each drug, return:
- source_url: The single most authoritative public URL. Priority order:
  (1) ClinicalTrials.gov study URL: https://clinicaltrials.gov/study/NCTxxxxxxxx
  (2) Company pipeline/IR page URL
  (3) Press release or SEC filing URL
  Set null ONLY when you genuinely cannot identify a URL. NEVER fabricate URLs.
  If you know an NCT number exists but cannot verify the exact URL, set null.

- confidence_level: One of:
  "confirmed" — you know a primary source URL (CT.gov, FDA label, company press release)
  "supported"  — credible secondary sources but no single primary URL
  "inferred"   — classified from mechanism/indication; no direct public source found

Return ONLY a JSON array. No markdown, no explanation."""

def build_prompt(batch: list) -> str:
    lines = []
    for item in batch:
        drug   = item["drug"]
        row    = item["row"]
        name   = drug.get("display_name") or drug.get("name") or drug["id"]
        target = drug.get("target", "unknown")
        stage  = drug.get("stage", "unknown")
        co     = drug.get("company_id", "unknown")
        area   = row["area_id"]
        lines.append(
            f"- drug_id: {drug['id']}, name: {name}, target: {target}, "
            f"stage: {stage}, company: {co}, area: {area}"
        )

    drugs_block = "\n".join(lines)
    return f"""Provide source_url and confidence_level for each of the following drugs.
Use your training knowledge of clinical trials, company pipelines, and public databases.

Drugs:
{drugs_block}

Return a JSON array, one object per drug, in the same order:
[
  {{
    "drug_id": "<id>",
    "area_id": "<area>",
    "source_url": "<url or null>",
    "confidence_level": "confirmed|supported|inferred"
  }},
  ...
]"""

# ── Claude call ───────────────────────────────────────────────────────────────
_SOURCE_LOOKUP_CFG = PromptConfig(name="source_verify_lookup", system=SYSTEM, model=MODEL, max_tokens=1000)


def call_claude(batch: list) -> list:
    prompt = build_prompt(batch)
    # run_text (not run_json): the response is a JSON *array*, and ai_client._parse_json
    # only handles top-level JSON objects.
    raw = ai_client.run_text(_SOURCE_LOOKUP_CFG, prompt, timeout=30.0).strip()
    if not raw:
        log("  Claude call failed or returned empty response")
        return []
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log(f"  JSON parse error: {e} — raw: {raw[:200]}")
        return []

# ── Write results ─────────────────────────────────────────────────────────────
def write_results(results: list, dry_run: bool) -> tuple[int, int]:
    ok_count  = 0
    err_count = 0
    for r in results:
        drug_id  = r.get("drug_id")
        area_id  = r.get("area_id")
        src_url  = r.get("source_url")
        conf     = r.get("confidence_level")

        if not drug_id or not area_id:
            log(f"  ⚠ Missing drug_id or area_id — skipping")
            err_count += 1
            continue

        if conf not in ("confirmed", "supported", "inferred"):
            log(f"  ⚠ {drug_id}/{area_id}: invalid confidence '{conf}' — skipping")
            err_count += 1
            continue

        tag  = "✓" if src_url else "~"
        disp = src_url[:60] if src_url else "(null — inferred)"
        log(f"  {tag} {drug_id}/{area_id}: {conf} | {disp}")

        if dry_run:
            ok_count += 1
            continue

        patch = {
            "source_url":       src_url,
            "confidence_level": conf,
            "enriched_model":   MODEL,
        }
        ok = sb_patch(
            "drug_area_scores",
            f"drug_id=eq.{drug_id}&area_id=eq.{area_id}",
            patch,
        )
        if ok:
            ok_count += 1
        else:
            err_count += 1

    return ok_count, err_count

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Populate drug_area_scores.source_url")
    parser.add_argument("--drug-ids", nargs="+", default=[],
                        help="Specific drug IDs to process")
    parser.add_argument("--company",  default=None,
                        help="Filter by company_id")
    parser.add_argument("--area",     default=None,
                        help="Filter by area_id (e.g. tl1a, ibd, fcrn)")
    parser.add_argument("--batch-size", type=int, default=6,
                        help="Drugs per Claude call (default: 6)")
    parser.add_argument("--dry-run",  action="store_true",
                        help="No Supabase writes")
    args = parser.parse_args()

    log(f"source_verify.py — {TODAY} | model: {MODEL} | dry_run: {args.dry_run}")

    # 1. Fetch candidate rows
    candidates = fetch_candidates(args.drug_ids, args.company, args.area)
    log(f"Found {len(candidates)} drug_area_scores rows with null source_url")

    if not candidates:
        log("Nothing to do.")
        return

    # 2. Fetch drug context for each candidate
    drug_cache = {}
    drug_ids_needed = list(set(r["drug_id"] for r in candidates))
    for did in drug_ids_needed:
        drug_cache[did] = fetch_drug_context(did)

    # 3. Build batches
    items = []
    for row in candidates:
        items.append({"row": row, "drug": drug_cache.get(row["drug_id"], {"id": row["drug_id"]})})

    batches = [items[i:i+args.batch_size] for i in range(0, len(items), args.batch_size)]
    log(f"Processing {len(items)} items in {len(batches)} batches of ≤{args.batch_size}")

    total_ok  = 0
    total_err = 0

    for i, batch in enumerate(batches):
        batch_drug_ids = [b["drug"]["id"] for b in batch]
        log(f"\nBatch {i+1}/{len(batches)}: {batch_drug_ids}")

        results = call_claude(batch)
        if not results:
            log("  No results from Claude — skipping batch")
            total_err += len(batch)
            continue

        ok, err = write_results(results, args.dry_run)
        total_ok  += ok
        total_err += err

        if i < len(batches) - 1:
            time.sleep(1)  # brief pause between batches

    log(f"\n{'='*50}")
    log(f"Complete: {total_ok} written, {total_err} errors")
    log(f"{'='*50}")

if __name__ == "__main__":
    main()
