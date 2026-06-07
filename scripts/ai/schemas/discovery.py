"""
schemas/discovery.py — Output schema for entity_discovery (Step 1 Phase B).

The LLM returns JSON matching DiscoveryEntity shape. These are queued in
discovery_queue (status='pending') and promoted to companies/drugs only
after human review.

KNOWN_DRUG_TARGETS override is applied in step1_discover_new_entities()
BEFORE any entity is written to the queue.
"""
from __future__ import annotations

from typing import Optional

# Expected JSON output shape from entity_discovery prompt.
# Used as documentation and for runtime key-checking — no Pydantic required.
DISCOVERY_ENTITY_KEYS = {
    "company_name":           str,    # required
    "drug_name":              str,    # optional (some entities are platform-only)
    "target":                 str,    # molecular target(s)
    "stage":                  str,    # Preclinical | Phase 1 | Phase 2 | Phase 3 | Approved
    "mechanism":              str,    # free text
    "confidence":             int,    # 0–100
    "relevance_score":        int,    # 1–10
    "relevance_rationale":    str,
    "competition_layer":      str,    # Direct | Adjacent | Watch | Reference
    "overlap":                str,    # Watch | Competitive | Adjacent
    "entity_type":            str,    # company | drug | platform
    "reason":                 str,    # why discovered
    "relationship_type":      str,    # peer_competitor | licensor | licensee | ...
    "relationship_confidence":str,    # confirmed | inferred | suggested
    "why_discovered":         str,    # specific search criteria
}

# Top-level JSON shape: {"new_entities": [<DiscoveryEntity>, ...]}
DISCOVERY_OUTPUT_KEYS = {
    "new_entities": list,
}


def validate_entity(raw: dict) -> tuple[bool, list[str]]:
    """Basic presence check on required fields. Returns (ok, missing_keys)."""
    required = ["company_name", "confidence", "relevance_score"]
    missing = [k for k in required if not raw.get(k)]
    return len(missing) == 0, missing
