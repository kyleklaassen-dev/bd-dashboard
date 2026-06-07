"""
Supabase access for the drug_sources table.
"""
import os
import sys
from datetime import datetime, timezone

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_SCRIPTS, "enrichment"))
from _db import sb_get, sb_insert  # noqa: E402

SESSION_LABEL = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_existing_source_urls(drug_id: str) -> set[str]:
    rows = sb_get("drug_sources", {"drug_id": f"eq.{drug_id}", "select": "source_url"})
    return {r["source_url"] for r in rows if r.get("source_url")}


def insert_sources(rows: list[dict]) -> bool:
    """Plain INSERT — no on-conflict merge. Returns True if all rows landed."""
    if not rows:
        return True
    result = sb_insert("drug_sources", rows)
    return len(result) > 0
