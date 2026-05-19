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
    from identity_resolution import DrugIdentityResolver
    _IDENTITY_RESOLVER_AVAILABLE = True
except ImportError:
    _IDENTITY_RESOLVER_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════
# CREDENTIALS + CONSTANTS
# ══════════════════════════════════════════════════════════════════════════

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
CT_GOV_BASE  = "https://clinicaltrials.gov/api/v2"
TODAY        = datetime.datetime.utcnow().strftime("%Y-%m-%d")
NOW_ISO      = datetime.datetime.utcnow().isoformat()

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}
SB_UPSERT_HEADERS = {
    **SB_HEADERS,
    "Prefer": "resolution=merge-duplicates,return=representation",
}

# CT.gov status → our normalized status
CT_STATUS_MAP = {
    "RECRUITING":              "Recruiting",
    "ACTIVE_NOT_RECRUITING":   "Active, not recruiting",
    "COMPLETED":               "Completed",
    "TERMINATED":              "Terminated",
    "WITHDRAWN":               "Withdrawn",
    "NOT_YET_RECRUITING":      "Not yet recruiting",
    "ENROLLING_BY_INVITATION": "Enrolling by invitation",
    "APPROVED_FOR_MARKETING":  "Approved",
    "UNKNOWN":                 "Unknown",
}

# CT.gov phase codes → our display strings
CT_PHASE_MAP = {
    "PHASE1":        "Phase 1",
    "PHASE2":        "Phase 2",
    "PHASE3":        "Phase 3",
    "PHASE1_PHASE2": "Phase 1/2",
    "PHASE2_PHASE3": "Phase 2/3",
    "EARLY_PHASE1":  "Pre-IND",
    "NA":            "N/A",
}

# Stage rank for determining "most advanced" trial per drug
STAGE_RANK = {
    "Approved":    9,
    "Phase 3":     7,
    "Phase 2/3":   6,
    "Phase 2":     5,
    "Phase 1/2":   4,
    "Phase 1":     3,
    "Pre-IND":     2,
    "Preclinical": 1,
}


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
    # Duvakitug — NCT IDs not hardcoded (use search: "duvakitug")
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
}

# Drugs that are pre-IND (no trial expected yet — mark as 'pending')
PENDING_TRIAL_DRUGS = {
    "sim0709",    # Simcere/BI — FIH planned H2 2026
    "xmab412",    # Xencor bispecific — FIH planned Q3 2026
    "hxn1003",    # Earendil/Sanofi — IND expected 2026
}


# ══════════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════════

def log(msg: str, indent: int = 0):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    prefix = "  " * indent
    print(f"[ct_gov {ts}] {prefix}{msg}", flush=True)


# ══════════════════════════════════════════════════════════════════════════
# SUPABASE HELPERS
# ══════════════════════════════════════════════════════════════════════════

def sb_get(table: str, params: dict) -> list:
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=SB_HEADERS, params=params, timeout=15
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"[sb_get {table}] {e}", indent=1)
        return []


def sb_upsert(table: str, records: list | dict) -> list:
    if isinstance(records, dict):
        records = [records]
    if not records:
        return []
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=SB_UPSERT_HEADERS, json=records, timeout=15
        )
        if r.status_code not in (200, 201):
            log(f"[sb_upsert {table}] {r.status_code}: {r.text[:200]}", indent=1)
            return []
        return r.json()
    except Exception as e:
        log(f"[sb_upsert {table}] {e}", indent=1)
        return []


def sb_patch(table: str, record: dict, match_params: dict) -> bool:
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=SB_HEADERS, params=match_params, json=record, timeout=15
        )
        return r.status_code in (200, 204)
    except Exception as e:
        log(f"[sb_patch {table}] {e}", indent=1)
        return False


# ══════════════════════════════════════════════════════════════════════════
# CLINICALTRIALS.GOV API v2 — FETCH AND PARSE
# ══════════════════════════════════════════════════════════════════════════

