"""
_common.py — Shared utilities for Meridian enrichment scripts.

Provides three things:
  load_credentials(require_anthropic=True) → (supabase_url, supabase_key, anthropic_key)
  sb_headers(key) → dict
  log(msg, indent=0) → None

All enrichment scripts import from here instead of duplicating credential
loading and boilerplate. Scripts that don't need Anthropic pass
require_anthropic=False; anthropic_key will be None in that case.
"""

from __future__ import annotations

import datetime
import os
import sys
from typing import Optional

# _common.py lives at scripts/enrichment/ — repo root is two levels up.
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))

_DEFAULT_SUPABASE_URL = "https://tghntyofptvfhmtchwcv.supabase.co"


def _read_file(name: str) -> Optional[str]:
    """Read a credential file from the repo root, return stripped value or None."""
    p = os.path.join(_REPO, name)
    try:
        v = open(p).read().strip()
        return v or None
    except OSError:
        return None


def load_credentials(require_anthropic: bool = True) -> tuple[str, str, Optional[str]]:
    """
    Load Supabase and Anthropic credentials.

    Priority for each value: environment variable → repo-root dotfile → default (URL only).
    Exits with a clear error message if a required credential is missing.

    Returns:
        (supabase_url, supabase_key, anthropic_key)
        anthropic_key is None when require_anthropic=False and the key is absent.
    """
    supabase_url: str = (
        os.environ.get("SUPABASE_URL") or
        _read_file(".supabase_url") or
        _DEFAULT_SUPABASE_URL
    )
    supabase_key: str = (
        os.environ.get("SUPABASE_SERVICE_KEY") or
        _read_file(".supabase_service_key") or ""
    )
    anthropic_key: Optional[str] = (
        os.environ.get("ANTHROPIC_API_KEY") or
        _read_file(".anthropic_api_key") or None
    )

    if not supabase_key:
        print("ERROR: SUPABASE_SERVICE_KEY not set and .supabase_service_key not found")
        sys.exit(1)
    if require_anthropic and not anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY not set and .anthropic_api_key not found")
        sys.exit(1)

    return supabase_url, supabase_key, anthropic_key


def sb_headers(key: str) -> dict:
    """Standard Supabase REST API request headers (without Prefer — add per-call as needed)."""
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def log(msg: str, indent: int = 0) -> None:
    """Print a timestamped log line with optional indentation."""
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {'  ' * indent}{msg}", flush=True)
