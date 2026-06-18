#!/usr/bin/env python3
"""
Ailux BD Platform — Systematic Intelligence Pipeline
=====================================================
The full 7-step conditional intelligence model.

ARCHITECTURE:
  Strategic Competitive Entity (top-level unit in the dashboard)
    └── Drugs / Programs     (one or many per entity)
          └── Trials         (synced by ct_gov_sync.py — Step 3)
                └── Catalysts (generated from trial dates — Step 4)
    └── Deals                (discovered + enriched — Step 6)
    └── Company Profile      (narrative fields — Step 5)

STEP OVERVIEW (if/then logic):

  STEP 1 — Entity Discovery
    IF new competitor found in target/disease space:
      → Create strategic entity, drug, company records
      → tag discovery_status='auto', confidence_score
    Called once per area per pipeline run.

  STEP 2 — Drug Mapping  (handled by Supabase entity_id on drugs)
    IF entity has one drug → show single drug in expanded row
    IF entity has multiple drugs → group under platform entity
    IF two companies share one asset → entity_type = 'partnership'
    (The data model enforces this; no runtime step needed here.)

  STEP 3 — Trial Sync  (handled by ct_gov_sync.py — runs BEFORE this script)
    IF drug has known NCT IDs → fetch from CT.gov, upsert trials table
    IF drug has no NCT ID → search CT.gov by name
    This script reads from the already-populated trials table.

  STEP 4 — Catalyst Generation
    IF trial has primary_completion_date → create upcoming catalyst
    IF company disclosed expected data timing → override with company date
    IF catalyst date has passed → mark resolved, search for results

  STEP 5 — Company Enrichment (Claude Sonnet)
    IF company profile is incomplete → generate all narrative fields
    IF public company → collect market cap, cash runway
    IF private → collect financing history, key investors
    Writes: company_profiles (all fields), drugs (detail columns)

  STEP 6 — Deal Intelligence
    IF new deal found for company/asset → create deal record
    IF existing deal missing fields → back-fill from Claude synthesis

  STEP 7 — Dashboard Integration (handled by frontend JS)
    The dashboard reads directly from Supabase — no pipeline step needed.

USAGE:
  python src/meridian/enrichment/company_enrichment.py --area tl1a
  python src/meridian/enrichment/company_enrichment.py --area tl1a --company sanofi
  python src/meridian/enrichment/company_enrichment.py --area tl1a --discover-only
  python src/meridian/enrichment/company_enrichment.py --area tl1a --dry-run

DEPENDS ON:
  ct_gov_sync.py is optional — enrichment now auto-syncs missing trials from CT.gov
  before calling Claude, so it is self-contained for drugs with zero trial rows.

ENVIRONMENT:
  ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import os
import sys
import json
import time
import datetime
import argparse
import re
from typing import Optional, List

import requests
import anthropic

try:
    from pydantic import BaseModel, Field as PydanticField
    _PYDANTIC_AVAILABLE = True

    class DrugEnrichmentOutput(BaseModel):
        mechanism: Optional[str] = None
        ailux_angle: Optional[str] = None
        drug_summary: Optional[str] = None
        source_url: Optional[str] = None
        overlap: Optional[str] = None
        overlap_rationale: Optional[str] = None
        differentiation_thesis: Optional[str] = None

except ImportError:
    _PYDANTIC_AVAILABLE = False
    DrugEnrichmentOutput = None  # type: ignore[assignment,misc]

# Ensure the scripts/ directory is on sys.path so relative imports work
# whether the script is invoked from the repo root or from scripts/ directly.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

try:
    from meridian.identity.identity_resolution import DrugIdentityResolver
    _IDENTITY_RESOLVER_AVAILABLE = True
except ImportError:
    _IDENTITY_RESOLVER_AVAILABLE = False

try:
    from meridian.identity.model_comparison import log_enrichment_run, update_enrichment_run, patch_enrichment_run, build_enrichment_summary
    _MODEL_COMPARISON_AVAILABLE = True
except ImportError:
    _MODEL_COMPARISON_AVAILABLE = False
    def log_enrichment_run(*args, **kwargs):   # type: ignore[misc]
        return None
    def update_enrichment_run(*args, **kwargs): # type: ignore[misc]
        return False
    def patch_enrichment_run(*args, **kwargs): # type: ignore[misc]
        return False
    def build_enrichment_summary(*args, **kwargs):  # type: ignore[misc]
        return None


from meridian.enrichment.company.prompts import (
    enrichment_system_prompt,
    build_step5_prompt,
)


# ══════════════════════════════════════════════════════════════════════════
# SHARED BASE — credentials, LLM client, Supabase I/O, logging, validation.
# Extracted to company/common.py (§3 split); imported here so existing call
# sites are unchanged. New feature modules import from common.py directly.
# ══════════════════════════════════════════════════════════════════════════
from meridian.enrichment.company.common import (
    client, _RUN_TOKENS, _acc_tokens,
    SUPABASE_URL, SUPABASE_KEY,
    TODAY, NOW_ISO,
    VALID_AREA_IDS, normalize_area_id, AREA_LABELS_MAP,
    KNOWN_DRUG_TARGETS, infer_catalog_category,
    validate_source_url, enforce_confidence_constraints,
    log,
    sb_get, sb_upsert, sb_post, sb_delete, sb_patch, _catalyst_upsert,
    update_system_status,
)


from meridian.enrichment.company.resolve import (
    COMPANY_ALIASES,
    get_company_map,
    resolve_company_id,
)


from meridian.enrichment.company.discovery import (
    gather_landscape_intel,
    step1_discover_new_entities,
)


from meridian.enrichment.company.trials import (
    _pre_sync_trials_from_ctgov,
    _refresh_existing_trials_from_ctgov,
    fetch_company_context,
)


from meridian.enrichment.company.catalysts import (
    _parse_sort_date,
    step4_generate_catalysts_from_trials,
)


from meridian.enrichment.company.assessment import (
    gather_web_intelligence,
    parse_enrichment_response,
    write_step5,
)


from meridian.enrichment.company.deals import step6_deal_intelligence


from meridian.enrichment.company.scoring import _score_company_completeness


# ══════════════════════════════════════════════════════════════════════════
# PER-COMPANY ORCHESTRATION — Steps 4, 5, 6
# ══════════════════════════════════════════════════════════════════════════

def enrich_company(company_id: str, area_id: str, company_map: dict,
                   dry_run: bool = False, resolver=None,
                   skip_web_search: bool = False,
                   skip_trial_refresh: bool = False,
                   fast_model: bool = False,
                   enrichment_run_id: Optional[str] = None) -> bool:
    """Run Steps 4-6 for one company.

    Args:
      resolver:            a pre-instantiated DrugIdentityResolver (passed from run_intelligence_pipeline).
      enrichment_run_id:   UUID of the parent enrichment_runs row (from log_enrichment_run).
                           When set, stamped on drug/company rows as last_enrichment_run_id.
    """
    log(f"\n{'='*56}")
    log(f"Enriching: {company_id} / {area_id}")
    log(f"{'='*56}")

    log("Fetching Supabase context...", indent=1)
    ctx = fetch_company_context(company_id, area_id,
                                skip_trial_refresh=skip_trial_refresh)
    log(f"  {len(ctx['drugs'])} drugs | {len(ctx['trials'])} trials | "
        f"{len(ctx['catalysts'])} catalysts | {len(ctx['deals'])} deals | "
        f"{len(ctx['recent_intel'])} intel items", indent=1)

    # STEP 4: Auto-catalysts from trial dates
    log("STEP 4 — Catalyst auto-generation...", indent=1)
    cats = step4_generate_catalysts_from_trials(company_id, area_id, ctx, dry_run)
    log(f"  {cats} new catalysts", indent=1)

    # STEP 5: Claude narrative enrichment
    log("STEP 5 — Claude enrichment...", indent=1)

    # Phase A: Web intelligence gathering (live search, non-fatal)
    # Skip when --skip-web-search is set (e.g. source_url re-enrichment runs where
    # Claude's training data is sufficient and speed matters more than live data).
    co = ctx["company"]
    log("  Phase A — Web intelligence search...", indent=1)
    web_intel = ""
    if not skip_web_search:
        web_intel = gather_web_intelligence(
            company_name=co.get("name", company_id),
            area_id=area_id,
            drugs=ctx["drugs"],
            ticker=co.get("ticker", ""),
        )
        if web_intel:
            log(f"  Web intelligence gathered ({len(web_intel)} chars)", indent=1)
        else:
            log("  No web intelligence (continuing with Supabase context only)", indent=1)
    else:
        log("  Skipped (--skip-web-search flag set) — using Supabase context only", indent=1)

    # Phase B: Claude synthesis with web context injected
    log("  Phase B — Claude synthesis...", indent=1)
    prompt = build_step5_prompt(company_id, area_id, ctx, web_intel=web_intel)

    _synthesis_model = "claude-haiku-4-5-20251001" if fast_model else "claude-sonnet-4-6"
    _synthesis_tokens = 4096 if fast_model else 8192
    if fast_model:
        log(f"  [fast mode] Using {_synthesis_model} (max_tokens={_synthesis_tokens})", indent=1)

    text = None
    for attempt in range(1, 4):
        try:
            resp = client.messages.create(
                model=_synthesis_model, max_tokens=_synthesis_tokens,
                system=enrichment_system_prompt(),
                messages=[{"role": "user", "content": prompt}]
            )
            text = resp.content[0].text
            _acc_tokens(resp)
            cost = (resp.usage.input_tokens / 1e6 * 3.0 +
                    resp.usage.output_tokens / 1e6 * 15.0)
            finish = getattr(resp, 'stop_reason', None)
            log(f"  {resp.usage.input_tokens}in / {resp.usage.output_tokens}out (${cost:.4f}) stop={finish}", indent=1)
            # Detect truncation — if stop_reason is max_tokens, the JSON is incomplete
            if finish == 'max_tokens':
                log("  WARNING: response truncated at max_tokens — JSON will be incomplete, retrying is unlikely to help. Increase max_tokens or shorten prompt.", indent=1)
            break
        except Exception as e:
            log(f"  Claude error (attempt {attempt}/3): {e}", indent=1)
            if attempt < 3:
                time.sleep(10 * attempt)

    if text is None:
        log("  Claude failed — skipping", indent=1)
        return False

    # ── v59 trajectory capture: store raw LLM response ───────────────────────
    if enrichment_run_id and not dry_run:
        try:
            patch_enrichment_run(enrichment_run_id, {
                "raw_llm_response": (text or "")[:8000],
                "entity_id":        company_id,
                "skill_name":       "company_enrich",
            })
        except Exception as _traj_exc:
            log(f"  [trajectory] raw_llm_response patch failed (non-fatal): {_traj_exc}", indent=2)

    data = parse_enrichment_response(text)
    if not data:
        log("  Parse failed — skipping", indent=1)
        return False

    # ── v59 Pydantic schema validation on drug_updates fields ────────────────
    # Validates the specific fields in DrugEnrichmentOutput schema before DB writes.
    # If validation fails for any field, that field is skipped; schema_valid = False.
    # All validation logic is wrapped in try/except so failures never block enrichment.
    _VALIDATED_DRUG_FIELDS = {"mechanism", "ailux_angle", "drug_summary",
                               "source_url", "overlap", "overlap_rationale",
                               "differentiation_thesis"}
    _fields_attempted: list = []
    _fields_changed:   list = []
    _fields_confirmed: list = []
    _fields_failed:    list = []
    _schema_valid: Optional[bool] = None
    _correction_count = 0

    try:
        # Build lookup of existing (pre-enrichment) drug field values from context
        _ctx_drug_map = {d["id"]: d for d in ctx.get("drugs", [])}

        for du in (data.get("drug_updates") or []):
            drug_id_val = du.get("drug_id") or ""
            old_drug = _ctx_drug_map.get(drug_id_val, {})

            for field in _VALIDATED_DRUG_FIELDS:
                new_val = du.get(field)
                if new_val is None:
                    continue
                _fields_attempted.append(field)

                # Pydantic validation: build a single-field model and validate
                if _PYDANTIC_AVAILABLE and DrugEnrichmentOutput is not None:
                    try:
                        DrugEnrichmentOutput(**{field: new_val})
                    except Exception as _val_err:
                        log(f"  [schema] {drug_id_val}.{field} failed validation: {_val_err}", indent=2)
                        _fields_failed.append(f"{drug_id_val}.{field}")
                        # Remove from du so write_step5 skips it
                        du.pop(field, None)
                        continue

                # Track changed vs confirmed vs corrected
                old_val = old_drug.get(field)
                if old_val and old_val == new_val:
                    _fields_confirmed.append(f"{drug_id_val}.{field}")
                elif old_val and old_val != new_val:
                    _fields_changed.append(f"{drug_id_val}.{field}")
                    _correction_count += 1
                else:
                    # Field was empty before → new value
                    _fields_changed.append(f"{drug_id_val}.{field}")

        _schema_valid = len(_fields_failed) == 0
        log(f"  [schema] attempted={len(_fields_attempted)} changed={len(_fields_changed)} "
            f"confirmed={len(_fields_confirmed)} failed={len(_fields_failed)} "
            f"corrections={_correction_count}", indent=1)

    except Exception as _schema_exc:
        log(f"  [schema] validation block error (non-fatal): {_schema_exc}", indent=2)

    write_step5(company_id, area_id, data, ctx, dry_run,
                enrichment_run_id=enrichment_run_id)

    # ── v59 trajectory capture: patch enrichment_runs with field tracking ─────
    if enrichment_run_id and not dry_run:
        try:
            _traj_patch: dict = {
                "fine_tune_eligible": True,
            }
            if _fields_attempted:
                _traj_patch["fields_attempted"] = _fields_attempted
            if _fields_changed:
                _traj_patch["fields_changed"] = _fields_changed
            if _fields_confirmed:
                _traj_patch["fields_confirmed"] = _fields_confirmed
            if _fields_failed:
                _traj_patch["fields_failed"] = _fields_failed
            if _schema_valid is not None:
                _traj_patch["schema_valid"] = _schema_valid
            if _correction_count:
                _traj_patch["correction_count"] = _correction_count
            patch_enrichment_run(enrichment_run_id, _traj_patch)
        except Exception as _traj_exc2:
            log(f"  [trajectory] field-tracking patch failed (non-fatal): {_traj_exc2}", indent=2)

    # POST-ENRICHMENT COMPLETENESS SCORING
    log("  Completeness scoring...", indent=1)
    cs = _score_company_completeness(company_id, area_id, data, ctx)
    c_score  = cs["score"]
    c_tier   = cs["tier"]
    c_missing = cs["missing"]
    log(f"  Score: {c_score}/100 ({c_tier}) | {len(c_missing)} missing field(s)", indent=1)
    if c_missing:
        log(f"    Missing: {', '.join(c_missing[:8])}", indent=2)
    if not dry_run:
        # Write score + missing_fields to company_profiles
        # Profile row must exist (just written above) — safe to patch
        ok = sb_patch("company_profiles", {
            "completeness_score":      c_score,
            "missing_fields":          c_missing,
            "completeness_checked_at": NOW_ISO,
        }, {"company_id": f"eq.{company_id}", "area_id": f"eq.{area_id}"})
        if not ok:
            log("  ⚠ completeness score patch failed — profile row may not exist yet", indent=1)

    # STEP 6: Deal intelligence
    log("STEP 6 — Deal intelligence...", indent=1)
    deals = step6_deal_intelligence(company_id, area_id, ctx, company_map, dry_run,
                                    resolver=resolver)
    log(f"  {deals} new deals", indent=1)

    return True


# ══════════════════════════════════════════════════════════════════════════
# RECONCILIATION — post-run cleanup for an area
#
# Runs after all enrichment is complete. Two jobs:
#
# Job A — Stale removal:
#   Any company in company_areas that has ZERO drugs (in drug_areas) AND
#   ZERO combo programs (in drug_combinations) for this area gets removed
#   from company_areas. They disappear from the PI table automatically.
#   Safe: company + drug records are NOT deleted — only the area link.
#
# Job B — Ghost entity detection:
#   Companies in this area with the same ticker but different IDs are flagged.
#   This catches any sub-entities that slipped past the improved resolver.
#   Logs them clearly so they can be merged manually or auto-merged in future.
#
# Skipped when company_filter is set (targeted runs don't reconcile the whole area).
# ══════════════════════════════════════════════════════════════════════════

def reconcile_company_areas(area_id: str, dry_run: bool = False) -> dict:
    """Post-run reconciliation for a disease area."""
    log(f"\n── Reconciliation: area={area_id} ──")
    results = {"stale_removed": 0, "ghost_flagged": 0}

    # All companies currently linked to this area
    ca_rows = sb_get("company_areas", {"area_id": f"eq.{area_id}", "select": "company_id"})
    all_company_ids = [r["company_id"] for r in ca_rows]
    if not all_company_ids:
        log("  No companies in area — nothing to reconcile", indent=1)
        return results

    # Which companies have drugs in this area (via drug_areas)?
    # A company "has a program" in an area through ANY of these paths — all count,
    # so reconciliation must not delete a legitimately-linked company:
    #   1. direct        — a drug whose company_id is the company (originator)
    #   2. acquired-sub  — a drug whose originator is an acquired subsidiary whose
    #                      parent_company_id is the company (e.g. tulisokibart →
    #                      prometheus(acquired) → merck)
    #   3. co-dev/license — a drug whose partner_company resolves to the company
    #                      (e.g. dupilumab → partner Regeneron; sim0709 → Boehringer)
    da_rows = sb_get("drug_areas", {"area_id": f"eq.{area_id}", "select": "drug_id"})
    drug_ids_in_area = {r["drug_id"] for r in da_rows}
    companies_with_drugs: set[str] = set()
    partner_names: set[str] = set()
    if drug_ids_in_area:
        chunk = list(drug_ids_in_area)[:300]
        drug_rows = sb_get("drugs", {
            "id": f"in.({','.join(chunk)})",
            "select": "id,company_id,partner_company",
        })
        companies_with_drugs = {d["company_id"] for d in drug_rows if d.get("company_id")}
        partner_names = {d["partner_company"] for d in drug_rows if d.get("partner_company")}

    # Path 2 — roll acquired subsidiaries up to their parent.
    acquired = sb_get("companies", {"status": "eq.acquired", "select": "id,parent_company_id"})
    sub_to_parent = {c["id"]: c["parent_company_id"] for c in acquired if c.get("parent_company_id")}
    rolled_up = {sub_to_parent[c] for c in companies_with_drugs if c in sub_to_parent}

    # Path 3 — resolve partner company NAMES to ids (co-development / licensing).
    partner_ids: set[str] = set()
    if partner_names:
        all_cos = sb_get("companies", {"select": "id,name"})
        name_to_id = {(c.get("name") or "").strip().lower(): c["id"] for c in all_cos}
        for pn in partner_names:
            key = pn.strip().lower()
            pid = COMPANY_ALIASES.get(key) or name_to_id.get(key)
            if pid:
                partner_ids.add(pid)

    # Which companies have combo programs in this area?
    combo_rows = sb_get("drug_combinations", {
        "area_id": f"eq.{area_id}",
        "select": "company_id",
    })
    companies_with_combos = {r["company_id"] for r in combo_rows}

    companies_with_programs = (companies_with_drugs | companies_with_combos
                               | rolled_up | partner_ids)

    # ── Job A: remove stale company_areas links ──────────────────────────
    stale = [cid for cid in all_company_ids if cid not in companies_with_programs]
    if stale:
        log(f"  Stale companies (no programs in '{area_id}'): {stale}", indent=1)
        for cid in stale:
            if dry_run:
                log(f"    [DRY RUN] Would remove {cid} from company_areas", indent=2)
            else:
                n = sb_delete("company_areas", {
                    "company_id": f"eq.{cid}",
                    "area_id":    f"eq.{area_id}",
                })
                log(f"    ✓ Removed {cid} from company_areas ({n} rows)", indent=2)
                results["stale_removed"] += 1
    else:
        log("  Job A: no stale companies", indent=1)

    # ── Job B: detect ghost entities (same ticker, multiple company IDs) ──
    if all_company_ids:
        co_details = sb_get("companies", {
            "id":     f"in.({','.join(all_company_ids[:150])})",
            "select": "id,name,ticker,group_id",
        })
        ticker_to_ids: dict[str, list[str]] = {}
        for co in co_details:
            t = (co.get("ticker") or "").strip().upper()
            if not t or t == "PRIVATE":
                continue
            ticker_to_ids.setdefault(t, []).append(co["id"])

        for ticker, ids in ticker_to_ids.items():
            if len(ids) > 1:
                log(f"  ⚠ Ghost entities — ticker '{ticker}' → {ids}", indent=1)
                log(f"    Action: set group_id on sub-entities to canonical ID, then re-run.", indent=2)
                results["ghost_flagged"] += 1

        if results["ghost_flagged"] == 0:
            log("  Job B: no ghost entities", indent=1)

    log(f"  Done — stale_removed={results['stale_removed']}  ghost_flagged={results['ghost_flagged']}")
    return results


# ══════════════════════════════════════════════════════════════════════════
# COVERAGE PASS — ensure every drug gets enriched at least once
# ══════════════════════════════════════════════════════════════════════════

def enrich_never_touched_drugs(limit: int = 10, dry_run: bool = False) -> int:
    """
    Coverage pass: pick drugs with last_synced_date IS NULL (never enriched)
    and run a lightweight Claude enrichment to fill target, mechanism,
    drug_summary, ailux_angle, differentiation_thesis.

    Falls back to stale drugs (last_synced_date > 14 days ago) if nothing new.

    Called at the end of run_intelligence_pipeline() — after all area-based
    company enrichment passes are done — so it doesn't block primary work.

    Returns: count of drugs updated.
    """
    log(f"\n{'─'*56}")
    log("Coverage Pass — drugs with no last_synced_date")
    log(f"{'─'*56}")

    # 1. Never-enriched drugs first
    never = sb_get("drugs", {
        "select": "id,name,display_name,catalog_category,company_id,stage,target,mechanism,last_synced_date",
        "last_synced_date": "is.null",
        "catalog_category": "not.is.null",   # skip bare stubs with no category
        "limit": str(limit),
        "order": "created_at.asc",
    })

    if not never:
        # Fallback: stale drugs enriched more than 14 days ago
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=14)).strftime("%Y-%m-%d")
        never = sb_get("drugs", {
            "select": "id,name,display_name,catalog_category,company_id,stage,target,mechanism,last_synced_date",
            "last_synced_date": f"lte.{cutoff}",
            "limit": str(limit),
            "order": "last_synced_date.asc",
        })
        if never:
            log(f"  No never-enriched drugs found; falling back to {len(never)} stale (>14d) drugs")

    if not never:
        log("  Coverage pass: nothing to do")
        return 0

    log(f"  {len(never)} drug(s) selected for coverage enrichment")

    _COVERAGE_SYSTEM = (
        "You are Meridian, a pharmaceutical intelligence assistant. "
        "Research the given drug and return structured JSON. "
        "Use null for fields you cannot determine — do NOT hallucinate."
    )

    updated = 0
    for drug in never:
        did   = drug["id"]
        dname = drug.get("display_name") or drug.get("name") or did
        stage = drug.get("stage") or "unknown"
        cat   = drug.get("catalog_category") or "unknown"

        log(f"\n  Drug: {dname} ({did}) | stage={stage} | cat={cat}", indent=1)

        prompt = (
            f'Research the pharmaceutical drug "{dname}" (ID: {did}, stage: {stage}, '
            f'category: {cat}).\n\n'
            "Return JSON only:\n"
            "{\n"
            '  "target": "molecular target(s), e.g. TL1A, PD-1, IL-23p19",\n'
            '  "mechanism": "2–3 sentence mechanistic description",\n'
            '  "differentiation_thesis": "1–2 sentence unique value vs class",\n'
            '  "ailux_angle": "1–2 sentence relevance to TL1A×IL-23p19 bispecific program",\n'
            '  "drug_summary": "3–4 sentence overview: what it is, stage, key data, maker",\n'
            '  "stage": "Preclinical|Phase 1|Phase 2|Phase 3|NDA Filed|Approved|Discontinued",\n'
            '  "indication_short": "primary indication(s)"\n'
            "}"
        )

        text = None
        for attempt in range(1, 3):
            try:
                resp = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=600,
                    system=_COVERAGE_SYSTEM,
                    messages=[{"role": "user", "content": prompt}],
                )
                _acc_tokens(resp)
                text = resp.content[0].text.strip()
                break
            except Exception as e:
                log(f"    Claude error (attempt {attempt}/2): {e}", indent=2)
                if attempt < 2:
                    time.sleep(5)

        if not text:
            log("    Skipped — Claude unavailable", indent=2)
            continue

        # Parse JSON
        try:
            import re as _re
            raw = _re.sub(r"```(?:json)?", "", text).strip()
            enriched = json.loads(raw)
        except Exception as e:
            log(f"    JSON parse error: {e} | raw: {text[:120]}", indent=2)
            enriched = {}

        if not enriched:
            continue

        # Build update — only fill fields that are currently empty
        update: dict = {}
        NULLABLE = ["target", "mechanism", "differentiation_thesis", "ailux_angle", "drug_summary"]
        for field in NULLABLE:
            if enriched.get(field) and not drug.get(field):
                update[field] = enriched[field]

        if enriched.get("stage") and not drug.get("stage"):
            update["stage"] = enriched["stage"]
        if enriched.get("indication_short") and not drug.get("indication_short"):
            update["indication_short"] = enriched["indication_short"]

        update["last_synced_date"] = TODAY

        filled = [k for k in update if k != "last_synced_date"]
        log(f"    Fields to write: {filled}", indent=2)

        if dry_run:
            log("    [dry-run] skipping write", indent=2)
            updated += 1
            continue

        ok = sb_patch("drugs", {"id": f"eq.{did}"}, update)
        if ok:
            log(f"    Updated {dname}: {filled}", indent=2)
            # Mark the research_queue item resolved if one exists
            sb_patch(
                "research_queue",
                {"entity_id": f"eq.{did}", "context_type": "eq.never_enriched"},
                {
                    "assigned_status": "resolved",
                    "next_best_action": f"DONE: Coverage pass filled {filled}",
                    "last_action_at": NOW_ISO,
                },
            )
            updated += 1
        else:
            log(f"    PATCH failed for {dname}", indent=2)

        time.sleep(1)   # brief pause to stay within rate limits

    log(f"\n  Coverage pass complete: {updated}/{len(never)} drugs updated")
    return updated


# ══════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE ORCHESTRATION — all 7 steps for one area
# ══════════════════════════════════════════════════════════════════════════

def run_intelligence_pipeline(area_id: str,
                               company_filter: Optional[str] = None,
                               discover_only: bool = False,
                               skip_discovery: bool = False,
                               skip_web_search: bool = False,
                               skip_trial_refresh: bool = False,
                               fast_model: bool = False,
                               dry_run: bool = False):
    """
    Runs the full intelligence pipeline for one disease area.

    Note: Step 3 (Trial Sync) is handled by ct_gov_sync.py
    and must run BEFORE this script in the GitHub Actions workflow.
    """
    log(f"\n{'#'*60}")
    log(f"# Ailux Intelligence Pipeline — v2")
    log(f"# Area: {area_id}  |  Date: {TODAY}")
    log(f"# Model: claude-sonnet-4-6  |  Dry run: {dry_run}")
    log(f"{'#'*60}")

    company_map = get_company_map()
    log(f"Loaded {len(company_map)} company name→ID mappings")

    # ── Cleanup: mark any dangling 'running' runs older than 2h as 'failed' ─────
    # This prevents stuck runs from accumulating when the process is killed.
    # Uses 'failed' status (valid enum value; 'interrupted' not in DB enum).
    if not dry_run:
        try:
            cutoff = (datetime.datetime.utcnow() - datetime.timedelta(hours=2)).isoformat()
            sb_patch("enrichment_runs",
                     {"status": "failed", "completed_at": NOW_ISO,
                      "error_log": "Process killed or timed out before completion"},
                     {"status": "eq.running", "started_at": f"lt.{cutoff}",
                      "script_name": "eq.company_enrichment.py"})
            log("Checked for dangling enrichment_runs (failed if >2h old)")
        except Exception as _cleanup_exc:
            log(f"  Cleanup check failed (non-fatal): {_cleanup_exc}")

    # ── Model Comparison Engine: log this pipeline run ────────────────────────
    _synthesis_model = "claude-haiku-4-5-20251001" if fast_model else "claude-sonnet-4-6"
    _pipeline_run_id: Optional[str] = None
    if not dry_run and _MODEL_COMPARISON_AVAILABLE:
        _pipeline_run_id = log_enrichment_run(
            script_name="company_enrichment.py",
            model_name=_synthesis_model,
            prompt_version="v1.0",
            entity_type="company",
            notes=f"area={area_id} company_filter={company_filter or 'all'}",
            # v59 trajectory capture: store system prompt snapshot + skill name
            prompt_snapshot=enrichment_system_prompt()[:5000],
            entity_id=company_filter or "",
            skill_name="company_enrich",
            # v60 run classification
            model_version=_synthesis_model,
            run_type="scheduled",
        )
    _pipeline_start_time = time.time()
    _pipeline_fields_set = 0
    _pipeline_errors = 0

    # Instantiate identity resolver once per pipeline run.
    # A single instance loads the alias cache once (one Supabase round-trip),
    # then every enrich_company → step6 call reuses it.
    run_resolver = None
    if _IDENTITY_RESOLVER_AVAILABLE and not dry_run:
        try:
            run_resolver = DrugIdentityResolver(SUPABASE_URL, SUPABASE_KEY)
            run_resolver._load_alias_cache()  # pre-load once; per-company calls reuse this
            log(f"Identity resolver ready ({len(run_resolver._alias_cache)} cached aliases)")
        except Exception as exc:
            log(f"⚠ Could not initialise identity resolver: {exc} — running without it")

    # STEP 1: Entity Discovery (resolver passed for cross-company collision check)
    # Skip when --skip-discovery is set (e.g. targeted --company re-enrichment runs)
    if skip_discovery:
        log("Step 1 skipped (--skip-discovery flag set)")
    else:
        new_entities = step1_discover_new_entities(area_id, company_map, dry_run=dry_run,
                                                   resolver=run_resolver)
        log(f"Step 1 complete: {new_entities} candidates queued to discovery_queue (pending review)")

    if discover_only:
        log("--discover-only: stopping after Step 1")
        return

    # STEPS 4-6: Per-company enrichment
    company_areas = sb_get("company_areas", {"area_id": f"eq.{area_id}", "select": "company_id"})
    company_ids   = [r["company_id"] for r in company_areas]

    if company_filter:
        company_ids = [c for c in company_ids if company_filter.lower() in c.lower()]
        log(f"Filtered to {len(company_ids)} matching '{company_filter}'")

    if not company_ids:
        log(f"No companies for area '{area_id}'")
        return

    # ── Check enrichment_queue for signal-triggered priority items (Tier 1 P2) ──
    # Signal monitor writes high-relevance signals here. We process queued companies
    # first so they benefit from latest signal data, then continue with the full sweep.
    queued_items = sb_get("enrichment_queue", {
        "area_id": f"eq.{area_id}",
        "status":  "eq.pending",
        "select":  "id,company_id,priority,trigger",
        "order":   "priority.desc",
        "limit":   "50",
    })
    if queued_items:
        queued_cos = [q["company_id"] for q in queued_items]
        log(f"\n⚡ enrichment_queue: {len(queued_items)} pending item(s) for {area_id}")
        for q in queued_items:
            log(f"  {q['company_id']} (priority={q['priority']}, trigger={q['trigger']})", indent=1)
        # Mark queued items as dispatched
        if not dry_run:
            for q in queued_items:
                sb_patch("enrichment_queue",
                         {"status": "dispatched", "dispatched_at": NOW_ISO},
                         {"id": f"eq.{q['id']}"})
        # Reorder: queued companies run first, then the rest (deduped)
        queued_set = set(queued_cos)
        company_ids = queued_cos + [c for c in company_ids if c not in queued_set]
    else:
        log("\n── enrichment_queue: no pending items for this area ──")

    log(f"\n{len(company_ids)} companies to enrich: {company_ids}")
    log("Note: Trials pre-populated by ct_gov_sync.py (Step 3)")

    results = {"success": 0, "failed": 0}
    _companies_processed = 0
    for cid in company_ids:
        try:
            ok = enrich_company(cid, area_id, company_map, dry_run=dry_run,
                                resolver=run_resolver,
                                skip_web_search=skip_web_search,
                                skip_trial_refresh=skip_trial_refresh,
                                fast_model=fast_model,
                                enrichment_run_id=_pipeline_run_id)
            results["success" if ok else "failed"] += 1
            _companies_processed += 1
            if ok:
                _pipeline_fields_set += 1
            else:
                _pipeline_errors += 1
        except Exception as e:
            log(f"FATAL: {cid}: {e}")
            results["failed"] += 1
            _pipeline_errors += 1
        time.sleep(2)

    log(f"\n{'='*60}")
    log(f"Complete: {results['success']} success, {results['failed']} failed")
    log(f"{'='*60}")

    # ── Model Comparison Engine: update run totals + build summary ────────────
    if _pipeline_run_id and not dry_run:
        # Build comprehensive summary from enriched_field_log before closing run
        enrichment_summary = build_enrichment_summary(_pipeline_run_id)
        update_enrichment_run(
            run_id=_pipeline_run_id,
            fields_set=_pipeline_fields_set,
            run_duration_seconds=time.time() - _pipeline_start_time,
            error_count=_pipeline_errors,
            companies_processed=_companies_processed,
            areas_processed=[area_id],
            summary_json=enrichment_summary,
            prompt_tokens=_RUN_TOKENS["in"],
            completion_tokens=_RUN_TOKENS["out"],
        )
        log(f"  Run tokens: {_RUN_TOKENS['in']:,} in / {_RUN_TOKENS['out']:,} out "
            f"(~${_RUN_TOKENS['in']/1e6*3 + _RUN_TOKENS['out']/1e6*15:.2f})")

    # Mark dispatched enrichment_queue items as complete
    if not dry_run and queued_items:
        for q in queued_items:
            sb_patch("enrichment_queue",
                     {"status": "complete", "completed_at": NOW_ISO},
                     {"id": f"eq.{q['id']}"})
        log(f"enrichment_queue: marked {len(queued_items)} item(s) complete")

    # Reconciliation — runs only on full-area runs (not targeted --company filters).
    # Removes stale company_areas links and flags any remaining ghost entities.
    if not company_filter:
        reconcile_company_areas(area_id, dry_run=dry_run)
    else:
        log(f"\n── Reconciliation skipped (targeted run: {company_filter}) ──")

    # Coverage pass — fill any drugs that have never been enriched.
    # Runs only on full-area runs (not targeted --company filters) to avoid
    # double-processing during fast targeted re-enrichment sessions.
    # Limit=10 per area run keeps total cost bounded; never-enriched drugs
    # are also added to research_queue so they surface in the Discovery Queue.
    if not company_filter:
        enrich_never_touched_drugs(limit=10, dry_run=dry_run)
    else:
        log("\n── Coverage pass skipped (targeted run) ──")

    # ── S3: stamp system_status so the dashboard surfaces fresh-data banner ────
    if not dry_run:
        _touched = results.get('success', 0)
        update_system_status(
            "enrichment",
            record_count=_touched,
            note=f"Enrichment run for area '{area_id}' — {_touched} records updated",
        )


# ══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ailux BD Platform — Systematic Intelligence Pipeline"
    )
    parser.add_argument("--area",     required=True,
                        help="Disease area ID (e.g. tl1a, tslp, il4ra)")
    parser.add_argument("--company",  default=None,
                        help="Company ID substring filter")
    parser.add_argument("--discover-only", action="store_true",
                        help="Only run Step 1 (entity discovery)")
    parser.add_argument("--skip-discovery", action="store_true",
                        help="Skip Step 1 (entity discovery); go straight to per-company enrichment. "
                             "Use with --company for fast targeted re-enrichment runs.")
    parser.add_argument("--skip-web-search", action="store_true",
                        help="Skip Phase A web intelligence search in Step 5. Claude synthesises "
                             "from Supabase context + training data only. Fastest option for "
                             "source_url / confidence_level re-population runs.")
    parser.add_argument("--skip-trial-refresh", action="store_true",
                        help="Skip CT.gov re-fetch for existing trial rows during context fetch. "
                             "Saves ~1s per trial. Use with --skip-web-search for fastest targeted "
                             "company_profiles re-enrichment within the 45s bash window.")
    parser.add_argument("--fast", action="store_true",
                        help="Use claude-haiku-4-5-20251001 (max_tokens=4096) for synthesis instead "
                             "of claude-sonnet-4-6. ~3-5x faster. Combine with --skip-trial-refresh "
                             "and --skip-web-search for targeted company_profiles updates that fit "
                             "within the 45s bash window. Quality is lower — use for unenriched "
                             "companies where any data is better than none.")
    parser.add_argument("--dry-run",  action="store_true",
                        help="No Supabase writes")
    args = parser.parse_args()

    run_intelligence_pipeline(
        area_id=args.area,
        company_filter=args.company,
        discover_only=args.discover_only,
        skip_discovery=args.skip_discovery,
        skip_web_search=args.skip_web_search,
        skip_trial_refresh=args.skip_trial_refresh,
        fast_model=args.fast,
        dry_run=args.dry_run,
    )
