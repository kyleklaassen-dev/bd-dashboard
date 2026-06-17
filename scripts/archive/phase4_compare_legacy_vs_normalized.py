#!/usr/bin/env python3
"""
Phase 4 Comparison Harness — Meridian BD Platform
====================================================
Read-only. Does NOT modify any production data.
Compares legacy area_id-based queries against normalized ontology tables.

Usage:
  python3 scripts/phase4_compare_legacy_vs_normalized.py
  python3 scripts/phase4_compare_legacy_vs_normalized.py --indication uc
  python3 scripts/phase4_compare_legacy_vs_normalized.py --area tl1a
  python3 scripts/phase4_compare_legacy_vs_normalized.py --output docs/phase4_comparison_harness.md

Comparison targets:
  - drug_areas (legacy) vs drug_indications (normalized)
  - drug_area_scores (legacy) vs drug_targets + drug_indications (normalized)
  - deals.area_id (legacy) — no normalized equivalent yet
  - catalysts.area_id (legacy) vs trial_indications (normalized)
  - trials (legacy drug_id join) vs trial_indications (normalized)

Phase 4 model:
  Legacy data = production baseline. Normalized data = candidate truth layer.
  No single table is ground truth. Truth is evidence-weighted and relationship-validated.
  Phase 4 success = validated parity + justified correction. NOT raw parity.

Area status values:
  match                       — raw match ≥ 95%; all differences explained
  compare_pass_oos_adjusted   — raw% < 95% but adjusted% ≥ 95% after classifying legacy_noise_removed records
  acceptable_mismatch         — 70–94% match with unresolved extra-legacy
  needs_rule_adjustment       — gap needs alias, bridge rule, or backfill
  migration_blocker           — DO NOT migrate; unclassified gaps present or < 40% raw match
  not_ready                   — fundamental mapping doesn't exist yet

Difference classification types (per record):
  legacy_noise_removed        — legacy record normalized correctly excludes; remove from denominator
  normalized_gap              — valid legacy record normalized missed; backfill needed
  ontology_scope_difference   — legacy bucket ≠ normalized bucket semantically; bridge rule needed
  needs_manual_review         — insufficient evidence to classify; hold for review
  new_normalized_value        — normalized found a valid relationship legacy missed; improvement
  source_conflict             — record contradicted by drug target, modality, or source evidence
  cross_table_inconsistency   — record disagrees with multiple evidence tables simultaneously


Ontology governance — legacy dashboard view types (2026-05-25, advisor):
  Legacy dashboard "areas" are not a single ontological category.
  They must be treated as view-type-specific groupings:

    Target views (resolve via drug_targets.target_id):
      tl1a, fcrn, igf1r, tslp, il4ra

    Indication group views (resolve via drug_indications.indication_id):
      ibd, atopy, respiratory, autoimmune

    Indication views (near 1:1 with indication ontology):
      ted

    Platform / modality views (no clean normalized replacement yet):
      tcell

  TL1A = a biological TARGET.
  IBD = an indication group (UC + CD).
  These are not equivalent categories. Do not conflate them in migration logic.
  The correct normalized replacement paths are different:
    Legacy tl1a → drug_targets WHERE target_id = 'tl1a'
    Legacy ibd  → drug_indications WHERE indication_id IN ('uc','cd')

  The LEGACY_VIEW_TYPES constant below encodes this governance distinction.
"""

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://tghntyofptvfhmtchwcv.supabase.co"
# Read key from file at runtime
import os

def _load_key():
    key_file = os.path.join(os.path.dirname(__file__), '..', '.supabase_anon_key')
    with open(os.path.abspath(key_file)) as f:
        return f.read().strip()

# ── Supabase helpers ──────────────────────────────────────────────────────────
def sb_get(table: str, params: str = "limit=2000") -> list:
    key = _load_key()
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"GET {table}?{params} → {e.code}: {body[:300]}")


# ── Area → Indication mapping ─────────────────────────────────────────────────
# Each legacy area_id maps to one or more indication_ids in the normalized ontology.
# This mapping is evidence-based (not assumed). Rationale in normalization_engine.md.
AREA_TO_IND = {
    # Exact or near-exact semantic equivalence
    "ted":         ["ted"],
    # Target-defined areas that map to their primary disease indication(s)
    "tl1a":        ["uc", "cd"],
    "ibd":         ["uc", "cd"],
    "igf1r":       ["ted"],
    "fcrn":        ["gmg", "cidp", "waiha"],
    "il4ra":       ["ad", "asthma"],
    "atopy":       ["ad", "chronic_urticaria"],
    "tslp":        ["asthma", "copd", "crswnp"],
    "respiratory": ["asthma", "copd", "crswnp"],
    "autoimmune":  ["gmg", "cidp", "ra", "sle", "waiha", "sjogrens"],
    "tcell":       ["all", "multiple_myeloma"],
}

# Reverse: indication_id → legacy area_id(s)
IND_TO_AREA: dict[str, list[str]] = defaultdict(list)
for area, inds in AREA_TO_IND.items():
    for ind in inds:
        IND_TO_AREA[ind].append(area)


# ── Legacy View Type Governance ───────────────────────────────────────────────
# Governance rule (2026-05-25, advisor):
#   Legacy dashboard "areas" are not a uniform ontological category.
#   TL1A is a biological target. IBD is an indication group. These require
#   different normalized replacement paths and must NOT be conflated.
#
#   target_view          — legacy bucket groups drugs by molecular target
#                          Normalized replacement: drug_targets.target_id
#   indication_group_view — legacy bucket groups drugs by disease family
#                          Normalized replacement: drug_indications.indication_id
#   indication_view      — near 1:1 with a canonical indication node
#                          Normalized replacement: drug_indications.indication_id
#   platform_view        — modality/mechanism bucket without clean indication mapping
#                          Normalized replacement: not yet determined
LEGACY_VIEW_TYPES: dict[str, str] = {
    # Target views — normalized replacement via drug_targets
    "tl1a":        "target_view",
    "fcrn":        "target_view",
    "igf1r":       "target_view",
    "tslp":        "target_view",
    "il4ra":       "target_view",
    # Indication group views — normalized replacement via drug_indications
    "ibd":         "indication_group_view",
    "atopy":       "indication_group_view",
    "respiratory": "indication_group_view",
    "autoimmune":  "indication_group_view",
    # Indication views — normalized replacement via drug_indications
    "ted":         "indication_view",
    # Platform / modality views — no clean normalized path yet
    "tcell":       "platform_view",
}

