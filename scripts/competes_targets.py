#!/usr/bin/env python3
"""
competes_targets.py — target normalization for seed_competes_with.py (§3 split).

Pure: the raw-target -> canonical-id alias map plus the two normalizers. No I/O,
no project imports. Extracted verbatim so the seeding logic stays small.
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════
# TARGET NORMALIZATION
# ══════════════════════════════════════════════════════════════════════════════

# Maps raw drug.target text values → canonical target IDs.
# Conservative: only exact/near-exact synonyms. No biological inference.
# Bispecifics (containing × or /) are kept as-is after lowercasing.
TARGET_ALIASES: dict[str, str] = {
    # TL1A / TNFSF15
    "tl1a":                 "tl1a",
    "tnfsf15":              "tl1a",
    "tl1a/tnfsf15":         "tl1a",
    "tnfsf15 (tl1a)":       "tl1a",
    "tl1a (tnfsf15)":       "tl1a",

    # IL-23 p19 subunit
    "il-23p19":             "il23p19",
    "il23p19":              "il23p19",
    "il-23":                "il23p19",
    "il23":                 "il23p19",
    "il-23 (p19)":          "il23p19",

    # FcRn / neonatal Fc receptor
    "fcrn":                 "fcrn",
    "fcgrt":                "fcrn",
    "neonatal fc receptor": "fcrn",
    "neonatal fcrn":        "fcrn",
    "fc receptor":          "fcrn",  # loose but common
    "fcrn (fcgrt)":         "fcrn",

    # TSLP
    "tslp":                 "tslp",
    "thymic stromal lymphopoietin": "tslp",

    # IL-4 receptor alpha
    "il-4rα":               "il4ra",
    "il-4ra":               "il4ra",
    "il4ra":                "il4ra",
    "il4r":                 "il4ra",
    "il-4r":                "il4ra",
    "il-4rα/il-13rα1":      "il4ra",  # dupilumab mechanism; keep as il4ra for competition
    "il4rα":                "il4ra",

    # IL-33
    "il-33":                "il33",
    "il33":                 "il33",

    # IGF-1R
    "igf-1r":               "igf1r",
    "igf1r":                "igf1r",
    "igf1":                 "igf1r",
    "igfr":                 "igf1r",

    # BCMA / TNFRSF17
    "bcma":                 "bcma",
    "tnfrsf17":             "bcma",
    "bcma (tnfrsf17)":      "bcma",

    # IL-13
    "il-13":                "il13",
    "il13":                 "il13",

    # IL-31RA
    "il-31ra":              "il31ra",
    "il31ra":               "il31ra",

    # IL-5 / IL-5Rα
    "il-5":                 "il5",
    "il5":                  "il5",
    "il-5rα":               "il5ra",
    "il-5ra":               "il5ra",
    "il5ra":                "il5ra",

    # OX40 / OX40L
    "ox40l":                "ox40l",
    "ox40":                 "ox40",

    # CD19 (standalone — not bispecific)
    "cd19":                 "cd19",

    # T-cell engager bispecifics (each target pair is its own class)
    "bcma × cd3":           "bcma_cd3",
    "bcma×cd3":             "bcma_cd3",
    "bcmaXcd3":             "bcma_cd3",
    "bcma × cd19 × cd3":    "bcma_cd19_cd3",
    "cd19×bcma×cd3":        "bcma_cd19_cd3",
    "cd19 × cd3":           "cd19_cd3",
    "cd19×cd3":             "cd19_cd3",
    "cd3×cd19":             "cd19_cd3",
    "cd20 × cd3":           "cd20_cd3",
    "cd20×cd3":             "cd20_cd3",
    "cd19 × cd20 × cd3":    "cd19_cd20_cd3",

    # TL1A bispecifics (each gets own class — do NOT auto-compete with monospecifics)
    "tl1a × il-23p19":      "tl1a_il23p19",
    "tl1a×il-23p19":        "tl1a_il23p19",
    "tl1a×il23p19":         "tl1a_il23p19",
    "tl1a/il-23":           "tl1a_il23p19",
    "tl1a×il-23":           "tl1a_il23p19",
    "il-23p19 × tl1a":      "tl1a_il23p19",  # canonical direction
    "tl1a×il-23p19×α4β7":   "tl1a_il23p19_a4b7",
    "tl1a×il-12/23p40":     "tl1a_il12_23p40",
    "il-23p40 × tl1a":      "tl1a_il12_23p40",

    # TSLP bispecifics
    "tslp×il-13":           "tslp_il13",
    "tslp×il-33":           "tslp_il33",

    # IL-4Rα bispecifics
    "il-4rα×ox40l":         "il4ra_ox40l",
    "il-4rα×tslp":          "il4ra_tslp",

    # Other
    "pd-1 × vegf":          "pd1_vegf",
    "pd-1×vegf":            "pd1_vegf",
    "pd-1/vegf":            "pd1_vegf",
    "pd-1×ctla-4":          "pd1_ctla4",
}

def normalize_target(raw: str) -> tuple[str, bool]:
    """
    Returns (canonical_target_id, is_in_alias_map).
    If not in alias map, returns (lowercased_raw, False) — caller decides how to handle.
    """
    if not raw:
        return ("", False)
    cleaned = raw.strip().lower()
    # Replace unicode × with x for lookup
    cleaned = cleaned.replace("×", "×")  # keep canonical form
    canonical = TARGET_ALIASES.get(cleaned)
    if canonical:
        return (canonical, True)
    # Try without spaces
    no_space = cleaned.replace(" ", "")
    canonical = TARGET_ALIASES.get(no_space)
    if canonical:
        return (canonical, True)
    return (cleaned, False)


def is_bispecific_target(canonical: str) -> bool:
    """Returns True if the canonical target represents a bispecific or multi-target."""
    return "_" in canonical or "×" in canonical or "/" in canonical
