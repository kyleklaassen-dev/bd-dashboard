#!/usr/bin/env python3
"""Export live Supabase public schema to migrations/v1_schema.sql (read-only).

Uses REST API only — no DDL, no writes. Optional full export via Management API
when SUPABASE_PAT or .supabase_pat is present (information_schema query).

Usage:
    python3 scripts/export_schema_snapshot.py
    python3 scripts/export_schema_snapshot.py --output migrations/v1_schema.sql
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

# NOTE: three .parent hops — this file lives at scripts/build/, two hops would
# land on scripts/ (a bug introduced when the scripts/ reorg moved this file deeper).
ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT = ROOT / "migrations" / "v1_schema.sql"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://tghntyofptvfhmtchwcv.supabase.co")
ANON_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRnaG50eW9mcHR2ZmhtdGNod2N2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkwMzYxMTIsImV4cCI6MjA5NDYxMjExMn0.USGvaw5o9jgvJcpRYCADTgXDi7pF2v97qQsyIoyaP5g",
)
PROJECT_REF = SUPABASE_URL.replace("https://", "").split(".supabase.co")[0]

SKIP_OBJECTS = re.compile(
    r"(_pkey|_key|_idx|_check|_fkey|trg_|_trigger$|capture_field_changes|audit_trigger)",
    re.I,
)


def rest_headers() -> dict[str, str]:
    return {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}


def rest_get(path: str) -> list | dict:
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=rest_headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def rest_exists(name: str) -> bool:
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{name}?select=*&limit=0",
        headers={**rest_headers(), "Prefer": "count=exact"},
    )
    try:
        urllib.request.urlopen(req, timeout=12)
        return True
    except urllib.error.HTTPError as e:
        return e.code not in (400, 404)


def sample_row(name: str) -> dict:
    try:
        rows = rest_get(f"{name}?select=*&limit=1")
        return rows[0] if rows else {}
    except Exception:
        return {}


def infer_pg_type(val) -> str:
    if val is None:
        return "text"
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "bigint"
    if isinstance(val, float):
        return "numeric"
    if isinstance(val, (list, dict)):
        return "jsonb"
    if isinstance(val, str):
        if re.match(r"^\d{4}-\d{2}-\d{2}T", val):
            return "timestamptz"
        if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
            return "date"
        if re.match(r"^[0-9a-f-]{36}$", val, re.I):
            return "uuid"
    return "text"


def load_pat() -> str | None:
    for src in (
        os.environ.get("SUPABASE_PAT"),
        (ROOT / ".supabase_pat").read_text().strip()
        if (ROOT / ".supabase_pat").exists()
        else None,
    ):
        if src:
            return src
    return None


def mgmt_query(pat: str, sql: str) -> list[dict]:
    url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
    req = urllib.request.Request(
        url,
        data=json.dumps({"query": sql}).encode(),
        headers={
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
            "User-Agent": "meridian-pipeline/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        body = json.loads(r.read())
    return body if isinstance(body, list) else []


def export_via_mgmt(pat: str) -> str | None:
    """Full pg_dump-style export via information_schema (read-only SELECT)."""
    tables = mgmt_query(
        pat,
        """
        SELECT table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_type, table_name;
        """,
    )
    if not tables:
        return None

    lines = [
        "-- Exported via Supabase Management API (information_schema) — read-only query.",
        f"-- Project: {PROJECT_REF}",
        f"-- Date: {date.today().isoformat()}",
        "",
    ]

    cols = mgmt_query(
        pat,
        """
        SELECT table_name, column_name, data_type, udt_name, is_nullable,
               column_default, character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position;
        """,
    )
    by_table: dict[str, list] = {}
    for c in cols:
        by_table.setdefault(c["table_name"], []).append(c)

    for t in tables:
        name = t["table_name"]
        ttype = t["table_type"]
        if ttype == "VIEW":
            view_def = mgmt_query(
                pat,
                f"""
                SELECT view_definition FROM information_schema.views
                WHERE table_schema = 'public' AND table_name = '{name}';
                """,
            )
            if view_def:
                lines.append(f"CREATE OR REPLACE VIEW {name} AS")
                lines.append(view_def[0]["view_definition"].strip().rstrip(";") + ";")
                lines.append("")
            continue

        col_defs = by_table.get(name, [])
        if not col_defs:
            continue
        parts = []
        for c in col_defs:
            dt = c["udt_name"] if c["udt_name"] != "uuid" else "uuid"
            if c["data_type"] == "ARRAY":
                dt = c["udt_name"].lstrip("_") + "[]"
            elif c["data_type"] == "USER-DEFINED":
                dt = c["udt_name"]
            nullable = "" if c["is_nullable"] == "YES" else " NOT NULL"
            default = f" DEFAULT {c['column_default']}" if c["column_default"] else ""
            parts.append(f"    {c['column_name']} {dt}{nullable}{default}")
        lines.append(f"CREATE TABLE IF NOT EXISTS {name} (")
        lines.append(",\n".join(parts))
        lines.append(");")
        lines.append("")

    return "\n".join(lines)


def collect_candidates() -> set[str]:
    names: set[str] = set()
    for sql in ROOT.rglob("*.sql"):
        if "_archive" in sql.parts or sql.name == "v1_schema.sql":
            continue
        text = sql.read_text(errors="replace")
        for m in re.finditer(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?(\w+)",
            text,
            re.I,
        ):
            names.add(m.group(1).lower())

    offset = 0
    while True:
        batch = rest_get(f"schema_change_log?select=object_name&limit=1000&offset={offset}")
        if not batch:
            break
        for row in batch:
            obj = (row.get("object_name") or "").replace("public.", "").split(".")[0]
            if obj and re.match(r"^[a-z][a-z0-9_]*$", obj) and not SKIP_OBJECTS.search(obj):
                names.add(obj)
        if len(batch) < 1000:
            break
        offset += 1000
    return names


def ddl_from_archive(name: str) -> str | None:
    """Best-effort: pull CREATE block from archived migration SQL."""
    archive = ROOT / "migrations" / "_archive"
    if not archive.exists():
        for sql in ROOT.rglob("*.sql"):
            if "_archive" in sql.parts:
                continue
            text = sql.read_text(errors="replace")
            m = re.search(
                rf"CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?{name}\b.*?;",
                text,
                re.I | re.DOTALL,
            )
            if m:
                return m.group(0).strip()
        return None
    for sql in archive.rglob("*.sql"):
        text = sql.read_text(errors="replace")
        m = re.search(
            rf"CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW)\s+(?:IF\s+NOT EXISTS\s+)?(?:public\.)?{name}\b.*?;",
            text,
            re.I | re.DOTALL,
        )
        if m:
            return m.group(0).strip()
    return None


def export_via_rest() -> str:
    candidates = collect_candidates()
    live: list[tuple[str, dict]] = []
    for name in sorted(candidates):
        if rest_exists(name):
            live.append((name, sample_row(name)))

    lines = [
        "-- =============================================================================",
        "-- v1_schema.sql",
        f"-- Snapshot of live Supabase public schema — {date.today().isoformat()}",
        f"-- Project: {PROJECT_REF}",
        "--",
        "-- Generated by: scripts/export_schema_snapshot.py (read-only REST queries)",
        "--",
        "-- IMPORTANT:",
        "--   • Do NOT apply this file to the existing production database.",
        "--   • Use only for fresh environments, documentation, and diffing future v2+ migrations.",
        "--   • Column types inferred from sample rows where data exists; empty tables",
        "--     fall back to archived migration SQL when available.",
        "--   • Does NOT include: RLS policies, triggers, functions, indexes, grants.",
        "--     Re-export with SUPABASE_PAT for a fuller information_schema dump.",
        "-- =============================================================================",
        "",
        f"-- Live objects discovered: {len(live)}",
        "",
    ]

    archive_used = []
    inferred = []

    for name, row in live:
        archived = ddl_from_archive(name)
        if archived:
            lines.append(f"-- source: archived migration SQL")
            lines.append(archived)
            lines.append("")
            archive_used.append(name)
            continue

        if row:
            parts = [f"    {col} {infer_pg_type(val)}" for col, val in row.items()]
            lines.append(f"-- source: REST sample row (types inferred)")
            lines.append(f"CREATE TABLE IF NOT EXISTS {name} (")
            lines.append(",\n".join(parts))
            lines.append(");")
            lines.append("")
            inferred.append(name)
        else:
            lines.append(f"-- source: unknown (empty table, no archive DDL found)")
            lines.append(f"-- TABLE {name} EXISTS in production but schema could not be inferred.")
            lines.append("")

    lines.extend([
        "-- =============================================================================",
        "-- Export summary",
        f"--   From archive SQL: {len(archive_used)}",
        f"--   From REST inference: {len(inferred)}",
        f"--   Unresolved (empty): {len(live) - len(archive_used) - len(inferred)}",
        "-- =============================================================================",
    ])
    return "\n".join(lines)


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--output") + 1]) if "--output" in sys.argv else DEFAULT_OUT
    pat = load_pat()
    if pat:
        print("Attempting full export via Management API (read-only)...")
        try:
            content = export_via_mgmt(pat)
            if content:
                header = (
                    f"-- Full information_schema export — {date.today().isoformat()}\n"
                    f"-- Project: {PROJECT_REF}\n"
                    "-- Do NOT apply to existing production.\n\n"
                )
                out.write_text(header + content)
                print(f"Wrote {out} ({len(content)} bytes, Management API)")
                return 0
        except Exception as e:
            print(f"Management API export failed ({e}), falling back to REST.", file=sys.stderr)

    print("Exporting via read-only REST queries (this takes ~90s)...")
    content = export_via_rest()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content)
    print(f"Wrote {out} ({len(content)} bytes, REST)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
