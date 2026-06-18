#!/usr/bin/env python3
"""
CT.gov trial sync + company context fetch (§3 company_enrichment split).
========================================================================
Extracted verbatim from company_enrichment.py.

  - _pre_sync_trials_from_ctgov / _refresh_existing_trials_from_ctgov: search/refresh
    ClinicalTrials.gov by drug name or NCT and upsert the trials table (Step 3 backfill).
  - fetch_company_context: pulls all existing Supabase data for a company into the ctx
    dict consumed by Step 5.

Overlaps ct_gov_sync.py — a future pass can share the ctgov fetch/map modules. Self-
contained; calls no other company/* feature module.
"""

import datetime

import requests

from meridian.enrichment.company.common import NOW_ISO, log, sb_get, sb_upsert


# ══════════════════════════════════════════════════════════════════════════
# CONTEXT FETCH — pulls all existing Supabase data for a company
# (Step 3 trials are pre-populated by ct_gov_sync.py)
# ══════════════════════════════════════════════════════════════════════════

CT_GOV_BASE = "https://clinicaltrials.gov/api/v2"

def _pre_sync_trials_from_ctgov(drugs: list) -> int:
    """
    For each drug in `drugs`, search ClinicalTrials.gov by drug name and upsert
    any found trials into the trials table.  Returns the count of new rows inserted.
    Only runs for drugs that currently have zero trial rows — acts as a lightweight
    ct_gov_sync substitute so the enrichment step is self-contained.
    """
    import time as _time

    STATUS_MAP = {
        "RECRUITING":              "Recruiting",
        "ACTIVE_NOT_RECRUITING":   "Active, not recruiting",
        "COMPLETED":               "Completed",
        "NOT_YET_RECRUITING":      "Not yet recruiting",
        "ENROLLING_BY_INVITATION": "Enrolling by invitation",
        "TERMINATED":              "Terminated",
        "WITHDRAWN":               "Withdrawn",
        "SUSPENDED":               "Suspended",
    }

    def _ctgov_search(drug_name: str, indication: str = None, max_results: int = 8) -> list:
        # Note: query.cond is intentionally omitted — our indication_short strings
        # (e.g. "UC · CD") use abbreviations CT.gov doesn't parse, which returns 0
        # results. The drug name intervention search is specific enough on its own.
        params = {"format": "json", "pageSize": max_results, "query.intr": drug_name}
        try:
            r = requests.get(f"{CT_GOV_BASE}/studies", params=params, timeout=20)
            if r.status_code == 200:
                return r.json().get("studies", [])
        except Exception as e:
            log(f"    CT.gov search error for '{drug_name}': {e}", indent=2)
        return []

    def _parse_study(study: dict, drug_id: str) -> dict | None:
        ps = study.get("protocolSection", {})
        id_mod  = ps.get("identificationModule", {})
        st_mod  = ps.get("statusModule", {})
        de_mod  = ps.get("designModule", {})
        co_mod  = ps.get("conditionsModule", {})

        nct_id = id_mod.get("nctId", "")
        if not nct_id.startswith("NCT"):
            return None

        raw_status = (st_mod.get("overallStatus") or "").upper()
        status = STATUS_MAP.get(raw_status, raw_status.replace("_", " ").title())

        phases = de_mod.get("phases", [])
        if phases:
            phase_str = " / ".join(p.replace("PHASE", "Phase ").replace("_", " ").strip() for p in phases)
        else:
            # No phases → use studyType to determine non-interventional label
            study_type = (de_mod.get("studyType") or "").upper()
            if study_type == "OBSERVATIONAL":
                phase_str = "Observational"
            elif study_type == "EXPANDED_ACCESS":
                phase_str = "Expanded Access"
            else:
                phase_str = None

        pcd_struct = st_mod.get("primaryCompletionDateStruct", {})
        pcd = pcd_struct.get("date") or None  # YYYY-MM-DD or YYYY-MM

        conditions = co_mod.get("conditions", [])
        indication = " · ".join(conditions[:3]) if conditions else None

        return {
            "id":                     nct_id,
            "drug_id":                drug_id,
            "trial_name":             (id_mod.get("briefTitle") or "")[:300] or None,
            "study_acronym":          id_mod.get("acronym") or None,
            "phase":                  phase_str,
            "status":                 status,
            "indication":             indication[:200] if indication else None,
            "primary_completion_date": pcd,
            "source_url":             f"https://clinicaltrials.gov/study/{nct_id}",
            "last_synced_date":       NOW_ISO,
            "discovery_status":       "auto",
        }

    total_new = 0
    for drug in drugs:
        drug_id   = drug["id"]
        drug_name = drug.get("name") or drug_id
        indication = drug.get("indication_short") or None

        log(f"    CT.gov pre-sync: '{drug_name}' ({drug_id})", indent=2)
        studies = _ctgov_search(drug_name, indication=indication)

        inserted = 0
        for study in studies:
            rec = _parse_study(study, drug_id)
            if not rec:
                continue
            # Skip trials that already exist
            existing = sb_get("trials", {"id": f"eq.{rec['id']}", "select": "id"})
            if existing:
                continue
            rec_clean = {k: v for k, v in rec.items() if v is not None}
            result = sb_upsert("trials", rec_clean)
            if result:
                log(f"      ✓ {rec['id']} | {rec.get('phase','?')} | {rec.get('status','?')}", indent=3)
                inserted += 1
            _time.sleep(0.3)

        if not inserted:
            log(f"      no new trials found", indent=3)
        total_new += inserted

    return total_new


