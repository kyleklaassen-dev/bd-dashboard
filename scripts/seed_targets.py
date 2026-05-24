#!/usr/bin/env python3
"""
BD Platform — Target Normalization Seeder
==========================================
Phase 2 of the relationship-completeness sprint (2026-05-24).

PURPOSE
-------
Normalizes drugs.target free-text into queryable target nodes:
  1. Seeds the `targets` table with canonical entries + metadata
  2. Parses each drug's target field → writes `drug_targets` junction rows
  3. Writes drug → TARGETS → target edges to `entity_edges` for graph queries
  4. Adds validation test: every area-linked drug must have ≥1 drug_targets row

PARSING LOGIC
-------------
• Monospecific drug:   drugs.target = 'TL1A'    → 1 drug_targets row (role='primary')
• Bispecific drug:     drugs.target = 'TL1A×IL-23p19'
                       → 2 drug_targets rows (role='component' for each)
• Bispecific notation: '×' or '+' or ' + ' as separator
• Combination product (is_combo=true): separate drugs; drug-level target is the
  primary target; combo context is in combination_label (not parsed here)

NOT PARSED (logged as uncertain):
• Targets with 'or' in the text (ambiguous: 'IL-23p19 + IL-1α/β or TL1A')
• Targets with 'vs' in the text (narrative, not target: 'IL-23p19 vs α4β7 integrin')
• Free-text mechanism descriptions (e.g. 'PHD1/HIF-1α')

USAGE
-----
  python scripts/seed_targets.py --dry-run           # print, insert nothing
  python scripts/seed_targets.py --apply             # seed targets + drug_targets
  python scripts/seed_targets.py --apply-migration   # run v27 DDL first, then seed
  python scripts/seed_targets.py --apply --validate  # run validation suite after

ENVIRONMENT
-----------
  SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import os, sys, json, datetime, argparse, urllib.request, urllib.error, ssl
from collections import defaultdict

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.", file=sys.stderr)
    sys.exit(1)

ctx = ssl.create_default_context()
NOW_ISO = datetime.datetime.utcnow().isoformat() + "Z"


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


# ══════════════════════════════════════════════════════════════════════════════
# SUPABASE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _hdrs():
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }

def sb_get(table, params, limit=1000):
    """Paginate through all matching rows."""
    all_rows, offset, PAGE = [], 0, min(limit, 500)
    while True:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{SUPABASE_URL}/rest/v1/{table}?{qs}&limit={PAGE}&offset={offset}"
        req = urllib.request.Request(url, headers=_hdrs())
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                batch = json.loads(r.read())
                all_rows.extend(batch)
                if len(batch) < PAGE or len(all_rows) >= limit:
                    break
                offset += PAGE
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", errors="replace")
            print(f"  [ERROR] GET {table}: {e.code} — {body}", file=sys.stderr)
            break
    return all_rows[:limit]

def sb_post(table, payload, upsert=True):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    prefer = "resolution=merge-duplicates,return=representation" if upsert else "return=representation"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST",
          headers={**_hdrs(), "Prefer": prefer})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()[:400].decode("utf-8", errors="replace")
        print(f"  [ERROR] POST {table}: {e.code} — {body}", file=sys.stderr)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# PARSING LOGIC
# ══════════════════════════════════════════════════════════════════════════════

def parse_target_text(raw: str) -> tuple[str | None, str, bool]:
    """
    Parse drugs.target text → (canonical_target_id, note, is_uncertain).
    Returns (None, reason, True) for uncertain cases.
    """
    if not raw or not raw.strip():
        return (None, "empty target field", True)

    cleaned = raw.strip().lower()

    # Flag uncertain patterns before lookup
    for pattern in UNCERTAIN_PATTERNS:
        if pattern in cleaned:
            return (None, f"uncertain notation: '{raw}'", True)

    # Direct lookup
    canon = TARGET_TEXT_TO_ID.get(cleaned)
    if canon:
        return (canon, "", False)

    # No-space variant
    no_space = cleaned.replace(" ", "")
    canon = TARGET_TEXT_TO_ID.get(no_space)
    if canon:
        return (canon, "", False)

    return (None, f"unmapped target: '{raw}'", True)


def build_drug_target_rows(drug_id: str, canonical_id: str) -> list[dict]:
    """
    Given a drug and its canonical target ID, return all drug_targets rows to insert.
    For bispecifics, also inserts component target rows.
    """
    rows = []
    is_bispecific = canonical_id in BISPECIFIC_COMPONENTS

    # Always insert the top-level canonical target row
    rows.append({
        "drug_id":         drug_id,
        "target_id":       canonical_id,
        "role":            "component" if is_bispecific else "primary",
        "confidence_level": "confirmed",
        "derived_from":    "drugs.target",
        "created_by":      "seed_targets.py",
    })

    # For bispecifics, also insert component targets (if they exist as canonical targets)
    if is_bispecific:
        target_ids = {t["id"] for t in CANONICAL_TARGETS}
        for component_id in BISPECIFIC_COMPONENTS[canonical_id]:
            if component_id in target_ids:
                rows.append({
                    "drug_id":         drug_id,
                    "target_id":       component_id,
                    "role":            "component",
                    "confidence_level": "confirmed",
                    "derived_from":    "drugs.target",
                    "created_by":      "seed_targets.py",
                })

    return rows


def build_entity_edge_rows(drug_id: str, canonical_id: str) -> list[dict]:
    """Build entity_edges TARGETS rows for the drug→target relationship."""
    edges = []
    is_bispecific = canonical_id in BISPECIFIC_COMPONENTS

    # Top-level target edge
    edges.append({
        "subject_type":     "drug",
        "subject_id":       drug_id,
        "predicate":        "TARGETS",
        "object_type":      "target",
        "object_id":        canonical_id,
        "confidence_level": "confirmed",
        "generation_method": "deterministic",
        "rationale":        f"Parsed from drugs.target field by seed_targets.py {NOW_ISO[:10]}",
        "status":           "active",
        "created_by":       "seed_targets.py",
    })

    # Component target edges for bispecifics
    if is_bispecific:
        target_ids = {t["id"] for t in CANONICAL_TARGETS}
        for component_id in BISPECIFIC_COMPONENTS[canonical_id]:
            if component_id in target_ids:
                edges.append({
                    "subject_type":     "drug",
                    "subject_id":       drug_id,
                    "predicate":        "TARGETS",
                    "object_type":      "target",
                    "object_id":        component_id,
                    "confidence_level": "confirmed",
                    "generation_method": "deterministic",
                    "rationale":        f"Component target of {canonical_id}; derived by seed_targets.py {NOW_ISO[:10]}",
                    "status":           "active",
                    "created_by":       "seed_targets.py",
                })

    return edges


# ══════════════════════════════════════════════════════════════════════════════
# APPLY MIGRATION
# ══════════════════════════════════════════════════════════════════════════════

def apply_migration(project_id: str, pat: str) -> bool:
    migration_path = os.path.join(os.path.dirname(__file__), "migrations", "v27_targets.sql")
    if not os.path.exists(migration_path):
        print(f"  [ERROR] Not found: {migration_path}", file=sys.stderr)
        return False
    with open(migration_path) as f:
        sql = f.read()

    statements = []
    current = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        current.append(line)
        if stripped.endswith(";"):
            stmt = " ".join(current).strip().rstrip(";")
            if stmt:
                statements.append(stmt)
            current = []

    api_url = f"https://api.supabase.com/v1/projects/{project_id}/database/query"
    success = 0
    for stmt in statements:
        payload = json.dumps({"query": stmt + ";"}).encode()
        req = urllib.request.Request(api_url, data=payload, method="POST", headers={
            "Authorization": f"Bearer {pat}", "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                success += 1
                print(f"  ✓ {stmt[:80].replace(chr(10),' ')}...")
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", errors="replace")
            if "already exists" in body.lower():
                print(f"  ⚠ Already exists: {stmt[:60]}...")
                success += 1
            else:
                print(f"  ✗ FAILED: {stmt[:60]}...\n    {e.code} — {body}", file=sys.stderr)
                return False
    print(f"  Migration: {success} statements applied.")
    return True


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Seed targets table + drug_targets junction.")
    parser.add_argument("--dry-run",         action="store_true")
    parser.add_argument("--apply",           action="store_true")
    parser.add_argument("--apply-migration", action="store_true")
    parser.add_argument("--validate",        action="store_true")
    parser.add_argument("--project-id",      default="tghntyofptvfhmtchwcv")
    parser.add_argument("--pat-file",        default=".supabase_pat")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Specify --dry-run or --apply."); parser.print_help(); sys.exit(0)

    # ── Optional: apply migration DDL ─────────────────────────────────────────
    if args.apply_migration:
        pat_path = os.path.join(os.path.dirname(__file__), "..", args.pat_file)
        if not os.path.exists(pat_path):
            print(f"PAT file not found: {pat_path}", file=sys.stderr); sys.exit(1)
        with open(pat_path) as f:
            pat = f.read().strip()
        print("Applying migration v27...")
        if not apply_migration(args.project_id, pat):
            print("Migration failed."); sys.exit(1)

    # ── Fetch all drugs ────────────────────────────────────────────────────────
    drugs = sb_get("drugs", {"select": "id,name,target,stage"}, limit=1000)
    print(f"Drugs fetched: {len(drugs)}")

    # ── Parse drug targets ─────────────────────────────────────────────────────
    drug_target_rows = []
    entity_edge_rows = []
    uncertain = []

    for d in drugs:
        drug_id = d["id"]
        raw_target = (d.get("target") or "").strip()
        if not raw_target:
            continue

        canon, note, is_uncertain = parse_target_text(raw_target)
        if is_uncertain:
            uncertain.append({"drug_id": drug_id, "name": d.get("name","?"),
                               "raw_target": raw_target, "note": note})
            continue

        drug_target_rows.extend(build_drug_target_rows(drug_id, canon))
        entity_edge_rows.extend(build_entity_edge_rows(drug_id, canon))

    print(f"\n--- Audit ---")
    print(f"  Drug-target rows to insert:   {len(drug_target_rows)}")
    print(f"  Entity edge rows (TARGETS):   {len(entity_edge_rows)}")
    print(f"  Uncertain (not inserting):    {len(uncertain)}")

    if uncertain:
        print(f"\n  Uncertain cases:")
        for uc in uncertain:
            print(f"    {uc['drug_id']:35s} raw='{uc['raw_target']}'  — {uc['note']}")

    if args.dry_run:
        print("\n[DRY RUN] No rows inserted.")
        return

    # ── Insert targets catalog ─────────────────────────────────────────────────
    # DB uses `label` (not `name`) as the display column; `full_name` for expanded form.
    # Transform CANONICAL_TARGETS to match actual schema before inserting.
    targets_for_db = []
    for t in CANONICAL_TARGETS:
        row = dict(t)
        if "name" in row and "label" not in row:
            row["label"] = row.pop("name")
        targets_for_db.append(row)

    print(f"\nInserting {len(targets_for_db)} canonical targets...")
    result = sb_post("targets", targets_for_db)
    if result is None:
        print("  [ERROR] Failed to insert targets."); sys.exit(1)
    print(f"  ✓ {len(result) if isinstance(result,list) else 1} targets upserted (new; dupes ignored)")

    # ── Insert drug_targets rows ────────────────────────────────────────────────
    print(f"\nInserting {len(drug_target_rows)} drug_targets rows...")
    BATCH = 100
    inserted_dt = 0
    for i in range(0, len(drug_target_rows), BATCH):
        batch = drug_target_rows[i:i+BATCH]
        result = sb_post("drug_targets", batch)
        if result is None:
            print(f"  [ERROR] Batch {i//BATCH+1} failed."); sys.exit(1)
        count = len(result) if isinstance(result,list) else 1
        inserted_dt += count
        print(f"  ✓ Batch {i//BATCH+1}: {count} rows (total {inserted_dt})")

    # ── Insert entity_edges TARGETS rows ───────────────────────────────────────
    print(f"\nInserting {len(entity_edge_rows)} entity_edges TARGETS rows...")
    inserted_ee = 0
    for i in range(0, len(entity_edge_rows), BATCH):
        batch = entity_edge_rows[i:i+BATCH]
        result = sb_post("entity_edges", batch)
        if result is None:
            print(f"  [ERROR] Edge batch {i//BATCH+1} failed."); sys.exit(1)
        count = len(result) if isinstance(result,list) else 1
        inserted_ee += count
        print(f"  ✓ Batch {i//BATCH+1}: {count} edges (total {inserted_ee})")

    # ── Insert validation test ─────────────────────────────────────────────────
    print(f"\nInserting validation tests...")
    tests = [
        {
            "test_name":         "drug_has_target_node — area-linked drugs must have ≥1 drug_targets row",
            "test_type":         "count_check",
            "entity_type":       "drug",
            "entity_id":         "system",
            "field_name":        "drug_targets_coverage",
            "expected_value":    "0",
            "expected_operator": "eq",
            "priority":          "P2",
            "notes":             "Counts drugs in drug_areas with zero drug_targets rows. Expected = 0.",
        }
    ]
    result = sb_post("validation_tests", tests)
    if result:
        print(f"  ✓ Validation test inserted")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n═══════════════════════════════════════")
    print(f"Target normalization complete — {NOW_ISO[:10]}")
    print(f"  Canonical targets seeded:   {len(CANONICAL_TARGETS)}")
    print(f"  drug_targets rows inserted: {inserted_dt}")
    print(f"  entity_edges TARGETS:       {inserted_ee}")
    print(f"  Uncertain cases:            {len(uncertain)}")
    print(f"═══════════════════════════════════════")

    if args.validate:
        import subprocess
        print("\nRunning validation suite...")
        subprocess.run([sys.executable,
                        os.path.join(os.path.dirname(__file__), "validate_ground_truth.py")])


if __name__ == "__main__":
    main()
