#!/usr/bin/env python3
"""
Ailux BD Platform — ClinicalTrials.gov Sync Module
===================================================
Pipeline Step 3: Trial Sync

Maintains the `trials` table as a structured, always-current mirror
of ClinicalTrials.gov data for every drug tracked by the platform.

CONDITIONAL LOGIC (the "if this then this" model):

  ┌── For each drug in Supabase (optionally filtered by area/drug):
  │
  ├── IF drug has known NCT IDs (in NCT_SEED_MAP or existing trials):
  │     → Fetch each NCT ID directly from CT.gov API v2
  │     → Parse full structured fields (status, phase, enrollment,
  │       arms, endpoints, dates, sponsor)
  │     → Upsert into trials table (merge-duplicates on id)
  │     → Mark last_synced_date = NOW()
  │
  ├── IF drug has no known NCT IDs AND trial_data_status != 'pending':
  │     → Search CT.gov by drug name + indication
  │     → Score each result: name similarity + sponsor + indication
  │     → IF score >= 85: upsert with discovery_status='auto'
  │     → IF 60 <= score < 85: upsert with discovery_status='unverified'
  │     → IF score < 60: skip (log only, do not write)
  │
  └── AFTER all drugs synced:
        → Update drugs.stage where trials show advancement
          (e.g., if all trials are Phase 3, set stage = 'Phase 3')
        → Update drugs.trial_data_status:
            'populated' if ≥1 trial found
            'missing'   if search found nothing
        → Log sync summary

USAGE:
  python scripts/ct_gov_sync.py                       # all drugs
  python scripts/ct_gov_sync.py --area tl1a           # one area
  python scripts/ct_gov_sync.py --drug tulisokibart    # one drug
  python scripts/ct_gov_sync.py --dry-run             # no DB writes
  python scripts/ct_gov_sync.py --search-only         # only search, skip direct NCT fetch

CALLED BY:
  .github/workflows/company-enrichment.yml (runs before company_enrichment.py)
  Can also be imported: from scripts.ct_gov_sync import sync_drug, get_trials_for_drug

ENVIRONMENT:
  SUPABASE_URL         — https://tghntyofptvfhmtchwcv.supabase.co
  SUPABASE_SERVICE_KEY — service role key (write access)
"""

import os
import sys
import json
import time
import datetime
import argparse
import re
from typing import Optional

import requests

try:
    from meridian.identity.identity_resolution import DrugIdentityResolver
    _IDENTITY_RESOLVER_AVAILABLE = True
except ImportError:
    _IDENTITY_RESOLVER_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════
# CREDENTIALS + CONSTANTS
# ══════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════
# §3 SPLIT — credentials, constants, Supabase I/O, and the fetch/map/validate/write
# submodules now live in meridian.ingestion.ctgov.*; imported here so the
# orchestration (step3*, sync_drug, run_sync, get_trials_*) call sites are unchanged.
# ══════════════════════════════════════════════════════════════════════════
from meridian.ingestion.ctgov.common import (
    SUPABASE_URL, SUPABASE_KEY, CT_GOV_BASE, TODAY, NOW_ISO, STAGE_RANK,
    log, sb_get, sb_upsert, sb_patch,
)
from meridian.ingestion.ctgov.validate import run_field_validation
from meridian.ingestion.ctgov.fetch import ct_fetch_by_nct, ct_search_by_name
from meridian.ingestion.ctgov.map import parse_ct_study, score_search_match
from meridian.ingestion.ctgov.write import update_trial_registries


# ══════════════════════════════════════════════════════════════════════════
# NCT SEED MAP
# Known NCT IDs for drugs in the database, sourced from static TL1A_PROGRAMS
# and manually verified against ClinicalTrials.gov.
#
# FORMAT: { drug_id → [nct_id, ...] }
#
# This map is the authoritative starting point. As the pipeline discovers
# new trials via the search path, they are added to the trials table
# with discovery_status='auto'. This map itself should only contain
# manually verified IDs.
#
# Drugs not in this map go through the search path (Step 3b).
# ══════════════════════════════════════════════════════════════════════════