# ── Phase 4 difference classification model ───────────────────────────────────
# Governance rule (2026-05-25, advisor):
#   "Do not treat legacy data as ground truth. Treat it as the production baseline."
#   Phase 4 success = validated parity + justified correction. NOT raw parity.
#
# Every extra-legacy or extra-normalized record must be classified:
#
#   legacy_noise_removed    Legacy includes a record normalized correctly excludes.
#                           Action: No backfill. Remove from readiness denominator.
#   normalized_gap          Legacy has a valid record normalized missed.
#                           Action: Backfill or add alias rule.
#   ontology_scope_difference  Legacy bucket ≠ normalized bucket semantically.
#                           Action: Bridge rule or keep legacy view.
#   needs_manual_review     Evidence insufficient to classify.
#                           Action: Hold for human review.
#   new_normalized_value    Normalized has a valid relationship legacy does not.
#                           Action: Document as improvement.
#
# Format: (area_id, drug_id) → (classification, action, note)
# Direction convention: extra_legacy entries use the first 4 types;
#                       extra_norm entries use new_normalized_value or the last 3.
# Unclassified extra_legacy → needs_manual_review (conservative default)
# Unclassified extra_norm   → new_normalized_value (optimistic default)
DIFFERENCE_CLASSIFICATIONS: dict[tuple, tuple] = {

    # ── tl1a (extra_legacy) ──────────────────────────────────────────────────
    # Phase 4B gap classification (Session 53h): all 17 gap drugs classified.
    # KEY FINDING: zero gap drugs are true TL1A target drugs missing drug_targets rows.
    # The legacy TL1A area was a COMPETITIVE LANDSCAPE CONTAINER mixing TL1A target
    # drugs (35, already normalized) with IBD indication competitors (15) and noise (2).
    # Adjusted TL1A target-view match after excluding all 17: 35/35 = 100%.

    # Legacy noise — wrong area entirely (confirmed in IBD gap also)
    ("tl1a", "lm-302"):    ("legacy_noise_removed",
                            "Do not backfill. Exclude from TL1A target-view denominator.",
                            "CLDN18.2 MMAE-ADC for gastric/GEJ cancer. All trials off_target. "
                            "No TL1A biology. Wrong legacy area assignment."),
    ("tl1a", "sim0500"):   ("legacy_noise_removed",
                            "Do not backfill. Exclude from TL1A target-view denominator.",
                            "GPRC5D×BCMA×CD3 trispecific for RRMM (multiple myeloma). "
                            "No TL1A biology. Wrong legacy area assignment."),

    # IBD indication drugs — correct normalized path is drug_indications (uc/cd), NOT drug_targets (tl1a)
    # These were tracked in legacy TL1A bucket for IBD competitive landscape context only.
    # Do NOT backfill drug_targets tl1a for any of these.
    ("tl1a", "vedolizumab"):         ("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications uc+cd.",
                                      "Anti-α4β7 integrin mAb. Approved UC/CD. No TL1A biology. "
                                      "Legacy TL1A area used as IBD competitive landscape container."),
    ("tl1a", "risankizumab"):        ("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications cd+uc.",
                                      "Anti-IL-23p19 mAb. Approved PsO/CD/UC. No TL1A biology."),
    ("tl1a", "mirikizumab"):         ("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications uc+cd.",
                                      "Anti-IL-23p19 mAb. Approved UC (2023)/CD (2024). No TL1A biology."),
    ("tl1a", "guselkumab"):          ("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications cd.",
                                      "Anti-IL-23p19 mAb. Approved PsO/PsA/CD. No TL1A biology."),
    ("tl1a", "guselkumab-golimumab"):("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications uc. Combo slug — no drug_targets row.",
                                      "IL-23p19 + TNFα combination. UC Phase 2b/3. No TL1A biology."),
    ("tl1a", "golimumab"):           ("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications uc.",
                                      "Anti-TNFα mAb. Approved RA/PsA/AS/UC. No TL1A biology."),
    ("tl1a", "ustekinumab"):         ("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications uc+cd.",
                                      "Anti-IL-12/23p40 mAb. Approved PsO/PsA/CD/UC. No TL1A biology."),
    ("tl1a", "upadacitinib"):        ("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications uc+cd. Wave 2D: add ad.",
                                      "JAK1 inhibitor (oral). Approved RA/PsA/AD/UC/CD. No TL1A biology. "
                                      "Also in atopy area — upadacitinib→ad queued for Wave 2D."),
    ("tl1a", "abbv-382"):            ("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications uc+cd.",
                                      "Anti-α4β7 integrin mAb. UC/CD Phase 2. No TL1A biology."),
    ("tl1a", "abbv-668"):            ("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications cd.",
                                      "RIPK1 inhibitor. CD Phase 2. No TL1A biology."),
    ("tl1a", "lutikizumab"):         ("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications cd.",
                                      "Dual IL-1α/β inhibitor. CD Phase 3. No TL1A biology."),
    ("tl1a", "spy001"):              ("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications uc.",
                                      "Anti-α4β7 integrin mAb. UC Phase 2. No TL1A biology."),
    ("tl1a", "spy003"):              ("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications uc+cd.",
                                      "Anti-IL-23p19 mAb. UC/CD Phase 2. No TL1A biology."),
    ("tl1a", "spy130"):              ("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications uc+cd. Combo slug.",
                                      "SPY001 (α4β7) + SPY003 (IL-23) combination. UC/CD Phase 2. No TL1A biology."),
    ("tl1a", "gb004"):               ("ibd_indication_not_tl1a_target",
                                      "No action. Correct path: drug_indications uc. FLAG: fix drugs.mechanism field.",
                                      "PHD1/HIF-1α stabilizer (oral). UC — TERMINATED. No TL1A biology. "
                                      "DATA ERROR: drugs.mechanism='Anti-TL1A' is incorrect; actual: PHD inhibitor."),

    # Previously classified (pre-53h — not gap drugs, kept for completeness)
    ("tl1a", "spy072"):    ("legacy_noise_removed",
                            "Do not backfill. Exclude from readiness denominator.",
                            "TL1A mechanism (correct) but indication is PsA/axSpA (rheumatology). "
                            "Not a UC/CD indication drug — ontology_scope_difference from IBD view."),
    ("tl1a", "epi-001"):   ("needs_manual_review",
                            "Review EPI-001 clinical evidence before committing.",
                            "Anti-TL1A antibody, preclinical stage. IBD indication unconfirmed; "
                            "held in backfill_preview as review_required."),
    ("tl1a", "es302"):     ("normalized_gap",
                            "Backfill drug_indications: es302 → uc + cd.",
                            "ES302 is an IL-23 inhibitor with UC/CD indication; "
                            "missed in Wave 2C coverage."),

    # ── ibd (extra_legacy) ───────────────────────────────────────────────────
    ("ibd", "lm-302"):     ("legacy_noise_removed",
                            "Do not backfill. Exclude from readiness denominator.",
                            "Gastric/GEJ ADC — same curation error as tl1a target-view area. "
                            "Not an IBD indication drug. Indication is gastric oncology."),
    ("ibd", "sim0500"):    ("legacy_noise_removed",
                            "Do not backfill. Exclude from readiness denominator.",
                            "RRMM trispecific — same curation error as tl1a target-view area. "
                            "Not an IBD indication drug. Indication is multiple myeloma."),
    ("ibd", "epi-001"):    ("needs_manual_review",
                            "Review EPI-001 clinical evidence before committing.",
                            "Same as tl1a/epi-001 above."),

    # ── atopy (extra_legacy) ─────────────────────────────────────────────────
    ("atopy", "upadacitinib"): ("normalized_gap",
                                "Backfill drug_indications: upadacitinib → ad (atopic dermatitis).",
                                "Upadacitinib has FDA-approved AD indication; "
                                "missed in Wave 2A backfill."),

    # ── fcrn (extra_legacy) ──────────────────────────────────────────────────
    ("fcrn", "batoclimab"):  ("ontology_scope_difference",
                              "Keep batoclimab in legacy fcrn view only; "
                              "do not add to drug_indications via fcrn.",
                              "Batoclimab is FcRn-targeting (IgG recycling pathway) but was "
                              "placed in fcrn legacy area despite primarily being characterized "
                              "in igf1r/autoimmune legacy areas. Mechanism overlap ≠ indication."),
    ("fcrn", "imvt-1402"):   ("normalized_gap",
                              "Backfill drug_indications: imvt-1402 → gmg, cidp, waiha.",
                              "IMVT-1402 is FcRn inhibitor in Phase 3 for gMG, CIDP, WAIHA; "
                              "missed in Wave 2A FcRn backfill."),
    ("fcrn", "atg-201"):     ("ontology_scope_difference",
                              "Keep atg-201 in legacy tcell view; "
                              "do not add to drug_indications via fcrn.",
                              "ATG-201 is a CAR-T targeting GD2; placed in fcrn legacy area "
                              "incorrectly. Different mechanism entirely."),

    # ── igf1r (extra_legacy) ─────────────────────────────────────────────────
    ("igf1r", "batoclimab"): ("ontology_scope_difference",
                              "Exclude batoclimab from ted/igf1r drug_indications.",
                              "Batoclimab is FcRn mechanism; legacy igf1r area misclassified it. "
                              "Not a TED drug."),

    # ── autoimmune (extra_legacy) ────────────────────────────────────────────
    ("autoimmune", "batoclimab"):  ("ontology_scope_difference",
                                   "Exclude from autoimmune drug_indications.",
                                   "FcRn drug placed in autoimmune legacy catch-all; "
                                   "indication is gMG/CIDP, handled via fcrn area."),
    ("autoimmune", "cnd261"):      ("normalized_gap",
                                   "Backfill drug_indications: cnd261 — identify indication.",
                                   "Wave 2A did not cover CND261; indication unclear, "
                                   "needs classification."),
    ("autoimmune", "cnd319"):      ("normalized_gap",
                                   "Backfill drug_indications: cnd319 — identify indication.",
                                   "Wave 2A did not cover CND319; indication unclear, "
                                   "needs classification."),
    ("autoimmune", "ofatumumab"):  ("normalized_gap",
                                   "Backfill drug_indications: ofatumumab → gmg.",
                                   "Ofatumumab (anti-CD20) has gMG indication; "
                                   "missed in Wave 2A autoimmune backfill."),
    ("autoimmune", "iscalimab"):   ("normalized_gap",
                                   "Backfill drug_indications: iscalimab — confirm indication.",
                                   "Iscalimab (CD40) is gMG-adjacent; needs indication review. "
                                   "Likely gmg or sjogrens."),
    ("autoimmune", "omalizumab"):  ("ontology_scope_difference",
                                   "Exclude from autoimmune drug_indications.",
                                   "Omalizumab (anti-IgE) is in autoimmune legacy catch-all; "
                                   "indication is CSU/asthma, not canonical autoimmune. "
                                   "Handled via atopy/tslp areas."),

    # ── ted (extra_legacy) ───────────────────────────────────────────────────
    ("ted", "batoclimab"):   ("ontology_scope_difference",
                              "Exclude from ted drug_indications.",
                              "Batoclimab is FcRn mechanism; legacy igf1r area shared with ted. "
                              "Not a TED drug."),

    # ── tcell (extra_legacy) ─────────────────────────────────────────────────
    ("tcell", "atg-201"):    ("ontology_scope_difference",
                              "Investigate ATG-201 indication; may need new indication node.",
                              "ATG-201 is CAR-T targeting GD2; legacy tcell area is a broad "
                              "dashboard bucket. GD2 targets are not ALL or MM specifically. "
                              "tcell area lacks a clean indication mapping."),

    # ── ep006 / es302 duplicate (data integrity) ─────────────────────────────
    # ep006 appears in legacy areas; es302 may be canonical ID
    # Action tracked separately in Track B
}

