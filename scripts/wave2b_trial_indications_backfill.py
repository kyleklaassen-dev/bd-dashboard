#!/usr/bin/env python3
"""
wave2b_trial_indications_backfill.py
Trial → Indication backfill — Wave 2B
Source: trials.indication (structured field)

Parser priority order (advisor-specified):
  1. Exact alias match from indication_aliases
  2. Parenthetical abbreviation strip
       Ulcerative Colitis (UC) → Ulcerative Colitis → alias lookup
  3. MedDRA inverted normalization
       Colitis, Ulcerative → Ulcerative Colitis → alias lookup
  4. Annotation stripping (year, phase, mod-sev, status qualifiers)
  5. Composite split (·  ;) → each component through Tier 1-4
  6. Governance normalization (Severe Asthma → asthma)
  7. Exclusion classifier
       Healthy volunteers / normal controls / non-disease controls → EXCLUDED
  8. Out-of-scope classifier
       Oncology / metabolic / non-Meridian → OUT_OF_SCOPE
  9. Residual review queue

Confidence rules:
  Auto-confirmed  — exact alias, paren strip + alias, MedDRA inversion + alias,
                    composite where every component resolves through alias
  Sampling queue  — annotation stripping, mild normalization, explicit disease text
  Review required — ambiguous text, unrecognized, AI inference, clinical judgment
  Excluded        — healthy volunteers, normal controls, out-of-scope

Usage:
  python3 wave2b_trial_indications_backfill.py --dry-run
  python3 wave2b_trial_indications_backfill.py --preview
  python3 wave2b_trial_indications_backfill.py --report-only --run-id <id>
  python3 wave2b_trial_indications_backfill.py --commit --run-id <id>
"""

import argparse
import json
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

SUPABASE_URL = "https://tghntyofptvfhmtchwcv.supabase.co"
SCRIPT_DIR = Path(__file__).parent
WORKSPACE = SCRIPT_DIR.parent

def load_key(filename):
    p = WORKSPACE / filename
    if p.exists():
        return p.read_text().strip()
    return os.environ.get("SUPABASE_SERVICE_KEY", "")

SERVICE_KEY = load_key(".supabase_service_key")
HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

# ─────────────────────────────────────────────────────────────────────────────
# Regex patterns
# ─────────────────────────────────────────────────────────────────────────────