NCT_SEED_MAP: dict[str, list[str]] = {

    # ── TL1A DIRECT COMPETITORS ────────────────────────────────────────────
    "tulisokibart": [
        "NCT06052059",   # ATLAS-UC — Ph3 induction + maintenance (N=1020)
        "NCT06430801",   # ARES-CD  — Ph3 induction + maintenance (N=1200)
        "NCT06651281",   # Long-term extension — UC+CD (N=1380)
        "NCT06956235",   # HS expansion — Ph2 (N=147)
        "NCT07176390",   # RA expansion — Ph2 (N=182)
        "NCT05270668",   # Systemic Sclerosis — Ph2 (N=154)
    ],
    "afimkibart": [
        "NCT06589986",   # AMETRINE-2 — UC induction + maintenance (Ph3, N=400)
        "NCT06588855",   # AMETRINE-1 — UC induction (Ph3, N=350)
        "NCT06819878",   # SIBERITE-1 — CD induction + maintenance (Ph3, N=600)
        "NCT06819891",   # SIBERITE-2 — CD induction (Ph3, N=425)
        "NCT06863961",   # AD expansion (Ph2, N=160)
        "NCT07158242",   # Pediatric UC induction + maintenance (Ph3, N=100)
        "NCT07298421",   # Pediatric CD induction + maintenance (Ph3, N=100)
    ],
    "spy002": [
        "NCT07012395",   # SKYLINE Part A+B — Ph2 UC multi-arm (N=645 total)
        "NCT06672718",   # Phase 1 HV PK/safety (N=56)
    ],
    "xmab942": [
        "NCT06619990",   # XENITH-UC — Ph1/2b UC (N=270)
    ],
    "mt-251": [
        "NCT07423299",   # Phase 1 FIH — healthy volunteers (N=70)
    ],
    "duvakitug": [
        "NCT07184996",   # STARSCAPE UC — induction (N=980, PCD May 2028)
        "NCT07185009",   # STARSCAPE UC — maintenance (N=671, PCD Sep 2028)
        "NCT07184931",   # SUNSCAPE CD — induction (N=980, PCD May 2029)
        "NCT07184944",   # SUNSCAPE CD — maintenance (N=751, PCD Aug 2029)
        "NCT05499130",   # Phase 2b UC + CD — completed (N=290, PCD Nov 2024)
    ],
    # Izokibep — use search: "izokibep"
    # FG-M701  — use search: "fg-m701" or "FG-M701"
    # SIM0709  — pre-IND, no trial yet (trial_data_status='pending')

    # ── TL1A INDIRECT (SOC — approved products) ────────────────────────────
    # Approved products: skip deep trial sync; use simplified records
    # These will be handled by the search path if needed

    # ── TSLP COMPETITORS ──────────────────────────────────────────────────
    # Tezepelumab (astegolimab program), astegolimab — use search
    # Itepekimab — use search

    # ── IL-4Rα COMPETITORS ────────────────────────────────────────────────
    # Dupilumab — approved; use search for new trials
    # Amlitelimab — use search

    # ── IGF1R COMPETITORS ─────────────────────────────────────────────────
    # Teprotumumab — approved
    # Veligrotug — use search

    # ── FcRn COMPETITORS ──────────────────────────────────────────────────
    # Efgartigimod, rozanolixizumab, nipocalimab, batoclimab — use search
}

# Drugs that are approved products (pre-clinic trial sync not needed)
# These still get a simplified trial record but don't need deep CT.gov sync
APPROVED_DRUGS = {
    "dupilumab", "tezepelumab", "teprotumumab",
    "abbvie-skyrizi", "abbvie-rinvoq", "takeda-entyvio", "lilly-omvoh",
    "efgartigimod",
    "mirikizumab",    # Omvoh — approved UC (2023) + CD (2024); trials seeded manually
    "vedolizumab",    # Entyvio — approved UC + CD
    "ustekinumab",    # Stelara — approved UC + CD + PsO + PsA
    "risankizumab",   # Skyrizi — approved UC + CD + PsO
    "guselkumab",     # Tremfya — approved PsO + PsA
}

