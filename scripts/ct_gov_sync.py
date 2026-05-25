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
# FIELD SEMANTIC VALIDATION
# Guards against study acronyms / trial names leaking into molecule identity
# fields (brand_name, name, display_name). Run after upsert or on demand.
# ══════════════════════════════════════════════════════════════════════════

# Known study program acronyms — these must never appear as brand_name values.
# Add to this list whenever a new program acronym is seeded.
# NOTE: Do NOT add real brand names here — use KNOWN_BRAND_NAMES below instead.
KNOWN_STUDY_ACRONYMS: set[str] = {
    # TL1A programs
    "ATLAS", "ARES", "SKYLINE", "XENITH", "STARSCAPE", "SUNSCAPE",
    "ARTEMIS", "APOLLO", "DUET",
    # UC/CD programs
    "LUCENT", "VIVID", "PURSUIT", "ULTRAVIOLET", "UNIFI", "OCTAVE",
    "GEMINI", "VARSITY", "CALM",
    # Head-to-head program names
    "SEQUENCE",
    # TSLP / IL-4Ra
    "NAVIGATOR", "SOLSTICE", "LIBERTY", "SOLO", "CHRONOS",
    # FcRn
    "ADAPT", "ADAPT-NXT", "ARGX", "CHAMPION",
    # T-cell / CAR-T
    "CARTITUDE", "ZUMA", "JULIET", "ELARA",
    # Generic patterns caught by regex (see validate_drug_brand_name)
}

# Known legitimate brand names that look like acronyms (all-caps, short) but are
# real FDA/EMA/NMPA-approved trade names. Suppress false-positive warnings for these.
KNOWN_BRAND_NAMES: set[str] = {
    "TEPEZZA",    # teprotumumab — FDA-approved, thyroid eye disease (Horizon/Amgen)
    "CARVYKTI",   # ciltacabtagene autoleucel — FDA-approved, multiple myeloma (J&J/Legend)
    "SYCUME",     # ibi311 — NMPA-approved, thyroid eye disease (Innovent, China)
}

# Regex pattern for study-acronym-like strings:
#   - All caps, 3–10 chars, no digits, no spaces  →  likely a study acronym
#   - OR "WORD-WORD" pattern (e.g. DUET-CD, ATLAS-UC)
import re as _re
_STUDY_ACRONYM_RE = _re.compile(r'^[A-Z]{3,10}(-[A-Z0-9]{1,5})?$')

# INN suffix patterns — real brand names typically end in recognisable suffixes
# or contain mixed case / digits. Study acronyms are pure uppercase short words.
_INN_SUFFIX_RE = _re.compile(
    r'(mab|zumab|lumab|tinib|rafenib|lizumab|kibart|figast|lixizumab'
    r'|setamab|tilimab|golimab|pegol|cept|ximab|mumab|umab|inib|afil'
    r'|oxib|vastatin|prazole|sartan|parin|tinib|ciclib|sidenib|degib'
    r'|nib$|mab$|bix$|zib$)', _re.IGNORECASE
)


def validate_drug_brand_name(drug_id: str, brand_name: str) -> list[str]:
    """
    Validate that a drug's brand_name field contains an actual trade name,
    not a study acronym or trial name.

    Returns a list of warning strings (empty = clean).
    """
    warnings = []
    if not brand_name:
        return warnings

    bn = brand_name.strip()

    # Skip validation for confirmed legitimate brand names that look like acronyms
    if bn.upper() in {b.upper() for b in KNOWN_BRAND_NAMES}:
        return warnings

    # Check against known acronym list (case-insensitive)
    if bn.upper() in {a.upper() for a in KNOWN_STUDY_ACRONYMS}:
        warnings.append(
            f"[brand_name] '{bn}' on drug '{drug_id}' matches a known study acronym. "
            f"Study acronyms belong in trial_names or study_acronym on the trial record, "
            f"not in brand_name."
        )

    # Check regex: all-caps 3–10 char word (no INN suffix) → likely acronym
    if _STUDY_ACRONYM_RE.match(bn) and not _INN_SUFFIX_RE.search(bn):
        warnings.append(
            f"[brand_name] '{bn}' on drug '{drug_id}' looks like a study acronym "
            f"(all-caps, short, no INN suffix). Verify this is an actual trade name."
        )

    return warnings


