#!/usr/bin/env python3
"""
Step 5 — Company Enrichment: web intel + response write (§3 company_enrichment split).
======================================================================================
Extracted verbatim from company_enrichment.py — the largest section.

  - gather_web_intelligence: Phase A live web_search for clinical/financing/deal facts.
  - parse_enrichment_response: tolerant JSON extraction of the Claude enrichment output.
  - write_step5: persists the structured enrichment to Supabase (company_profiles, drugs,
    catalysts, deals, trials, news, competitive signals) with confidence/source-URL
    enforcement; delegates molecule + partnership writes to their modules.

The prompt *construction* lives in company/prompts.py (build_step5_prompt); this module
consumes the already-parsed response.
"""

import json
import datetime
from typing import Optional

import requests

from meridian.enrichment.company.common import (
    client, _acc_tokens, log,
    TODAY, NOW_ISO, AREA_LABELS_MAP,
    sb_get, sb_upsert, sb_patch, _catalyst_upsert,
    validate_source_url, enforce_confidence_constraints, infer_catalog_category,
)
from meridian.enrichment.company.catalysts import _parse_sort_date
from meridian.enrichment.company.molecule import write_molecule_intelligence
from meridian.enrichment.company.partnerships import write_company_partnerships


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
            from meridian.database import update_drug
            ok = update_drug(drug_id, update_fields)
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
