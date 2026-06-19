#!/usr/bin/env python3
"""signal_base.py — creds, config, RSS sources, and the Supabase IO layer for the
Signal Monitor (§3 split). Imported by signal_monitor (orchestrator) + signal_scoring."""
import os
import json
import datetime
import urllib.request
import urllib.error
from pathlib import Path

# ── Environment ──────────────────────────────────────────────────────────────

_HERE = Path(__file__).resolve().parents[3]
_CREDS_DIR = _HERE

def _read_cred(fname: str) -> str:
    p = _CREDS_DIR / fname
    if p.exists():
        return p.read_text().strip()
    return os.environ.get(fname.lstrip(".").upper().replace("-","_"), "")

SUPABASE_URL   = "https://tghntyofptvfhmtchwcv.supabase.co"
SUPABASE_KEY   = _read_cred(".supabase_service_key") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY","")
SUPABASE_ANON  = _read_cred(".supabase_anon_key")    or os.environ.get("SUPABASE_ANON_KEY","")

TODAY = datetime.date.today().isoformat()
NOW_ISO = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

# ── Score threshold for triggering Tier 2 enrichment ─────────────────────────

TIER2_THRESHOLD = 8

# ── RSS Sources ───────────────────────────────────────────────────────────────

RSS_SOURCES = [
    {
        "name": "FDA",
        "url":  "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml",
        "signal_type": "fda",
        "ua": "Mozilla/5.0 Meridian-SignalMonitor/1.0",
    },
    {
        "name": "FierceBiotech",
        "url":  "https://www.fiercebiotech.com/rss/xml",
        "signal_type": "press_release",
        "ua": "Mozilla/5.0 Meridian-SignalMonitor/1.0",
    },
    {
        "name": "BioPharma Dive",
        "url":  "https://www.biopharmadive.com/feeds/news/",
        "signal_type": "press_release",
        "ua": "Mozilla/5.0 Meridian-SignalMonitor/1.0",
    },
    {
        "name": "STAT News",
        "url":  "https://www.statnews.com/feed/",
        "signal_type": "press_release",
        "ua": "Mozilla/5.0 Meridian-SignalMonitor/1.0",
    },
]

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str, indent: int = 0) -> None:
    prefix = "  " * indent
    print(f"{prefix}{msg}", flush=True)

# ── Supabase helpers ──────────────────────────────────────────────────────────

def _sb_request(method: str, path: str, data: dict | None = None,
                params: dict | None = None, key: str | None = None) -> list | None:
    key = key or SUPABASE_KEY
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        qs = "&".join(f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in params.items())
        url = f"{url}?{qs}"
    headers = {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }
    body = json.dumps(data).encode() if data else None
    req  = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        log(f"  ✗ SB {method} /{path}: HTTP {e.code} — {err[:200]}", indent=1)
        return None
    except Exception as exc:
        log(f"  ✗ SB {method} /{path}: {exc}", indent=1)
        return None

import urllib.parse

def sb_get(table: str, params: dict) -> list:
    return _sb_request("GET", table, params=params, key=SUPABASE_ANON) or []

def sb_upsert(table: str, record: dict, on_conflict: str | None = None) -> list | None:
    path = table
    if on_conflict:
        path = f"{table}?on_conflict={on_conflict}"
    headers_extra = {"Prefer": "resolution=merge-duplicates,return=representation"}
    # Use raw request for upsert
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=representation",
    }
    body = json.dumps(record).encode()
    req  = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        if e.code == 409:
            return []  # duplicate — expected for dedup
        log(f"  ✗ SB upsert /{table}: HTTP {e.code} — {err[:200]}", indent=1)
        return None
    except Exception as exc:
        log(f"  ✗ SB upsert /{table}: {exc}", indent=1)
        return None

def sb_insert(table: str, record: dict) -> list | None:
    return _sb_request("POST", table, data=record)

# ── Entity loading ─────────────────────────────────────────────────────────────