# Drugs that are pre-IND (no trial expected yet — mark as 'pending')
PENDING_TRIAL_DRUGS = {
    "sim0709",    # Simcere/BI — FIH planned H2 2026
    "xmab412",    # Xencor bispecific — FIH planned Q3 2026
    "hxn1003",    # Earendil/Sanofi — IND expected 2026
}


# ══════════════════════════════════════════════════════════════════════════
# CLINICALTRIALS.GOV API v2 — FETCH AND PARSE
# ══════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════
# STEP 3a — DIRECT NCT SYNC
# For drugs with known NCT IDs: fetch directly, upsert with full fields
# ══════════════════════════════════════════════════════════════════════════

def step3a_direct_nct_sync(drug: dict, nct_ids: list[str],
                            dry_run: bool = False,
                            canonical_drug_id: str = None) -> list[str]:
    """
    Fetch each known NCT ID from CT.gov and upsert into trials table.

    Returns list of NCT IDs successfully synced.
    """
    drug_id   = drug["id"]
    entity_id = drug.get("entity_id")
    synced    = []

    # Build the full set of names to match against CT.gov interventions
    drug_name_lc  = drug.get("name", drug_id).lower()
    drug_aliases  = [a.lower() for a in (drug.get("aliases") or []) if a]
    drug_all_names = [drug_name_lc] + drug_aliases

    for nct_id in nct_ids:
        log(f"  → Fetching {nct_id}...", indent=2)
        study = ct_fetch_by_nct(nct_id)

        if not study:
            log(f"  ✗ {nct_id}: no data returned", indent=2)
            continue

        # ── Sanity check: drug name must appear somewhere in the trial ────────
        p = study.get("protocolSection", {})
        interv_module = p.get("armsInterventionsModule", {})
        interventions_raw = [i.get("name", "") for i in interv_module.get("interventions", [])]
        ct_title = p.get("identificationModule", {}).get("briefTitle", "")
        interv_text = (" ".join(interventions_raw) + " " + ct_title).lower()

        name_found = False
        for name in drug_all_names:
            if not name or name == "—":
                continue
            if name in interv_text:
                name_found = True
                break
            # Word-level match for multi-word or hyphenated names
            for part in name.replace("-", " ").split():
                if len(part) > 5 and part in interv_text:
                    name_found = True
                    break
            if name_found:
                break

        if not name_found and interventions_raw:
            # Interventions are present but drug not found → likely wrong NCT ID
            log(
                f"  ⚠ {nct_id}: SEED VALIDATION FAILED — drug '{drug_name_lc}' "
                f"not found in CT.gov interventions {interventions_raw[:3]}. "
                f"Skipping insert. Check NCT_SEED_MAP for wrong ID.",
                indent=2
            )
            continue

        record = parse_ct_study(
            study, drug_id, entity_id,
            discovery_status="manual",  # known NCT IDs are manually verified
            confidence_score=100,
            canonical_drug_id=canonical_drug_id,
        )
        if not record:
            log(f"  ✗ {nct_id}: parse failed", indent=2)
            continue

        if dry_run:
            log(f"  [DRY RUN] Would upsert: {nct_id} | {record['status']} | N={record['n_enrollment']}", indent=2)
        else:
            result = sb_upsert("trials", record)
            if result:
                log(f"  ✓ {nct_id}: {record['status']} | Ph={record['phase']} | N={record['n_enrollment']} | PCD={record['pcd_label']}", indent=2)
                synced.append(nct_id)
            else:
                log(f"  ✗ {nct_id}: upsert failed", indent=2)

        time.sleep(0.5)   # polite rate limiting

    return synced


# ══════════════════════════════════════════════════════════════════════════
# STEP 3b — SEARCH-BASED DISCOVERY
# For drugs without known NCT IDs: search CT.gov by name + indication
# ══════════════════════════════════════════════════════════════════════════

