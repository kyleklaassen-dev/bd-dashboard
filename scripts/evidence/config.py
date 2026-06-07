"""
Static configuration for the evidence source backfill pipeline.
"""

DEFAULT_AREAS = ["tl1a", "il23p19", "tslp", "il4ra", "fcrn", "igf1r", "a4b7"]

# indication_name → (Europe PMC search phrase, relevance token that must appear in title/abstract)
DISEASE_MAP: dict[str, tuple[str, str]] = {
    "Multiple Myeloma":                       ("multiple myeloma",          "myeloma"),
    "Generalized Myasthenia Gravis":          ("myasthenia gravis",          "myasthenia"),
    "Thyroid Eye Disease":                    ("thyroid eye disease",        "thyroid eye"),
    "Crohn's Disease":                        ("Crohn disease",              "crohn"),
    "Ulcerative Colitis":                     ("ulcerative colitis",         "ulcerative colitis"),
    "Atopic Dermatitis":                      ("atopic dermatitis",          "atopic dermatitis"),
    "Gastric/GEJ Adenocarcinoma - FGFR2b+":  ("gastric adenocarcinoma",     "gastric"),
    "IBD (Inflammatory Bowel Disease)":       ("inflammatory bowel disease", "inflammatory bowel"),
}

# Preferred title terms when scoring epidemiology publications
EPMC_PREF_TERMS = ("epidemiology", "prevalence", "incidence", "burden", "epidemiolog")

UA = "meridian-evidence-collector/1.0"