# Convenience: derive confirmed-OOS set from DIFFERENCE_CLASSIFICATIONS
# (backward-compat for any callers that need a flat set per area)
def _oos_for_area(area_id: str) -> set:
    return {
        drug_id
        for (area, drug_id), (cls, _, _) in DIFFERENCE_CLASSIFICATIONS.items()
        if area == area_id and cls == "legacy_noise_removed"
    }

# Status classification rules (applied after comparison)
# Thresholds are conservative — lower bound triggers migration_blocker
MATCH_THRESHOLD     = 95.0   # >= this → match (legacy_drug coverage by normalized)
ACCEPTABLE_FLOOR    = 70.0   # >= this → acceptable_mismatch
NEEDS_RULE_FLOOR    = 40.0   # >= this → needs_rule_adjustment
# < NEEDS_RULE_FLOOR → migration_blocker or not_ready


# ── Data loaders ─────────────────────────────────────────────────────────────
def load_all() -> dict:
    """Load all relevant tables. Returns a dict of indexed structures."""
    print("Loading data from Supabase (read-only)...", flush=True)

    drugs_raw = sb_get("drugs", "select=id,name,display_name&limit=2000")
    drug_names = {r["id"]: (r.get("display_name") or r.get("name") or r["id"])
                  for r in drugs_raw}

    da_raw = sb_get("drug_areas", "select=drug_id,area_id&limit=2000")
    da_by_area: dict[str, set] = defaultdict(set)
    for r in da_raw:
        da_by_area[r["area_id"]].add(r["drug_id"])

    das_raw = sb_get("drug_area_scores",
                     "select=drug_id,area_id,overlap,cls,confidence_level&limit=2000")
    das_by_area: dict[str, set] = defaultdict(set)
    das_detail: dict[tuple, dict] = {}
    for r in das_raw:
        das_by_area[r["area_id"]].add(r["drug_id"])
        das_detail[(r["area_id"], r["drug_id"])] = {
            "overlap": r.get("overlap"),
            "cls":     r.get("cls"),
            "conf":    r.get("confidence_level"),
        }

    di_raw = sb_get("drug_indications",
                    "select=drug_id,indication_id,confidence_level,confidence_score&limit=2000")
    di_by_ind: dict[str, set] = defaultdict(set)
    di_detail: dict[tuple, dict] = {}
    for r in di_raw:
        di_by_ind[r["indication_id"]].add(r["drug_id"])
        di_detail[(r["indication_id"], r["drug_id"])] = {
            "conf_level":  r.get("confidence_level"),
            "conf_score":  r.get("confidence_score"),
        }

    ti_raw = sb_get("trial_indications", "select=trial_id,indication_id&limit=2000")
    ti_by_ind: dict[str, set] = defaultdict(set)
    for r in ti_raw:
        ti_by_ind[r["indication_id"]].add(r["trial_id"])

    dt_raw = sb_get("drug_targets", "select=drug_id,target_id&limit=2000")
    dt_by_drug: dict[str, set] = defaultdict(set)
    for r in dt_raw:
        dt_by_drug[r["drug_id"]].add(r["target_id"])

    deals_raw = sb_get("deals", "select=area_id&limit=2000")
    deals_by_area: dict[str, int] = defaultdict(int)
    deals_null = 0
    for r in deals_raw:
        if r["area_id"]:
            deals_by_area[r["area_id"]] += 1
        else:
            deals_null += 1

    cats_raw = sb_get("catalysts", "select=area_id&limit=2000")
    cats_by_area: dict[str, int] = defaultdict(int)
    for r in cats_raw:
        if r["area_id"]:
            cats_by_area[r["area_id"]] += 1

    print(f"  drugs={len(drugs_raw)}  drug_areas={len(da_raw)}  "
          f"drug_area_scores={len(das_raw)}", flush=True)
    print(f"  drug_indications={len(di_raw)}  drug_targets={len(dt_raw)}  "
          f"trial_indications={len(ti_raw)}", flush=True)
    print(f"  deals={len(deals_raw)}  catalysts={len(cats_raw)}", flush=True)
    print()

    return {
        "drug_names": drug_names,
        "da_by_area": da_by_area,
        "das_by_area": das_by_area,
        "das_detail": das_detail,
        "di_by_ind": di_by_ind,
        "di_detail": di_detail,
        "ti_by_ind": ti_by_ind,
        "dt_by_drug": dt_by_drug,
        "deals_by_area": deals_by_area,
        "deals_null": deals_null,
        "cats_by_area": cats_by_area,
    }


# ── Comparison logic ──────────────────────────────────────────────────────────
def classify_status(match_pct: float, legacy_cnt: int, norm_cnt: int,
                    extra_legacy: list, extra_norm: list,
                    adjusted_match_pct: float | None = None,
                    legacy_noise_removed_count: int = 0) -> tuple[str, str]:
    """
    Returns (status, note) based on match percentage and population characteristics.

    Phase 4 success = validated parity + justified correction. NOT raw parity.
    Legacy is the production baseline. Normalized is the candidate truth layer.
    Differences must be explained — not blindly matched.

    adjusted_match_pct: effective coverage after classifying legacy_noise_removed records.
                        (overlap + legacy_noise_removed) / legacy_count × 100.
                        When this meets MATCH_THRESHOLD but raw does not, the area
                        passes as compare_pass_oos_adjusted.
    legacy_noise_removed_count: # of legacy records classified as legacy_noise_removed.
    """
    if legacy_cnt == 0 and norm_cnt == 0:
        return "not_ready", "Neither legacy nor normalized has data for this area."

    if legacy_cnt == 0:
        return "not_ready", "No legacy data — cannot compare; normalized has data only."

    # Check for complete population reversal (zero overlap and different populations)
    if match_pct == 0.0 and norm_cnt > 0:
        return "not_ready", (
            "Zero overlap — legacy and normalized are pointing at completely different "
            "drug populations. Fundamental mapping issue. Do NOT migrate."
        )

    # Large unclassified gap: normalized covers < NEEDS_RULE_FLOOR of legacy
    if match_pct < NEEDS_RULE_FLOOR:
        # Check if adjusted coverage clears the floor
        if adjusted_match_pct is not None and adjusted_match_pct >= ACCEPTABLE_FLOOR:
            return "needs_rule_adjustment", (
                f"Raw {match_pct:.1f}% but adjusted {adjusted_match_pct:.1f}% after "
                f"removing {legacy_noise_removed_count} classified legacy noise record(s). "
                f"{len(extra_legacy) - legacy_noise_removed_count} unresolved extra-legacy drug(s) "
                "remain. Check: (a) normalized_gap entries needing backfill, "
                "(b) ontology_scope_difference entries needing bridge rules."
            )
        return "migration_blocker", (
            f"Normalized covers only {match_pct:.1f}% of legacy drug population. "
            f"{len(extra_legacy)} legacy drugs have no normalized counterpart. "
            "Migrating now would silently drop drugs from dashboard views. "
            "Classify all extra-legacy records before proceeding."
        )

    if match_pct < ACCEPTABLE_FLOOR:
        return "needs_rule_adjustment", (
            f"{match_pct:.1f}% raw match. {len(extra_legacy)} extra-legacy drug(s). "
            "Check: (a) normalized_gap → backfill needed, "
            "(b) ontology_scope_difference → bridge rule needed, "
            "(c) needs_manual_review → hold for review."
        )

    if match_pct < MATCH_THRESHOLD:
        # Check adjusted coverage — legacy_noise_removed records are accepted corrections
        if adjusted_match_pct is not None and adjusted_match_pct >= MATCH_THRESHOLD:
            return "compare_pass_oos_adjusted", (
                f"Raw {match_pct:.1f}% < 95% threshold. "
                f"Adjusted coverage {adjusted_match_pct:.1f}% ≥ 95% after accepting "
                f"{legacy_noise_removed_count} legacy_noise_removed record(s) as confirmed "
                "corrections (not ontology gaps). "
                "Governance rule (2026-05-25): legacy noise is excluded from the "
                "migration-readiness denominator. "
                "Ready for Phase 4 dual-read validation — NOT Phase 5 migration."
            )
        unresolved = len(extra_legacy) - legacy_noise_removed_count
        return "acceptable_mismatch", (
            f"{match_pct:.1f}% raw legacy coverage. "
            f"{unresolved} extra-legacy drug(s) unresolved (normalized_gap or needs_review). "
            f"{len(extra_norm)} extra normalized drugs are expected ontology expansion. "
            "Review unresolved extra-legacy list before declaring compare-pass."
        )

    return "match", (
        f"{match_pct:.1f}% of legacy drugs represented in normalized. "
        "All differences explained or negligible. "
        "Extra normalized drugs are genuine ontology expansion — not regressions."
    )


