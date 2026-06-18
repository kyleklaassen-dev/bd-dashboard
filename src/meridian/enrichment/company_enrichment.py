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


# ══════════════════════════════════════════════════════════════════════════
# STEP 5 — COMPANY ENRICHMENT (Claude Sonnet + web_search)
#
# Phase A: Web intelligence gathering — live search for clinical data, financing,
#           deals, catalyst timing (web_search_20250305 tool).
# Phase B: Claude synthesis — structured enrichment using Supabase context +
#           web intelligence → company_profiles, drugs, catalysts, deals.
# ══════════════════════════════════════════════════════════════════════════


WEB_SEARCH_SYSTEM = """You are a biopharma competitive intelligence researcher.
Use web_search to gather current, specific facts about the target company.
Extract actual numbers, dates, partner names, dollar amounts — not general descriptions.
Prioritize press releases, SEC filings, ClinicalTrials.gov, conference abstracts, and IR pages.
Summarize findings in dense factual paragraphs. Do not fabricate — if you can't find something, say so."""


def gather_web_intelligence(company_name: str, area_id: str,
                             drugs: list, ticker: str = "") -> str:
    """
    Phase A of Step 5: use Claude with web_search to gather live intelligence.

    Runs 4 targeted searches:
      1. Clinical data — trial results, efficacy endpoints, conference readouts
      2. Financing — funding rounds, investors, cash runway, IPO/SPAC details
      3. BD activity — partnerships, licensing deals, M&A, collaborations
      4. Catalyst timeline — company-guided data windows, PDUFA dates, filings

    Returns a structured text block to inject into the Phase B enrichment prompt.
    Falls back to empty string on any failure (Phase B continues with Supabase context only).
    """
    area_label = AREA_LABELS_MAP.get(area_id, area_id)
    drug_names = ", ".join(d.get("name", "") for d in drugs[:4] if d.get("name"))
    ticker_str = f" (Ticker: {ticker})" if ticker and ticker.upper() not in ("PRIVATE", "N/A", "") else ""
    year = datetime.datetime.utcnow().year

    prompt = f"""Research {company_name}{ticker_str} for a competitive intelligence database.
Area of focus: {area_label}
Key programs to research: {drug_names or 'see company pipeline'}

Use web_search to find and extract SPECIFIC facts on all four topics:

TOPIC 1 — CLINICAL DATA (current AND historical)
Search for trial results across ALL phases — not just the most recent.
What endpoints did they hit? What were the response rates, p-values, or biomarker results?
Which conferences (ECCO, DDW, ACR, ASCO, NEJM, Lancet, NEJM Evidence)?
Any Phase 3 readouts, POC data, dose-selection results in the last 24 months?
CRITICAL: Also search for earlier Phase 1 and Phase 2 proof-of-concept or dose-finding trials that preceded the current Phase 3 program. These are often the scientific foundation for Phase 3 and may have published results (even if the trial completed 2-4 years ago). Search specifically for: "[drug name] Phase 1 results", "[drug name] Phase 2 results", "[drug name] proof of concept", "[drug name] dose escalation". A completed Phase 2b that missed its primary endpoint is MORE important to capture than a currently-recruiting Phase 3, because it carries the key risk data.

TOPIC 2 — FINANCING & COMPANY STATUS
All funding rounds with amounts, dates, and lead investors.
IPO, SPAC, or public listing details if applicable.
Current cash position or runway guidance if disclosed.
Key shareholders or strategic investors.

TOPIC 3 — BD ACTIVITY
Any licensing deals, partnerships, co-development agreements, M&A.
Deal terms where disclosed: upfront, milestones, royalties, geography.
Any stated partnering strategy or BD timeline guidance from management.

TOPIC 4 — CATALYST TIMELINE
Company-guided data readout windows for each program.
Any upcoming PDUFA dates, regulatory filings, or NDA/BLA submissions.
Expected enrollment completion or primary completion dates from company guidance (not just CT.gov).

Search year range: {year - 1}–{year}.
Be specific. Extract actual numbers and dates. Indicate uncertainty where present."""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            system=WEB_SEARCH_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            timeout=90.0,  # web search can be slow — cap at 90s to avoid infinite hang
        )
        # Extract all text content blocks (tool_use and tool_result blocks are intermediate)
        parts = []
        for block in resp.content:
            if hasattr(block, "text") and block.text:
                parts.append(block.text.strip())
        result = "\n\n".join(parts)
        _acc_tokens(resp)
        tokens_in  = resp.usage.input_tokens
        tokens_out = resp.usage.output_tokens
        cost = (tokens_in / 1e6 * 3.0) + (tokens_out / 1e6 * 15.0)
        log(f"  Web search: {tokens_in}in / {tokens_out}out (${cost:.4f})", indent=2)
        return result if result else ""
    except Exception as e:
        log(f"  Web search failed (non-fatal): {e}", indent=2)
        return ""




