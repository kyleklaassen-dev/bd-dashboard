#!/usr/bin/env python3
"""
Ailux BD Platform — Cross-Table Conflict Detector
==================================================
Detects contradictions between the drugs table and related structured
tables. Does NOT automatically correct any scientific field. Every
conflict is written to drug_validation_results as 'needs_review' with
full context so a human or model session can evaluate and confirm.

Design principle: no table is assumed to be correct.
When two tables disagree, both values are recorded and the discrepancy
is described. The reviewer decides which (if either) is right.

CHECKS:
  target_consistency
    drugs.target (free-text) vs drug_targets.target_id (structured).
    Runs only for drugs that already have drug_targets rows — absence
    of rows is a coverage gap, not a contradiction.

  indication_consistency
    drugs.indication_short (free-text) vs drug_indications + indications
    (structured). Same rule: only flags drugs that have drug_indications
    rows already.

  company_resolution
    drugs.company_display vs companies + company_aliases.
    Acquired-asset aware: drugs with acquired_asset=True are expected to
    use "Acquirer w/Acquired" display format and company_id=acquirer.
    Drugs still on an acquired company without acquired_asset=True are
    flagged as 'company_acquired_unhandled' (medium severity).
    "/" partnership notation (e.g. "Sanofi/Regeneron") is flagged as
    low severity only — these are deliberate co-development displays.

SEVERITY:
  high   — target or mechanism conflict between structured tables
  medium — company attribution conflict; indication mismatch
  low    — name/formatting inconsistency only

PRIORITY ORDER (for review queue):
  1: high severity   + confidence='inferred'
  2: medium severity + confidence='inferred'
  3: high severity   + confidence='confirmed' or 'supported'
  4: medium severity + confidence='confirmed' or 'supported'
  5: low severity    (any confidence)

OUTPUTS:
  drug_validation_results — one row per (drug, check_type) with
    check_status='needs_review' and full conflict detail in details JSONB
  stdout — formatted priority queue for immediate session review

USAGE:
  python scripts/conflict_detector.py              # all drugs
  python scripts/conflict_detector.py --drug spy001
  python scripts/conflict_detector.py --dry-run    # detect only, no DB writes

ENVIRONMENT:
  SUPABASE_URL         — https://tghntyofptvfhmtchwcv.supabase.co
  SUPABASE_SERVICE_KEY — service role key
"""

import os
import re
import sys
import json
import datetime
import argparse
import requests
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════════════
# CREDENTIALS + CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
TODAY        = datetime.datetime.utcnow().strftime("%Y-%m-%d")
NOW_ISO      = datetime.datetime.utcnow().isoformat()

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}
SB_UPSERT_HEADERS = {
    **SB_HEADERS,
    "Prefer": "resolution=merge-duplicates,return=minimal",
}

# ─── Target ID normalization ─────────────────────────────────────────
# Maps free-text variations that appear in drugs.target to the canonical
# target_id used in drug_targets. Add entries as new targets are added.
TARGET_TEXT_TO_ID: dict[str, str] = {
    "tl1a":          "tl1a",
    "tnfsf15":       "tl1a",
    "tslp":          "tslp",
    "tslpr":         "tslpr",
    "il4ra":         "il4ra",
    "il4r":          "il4ra",
    "il-4ra":        "il4ra",
    "il-4r":         "il4ra",
    "fcrn":          "fcrn",
    "fcgrt":         "fcrn",
    "igf1r":         "igf1r",
    "igf-1r":        "igf1r",
    "tshr":          "tshr",
    "il23p19":       "il23p19",
    "il-23p19":      "il23p19",
    "il23p40":       "il12_23p40",   # IL-23p40 and IL-12/23p40 are the same subunit
    "il-23p40":      "il12_23p40",
    "il1223p40":     "il12_23p40",
    "il12/23p40":    "il12_23p40",
    "il12_23p40":    "il12_23p40",
    "cd19":          "cd19",
    "cd20":          "cd20",
    "cd3":           "cd3",
    "cd38":          "cd38",
    "cd40":          "cd40",
    "a4b7":          "a4b7",
    "a4b7integrin":  "a4b7",
    "baff":          "baff",
    "baffr":         "baffr",
    "bcma":          "bcma",
    "ige":           "ige",
    "il13":          "il13",
    "il17a":         "il17a",
    "il17af":        "il17af",
    "il1ab":         "il1ab",
    "il1a":          "il1ab",
    "il1b":          "il1ab",
    "il31ra":        "il31ra",
    "il33":          "il33",
    "il5ra":         "il5ra",
    "il5r":          "il5ra",
    "il6r":          "il6r",
    "jak1":          "jak1",
    "ox40l":         "ox40l",
    "pd1":           "pd1",
    "pdl1":          "pdl1",
    "ripk1":         "ripk1",
    "tnf":           "tnf",
    "tnfa":          "tnf",
    "vegf":          "vegf",
    "ifnar1":        "ifnar1",
    "ifnar":         "ifnar1",
    "gprc5d":        "gprc5d",
    "epcam":         "epcam",
}

