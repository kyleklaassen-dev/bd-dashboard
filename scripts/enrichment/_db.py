"""
Shared Supabase CRUD helpers for enrichment scripts.

Call init_db(url, key) once after loading credentials, then use sb_get / sb_upsert /
sb_patch / sb_post / sb_delete anywhere.  If init_db() is never called (e.g. during
standalone node tests) _ensure_init() will lazy-load credentials from _common.
"""
from __future__ import annotations

import datetime
import os
import sys
from typing import Optional

import requests

# ── Module-level state ────────────────────────────────────────────────────────
_URL: str = ""
_HEADERS: dict = {}
_UPSERT_HEADERS: dict = {}
_initialized: bool = False


# ── Initialisation ────────────────────────────────────────────────────────────

def init_db(url: str, key: str) -> None:
    """Initialise the module with Supabase URL + service key."""
    global _URL, _HEADERS, _UPSERT_HEADERS, _initialized
    _URL = url
    _HEADERS = {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }
    _UPSERT_HEADERS = {
        **_HEADERS,
        "Prefer": "resolution=merge-duplicates,return=representation",
    }
    _initialized = True


def _ensure_init() -> None:
    """Lazy-init from credentials if init_db() was not called explicitly."""
    if _initialized:
        return
    _here = os.path.dirname(os.path.abspath(__file__))
    if _here not in sys.path:
        sys.path.insert(0, _here)
    from _common import load_credentials  # noqa: PLC0415
    url, key, _ = load_credentials(require_anthropic=False)
    init_db(url, key)


# ── Timestamp helpers (convenience, no side-effects) ─────────────────────────

def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()


def today_str() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


# ── CRUD helpers ──────────────────────────────────────────────────────────────

def sb_get(table: str, params: dict) -> list:
    _ensure_init()
    try:
        r = requests.get(f"{_URL}/rest/v1/{table}",
                         headers=_HEADERS, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _log(f"[sb_get {table}] {e}")
        return []


def sb_upsert(table: str, records: "list | dict",
              on_conflict: Optional[str] = None) -> list:
    _ensure_init()
    if isinstance(records, dict):
        records = [records]
    if not records:
        return []
    try:
        url = f"{_URL}/rest/v1/{table}"
        if on_conflict:
            url += f"?on_conflict={on_conflict}"
        r = requests.post(url, headers=_UPSERT_HEADERS, json=records, timeout=15)
        if r.status_code not in (200, 201):
            _log(f"[sb_upsert {table}] {r.status_code}: {r.text[:300]}")
            return []
        return r.json()
    except Exception as e:
        _log(f"[sb_upsert {table}] {e}")
        return []


def sb_insert(table: str, records: "list | dict") -> list:
    """Plain INSERT (no on-conflict merge). Use when duplicate rows per run are acceptable."""
    _ensure_init()
    if isinstance(records, dict):
        records = [records]
    if not records:
        return []
    try:
        r = requests.post(f"{_URL}/rest/v1/{table}",
                          headers=_HEADERS, json=records, timeout=15)
        if r.status_code not in (200, 201):
            _log(f"[sb_insert {table}] {r.status_code}: {r.text[:200]}")
            return []
        data = r.json()
        return data if isinstance(data, list) else ([data] if data else [])
    except Exception as e:
        _log(f"[sb_insert {table}] {e}")
        return []


def sb_post(table: str, record: dict) -> Optional[dict]:
    _ensure_init()
    try:
        r = requests.post(f"{_URL}/rest/v1/{table}",
                          headers=_HEADERS, json=record, timeout=15)
        if r.status_code not in (200, 201):
            _log(f"[sb_post {table}] {r.status_code}: {r.text[:200]}")
            return None
        data = r.json()
        return data[0] if data else None
    except Exception as e:
        _log(f"[sb_post {table}] {e}")
        return None


def sb_delete(table: str, match_params: dict) -> int:
    """DELETE rows matching match_params. Returns count of deleted rows."""
    _ensure_init()
    try:
        headers = {**_HEADERS, "Prefer": "return=representation"}
        r = requests.delete(f"{_URL}/rest/v1/{table}",
                            headers=headers, params=match_params, timeout=15)
        if r.status_code in (200, 204):
            deleted = r.json() if r.text and r.text.strip() not in ("", "[]") else []
            return len(deleted) if isinstance(deleted, list) else 0
        _log(f"[sb_delete {table}] HTTP {r.status_code}: {r.text[:200]}")
        return 0
    except Exception as e:
        _log(f"[sb_delete {table}] {e}")
        return 0


def sb_patch(table: str, record: dict, match_params: dict) -> bool:
    _ensure_init()
    try:
        r = requests.patch(f"{_URL}/rest/v1/{table}",
                           headers=_HEADERS, params=match_params,
                           json=record, timeout=15)
        if r.status_code in (200, 204):
            if r.status_code == 200 and r.text and r.text.strip() in ("[]", ""):
                _log(f"[sb_patch {table}] WARNING: 0 rows matched {match_params}")
                return False
            return True
        _log(f"[sb_patch {table}] HTTP {r.status_code}: {r.text[:300]}")
        return False
    except Exception as e:
        _log(f"[sb_patch {table}] {e}")
        return False


def _log(msg: str) -> None:
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)
