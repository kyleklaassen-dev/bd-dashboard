#!/usr/bin/env python3
"""
Pure CT.gov JSON → record mapping (§3 ct_gov_sync split): parse_ct_study,
_format_date_label, score_search_match. No I/O — the design's zero-risk seam.
"""

from typing import Optional

from meridian.ingestion.ctgov.common import CT_STATUS_MAP, CT_PHASE_MAP, NOW_ISO


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