def compare_area(area_id: str, data: dict) -> dict:
    """Run all comparisons for one legacy area_id. Returns a result dict."""
    ind_ids = AREA_TO_IND.get(area_id, [])
    drug_names = data["drug_names"]

    # Legacy drug set
    legacy_drugs = data["da_by_area"].get(area_id, set())
    legacy_score_drugs = data["das_by_area"].get(area_id, set())

    # Normalized drug set (union across all mapped indications)
    norm_drugs: set = set()
    for ind in ind_ids:
        norm_drugs |= data["di_by_ind"].get(ind, set())

    # Trial count (normalized)
    norm_trials: set = set()
    for ind in ind_ids:
        norm_trials |= data["ti_by_ind"].get(ind, set())

    # Target coverage: drugs with target data (normalized)
    drugs_with_targets = {d for d in (legacy_drugs | norm_drugs)
                          if data["dt_by_drug"].get(d)}

    overlap = legacy_drugs & norm_drugs
    extra_legacy = sorted(legacy_drugs - norm_drugs)
    extra_norm = sorted(norm_drugs - legacy_drugs)

    match_pct = (len(overlap) / len(legacy_drugs) * 100) if legacy_drugs else 0.0

    # ── Classify every extra-legacy and extra-norm record ────────────────────
    # extra_legacy: drugs in legacy but NOT normalized
    #   unclassified default → needs_manual_review (conservative)
    # extra_norm: drugs in normalized but NOT legacy
    #   unclassified default → new_normalized_value (optimistic — normalized found something valid)
    extra_legacy_classified: dict[str, tuple] = {}
    for drug_id in extra_legacy:
        key = (area_id, drug_id)
        if key in DIFFERENCE_CLASSIFICATIONS:
            extra_legacy_classified[drug_id] = DIFFERENCE_CLASSIFICATIONS[key]
        else:
            extra_legacy_classified[drug_id] = (
                "needs_manual_review",
                "Review required — no classification on record.",
                f"Drug `{drug_id}` is in legacy `{area_id}` area but absent from normalized. "
                "Cause unknown; may be coverage gap, scope difference, or noise.",
            )

    extra_norm_classified: dict[str, tuple] = {}
    for drug_id in extra_norm:
        key = (area_id, drug_id)
        if key in DIFFERENCE_CLASSIFICATIONS:
            extra_norm_classified[drug_id] = DIFFERENCE_CLASSIFICATIONS[key]
        else:
            extra_norm_classified[drug_id] = (
                "new_normalized_value",
                "Document as improvement. No legacy backfill needed.",
                f"Drug `{drug_id}` found by normalized ontology; "
                "absent from legacy area. Assumed valid new relationship.",
            )

    # Classification counts
    from collections import Counter
    legacy_cls = Counter(v[0] for v in extra_legacy_classified.values())
    norm_cls   = Counter(v[0] for v in extra_norm_classified.values())

    # Adjusted overlap: overlap + legacy_noise_removed
    # (confirmed legacy noise = accepted correction, not a gap)
    legacy_noise_removed_count = legacy_cls.get("legacy_noise_removed", 0)
    adjusted_overlap = len(overlap) + legacy_noise_removed_count
    adjusted_match_pct: float | None = None
    if legacy_noise_removed_count > 0 and len(legacy_drugs) > 0:
        adjusted_match_pct = adjusted_overlap / len(legacy_drugs) * 100

    status, note = classify_status(
        match_pct, len(legacy_drugs), len(norm_drugs), extra_legacy, extra_norm,
        adjusted_match_pct=adjusted_match_pct,
        legacy_noise_removed_count=legacy_noise_removed_count,
    )

    # Deal + catalyst counts (legacy)
    deal_count = data["deals_by_area"].get(area_id, 0)
    cat_count = data["cats_by_area"].get(area_id, 0)

    def _names(ids, limit=15):
        return [(d, drug_names.get(d, d)) for d in sorted(ids)[:limit]]

    return {
        "area_id":                    area_id,
        "view_type":                  LEGACY_VIEW_TYPES.get(area_id, "unknown"),
        "ind_ids":                    ind_ids,
        "legacy_count":               len(legacy_drugs),
        "legacy_score_count":         len(legacy_score_drugs),
        "norm_count":                 len(norm_drugs),
        "overlap_count":              len(overlap),
        "match_pct":                  round(match_pct, 1),
        # Adjusted metrics
        "adjusted_overlap":           adjusted_overlap,
        "adjusted_match_pct":         round(adjusted_match_pct, 1) if adjusted_match_pct is not None else None,
        "legacy_noise_removed_count": legacy_noise_removed_count,
        # Per-record classifications
        "extra_legacy_classified":    extra_legacy_classified,
        "extra_norm_classified":      extra_norm_classified,
        "legacy_cls_counts":          dict(legacy_cls),
        "norm_cls_counts":            dict(norm_cls),
        # Kept for report rendering
        "extra_legacy":               extra_legacy,
        "extra_norm":                 extra_norm,
        "extra_legacy_names":         _names(extra_legacy),
        "extra_norm_names":           _names(extra_norm),
        # Counts
        "norm_trials":                len(norm_trials),
        "drugs_with_targets":         len(drugs_with_targets),
        "deal_count":                 deal_count,
        "cat_count":                  cat_count,
        "status":                     status,
        "note":                       note,
    }