def step3b_search_discovery(drug: dict, dry_run: bool = False,
                             canonical_drug_id: str = None) -> list[str]:
    """
    Search CT.gov for trials matching this drug by name.

    Confidence scoring:
      >= 85 → upsert with discovery_status='auto'
      60-84 → upsert with discovery_status='unverified'
      < 60  → skip (log only)

    Returns list of NCT IDs found (regardless of confidence).
    """
    drug_id    = drug["id"]
    drug_name  = drug.get("name", drug_id)
    entity_id  = drug.get("entity_id")
    indication = drug.get("indication_short") or drug.get("stage_detail") or None
    found      = []

    log(f"  → Searching CT.gov: '{drug_name}'...", indent=2)
    results = ct_search_by_name(drug_name, indication=indication)

    if not results:
        log(f"  ✗ No results for '{drug_name}'", indent=2)
        return []

    for study in results:
        nct_id = (study.get("protocolSection", {})
                       .get("identificationModule", {})
                       .get("nctId", ""))
        if not nct_id:
            continue

        # Check if we already have this trial
        existing = sb_get("trials", {"id": f"eq.{nct_id}", "select": "id"})
        if existing:
            log(f"  ↩ {nct_id}: already exists — skip", indent=3)
            found.append(nct_id)
            continue

        score = score_search_match(study, drug_id, drug_name, indication)

        if score < 60:
            log(f"  ↷ {nct_id}: score={score} (too low, skipping)", indent=3)
            continue

        # Determine discovery status based on confidence
        if score >= 85:
            discovery_status = "auto"
            flag = "✓"
        else:  # 60-84
            discovery_status = "unverified"
            flag = "⚠"

        record = parse_ct_study(
            study, drug_id, entity_id,
            discovery_status=discovery_status,
            confidence_score=score,
            canonical_drug_id=canonical_drug_id,
        )
        if not record:
            continue

        if dry_run:
            log(f"  [DRY RUN] {flag} {nct_id}: score={score} | {record['status']}", indent=3)
        else:
            result = sb_upsert("trials", record)
            if result:
                log(f"  {flag} {nct_id}: score={score} | {record['status']} | {discovery_status}", indent=3)
                found.append(nct_id)

        time.sleep(0.3)

    return found


# ══════════════════════════════════════════════════════════════════════════
# STEP 3c — STAGE UPDATE
# After syncing trials, update drug.stage to match most advanced trial
# ══════════════════════════════════════════════════════════════════════════

def step3c_update_drug_stage(drug_id: str, synced_nct_ids: list[str],
                              dry_run: bool = False):
    """
    Determine the most advanced phase across all trials for this drug
    and update drugs.stage if it differs.

    Logic:
      IF any trial is Phase 3 (active/recruiting) → stage = 'Phase 3'
      ELSE IF Phase 2/3 or Phase 2 → stage = that phase
      ... etc.
      IF no trials found → stage unchanged
    """
    if not synced_nct_ids:
        return

    # Fetch all trials for this drug
    trials = sb_get("trials", {"drug_id": f"eq.{drug_id}", "select": "phase,status"})
    if not trials:
        return

    # Find highest-ranked active phase
    best_phase = None
    best_rank  = 0
    active_statuses = {"Recruiting", "Active, not recruiting", "Not yet recruiting",
                       "Enrolling by invitation", "Approved"}

    for t in trials:
        phase  = t.get("phase", "")
        status = t.get("status", "")
        rank   = STAGE_RANK.get(phase, 0)
        if rank > best_rank and status in active_statuses:
            best_rank  = rank
            best_phase = phase

    if not best_phase:
        return

    # Only update if the stage has changed
    drug_rows = sb_get("drugs", {"id": f"eq.{drug_id}", "select": "stage"})
    current_stage = drug_rows[0]["stage"] if drug_rows else None

    if current_stage == best_phase:
        return   # already correct

    if dry_run:
        log(f"  [DRY RUN] Would update {drug_id}.stage: {current_stage!r} → {best_phase!r}", indent=2)
    else:
        ok = sb_patch("drugs",
                      {"stage": best_phase, "last_synced_date": NOW_ISO},
                      {"id": f"eq.{drug_id}"})
        if ok:
            log(f"  ↑ Stage updated: {drug_id} {current_stage!r} → {best_phase!r}", indent=2)


