"""
validators/drug_fields.py — Per-field Pydantic validation for drug_update rows.

Called in company_enrichment.py after parsing the Step 5 synthesis response,
before writing drug_update fields to the database.

Usage
-----
  from ai.validators.drug_fields import validate_drug_updates
  result = validate_drug_updates(data.get("drug_updates", []), ctx_drug_map)
  # result.valid_updates  — list with invalid fields already stripped
  # result.stats          — ValidationStats with attempt/change/fail counts
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ai.schemas.enrichment import DrugEnrichmentOutput, VALIDATED_DRUG_FIELDS, _PYDANTIC_AVAILABLE

logger = logging.getLogger(__name__)


@dataclass
class ValidationStats:
    attempted:   list[str] = field(default_factory=list)
    changed:     list[str] = field(default_factory=list)
    confirmed:   list[str] = field(default_factory=list)
    failed:      list[str] = field(default_factory=list)
    corrections: int = 0
    schema_valid: Optional[bool] = None

    def log(self, indent: int = 1) -> None:
        pad = "  " * indent
        logger.info(
            "%s[schema] attempted=%d changed=%d confirmed=%d failed=%d corrections=%d",
            pad,
            len(self.attempted), len(self.changed),
            len(self.confirmed), len(self.failed),
            self.corrections,
        )


@dataclass
class ValidationResult:
    valid_updates: list[dict]   # drug_updates with invalid fields stripped
    stats: ValidationStats


def validate_drug_updates(
    drug_updates: list[dict],
    ctx_drug_map: dict[str, dict],
) -> ValidationResult:
    """Validate drug_update fields using DrugEnrichmentOutput schema.

    For each validated field:
    - If Pydantic raises, drop the field from du and record in stats.failed.
    - Track whether the field changed vs. confirmed vs. is new.

    If Pydantic is not installed, returns the updates unchanged with
    stats.schema_valid = None.
    """
    stats = ValidationStats()

    if not _PYDANTIC_AVAILABLE or DrugEnrichmentOutput is None:
        return ValidationResult(valid_updates=list(drug_updates), stats=stats)

    validated: list[dict] = []
    for du in drug_updates:
        du = dict(du)  # shallow copy — don't mutate caller's list
        drug_id = du.get("drug_id") or ""
        old_drug = ctx_drug_map.get(drug_id, {})

        for fld in list(VALIDATED_DRUG_FIELDS):
            new_val = du.get(fld)
            if new_val is None:
                continue

            stats.attempted.append(f"{drug_id}.{fld}")

            try:
                DrugEnrichmentOutput(**{fld: new_val})
            except Exception as exc:
                logger.warning(
                    "[schema] %s.%s failed validation: %s", drug_id, fld, exc
                )
                stats.failed.append(f"{drug_id}.{fld}")
                du.pop(fld, None)
                continue

            old_val = old_drug.get(fld)
            if old_val and old_val == new_val:
                stats.confirmed.append(f"{drug_id}.{fld}")
            elif old_val and old_val != new_val:
                stats.changed.append(f"{drug_id}.{fld}")
                stats.corrections += 1
            else:
                stats.changed.append(f"{drug_id}.{fld}")

        validated.append(du)

    stats.schema_valid = len(stats.failed) == 0
    return ValidationResult(valid_updates=validated, stats=stats)
