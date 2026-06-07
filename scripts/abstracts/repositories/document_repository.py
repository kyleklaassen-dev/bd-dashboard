"""
Supabase write access for the company_documents table.
"""
import os
import sys

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_SCRIPTS, "enrichment"))
from _db import sb_upsert  # noqa: E402


def upsert_documents(rows: list[dict]) -> int:
    """
    Upsert rows into company_documents, deduplicating on source_url.
    Returns the number of rows written.
    """
    if not rows:
        return 0
    result = sb_upsert("company_documents", rows, on_conflict="source_url")
    return len(result)