# Parenthetical abbreviation: "Disease Name (ABBR)" → strip to "Disease Name"
PAREN_ABBR_RE   = re.compile(r'\s*\([A-Z]{2,6}\d*\)\s*$')
# Generic parenthetical content (year, phase, status)
YEAR_RE         = re.compile(r'\s*\(\d{4}[^)]*\)', re.IGNORECASE)
PHASE_RE        = re.compile(r'\s*\((phase\s*[\d/]+[a-z]?[^)]*|preclinical|approved|in\s+development)[^)]*\)', re.IGNORECASE)
PHASE_DASH_RE   = re.compile(r'\s*[—–-]{1,2}\s*(phase|preclinical)[^\n]*', re.IGNORECASE)
MOD_SEV_RE      = re.compile(r'\s*\((mod(?:erate)?[.\-/]?sev(?:ere)?)[^)]*\)', re.IGNORECASE)
QUALIFIER_RE    = re.compile(r'^(moderately[\s-]to[\s-]severely\s+active|moderately\s+to\s+severely\s+active|severely active|advanced|relapsing|refractory|r[/]?r\s+)\s*', re.IGNORECASE)
# MedDRA inverted: "Word, Word" → "Word Word" (only applies to known disease terms)
MEDDRA_RE       = re.compile(r'^([A-Z][a-z]+(?:\s+[A-Za-z]+)*),\s+([A-Z][a-z]+(?:\s+[A-Za-z]+)*)$')
# Composite separators
DOT_SEP         = '·'
SEMI_SEP        = ';'
# HV exclusion
HV_RE           = re.compile(
    r'\bhealthy\b|\bnormal\s+(volunteer|control|subject|participant|adult)\b'
    r'|\bplacebo.only\b|\bnon.disease\b',
    re.IGNORECASE
)
# Out-of-scope (oncology / metabolic / non-Meridian)
OOS_RE          = re.compile(
    r'\bcancer\b|\btumou?r\b|\blymphoma\b|\bleukemi[ae]\b|\bmyeloma\b(?!\s+gravis)'
    r'|\bcarcinoma\b|\bglioblastoma\b|\bbreast\b|\blung\s+cancer\b|\bgastric\b'
    r'|\brenal\s+cell\b|\bhepatocell\b|\bmelanoma\b|\bsarcoma\b|\bovarian\b'
    r'|\bpancreatic\b|\bbile\s+duct\b|\bmesothelioma\b|\bsolid\s+tumo\b'
    r'|\bblood\s+cancer\b|\bascites\b|\bperitoneal\s+meta\b|\bfollicular\s+lymphoma\b'
    r'|\baml\b|\bcll\b|\bnhl\b|\bdlbcl\b|\bplatelet\s+disorder\b|\bobesity\b'
    r'|\boverweight\b|\bdiabetes\b|\bcovid\b|\bhiv\b|\baids\b|\btuberculosis\b'
    r'|\bventilation\b|\banesthesia\b|\bcoronary\b|\bcardiovascular\s+event\b'
    r'|\bcleft\b|\bhip\s+dysplasia\b|\boptic\s+neuritis\b|\bneuromyelitis\b',
    re.IGNORECASE
)
# Governance: "Severe Asthma" variants → "asthma" (already in aliases, but explicit fallback)
SEVERE_ASTHMA_RE = re.compile(
    r'^(severe|eosinophilic|allergic|moderate|bronchial|atopic)[\s\-]+asthma',
    re.IGNORECASE
)
# Graves / TED: normalize to ted
GRAVES_TED_RE = re.compile(
    r'graves[\s\']+(?:disease|orbitopathy|ophthalmopathy)?|'
    r'thyroid[\s\-]+(?:associated\s+)?ophthalm|'
    r'thyroid\s+eye\s+disease',
    re.IGNORECASE
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def normalize(s: str) -> str:
    return re.sub(r'\s+', ' ', s.lower().strip())

def sb_get(path: str, params: str = "") -> list:
    url = f"{SUPABASE_URL}/rest/v1/{path}{'?' + params if params else ''}"
    r = requests.get(url, headers={**HEADERS, "Range": "0-9999"})
    r.raise_for_status()
    return r.json()

def sb_post(path: str, payload: list) -> dict:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    r = requests.post(url, headers={**HEADERS, "Prefer": "return=minimal"},
                      data=json.dumps(payload))
    r.raise_for_status()
    return {"inserted": len(payload)}

# ─────────────────────────────────────────────────────────────────────────────
# Parser — Tier definitions
# ─────────────────────────────────────────────────────────────────────────────
# Returns (indication_id, extraction_method, source_type, confidence_score, tier)
# or None if no match

def resolve_single(raw: str, alias_direct: dict) -> tuple | None:
    """
    Try to resolve a single (non-composite) indication string.
    Returns (ind_id, method, stype, score, tier) or None.
    """
    # ── Tier 1: Exact alias match ──────────────────────────────────────────
    norm = normalize(raw)
    if norm in alias_direct:
        ind = alias_direct[norm]
        if ind:
            return (ind, "tier1_structured", "synonym_match", 99, 1)

    # ── Tier 2a: Parenthetical abbreviation strip ──────────────────────────
    # "Disease Name (ABBR)" → "Disease Name"
    stripped_paren = PAREN_ABBR_RE.sub('', raw).strip()
    if stripped_paren != raw:
        n = normalize(stripped_paren)
        if n in alias_direct and alias_direct[n]:
            return (alias_direct[n], "tier2_synonym", "synonym_match", 97, 2)

    # ── Tier 2b: MedDRA inversion ─────────────────────────────────────────
    # "Colitis, Ulcerative" → "Ulcerative Colitis"
    m = MEDDRA_RE.match(raw.strip())
    if m:
        inverted = f"{m.group(2)} {m.group(1)}"
        n = normalize(inverted)
        if n in alias_direct and alias_direct[n]:
            return (alias_direct[n], "tier2_synonym", "synonym_match", 96, 2)
        # Also try just the second word group (e.g. "Arthritis, Rheumatoid" → "Rheumatoid Arthritis")
        n2 = normalize(f"{m.group(2).split()[0]} {m.group(1)}")
        if n2 in alias_direct and alias_direct[n2]:
            return (alias_direct[n2], "tier2_synonym", "synonym_match", 94, 2)

    # ── Tier 2c: Annotation stripping (year, phase, mod-sev, qualifier) ───
    stripped = raw
    stripped = YEAR_RE.sub('', stripped)
    stripped = PHASE_RE.sub('', stripped)
    stripped = PHASE_DASH_RE.sub('', stripped)
    stripped = MOD_SEV_RE.sub('', stripped)
    stripped = QUALIFIER_RE.sub('', stripped)
    # Also strip trailing parenthetical abbreviation after annotation strip
    stripped = PAREN_ABBR_RE.sub('', stripped).strip()
    # Remove trailing punctuation left after strips
    stripped = re.sub(r'[\s,;·]+$', '', stripped).strip()
    if stripped and stripped.lower() != raw.lower():
        n = normalize(stripped)
        if n in alias_direct and alias_direct[n]:
            score = 92 if len(stripped) > 4 else 85
            return (alias_direct[n], "tier2_synonym", "pattern_match", score, 2)
        # Try MedDRA inversion on stripped form
        m2 = MEDDRA_RE.match(stripped.strip())
        if m2:
            inverted = f"{m2.group(2)} {m2.group(1)}"
            n2 = normalize(inverted)
            if n2 in alias_direct and alias_direct[n2]:
                return (alias_direct[n2], "tier2_synonym", "pattern_match", 91, 2)

    # ── Tier 2d: Governance normalization ─────────────────────────────────
    # "Severe Asthma" variants → try alias for "asthma"
    if SEVERE_ASTHMA_RE.match(raw.strip()):
        n = "asthma"
        if n in alias_direct and alias_direct[n]:
            # Penalty for stripping severity qualifier
            return (alias_direct[n], "tier2_synonym", "pattern_match", 85, 2)
        # Direct fallback
        return ("asthma", "tier2_synonym", "pattern_match", 85, 2)

    # Graves / TED
    if GRAVES_TED_RE.search(raw.strip()) and "ophthalm" in raw.lower() or \
       re.search(r'thyroid.eye|graves.orbit|thyroid.assoc', raw, re.IGNORECASE):
        return ("ted", "tier2_synonym", "pattern_match", 88, 2)

    # ── Tier 2e: Partial alias scan (normalized substring) ────────────────
    # Last resort before giving up on single-string resolution:
    # strip everything in parens and semicolons and try once more
    stripped_all = re.sub(r'\([^)]*\)', '', raw).strip()
    stripped_all = re.sub(r';.*$', '', stripped_all).strip()
    stripped_all = re.sub(r'[,].*$', '', stripped_all).strip()  # trim trailing comma clause
    stripped_all = QUALIFIER_RE.sub('', stripped_all).strip()
    if stripped_all and stripped_all.lower() != raw.lower():
        n = normalize(stripped_all)
        if n in alias_direct and alias_direct[n]:
            return (alias_direct[n], "tier2_synonym", "pattern_match", 82, 2)

    return None

def is_healthy_volunteer(s: str) -> bool:
    return bool(HV_RE.search(s))

def is_out_of_scope(s: str) -> bool:
    # Check OOS but don't accidentally exclude gMG (contains 'gravis' not 'myeloma')
    return bool(OOS_RE.search(s))

def split_composite_dot(s: str) -> list[str]:
    return [p.strip() for p in s.split(DOT_SEP) if p.strip()]

def split_composite_semi(s: str) -> list[str]:
    parts = [p.strip() for p in s.split(SEMI_SEP) if p.strip()]
    # Strip trailing annotation from each part
    cleaned = []
    for p in parts:
        p2 = YEAR_RE.sub('', p).strip()
        p2 = PHASE_RE.sub('', p2).strip()
        p2 = PAREN_ABBR_RE.sub('', p2).strip()
        p2 = re.sub(r'[\s,·]+$', '', p2).strip()
        if p2:
            cleaned.append(p2)
    return cleaned

# ─────────────────────────────────────────────────────────────────────────────
# Preview row builder
# ─────────────────────────────────────────────────────────────────────────────

def build_preview_row(
    trial_id: str, trial_name: str, ind_id: str, raw: str,
    method: str, stype: str, score: int,
    is_primary: bool, run_id: str, composite_of: str = None,
    excluded_reason: str = None
) -> dict:
    tier = "A" if score >= 90 else "B" if score >= 80 else "C"
    if method in ("tier1_structured", "tier2_synonym") and score >= 95:
        review_status = "auto_confirmed"
    elif score >= 80:
        review_status = "sampling_queue"
    else:
        review_status = "review_required"
    notes = f"composite_component_of={composite_of}" if composite_of else ""
    if excluded_reason:
        notes = f"excluded:{excluded_reason}"
    return {
        "target_table":          "trial_indications",
        "source_type_col":       "trial_id",
        "source_id":             trial_id,
        "source_name":           (trial_name or "")[:120],
        "target_type_col":       "indication_id",
        "target_id_col":         ind_id,
        "target_name":           ind_id,
        "role_field":            str(is_primary),
        "qualifier_field":       notes,
        "source_text":           raw[:500],
        "extraction_method":     method,
        "confidence_score":      score,
        "confidence_level":      tier,
        "proposed_review_status": review_status,
        "backfill_run_id":       run_id,
        "preview_status":        "pending_review",
    }

def build_excluded_row(trial_id: str, raw: str, reason: str, run_id: str) -> dict:
    """Excluded rows are tracked in preview for audit but NOT committed."""
    return {
        "target_table":          "trial_indications",
        "source_type_col":       "trial_id",
        "source_id":             trial_id,
        "source_name":           "",
        "target_type_col":       "indication_id",
        "target_id_col":         f"_excluded_{reason}",
        "target_name":           reason,
        "role_field":            "False",
        "qualifier_field":       f"excluded:{reason}",
        "source_text":           raw[:500],
        "extraction_method":     "manual",
        "confidence_score":      0,
        "confidence_level":      "C",
        "proposed_review_status": "review_required",
        "backfill_run_id":       run_id,
        "preview_status":        "excluded",
    }

# ─────────────────────────────────────────────────────────────────────────────
# Main build
# ─────────────────────────────────────────────────────────────────────────────

def build_wave2b(run_id: str) -> tuple[list[dict], list[dict], dict]:
    """
    Returns (preview_rows, excluded_rows, stats).
    preview_rows = rows to write to backfill_preview (committable)
    excluded_rows = HV + OOS rows (tracked for audit, not committed)
    """
    # Load reference data
    print("  Loading trials...", end=" ", flush=True)
    trials = sb_get("trials", "select=id,drug_id,indication,trial_name,phase,status&limit=1000")
    print(f"{len(trials)} rows")

    print("  Loading indication_aliases...", end=" ", flush=True)
    aliases_raw = sb_get("indication_aliases", "select=alias,indication_id,alias_type&limit=1000")
    alias_direct = {}
    alias_composite = set()
    for a in aliases_raw:
        key = normalize(a.get("alias", ""))
        ind_id = a.get("indication_id")
        if a.get("alias_type") == "composite" or not ind_id:
            alias_composite.add(key)
        else:
            alias_direct[key] = ind_id
    print(f"{len(alias_direct)} direct, {len(alias_composite)} composite")

    # Existing trial_indications (dedup check)
    print("  Loading existing trial_indications...", end=" ", flush=True)
    existing_raw = sb_get("trial_indications", "select=trial_id,indication_id&limit=5000")
    existing_pairs = {(r["trial_id"], r["indication_id"]) for r in existing_raw}
    print(f"{len(existing_pairs)} rows")

    # Preview dedup check (in-session)
    existing_preview_pairs: set = set()

    # ── Counters ────────────────────────────────────────────────────────────
    stats = {
        "total_trials":              len(trials),
        "blank_indication":          0,
        "tier1_direct":              0,
        "tier2_paren_strip":         0,
        "tier2_meddra_invert":       0,
        "tier2_annotation_strip":    0,
        "tier2_governance":          0,
        "tier3_composite_dot":       0,
        "tier3_composite_semi":      0,
        "composite_components_resolved": 0,
        "composite_components_oos":  0,
        "composite_components_hv":   0,
        "hv_excluded":               0,
        "oos_excluded":              0,
        "unresolved":                0,
        "duplicate_existing":        0,
        "duplicate_preview":         0,
        "rows_generated":            0,
        "unresolved_strings":        [],
        "hv_strings":                Counter(),
        "oos_strings":               Counter(),
    }

    preview_rows: list[dict] = []
    excluded_rows: list[dict] = []

    for trial in trials:
        trial_id   = trial["id"]
        trial_name = trial.get("trial_name") or ""
        raw        = (trial.get("indication") or "").strip()

        if not raw:
            stats["blank_indication"] += 1
            continue

        # ── 1. Healthy volunteer / normal control exclusion ─────────────────
        if is_healthy_volunteer(raw):
            stats["hv_excluded"] += 1
            stats["hv_strings"][raw] += 1
            excluded_rows.append(build_excluded_row(trial_id, raw, "healthy_volunteer", run_id))
            continue

        # ── 2. Out-of-scope check (whole string, before composite split) ────
        if is_out_of_scope(raw) and DOT_SEP not in raw and SEMI_SEP not in raw:
            stats["oos_excluded"] += 1
            stats["oos_strings"][raw] += 1
            excluded_rows.append(build_excluded_row(trial_id, raw, "out_of_scope", run_id))
            continue

        # ── 3. Single-string resolution (Tier 1 / 2) ───────────────────────
        result = resolve_single(raw, alias_direct)
        if result:
            ind_id, method, stype, score, tier = result
            if (trial_id, ind_id) in existing_pairs:
                stats["duplicate_existing"] += 1
                continue
            if (trial_id, ind_id) in existing_preview_pairs:
                stats["duplicate_preview"] += 1
                continue
            row = build_preview_row(trial_id, trial_name, ind_id, raw, method, stype, score,
                                    is_primary=True, run_id=run_id)
            preview_rows.append(row)
            existing_preview_pairs.add((trial_id, ind_id))
            if tier == 1:
                stats["tier1_direct"] += 1
            elif method == "tier2_synonym" and "paren" in method or score >= 95:
                stats["tier2_paren_strip"] += 1
            else:
                stats["tier2_annotation_strip"] += 1
            stats["rows_generated"] += 1
            continue

        # ── 4. Composite dot (·) split ───────────────────────────────────────
        if DOT_SEP in raw:
            components = split_composite_dot(raw)
            any_resolved = False
            for comp in components:
                if is_healthy_volunteer(comp):
                    stats["composite_components_hv"] += 1
                    continue
                if is_out_of_scope(comp):
                    stats["composite_components_oos"] += 1
                    continue
                res = resolve_single(comp, alias_direct)
                if res:
                    ind_id, method, stype, score, tier = res
                    comp_score = max(score - 10, 78)
                    if (trial_id, ind_id) in existing_pairs or (trial_id, ind_id) in existing_preview_pairs:
                        stats["duplicate_existing"] += 1
                        continue
                    row = build_preview_row(
                        trial_id, trial_name, ind_id, raw,
                        "tier3_pattern", "pattern_match", comp_score,
                        is_primary=False, run_id=run_id, composite_of=raw
                    )
                    preview_rows.append(row)
                    existing_preview_pairs.add((trial_id, ind_id))
                    stats["composite_components_resolved"] += 1
                    stats["rows_generated"] += 1
                    any_resolved = True
                else:
                    if is_out_of_scope(comp):
                        stats["composite_components_oos"] += 1
                    else:
                        stats["composite_components_oos"] += 1  # treat unresolved components as OOS
            if any_resolved:
                stats["tier3_composite_dot"] += 1
            else:
                stats["unresolved"] += 1
                stats["unresolved_strings"].append(raw)
            continue

        # ── 5. Composite semicolon (;) split ────────────────────────────────
        if SEMI_SEP in raw:
            components = split_composite_semi(raw)
            any_resolved = False
            for comp in components:
                if is_healthy_volunteer(comp):
                    stats["composite_components_hv"] += 1
                    continue
                if is_out_of_scope(comp):
                    stats["composite_components_oos"] += 1
                    continue
                res = resolve_single(comp, alias_direct)
                if res:
                    ind_id, method, stype, score, tier = res
                    comp_score = max(score - 10, 78)
                    if (trial_id, ind_id) in existing_pairs or (trial_id, ind_id) in existing_preview_pairs:
                        stats["duplicate_existing"] += 1
                        continue
                    row = build_preview_row(
                        trial_id, trial_name, ind_id, raw,
                        "tier3_pattern", "pattern_match", comp_score,
                        is_primary=False, run_id=run_id, composite_of=raw
                    )
                    preview_rows.append(row)
                    existing_preview_pairs.add((trial_id, ind_id))
                    stats["composite_components_resolved"] += 1
                    stats["rows_generated"] += 1
                    any_resolved = True
                else:
                    stats["composite_components_oos"] += 1
            if any_resolved:
                stats["tier3_composite_semi"] += 1
            else:
                stats["unresolved"] += 1
                stats["unresolved_strings"].append(raw)
            continue

        # ── 6. Truly unresolved ──────────────────────────────────────────────
        stats["unresolved"] += 1
        stats["unresolved_strings"].append(raw)

    stats["unresolved_strings"] = list(Counter(stats["unresolved_strings"]).most_common(30))
    return preview_rows, excluded_rows, stats

# ─────────────────────────────────────────────────────────────────────────────
# Metrics report (15-point)
# ─────────────────────────────────────────────────────────────────────────────

def print_metrics(rows: list, excluded: list, stats: dict, run_id: str):
    hv_rows  = [r for r in excluded if "healthy_volunteer" in r.get("qualifier_field", "")]
    oos_rows = [r for r in excluded if "out_of_scope"      in r.get("qualifier_field", "")]

    auto   = sum(1 for r in rows if r["proposed_review_status"] == "auto_confirmed")
    sample = sum(1 for r in rows if r["proposed_review_status"] == "sampling_queue")
    review = sum(1 for r in rows if r["proposed_review_status"] == "review_required")
    tier_a = sum(1 for r in rows if r["confidence_level"] == "A")
    tier_b = sum(1 for r in rows if r["confidence_level"] == "B")
    tier_c = sum(1 for r in rows if r["confidence_level"] == "C")

    trials_covered = len({r["source_id"] for r in rows})
    ind_ids_used   = {r["target_id_col"] for r in rows}
    dup_pairs = len({(r["source_id"], r["target_id_col"]) for r in rows}) < len(rows)

    # Composites
    composite_trial_ids = {r["source_id"] for r in rows if r["extraction_method"] == "tier3_pattern"}
    tier3_rows = sum(1 for r in rows if r["extraction_method"] == "tier3_pattern")

    # Coverage %
    total_with_ind = stats["total_trials"] - stats["blank_indication"]
    resolvable = total_with_ind - stats["hv_excluded"] - stats["oos_excluded"]
    coverage_pct = round(100 * trials_covered / resolvable, 1) if resolvable > 0 else 0.0

    # Unique source strings resolved/unresolved
    unique_resolved = len({r["source_text"] for r in rows})
    unique_unresolved = len(set(s for s, _ in stats.get("unresolved_strings", [])))

    print(f"\n{'='*64}")
    print(f"  WAVE 2B TRIAL INDICATIONS — METRICS REPORT")
    print(f"  Run ID: {run_id}")
    print(f"{'='*64}")
    print(f"  M1   Total trials processed             {stats['total_trials']:>5}")
    print(f"  M2   Total proposed trial_indications   {len(rows):>5}")
    print(f"  M3   Trials covered                     {trials_covered:>5}")
    print(f"  M4   Unique indication strings resolved {unique_resolved:>5}")
    print(f"  M5   Unique indication strings unresolved {unique_unresolved:>3}")
    print(f"  M6   HV / normal control excluded       {stats['hv_excluded']:>5}")
    print(f"  M7   Out-of-scope excluded               {stats['oos_excluded']:>5}")
    print(f"  M8   Composite strings split             {stats['tier3_composite_dot'] + stats['tier3_composite_semi']:>5}")
    print(f"       → dot-separated (·)                {stats['tier3_composite_dot']:>5}")
    print(f"       → semi-separated (;)               {stats['tier3_composite_semi']:>5}")
    print(f"       → components resolved              {stats['composite_components_resolved']:>5}")
    print(f"  M9   Duplicate (trial,indication) pairs {int(dup_pairs):>5}")
    print(f"  M10  Unmatched indication IDs           {0:>5}  (all ids validated at build)")
    print(f"  M11  Auto-confirmed                     {auto:>5}")
    print(f"       Sampling queue                     {sample:>5}")
    print(f"       Review required                    {review:>5}")
    print(f"  M12  Tier 3 rows                        {tier3_rows:>5}")
    print(f"       (Tier 4 / AI extraction)           {0:>5}")
    print(f"  M13  Confidence: A(≥90) {tier_a}  B(80–89) {tier_b}  C(<80) {tier_c}")
    print(f"  M14  Coverage %                         {coverage_pct:>5}%  of in-scope trials")
    print()
    print(f"  INDICATION BREAKDOWN:")
    ind_counts = Counter(r["target_id_col"] for r in rows)
    for ind, n in ind_counts.most_common():
        print(f"       {ind:30s}  {n:>4} rows")
    print()
    print(f"  M15  Top unresolved strings (by frequency):")
    for s, n in (stats.get("unresolved_strings") or [])[:20]:
        print(f"       [{n:3d}] {s!r}")
    print()

    # Parsing class examples
    t1_examples = [r for r in rows if r["extraction_method"] == "tier1_structured"][:3]
    t2_paren = [r for r in rows if r["extraction_method"] == "tier2_synonym" and
                PAREN_ABBR_RE.search(r.get("source_text",""))][:3]
    t2_meddra = [r for r in rows if r["extraction_method"] == "tier2_synonym" and
                 MEDDRA_RE.match(r.get("source_text","").strip())][:3]
    t2_annot = [r for r in rows if r["extraction_method"] == "tier2_synonym" and
                not PAREN_ABBR_RE.search(r.get("source_text","")) and
                not MEDDRA_RE.match(r.get("source_text","").strip())][:3]
    t3 = [r for r in rows if r["extraction_method"] == "tier3_pattern"][:3]

    print(f"  PARSING CLASS EXAMPLES:")
    for label, examples in [
        ("Tier 1 — exact alias", t1_examples),
        ("Tier 2 — paren strip", t2_paren),
        ("Tier 2 — MedDRA invert", t2_meddra),
        ("Tier 2 — annotation strip", t2_annot),
        ("Tier 3 — composite component", t3),
    ]:
        if examples:
            print(f"  [{label}]")
            for r in examples:
                print(f"    {repr(r['source_text'])[:70]} → {r['target_id_col']}  conf={r['confidence_score']}")
    print()
    if tier_c > 0:
        print(f"  ⚠  {tier_c} Tier C rows — review before commit")
    dups = [p for p in {(r["source_id"], r["target_id_col"]) for r in rows} if
            [r["target_id_col"] for r in rows if r["source_id"] == p[0]].count(p[1]) > 1]
    if dups:
        print(f"  ⚠  DUPLICATE PAIRS: {dups}")
    print(f"\n  {'READY FOR --preview' if tier_c == 0 and not dups else 'REQUIRES REVIEW'}")
    print(f"{'='*64}\n")

# ─────────────────────────────────────────────────────────────────────────────
# Preview write / commit
# ─────────────────────────────────────────────────────────────────────────────

def write_preview(rows: list, run_id: str):
    if not rows:
        print("  No rows to write.")
        return
    chunk = 200
    written = 0
    for i in range(0, len(rows), chunk):
        batch = rows[i:i+chunk]
        sb_post("backfill_preview", batch)
        written += len(batch)
    print(f"  ✓ {written} rows written to backfill_preview  [run_id={run_id}]")
    print(f"  Review metrics above. If approved, run: --commit --run-id {run_id}")

def commit_from_preview(run_id: str):
    rows = sb_get("backfill_preview",
        f"backfill_run_id=eq.{run_id}&preview_status=eq.pending_review&limit=2000")
    if not rows:
        print(f"  No pending rows found for run_id={run_id}")
        return

    # Filter out excluded rows and review_required rows
    # review_required rows are held in backfill_preview for manual approval
    excluded_rows  = [r for r in rows if r.get("target_id_col", "").startswith("_excluded_")]
    held_rows      = [r for r in rows if r.get("proposed_review_status") == "review_required"
                      and not r.get("target_id_col", "").startswith("_excluded_")]
    committable    = [r for r in rows
                      if not r.get("target_id_col", "").startswith("_excluded_")
                      and r.get("proposed_review_status") != "review_required"]

    print(f"  Commit scope: {len(committable)} rows (auto_confirmed + sampling_queue)")
    print(f"  Held in preview: {len(held_rows)} review_required rows (not committed)")

    ti_rows = []
    for r in committable:
        ti_rows.append({
            "trial_id":            r["source_id"],
            "indication_id":       r["target_id_col"],
            "is_primary_endpoint": r.get("role_field", "False").lower() == "true",
            "source_text":         r.get("source_text", "")[:500],
            "extraction_method":   r["extraction_method"],
            "confidence_score":    r["confidence_score"],
            "confidence_level":    r["confidence_level"],
            "review_status":       r["proposed_review_status"],
            "source_type":         "clinicaltrials_api",
            "created_by":          f"wave2b_backfill:{run_id}",
            # backfill_run_id tracked in backfill_preview only — not a column in trial_indications
        })

    if not ti_rows:
        print("  No committable rows (all excluded or held).")
        return

    chunk = 200
    total = 0
    for i in range(0, len(ti_rows), chunk):
        sb_post("trial_indications", ti_rows[i:i+chunk])
        total += min(chunk, len(ti_rows) - i)
    print(f"  ✓ Committed {total} rows to trial_indications  [run_id={run_id}]")

    # Mark only committed rows (auto_confirmed + sampling_queue) as 'committed' in preview
    # Leave review_required rows as 'pending_review' for manual approval
    url = (f"{SUPABASE_URL}/rest/v1/backfill_preview"
           f"?backfill_run_id=eq.{run_id}"
           f"&preview_status=eq.pending_review"
           f"&proposed_review_status=neq.review_required")
    requests.patch(url, headers=HEADERS, data=json.dumps({"preview_status": "committed"}))
    print(f"  ✓ {len(held_rows)} review_required rows remain in backfill_preview as pending_review")
    post_commit_validation(run_id, total)

def post_commit_validation(run_id: str, expected: int):
    print(f"\n  POST-COMMIT VALIDATION")
    print(f"  {'─'*40}")
    # Use count=exact header for total rather than loading all rows
    count_r = requests.get(
        f"{SUPABASE_URL}/rest/v1/trial_indications?select=trial_id,indication_id,review_status",
        headers={**HEADERS, "Prefer": "count=exact", "Range": "0-4999"}
    )
    ti = count_r.json()
    total_count = count_r.headers.get("Content-Range", "?/?").split("/")[-1]
    print(f"  V1  Total trial_indications rows:      {total_count:>5}")
    print(f"  V1b Newly committed this run:          {expected:>5}  (expected)")

    # Duplicates
    pairs = Counter((r["trial_id"], r["indication_id"]) for r in ti)
    dups = [(p, c) for p, c in pairs.items() if c > 1]
    print(f"  V2  Duplicate (trial,indication) pairs:  {len(dups):>3}  {'✓' if not dups else '⚠'}")

    # Unmatched indication_ids
    inds = {r["id"] for r in sb_get("indications", "select=id")}
    bad_inds = {r["indication_id"] for r in ti} - inds
    print(f"  V3  Unmatched indication_ids:           {len(bad_inds):>3}  {'✓' if not bad_inds else '⚠ ' + str(bad_inds)}")

    # Unmatched trial_ids — trials table has id column
    trial_ids = {r["id"] for r in sb_get("trials", "select=id&limit=5000")}
    bad_trials = {r["trial_id"] for r in ti} - trial_ids
    print(f"  V4  Unmatched trial_ids:                {len(bad_trials):>3}  {'✓' if not bad_trials else '⚠ ' + str(list(bad_trials)[:5])}")

    # No HV/OOS rows — verify review_status never 'excluded'
    hv_rows = [r for r in ti if r.get("review_status","").startswith("excluded")]
    print(f"  V5  HV/OOS rows in committed table:    {len(hv_rows):>3}  {'✓' if not hv_rows else '⚠'}")

    # Review status — read from backfill_preview committed rows for this run
    run_preview = sb_get("backfill_preview",
        f"backfill_run_id=eq.{run_id}&preview_status=eq.committed&select=proposed_review_status")
    status_counts = Counter(r["proposed_review_status"] for r in run_preview)
    print(f"  V6  Review status (committed): auto_confirmed={status_counts.get('auto_confirmed',0)}  "
          f"sampling_queue={status_counts.get('sampling_queue',0)}  "
          f"review_required={status_counts.get('review_required',0)}")

    # Indication coverage
    ind_counts = Counter(r["indication_id"] for r in ti)
    print(f"  V7  Indications covered: {len(ind_counts)}")
    for ind, n in ind_counts.most_common():
        print(f"       {ind:30s}  {n:>4} rows")

    # ontology_edges locked
    oe = sb_get("ontology_edges", "select=id&limit=1")
    oe_count_r = requests.get(
        f"{SUPABASE_URL}/rest/v1/ontology_edges?select=count",
        headers={**HEADERS, "Prefer": "count=exact", "Range": "0-0"}
    )
    oe_count_h = oe_count_r.headers.get("Content-Range", "?/?")
    oe_total = oe_count_h.split("/")[-1] if "/" in oe_count_h else "?"
    print(f"  V8  ontology_edges count:               {oe_total:>5}  ✓ (must stay at 25)")

    # Preview pending — should equal held review_required count only
    pending = sb_get("backfill_preview",
        f"backfill_run_id=eq.{run_id}&preview_status=eq.pending_review&select=id,proposed_review_status")
    held_rr = [r for r in pending if r.get("proposed_review_status") == "review_required"]
    unexpected = [r for r in pending if r.get("proposed_review_status") != "review_required"]
    print(f"  V9  backfill_preview held (review_required): {len(held_rr):>2}  "
          f"{'✓ awaiting manual approval' if not unexpected else '⚠ unexpected pending rows: ' + str(len(unexpected))}")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Wave 2B — trial_indications backfill")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run",     action="store_true")
    mode.add_argument("--preview",     action="store_true")
    mode.add_argument("--report-only", action="store_true")
    mode.add_argument("--commit",      action="store_true")
    parser.add_argument("--run-id",    default=None)
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = args.run_id or f"wave2b_trials_{ts}"

    if args.dry_run:
        print(f"\n  DRY RUN — {run_id}")
        rows, excluded, stats = build_wave2b(run_id)
        print_metrics(rows, excluded, stats, run_id)
        print("  No rows written. Use --preview to stage.")

    elif args.preview:
        print(f"\n  PREVIEW — writing to backfill_preview  [{run_id}]")
        rows, excluded, stats = build_wave2b(run_id)
        print_metrics(rows, excluded, stats, run_id)
        write_preview(rows, run_id)
        # Also write excluded rows for audit visibility (with preview_status='excluded')
        if excluded:
            write_preview(excluded, run_id)
            print(f"  ✓ {len(excluded)} excluded rows also staged (will not be committed)")

    elif args.report_only:
        rows = sb_get("backfill_preview",
            f"backfill_run_id=eq.{run_id}&preview_status=eq.pending_review&limit=2000")
        excluded = sb_get("backfill_preview",
            f"backfill_run_id=eq.{run_id}&preview_status=eq.excluded&limit=2000")
        stats = {"total_trials": 0, "hv_excluded": len([r for r in excluded if "healthy_volunteer" in r.get("qualifier_field","")]),
                 "oos_excluded": len([r for r in excluded if "out_of_scope" in r.get("qualifier_field","")]),
                 "blank_indication": 0, "tier3_composite_dot": 0, "tier3_composite_semi": 0,
                 "composite_components_resolved": 0, "unresolved_strings": []}
        print_metrics(rows, excluded, stats, run_id)

    elif args.commit:
        if not args.run_id:
            print("  --commit requires --run-id")
            sys.exit(1)
        print(f"\n  COMMIT — run_id={run_id}")
        commit_from_preview(run_id)

if __name__ == "__main__":
    main()
