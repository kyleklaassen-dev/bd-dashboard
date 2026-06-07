"""
prompts/entity_discovery.py — Step 1 Phase B: entity extraction + DB diff.

Takes landscape intel (from landscape_search) and existing DB company list.
Returns structured JSON of NEW entities to queue for human review.
"""
from ai.client import PromptConfig

SYSTEM = """You are a biopharma competitive intelligence analyst for Ailux Biotherapeutics.
Identify NEW companies or drug programs that are relevant to the given disease area but not yet in our
database. Return ONLY valid JSON — no markdown, no explanation."""

PROMPT_CFG = PromptConfig(
    name="entity_discovery",
    system=SYSTEM,
    model="claude-haiku-4-5-20251001",
    max_tokens=1500,
)