def _refresh_existing_trials_from_ctgov(trials: list) -> int:
    """
    For each trial row that already exists in the DB, re-fetch its CT.gov record
    directly by NCT ID and upsert the latest status, phase, PCD, and acronym.
    Returns the count of successfully refreshed rows.
    """
    import time as _time

    STATUS_MAP = {
        "RECRUITING":              "Recruiting",
        "ACTIVE_NOT_RECRUITING":   "Active, not recruiting",
        "COMPLETED":               "Completed",
        "NOT_YET_RECRUITING":      "Not yet recruiting",
        "ENROLLING_BY_INVITATION": "Enrolling by invitation",
        "TERMINATED":              "Terminated",
        "WITHDRAWN":               "Withdrawn",
        "SUSPENDED":               "Suspended",
    }

    def _fetch_study(nct_id: str) -> dict | None:
        try:
            r = requests.get(f"{CT_GOV_BASE}/studies/{nct_id}", params={"format": "json"}, timeout=20)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            log(f"    CT.gov fetch error for {nct_id}: {e}", indent=3)
        return None

    refreshed = 0
    for trial in trials:
        nct_id  = (trial.get("id") or "").strip()
        drug_id = (trial.get("drug_id") or "").strip()
        if not nct_id.startswith("NCT") or not drug_id:
            continue

        study = _fetch_study(nct_id)
        if not study:
            log(f"      ✗ {nct_id} — not found on CT.gov", indent=3)
            _time.sleep(0.2)
            continue

        ps     = study.get("protocolSection", {})
        id_mod = ps.get("identificationModule", {})
        st_mod = ps.get("statusModule", {})
        de_mod = ps.get("designModule", {})
        co_mod = ps.get("conditionsModule", {})
        en_mod = ps.get("designModule", {}).get("enrollmentInfo", {}) or {}

        raw_status = (st_mod.get("overallStatus") or "").upper()
        status = STATUS_MAP.get(raw_status, raw_status.replace("_", " ").title())

        phases = de_mod.get("phases", [])
        if phases:
            phase_str = " / ".join(p.replace("PHASE", "Phase ").replace("_", " ").strip() for p in phases)
        else:
            study_type = (de_mod.get("studyType") or "").upper()
            if study_type == "OBSERVATIONAL":
                phase_str = "Observational"
            elif study_type == "EXPANDED_ACCESS":
                phase_str = "Expanded Access"
            else:
                phase_str = None

        pcd = (st_mod.get("primaryCompletionDateStruct", {}) or {}).get("date") or None

        conditions = co_mod.get("conditions", [])
        indication = " · ".join(conditions[:3]) if conditions else None

        n_enrollment = en_mod.get("count") or None  # integer enrollment count

        update_rec = {
            "id":                     nct_id,
            "drug_id":                drug_id,
            "status":                 status,
            "last_synced_date":       NOW_ISO,
        }
        if phase_str:
            update_rec["phase"] = phase_str
        if pcd:
            update_rec["primary_completion_date"] = pcd
        if indication:
            update_rec["indication"] = indication[:200]
        if id_mod.get("acronym"):
            update_rec["study_acronym"] = id_mod["acronym"]
        if n_enrollment is not None:
            update_rec["n_enrollment"] = n_enrollment
        update_rec["source_url"] = f"https://clinicaltrials.gov/study/{nct_id}"

        ok = sb_upsert("trials", update_rec)
        if ok:
            log(f"      ↻ {nct_id} | {status} | pcd={pcd or '—'}", indent=3)
            refreshed += 1
        else:
            log(f"      ✗ {nct_id} — upsert failed", indent=3)

        _time.sleep(0.25)

    return refreshed


