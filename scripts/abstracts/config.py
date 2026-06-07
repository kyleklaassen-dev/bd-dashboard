"""
Static configuration for the abstract fetcher pipeline.
"""

# Drug stages worth sweeping for abstracts
TARGET_STAGES = frozenset({
    "phase_2", "phase_2b", "phase_2_positive", "phase_2b_positive",
    "phase_3", "phase_3_positive",
    "approved", "approved_us", "approved_eu", "approved_china",
    "approved_us_eu", "approved_partial",
    "bla_filed", "nda_filed",
})

# Keywords for the preprint monitor sweep
PREPRINT_KEYWORDS = [
    "TL1A DR3 IBD",
    "IL-23p19 bispecific",
    "FcRn inhibitor autoimmune",
    "IGF-1R thyroid eye disease",
    "TSLP atopic dermatitis bispecific",
    "CD19 BCMA T cell engager autoimmune",
    "tulisokibart",
    "afimkibart",
    "efgartigimod",
    "nipocalimab",
    "zumilokibart",
    "spesolimab IBD",
    "mirikizumab",
]

UA = "Mozilla/5.0 (compatible; Meridian-BD/1.0)"