SKIP_TARGETS = {"—", "n/a", "unknown", "multiple", "various", "combination"}


def canonical_target(text: str) -> str:
    """
    Normalise a target text fragment to a lookup key for TARGET_TEXT_TO_ID.
    Converts to lowercase, strips Greek letters, removes punctuation.
    """
    t = text.strip().lower()
    # Greek → ASCII
    for greek, asc in [("α","a"),("β","b"),("γ","g"),("δ","d"),("ε","e"),("ζ","z")]:
        t = t.replace(greek, asc)
    # Remove common suffixes that aren't part of the gene name
    t = re.sub(r'\s*(inhibitor|antibody|mab|antagonist|bispecific|trispecific|integrin)\s*$', '', t)
    # Strip separators
    t = re.sub(r'[\s\-_/]', '', t)
    return t


def parse_target_field(target_str: str) -> list[str]:
    """
    Split drugs.target into individual target tokens.
    Handles: '×', '/', ' and ', ' + ', '·', ','
    Returns canonical forms.
    """
    if not target_str:
        return []
    t = target_str.strip()
    if t.lower() in SKIP_TARGETS:
        return []
    # Split on bispecific/multi-target separators
    parts = re.split(r'[×x/·,]|\band\b|\bplus\b|\+', t, flags=re.IGNORECASE)
    tokens = []
    for part in parts:
        c = canonical_target(part.strip())
        if c and len(c) > 1:
            tokens.append(c)
    return tokens


def target_tokens_match(drugs_token: str, target_id: str) -> bool:
    """
    Return True if a drugs.target token matches a drug_targets.target_id.
    Uses the normalisation map, then falls back to substring / equality.
    """
    # Direct map lookup
    mapped = TARGET_TEXT_TO_ID.get(drugs_token)
    if mapped == target_id:
        return True
    # Exact canonical match
    if drugs_token == target_id:
        return True
    # Substring: "il4ra" in "il4ra" or target_id starts/ends with the token
    if drugs_token in target_id or target_id in drugs_token:
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# SUPABASE HELPERS
# ═══════════════════════════════════════════════════════════════════════

def sb_get(table: str, params: dict) -> list:
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=SB_HEADERS,
            params={**params, "limit": "2000"},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"[sb_get {table}] {e}")
        return []


def sb_upsert(table: str, records: list | dict,
              on_conflict: str | None = None) -> bool:
    if isinstance(records, dict):
        records = [records]
    if not records:
        return True
    all_keys   = sorted({k for r in records for k in r.keys()})
    normalized = [{k: r.get(k) for k in all_keys} for r in records]
    params     = {"on_conflict": on_conflict} if on_conflict else {}
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=SB_UPSERT_HEADERS,
            params=params,
            json=normalized,
            timeout=20,
        )
        if r.status_code not in (200, 201):
            log(f"[sb_upsert {table}] {r.status_code}: {r.text[:200]}")
            return False
        return True
    except Exception as e:
        log(f"[sb_upsert {table}] {e}")
        return False


def sb_patch(table: str, record: dict, match_params: dict) -> bool:
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=SB_HEADERS,
            params=match_params,
            json=record,
            timeout=20,
        )
        return r.status_code in (200, 204)
    except Exception as e:
        log(f"[sb_patch {table}] {e}")
        return False


def log(msg: str, indent: int = 0):
    ts     = datetime.datetime.utcnow().strftime("%H:%M:%S")
    prefix = "  " * indent
    print(f"[conflict_detector {ts}] {prefix}{msg}", flush=True)


# ═══════════════════════════════════════════════════════════════════════
# PRIORITY SCORING
# ═══════════════════════════════════════════════════════════════════════

SEVERITY_SCORE = {"high": 3, "medium": 2, "low": 1}