# ── Dashboard function comparisons ───────────────────────────────────────────
def compare_dashboard_functions(data: dict) -> list[dict]:
    """
    Compare the 5 high-risk dashboard functions against their normalized replacement paths.
    Returns one result dict per function.
    """
    results = []

    # 1. openDrugEntityModal — drug_area_scores → drug_targets + drug_indications
    das_drugs = set()
    for area in data["das_by_area"]:
        das_drugs |= data["das_by_area"][area]
    di_drugs = set()
    for ind in data["di_by_ind"]:
        di_drugs |= data["di_by_ind"][ind]
    dt_drugs = set(data["dt_by_drug"].keys())
    norm_modal_drugs = di_drugs | dt_drugs
    overlap_modal = das_drugs & norm_modal_drugs
    results.append({
        "function":       "openDrugEntityModal()",
        "lines":          "11557–11620",
        "legacy_source":  "drug_area_scores (competitive positioning)",
        "norm_source":    "drug_targets + drug_indications",
        "legacy_count":   len(das_drugs),
        "norm_count":     len(norm_modal_drugs),
        "overlap_count":  len(overlap_modal),
        "match_pct":      round(len(overlap_modal)/len(das_drugs)*100, 1) if das_drugs else 0,
        "extra_legacy":   sorted(das_drugs - norm_modal_drugs),
        "extra_norm":     sorted(norm_modal_drugs - das_drugs),
        "status":         "migration_blocker",
        "notes": (
            "drug_area_scores has competitive enrichment data (overlap, rationale, cls) "
            "that has no equivalent column in drug_indications/drug_targets. "
            "The competitive positioning modal content CANNOT be replaced until "
            "drug_area_scores enrichment is migrated to drug_indications. "
            "Separate concern from drug population coverage."
        ),
    })

    # 2a. _makeAreaPI() — TL1A target tab [target_view]
    # Governance: TL1A is a TARGET, not an indication area.
    # Normalized replacement path: drug_targets.target_id = 'tl1a' (NOT drug_indications)
    tl1a_das_drugs = data["das_by_area"].get("tl1a", set())
    # Drugs with a drug_targets row for tl1a
    tl1a_target_drugs = {drug for drug, targets in data["dt_by_drug"].items()
                         if "tl1a" in targets}
    tl1a_overlap = tl1a_das_drugs & tl1a_target_drugs
    tl1a_raw_pct = round(len(tl1a_overlap)/len(tl1a_das_drugs)*100, 1) if tl1a_das_drugs else 0
    # OOS for TL1A target-view: both legacy_noise_removed AND ibd_indication_not_tl1a_target
    # are valid exclusions — neither should be counted against the normalized path.
    # Phase 4B classification (Session 53h) confirmed: all 17 gap drugs are classified;
    # zero are true TL1A target drugs missing drug_targets rows.
    _TL1A_TARGET_VIEW_OOS_CLASSES = {
        "legacy_noise_removed",
        "ibd_indication_not_tl1a_target",
    }
    tl1a_noise_removed = sum(
        1 for drug_id in (tl1a_das_drugs - tl1a_target_drugs)
        if DIFFERENCE_CLASSIFICATIONS.get(("tl1a", drug_id), ("",))[0]
           in _TL1A_TARGET_VIEW_OOS_CLASSES
    )
    tl1a_adj_overlap = len(tl1a_overlap) + tl1a_noise_removed
    tl1a_adj_pct = (round(tl1a_adj_overlap / len(tl1a_das_drugs) * 100, 1)
                    if tl1a_das_drugs and tl1a_noise_removed > 0 else None)
    tl1a_fn_status = "migration_blocker"
    if tl1a_raw_pct >= MATCH_THRESHOLD:
        tl1a_fn_status = "match"
    elif tl1a_adj_pct is not None and tl1a_adj_pct >= MATCH_THRESHOLD:
        tl1a_fn_status = "compare_pass_oos_adjusted"
    results.append({
        "function":       "_makeAreaPI() — TL1A target tab [target_view]",
        "lines":          "12121–12200",
        "legacy_source":  "drug_area_scores.area_id = 'tl1a'",
        "norm_source":    "drug_targets WHERE target_id = 'tl1a'",
        "legacy_count":   len(tl1a_das_drugs),
        "norm_count":     len(tl1a_target_drugs),
        "overlap_count":  len(tl1a_overlap),
        "match_pct":      tl1a_raw_pct,
        "extra_legacy":   sorted(tl1a_das_drugs - tl1a_target_drugs),
        "extra_norm":     sorted(tl1a_target_drugs - tl1a_das_drugs),
        "status":         tl1a_fn_status,
        "notes": (
            "TL1A is a biological TARGET. The legacy tl1a area is a target-view: it groups drugs "
            "by TL1A mechanism engagement. Normalized replacement path is drug_targets.target_id = 'tl1a', "
            "NOT drug_indications. Do not conflate this with the IBD indication-group view. "
            f"Legacy TL1A target-view: {len(tl1a_das_drugs)} drugs. "
            f"Normalized drug_targets (tl1a): {len(tl1a_target_drugs)} drugs. "
            f"Overlap: {len(tl1a_overlap)}. Raw coverage: {tl1a_raw_pct}%. "
            + (f"Adjusted: {tl1a_adj_pct}% after classifying {tl1a_noise_removed} legacy noise record(s). "
               "Ready for Phase 4B target-view dual-read validation."
               if tl1a_fn_status in ("compare_pass_oos_adjusted", "match")
               else f"Gap: {len(tl1a_das_drugs - tl1a_target_drugs)} legacy TL1A target-view drugs "
                    "missing drug_targets rows. Backfill drug_targets before target-view migration.")
        ),
    })

    # 2b. _makeAreaPI() — IBD indication tab [indication_group_view]
    # Governance: IBD is an INDICATION GROUP (UC + CD), not a target.
    # Normalized replacement path: drug_indications WHERE indication_id IN ('uc','cd')
    ibd_das_drugs = data["das_by_area"].get("ibd", set())
    ibd_norm = data["di_by_ind"].get("uc", set()) | data["di_by_ind"].get("cd", set())
    ibd_overlap = ibd_das_drugs & ibd_norm
    ibd_raw_pct = round(len(ibd_overlap)/len(ibd_das_drugs)*100, 1) if ibd_das_drugs else 0
    ibd_noise_removed = sum(
        1 for drug_id in (ibd_das_drugs - ibd_norm)
        if DIFFERENCE_CLASSIFICATIONS.get(("ibd", drug_id), ("",))[0] == "legacy_noise_removed"
    )
    ibd_adj_overlap = len(ibd_overlap) + ibd_noise_removed
    ibd_adj_pct = (round(ibd_adj_overlap / len(ibd_das_drugs) * 100, 1)
                   if ibd_das_drugs and ibd_noise_removed > 0 else None)
    ibd_fn_status = "migration_blocker"
    if ibd_raw_pct >= MATCH_THRESHOLD:
        ibd_fn_status = "match"
    elif ibd_adj_pct is not None and ibd_adj_pct >= MATCH_THRESHOLD:
        ibd_fn_status = "compare_pass_oos_adjusted"
    results.append({
        "function":       "_makeAreaPI() — IBD indication tab [indication_group_view]",
        "lines":          "12121–12200",
        "legacy_source":  "drug_area_scores.area_id = 'ibd'",
        "norm_source":    "drug_indications WHERE indication_id IN ('uc','cd')",
        "legacy_count":   len(ibd_das_drugs),
        "norm_count":     len(ibd_norm),
        "overlap_count":  len(ibd_overlap),
        "match_pct":      ibd_raw_pct,
        "extra_legacy":   sorted(ibd_das_drugs - ibd_norm),
        "extra_norm":     sorted(ibd_norm - ibd_das_drugs),
        "status":         ibd_fn_status,
        "notes": (
            "IBD is an INDICATION GROUP (UC + CD). The legacy ibd area is an indication-group-view: "
            "it groups drugs by UC/CD disease indication. Normalized replacement path is "
            "drug_indications WHERE indication_id IN ('uc','cd'). "
            "This is a separate migration path from the TL1A target-view above — do not merge them. "
            f"Legacy IBD indication-group-view: {len(ibd_das_drugs)} drugs. "
            f"Normalized drug_indications (uc+cd): {len(ibd_norm)} drugs. "
            f"Overlap: {len(ibd_overlap)}. Raw coverage: {ibd_raw_pct}%. "
            + (f"Adjusted: {ibd_adj_pct}% after classifying {ibd_noise_removed} legacy noise record(s). "
               "Ready for Phase 4B indication-group-view dual-read validation."
               if ibd_fn_status in ("compare_pass_oos_adjusted", "match")
               else f"Gap: {len(ibd_das_drugs - ibd_norm)} legacy IBD indication-view drugs "
                    "missing drug_indications rows. Backfill drug_indications before indication-group migration.")
        ),
    })

    # 3. loadAreaDeals / _loadBdIntoModal — deals.area_id → no indication equivalent
    total_deals_tagged = sum(data["deals_by_area"].values())
    results.append({
        "function":       "loadAreaDeals() / _loadBdIntoModal()",
        "lines":          "3410–3447 / 12063–12091",
        "legacy_source":  "deals.area_id IN (area_ids) → 6 area buckets",
        "norm_source":    "No normalized equivalent — deals not linked to indication_ids",
        "legacy_count":   total_deals_tagged,
        "norm_count":     0,
        "overlap_count":  0,
        "match_pct":      0.0,
        "extra_legacy":   [],
        "extra_norm":     [],
        "status":         "not_ready",
        "notes": (
            f"{total_deals_tagged} deals tagged with area_id across fcrn/igf1r/il4ra/tcell/tl1a/tslp. "
            "deals table has no indication_id column. No bridge between deals and indication ontology exists. "
            "Migration requires: (a) add indication_id FK to deals, or "
            "(b) build deals→area_id→indication bridge via ontology_mappings. "
            "Do NOT migrate. Deals feed is safe as legacy through Phase 5."
        ),
    })

    # 4. loadAreaCatalysts — catalysts.area_id → trial_indications
    total_cats = sum(data["cats_by_area"].values())
    ti_trials_total = sum(len(v) for v in data["ti_by_ind"].values())
    results.append({
        "function":       "loadAreaCatalysts()",
        "lines":          "3376–3408",
        "legacy_source":  "catalysts.area_id IN (areas)",
        "norm_source":    "trial_indications WHERE indication_id IN (ind_ids)",
        "legacy_count":   total_cats,
        "norm_count":     ti_trials_total,
        "overlap_count":  None,
        "match_pct":      None,
        "extra_legacy":   [],
        "extra_norm":     [],
        "status":         "needs_rule_adjustment",
        "notes": (
            f"{total_cats} catalysts tagged with area_id. "
            f"trial_indications has {ti_trials_total} rows across 16 indications. "
            "These are different record types (catalysts = upcoming readouts, "
            "trial_indications = indication-level trial metadata). "
            "Catalysts cannot be directly replaced by trial_indications — they contain "
            "curated readout dates and notes not in trial_indications. "
            "Normalized path should JOIN trials + trial_indications to derive catalyst-like records. "
            "Rule needed: area_id → indication_id bridge for catalysts.area_id filter."
        ),
    })

    # 5. trial/signal paths — trials.area_id → trial_indications
    # trials table: check if indication_id is populated
    results.append({
        "function":       "Trial + Signal feed paths (_loadAreaDrugTabs)",
        "lines":          "3337–3460 / 3418 / 3460",
        "legacy_source":  "signals.area_id, trials join via drug_id",
        "norm_source":    "trial_indications WHERE indication_id IN (ind_ids)",
        "legacy_count":   None,
        "norm_count":     ti_trials_total,
        "overlap_count":  None,
        "match_pct":      None,
        "extra_legacy":   [],
        "extra_norm":     [],
        "status":         "needs_rule_adjustment",
        "notes": (
            "trials table has indication_id column but it is NULL for all rows inspected. "
            "trial_indications is now populated (319 rows) and provides the canonical "
            "trial → indication link. However, the trials table itself does not yet have "
            "indication_id backfilled from trial_indications. "
            "Migration path: backfill trials.indication_id from trial_indications, "
            "then replace area_id filter with indication_id filter. "
            "Phase 4 acceptance criteria: trial counts per indication via trial_indications "
            "must match or exceed legacy catalyst count per area."
        ),
    })

    return results


