#!/usr/bin/env python3
"""catalog_category — the ONE source of truth for inferring a drug's catalog_category.

Invariant: every drug that receives a drug_areas row must have catalog_category set so
it appears in the "Drugs to Know" tab. This logic was previously triplicated across
company_enrichment, drug_intake, and approve_discovery — now it lives here. Import it:

    from meridian.enrichment.catalog_category import infer_catalog_category
"""
import re as _re

_CCat_TCE_TARGETS   = {"bcma", "cd3", "cd19", "cd20", "cd38", "cd33", "cd123",
                       "her2", "egfr", "pd-1", "pd-l1", "pdl1", "ctla-4", "ctla4",
                       "tim-3", "lag-3", "cd47", "vegf"}
_CCat_IMMUNO_KWORDS = {"tl1a", "tnfrsf25", "il-4r", "il4r", "tslp", "fcrn",
                       "neonatal fc", "il-23", "il23", "il-17", "il17", "tnf",
                       "il-13", "il13", "il-33", "il33", "il-31", "il31",
                       "integrin", "α4β7", "a4b7", "rankl", "baff", "april",
                       "igg4", "ige", "il-5", "il5", "il-6", "il6"}
_CCat_ONCOLOGY_AREAS = {"tcell", "t_cell"}
_CCat_IMMUNO_AREAS   = {"tl1a", "fcrn", "il4ra", "tslp", "autoimmune",
                        "ibd", "respiratory", "ige"}
_CCat_EARLY_STAGES   = {"preclinical", "phase 1", "phase i", "pre-ind",
                        "ind-enabling", "discovery"}


def infer_catalog_category(target: str = "", modality: str = "",
                           stage: str = "", area_id: str = "") -> str:
    """Infer catalog_category from drug attributes (Oncology / Small Molecule /
    Immunology / Pipeline). Deterministic; ordering matters (TCE/ADC → Oncology first)."""
    tgt  = (target   or "").lower()
    mod  = (modality or "").lower()
    stg  = (stage    or "").lower()
    area = (area_id  or "").lower()

    tgt_parts = {p.strip() for p in _re.split(r"[×x×/]", tgt) if p.strip()}
    if _CCat_TCE_TARGETS & tgt_parts:
        return "Oncology"
    if any(m in mod for m in ("adc", "car-t", "car t", "antibody-drug conjugate")):
        return "Oncology"
    if area in _CCat_ONCOLOGY_AREAS:
        return "Oncology"
    if "jak" in tgt or "small molecule" in mod or "oral small molecule" in mod:
        return "Small Molecule"
    is_immuno = any(kw in tgt for kw in _CCat_IMMUNO_KWORDS) or area in _CCat_IMMUNO_AREAS
    if is_immuno:
        return "Pipeline" if any(s in stg for s in _CCat_EARLY_STAGES) else "Immunology"
    return "Pipeline"