def review_priority(severity: str, confidence_level: str) -> int:
    """
    Return integer priority 1–5.
    Lower number = review first.
      1: high    + inferred
      2: medium  + inferred
      3: high    + confirmed/supported
      4: medium  + confirmed/supported
      5: low     (any)
    """
    if severity == "low":
        return 5
    is_inferred = (confidence_level or "").lower() == "inferred"
    if severity == "high":
        return 1 if is_inferred else 3
    if severity == "medium":
        return 2 if is_inferred else 4
    return 5


def make_conflict_record(drug_id: str, check_type: str, severity: str,
                          conflict_type: str, drugs_value, related_table: str,
                          related_value, discrepancy: str, confidence_level: str,
                          suggested_action: str, source_needed: str) -> dict:
    priority = review_priority(severity, confidence_level)
    return {
        "drug_id":      drug_id,
        "check_type":   check_type,
        "check_status": "needs_review",
        "confidence":   confidence_level or "inferred",
        "verified_by":  "conflict_detector",
        "verified_at":  NOW_ISO,
        "details": {
            "severity":          severity,
            "conflict_type":     conflict_type,
            "drugs_table_value": drugs_value,
            "related_table":     related_table,
            "related_value":     related_value,
            "discrepancy":       discrepancy,
            "confidence_level":  confidence_level,
            "review_priority":   priority,
            "suggested_action":  suggested_action,
            "source_needed":     source_needed,
            "detected_on":       TODAY,
        },
        "notes":        discrepancy,
        "updated_at":   NOW_ISO,
    }


# ═══════════════════════════════════════════════════════════════════════
# CHECK 1 — TARGET CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════

def check_target_consistency(drug: dict,
                              drug_targets_by_id: dict[str, list]) -> dict | None:
    """
    Compare drugs.target (free-text) against drug_targets rows (structured).

    Only runs if the drug HAS drug_targets rows — absence is a coverage gap,
    not a contradiction.

    Returns a conflict record dict, or None if clean.
    """
    did         = drug["id"]
    drugs_target = drug.get("target") or ""
    confidence  = drug.get("confidence_level") or "inferred"

    dt_rows = drug_targets_by_id.get(did, [])
    if not dt_rows:
        return None  # No structured data to contradict — skip

    structured_ids = {r["target_id"] for r in dt_rows}

    # If drugs.target is empty but structured rows exist → flag
    if not drugs_target or drugs_target.strip().lower() in SKIP_TARGETS:
        return make_conflict_record(
            drug_id        = did,
            check_type     = "target_consistency",
            severity       = "high",
            conflict_type  = "target_field_empty_but_structured_rows_exist",
            drugs_value    = drugs_target or "(null)",
            related_table  = "drug_targets",
            related_value  = sorted(structured_ids),
            discrepancy    = (f"drugs.target is empty/null but drug_targets has "
                              f"{len(dt_rows)} row(s): {sorted(structured_ids)}. "
                              f"One source has data the other lacks."),
            confidence_level = confidence,
            suggested_action = "Verify which targets are correct against company pipeline or CT.gov, then populate both fields consistently.",
            source_needed    = "Company IR page, ClinicalTrials.gov, press release",
        )

    # Parse drugs.target into canonical tokens
    drugs_tokens = parse_target_field(drugs_target)
    if not drugs_tokens:
        return None  # Can't parse — not enough signal to flag

    # Check 1a: any drug_targets.target_id not represented in drugs.target
    unmatched_structured = []
    for sid in sorted(structured_ids):
        matched = any(target_tokens_match(tok, sid) for tok in drugs_tokens)
        if not matched:
            unmatched_structured.append(sid)

    # Check 1b: any drugs.target token not represented in drug_targets
    unmatched_in_drugs = []
    for tok in drugs_tokens:
        matched = any(target_tokens_match(tok, sid) for sid in structured_ids)
        if not matched:
            unmatched_in_drugs.append(tok)

    if not unmatched_structured and not unmatched_in_drugs:
        return None  # Clean — both sides agree

    # Build discrepancy description
    parts = []
    if unmatched_structured:
        parts.append(
            f"drug_targets has target_id(s) {unmatched_structured} not found in "
            f"drugs.target='{drugs_target}'"
        )
    if unmatched_in_drugs:
        parts.append(
            f"drugs.target token(s) {unmatched_in_drugs} not matched in "
            f"drug_targets rows {sorted(structured_ids)}"
        )
    discrepancy = "; ".join(parts)

    # Severity: any unmatched structured target → high (direct contradiction)
    # Only unmatched drugs.target token → could be bispecific arm not yet extracted → medium
    severity = "high" if unmatched_structured else "medium"

    return make_conflict_record(
        drug_id        = did,
        check_type     = "target_consistency",
        severity       = severity,
        conflict_type  = "target_mismatch",
        drugs_value    = drugs_target,
        related_table  = "drug_targets",
        related_value  = sorted(structured_ids),
        discrepancy    = discrepancy,
        confidence_level = confidence,
        suggested_action = ("Verify the correct target(s) against company pipeline page "
                            "or ClinicalTrials.gov interventions. Update whichever "
                            "source is wrong — do not assume either is correct."),
        source_needed  = "Company IR page, ClinicalTrials.gov, FDA label (if approved)",
    )


