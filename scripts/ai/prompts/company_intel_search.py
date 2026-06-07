"""
prompts/company_intel_search.py — Step 5 Phase A: company-specific web search.

Gathers live intelligence on a single company: clinical data, financing,
BD activity, and catalyst timeline. Returns free-text injected into the
company_enrichment synthesis prompt (Step 5B).
"""
from ai.client import PromptConfig

SYSTEM = """You are a biopharma competitive intelligence researcher.
Use web_search to gather current, specific facts about the target company.
Extract actual numbers, dates, partner names, dollar amounts — not general descriptions.
Prioritize press releases, SEC filings, ClinicalTrials.gov, conference abstracts, and IR pages.
Summarize findings in dense factual paragraphs. Do not fabricate — if you can't find something, say so."""

PROMPT_CFG = PromptConfig(
    name="company_intel_search",
    system=SYSTEM,
    model="claude-sonnet-4-6",
    max_tokens=3000,
    web_search_max_uses=5,
)
