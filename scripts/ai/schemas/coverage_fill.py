"""
schemas/coverage_fill.py — Output schema for coverage_fill (post-pipeline).

The LLM returns a small JSON object for a single drug. The caller only
writes fields where the current DB value is null or empty — no overwrites.
"""
from __future__ import annotations

# Expected JSON output shape from coverage_fill prompt.
COVERAGE_FILL_KEYS = {
    "target":                 str,   # molecular target(s)
    "mechanism":              str,   # 2-3 sentence mechanistic description
    "differentiation_thesis": str,   # 1-2 sentence unique value vs class
    "ailux_angle":            str,   # 1-2 sentence relevance to TL1A×IL-23p19 program
    "drug_summary":           str,   # 3-4 sentence overview
    "stage":                  str,   # Preclinical | Phase 1 | Phase 2 | Phase 3 | ...
    "indication_short":       str,   # primary indication(s)
}

# Fields safe to backfill (only when current DB value is null/empty).
NULLABLE_FILL_FIELDS = [
    "target",
    "mechanism",
    "differentiation_thesis",
    "ailux_angle",
    "drug_summary",
]