# ═══════════════════════════════════════════════════════════════════════
# CHECK 2 — INDICATION CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════

def check_indication_consistency(drug: dict,
                                  drug_indications_by_id: dict[str, list],
                                  indication_abbrevs: dict[str, str]) -> dict | None:
    """
    Compare drugs.indication_short (free-text) against drug_indications rows.
    Only runs if the drug has drug_indications rows.
    """
    did          = drug["id"]
    ind_short    = drug.get("indication_short") or ""
    confidence   = drug.get("confidence_level") or "inferred"

    di_rows = drug_indications_by_id.get(did, [])
    if not di_rows:
        return None  # No structured rows — skip

    structured_inds = {r["indication_id"] for r in di_rows}

    if not ind_short or ind_short.strip().lower() in ("—", "n/a", "unknown"):
        return make_conflict_record(
            drug_id        = did,
            check_type     = "indication_consistency",
            severity       = "medium",
            conflict_type  = "indication_field_empty_but_structured_rows_exist",
            drugs_value    = ind_short or "(null)",
            related_table  = "drug_indications",
            related_value  = sorted(structured_inds),
            discrepancy    = (f"drugs.indication_short is empty but drug_indications "
                              f"has rows: {sorted(structured_inds)}"),
            confidence_level = confidence,
            suggested_action = "Populate drugs.indication_short to match the structured drug_indications rows, or verify the structured rows are correct.",
            source_needed    = "ClinicalTrials.gov, company pipeline page",
        )

    # Normalize indication_short for loose matching
    ind_short_lower = ind_short.lower()
    # Normalise punctuation for substring search
    ind_short_norm = re.sub(r'[_\-/·;,()\s]+', ' ', ind_short_lower).strip()

    # For each structured indication, check if its abbreviation or id appears
    # as a substring in the indication_short text. Substring search (not token
    # split) handles multi-word names like "multiple myeloma" inside
    # "R/R multiple myeloma".
    unmatched_structured = []
    for ind_id in sorted(structured_inds):
        abbrev   = (indication_abbrevs.get(ind_id) or ind_id).lower()
        # Also normalise the indication id (underscores → spaces)
        id_norm  = ind_id.lower().replace('_', ' ')
        abbrev_norm = abbrev.replace('_', ' ')
        found = (
            id_norm       in ind_short_norm or
            abbrev_norm   in ind_short_norm or
            # Allow abbreviation appearing as uppercase in original (e.g. "UC", "TED")
            abbrev.upper() in ind_short
        )
        if not found:
            unmatched_structured.append(ind_id)

    if not unmatched_structured:
        return None  # All structured indications represented in the text

    return make_conflict_record(
        drug_id        = did,
        check_type     = "indication_consistency",
        severity       = "medium",
        conflict_type  = "indication_mismatch",
        drugs_value    = ind_short,
        related_table  = "drug_indications",
        related_value  = sorted(structured_inds),
        discrepancy    = (f"drug_indications has indication(s) {unmatched_structured} "
                          f"not represented in drugs.indication_short='{ind_short}'"),
        confidence_level = confidence,
        suggested_action = ("Verify which indications are correct. Update drugs.indication_short "
                            "or drug_indications rows — do not assume either is correct."),
        source_needed  = "ClinicalTrials.gov, company pipeline, press release",
    )


# ═══════════════════════════════════════════════════════════════════════
# CHECK 3 — COMPANY RESOLUTION
# ═══════════════════════════════════════════════════════════════════════