# ══════════════════════════════════════════════════════════════════════════
# MAIN SYNC FUNCTION — orchestrates Steps 3a + 3b + 3c per drug
# ══════════════════════════════════════════════════════════════════════════

def sync_drug(drug: dict, dry_run: bool = False, resolver=None,
              search_only: bool = False) -> dict:
    """
    Run full trial sync for a single drug.

    Conditional routing:
      IF drug is in APPROVED_DRUGS → create a simplified approved record, skip deep sync
      IF drug is in PENDING_TRIAL_DRUGS → mark trial_data_status='pending', skip
      ELIF drug is in NCT_SEED_MAP → Step 3a (direct NCT fetch)
      ELIF has existing trial records → Step 3a for those NCT IDs
      ELSE → Step 3b (search discovery)

    Args:
      resolver:     a pre-instantiated DrugIdentityResolver (created once in run_sync).
                    Pass None to skip identity resolution.
      search_only:  if True, skip Step 3a (direct NCT fetch) and only run Step 3b
                    (search discovery). Useful for testing search paths without
                    direct CT.gov NCT lookups.

    Returns: {"synced": [...nct_ids], "status": "ok"|"pending"|"approved"|"no_results"}
    """
    drug_id   = drug["id"]
    drug_name = drug.get("name", drug_id)

    # ── Identity resolution (circuit-breaker pattern) ─────────────────────
    # Resolver is pre-instantiated in run_sync() — one alias-cache load per run,
    # not once per drug. On any failure: log and continue with canonical_drug_id=None.
    canonical_drug_id = None
    if resolver is not None and not dry_run:
        try:
            canon_id, conf, method = resolver.resolve(
                drug_name, source="ct_gov",
                drug_class=drug.get("drug_class"),
                mechanism=drug.get("mechanism"),
                target=drug.get("target"),
            )
            canonical_drug_id = canon_id
            log(f"  ↳ Identity: {canon_id} (conf={conf}, method={method})", indent=1)
        except Exception as exc:
            log(f"  ⚠ Identity resolver failed for '{drug_name}': {exc} — proceeding without canonical_drug_id", indent=1)
            try:
                resolver.log_resolver_error(
                    drug_name=drug_name, source="ct_gov_sync", error=exc,
                    source_table="drugs", source_row_id=drug_id,
                )
            except Exception:
                pass  # never let error-logging crash the sync

    # ── Approved products: simplified handling ────────────────────────────
    if drug_id in APPROVED_DRUGS:
        log(f"  ⊘ {drug_id}: approved product — marking trial_data_status='populated'", indent=1)
        if not dry_run:
            sb_patch("drugs",
                     {"trial_data_status": "populated", "last_synced_date": NOW_ISO},
                     {"id": f"eq.{drug_id}"})
        return {"synced": [], "status": "approved"}

    # ── Pre-IND drugs: no trial expected yet ─────────────────────────────
    if drug_id in PENDING_TRIAL_DRUGS:
        log(f"  ⏳ {drug_id}: pre-IND — marking trial_data_status='pending'", indent=1)
        if not dry_run:
            sb_patch("drugs",
                     {"trial_data_status": "pending", "last_synced_date": NOW_ISO},
                     {"id": f"eq.{drug_id}"})
        return {"synced": [], "status": "pending"}

    # ── Collect known NCT IDs ─────────────────────────────────────────────
    # Priority: NCT_SEED_MAP > existing trials table records
    known_ncts = list(NCT_SEED_MAP.get(drug_id, []))

    if not known_ncts:
        existing_trials = sb_get("trials", {
            "drug_id": f"eq.{drug_id}",
            "select":  "id",
        })
        known_ncts = [t["id"] for t in existing_trials if t["id"].startswith("NCT")]

    all_synced = []

    # ── Step 3a: Direct NCT fetch (known IDs) ────────────────────────────
    if known_ncts and not search_only:
        log(f"  [3a] Direct sync: {len(known_ncts)} known NCT IDs", indent=1)
        synced = step3a_direct_nct_sync(drug, known_ncts, dry_run=dry_run,
                                         canonical_drug_id=canonical_drug_id)
        all_synced.extend(synced)
    elif known_ncts and search_only:
        log(f"  [3a] Skipped (--search-only): {len(known_ncts)} known NCT IDs", indent=1)

    # ── Step 3b: Search discovery (unknown IDs) ───────────────────────────
    # Run search even when we have seed NCT IDs — may find additional trials
    # (e.g., expansion studies, new indications)
    if not dry_run or not known_ncts:
        log(f"  [3b] Search discovery: '{drug_name}'", indent=1)
        found = step3b_search_discovery(drug, dry_run=dry_run,
                                         canonical_drug_id=canonical_drug_id)
        # Only add IDs not already in all_synced
        all_synced.extend(nct for nct in found if nct not in all_synced)

    # ── Step 3c: Update drug stage ────────────────────────────────────────
    step3c_update_drug_stage(drug_id, all_synced, dry_run=dry_run)

    # ── Update trial_data_status ─────────────────────────────────────────
    trial_status = "populated" if all_synced else "missing"
    if not dry_run:
        sb_patch("drugs",
                 {"trial_data_status": trial_status, "last_synced_date": NOW_ISO},
                 {"id": f"eq.{drug_id}"})

    # ── Update trial_registries.ct_gov row for this drug ─────────────────
    update_trial_registries(drug_id, all_synced, dry_run=dry_run)

    return {"synced": all_synced, "status": "ok" if all_synced else "no_results"}


