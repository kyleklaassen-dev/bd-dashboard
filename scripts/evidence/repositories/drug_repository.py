"""
Read-only Supabase access for drug and area data.
"""
import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_SCRIPTS, "enrichment"))
from _db import sb_get  # noqa: E402


def get_drug(drug_id: str) -> dict | None:
    rows = sb_get("drugs", {"id": f"eq.{drug_id}", "select": "id,name,display_name"})
    return rows[0] if rows else None


def get_drug_ids_for_area(area: str) -> list[str]:
    rows = sb_get("drug_targets", {"target_id": f"eq.{area}", "select": "drug_id"})
    return sorted({r["drug_id"] for r in rows if r.get("drug_id")})


def get_trials_for_drug(drug_id: str) -> list[dict]:
    return sb_get("trials", {"drug_id": f"eq.{drug_id}", "select": "id,phase,indication"})
