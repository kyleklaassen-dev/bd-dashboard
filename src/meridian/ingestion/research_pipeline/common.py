#!/usr/bin/env python3
"""
Shared base for the research.py split (§3): credentials, the Anthropic client,
Supabase headers, and log(). Bottom of the dependency star.
"""

import os
import datetime

import anthropic


ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SUPABASE_URL      = os.environ["SUPABASE_URL"]
SUPABASE_KEY      = os.environ["SUPABASE_SERVICE_KEY"]

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

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