# ══════════════════════════════════════════════════════════════════════════
# SYNC LOOP — fetch drugs from Supabase and sync each one
# ══════════════════════════════════════════════════════════════════════════

def run_sync(area_id: str = None, drug_filter: str = None,
             dry_run: bool = False, search_only: bool = False):
    """
    Main entry point. Fetches drugs from Supabase and syncs each one.

    IF area_id is set: only sync drugs linked to that disease area
    IF drug_filter is set: only sync drugs matching that substring
    """
    log(f"{'='*60}")
    log(f"ClinicalTrials.gov Sync — {TODAY}")
    log(f"Area: {area_id or 'all'} | Drug filter: {drug_filter or 'none'}")
    log(f"Dry run: {dry_run} | Search only: {search_only}")
    log(f"{'='*60}")

    # ── Fetch drugs ───────────────────────────────────────────────────────
    if area_id:
        # Fetch the indication_group for this area (e.g. tl1a → 'ibd').
        # The frontend shows drugs tagged with the indication_group (e.g. all IBD drugs
        # in the TL1A tab, not just TL1A-tagged ones). We mirror this so the trial sync
        # covers the same drug set the dashboard displays.
        area_meta = sb_get("disease_areas", {"id": f"eq.{area_id}", "select": "indication_group"})
        indication_group = (area_meta[0].get("indication_group") if area_meta else None) or area_id
        fetch_areas = list({area_id, indication_group})  # deduplicate

        drug_area_rows = sb_get("drug_areas", {
            "area_id": f"in.({','.join(fetch_areas)})",
            "select":  "drug_id",
        })
        drug_ids = [r["drug_id"] for r in drug_area_rows]
        if not drug_ids:
            log(f"No drugs found for area '{area_id}' (+ ig='{indication_group}')")
            return

        drug_id_filter = ",".join(drug_ids)
        drugs = sb_get("drugs", {
            "id":     f"in.({drug_id_filter})",
            "select": "*",
        })
    else:
        drugs = sb_get("drugs", {"select": "*"})

    if drug_filter:
        drugs = [d for d in drugs if drug_filter.lower() in d["id"].lower()
                 or drug_filter.lower() in (d.get("name") or "").lower()]

    log(f"Drugs to sync: {len(drugs)}")

    # ── Instantiate identity resolver once for this run ───────────────────
    # A single instance loads the alias cache once (one Supabase round-trip),
    # then each sync_drug() call reuses the cached data.
    run_resolver = None
    if _IDENTITY_RESOLVER_AVAILABLE and not dry_run:
        try:
            run_resolver = DrugIdentityResolver(SUPABASE_URL, SUPABASE_KEY)
            run_resolver._load_alias_cache()  # pre-load once; per-drug calls reuse this
            log(f"Identity resolver ready ({len(run_resolver._alias_cache)} cached aliases)")
        except Exception as exc:
            log(f"⚠ Could not initialise identity resolver: {exc} — running without it")

    # ── Sync each drug ────────────────────────────────────────────────────
    stats = {"synced": 0, "no_results": 0, "pending": 0, "approved": 0, "total_trials": 0}

    for drug in drugs:
        drug_id   = drug["id"]
        drug_name = drug.get("name", drug_id)

        log(f"\n[Drug] {drug_name} ({drug_id}) — {drug.get('stage','?')}", indent=0)

        result = sync_drug(drug, dry_run=dry_run, resolver=run_resolver,
                           search_only=search_only)

        if result["status"] == "ok":
            stats["synced"] += 1
            stats["total_trials"] += len(result["synced"])
        elif result["status"] == "no_results":
            stats["no_results"] += 1
        elif result["status"] == "pending":
            stats["pending"] += 1
        elif result["status"] == "approved":
            stats["approved"] += 1

        time.sleep(1.0)   # pause between drugs to be polite to CT.gov

    # ── Summary ───────────────────────────────────────────────────────────
    log(f"\n{'='*60}")
    log(f"Sync complete:")
    log(f"  Synced:     {stats['synced']} drugs ({stats['total_trials']} trials upserted)")
    log(f"  No results: {stats['no_results']} drugs (flagged 'missing')")
    log(f"  Pre-IND:    {stats['pending']} drugs (marked 'pending')")
    log(f"  Approved:   {stats['approved']} drugs (marked 'populated')")
    log(f"{'='*60}")

    # ── Field semantic validation (runs after every sync) ─────────────────
    # Catches study acronyms in brand_name, mismatched study_acronym vs
    # trial_name, and other identity field contamination introduced during
    # the sync or by manual seeding. Warnings are printed to stdout so they
    # appear in GitHub Actions logs without failing the workflow.
    if not dry_run:
        log(f"\n[Validation] Running field semantic checks...")
        run_field_validation(dry_run=dry_run)


