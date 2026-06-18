#!/usr/bin/env python3
"""
Company name → Supabase id resolution (§3 company_enrichment split).
====================================================================
Extracted verbatim from company_enrichment.py. Maps a free-text company name
(possibly an LLM variant, alias, ticker, or parenthetical-qualified form) to the
canonical companies.id, preventing ghost sub-entity creation.

TODO (dedupe, supervised): overlaps the shared identity/entity_matcher resolver —
consolidate once the write-path routing lands.
"""

import re
from typing import Optional

from meridian.enrichment.company.common import log, sb_get


# ══════════════════════════════════════════════════════════════════════════
# COMPANY NAME → SUPABASE ID MAPPING
# ══════════════════════════════════════════════════════════════════════════

COMPANY_ALIASES = {
    "johnson & johnson":     "jnj",
    "j&j":                   "jnj",
    "eli lilly":             "lilly",
    "roche":                 "roche",
    "roche/genentech":       "roche",
    "genentech":             "roche",
    "boehringer ingelheim":  "boehringer",
    "bristol myers squibb":  "bms",
    "bristol-myers squibb":  "bms",
    "merck":                 "merck",
    "merck & co":            "merck",
    "merck & co.":           "merck",
    "generate:biomedicines": "generate",
    "harbour biomed":        "harbourbiomed",
    "santa ana bio":         "santaana",
}


def get_company_map() -> dict[str, str]:
    """Fetch all companies from Supabase → dict: name/alias/ticker/group_id → id.

    Including ticker and group_id means that if enrichment discovers a variant
    name like 'Spyre Therapeutics (TL1A mono)', it can still resolve to the
    canonical 'spyre' company_id via ticker or group_id match — preventing
    ghost sub-entity creation.
    """
    try:
        rows = sb_get("companies", {"select": "id,name,ticker,group_id"})
        cmap = {}
        for row in rows:
            cmap[row["id"].lower()] = row["id"]
            cmap[row["name"].lower()] = row["id"]
            if row.get("group_id"):
                cmap[row["group_id"].lower()] = row["id"]
            # Ticker-based lookup (skip generic placeholders)
            ticker = (row.get("ticker") or "").strip()
            if ticker and ticker.upper() not in ("PRIVATE", ""):
                cmap[ticker.lower()] = row["id"]
        cmap.update(COMPANY_ALIASES)
        return cmap
    except Exception as e:
        log(f"Company map fetch error: {e}")
        return {}


def resolve_company_id(name: str, company_map: dict) -> Optional[str]:
    """Resolve a company name to its canonical company_id.

    Resolution order:
    1. Exact lowercase match
    2. Strip parenthetical qualifier (e.g. 'Spyre (TL1A mono)' → 'Spyre') then exact match
    3. Substring match (either direction)

    The parenthetical strip prevents enrichment from creating ghost sub-entities
    when Claude qualifies a known company with a program descriptor.
    """
    lc = (name or "").strip().lower()
    if not lc:
        return None
    # 1. Exact match
    if lc in company_map:
        return company_map[lc]
    # 2. Strip trailing parenthetical qualifier, try again
    base = re.sub(r'\s*\([^)]*\)\s*$', '', lc).strip()
    if base and base != lc and base in company_map:
        return company_map[base]
    # 3. Substring match (both directions)
    for key, cid in company_map.items():
        if len(lc) >= 4 and (lc in key or key in lc):
            return cid
    # 4. Base-name substring match
    if base and base != lc:
        for key, cid in company_map.items():
            if len(base) >= 4 and (base in key or key in base):
                return cid
    return None
