"""
Supabase read access for drug data.
"""
import os
import sys
import urllib.parse

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _SCRIPTS)
from _db import sb_get  # noqa: E402

from ..config import TARGET_STAGES


def get_phase2_plus_drugs() -> list[dict]:
    """Return all drugs at Phase 2 or later (up to 80)."""
    stage_values = ",".join(TARGET_STAGES)
    # sb_get passes params as query string via requests — use in.() PostgREST syntax
    return sb_get("drugs", {
        "select": "id,name,dev_code,target,stage,company_id",
        "stage":  f"in.({stage_values})",
        "limit":  "80",
    })


def find_by_name(name: str) -> list[dict]:
    """Return drugs whose name matches the given string (case-insensitive, partial)."""
    encoded = urllib.parse.quote(name)
    return sb_get("drugs", {
        "select": "id,name,dev_code,target,stage,company_id",
        "name":   f"ilike.*{encoded}*",
        "limit":  "5",
    })
