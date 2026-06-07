"""
ai/client.py — Unified LLM client for the Meridian enrichment pipeline.

All anthropic.Anthropic().messages.create() calls must go through run_text()
or run_json() — scripts must never call the Anthropic SDK directly.

Public API
----------
  setup(api_key)                                   → initialize the module client
  run_text(cfg, prompt, *, timeout)  → str         free-text (web-search calls)
  run_json(cfg, prompt, *, system_override,        structured JSON calls
           max_retries)              → RunResult
  token_usage()                      → dict        {"in": N, "out": N}
  reset_tokens()                                   call at the start of each run

Internal helpers
----------------
  _acc_tokens(resp)  — add response token counts to the module accumulator
  _parse_json(text)  — strip markdown fences, parse JSON, return dict or None
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field, replace as dc_replace
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

# ── Module-level state ────────────────────────────────────────────────────────

_client: Optional[anthropic.Anthropic] = None
_RUN_TOKENS: dict[str, int] = {"in": 0, "out": 0}


def setup(api_key: str) -> None:
    """Initialize the shared Anthropic client. Call once at script startup."""
    global _client
    _client = anthropic.Anthropic(api_key=api_key)


def token_usage() -> dict[str, int]:
    """Return accumulated input/output token counts for the current run."""
    return dict(_RUN_TOKENS)


def reset_tokens() -> None:
    """Reset token accumulator. Call at the start of each enrichment run."""
    _RUN_TOKENS["in"] = 0
    _RUN_TOKENS["out"] = 0


def _acc_tokens(resp: anthropic.types.Message) -> None:
    try:
        _RUN_TOKENS["in"]  += getattr(resp.usage, "input_tokens",  0) or 0
        _RUN_TOKENS["out"] += getattr(resp.usage, "output_tokens", 0) or 0
    except Exception:
        pass


def _parse_json(text: str) -> Optional[dict]:
    """Strip markdown code fences and parse JSON. Returns dict or None."""
    text = text.strip()
    if "```" in text:
        for part in text.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break
    # Also strip trailing content after the closing brace
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse error: %s | raw[:400]: %s", exc, text[:400])
        return None


# ── PromptConfig ─────────────────────────────────────────────────────────────

@dataclass
class PromptConfig:
    """Immutable descriptor for a single prompt type.

    Create one instance per prompt in ai/prompts/*.py and pass it to
    run_text() or run_json(). Use dataclasses.replace() (re-exported as
    ``override()``) to create per-call variants (e.g. fast model).
    """
    name: str
    system: str
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096
    web_search_max_uses: int = 0  # 0 = no web_search tool

    def override(self, **kwargs) -> "PromptConfig":
        """Return a copy with selected fields replaced."""
        return dc_replace(self, **kwargs)


# ── RunResult ─────────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    """Structured return type from run_json()."""
    data: Optional[dict]           # parsed JSON dict, or None on failure
    raw_text: str                  # full LLM response text before parsing
    stop_reason: Optional[str]     # 'end_turn' | 'max_tokens' | None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    truncated: bool = False        # True when stop_reason == 'max_tokens'
    ok: bool = field(init=False)

    def __post_init__(self) -> None:
        self.ok = self.data is not None

    def log_cost(self, label: str = "") -> None:
        prefix = f"[{label}] " if label else ""
        logger.info(
            "%s%din / %dout ($%.4f) stop=%s%s",
            prefix,
            self.tokens_in, self.tokens_out, self.cost_usd, self.stop_reason,
            " TRUNCATED" if self.truncated else "",
        )


# ── Price table ($ per 1M tokens) ────────────────────────────────────────────

_PRICE: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6":          (3.0,  15.0),
    "claude-haiku-4-5-20251001":  (0.8,   4.0),
}

def _cost(model: str, tokens_in: int, tokens_out: int) -> float:
    p_in, p_out = _PRICE.get(model, (3.0, 15.0))
    return (tokens_in / 1e6 * p_in) + (tokens_out / 1e6 * p_out)


# ── Public call functions ─────────────────────────────────────────────────────

def run_text(
    cfg: PromptConfig,
    prompt: str,
    *,
    timeout: float = 90.0,
) -> str:
    """Run a web-search-enabled call. Returns concatenated text from all
    text content blocks, or '' on any failure. Token costs are accumulated
    in the module accumulator (token_usage()).

    Use for: landscape_search, company_intel_search.
    """
    if _client is None:
        raise RuntimeError("ai.client not initialized — call setup(api_key) first")

    tools = []
    if cfg.web_search_max_uses > 0:
        tools = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": cfg.web_search_max_uses,
        }]

    kwargs: dict = dict(
        model=cfg.model,
        max_tokens=cfg.max_tokens,
        system=cfg.system,
        messages=[{"role": "user", "content": prompt}],
    )
    if tools:
        kwargs["tools"] = tools
    if timeout:
        kwargs["timeout"] = timeout

    try:
        resp = _client.messages.create(**kwargs)
        _acc_tokens(resp)
        parts = [b.text for b in resp.content if hasattr(b, "text") and b.text]
        return "\n\n".join(parts)
    except Exception as exc:
        logger.warning("[%s] run_text failed (non-fatal): %s", cfg.name, exc)
        return ""


def run_json(
    cfg: PromptConfig,
    prompt: str,
    *,
    system_override: str = "",
    max_retries: int = 3,
) -> RunResult:
    """Run a JSON-extraction call with retry and truncation detection.
    Returns a RunResult whose .ok is False if all retries failed or JSON
    could not be parsed.

    Use for: entity_discovery, company_enrichment, coverage_fill.
    """
    if _client is None:
        raise RuntimeError("ai.client not initialized — call setup(api_key) first")

    system = system_override or cfg.system

    raw_text = ""
    stop_reason: Optional[str] = None
    tokens_in = tokens_out = 0

    for attempt in range(1, max_retries + 1):
        try:
            resp = _client.messages.create(
                model=cfg.model,
                max_tokens=cfg.max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = resp.content[0].text if resp.content else ""
            _acc_tokens(resp)
            tokens_in  = getattr(resp.usage, "input_tokens",  0) or 0
            tokens_out = getattr(resp.usage, "output_tokens", 0) or 0
            stop_reason = getattr(resp, "stop_reason", None)
            break
        except Exception as exc:
            logger.warning(
                "[%s] run_json attempt %d/%d failed: %s",
                cfg.name, attempt, max_retries, exc,
            )
            if attempt < max_retries:
                time.sleep(10 * attempt)

    if not raw_text:
        return RunResult(
            data=None, raw_text="", stop_reason=None,
            tokens_in=0, tokens_out=0, cost_usd=0.0, truncated=False,
        )

    truncated = stop_reason == "max_tokens"
    if truncated:
        logger.warning(
            "[%s] Response truncated at max_tokens=%d — JSON may be incomplete.",
            cfg.name, cfg.max_tokens,
        )

    data = _parse_json(raw_text)
    cost = _cost(cfg.model, tokens_in, tokens_out)

    return RunResult(
        data=data,
        raw_text=raw_text,
        stop_reason=stop_reason,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        truncated=truncated,
    )
