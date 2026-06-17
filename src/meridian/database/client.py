#!/usr/bin/env python3
"""
src/meridian/database/client.py — the ONE shared Supabase REST client.
=============================================================
Replaces the 30 ad-hoc `sb_upsert()` helpers scattered across scripts. All
database access in the new architecture goes through this module so behavior
(headers, paging, error handling, on_conflict) is consistent in one place.

This is infrastructure only — it does NOT enforce governance. Governance lives
in the per-entity Writers (e.g. drug_writer.DrugWriter), which use this client.
"""
import os, json, pathlib, urllib.request, urllib.error, urllib.parse

_BASE = pathlib.Path(__file__).resolve().parents[3]
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")


def _key():
    k = os.environ.get("SUPABASE_SERVICE_KEY")
    if k:
        return k.strip()
    f = _BASE / ".supabase_service_key"
    return f.read_text().strip() if f.exists() else ""


def _headers(extra=None):
    k = _key()
    h = {"apikey": k, "Authorization": f"Bearer {k}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def _req(method, path, body=None, prefer=None):
    h = _headers({"Prefer": prefer} if prefer else None)
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            t = resp.read().decode()
            return resp.status, (json.loads(t) if t else None), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers


def select(table, params=None):
    """GET rows. params: dict of PostgREST filters, e.g. {'id':'eq.sl325','select':'*'}."""
    q = urllib.parse.urlencode(params or {"select": "*"}, safe="*.,()")
    code, body, _ = _req("GET", f"{table}?{q}")
    return body if isinstance(body, list) else []


def select_all(table, params=None):
    """Paged GET (handles >1000 rows)."""
    out, start = [], 0
    base = dict(params or {"select": "*"})
    while True:
        q = urllib.parse.urlencode(base, safe="*.,()")
        h = _headers({"Range": f"{start}-{start+999}"})
        r = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{table}?{q}", headers=h, method="GET")
        try:
            with urllib.request.urlopen(r) as resp:
                d = json.loads(resp.read().decode() or "[]")
        except urllib.error.HTTPError:
            break
        if not isinstance(d, list):
            break
        out += d
        if len(d) < 1000:
            break
        start += 1000
    return out


def count(table, flt=None):
    q = "select=id" + (f"&{flt}" if flt else "")
    code, _, hdrs = _req("GET", f"{table}?{q}", prefer="count=exact")
    cr = (hdrs.get("content-range") if hdrs else "") or ""
    v = cr.split("/")[-1]
    return int(v) if v.isdigit() else None


def insert(table, rows, on_conflict=None, ignore_duplicates=False, return_rep=True):
    prefer = "return=representation" if return_rep else "return=minimal"
    if ignore_duplicates:
        prefer += ",resolution=ignore-duplicates"
    elif on_conflict:
        prefer += ",resolution=merge-duplicates"
    path = table + (f"?on_conflict={on_conflict}" if on_conflict else "")
    return _req("POST", path, rows if isinstance(rows, list) else [rows], prefer=prefer)


def update(table, flt, patch, return_rep=False):
    prefer = "return=representation" if return_rep else "return=minimal"
    return _req("PATCH", f"{table}?{flt}", patch, prefer=prefer)


def delete(table, flt):
    return _req("DELETE", f"{table}?{flt}", prefer="return=minimal")


# table column registry (cached) — used by writers to reject unknown columns
_COLS = {}


def columns(table):
    if table not in _COLS:
        spec_code, spec, _ = _req("GET", "")
        defs = (spec or {}).get("definitions") or {} if isinstance(spec, dict) else {}
        _COLS.update({t: list((d.get("properties") or {}).keys()) for t, d in defs.items()})
    return set(_COLS.get(table, []))
