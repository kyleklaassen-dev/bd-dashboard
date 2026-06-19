#!/usr/bin/env python3
"""
seed_targets_data.py — curated target catalog for seed_targets.py (§3 split).

Pure data only (no imports of project code, no I/O): the canonical target list,
bispecific component mappings, the target-text→id lookup, and the uncertain-text
patterns. Extracted verbatim from seed_targets.py so the seeding logic stays small.
"""
from __future__ import annotations


# ══════════════════════════════════════════════════════════════════════════════
# CANONICAL TARGET CATALOG
# ══════════════════════════════════════════════════════════════════════════════
#
# Built from auditing all distinct drugs.target values in the live DB (2026-05-24).
# Each entry: {id, name, alt_names, target_class, pathway, notes}
#
# Bispecific targets are included as their own entries with target_class='bispecific_pair'.
# They also have component mappings in BISPECIFIC_COMPONENTS below.

CANONICAL_TARGETS: list[dict] = [
    # ── TL1A / TNFSF15 ──────────────────────────────────────────────────────
    {
        "id":           "tl1a",
        "name":         "TL1A/TNFSF15",
        "alt_names":    ["TL1A", "TNFSF15", "VEGI", "DR3 ligand", "TL1A/TNFSF15"],
        "target_class": "cytokine",
        "pathway":      "tl1a_ibd",
        "notes":        "TNF superfamily member 15; primary driver of mucosal inflammation in IBD",
    },
    # ── IL-23 (p19 subunit) ──────────────────────────────────────────────────
    {
        "id":           "il23p19",
        "name":         "IL-23p19",
        "alt_names":    ["IL-23p19", "IL-23", "IL23p19", "IL-23 (p19)", "IL-23A"],
        "target_class": "cytokine",
        "pathway":      "il23_th17",
        "notes":        "p19 subunit of IL-23; selective target (spares IL-12/p40)",
    },
    # ── IL-12/IL-23 shared subunit ───────────────────────────────────────────
    {
        "id":           "il12_23p40",
        "name":         "IL-12/23p40",
        "alt_names":    ["IL-12/23p40", "IL-23p40", "IL-12p40"],
        "target_class": "cytokine",
        "pathway":      "il23_th17",
        "notes":        "Shared p40 subunit of both IL-12 and IL-23; ustekinumab mechanism",
    },
    # ── FcRn ────────────────────────────────────────────────────────────────
    {
        "id":           "fcrn",
        "name":         "FcRn (neonatal Fc receptor)",
        "alt_names":    ["FcRn", "FCGRT", "neonatal Fc receptor", "FcRn (FCGRT)"],
        "target_class": "cytokine_receptor",
        "pathway":      "fcrn_igg_recycling",
        "notes":        "IgG half-life regulator; blocking → IgG catabolism → Ig reduction for autoimmune",
    },
    # ── TSLP ────────────────────────────────────────────────────────────────
    {
        "id":           "tslp",
        "name":         "TSLP",
        "alt_names":    ["TSLP", "thymic stromal lymphopoietin"],
        "target_class": "cytokine",
        "pathway":      "il4_il13_atopy",
        "notes":        "Epithelial-derived alarmin; upstream of IL-4, IL-5, IL-13 cascade",
    },
    # ── TSLP Receptor ───────────────────────────────────────────────────────
    {
        "id":           "tslpr",
        "name":         "TSLPR (TSLP Receptor)",
        "alt_names":    ["TSLP Receptor (TSLPR)", "TSLPR", "CRLF2"],
        "target_class": "cytokine_receptor",
        "pathway":      "il4_il13_atopy",
        "notes":        "Receptor subunit for TSLP; targeting blocks TSLP signaling",
    },
    # ── IL-4Rα ──────────────────────────────────────────────────────────────
    {
        "id":           "il4ra",
        "name":         "IL-4Rα",
        "alt_names":    ["IL-4Rα", "IL-4Ra", "IL4RA", "IL-4R", "IL-4Rα/IL-13Rα1"],
        "target_class": "cytokine_receptor",
        "pathway":      "il4_il13_atopy",
        "notes":        "Shared receptor subunit for IL-4 and IL-13; dupilumab mechanism",
    },
    # ── IL-33 ────────────────────────────────────────────────────────────────
    {
        "id":           "il33",
        "name":         "IL-33",
        "alt_names":    ["IL-33", "IL33", "IL-33 (anti-ST2)"],
        "target_class": "cytokine",
        "pathway":      "il33_alarmin",
        "notes":        "Alarmin cytokine; anti-ST2 = blocking the IL-33 receptor = same pathway",
    },
    # ── IL-13 ────────────────────────────────────────────────────────────────
    {
        "id":           "il13",
        "name":         "IL-13",
        "alt_names":    ["IL-13", "IL13"],
        "target_class": "cytokine",
        "pathway":      "il4_il13_atopy",
        "notes":        "Key effector cytokine in atopic dermatitis and asthma",
    },
    # ── IL-13Rα1 ─────────────────────────────────────────────────────────────
    {
        "id":           "il13ra1",
        "name":         "IL-13Rα1",
        "alt_names":    ["IL-13Rα1", "IL-13Ra1"],
        "target_class": "cytokine_receptor",
        "pathway":      "il4_il13_atopy",
        "notes":        "Part of type II IL-4R complex; specific to IL-13 (not IL-4) signaling",
    },
    # ── IL-31RA ──────────────────────────────────────────────────────────────
    {
        "id":           "il31ra",
        "name":         "IL-31RA",
        "alt_names":    ["IL-31RA", "IL31RA", "IL-31 receptor"],
        "target_class": "cytokine_receptor",
        "pathway":      "il31_pruritus",
        "notes":        "IL-31 receptor; blocking reduces itch signaling in atopic dermatitis",
    },
    # ── IL-5 / IL-5Rα ────────────────────────────────────────────────────────
    {
        "id":           "il5",
        "name":         "IL-5",
        "alt_names":    ["IL-5"],
        "target_class": "cytokine",
        "pathway":      "eosinophil_axis",
        "notes":        "Eosinophil growth and survival factor",
    },
    {
        "id":           "il5ra",
        "name":         "IL-5Rα",
        "alt_names":    ["IL-5Rα", "IL-5Ra", "IL5RA"],
        "target_class": "cytokine_receptor",
        "pathway":      "eosinophil_axis",
        "notes":        "IL-5 receptor alpha subunit; benralizumab mechanism",
    },
    # ── IGF-1R ───────────────────────────────────────────────────────────────
    {
        "id":           "igf1r",
        "name":         "IGF-1R",
        "alt_names":    ["IGF-1R", "IGF1R", "Insulin-like growth factor 1 receptor"],
        "target_class": "growth_factor",
        "pathway":      "igf_ted",
        "notes":        "IGF-1 receptor; mechanism for thyroid eye disease (Graves' orbitopathy)",
    },
    # ── OX40 / OX40L ─────────────────────────────────────────────────────────
    {
        "id":           "ox40l",
        "name":         "OX40L",
        "alt_names":    ["OX40L", "TNFSF4"],
        "target_class": "cytokine",
        "pathway":      "ox40_costim",
        "notes":        "OX40 ligand; blocks T-cell co-stimulation",
    },
    {
        "id":           "ox40",
        "name":         "OX40",
        "alt_names":    ["OX40", "TNFRSF4", "CD134"],
        "target_class": "cytokine_receptor",
        "pathway":      "ox40_costim",
        "notes":        "OX40 receptor on T cells; co-stimulatory signal",
    },
    # ── BCMA ─────────────────────────────────────────────────────────────────
    {
        "id":           "bcma",
        "name":         "BCMA (TNFRSF17)",
        "alt_names":    ["BCMA", "TNFRSF17", "CD269"],
        "target_class": "surface_antigen",
        "pathway":      "b_cell_myeloma",
        "notes":        "B-cell maturation antigen; highly expressed on plasma cells and myeloma",
    },
    # ── CD19 ─────────────────────────────────────────────────────────────────
    {
        "id":           "cd19",
        "name":         "CD19",
        "alt_names":    ["CD19"],
        "target_class": "surface_antigen",
        "pathway":      "b_cell_autoimmune",
        "notes":        "Pan-B-cell marker; depletion used for autoimmune B-cell diseases",
    },
    # ── CD20 ─────────────────────────────────────────────────────────────────
    {
        "id":           "cd20",
        "name":         "CD20",
        "alt_names":    ["CD20", "MS4A1"],
        "target_class": "surface_antigen",
        "pathway":      "b_cell_autoimmune",
        "notes":        "B-cell surface marker; broad B-cell depletion",
    },
    # ── CD38 ─────────────────────────────────────────────────────────────────
    {
        "id":           "cd38",
        "name":         "CD38",
        "alt_names":    ["CD38"],
        "target_class": "surface_antigen",
        "pathway":      "b_cell_myeloma",
        "notes":        "Expressed on plasma cells and myeloma; daratumumab mechanism",
    },
    # ── CD3 (T-cell engager anchor) ──────────────────────────────────────────
    {
        "id":           "cd3",
        "name":         "CD3",
        "alt_names":    ["CD3", "CD3ε", "CD3e"],
        "target_class": "surface_antigen",
        "pathway":      "t_cell_engager",
        "notes":        "T-cell co-receptor; one arm of T-cell engager bispecifics",
    },
    # ── α4β7 integrin ────────────────────────────────────────────────────────
    {
        "id":           "a4b7",
        "name":         "α4β7 integrin",
        "alt_names":    ["α4β7", "a4b7", "α4β7 integrin", "LPAM-1"],
        "target_class": "cytokine_receptor",
        "pathway":      "gut_homing",
        "notes":        "Gut-homing integrin; vedolizumab mechanism",
    },
    # ── PD-1 ─────────────────────────────────────────────────────────────────
    {
        "id":           "pd1",
        "name":         "PD-1",
        "alt_names":    ["PD-1", "PDCD1", "CD279"],
        "target_class": "checkpoint",
        "pathway":      "pd1_checkpoint",
        "notes":        "Checkpoint receptor; blocks T-cell exhaustion",
    },
    # ── VEGF ─────────────────────────────────────────────────────────────────
    {
        "id":           "vegf",
        "name":         "VEGF",
        "alt_names":    ["VEGF", "VEGF-A", "VEGFA"],
        "target_class": "growth_factor",
        "pathway":      "vegf_angiogenesis",
        "notes":        "Vascular endothelial growth factor",
    },
    # ── Bispecific pair entries ───────────────────────────────────────────────
    {
        "id":           "tl1a_il23p19",
        "name":         "TL1A × IL-23p19",
        "alt_names":    ["TL1A×IL-23p19", "TL1A × IL-23p19", "IL-23p19 × TL1A"],
        "target_class": "bispecific_pair",
        "pathway":      "tl1a_ibd",
        "notes":        "Bispecific — component targets: tl1a + il23p19",
    },
    {
        "id":           "tl1a_il12_23p40",
        "name":         "TL1A × IL-12/23p40",
        "alt_names":    ["TL1A×IL-12/23p40", "IL-23p40 × TL1A"],
        "target_class": "bispecific_pair",
        "pathway":      "tl1a_ibd",
        "notes":        "Bispecific — component targets: tl1a + il12_23p40",
    },
    {
        "id":           "tl1a_il23p19_a4b7",
        "name":         "TL1A × IL-23p19 × α4β7",
        "alt_names":    ["TL1A×IL-23p19×α4β7"],
        "target_class": "bispecific_pair",
        "pathway":      "tl1a_ibd",
        "notes":        "Trispecific — component targets: tl1a + il23p19 + a4b7",
    },
    {
        "id":           "bcma_cd3",
        "name":         "BCMA × CD3",
        "alt_names":    ["BCMA × CD3", "BCMA×CD3"],
        "target_class": "bispecific_pair",
        "pathway":      "t_cell_engager",
        "notes":        "TCE bispecific — component targets: bcma + cd3",
    },
    {
        "id":           "cd19_cd3",
        "name":         "CD19 × CD3",
        "alt_names":    ["CD19 × CD3", "CD19×CD3"],
        "target_class": "bispecific_pair",
        "pathway":      "t_cell_engager",
        "notes":        "TCE bispecific — component targets: cd19 + cd3",
    },
    {
        "id":           "cd20_cd3",
        "name":         "CD20 × CD3",
        "alt_names":    ["CD20 × CD3", "CD20×CD3"],
        "target_class": "bispecific_pair",
        "pathway":      "t_cell_engager",
        "notes":        "TCE bispecific — component targets: cd20 + cd3",
    },
    {
        "id":           "bcma_cd19_cd3",
        "name":         "BCMA × CD19 × CD3",
        "alt_names":    ["BCMA × CD19 × CD3", "CD19×BCMA×CD3"],
        "target_class": "bispecific_pair",
        "pathway":      "t_cell_engager",
        "notes":        "Trispecific TCE — component targets: bcma + cd19 + cd3",
    },
    {
        "id":           "cd19_cd20_cd3",
        "name":         "CD19 × CD20 × CD3",
        "alt_names":    ["CD19 × CD20 × CD3"],
        "target_class": "bispecific_pair",
        "pathway":      "t_cell_engager",
        "notes":        "Trispecific TCE — component targets: cd19 + cd20 + cd3",
    },
    {
        "id":           "tslp_il13",
        "name":         "TSLP × IL-13",
        "alt_names":    ["TSLP×IL-13"],
        "target_class": "bispecific_pair",
        "pathway":      "il4_il13_atopy",
        "notes":        "Bispecific — component targets: tslp + il13",
    },
    {
        "id":           "tslp_il33",
        "name":         "TSLP × IL-33",
        "alt_names":    ["TSLP×IL-33"],
        "target_class": "bispecific_pair",
        "pathway":      "il4_il13_atopy",
        "notes":        "Bispecific — component targets: tslp + il33",
    },
    {
        "id":           "il4ra_ox40l",
        "name":         "IL-4Rα × OX40L",
        "alt_names":    ["IL-4Rα×OX40L"],
        "target_class": "bispecific_pair",
        "pathway":      "il4_il13_atopy",
        "notes":        "Bispecific — component targets: il4ra + ox40l",
    },
    {
        "id":           "il4ra_tslp",
        "name":         "IL-4Rα × TSLP",
        "alt_names":    ["IL-4Rα×TSLP"],
        "target_class": "bispecific_pair",
        "pathway":      "il4_il13_atopy",
        "notes":        "Bispecific — component targets: il4ra + tslp",
    },
    {
        "id":           "pd1_vegf",
        "name":         "PD-1 × VEGF",
        "alt_names":    ["PD-1 × VEGF", "PD-1/VEGF"],
        "target_class": "bispecific_pair",
        "pathway":      "pd1_checkpoint",
        "notes":        "Bispecific — component targets: pd1 + vegf",
    },
]