def ct_fetch_by_nct(nct_id: str) -> Optional[dict]:
    """
    Fetch a single study by NCT ID from CT.gov API v2.
    Returns the raw study JSON or None on error/not found.
    """
    if not nct_id or not nct_id.startswith("NCT"):
        return None
    try:
        r = requests.get(
            f"{CT_GOV_BASE}/studies/{nct_id}",
            params={"format": "json"},
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            log(f"  NCT {nct_id}: not found on CT.gov", indent=2)
        else:
            log(f"  NCT {nct_id}: HTTP {r.status_code}", indent=2)
        return None
    except Exception as e:
        log(f"  NCT {nct_id}: fetch error — {e}", indent=2)
        return None


def ct_search_by_name(drug_name: str, indication: str = None, max_results: int = 10) -> list[dict]:
    """
    Search CT.gov by drug name + optional indication.
    Returns list of study JSON objects.
    """
    params = {
        "format":   "json",
        "pageSize": max_results,
        "query.intr": drug_name,
    }
    if indication:
        params["query.cond"] = indication
    try:
        r = requests.get(f"{CT_GOV_BASE}/studies", params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get("studies", [])
        return []
    except Exception as e:
        log(f"  Search '{drug_name}': error — {e}", indent=2)
        return []


def parse_ct_study(study: dict, drug_id: str, entity_id: str = None,
                   discovery_status: str = "manual",
                   confidence_score: int = 100,
                   canonical_drug_id: str = None) -> Optional[dict]:
    """
    Parse a raw CT.gov v2 study JSON into a Supabase trials record.

    CT.gov v2 response structure:
      study.protocolSection.identificationModule  → NCT ID, title
      study.protocolSection.statusModule          → status, dates
      study.protocolSection.designModule          → phase, enrollment
      study.protocolSection.outcomesModule        → endpoints
      study.protocolSection.armsInterventionsModule → arms
      study.protocolSection.conditionsModule      → conditions/indications
      study.protocolSection.sponsorCollaboratorsModule → sponsor
    """
    proto  = study.get("protocolSection", {})
    id_mod = proto.get("identificationModule", {})
    st_mod = proto.get("statusModule", {})
    de_mod = proto.get("designModule", {})
    ou_mod = proto.get("outcomesModule", {})
    ar_mod = proto.get("armsInterventionsModule", {})
    co_mod = proto.get("conditionsModule", {})
    sp_mod = proto.get("sponsorCollaboratorsModule", {})

    nct_id = id_mod.get("nctId", "")
    if not nct_id:
        return None

    # ── Status ──────────────────────────────────────────────────────────
    raw_status = st_mod.get("overallStatus", "UNKNOWN")
    status = CT_STATUS_MAP.get(raw_status, raw_status.replace("_", " ").title())

    # ── Phase ────────────────────────────────────────────────────────────
    phases = de_mod.get("phases", [])
    if phases:
        phase = CT_PHASE_MAP.get(phases[0], phases[0])
        if len(phases) > 1:
            # e.g. ["PHASE1", "PHASE2"] → "Phase 1/2"
            combined = "/".join(CT_PHASE_MAP.get(p, p) for p in phases)
            if "/" in combined:
                phase = combined
    else:
        phase = "N/A"

    # ── Enrollment ───────────────────────────────────────────────────────
    enroll = de_mod.get("enrollmentInfo", {})
    n_enrollment = enroll.get("count")

    # ── Dates ────────────────────────────────────────────────────────────
    pcd_struct = st_mod.get("primaryCompletionDateStruct", {})
    pcd_raw = pcd_struct.get("date", "")
    start_struct = st_mod.get("startDateStruct", {})
    start_date = start_struct.get("date", "")

    # Human-readable PCD label (e.g. "Aug 2026" from "2026-08-01")
    pcd_label = _format_date_label(pcd_raw)

    # ── Primary endpoint ─────────────────────────────────────────────────
    primary_outcomes = ou_mod.get("primaryOutcomes", [])
    primary_endpoint = ""
    if primary_outcomes:
        m = primary_outcomes[0].get("measure", "")
        tf = primary_outcomes[0].get("timeFrame", "")
        primary_endpoint = f"{m} ({tf})" if tf else m

    # ── Secondary endpoints ──────────────────────────────────────────────
    secondary_outcomes = ou_mod.get("secondaryOutcomes", [])
    secondary_endpoints = [
        {"measure": o.get("measure", ""), "time_frame": o.get("timeFrame", "")}
        for o in secondary_outcomes[:5]   # cap at 5 for storage efficiency
    ]

    # ── Arms ─────────────────────────────────────────────────────────────
    arm_groups = ar_mod.get("armGroups", [])
    arms = [
        {
            "label":       a.get("label", ""),
            "type":        a.get("type", ""),
            "description": (a.get("description", "") or "")[:200],
        }
        for a in arm_groups[:6]   # cap at 6 arms
    ]

    # ── Indication ───────────────────────────────────────────────────────
    conditions = co_mod.get("conditions", [])
    indication = " · ".join(conditions[:3]) if conditions else ""

    # ── Sponsor ──────────────────────────────────────────────────────────
    lead_sponsor = sp_mod.get("leadSponsor", {})
    sponsor = lead_sponsor.get("name", "")

    # ── Source URL ───────────────────────────────────────────────────────
    source_url = f"https://clinicaltrials.gov/study/{nct_id}"

    return {
        "id":                    nct_id,
        "drug_id":               drug_id,
        "entity_id":             entity_id,
        "trial_name":            id_mod.get("briefTitle", "")[:300],
        "phase":                 phase,
        "status":                status,
        "indication":            indication[:200] if indication else None,
        "n_enrollment":          n_enrollment,
        "primary_endpoint":      primary_endpoint[:500] if primary_endpoint else None,
        "secondary_endpoints":   secondary_endpoints or None,
        "arms":                  arms or None,
        "start_date":            start_date or None,
        "primary_completion_date": pcd_raw or None,
        "pcd_label":             pcd_label or None,
        "readout_date":          pcd_label or None,   # alias for backward compat
        "source_url":            source_url,
        "sponsor":               sponsor[:200] if sponsor else None,
        "last_synced_date":      NOW_ISO,
        "discovery_status":      discovery_status,
        "confidence_score":      confidence_score,
        "canonical_drug_id":     canonical_drug_id,
    }


def _format_date_label(date_str: str) -> str:
    """
    Convert CT.gov date string to human-readable label.
    "2026-08-01" → "Aug 2026"
    "2026-08"    → "Aug 2026"
    "2026"       → "2026"
    """
    if not date_str:
        return ""
    month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    parts = date_str.split("-")
    if len(parts) >= 2:
        try:
            month_idx = int(parts[1]) - 1
            year = parts[0]
            return f"{month_names[month_idx]} {year}"
        except (ValueError, IndexError):
            pass
    return date_str


# ══════════════════════════════════════════════════════════════════════════
# CONFIDENCE SCORING — for search-discovered trials
# ══════════════════════════════════════════════════════════════════════════

def score_search_match(study: dict, drug_id: str, drug_name: str,
                       drug_indication: str = None) -> int:
    """
    Score how well a CT.gov search result matches our drug.
    Returns 0-100 confidence score.

    Scoring rubric:
      +50  if drug name appears in brief title (exact match, case-insensitive)
      +30  if drug name appears in interventions
      +20  if drug name appears in sponsor
      +15  if indication matches condition
      -20  if study is terminated/withdrawn
    """
    score = 0
    proto = study.get("protocolSection", {})
    id_mod = proto.get("identificationModule", {})
    title = (id_mod.get("briefTitle", "") or "").lower()
    st_mod = proto.get("statusModule", {})
    status = st_mod.get("overallStatus", "")
    co_mod = proto.get("conditionsModule", {})
    conditions = " ".join(co_mod.get("conditions", [])).lower()
    sp_mod = proto.get("sponsorCollaboratorsModule", {})
    sponsor = (sp_mod.get("leadSponsor", {}).get("name", "") or "").lower()
    ar_mod = proto.get("armsInterventionsModule", {})
    interventions = " ".join(
        i.get("name", "") for i in ar_mod.get("interventions", [])
    ).lower()

    name_lc = drug_name.lower()

    # Name in title
    if name_lc in title:
        score += 50
    elif any(part in title for part in name_lc.split() if len(part) > 4):
        score += 25

    # Name in interventions
    if name_lc in interventions:
        score += 30
    elif any(part in interventions for part in name_lc.split() if len(part) > 4):
        score += 15

    # Indication match
    if drug_indication:
        ind_lc = drug_indication.lower()
        if any(kw in conditions for kw in ind_lc.split() if len(kw) > 4):
            score += 15

    # Penalty for terminated/withdrawn
    if status in ("TERMINATED", "WITHDRAWN"):
        score -= 20

    return min(100, max(0, score))


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

    for nct_id in nct_ids:
        log(f"  → Fetching {nct_id}...", indent=2)
        study = ct_fetch_by_nct(nct_id)

        if not study:
            log(f"  ✗ {nct_id}: no data returned", indent=2)
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

def sync_drug(drug: dict, dry_run: bool = False) -> dict:
    """
    Run full trial sync for a single drug.

    Conditional routing:
      IF drug is in APPROVED_DRUGS → create a simplified approved record, skip deep sync
      IF drug is in PENDING_TRIAL_DRUGS → mark trial_data_status='pending', skip
      ELIF drug is in NCT_SEED_MAP → Step 3a (direct NCT fetch)
      ELIF has existing trial records → Step 3a for those NCT IDs
      ELSE → Step 3b (search discovery)

    Returns: {"synced": [...nct_ids], "status": "ok"|"pending"|"approved"|"no_results"}
    """
    drug_id   = drug["id"]
    drug_name = drug.get("name", drug_id)

    # ── Identity resolution (circuit-breaker pattern) ─────────────────────
    # Resolve drug name → canonical_drug_id before writing any trial record.
    # On any failure: log and continue with canonical_drug_id=None.
    # This ensures resolver failures never crash the CT.gov sync.
    canonical_drug_id = None
    if _IDENTITY_RESOLVER_AVAILABLE and not dry_run:
        try:
            resolver = DrugIdentityResolver(SUPABASE_URL, SUPABASE_KEY)
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
    if known_ncts:
        log(f"  [3a] Direct sync: {len(known_ncts)} known NCT IDs", indent=1)
        synced = step3a_direct_nct_sync(drug, known_ncts, dry_run=dry_run,
                                         canonical_drug_id=canonical_drug_id)
        all_synced.extend(synced)

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
        # Get drug IDs linked to this area
        drug_area_rows = sb_get("drug_areas", {
            "area_id": f"eq.{area_id}",
            "select":  "drug_id",
        })
        drug_ids = [r["drug_id"] for r in drug_area_rows]
        if not drug_ids:
            log(f"No drugs found for area '{area_id}'")
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

    # ── Sync each drug ────────────────────────────────────────────────────
    stats = {"synced": 0, "no_results": 0, "pending": 0, "approved": 0, "total_trials": 0}

    for drug in drugs:
        drug_id   = drug["id"]
        drug_name = drug.get("name", drug_id)

        log(f"\n[Drug] {drug_name} ({drug_id}) — {drug.get('stage','?')}", indent=0)

        # Skip search if search_only=False and drug not in NCT_SEED_MAP
        # (will still do 3b search regardless)

        result = sync_drug(drug, dry_run=dry_run)

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