def parse_enrichment_response(text: str) -> Optional[dict]:
    text = text.strip()
    if "```" in text:
        for p in text.split("```"):
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                text = p
                break
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        log(f"  JSON parse error: {e} | Raw: {text[:400]}", indent=1)
        return None


def write_step5(company_id: str, area_id: str, data: dict, ctx: dict, dry_run: bool = False,
                enrichment_run_id: Optional[str] = None):
    """Write Claude enrichment results to Supabase."""
    if dry_run:
        log(f"  [DRY RUN] {json.dumps(data, indent=2)[:400]}...", indent=1)
        return

    cp = data.get("company_profile", {})
    if cp:
        # Validate structured intelligence fields are present
        pi = cp.get("platform_intelligence") or {}
        bi = cp.get("bd_intelligence") or {}

        if not pi:
            log("  ⚠ WARNING: platform_intelligence is null — model did not follow structured schema. "
                "Check model output. Falling back to legacy text if present.", indent=1)
        else:
            # Evidence label compliance — direction bullets must start with [INFERRED],
            # assessment must start with [ASSESSED]. Log warnings, don't block writes.
            direction = pi.get("direction") or []
            for i, bullet in enumerate(direction):
                if isinstance(bullet, str) and not bullet.strip().startswith("[INFERRED]"):
                    log(f"  ⚠ DATA QUALITY: platform_intelligence.direction[{i}] missing [INFERRED] label: "
                        f"'{bullet[:80]}'", indent=1)
            assessment = pi.get("assessment") or ""
            if assessment and isinstance(assessment, str) and not assessment.strip().startswith("[ASSESSED]"):
                log(f"  ⚠ DATA QUALITY: platform_intelligence.assessment missing [ASSESSED] label: "
                    f"'{assessment[:80]}'", indent=1)
            facts = pi.get("facts") or []
            if not facts:
                log("  ⚠ DATA QUALITY: platform_intelligence.facts is empty — no factual bullets written", indent=1)

        if not bi:
            log("  ⚠ WARNING: bd_intelligence is null — model did not follow structured schema. "
                "Check model output.", indent=1)
        else:
            bd_assessments = bi.get("assessment") or []
            for i, bullet in enumerate(bd_assessments):
                if isinstance(bullet, str) and not bullet.strip().startswith("[ASSESSED]"):
                    log(f"  ⚠ DATA QUALITY: bd_intelligence.assessment[{i}] missing [ASSESSED] label: "
                        f"'{bullet[:80]}'", indent=1)

        profile_rec = {
            "company_id":          company_id,
            "area_id":             area_id,
            "last_enriched_at":    NOW_ISO,
            "enriched_by":         "claude-intelligence-v2",
            "last_enriched_model": "claude-sonnet-4-6",
        }
        # Stamp enrichment run provenance on company_profiles (v57 model comparison engine)
        if enrichment_run_id:
            profile_rec["last_enrichment_run_id"] = enrichment_run_id
        for field in ["platform_intelligence","bd_intelligence",
                      "platform_summary","bd_summary","key_risk","why_it_matters",
                      "vs_ailux","strategic_behavior","pipeline_url",
                      "market_cap_usd_m","cash_runway","financing_history","key_investors"]:
            if cp.get(field) is not None:
                profile_rec[field] = cp[field]
        # ── Guard E3: company_areas must exist before company_profiles ──────────
        # Invariant: if company_profiles exists for company×area, company_areas must too.
        # Upsert is idempotent — harmless if row already exists.
        sb_upsert("company_areas", {"company_id": company_id, "area_id": area_id},
                  on_conflict="company_id,area_id")
        log(f"  [E3 guard] company_areas ensured: {company_id} → {area_id}", indent=1)

        # Patch-or-insert: avoid duplicate rows (no UNIQUE constraint in DB yet)
        existing = sb_get("company_profiles", {
            "company_id": f"eq.{company_id}",
            "area_id":    f"eq.{area_id}",
            "select":     "company_id",
            "limit":      "1",
        })
        if existing:
            ok = sb_patch("company_profiles", profile_rec,
                          {"company_id": f"eq.{company_id}", "area_id": f"eq.{area_id}"})
            log(f"  company_profiles: {'✓ patched' if ok else '✗ patch failed'}", indent=1)
        else:
            result = sb_upsert("company_profiles", profile_rec)
            log(f"  company_profiles: {'✓ inserted' if result else '✗ insert failed'}", indent=1)

    # Pre-validate drug IDs: fetch actual IDs in DB so we catch Claude hallucinating non-existent ones
    db_drug_ids = {d["id"] for d in sb_get("drugs", {"company_id": f"eq.{company_id}", "select": "id"})}

    # canonical_drug_id lookup for drug_area_scores parallel write (P1-D)
    _canon_map: dict = {d["id"]: d.get("canonical_drug_id") for d in ctx.get("drugs", []) if d.get("id")}

    # catalog_category lookup — used below to auto-stamp drugs that are missing it
    _drug_catalog_map: dict = {d["id"]: d.get("catalog_category") for d in ctx.get("drugs", []) if d.get("id")}

    # v60: pre-enrichment drug snapshot for old_value capture in enriched_field_log
    # ctx["drugs"] was loaded before Claude ran — it holds the pre-enrichment state
    _pre_enrich_drug_map: dict = {d["id"]: d for d in ctx.get("drugs", []) if d.get("id")}

    # Area-specific fields that belong in drug_area_scores (in addition to drugs table)
    # source_url + confidence_level are included so every area score carries provenance
    _AREA_SCORE_FIELDS = {"overlap", "overlap_rationale", "cls", "vs_ailux", "area_fit",
                          "source_url", "confidence_level"}

    for du in data.get("drug_updates", []):
        drug_id = du.pop("drug_id", None)
        if not drug_id:
            log("  drug_updates entry missing drug_id — skipping", indent=1)
            continue
        if drug_id not in db_drug_ids:
            log(f"  WARNING: Claude returned unknown drug_id '{drug_id}' (not in DB for {company_id}) — skipping", indent=1)
            log(f"    Valid IDs are: {sorted(db_drug_ids)}", indent=2)
            continue
        update_fields = {k: v for k, v in du.items() if v is not None}
        # strategic_role must always be written, even if it's the first enrichment
        if "strategic_role" in du and du["strategic_role"] is None:
            update_fields.pop("strategic_role", None)  # skip null roles
        # ── catalog_category invariant: stamp if currently null ───────────────
        # Any drug with a drug_areas row must have catalog_category set so it
        # appears in the Drugs to Know tab. Infer it here if the DB record is null.
        existing_cc = _drug_catalog_map.get(drug_id)
        if not existing_cc and "catalog_category" not in update_fields:
            ctx_drug = next((d for d in ctx.get("drugs", []) if d.get("id") == drug_id), {})
            inferred_cc = infer_catalog_category(
                target   = ctx_drug.get("target", ""),
                modality = ctx_drug.get("modality", ""),
                stage    = ctx_drug.get("stage", ""),
                area_id  = area_id,
            )
            update_fields["catalog_category"] = inferred_cc
            log(f"  catalog_category auto-stamped → '{inferred_cc}' for {drug_id}", indent=2)
        if update_fields:
            # Stamp model version on every drug write (v16 provenance column)
            update_fields["last_enriched_model"] = "claude-sonnet-4-6"
            # Stamp enrichment run provenance (v57 model comparison engine)
            if enrichment_run_id:
                update_fields["last_enrichment_run_id"] = enrichment_run_id
                update_fields["enriched_by"]  = "claude-sonnet-4-6"
                update_fields["enriched_at"]  = NOW_ISO
            ok = sb_patch("drugs", update_fields, {"id": f"eq.{drug_id}"})
            role = update_fields.get("strategic_role", "")
            summary_preview = (update_fields.get("drug_summary") or "")[:60]
            log(f"  drug {drug_id} [{role}]: {'✓' if ok else '✗'} | summary: {summary_preview!r}", indent=1)

            # ── v60: enriched_field_log writes with old_value capture ─────────
            # Write one row per enriched field. old_value comes from the pre-enrichment
            # ctx snapshot captured before Claude ran — this is the diff training signal.
            if ok and enrichment_run_id and not dry_run:
                _pre_drug = _pre_enrich_drug_map.get(drug_id, {})
                # Fields that carry enrichment signal (skip provenance/admin fields)
                _LOGGABLE_FIELDS = {
                    "mechanism", "ailux_angle", "drug_summary", "source_url",
                    "overlap", "overlap_rationale", "differentiation_thesis",
                    "stage", "modality", "target", "catalog_category",
                    "strategic_role", "risk_summary", "bd_angle",
                }
                # ── confidence_score: derive from LLM confidence_level + source heuristic ──
                # confidence_level in drug_updates: 'confirmed' | 'supported' | 'inferred'
                _cl = (du.get("confidence_level") or "").lower()
                _has_source = bool(du.get("source_url"))
                if _cl == "confirmed":
                    _conf_score = 0.90
                elif _cl == "supported":
                    _conf_score = 0.80
                elif _cl == "inferred":
                    _conf_score = 0.65
                elif _has_source:
                    _conf_score = 0.80
                else:
                    _conf_score = 0.75
                _field_log_rows = []
                _now_ts = datetime.datetime.utcnow().isoformat()
                for _fname, _fval in update_fields.items():
                    if _fname not in _LOGGABLE_FIELDS:
                        continue
                    if _fval is None:
                        continue
                    _fval_str = str(_fval) if not isinstance(_fval, str) else _fval
                    _old_val = _pre_drug.get(_fname)
                    _old_val_str = str(_old_val) if (_old_val is not None and not isinstance(_old_val, str)) else _old_val
                    _field_log_rows.append({
                        "enrichment_run_id": enrichment_run_id,
                        "entity_type":       "drug",
                        "entity_id":         drug_id,
                        "field_name":        _fname,
                        "enriched_value":    _fval_str,
                        "old_value":         _old_val_str,
                        "old_value_captured_at": _now_ts if _old_val_str is not None else None,
                        "was_changed":       _old_val_str != _fval_str if _old_val_str is not None else True,
                        "model_name":        "claude-sonnet-4-6",
                        "confidence_score":  _conf_score,
                        "source_citation":   du.get("source_url") or None,
                        "enriched_at":       _now_ts,
                        "field_label":       "pending",
                        "label_source":      "pending",
                    })
                if _field_log_rows:
                    try:
                        _fl_result = sb_upsert("enriched_field_log", _field_log_rows)
                        log(f"    enriched_field_log: {len(_fl_result or [])} field(s) logged for {drug_id}", indent=2)
                    except Exception as _fl_exc:
                        log(f"    enriched_field_log: write failed (non-fatal): {_fl_exc}", indent=2)

            # ── Source traceability: write drug_sources row ───────────────────
            # Every drug write must have at least one source URL.
            # The LLM is instructed to embed drug_sources rows in its response JSON.
            # As a fallback, we also auto-generate a CT.gov search source for any
            # drug that has a stage claim but no explicit source URL in the response.
            _source_rows = du.get("drug_sources") or []
            if not _source_rows:
                # Fallback: generate a CT.gov search source for stage claims
                _stage_val = update_fields.get("stage") or du.get("stage") or ""
                _drug_name_val = du.get("name") or drug_id
                if _stage_val:
                    _ct_search = f"https://clinicaltrials.gov/search?term={requests.utils.quote(_drug_name_val)}"
                    _source_rows = [{
                        "drug_id":              drug_id,
                        "drug_name":            _drug_name_val,
                        "claim_type":           "stage",
                        "claim_value":          _stage_val,
                        "source_url":           _ct_search,
                        "source_type":          "clinicaltrials",
                        "source_domain":        "clinicaltrials.gov",
                        "content_confirms_claim": False,
                        "confidence":           "low",
                        "added_by":             "enrichment",
                        "session_label":        f"{area_id}_{TODAY}",
                    }]
            else:
                # LLM-provided sources: validate and tag them
                for _sr in _source_rows:
                    _sr.setdefault("drug_id",       drug_id)
                    _sr.setdefault("drug_name",     du.get("name") or drug_id)
                    _sr.setdefault("added_by",      "enrichment")
                    _sr.setdefault("session_label", f"{area_id}_{TODAY}")
                    _sr.setdefault("confidence",    "medium")
                    # Validate URL format before storing
                    raw_url = _sr.get("source_url") or ""
                    if raw_url:
                        validated = validate_source_url(raw_url, context=f"{drug_id}_source",
                                                         head_check=False)
                        if not validated:
                            _sr["source_url"] = ""
                            _sr["url_status"] = "dead"
                        else:
                            _sr.setdefault("url_status", "unverified")
            _valid_sources = [s for s in _source_rows if s.get("source_url")]
            if _valid_sources:
                _src_result = sb_upsert("drug_sources", _valid_sources)
                log(f"    drug_sources: {len(_src_result or [])} row(s) written for {drug_id}", indent=2)
            else:
                log(f"    drug_sources: no valid source URL for {drug_id} — "
                    f"add a CT.gov NCT link or FDA URL to improve data confidence", indent=2)

            # ── P1-D: Parallel write to drug_area_scores ──────────────────────
            # Write area-specific competitive fields to the normalised table so
            # multi-area drugs accumulate per-area scores without overwriting.
            _das_payload = {
                k: update_fields[k] for k in _AREA_SCORE_FIELDS if k in update_fields
            }
            if _das_payload:
                _das_rec = {
                    "drug_id":            drug_id,
                    "canonical_drug_id":  _canon_map.get(drug_id),
                    "area_id":            area_id,
                    "last_enriched_at":   NOW_ISO,
                    "enriched_model":     "claude-sonnet-4-6",
                }
                # Map vs_ailux → vs_ailux_positioning (column name differs in drug_area_scores)
                if "vs_ailux" in _das_payload:
                    _das_rec["vs_ailux_positioning"] = _das_payload.pop("vs_ailux")
                _das_rec.update(_das_payload)
                # ── E6 guard: post-LLM confidence invariant enforcement ───────────
                enforce_confidence_constraints(_das_rec, context=f"{drug_id}×{area_id}")
                # ── Guard E4: drug_areas must exist before drug_area_scores ──────
                # Invariant: a drug_area_scores row without a matching drug_areas row
                # violates E4. Upsert drug_areas first — idempotent if already present.
                sb_upsert("drug_areas", {"drug_id": drug_id, "area_id": area_id},
                          on_conflict="drug_id,area_id")

                _das_existing = sb_get("drug_area_scores", {
                    "drug_id": f"eq.{drug_id}",
                    "area_id": f"eq.{area_id}",
                    "select":  "drug_id",
                    "limit":   "1",
                })
                if _das_existing:
                    sb_patch("drug_area_scores", _das_rec,
                             {"drug_id": f"eq.{drug_id}", "area_id": f"eq.{area_id}"})
                else:
                    sb_upsert("drug_area_scores", _das_rec)
                log(f"    drug_area_scores [{area_id}]: overlap={_das_rec.get('overlap','—')} cls={_das_rec.get('cls','—')}", indent=2)

            # ── partner_company guard — must be set for all non-self deals ──────
            pt_written = update_fields.get("partnership_type") or du.get("partnership_type")
            pc_written = update_fields.get("partner_company") or du.get("partner_company")
            if pt_written and pt_written != 'self' and not pc_written:
                log(f"  ⚠ DATA QUALITY: drug '{drug_id}' has partnership_type='{pt_written}' "
                    f"but partner_company is null — pill will not render. "
                    f"Set partner_company to the short originator name (e.g. 'Simcere', 'FutureGen Biopharmaceutical').", indent=1)

            # ── Acquired-drug display_name guard ─────────────────────────────
            # If drug has a licensor but display_name wasn't set (or equals drug_id),
            # this is a data quality failure — log a hard warning so it's visible in CI logs.
            licensor_code_written = update_fields.get("licensor_code") or du.get("licensor_code")
            display_name_written  = update_fields.get("display_name") or ""
            if licensor_code_written and (not display_name_written or display_name_written == drug_id):
                log(f"  ⚠ DATA QUALITY: drug '{drug_id}' has licensor_code='{licensor_code_written}' "
                    f"but display_name='{display_name_written or 'null'}' — acquirer code not set. "
                    f"Set display_name to the acquirer's name ONLY (e.g. 'ABBV-701', not 'ABBV-701 ({licensor_code_written})').", indent=1)
            # Also warn if display_name looks like "AcquirerCode (OldCode)" — old format
            elif licensor_code_written and licensor_code_written in (display_name_written or ''):
                log(f"  ⚠ DATA QUALITY: drug '{drug_id}' display_name='{display_name_written}' "
                    f"still contains the old licensor code '{licensor_code_written}'. "
                    f"Update to acquirer name only (strip the '({licensor_code_written})' suffix).", indent=1)

    # Write combination programs
    for combo in data.get("combination_programs", []):
        label = (combo.get("label") or "").strip()
        if not label:
            continue
        component_ids = combo.get("component_drug_ids") or []
        stage_val = combo.get("stage") or "Concept"
        is_planned = stage_val.startswith("Planned")
        combo_rec = {
            "company_id":            company_id,
            "area_id":               area_id,
            "label":                 label[:300],
            "component_drug_ids":    component_ids,
            "combination_type":      combo.get("combination_type") or "rational_combo",
            "stage":                 stage_val,
            "phase_display":         combo.get("phase_display"),
            "anticipated_start":     combo.get("anticipated_start"),
            "prerequisite_note":     combo.get("prerequisite_note"),
            "indication_short":      combo.get("indication_short"),
            "strategic_significance": combo.get("strategic_significance") or "medium",
            "mechanism_detail":      combo.get("mechanism_detail"),
            "drug_summary":          combo.get("drug_summary"),
            "overlap":               combo.get("overlap"),
            "overlap_rationale":     combo.get("overlap_rationale"),
            "notes":                 combo.get("notes"),
            "updated_at":            NOW_ISO,
        }
        if combo.get("source_url"):
            combo_rec["source_url"] = combo["source_url"]
        elif is_planned:
            log(f"  ⚠ combo '{label[:45]}': stage is Planned but source_url missing — data quality risk", indent=1)
        # Upsert by company + label (idempotent)
        existing = sb_get("drug_combinations", {
            "company_id": f"eq.{company_id}",
            "label":      f"eq.{label}",
            "select":     "id",
            "limit":      "1",
        })
        if existing:
            combo_id = existing[0].get("id")
            ok = sb_patch("drug_combinations", combo_rec, {"id": f"eq.{combo_id}"})
            log(f"  combo '{label[:45]}': {'✓ patched' if ok else '✗ patch failed'}", indent=1)
        else:
            result = sb_upsert("drug_combinations", combo_rec)
            log(f"  combo '{label[:45]}': {'✓ inserted' if result else '✗ insert failed'}", indent=1)

    # ── Insert net-new trials discovered by Claude ────────────────────────────
    # These are trials Claude found (via web intelligence or knowledge) that are
    # not yet in the trials table. We upsert on id (NCT number) so re-runs are safe.
    new_trials = data.get("new_trials", [])
    if new_trials:
        log(f"  new_trials to seed: {len(new_trials)}", indent=1)
    for nt in new_trials:
        nct_id = (nt.get("id") or "").strip()
        drug_id = (nt.get("drug_id") or "").strip()
        if not nct_id or not nct_id.startswith("NCT") or not drug_id:
            log(f"  ✗ skipping new_trial — missing/invalid id or drug_id: {nt}", indent=2)
            continue
        if drug_id not in db_drug_ids:
            log(f"  ✗ skipping new_trial {nct_id} — drug_id '{drug_id}' not in DB", indent=2)
            continue
        trial_rec = {
            "id":                     nct_id,
            "drug_id":                drug_id,
            "trial_name":             nt.get("trial_name") or None,
            "phase":                  nt.get("phase") or None,
            "status":                 nt.get("status") or None,
            "indication":             nt.get("indication") or None,
            "primary_completion_date": nt.get("primary_completion_date") or None,
            "study_acronym":          nt.get("study_acronym") or None,
            "source_url":             nt.get("source_url") or None,
            "estimand":               nt.get("estimand") or None,
            "results_note":           nt.get("results_note") or None,
            "area_fit":               nt.get("area_fit") or None,
        }
        # Strip None values — only send fields with actual data
        trial_rec = {k: v for k, v in trial_rec.items() if v is not None}
        ok = sb_upsert("trials", trial_rec)
        log(f"  new trial {nct_id} ({drug_id}): {'✓ inserted' if ok else '✗ failed'}", indent=2)

    for tu in data.get("trial_updates", []):
        trial_id = tu.get("trial_id")
        if not trial_id:
            continue
        update_fields = {k: v for k, v in tu.items()
                        if k != "trial_id" and v is not None}
        if update_fields:
            ok = sb_patch("trials", update_fields, {"id": f"eq.{trial_id}"})
            log(f"  trial {trial_id}: {'✓' if ok else '✗'}", indent=1)

    for cat in data.get("catalysts", []):
        sort_date = _parse_sort_date(
            cat.get("sort_date_approx") or cat.get("catalyst_date") or TODAY
        ) or TODAY
        if sort_date < TODAY:
            continue
        drug_id_raw = (cat.get("drug_id") or "").strip() or None
        cat_type    = cat.get("catalyst_type", "readout")

        # Dedup check: skip if this (company, area, label) already exists.
        # Label is the most stable identifier across LLM runs — two events with the
        # same label are almost certainly the same catalyst, even if sort_date drifts
        # slightly between enrichment passes.  This is the fix for the duplicate
        # accumulation bug identified 2026-05-22 (137 dupes removed across all areas).
        # The ideal guard is a DB unique index on (company_id, area_id, label) — add
        # that via Supabase SQL editor: see docs/catalyst_quality_diagnosis.md Step 3.
        label_truncated = (cat.get("label") or "")[:200]
        dedup_by_label: dict = {
            "company_id": f"eq.{company_id}",
            "area_id":    f"eq.{area_id}",
            "label":      f"eq.{label_truncated}",
            "select":     "id",
        }
        if sb_get("catalysts", dedup_by_label):
            log(f"  catalyst '{label_truncated[:40]}': already exists (label match), skipping", indent=1)
            continue

        # Secondary dedup: also check (company, drug, type, sort_date) to catch
        # same-event catalysts with slightly different label wording.
        dedup_by_date: dict = {
            "company_id":    f"eq.{company_id}",
            "area_id":       f"eq.{area_id}",
            "catalyst_type": f"eq.{cat_type}",
            "sort_date":     f"eq.{sort_date}",
            "select":        "id",
        }
        if drug_id_raw:
            dedup_by_date["drug_id"] = f"eq.{drug_id_raw}"
        else:
            dedup_by_date["drug_id"] = "is.null"
        if sb_get("catalysts", dedup_by_date):
            log(f"  catalyst '{label_truncated[:40]}': already exists (date+type match), skipping", indent=1)
            continue

        cat_rec = {
            "catalyst_date":    cat.get("catalyst_date", ""),
            "sort_date":        sort_date,
            "label":            (cat.get("label") or "")[:200],
            "company_id":       company_id,
            "area_id":          area_id,
            "drug_id":          drug_id_raw,
            "significance":     cat.get("significance", "medium"),
            "catalyst_type":    cat_type,
            "notes":            cat.get("notes", ""),
            "is_key_watch":     bool(cat.get("is_key_watch", False)),
            "confidence_level": cat.get("confidence_level", "inferred"),
            "resolved":         False,
            "confidence_source": "company-disclosed",
        }
        # RULE: Always persist source_url when provided — required for validated references
        if cat.get("source_url"):
            cat_rec["source_url"] = cat["source_url"]
        result = _catalyst_upsert(cat_rec)
        log(f"  catalyst '{cat_rec['label'][:40]}': {'✓' if result else '✗'}", indent=1)

        # BUG 7 FIX: Dual-write to catalyst_calendar so new table populates going forward.
        # NOTE: The legacy catalysts table (862 rows) is the live data source. catalyst_calendar
        # (14 rows) is the new schema. We do NOT migrate old rows — too risky. Instead, every
        # new catalyst written here is mirrored to catalyst_calendar. Once catalyst_calendar
        # has sufficient coverage, the dashboard can switch its primary read to it.
        try:
            cc_rec = {
                "drug_id":              drug_id_raw,
                "company_id":           company_id,
                "event_type":           cat_type,
                "event_name":           (cat.get("label") or "")[:200],
                "expected_date":        sort_date,
                "expected_quarter":     cat.get("catalyst_date", ""),
                "description":          cat.get("notes", ""),
                "strategic_significance": cat.get("significance", "medium"),
                "ailux_impact":         cat.get("ailux_angle", ""),
                "confidence":           cat.get("confidence_level", "inferred"),
                "is_past":              False,
            }
            if cat.get("source_url"):
                cc_rec["source_url"] = cat["source_url"]
            if enrichment_run_id:
                cc_rec["enrichment_run_id"] = enrichment_run_id
            sb_upsert("catalyst_calendar", cc_rec)
        except Exception as _cc_exc:
            log(f"  catalyst_calendar mirror: non-fatal error: {_cc_exc}", indent=1)

    for du in data.get("deal_updates", []):
        headline = du.get("headline", "")
        if not headline:
            continue
        # RULE: source_url is a validated reference field — always persist if provided
        update_fields = {k: v for k, v in du.items()
                        if k != "headline" and v is not None}
        if update_fields:
            ok = sb_patch("deals", update_fields,
                          {"headline": f"ilike.*{headline[:30]}*",
                           "company_id": f"eq.{company_id}"})
            log(f"  deal '{headline[:40]}': {'✓' if ok else '✗'}", indent=1)

    # Write news items to intel + intel_companies junction
    # Deduplicate by source_url — skip if already in DB
    news_written = 0
    for item in data.get("news_items", []):
        source_url = (item.get("source_url") or "").strip()
        headline   = (item.get("headline") or "").strip()
        if not source_url or not headline:
            continue  # require both — no unverified articles

        # Deduplicate: skip if source_url already exists in intel
        existing = sb_get("intel", {
            "source_url": f"eq.{source_url}",
            "select": "id",
            "limit": "1",
        })
        if existing:
            log(f"  news '{headline[:45]}': already in DB — skip", indent=1)
            continue

        # Normalize intel_type: 'financing' and 'pipeline' not yet in DB check constraint.
        # Map to nearest valid value until constraint is updated via Supabase dashboard.
        # TODO: ALTER TABLE intel DROP CONSTRAINT intel_intel_type_check;
        #       ALTER TABLE intel ADD CONSTRAINT intel_intel_type_check
        #         CHECK (intel_type IN ('data','deal','regulatory','financing',
        #                               'conference','partnership','management','pipeline'));
        _INTEL_TYPE_NORM = {"financing": "deal", "pipeline": "data"}
        _raw_type = item.get("intel_type") or "data"
        _norm_type = _INTEL_TYPE_NORM.get(_raw_type, _raw_type)

        intel_rec = {
            "intel_date":  (item.get("intel_date") or TODAY),
            "headline":    headline[:255],
            "body":        (item.get("body") or "")[:2000],
            "source_url":  source_url,
            "source_name": (item.get("source_name") or "")[:100],
            "importance":  item.get("importance") or "medium",
            "intel_type":  _norm_type,
            "verified":    True,
        }
        intel_rec["primary_company_id"] = company_id  # P1-B: spine FK for direct lookups
        result = sb_upsert("intel", intel_rec)
        if result and isinstance(result, list) and result:
            intel_id = result[0].get("id")
            if intel_id:
                # Tag to company via junction table
                sb_upsert("intel_companies", {"intel_id": intel_id, "company_id": company_id})
                news_written += 1
                log(f"  news '{headline[:45]}': ✓ saved (id={intel_id})", indent=1)
            else:
                log(f"  news '{headline[:45]}': ✗ insert returned no id", indent=1)
        else:
            log(f"  news '{headline[:45]}': ✗ insert failed", indent=1)

    if news_written:
        log(f"  → {news_written} new intel item(s) saved for {company_id}", indent=1)

    # ── Competitive Signals ──────────────────────────────────────────────
    # Past discrete events (conference presentations, financing rounds, patent filings,
    # regulatory milestones). Dedup by (company_id, drug_id, title) — same title = same event.
    _VALID_SIGNAL_TYPES = {'conference','patent','financing','publication',
                           'licensing','regulatory','clinical_update'}
    signals_written = 0
    for sig in data.get("competitive_signals", []):
        sig_title = (sig.get("title") or "").strip()
        sig_type  = (sig.get("signal_type") or "").strip()
        if not sig_title or sig_type not in _VALID_SIGNAL_TYPES:
            log(f"  competitive_signal skipped — missing title or invalid type '{sig_type}'", indent=1)
            continue
        if not sig.get("source_url"):
            log(f"  competitive_signal '{sig_title[:40]}': no source_url — skipping", indent=1)
            continue

        # Resolve drug_id — must exist in DB for this company
        sig_drug_id = (sig.get("drug_id") or "").strip() or None
        if sig_drug_id and sig_drug_id not in db_drug_ids:
            log(f"  competitive_signal '{sig_title[:40]}': unknown drug_id '{sig_drug_id}' — clearing", indent=1)
            sig_drug_id = None

        # Dedup: skip if (company_id, title) already exists
        dedup_q: dict = {
            "company_id": f"eq.{company_id}",
            "title":      f"eq.{sig_title[:200]}",
            "select":     "id",
            "limit":      "1",
        }
        if sb_get("competitive_signals", dedup_q):
            log(f"  competitive_signal '{sig_title[:45]}': already exists — skip", indent=1)
            continue

        sig_rec = {
            "company_id":  company_id,
            "drug_id":     sig_drug_id,
            "area_id":     area_id,
            "signal_type": sig_type,
            "title":       sig_title[:255],
            "description": (sig.get("description") or "")[:2000],
            "source_url":  (sig.get("source_url") or "")[:500],
            "source_date": sig.get("source_date"),
            "confidence":  float(sig.get("confidence") or 0.80),
        }
        result = sb_upsert("competitive_signals", sig_rec)
        if result:
            signals_written += 1
            log(f"  competitive_signal [{sig_type}] '{sig_title[:45]}': ✓", indent=1)
        else:
            log(f"  competitive_signal '{sig_title[:45]}': ✗ insert failed", indent=1)

    if signals_written:
        log(f"  → {signals_written} competitive_signal(s) saved for {company_id}", indent=1)

    # ── Molecule Intelligence ────────────────────────────────────────────
    mol_written = write_molecule_intelligence(company_id, area_id, data, ctx, dry_run,
                                              enrichment_run_id=enrichment_run_id)
    if mol_written:
        log(f"  → {mol_written} molecule_intelligence row(s) upserted", indent=1)

    # ── Company Partnerships ─────────────────────────────────────────────
    # If the LLM response includes a "new_partnerships" key, write them to
    # company_partnerships.  This key is optional — most responses won't have it.
    new_partnerships = data.get("new_partnerships") or []
    if new_partnerships:
        cp_written = write_company_partnerships(
            company_id, new_partnerships,
            run_id=enrichment_run_id,
            dry_run=dry_run,
        )
        if cp_written:
            log(f"  → {cp_written} company_partnership(s) written for {company_id}", indent=1)


from meridian.enrichment.company.molecule import write_molecule_intelligence


from meridian.enrichment.company.partnerships import write_company_partnerships


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
