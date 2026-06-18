#!/usr/bin/env python3
"""
Molecule Intelligence Writer (§3 company_enrichment split).
===========================================================
Extracted verbatim from company_enrichment.py. Persists per-drug molecule-level
intelligence (format, modality, IgG subclass, Fc engineering, epitope, affinity,
differentiation claim + field_status) produced by Step 5. Self-contained leaf.
"""

import datetime
from typing import Optional

from meridian.enrichment.company.common import NOW_ISO, log, sb_get, sb_upsert


# ══════════════════════════════════════════════════════════════════════════
# MOLECULE INTELLIGENCE WRITER
# ══════════════════════════════════════════════════════════════════════════

def write_molecule_intelligence(company_id: str, area_id: str,
                                 data: dict, ctx: dict,
                                 dry_run: bool = False,
                                 enrichment_run_id: Optional[str] = None) -> int:
    """Upsert molecule_intelligence rows for each drug in molecule_updates.

    Keyed on canonical_drug_id (UNIQUE) — one row per molecule, area-agnostic.
    field_status JSONB distinguishes confirmed / inferred / unknown per field.
    Full provenance: enrichment_run_id, updated_at, and enriched_field_log writes.
    Returns count of rows upserted.
    """
    mol_updates = data.get("molecule_updates") or []
    if not mol_updates:
        return 0

    # Build a quick lookup: drug_id → canonical_drug_id from context drugs
    canon_map = {d["id"]: d.get("canonical_drug_id") for d in ctx.get("drugs", []) if d.get("id")}

    # MI_LOGGABLE_FIELDS: fields that carry enrichment signal for enriched_field_log
    MI_LOGGABLE_FIELDS = {
        "format", "valency", "modality", "igg_subclass", "fc_engineering",
        "epitope", "affinity_kd", "lowest_active_dose", "safety_observations",
        "differentiation_claim", "confidence", "source_url",
    }

    written = 0
    for mu in mol_updates:
        drug_id = mu.get("drug_id") or ""
        if not drug_id:
            log("  ⚠ molecule_update missing drug_id — skipped", indent=2)
            continue

        canonical_drug_id = canon_map.get(drug_id)
        if not canonical_drug_id:
            log(f"  ⚠ no canonical_drug_id for {drug_id} — skipping molecule write", indent=2)
            continue

        # Validate field_status values
        VALID_STATUS = {"confirmed", "inferred", "unknown"}
        raw_fs = mu.get("field_status") or {}
        field_status = {}
        for k, v in raw_fs.items():
            if v in VALID_STATUS:
                field_status[k] = v
            else:
                log(f"  ⚠ field_status[{k}]={v!r} invalid — defaulting to 'unknown'", indent=2)
                field_status[k] = "unknown"

        # 1. Fetch current molecule_intelligence row for old_value capture
        existing_mi_rows = sb_get("molecule_intelligence", {
            "canonical_drug_id": f"eq.{canonical_drug_id}",
            "select": "id," + ",".join(MI_LOGGABLE_FIELDS),
            "limit": "1",
        })
        existing_mi = existing_mi_rows[0] if existing_mi_rows else {}

        rec = {
            "canonical_drug_id":       canonical_drug_id,
            "drug_id":                 drug_id,
            "format":                  mu.get("format")                or None,
            "valency":                 mu.get("valency")               or None,
            "modality":                mu.get("modality")              or None,
            "igg_subclass":            mu.get("igg_subclass")          or None,
            "fc_engineering":          mu.get("fc_engineering")        or None,
            "epitope":                 mu.get("epitope")               or None,
            "affinity_kd":             mu.get("affinity_kd")           or None,
            "lowest_active_dose":      mu.get("lowest_active_dose")    or None,
            "lowest_active_dose_unit": mu.get("lowest_active_dose_unit") or None,
            "safety_observations":     mu.get("safety_observations")   or None,
            "differentiation_claim":   mu.get("differentiation_claim") or None,
            "field_status":            field_status,
            "confidence":              mu.get("confidence")            or None,
            "source_url":              mu.get("source_url")            or None,
            "last_enriched_at":        NOW_ISO,
            "updated_at":              NOW_ISO,
            "enriched_by":             "company_enrichment.py",
            "model_version":           "claude-sonnet-4-6",
        }
        # Stamp enrichment run provenance
        if enrichment_run_id:
            rec["enrichment_run_id"] = enrichment_run_id

        # Strip Nones except field_status (always present)
        rec = {k: v for k, v in rec.items() if v is not None or k == "field_status"}

        if dry_run:
            log(f"  [dry] molecule {drug_id}: format={rec.get('format')} "
                f"modality={rec.get('modality')} "
                f"status_keys={list(field_status.keys())}", indent=2)
            written += 1
            continue

        # 2. Write to molecule_intelligence
        ok = sb_upsert("molecule_intelligence", rec,
                        on_conflict="canonical_drug_id")
        if ok:
            inferred_fields = [k for k, v in field_status.items() if v == "inferred"]
            unknown_fields  = [k for k, v in field_status.items() if v == "unknown"]
            log(f"  molecule {drug_id}: ✓ upserted | "
                f"inferred={inferred_fields} unknown={unknown_fields}", indent=2)
            written += 1

            # 3. Log each changed field to enriched_field_log
            if enrichment_run_id:
                _now_ts = datetime.datetime.utcnow().isoformat()
                _field_log_rows = []
                # ── confidence_score for molecule intelligence fields ──────────
                # Use field_status to infer confidence: confirmed>inferred>unknown
                _fs = field_status or {}
                _mi_source_url = mu.get("source_url") or None
                for _fname in MI_LOGGABLE_FIELDS:
                    _new_val = rec.get(_fname)
                    if _new_val is None:
                        continue
                    _old_val = existing_mi.get(_fname)
                    _new_str = str(_new_val)
                    _old_str = str(_old_val) if _old_val is not None else None
                    _was_changed = _old_str != _new_str if _old_str is not None else True
                    # Per-field confidence from field_status if available, else source heuristic
                    _fs_val = (_fs.get(_fname) or "").lower()
                    if _fs_val == "confirmed":
                        _mi_conf = 0.90
                    elif _fs_val == "inferred":
                        _mi_conf = 0.65
                    elif _fs_val == "unknown":
                        _mi_conf = 0.50
                    elif _mi_source_url:
                        _mi_conf = 0.80
                    else:
                        _mi_conf = 0.75
                    _field_log_rows.append({
                        "enrichment_run_id": enrichment_run_id,
                        "entity_type":       "drug",
                        "entity_id":         drug_id,
                        "field_name":        f"molecule_intelligence.{_fname}",
                        "enriched_value":    _new_str,
                        "old_value":         _old_str,
                        "was_changed":       _was_changed,
                        "model_name":        "claude-sonnet-4-6",
                        "confidence_score":  _mi_conf,
                        "source_citation":   _mi_source_url,
                        "enriched_at":       _now_ts,
                        "field_label":       "pending",
                        "label_source":      "pending",
                    })
                if _field_log_rows:
                    try:
                        _fl_result = sb_upsert("enriched_field_log", _field_log_rows)
                        log(f"    enriched_field_log: {len(_fl_result or [])} molecule field(s) logged for {drug_id}", indent=2)
                    except Exception as _fl_exc:
                        log(f"    enriched_field_log (molecule): write failed (non-fatal): {_fl_exc}", indent=2)
        else:
            log(f"  molecule {drug_id}: ✗ upsert failed", indent=2)

    return written