def validate_trial_study_acronym(nct_id: str, study_acronym: str, trial_name: str) -> list[str]:
    """
    Validate that the study_acronym field contains an actual protocol acronym,
    not a full study title or misplaced value.

    CT.gov brief titles (trial_name) typically do NOT include the protocol
    name/acronym — checking for its presence there produces only false positives.
    Instead we flag things that clearly should not be in the acronym field:
      - Full sentences (> 40 chars) — likely a title was pasted into this field
      - An NCT or registry ID — registry IDs belong in id/nct_id, not here
      - A study_type value ('Interventional') that was mistakenly stored here
    """
    warnings = []
    if not study_acronym:
        return warnings

    acr = study_acronym.strip()

    # Flag if it looks like a full sentence pasted into the acronym field
    if len(acr) > 40:
        warnings.append(
            f"[study_acronym] trial '{nct_id}': study_acronym is unusually long "
            f"({len(acr)} chars): '{acr[:60]}...'. Should be a short protocol code."
        )

    # Flag if an NCT ID or registry number ended up here
    if re.match(r'^NCT\d{8}$', acr) or re.match(r'^ACTRN\d+', acr, re.I):
        warnings.append(
            f"[study_acronym] trial '{nct_id}': study_acronym='{acr}' looks like "
            f"a registry ID, not a protocol name."
        )

    # Flag if a study_type value was mistakenly stored in the acronym field
    if acr.lower() in ("interventional", "observational", "expanded access"):
        warnings.append(
            f"[study_acronym] trial '{nct_id}': study_acronym='{acr}' is a study "
            f"type, not a protocol acronym — field was likely populated from the "
            f"wrong CT.gov attribute."
        )

    return warnings


def validate_drug_field_consistency(drug: dict) -> list[str]:
    """
    Check for internal contradictions between drug fields:
      - target says bispecific (×) but drug_format says mAb (monospecific)
      - mechanism says bispecific but target is a single gene
      - drug_format says bispecific but target has no × separator
    Returns list of warning strings (empty = clean).
    """
    import re as _re2
    warnings = []
    did      = drug.get("id", "")
    target   = drug.get("target") or ""
    mechanism = drug.get("mechanism") or ""
    drug_format = (drug.get("drug_format") or "").lower()
    is_combo = drug.get("is_combo") or drug.get("is_combination") or False

    if is_combo:
        return warnings  # combination drugs have intentional mixed fields

    is_target_bispecific  = "×" in target
    is_format_bispecific  = "bispecific" in drug_format or "trispecific" in drug_format
    is_format_mono        = drug_format in ("mab", "antibody") and not is_format_bispecific
    is_mechanism_bispecific = "bispecific" in mechanism.lower() or "trispecific" in mechanism.lower()
    is_mechanism_mono     = bool(_re2.search(r'\banti-\w+\s+m[Aa][Bb]\b', mechanism)) and not is_mechanism_bispecific

    if is_target_bispecific and is_format_mono:
        warnings.append(
            f"[field_conflict] drug '{did}': target='{target}' implies bispecific "
            f"but drug_format='{drug_format}' implies monospecific."
        )

    if is_target_bispecific and is_mechanism_mono:
        warnings.append(
            f"[field_conflict] drug '{did}': target='{target}' implies bispecific "
            f"but mechanism='{mechanism[:60]}' implies monospecific."
        )

    if is_format_bispecific and target and "×" not in target and "/" not in target:
        warnings.append(
            f"[field_conflict] drug '{did}': drug_format='{drug_format}' but "
            f"target='{target}' has no bispecific separator (× or /). "
            f"Check whether target field is complete."
        )

    if is_mechanism_bispecific and target and "×" not in target and "/" not in target and target:
        warnings.append(
            f"[field_conflict] drug '{did}': mechanism implies bispecific "
            f"but target='{target}' shows only one target. Add second target to target field."
        )

    return warnings