# ══════════════════════════════════════════════════════════════════════════
# UTILITY — get all trials for a drug (for use as an import by other scripts)
# ══════════════════════════════════════════════════════════════════════════

def get_trials_for_drug(drug_id: str) -> list[dict]:
    """
    Fetch current trial records for a drug from Supabase.
    Used by company_enrichment.py Step 3 context pull.
    """
    return sb_get("trials", {"drug_id": f"eq.{drug_id}", "select": "*"})


def get_trials_for_area(area_id: str) -> list[dict]:
    """
    Fetch all trial records for drugs in a disease area.
    """
    drug_area_rows = sb_get("drug_areas", {
        "area_id": f"eq.{area_id}",
        "select":  "drug_id",
    })
    drug_ids = [r["drug_id"] for r in drug_area_rows]
    if not drug_ids:
        return []
    return sb_get("trials", {
        "drug_id": f"in.({','.join(drug_ids)})",
        "select":  "*",
    })


# ══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ailux BD Platform — ClinicalTrials.gov Sync"
    )
    parser.add_argument("--area",  help="Disease area ID to sync (e.g. tl1a)")
    parser.add_argument("--drug",  help="Drug ID substring to sync (e.g. tulisokibart)")
    parser.add_argument("--dry-run",     action="store_true",
                        help="Fetch and score but do not write to Supabase")
    parser.add_argument("--search-only", action="store_true",
                        help="Only run search discovery (skip direct NCT fetch)")
    args = parser.parse_args()

    run_sync(
        area_id=args.area,
        drug_filter=args.drug,
        dry_run=args.dry_run,
        search_only=args.search_only,
    )
