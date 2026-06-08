"""
prompts/pkpd_extraction.py — PK/PD parameter extraction from PubMed abstracts.

Used by the research_queue 'pkpd_literature' processor (intelligence/research.py
process_pkpd_queue). Returns a single JSON object with a confidence score —
fits ai_client.run_json() (unlike research_news, which returns a JSON array).
"""
from __future__ import annotations

from ai.client import PromptConfig

SYSTEM = (
    "You are a pharmacokinetics data-extraction assistant. Extract only values "
    "explicitly stated in the abstract — never infer or estimate. Return JSON only."
)

PROMPT_TEMPLATE = """\
Extract PK/PD parameters from this abstract. Return JSON only — no markdown, no explanation.
Use null for any field not mentioned. Confidence should reflect how clearly the value appears
(1.0 = explicit numeric in results section, 0.5 = approximate or inferred, 0.0 = not found).

{{
  "half_life_h": null,
  "half_life_unit": null,
  "cmax_value": null,
  "cmax_unit": null,
  "auc_value": null,
  "auc_unit": null,
  "bioavailability_pct": null,
  "vd_value": null,
  "vd_unit": null,
  "clearance_value": null,
  "clearance_unit": null,
  "route": null,
  "species": null,
  "confidence": 0.0
}}

Rules:
- half_life_unit: use "h" for hours, "d" for days, "wk" for weeks
- route: MUST be exactly ONE of: "SC", "IV", "oral", or null — never a combination like "SC/IV"
  If multiple routes are studied, pick the PRIMARY route or null
- species: "human", "mouse", "monkey", "rat", or null
- If half_life_h is given in days in the abstract, convert to hours (multiply by 24) and set half_life_unit="h"
- Only extract values explicitly stated — do not infer or estimate
- confidence above 0.5 means the abstract explicitly reports the parameter with a numeric value

Abstract:
{abstract_text}"""

PKPD_CFG = PromptConfig(
    name="pkpd_extraction",
    system=SYSTEM,
    model="claude-haiku-4-5-20251001",
    max_tokens=512,
)
