#!/usr/bin/env python3
"""
Shared base layer for the Meridian Issue generator (§3 write_meridian split).
=============================================================================
Extracted verbatim from write_meridian.py. Bottom of the dependency star: the
issue/* feature modules import from here; nothing here imports a feature module.

Holds: credentials + the Anthropic client + Supabase/GitHub REST headers, the
log() helper, the AREA_NAMES display map, and the pre-publish fact-check gate
primitives (_is_fabricated_source / _FABRICATED_SOURCE / _FACT_CHECK /
fact_check_filter) that fetch_* uses to drop fabricated-source rows.
"""

import os
import datetime

import requests
import anthropic


# ── Credentials ─────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SUPABASE_URL      = os.environ["SUPABASE_URL"]
SUPABASE_KEY      = os.environ["SUPABASE_SERVICE_KEY"]
GITHUB_TOKEN      = os.environ["GITHUB_TOKEN"]
GITHUB_REPO       = os.environ.get("GITHUB_REPO", "kyleklaassen-dev/bd-dashboard")

# PUBLIC anon key for the in-issue feedback widget (write-only to meridian_feedback via
# RLS; same key already embedded client-side in index.html). NOT the service key — never
# put the service key in a deployed page. Env override allowed.
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY",
    "sb_publishable_3GLfZ7b9Tjp9RFRcc4YZew_ov-fY7dI")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SB_HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}


# ── Pre-publish fact-check gate ───────────────────────────────────────────────
# A fact only earns a place in the Issue if it isn't backed by a FABRICATED source.
# This is the gate that would have stopped the veligrotug "gMG" line at the door:
# its catalyst carried a clinicaltrials.gov/search?term= URL (an invented citation).
# Keep the same patterns the Source Verifier uses. We DROP rows whose source_url is
# present-but-fabricated; we KEEP rows with no source (real-but-unsourced is fine —
# we never want to lose a real molecule like CLD-423), and log everything dropped.
import re as _re
_FABRICATED_SOURCE = _re.compile(
    r"(/search\?term=|/search\?q=|google\.com/search|clinicaltrials\.gov/search"
    r"|example\.com|placeholder\.|/drug-name-here|localhost|127\.0\.0\.1)", _re.I)

def _is_fabricated_source(url):
    return bool(url) and bool(_FABRICATED_SOURCE.search(str(url)))

_FACT_CHECK = {"dropped": [], "checked": 0}

def fact_check_filter(rows, label, url_field="source_url"):
    """Drop rows whose source_url is fabricated; keep the rest. Records drops."""
    kept = []
    for r in rows:
        _FACT_CHECK["checked"] += 1
        if _is_fabricated_source(r.get(url_field)):
            _FACT_CHECK["dropped"].append({"kind": label, "row": r.get("label") or r.get("headline") or r.get("id"), "url": r.get(url_field)})
        else:
            kept.append(r)
    n = len(rows) - len(kept)
    if n:
        log(f"  ⚖ fact-check: dropped {n} {label} with fabricated source URLs (kept {len(kept)})")
    return kept


GH_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept":        "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def log(msg):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ── Area display names ───────────────────────────────────────────────────────
AREA_NAMES = {
    "tl1a":  "TL1A / IBD",
    "tslp":  "TSLP / Severe Asthma",
    "il4ra": "IL-4Rα / Atopy",
    "igf1r": "IGF1R / Thyroid Eye Disease",
    "fcrn":  "FcRn / IgG Autoimmune",
    "tcell": "T-cell / Treg Therapy",
    "ibd":   "IBD (broad)",
    "respiratory": "Respiratory",
}
