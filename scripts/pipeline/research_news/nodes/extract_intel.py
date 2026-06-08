"""
Node: extract_intel
Phase 5a — sends batches of new articles to Claude and parses structured intel
records out of the JSON-array response.

Routed through ai_client.run_text() (not a raw anthropic.Anthropic() call) so
this gets the shared retry/timeout/token-accounting infrastructure. The prompt
lives in ai/prompts/research_news.py — discoverable from the prompt registry
instead of buried as a string literal in the monolith.

run_text (not run_json) because the response is a JSON *array*, and
ai_client._parse_json only handles top-level JSON objects (see source_verify.py
for the same pattern).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

_HERE     = os.path.dirname(os.path.abspath(__file__))
_PIPELINE = os.path.dirname(os.path.dirname(_HERE))
_SCRIPTS  = os.path.dirname(_PIPELINE)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import ai.client as ai_client                 # noqa: E402
import ai.prompts.research_news as _p          # noqa: E402
from _common import log                        # noqa: E402
from ..state import ResearchNewsState           # noqa: E402

_BATCH_SIZE = 6  # Sonnet writes richer body text per article — needs more headroom


def _research():
    import intelligence.research as research  # noqa: PLC0415
    return research


def _parse_array(raw: str) -> list:
    """Strip markdown fences and parse a top-level JSON array. Returns [] on failure."""
    text = raw.strip()
    if "```" in text:
        text = re.sub(r"^```[a-z]*\n?", "", text, flags=re.MULTILINE)
        text = text.replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        log(f"  JSON parse error: {exc} — raw[:200]: {text[:200]}")
        return []


def run(state: ResearchNewsState) -> ResearchNewsState:
    r = _research()
    articles = state.new_articles
    all_intel: list = []

    total_batches = (len(articles) + _BATCH_SIZE - 1) // _BATCH_SIZE
    for i in range(0, len(articles), _BATCH_SIZE):
        batch_num = i // _BATCH_SIZE + 1
        log(f"  [EXTRACT {batch_num}/{total_batches}] articles {i + 1}–"
            f"{min(i + _BATCH_SIZE, len(articles))} of {len(articles)}")
        batch = articles[i:i + _BATCH_SIZE]
        batch_text = "\n\n---\n\n".join(r._format_article_for_extraction(a) for a in batch)
        prompt = _p.PROMPT_TEMPLATE.format(
            articles=batch_text,
            ailux_context=r.AILUX_CONTEXT_COMPACT,
        )

        raw = ai_client.run_text(_p.EXTRACT_CFG, prompt, timeout=90.0)
        if not raw:
            log(f"  Batch {batch_num}: empty response — skipping")
            time.sleep(0.8)
            continue

        intel = _parse_array(raw)
        all_intel.extend(intel)
        log(f"  Batch {batch_num}: extracted {len(intel)} items")
        time.sleep(0.8)

    state.intel = all_intel
    log(f"Total extracted: {len(all_intel)} intel items")
    state.mark_complete("extract_intel")
    return state