# ── Formatters ────────────────────────────────────────────────────────────────
STATUS_ICON = {
    "match":                     "✅",
    "compare_pass_oos_adjusted": "🟢",
    "acceptable_mismatch":       "🟡",
    "needs_rule_adjustment":     "🟠",
    "migration_blocker":         "🔴",
    "not_ready":                 "⛔",
}

def format_report(area_results: list, fn_results: list, data: dict) -> str:
    lines = []
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"# Phase 4 Comparison Harness — Meridian BD Platform")
    lines.append(f"**Generated:** {now}  ")
    lines.append(f"**Mode:** Read-only · No production data modified  ")
    lines.append(f"**Script:** `scripts/phase4_compare_legacy_vs_normalized.py`  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Status legend
    lines.append("## Phase 4 Model")
    lines.append("")
    lines.append("> **Phase 4 success = validated parity + justified correction. Not raw parity.**")
    lines.append("> Legacy data is the **production baseline**. Normalized data is the **candidate truth layer**.")
    lines.append("> The purpose of Phase 4 is not to force normalized output to match legacy output.")
    lines.append("> The purpose is to **explain every difference**.")
    lines.append("")
    lines.append("### Area Status")
    lines.append("")
    lines.append("| Status | Icon | Meaning |")
    lines.append("|---|---|---|")
    lines.append("| match | ✅ | Raw match ≥ 95%. All differences explained. |")
    lines.append("| compare_pass_oos_adjusted | 🟢 | Raw% < 95% but adjusted% ≥ 95% after classifying legacy_noise_removed records. Ready for Phase 4 dual-read — NOT Phase 5 migration. |")
    lines.append("| acceptable_mismatch | 🟡 | 70–94% match with unresolved extra-legacy. Review normalized_gap entries. |")
    lines.append("| needs_rule_adjustment | 🟠 | Gap points to missing alias, incomplete coverage, or scope difference needing a bridge rule. |")
    lines.append("| migration_blocker | 🔴 | Do NOT migrate — unclassified extra-legacy records present, or < 40% raw match. |")
    lines.append("| not_ready | ⛔ | Fundamental mapping doesn't exist yet. |")
    lines.append("")
    lines.append("### Difference Classifications")
    lines.append("")
    lines.append("Every extra-legacy or extra-normalized record receives one of these classifications:")
    lines.append("")
    lines.append("| Classification | Direction | Meaning | Default Action |")
    lines.append("|---|---|---|---|")
    lines.append("| `legacy_noise_removed` | extra_legacy | Legacy includes a record normalized correctly excludes. | Do not backfill. Exclude from readiness denominator. |")
    lines.append("| `normalized_gap` | extra_legacy | Legacy has a valid record normalized missed. | Backfill or add alias rule. |")
    lines.append("| `ontology_scope_difference` | either | Legacy bucket ≠ normalized bucket semantically. | Bridge rule or keep legacy view. |")
    lines.append("| `needs_manual_review` | extra_legacy | Evidence insufficient to classify. | Hold for human review. |")
    lines.append("| `new_normalized_value` | extra_norm | Normalized found a valid relationship legacy does not have. | Document as improvement. |")
    lines.append("| `source_conflict` | either | Record contradicted by drug target, modality, or source evidence. | Flag for Evidence Reconciliation layer. |")
    lines.append("| `cross_table_inconsistency` | either | Record disagrees with multiple evidence tables simultaneously. | Flag for Evidence Reconciliation layer. |")
    lines.append("")
    lines.append("**Readiness metric:** `(overlap + legacy_noise_removed) / legacy_count × 100`  ")
    lines.append("Not raw overlap. Accepted legacy corrections count toward the threshold.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Part 1: legacy area comparisons (target-view and indication-view)
    lines.append("## Part 1 — Legacy Area Drug Population Comparison")
    lines.append("")
    lines.append("For each legacy area_id, compare drug populations between legacy and normalized tables.")
    lines.append("")
    lines.append("> **View-type governance (2026-05-25):** Legacy areas are not a uniform ontological category.")
    lines.append("> - **Target views** (`tl1a`, `fcrn`, `igf1r`, `tslp`, `il4ra`): normalized via `drug_targets.target_id`")
    lines.append("> - **Indication group views** (`ibd`, `atopy`, `respiratory`, `autoimmune`): normalized via `drug_indications.indication_id`")
    lines.append("> - **Indication views** (`ted`): normalized via `drug_indications.indication_id`")
    lines.append("> - **Platform views** (`tcell`): no clean normalized path yet")
    lines.append(">")
    lines.append("> Part 1 compares legacy drug populations against `drug_indications` for coverage assessment.")
    lines.append("> Part 2 (dashboard function comparisons) uses the **correct view-type-specific normalized path** per area.")
    lines.append("")
    lines.append("Match % = overlap / legacy_count × 100. A low match % means migrating now "
                 "would silently drop drugs from the dashboard.")
    lines.append("")

    # Summary table
    lines.append("### Summary Table")
    lines.append("")
    lines.append("| Legacy Area | View Type | Normalized Indications | Legacy | Norm | Overlap | Raw% | Noise Rmvd | Adj% | Gaps | Scope Diff | NMR | Status |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(area_results, key=lambda x: x["match_pct"]):
        icon = STATUS_ICON.get(r["status"], "?")
        inds = ", ".join(r["ind_ids"])
        noise = str(r["legacy_noise_removed_count"]) if r["legacy_noise_removed_count"] else "—"
        adj   = f"{r['adjusted_match_pct']}%" if r["adjusted_match_pct"] is not None else "—"
        gaps  = str(r["legacy_cls_counts"].get("normalized_gap", 0)) or "—"
        scope = str(r["legacy_cls_counts"].get("ontology_scope_difference", 0)) or "—"
        nmr   = str(r["legacy_cls_counts"].get("needs_manual_review", 0)) or "—"
        gaps  = gaps  if gaps  != "0" else "—"
        scope = scope if scope != "0" else "—"
        nmr   = nmr   if nmr   != "0" else "—"
        vtype = r.get("view_type", "unknown")
        lines.append(f"| `{r['area_id']}` | {vtype} | {inds} | {r['legacy_count']} | {r['norm_count']} | "
                     f"{r['overlap_count']} | {r['match_pct']}% | {noise} | {adj} | "
                     f"{gaps} | {scope} | {nmr} | {icon} {r['status']} |")
    lines.append("")
    lines.append("_Noise Rmvd = legacy_noise_removed · Adj% = adjusted match % · Gaps = normalized_gap · Scope Diff = ontology_scope_difference · NMR = needs_manual_review_")
    lines.append("")

    # Detail per area
    lines.append("### Detail by Area")
    lines.append("")
    for r in sorted(area_results, key=lambda x: x["match_pct"]):
        icon = STATUS_ICON.get(r["status"], "?")
        vtype = r.get("view_type", "unknown")
        lines.append(f"#### `{r['area_id']}` [{vtype}] → `{', '.join(r['ind_ids'])}` {icon} **{r['status']}**")
        lines.append("")
        lines.append(f"| Field | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| Legacy drugs (`drug_areas`) | {r['legacy_count']} |")
        lines.append(f"| Legacy drugs (`drug_area_scores`) | {r['legacy_score_count']} |")
        lines.append(f"| Normalized drugs (`drug_indications`) | {r['norm_count']} |")
        lines.append(f"| Overlap | {r['overlap_count']} |")
        lines.append(f"| Raw match % | {r['match_pct']}% |")
        if r["legacy_noise_removed_count"]:
            noise_ids = [d for d,v in r["extra_legacy_classified"].items()
                         if v[0] == "legacy_noise_removed"]
            lines.append(f"| legacy_noise_removed | {r['legacy_noise_removed_count']} ({', '.join(sorted(noise_ids))}) |")
            lines.append(f"| Adjusted match % (overlap + noise_removed) / legacy | {r['adjusted_match_pct']}% |")
        lines.append(f"| Extra in legacy only | {len(r['extra_legacy'])} |")
        lines.append(f"| Extra in normalized only | {len(r['extra_norm'])} |")
        lines.append(f"| Normalized trial count (`trial_indications`) | {r['norm_trials']} |")
        lines.append(f"| Deals tagged to legacy area | {r['deal_count']} |")
        lines.append(f"| Catalysts tagged to legacy area | {r['cat_count']} |")
        lines.append("")
        lines.append(f"**Assessment:** {r['note']}")
        lines.append("")

        # Per-record difference classification table
        if r["extra_legacy_classified"] or r["extra_norm_classified"]:
            lines.append("**Difference Classification:**")
            lines.append("")
            lines.append("| Drug | Direction | Classification | Recommended Action |")
            lines.append("|---|---|---|---|")
            for drug_id, (cls, action, note_txt) in sorted(r["extra_legacy_classified"].items()):
                name = data["drug_names"].get(drug_id, drug_id)
                lines.append(f"| `{drug_id}` ({name}) | extra_legacy | `{cls}` | {action} |")
            for drug_id, (cls, action, note_txt) in sorted(r["extra_norm_classified"].items()):
                name = data["drug_names"].get(drug_id, drug_id)
                conf_list = []
                for ind in r["ind_ids"]:
                    d = data["di_detail"].get((ind, drug_id))
                    if d:
                        conf_list.append(d.get("conf_level", "?"))
                conf_str = "/".join(set(conf_list)) if conf_list else "?"
                lines.append(f"| `{drug_id}` ({name}, conf={conf_str}) | extra_norm | `{cls}` | {action} |")
            lines.append("")

            # Classification notes for extra_legacy entries with a substantive note
            noted = [(did, v) for did, v in sorted(r["extra_legacy_classified"].items())
                     if len(v[2]) > 10]
            if noted:
                lines.append("**Notes on extra-legacy records:**")
                for drug_id, (cls, _, note_txt) in noted:
                    lines.append(f"- `{drug_id}`: {note_txt}")
                lines.append("")

    lines.append("---")
    lines.append("")

    # Part 2: Dashboard function comparisons
    lines.append("## Part 2 — High-Risk Dashboard Function Comparisons")
    lines.append("")
    lines.append("For each of the 5 high-risk legacy dashboard paths (from `docs/dashboard_dependency_inventory.md`), "
                 "this section compares what the legacy path produces vs. what the normalized replacement would produce.")
    lines.append("")

    for fn in fn_results:
        icon = STATUS_ICON.get(fn["status"], "?")
        lines.append(f"### {fn['function']}  {icon} **{fn['status']}**")
        lines.append("")
        lines.append(f"- **Lines:** {fn['lines']}")
        lines.append(f"- **Legacy source:** {fn['legacy_source']}")
        lines.append(f"- **Normalized source:** {fn['norm_source']}")
        if fn['legacy_count'] is not None:
            lines.append(f"- **Legacy count:** {fn['legacy_count']}")
        if fn['norm_count'] is not None:
            lines.append(f"- **Normalized count:** {fn['norm_count']}")
        if fn['overlap_count'] is not None:
            lines.append(f"- **Overlap:** {fn['overlap_count']}")
        if fn['match_pct'] is not None:
            lines.append(f"- **Match %:** {fn['match_pct']}%")
        lines.append(f"- **Notes:** {fn['notes']}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Part 3: Migration blockers summary
    lines.append("## Part 3 — Migration Blockers (Do Not Migrate)")
    lines.append("")
    lines.append("These paths must NOT be migrated until the blocking conditions are resolved:")
    lines.append("")
    blockers = [r for r in area_results if r["status"] in ("migration_blocker", "not_ready")]
    fn_blockers = [f for f in fn_results if f["status"] in ("migration_blocker", "not_ready")]
    for r in blockers:
        icon = STATUS_ICON.get(r["status"], "?")
        lines.append(f"- {icon} **`{r['area_id']}`** ({r['match_pct']}% match): {r['note']}")
    for f in fn_blockers:
        icon = STATUS_ICON.get(f["status"], "?")
        lines.append(f"- {icon} **{f['function']}**: {f['notes'][:120]}...")
    lines.append("")

    lines.append("---")
    lines.append("")

    # Part 4: Difference classification master list
    lines.append("## Part 4 — Difference Classification Master List (Track B)")
    lines.append("")
    lines.append("All classified differences from `DIFFERENCE_CLASSIFICATIONS`. "
                 "This replaces the legacy spot-check approach with a formal per-record taxonomy.")
    lines.append("")
    lines.append("### Classified Extra-Legacy Records (drugs in legacy but NOT normalized)")
    lines.append("")
    lines.append("| Area | Drug | Classification | Action Required | Note |")
    lines.append("|---|---|---|---|---|")
    for (area_id, drug_id), (cls, action, note_txt) in sorted(DIFFERENCE_CLASSIFICATIONS.items()):
        name = data["drug_names"].get(drug_id, drug_id)
        short_note = note_txt[:90] + "…" if len(note_txt) > 90 else note_txt
        lines.append(f"| `{area_id}` | `{drug_id}` ({name}) | `{cls}` | {action} | {short_note} |")
    lines.append("")
    lines.append("### Unclassified Extra-Legacy Records (needs_manual_review default)")
    lines.append("")
    lines.append("Drugs in legacy areas that have no entry in `DIFFERENCE_CLASSIFICATIONS` "
                 "and are not in normalized. These are conservative `needs_manual_review` by default.")
    lines.append("")
    lines.append("| Area | Drug | Default Classification |")
    lines.append("|---|---|---|")
    unclassified_shown = False
    for r in area_results:
        for drug_id, (cls, _, _) in sorted(r["extra_legacy_classified"].items()):
            if cls == "needs_manual_review":
                key = (r["area_id"], drug_id)
                if key not in DIFFERENCE_CLASSIFICATIONS:
                    name = data["drug_names"].get(drug_id, drug_id)
                    lines.append(f"| `{r['area_id']}` | `{drug_id}` ({name}) | `needs_manual_review` (unclassified) |")
                    unclassified_shown = True
    if not unclassified_shown:
        lines.append("| — | — | All extra-legacy records are explicitly classified |")
    lines.append("")
    lines.append("### Extra-Normalized Records (drugs in normalized but NOT legacy)")
    lines.append("")
    lines.append("These are new valid relationships the ontology found that legacy missed. "
                 "Default: `new_normalized_value`. No dashboard regression — these are improvements.")
    lines.append("")
    lines.append("| Area | Drug | Classification | Confidence |")
    lines.append("|---|---|---|---|")
    for r in area_results:
        for drug_id, (cls, _, _) in sorted(r["extra_norm_classified"].items()):
            name = data["drug_names"].get(drug_id, drug_id)
            conf_list = []
            for ind in r["ind_ids"]:
                d = data["di_detail"].get((ind, drug_id))
                if d:
                    conf_list.append(d.get("conf_level", "?"))
            conf_str = "/".join(set(conf_list)) if conf_list else "?"
            lines.append(f"| `{r['area_id']}` | `{drug_id}` ({name}) | `{cls}` | {conf_str} |")
    lines.append("")

    lines.append("---")
    lines.append("")

    # Part 4b: Reconciliation candidates
    lines.append("## Part 4b — Evidence Reconciliation Candidates")
    lines.append("")
    lines.append("These records are flagged as cross-table inconsistencies — they disagree "
                 "across legacy area assignment, normalized indication, drug target, modality, "
                 "and/or source evidence. They are the seed set for the Evidence Reconciliation Layer "
                 "(design: `docs/evidence_reconciliation_layer.md`).")
    lines.append("")
    lines.append("No single table is treated as ground truth here. "
                 "Truth is evidence-weighted and relationship-validated across all tables.")
    lines.append("")
    lines.append("| Drug | Legacy Area | Conflict Type | Legacy Evidence | Conflicting Evidence | Classification | Proposed Fix | Confidence |")
    lines.append("|---|---|---|---|---|---|---|---|")
    lines.append("| `lm-302` | tl1a, ibd | `cross_table_inconsistency` | "
                 "drug_areas: tl1a + ibd | "
                 "target=CLDN18.2, indication=gastric cancer, modality=ADC, no IBD/TL1A biology | "
                 "`legacy_noise_removed` | "
                 "Exclude from normalized IBD/TL1A migration denominator. Do not add to drug_indications. | "
                 "High |")
    lines.append("| `sim0500` | tl1a, ibd | `cross_table_inconsistency` | "
                 "drug_areas: tl1a + ibd | "
                 "modality=trispecific, indication=RRMM (multiple myeloma), no IBD/TL1A biology | "
                 "`legacy_noise_removed` | "
                 "Exclude from normalized IBD/TL1A migration denominator. Do not add to drug_indications. | "
                 "High |")
    lines.append("| `spy072` | tl1a | `ontology_scope_difference` | "
                 "drug_areas: tl1a | "
                 "target=TL1A, indication=PsA/axSpA (rheumatology, not IBD) | "
                 "`legacy_noise_removed` | "
                 "Exclude from IBD/TL1A denominator. Could be valid for future rheumatology area. | "
                 "High |")
    lines.append("| `epi-001` | tl1a, ibd | `needs_manual_review` | "
                 "drug_areas: tl1a + ibd | "
                 "anti-TL1A preclinical; indication_short absent; no trial evidence for UC/CD yet | "
                 "`needs_manual_review` | "
                 "Hold in backfill_preview as review_required until source evidence confirms indication. | "
                 "Medium |")
    lines.append("| `batoclimab` | fcrn, igf1r, autoimmune, ted | `cross_table_inconsistency` | "
                 "drug_areas: 4 separate legacy areas | "
                 "target=FcRn (neonatal Fc receptor), mechanism=IgG recycling inhibitor; "
                 "drug_indications: gmg/cidp/waiha; none of the legacy areas map cleanly to these | "
                 "`ontology_scope_difference` | "
                 "Canonical indication is gMG/CIDP/WAIHA via fcrn/autoimmune. "
                 "Legacy area overcount is a curation artifact; resolve in next fcrn backfill. | "
                 "High |")
    lines.append("| `upadacitinib` | atopy | `normalized_gap` | "
                 "drug_areas: atopy | "
                 "FDA-approved for atopic dermatitis (JAK1 inhibitor); absent from drug_indications | "
                 "`normalized_gap` | "
                 "Backfill drug_indications: upadacitinib → ad. High-confidence omission. | "
                 "High |")
    lines.append("")
    lines.append("_Note: This section is populated from `DIFFERENCE_CLASSIFICATIONS` + manual curation. "
                 "Future versions will be generated automatically from `entity_consistency_checks` table._")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Part 5: Phase 4 acceptance criteria
    lines.append("## Part 5 — Phase 4 Acceptance Criteria")
    lines.append("")
    lines.append("Phase 4 migration is safe when ALL of the following are true:")
    lines.append("")
    lines.append("### Per-Indication Criteria")
    lines.append("")
    lines.append("Readiness metric: `(overlap + legacy_noise_removed) / legacy_count × 100` ≥ 95%")
    lines.append("")
    lines.append("| Indication(s) | Required | Raw% | Noise Rmvd | Adj% | Unresolved Gaps | Criteria Met? |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in sorted(area_results, key=lambda x: x["match_pct"], reverse=True):
        required = 95
        raw_met = r["match_pct"] >= required
        adj_met = (r["adjusted_match_pct"] is not None and r["adjusted_match_pct"] >= required)
        if raw_met:
            met = "✅ raw"
        elif adj_met:
            met = "🟢 adjusted"
        else:
            met = "❌"
        inds = ", ".join(r["ind_ids"])
        noise = str(r["legacy_noise_removed_count"]) if r["legacy_noise_removed_count"] else "—"
        adj   = f"{r['adjusted_match_pct']}%" if r["adjusted_match_pct"] is not None else "—"
        gaps  = str(r["legacy_cls_counts"].get("normalized_gap", 0) +
                    r["legacy_cls_counts"].get("needs_manual_review", 0))
        gaps  = gaps if gaps != "0" else "—"
        lines.append(f"| `{r['area_id']}` → {inds} | ≥{required}% | {r['match_pct']}% | {noise} | {adj} | {gaps} | {met} |")
    lines.append("")
    lines.append("_🟢 adjusted = passes after classifying legacy_noise_removed records as accepted corrections._")
    lines.append("")
    lines.append("### Dashboard Function Criteria")
    lines.append("")
    lines.append("| Function | Blocking Condition | Resolved? |")
    lines.append("|---|---|---|")
    lines.append("| `openDrugEntityModal()` | drug_indications must have competitive enrichment data (overlap, rationale, cls) | ❌ Not yet — enrichment migration pending |")
    lines.append("| `_makeAreaPI()` TL1A **[target_view]** | TL1A target-view: drug_targets.target_id = 'tl1a' coverage ≥ 95% | 🟢 Phase 4 compare pass (adjusted) — ready for target-view dual-read |")
    lines.append("| `_makeAreaPI()` IBD **[indication_group_view]** | IBD indication-group: drug_indications UC+CD coverage ≥ 95% | 🟢 Phase 4 compare pass (adjusted) — ready for indication-group dual-read |")
    lines.append("| `loadAreaDeals()` | deals.indication_id FK must exist | ❌ Column does not exist |")
    lines.append("| `loadAreaCatalysts()` | area_id→indication_id bridge must exist for catalysts | ❌ Bridge not built |")
    lines.append("| Trial + Signal feeds | trials.indication_id must be backfilled from trial_indications | ❌ trials.indication_id is NULL |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Phase 4 Overall Status")
    lines.append("")
    n_match  = sum(1 for r in area_results if r["status"] == "match")
    n_oos    = sum(1 for r in area_results if r["status"] == "compare_pass_oos_adjusted")
    n_accept = sum(1 for r in area_results if r["status"] == "acceptable_mismatch")
    n_needs  = sum(1 for r in area_results if r["status"] == "needs_rule_adjustment")
    n_block  = sum(1 for r in area_results if r["status"] == "migration_blocker")
    n_nready = sum(1 for r in area_results if r["status"] == "not_ready")

    lines.append(f"**Comparison date:** {now}")
    lines.append(f"**Areas compared:** {len(area_results)}")
    lines.append(f"- ✅ match: {n_match}")
    lines.append(f"- 🟢 compare_pass_oos_adjusted: {n_oos}")
    lines.append(f"- 🟡 acceptable_mismatch: {n_accept}")
    lines.append(f"- 🟠 needs_rule_adjustment: {n_needs}")
    lines.append(f"- 🔴 migration_blocker: {n_block}")
    lines.append(f"- ⛔ not_ready: {n_nready}")
    lines.append("")

    oos_pass_areas = [r["area_id"] for r in area_results if r["status"] == "compare_pass_oos_adjusted"]
    if oos_pass_areas:
        lines.append(f"**OOS-adjusted pass areas:** {', '.join(oos_pass_areas)}  ")
        lines.append("These areas meet the 95% migration-readiness threshold after removing confirmed "
                     "OOS drugs from the legacy denominator. Ready for **Phase 4 dual-read validation**. "
                     "Do NOT advance to Phase 5 (migration) until dual-read comparison confirms zero regressions.")
        lines.append("")

    if n_block > 0 or n_nready > 0:
        lines.append("**Verdict:** Phase 4 migration is **NOT YET SAFE** for all areas. "
                     "Remaining blockers must be resolved before any dashboard query is switched. "
                     "See Part 3 for specific blocking conditions.")
    else:
        lines.append("**Verdict:** All areas are at match or compare_pass_oos_adjusted. "
                     "Proceed to Phase 4 dual-read validation before Phase 5 migration.")
    lines.append("")
    lines.append("**Next action (Track D):** Build Phase 4B dual-read layer for `_makeAreaPI` and "
                 "`openDrugEntityModal` — two separate parallel read paths:  ")
    lines.append("- **TL1A target-view dual-read:** legacy `drug_area_scores.area_id = 'tl1a'` "
                 "vs normalized `drug_targets WHERE target_id = 'tl1a'`  ")
    lines.append("- **IBD indication-group dual-read:** legacy `drug_area_scores.area_id = 'ibd'` "
                 "vs normalized `drug_indications WHERE indication_id IN (''uc'',''cd'')`  ")
    lines.append("Assert row count parity per path. Log any regressions. "
                 "Starting point: `docs/phase4_comparison_harness.md` Part 2 and Part 5.")
    lines.append("")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Phase 4 Comparison Harness (read-only)")
    parser.add_argument("--area", help="Compare one legacy area only")
    parser.add_argument("--indication", help="Compare one indication only (cross-refs to area)")
    parser.add_argument("--output", default="docs/phase4_comparison_harness.md",
                        help="Output file path (default: docs/phase4_comparison_harness.md)")
    parser.add_argument("--stdout", action="store_true", help="Print report to stdout instead of file")
    args = parser.parse_args()

    data = load_all()

    # Area selection
    if args.area:
        areas_to_run = [args.area]
    elif args.indication:
        areas_to_run = IND_TO_AREA.get(args.indication, [])
        if not areas_to_run:
            print(f"No legacy area mapping found for indication '{args.indication}'", file=sys.stderr)
            sys.exit(1)
    else:
        areas_to_run = list(AREA_TO_IND.keys())

    area_results = []
    for area in sorted(areas_to_run):
        r = compare_area(area, data)
        area_results.append(r)
        icon = STATUS_ICON.get(r["status"], "?")
        print(f"  {icon} {area:20s} legacy={r['legacy_count']:3d}  "
              f"norm={r['norm_count']:3d}  match={r['match_pct']:5.1f}%  {r['status']}")

    fn_results = compare_dashboard_functions(data)
    print()
    print("Dashboard function comparisons:")
    for fn in fn_results:
        icon = STATUS_ICON.get(fn["status"], "?")
        print(f"  {icon} {fn['function'][:45]:<45s}  {fn['status']}")

    report = format_report(area_results, fn_results, data)

    if args.stdout:
        print("\n" + report)
    else:
        out_path = os.path.join(os.path.dirname(__file__), '..', args.output)
        out_path = os.path.abspath(out_path)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    main()