# ── Bispecific components map ────────────────────────────────────────────────
# For bispecific target IDs, which single-target nodes are the components?
# Used to write additional drug_targets component rows.
BISPECIFIC_COMPONENTS: dict[str, list[str]] = {
    "tl1a_il23p19":      ["tl1a", "il23p19"],
    "tl1a_il12_23p40":   ["tl1a", "il12_23p40"],
    "tl1a_il23p19_a4b7": ["tl1a", "il23p19", "a4b7"],
    "bcma_cd3":          ["bcma", "cd3"],
    "cd19_cd3":          ["cd19", "cd3"],
    "cd20_cd3":          ["cd20", "cd3"],
    "bcma_cd19_cd3":     ["bcma", "cd19", "cd3"],
    "cd19_cd20_cd3":     ["cd19", "cd20", "cd3"],
    "tslp_il13":         ["tslp", "il13"],
    "tslp_il33":         ["tslp", "il33"],
    "il4ra_ox40l":       ["il4ra", "ox40l"],
    "il4ra_tslp":        ["il4ra", "tslp"],
    "pd1_vegf":          ["pd1", "vegf"],
    "tl1a_a4b7":         ["tl1a", "a4b7"],
}

# ── Target text → canonical ID map (same as in seed_competes_with.py) ────────
TARGET_TEXT_TO_ID: dict[str, str] = {
    "tl1a": "tl1a", "tnfsf15": "tl1a", "tl1a/tnfsf15": "tl1a",
    "il-23p19": "il23p19", "il23p19": "il23p19", "il-23": "il23p19",
    "il-12/23p40": "il12_23p40",
    "fcrn": "fcrn", "fcgrt": "fcrn", "neonatal fc receptor": "fcrn",
    "tslp": "tslp", "thymic stromal lymphopoietin": "tslp",
    "tslp receptor (tslpr)": "tslpr",
    "il-4rα": "il4ra", "il-4ra": "il4ra", "il4ra": "il4ra", "il-4r": "il4ra",
    "il-4rα/il-13rα1": "il4ra",
    "il-33": "il33", "il33": "il33", "il-33 (anti-st2)": "il33",
    "il-13": "il13", "il13": "il13",
    "il-13rα1": "il13ra1",
    "il-31ra": "il31ra", "il31ra": "il31ra",
    "il-5": "il5", "il-5rα": "il5ra", "il5rα": "il5ra",
    "igf-1r": "igf1r", "igf1r": "igf1r",
    "ox40l": "ox40l", "ox40": "ox40",
    "bcma": "bcma", "tnfrsf17": "bcma",
    "cd19": "cd19", "cd20": "cd20", "cd38": "cd38",
    "α4β7": "a4b7", "α4β7 integrin": "a4b7", "a4b7 integrin": "a4b7",
    "pd-1": "pd1",
    "vegf-a": "vegf", "vegf": "vegf",
    "tl1a × il-23p19": "tl1a_il23p19", "tl1a×il-23p19": "tl1a_il23p19",
    "tl1a×il-23": "tl1a_il23p19", "il-23p19 × tl1a": "tl1a_il23p19",
    "tl1a×il-12/23p40": "tl1a_il12_23p40", "il-23p40 × tl1a": "tl1a_il12_23p40",
    "tl1a×il-23p19×α4β7": "tl1a_il23p19_a4b7",
    "bcma × cd3": "bcma_cd3", "bcma×cd3": "bcma_cd3",
    "bcma × cd19 × cd3": "bcma_cd19_cd3", "cd19×bcma×cd3": "bcma_cd19_cd3",
    "cd19 × cd3": "cd19_cd3", "cd19×cd3": "cd19_cd3",
    "cd20 × cd3": "cd20_cd3", "cd20×cd3": "cd20_cd3",
    "cd19 × cd20 × cd3": "cd19_cd20_cd3",
    "tslp×il-13": "tslp_il13", "tslp×il-33": "tslp_il33",
    "il-4rα×ox40l": "il4ra_ox40l", "il-4rα×tslp": "il4ra_tslp",
    "pd-1 × vegf": "pd1_vegf", "pd-1/vegf": "pd1_vegf",
}

UNCERTAIN_PATTERNS = ["or", " vs ", "combination"]
