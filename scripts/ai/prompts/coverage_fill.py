"""
prompts/coverage_fill.py — Post-pipeline: coverage fill for never-enriched drugs.

Backfills basic fields (target, mechanism, stage, etc.) for drugs with
last_synced_date=NULL or stale >14 days. Only fills empty fields — never
overwrites existing values (enforced in the caller, not the prompt).
"""
from ai.client import PromptConfig

SYSTEM = (
    "You are Meridian, a pharmaceutical intelligence assistant. "
    "Research the given drug and return structured JSON. "
    "Use null for fields you cannot determine — do NOT hallucinate."
)

PROMPT_CFG = PromptConfig(
    name="coverage_fill",
    system=SYSTEM,
    model="claude-haiku-4-5-20251001",
    max_tokens=600,
)