def check_company_resolution(drug: dict,
                              alias_to_company_id: dict[str, str],
                              company_by_id: dict[str, dict]) -> list[dict]:
    """
    Check drugs.company_display and drugs.company_id against companies table.
    Can return multiple conflict records (one per distinct issue found).

    Acquired-asset aware:
    - If acquired_asset=True, the drug has been reviewed per the acquired asset rule
      (company_id=acquirer, display='Acquirer w/Acquired', original_company_id=acquired).
      Skip the company_acquired sub-check; it is not a conflict.
    - If company_id points to an acquired company AND acquired_asset is NOT True,
      flag as medium: the acquired asset rule has not been applied yet.
    - Partnership "Acquirer w/Acquired" display format → not flagged as unresolvable
      when acquired_asset=True.
    - "/" partnership notation (e.g. "Sanofi/Regeneron") → LOW severity; these are
      deliberate co-development display names, not errors.
    """
    did             = drug["id"]
    company_display = drug.get("company_display") or ""
    company_id      = drug.get("company_id") or ""
    confidence      = drug.get("confidence_level") or "inferred"
    acquired_asset  = drug.get("acquired_asset") or False
    conflicts       = []

    display_lower = company_display.strip().lower()

    # ── Sub-check A: company_id points to an acquired company ─────────
    # Only flag if acquired_asset is NOT already set to True.
    # If acquired_asset=True, the rule has been applied; the drug now lives
    # under the acquirer, so company_id won't point to the acquired entity anyway.
    if company_id and company_id in company_by_id:
        co = company_by_id[company_id]
        if co.get("status") == "acquired" and co.get("acquired_by"):
            if not acquired_asset:
                # Acquired asset rule has NOT been applied — this is a real gap
                acquirer_name = (company_by_id.get(co["acquired_by"], {})
                                 .get("name", co["acquired_by"]))
                conflicts.append(make_conflict_record(
                    drug_id        = did,
                    check_type     = "company_resolution",
                    severity       = "medium",
                    conflict_type  = "company_acquired_unhandled",
                    drugs_value    = f"company_id='{company_id}' ({co['name']})",
                    related_table  = "companies",
                    related_value  = {
                        "status":        "acquired",
                        "acquired_by":   co["acquired_by"],
                        "acquirer_name": acquirer_name,
                    },
                    discrepancy    = (f"Drug is attributed to '{company_id}' ({co['name']}) "
                                      f"which has status='acquired' (by {co['acquired_by']} / "
                                      f"{acquirer_name}). Acquired asset rule has NOT been applied: "
                                      f"company_id should be '{co['acquired_by']}', acquired_asset "
                                      f"should be true, original_company_id='{company_id}'."),
                    confidence_level = confidence,
                    suggested_action = (
                        "Apply acquired asset rule: set company_id='" + co["acquired_by"] + "', "
                        "company_display='" + acquirer_name + " w/" + co["name"] + "', "
                        "original_company_id='" + company_id + "', acquired_asset=true, "
                        "attribution_note='Asset entered pipeline through acquisition "
                        "of " + co["name"] + "'."
                    ),
                    source_needed    = "Acquisition announcement, company IR page",
                ))
            # If acquired_asset=True, this is correctly handled — no conflict.

    # ── Sub-check B: does company_display resolve to a known company? ─
    if not company_display or display_lower in ("—", "n/a", "unknown", ""):
        return conflicts  # No display name to check

    # ── Partnership "Acquirer w/Acquired" format ──────────────────────
    # e.g. "UCB w/Candid", "Sanofi w/Kali", "Merck w/Prometheus"
    # When acquired_asset=True, this is the canonical format — not a conflict.
    if acquired_asset and " w/" in company_display.lower():
        # Verify the acquirer portion resolves correctly
        acquirer_part = company_display.split(" w/")[0].strip()
        resolved_acquirer = alias_to_company_id.get(acquirer_part.lower())
        if resolved_acquirer and resolved_acquirer == company_id:
            return conflicts  # Correctly formatted acquired asset — clean
        elif resolved_acquirer and resolved_acquirer != company_id:
            conflicts.append(make_conflict_record(
                drug_id        = did,
                check_type     = "company_resolution",
                severity       = "medium",
                conflict_type  = "company_id_display_mismatch",
                drugs_value    = {
                    "company_display": company_display,
                    "company_id":      company_id,
                },
                related_table  = "company_aliases",
                related_value  = {
                    "resolved_acquirer_from_display": resolved_acquirer,
                },
                discrepancy    = (f"Acquired-asset display '{company_display}' has acquirer "
                                  f"portion '{acquirer_part}' resolving to '{resolved_acquirer}', "
                                  f"but company_id='{company_id}'. These disagree."),
                confidence_level = confidence,
                suggested_action = ("Correct company_id to match the acquirer in company_display, "
                                    "or update company_display to reflect the correct acquirer."),
                source_needed    = "Acquisition announcement",
            ))
        return conflicts  # Either clean or already flagged above

    # ── "/" partnership display (e.g. "Roche/Genentech", "Sanofi/Regeneron") ─
    # These are deliberate co-development naming conventions — not typos.
    # Downgrade to LOW severity; just note the display name isn't in aliases.
    if "/" in company_display and not acquired_asset:
        resolved_id = alias_to_company_id.get(display_lower)
        if not resolved_id:
            # Check if the first part before "/" resolves
            primary_part = company_display.split("/")[0].strip()
            primary_resolved = alias_to_company_id.get(primary_part.lower())
            if primary_resolved and primary_resolved == company_id:
                return conflicts  # Primary part matches company_id — clean
            conflicts.append(make_conflict_record(
                drug_id        = did,
                check_type     = "company_resolution",
                severity       = "low",
                conflict_type  = "partnership_display_notation",
                drugs_value    = company_display,
                related_table  = "companies + company_aliases",
                related_value  = None,
                discrepancy    = (f"drugs.company_display='{company_display}' uses '/' partnership "
                                  f"notation which doesn't match a single alias entry. This may be "
                                  f"intentional for co-development partnerships."),
                confidence_level = confidence,
                suggested_action = ("Confirm this is an intentional co-development display name. "
                                    "If so, verify drugs.company_id correctly reflects primary "
                                    "development/commercial owner. Add an alias if this display "
                                    "name is used consistently."),
                source_needed    = "Company partnership announcement, press release",
            ))
        return conflicts

    # ── Standard resolution: does display match any alias? ───────────
    resolved_id = alias_to_company_id.get(display_lower)

    if not resolved_id:
        # Can't resolve — may be a new/unlisted company or a typo
        conflicts.append(make_conflict_record(
            drug_id        = did,
            check_type     = "company_resolution",
            severity       = "medium",
            conflict_type  = "company_unresolvable",
            drugs_value    = company_display,
            related_table  = "companies + company_aliases",
            related_value  = None,
            discrepancy    = (f"drugs.company_display='{company_display}' does not match "
                              f"any entry in company_aliases. Either a new company needs "
                              f"adding, or the display name has a typo."),
            confidence_level = confidence,
            suggested_action = ("Verify the correct company name, add it to company_aliases "
                                "if legitimate, or correct the typo in drugs.company_display."),
            source_needed    = "Company website, ClinicalTrials.gov sponsor field",
        ))
        return conflicts

    # ── Sub-check C: does resolved display match company_id? ─────────
    if company_id and resolved_id and resolved_id != company_id:
        conflicts.append(make_conflict_record(
            drug_id        = did,
            check_type     = "company_resolution",
            severity       = "medium",
            conflict_type  = "company_id_display_mismatch",
            drugs_value    = {
                "company_display":  company_display,
                "company_id":       company_id,
            },
            related_table  = "company_aliases",
            related_value  = {
                "resolved_company_id": resolved_id,
                "resolved_company_name": company_by_id.get(resolved_id, {}).get("name"),
            },
            discrepancy    = (f"drugs.company_display='{company_display}' resolves to "
                              f"company_id='{resolved_id}' via aliases, but drugs.company_id "
                              f"is set to '{company_id}'. These two fields disagree."),
            confidence_level = confidence,
            suggested_action = ("Determine which field is correct. Update drugs.company_id "
                                "to match the display name, or update the display name to "
                                "match company_id."),
            source_needed    = "Company website, acquisition history",
        ))

    return conflicts


