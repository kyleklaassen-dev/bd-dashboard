"""
Supabase access for the indication_patient_intelligence table.
"""
import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _SCRIPTS)
from _db import sb_get, sb_patch  # noqa: E402


def get_all_rows() -> list[dict]:
    return sb_get(
        "indication_patient_intelligence",
        {"select": "id,indication_name,source_urls"},
    )


def patch_source_urls(row_id: str, urls: list[str]) -> bool:
    return sb_patch(
        "indication_patient_intelligence",
        {"source_urls": urls},
        {"id": f"eq.{row_id}"},
    )