def run_field_validation(dry_run: bool = False) -> dict:
    """
    Scan all drugs and trials in Supabase for field semantic violations.

    After each check, results are written to drug_validation_results and
    a validation_summary JSONB is updated on each drug row.  This makes
    validation state queryable in Supabase rather than buried in CI logs.

    Returns: {"drug_warnings": [...], "trial_warnings": [...]}
    """
    drug_warnings  = []
    trial_warnings = []

    # ── Fetch drugs for brand_name + field_consistency + stage_trial_match ──
    r = sb_get("drugs", {
        "select": ("id,name,brand_name,target,mechanism,drug_format,"
                   "is_combo,is_combination,stage,trial_data_status"),
    })

    # Build drug -> trial_count from trials table (one query, not N)
    trial_rows = sb_get("trials", {"select": "drug_id"})
    trial_counts: dict[str, int] = {}
    for t in trial_rows:
        did = t.get("drug_id") or ""
        if did:
            trial_counts[did] = trial_counts.get(did, 0) + 1

    dvr_rows: list[dict] = []   # rows to upsert into drug_validation_results

    for drug in r:
        did   = drug["id"]
        stage = drug.get("stage") or ""
        n_trials = trial_counts.get(did, 0)

        # Check 1: brand_name semantic validity
        w1 = validate_drug_brand_name(did, drug.get("brand_name") or "")
        bn_status = "fail" if w1 else "pass"
        if w1:
            drug_warnings.extend(w1)
            for msg in w1:
                log(f"⚠ VALIDATION [brand_name]: {msg}")

        # Check 2: target/mechanism/drug_format internal consistency
        w2 = validate_drug_field_consistency(drug)
        fc_status = "warning" if w2 else "pass"
        if w2:
            drug_warnings.extend(w2)
            for msg in w2:
                log(f"⚠ VALIDATION [field_consistency]: {msg}")

        # Check 3: stage vs trial data
        w3: list[str] = []
        clinical_stages = {"Phase 1","Phase 2","Phase 3","Phase 1/2","Phase 2/3"}
        if stage in clinical_stages and n_trials == 0:
            w3.append(
                f"[stage_trial_match] drug '{did}': stage='{stage}' "
                f"but 0 CT.gov trials found"
            )
        st_status = "warning" if w3 else "pass"
        if w3:
            drug_warnings.extend(w3)
            for msg in w3:
                log(f"⚠ VALIDATION [stage_trial_match]: {msg}")

        if not dry_run:
            all_statuses = [bn_status, fc_status, st_status]
            overall = "fail" if "fail" in all_statuses else ("warning" if "warning" in all_statuses else "pass")
            for check_type, status, warns in [
                ("brand_name",        bn_status, w1),
                ("field_consistency", fc_status, w2),
                ("stage_trial_match", st_status, w3),
            ]:
                dvr_rows.append({
                    "drug_id":      did,
                    "check_type":   check_type,
                    "check_status": status,
                    "confidence":   "inferred",
                    "verified_by":  "ct_gov_sync",
                    "verified_at":  NOW_ISO,
                    "details":      {"warnings": warns, "trial_count": n_trials},
                    "updated_at":   NOW_ISO,
                })
            # Update validation_summary on drug row (fast dashboard display)
            sb_patch("drugs",
                     {"validation_summary": {
                         "overall":            overall,
                         "brand_name":         bn_status,
                         "field_consistency":  fc_status,
                         "stage_trial_match":  st_status,
                         "last_validated_at":  NOW_ISO,
                     }},
                     {"id": f"eq.{did}"})

    # ── Validate trials.study_acronym vs trial_name ──────────────────────
    r2 = sb_get("trials", {"select": "id,drug_id,study_acronym,trial_name"})
    for trial in r2:
        w = validate_trial_study_acronym(
            trial["id"],
            trial.get("study_acronym") or "",
            trial.get("trial_name") or ""
        )
        if w:
            trial_warnings.extend(w)
            for msg in w:
                log(f"⚠ VALIDATION [study_acronym]: {msg}")

    # ── Write all drug_validation_results in one pass ────────────────────
    if dvr_rows and not dry_run:
        # Normalize all rows to identical key set (PostgREST batch requirement)
        all_keys = sorted({k for row in dvr_rows for k in row.keys()})
        normalized = [{k: row.get(k) for k in all_keys} for row in dvr_rows]
        for i in range(0, len(normalized), 200):
            sb_upsert("drug_validation_results", normalized[i:i+200],
                      on_conflict="drug_id,check_type")
        log(f"  → Wrote {len(normalized)} validation results to drug_validation_results")

    log(f"Field validation complete: {len(drug_warnings)} drug warnings, "
        f"{len(trial_warnings)} trial warnings")
    return {"drug_warnings": drug_warnings, "trial_warnings": trial_warnings}