# ═══════════════════════════════════════════════════════════════════════
# LOAD ALL REFERENCE DATA
# ═══════════════════════════════════════════════════════════════════════

def load_reference_data() -> dict:
    log("Loading reference data from Supabase...")

    # Drug_targets: group by drug_id
    dt_rows = sb_get("drug_targets", {"select": "drug_id,target_id,confidence_level,review_status"})
    drug_targets_by_id = defaultdict(list)
    for row in dt_rows:
        drug_targets_by_id[row["drug_id"]].append(row)

    # Drug_indications: group by drug_id
    di_rows = sb_get("drug_indications", {"select": "drug_id,indication_id,development_stage"})
    drug_indications_by_id = defaultdict(list)
    for row in di_rows:
        drug_indications_by_id[row["drug_id"]].append(row)

    # Indications: id → abbreviation
    ind_rows = sb_get("indications", {"select": "id,abbreviation"})
    indication_abbrevs = {r["id"]: r.get("abbreviation", r["id"]) for r in ind_rows}

    # Companies: id → full row
    co_rows = sb_get("companies", {"select": "id,name,status,acquired_by"})
    company_by_id = {r["id"]: r for r in co_rows}

    # Company aliases: alias_name.lower() → company_id
    alias_rows = sb_get("company_aliases", {"select": "company_id,alias_name"})
    alias_to_company_id = {}
    for row in alias_rows:
        alias_to_company_id[row["alias_name"].strip().lower()] = row["company_id"]
    # Also add company names directly
    for co in co_rows:
        alias_to_company_id[co["name"].strip().lower()] = co["id"]

    log(f"  drug_targets: {len(dt_rows)} rows across "
        f"{len(drug_targets_by_id)} drugs")
    log(f"  drug_indications: {len(di_rows)} rows across "
        f"{len(drug_indications_by_id)} drugs")
    log(f"  companies: {len(co_rows)} | aliases: {len(alias_rows)}")

    return {
        "drug_targets_by_id":      dict(drug_targets_by_id),
        "drug_indications_by_id":  dict(drug_indications_by_id),
        "indication_abbrevs":      indication_abbrevs,
        "company_by_id":           company_by_id,
        "alias_to_company_id":     alias_to_company_id,
    }


