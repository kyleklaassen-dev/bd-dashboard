"""
schemas/enrichment.py — Output schema for company_enrichment (Step 5 Phase B).

DrugEnrichmentOutput is the Pydantic model used for per-field validation
before writing drug_updates to the database. Only the 7 highest-risk drug
fields are validated here — company_profile narrative fields are validated
by governance rules in the prompt itself.

Import this instead of defining DrugEnrichmentOutput inline in scripts.
"""
from __future__ import annotations

from typing import Optional

try:
    from pydantic import BaseModel
    _PYDANTIC_AVAILABLE = True

    class DrugEnrichmentOutput(BaseModel):
        """Pydantic model for per-field validation on drug_update rows.

        Fields not listed here are written without schema enforcement.
        A field failing validation is dropped from the write (not rejected
        entirely) — other fields in the same drug_update continue to write.
        """
        mechanism:              Optional[str] = None
        ailux_angle:            Optional[str] = None
        drug_summary:           Optional[str] = None
        source_url:             Optional[str] = None
        overlap:                Optional[str] = None
        overlap_rationale:      Optional[str] = None
        differentiation_thesis: Optional[str] = None

except ImportError:
    _PYDANTIC_AVAILABLE = False
    DrugEnrichmentOutput = None  # type: ignore[assignment,misc]


# Fields covered by DrugEnrichmentOutput validation.
VALIDATED_DRUG_FIELDS = frozenset({
    "mechanism",
    "ailux_angle",
    "drug_summary",
    "source_url",
    "overlap",
    "overlap_rationale",
    "differentiation_thesis",
})

# Top-level keys expected in the company_enrichment JSON response.
ENRICHMENT_OUTPUT_KEYS = {
    "company_profile": dict,   # key_risk, why_it_matters, bd_summary, vs_ailux, ...
    "drug_updates":    list,   # [{drug_id, target, mechanism, ...}, ...]
    "molecule_updates":list,   # [{drug_id, format, valency, modality, ...}, ...]
    "catalysts":       list,
    "deals":           list,
    "intel":           list,
    "competitive_signals": list,
}