def fetch_company_context(company_id: str, area_id: str,
                          skip_trial_refresh: bool = False) -> dict:
    """Pull all Supabase data for a company × area."""
    companies = sb_get("companies", {"id": f"eq.{company_id}", "select": "*"})
    company   = companies[0] if companies else {}

    profiles = sb_get("company_profiles", {
        "company_id": f"eq.{company_id}", "area_id": f"eq.{area_id}", "select": "*"
    })
    profile = profiles[0] if profiles else {}

    # Fetch the indication_group for this area (e.g. tl1a → 'ibd').
    # The frontend shows drugs tagged with the indication_group (broader IBD set),
    # not just the specific area. We must mirror this so the enrichment context
    # includes the same drugs the dashboard displays (e.g. risankizumab + upadacitinib
    # for AbbVie in the TL1A tab, even though they're tagged 'ibd' not 'tl1a').
    area_meta = sb_get("disease_areas", {"id": f"eq.{area_id}", "select": "indication_group"})
    indication_group = (area_meta[0].get("indication_group") if area_meta else None) or area_id
    fetch_areas = list({area_id, indication_group})  # deduplicate
    drug_area_rows = sb_get("drug_areas", {
        "area_id": f"in.({','.join(fetch_areas)})", "select": "drug_id"
    })
    area_drug_ids  = {r["drug_id"] for r in drug_area_rows}
    all_co_drugs   = sb_get("drugs", {"company_id": f"eq.{company_id}", "select": "*"})
    drugs = [d for d in all_co_drugs if d["id"] in area_drug_ids]

    # Trials: fetch existing rows, then pre-sync any drugs that have none
    trials = []
    for d in drugs:
        t_rows = sb_get("trials", {"drug_id": f"eq.{d['id']}", "select": "*"})
        trials.extend(t_rows)

    # ── Pre-sync missing trials via CT.gov API ────────────────────────────
    # For drugs with zero trial rows, search ClinicalTrials.gov directly and
    # upsert what we find so the TRIALS block Claude sees is already populated.
    drug_ids_with_trials = {t["drug_id"] for t in trials}
    drugs_needing_trials = [d for d in drugs if d["id"] not in drug_ids_with_trials]
    if drugs_needing_trials:
        log(f"  Pre-syncing CT.gov trials for {len(drugs_needing_trials)} drugs with no trial rows…")
        newly_synced = _pre_sync_trials_from_ctgov(drugs_needing_trials)
        if newly_synced:
            # Re-fetch trials so they appear in the TRIALS block sent to Claude
            for d in drugs_needing_trials:
                t_rows = sb_get("trials", {"drug_id": f"eq.{d['id']}", "select": "*"})
                trials.extend(t_rows)
            log(f"  Pre-sync complete — {newly_synced} new trial rows added")

    # ── Refresh existing trials via CT.gov direct fetch ───────────────────
    # For drugs that already have trial rows, re-fetch each NCT ID from CT.gov
    # so status, PCD, enrollment, and phase stay current.
    # Skip with --skip-trial-refresh for fast targeted enrichment runs.
    if trials and not skip_trial_refresh:
        log(f"  Refreshing {len(trials)} existing trial(s) from CT.gov…")
        refreshed = _refresh_existing_trials_from_ctgov(trials)
        log(f"  Refresh complete — {refreshed}/{len(trials)} trial(s) updated")
        # Re-fetch updated rows so Claude sees the latest values
        if refreshed:
            trials = []
            for d in drugs:
                t_rows = sb_get("trials", {"drug_id": f"eq.{d['id']}", "select": "*"})
                trials.extend(t_rows)
    elif trials and skip_trial_refresh:
        log(f"  Trial refresh skipped (--skip-trial-refresh flag set) — using {len(trials)} cached rows")

    ninety_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    intel_co   = sb_get("intel_companies", {"company_id": f"eq.{company_id}", "select": "intel_id"})
    recent_intel = []
    for row in intel_co[:10]:
        items = sb_get("intel", {
            "id": f"eq.{row['intel_id']}", "intel_date": f"gte.{ninety_ago}",
            "select": "intel_date,headline,body,source_url"
        })
        recent_intel.extend(items)

    catalysts = sb_get("catalysts", {
        "company_id": f"eq.{company_id}", "area_id": f"eq.{area_id}",
        "resolved": "eq.false", "select": "*", "order": "sort_date.asc"
    })

    deals = sb_get("deals", {
        "company_id": f"eq.{company_id}", "area_id": f"eq.{area_id}",
        "select": "*", "order": "deal_date.desc"
    })
    if not deals:
        co_name_prefix = (company.get("name") or "")[:12]
        if co_name_prefix:
            deals = sb_get("deals", {
                "area_id": f"eq.{area_id}",
                "or": f"(from_company.ilike.*{co_name_prefix}*,to_company.ilike.*{co_name_prefix}*)",
                "select": "*", "order": "deal_date.desc"
            })

    # Fetch ailux_positions for this area (or its indication_group) so enrichment can
    # classify every drug against Ailux's competitive anchor — without hardcoded rules.
    # Try area_id first (e.g. 'tl1a'), then indication_group (e.g. 'ibd') as fallback.
    ailux_pos = {}
    _pos_rows = sb_get("ailux_positions", {"area_id": f"eq.{area_id}", "select": "*"})
    if not _pos_rows and indication_group:
        _pos_rows = sb_get("ailux_positions", {"area_id": f"eq.{indication_group}", "select": "*"})
    if _pos_rows:
        ailux_pos = _pos_rows[0]

    return {
        "company": company, "profile": profile, "drugs": drugs,
        "trials": trials, "catalysts": catalysts, "deals": deals,
        "recent_intel": recent_intel, "ailux_pos": ailux_pos,
    }