# ═══════════════════════════════════════════════════════════════════════
# MAIN DETECTION LOOP
# ═══════════════════════════════════════════════════════════════════════

def run(drug_filter: str = None, dry_run: bool = False):
    log("=" * 64)
    log(f"Cross-Table Conflict Detector — {TODAY}")
    log(f"Dry run: {dry_run} | Drug filter: {drug_filter or 'none'}")
    log("=" * 64)

    ref = load_reference_data()

    # Fetch all drugs
    drugs = sb_get("drugs", {
        "select": ("id,name,target,mechanism,indication_short,"
                   "company_display,company_id,confidence_level,drug_format,"
                   "acquired_asset,original_company_id"),
    })
    if drug_filter:
        drugs = [d for d in drugs
                 if drug_filter.lower() in d["id"].lower()
                 or drug_filter.lower() in (d.get("name") or "").lower()]
    log(f"Drugs to check: {len(drugs)}")

    all_conflicts: list[dict] = []

    for drug in drugs:
        did = drug["id"]

        # ── Check 1: target_consistency ────────────────────────────────
        c = check_target_consistency(drug, ref["drug_targets_by_id"])
        if c:
            all_conflicts.append(c)

        # ── Check 2: indication_consistency ───────────────────────────
        c = check_indication_consistency(
            drug,
            ref["drug_indications_by_id"],
            ref["indication_abbrevs"],
        )
        if c:
            all_conflicts.append(c)

        # ── Check 3: company_resolution ────────────────────────────────
        cc = check_company_resolution(
            drug,
            ref["alias_to_company_id"],
            ref["company_by_id"],
        )
        all_conflicts.extend(cc)

    # ── Clean run: mark drugs with no conflicts as 'pass' ─────────────
    conflict_drug_ids = {c["drug_id"] for c in all_conflicts}
    clean_drug_ids    = [d["id"] for d in drugs if d["id"] not in conflict_drug_ids]

    # ══════════════════════════════════════════════════════════════════
    # WRITE TO drug_validation_results
    # ══════════════════════════════════════════════════════════════════

    if not dry_run:
        # Write conflict records
        if all_conflicts:
            log(f"Writing {len(all_conflicts)} conflict records to drug_validation_results...")
            sb_upsert(
                "drug_validation_results",
                all_conflicts,
                on_conflict="drug_id,check_type",
            )

        # Write pass records for clean drugs (all three check types)
        pass_records = []
        for did in clean_drug_ids:
            for check_type in ("target_consistency", "indication_consistency", "company_resolution"):
                pass_records.append({
                    "drug_id":      did,
                    "check_type":   check_type,
                    "check_status": "pass",
                    "confidence":   "inferred",
                    "verified_by":  "conflict_detector",
                    "verified_at":  NOW_ISO,
                    "details":      {"detected_on": TODAY, "no_conflicts_found": True},
                    "updated_at":   NOW_ISO,
                })
        if pass_records:
            log(f"Writing {len(pass_records)} pass records for clean drugs...")
            for i in range(0, len(pass_records), 200):
                sb_upsert(
                    "drug_validation_results",
                    pass_records[i:i+200],
                    on_conflict="drug_id,check_type",
                )

        # Update validation_summary on each drug
        log("Refreshing validation_summary on drugs...")
        for drug in drugs:
            did = drug["id"]
            # Build summary from current drug_validation_results
            all_checks = sb_get("drug_validation_results", {
                "drug_id": f"eq.{did}",
                "select":  "check_type,check_status",
            })
            statuses = {r["check_type"]: r["check_status"] for r in all_checks}
            all_vals = list(statuses.values())
            overall  = (
                "fail"         if "fail"         in all_vals else
                "needs_review" if "needs_review" in all_vals else
                "warning"      if "warning"      in all_vals else "pass"
            )
            sb_patch("drugs",
                     {"validation_summary": {
                         **statuses,
                         "overall":           overall,
                         "last_validated_at": NOW_ISO,
                     }},
                     {"id": f"eq.{did}"})

    # ══════════════════════════════════════════════════════════════════
    # PRINT PRIORITIZED REVIEW QUEUE
    # ══════════════════════════════════════════════════════════════════

    print_review_queue(all_conflicts, drugs)


