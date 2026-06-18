#!/usr/bin/env python3
"""
Shared base for the research.py split (§3): credentials, the Anthropic client,
Supabase headers, and log(). Bottom of the dependency star.
"""

import os
import datetime

import anthropic


# repo root: this file is src/meridian/ingestion/research_pipeline/common.py → 5 dirnames up.
_WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


def _read_key(env, filename, default=""):
    """Credential read, tolerant for CI/tests: env var first, then the repo-root file,
    then default (never raises) so this base imports test-clean without secrets."""
    if os.environ.get(env, "").strip():
        return os.environ[env].strip()
    try:
        with open(os.path.join(_WORKSPACE, filename)) as f:
            return f.read().strip()
    except FileNotFoundError:
        return default


ANTHROPIC_API_KEY = _read_key("ANTHROPIC_API_KEY", ".anthropic_api_key")
SUPABASE_URL      = _read_key("SUPABASE_URL", ".supabase_url", "https://tghntyofptvfhmtchwcv.supabase.co")
SUPABASE_KEY      = _read_key("SUPABASE_SERVICE_KEY", ".supabase_service_key")

# Guarded: the SDK raises if api_key is empty, which would break test-clean imports.
# Real runs (env/file present) get a live client; key-less imports get None (LLM call
# sites only run in real pipelines, never in pure-function tests).
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}
SB_UPSERT = {**SB_HEADERS, "Prefer": "resolution=ignore-duplicates,return=representation"}


def log(msg):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")
