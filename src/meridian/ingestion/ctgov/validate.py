#!/usr/bin/env python3
"""
Pre/post-sync field validation for ct_gov_sync (§3 split). Brand-name, study-acronym,
and drug-field-consistency checks + run_field_validation. Extracted verbatim.
"""

import re

from meridian.ingestion.ctgov.common import log, sb_get, sb_upsert, sb_patch, NOW_ISO


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

    def _has_bispecific_sep(t):
        # Recognize the multiple delimiters real target data uses, not just "×":
        #   "×" / "/"  ·  spaced " x " (CD5 x CD3, IL-4Ra x TSLP)  ·  compact AxB (CD19xCD3)
        if not t:
            return False
        if "×" in t or "/" in t:
            return True
        if _re2.search(r'\s[xX]\s', t):
            return True
        if _re2.search(r'[A-Za-z0-9]x[A-Z0-9]', t):   # CD19xCD3 — x between token end and an UPPER/digit
            return True
        return False

    is_target_bispecific  = _has_bispecific_sep(target)
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

    if is_format_bispecific and target and not _has_bispecific_sep(target):
        warnings.append(
            f"[field_conflict] drug '{did}': drug_format='{drug_format}' but "
            f"target='{target}' has no bispecific separator (× or /). "
            f"Check whether target field is complete."
        )

    if is_mechanism_bispecific and target and not _has_bispecific_sep(target):
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