def print_review_queue(conflicts: list[dict], drugs: list[dict]):
    """Print a formatted, prioritised review queue to stdout."""

    if not conflicts:
        print("\n" + "=" * 64)
        print("NO CONFLICTS DETECTED — all checks clean.")
        print("=" * 64)
        return

    # Sort by review_priority then drug_id
    def sort_key(c):
        priority = c.get("details", {}).get("review_priority", 5)
        return (priority, c["drug_id"])

    sorted_conflicts = sorted(conflicts, key=sort_key)

    # Group by priority
    by_priority: dict[int, list] = defaultdict(list)
    for c in sorted_conflicts:
        p = c.get("details", {}).get("review_priority", 5)
        by_priority[p].append(c)

    priority_labels = {
        1: "HIGH severity / INFERRED confidence  ← fix first",
        2: "MEDIUM severity / INFERRED confidence",
        3: "HIGH severity / CONFIRMED or SUPPORTED confidence",
        4: "MEDIUM severity / CONFIRMED or SUPPORTED confidence",
        5: "LOW severity — formatting / naming",
    }

    total = len(sorted_conflicts)
    print("\n" + "=" * 64)
    print(f"CROSS-TABLE CONFLICT DETECTION REPORT — {TODAY}")
    print(f"Total conflicts detected: {total}")
    print("=" * 64)

    for p in sorted(by_priority.keys()):
        group = by_priority[p]
        label = priority_labels.get(p, f"Priority {p}")
        print(f"\n▸ PRIORITY {p}: {label}  ({len(group)} conflict(s))")
        print("-" * 64)

        for c in group:
            d        = c.get("details", {})
            severity = d.get("severity", "?").upper()
            ctype    = d.get("conflict_type", "?")
            conf     = d.get("confidence_level", "?")
            drug_val = d.get("drugs_table_value", "?")
            rel_val  = d.get("related_value", "?")
            disc     = d.get("discrepancy", "")
            action   = d.get("suggested_action", "")
            source   = d.get("source_needed", "")

            print(f"\n  [{severity}] {c['drug_id']}  ({c['check_type']} · {ctype})")
            print(f"  Confidence: {conf}")
            print(f"  drugs table:   {drug_val}")
            print(f"  related table: {rel_val}")
            print(f"  ⚡ {disc}")
            print(f"  → Action: {action}")
            print(f"  → Source: {source}")

    print("\n" + "=" * 64)
    print(f"Conflicts written to drug_validation_results (check_status='needs_review')")
    print(f"Query to view: SELECT drug_id,check_type,details FROM drug_validation_results")
    print(f"               WHERE check_status='needs_review'")
    print(f"               ORDER BY (details->>'review_priority')::int, drug_id;")
    print("=" * 64 + "\n")


# ═══════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ailux BD Platform — Cross-Table Conflict Detector"
    )
    parser.add_argument("--drug",    help="Drug ID substring to check (e.g. spy001)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect conflicts but do not write to Supabase")
    args = parser.parse_args()

    run(drug_filter=args.drug, dry_run=args.dry_run)