def update_trial_registries(drug_id: str, synced_ncts: list[str],
                             dry_run: bool = False) -> None:
    """
    Update trial_registries.ct_gov row after a drug is synced.
    Called from sync_drug() so the table stays current after every run.
    """
    if dry_run:
        return
    status = "found" if synced_ncts else "not_found"
    row = {
        "drug_id":          drug_id,
        "registry_name":    "ct_gov",
        "registry_id":      None,
        "registry_url":     None,
        "search_status":    status,
        "trial_count":      len(synced_ncts),
        "last_searched_at": NOW_ISO,
        "verified_by":      "ct_gov_sync",
        "notes":            (f"{len(synced_ncts)} trial(s) found" if synced_ncts
                             else "Searched; no trials found on CT.gov"),
        "updated_at":       NOW_ISO,
    }
    sb_upsert("trial_registries", [row], on_conflict="drug_id,registry_name")


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


def sb_upsert(table: str, records: list | dict,
              on_conflict: str | None = None) -> list:
    """
    Upsert records into a Supabase table.

    on_conflict: comma-separated column names for conflict target (e.g.
    'drug_id,check_type'). Required when the table has a non-PK unique
    constraint that should drive ON CONFLICT resolution. If omitted,
    PostgREST defaults to the primary key.
    """
    if isinstance(records, dict):
        records = [records]
    if not records:
        return []
    url    = f"{SUPABASE_URL}/rest/v1/{table}"
    params = {"on_conflict": on_conflict} if on_conflict else {}
    try:
        r = requests.post(url, headers=SB_UPSERT_HEADERS,
                          params=params, json=records, timeout=15)
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

    # Study acronym: the branded program name companies give their trials
    # e.g. "SKYLINE-UC" (Spyre), "U-ACHIEVE" (AbbVie), "PURSUIT" (J&J)
    # Lives in identificationModule.acronym on CT.gov
    study_acronym = id_mod.get("acronym") or None

    return {
        "id":                    nct_id,
        "drug_id":               drug_id,
        "entity_id":             entity_id,
        "trial_name":            id_mod.get("briefTitle", "")[:300],
        "study_acronym":         study_acronym,
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
      →  0  (hard zero) if drug name does not appear in interventions OR title
             This prevents false positives where CT.gov returns trials for
             similarly-named compounds or multi-arm studies. A trial that
             doesn't mention our drug anywhere cannot be a valid match.
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

    # HARD GATE: drug name must appear in either interventions or title.
    # A trial that doesn't mention our drug anywhere is a false positive —
    # score it 0 immediately rather than accumulating partial credit.
    # This prevents misassignment of multi-arm trials with similar drug names.
    name_in_interventions = name_lc in interventions or any(
        part in interventions for part in name_lc.split() if len(part) > 5
    )
    name_in_title = name_lc in title or any(
        part in title for part in name_lc.split() if len(part) > 5
    )
    if not name_in_interventions and not name_in_title:
        return 0   # hard zero — not our drug

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
