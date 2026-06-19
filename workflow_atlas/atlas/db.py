"""
Database lens — model the Supabase tables the way `parse.py` models workflows.

Three ground-truth sources, all read statically from the repo:
  1. CREATE TABLE statements in migrations/*.sql + docs/**/*.sql  → schema + columns
  2. sb_*/client table calls in src/ + scripts/                   → who writes / reads each table
  3. docs/database/governance_table.md                            → core-table owner / Writer / validation

From those we can answer "how is it all wired" and, more usefully, "where are the
gaps": dead tables, writes with no Writer, core tables written by ad-hoc paths
(the governance rule in CLAUDE.md), write-only / read-only tables.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .parse import REPO_ROOT, load_workflows

# --- access-helper vocabulary (from src/meridian/database/client.py + sb_* shims) ---
READ_FUNCS = {
    "sb_get", "sb_get_all", "sb_list", "sb_all", "select", "select_all",
    "count", "columns", "sb_rpc",
}
WRITE_FUNCS = {
    "sb_upsert", "sb_insert", "sb_insert_new", "sb_insert_mol_intel",
    "sb_post", "sb_post_rows", "sb_post_single", "sb_patch", "sb_patch_row",
    "sb_patch_filter", "sb_write", "sb_update_where", "sb_delete",
    "sb_delete_by_drug_id", "insert", "update", "delete",
}
_ALL_FUNCS = READ_FUNCS | WRITE_FUNCS
_CALL = re.compile(
    r"\b(" + "|".join(sorted(_ALL_FUNCS, key=len, reverse=True)) +
    r")\(\s*f?['\"]([a-z_][a-z0-9_]*)"
)

# core tables → (designated writer file, Writer class) from governance_table.md / CLAUDE.md
CORE_TABLES = {
    "drugs": ("drug_writer.py", "DrugWriter"),
    "companies": ("company_writer.py", "CompanyWriter"),
    "entity_edges": ("edge_writer.py", "EdgeWriter"),
    "catalysts": ("catalyst_writer.py", "CatalystWriter"),
}

# directories whose writes are historical / not part of the live pipeline
ARCHIVE_HINTS = ("/archive/", "/one_off/", "/_retired", "/deprecated/")


@dataclass
class Ref:
    file: str
    line: int
    func: str
    mode: str  # "read" | "write"


@dataclass
class Table:
    name: str
    defined: bool = False                 # has a CREATE TABLE in the repo
    create_files: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    refs: list[Ref] = field(default_factory=list)
    governance: dict | None = None        # owner/writer/validation if documented

    @property
    def is_core(self) -> bool:
        return self.name in CORE_TABLES

    @property
    def writers(self) -> list[Ref]:
        return [r for r in self.refs if r.mode == "write"]

    @property
    def readers(self) -> list[Ref]:
        return [r for r in self.refs if r.mode == "read"]

    @property
    def writer_files(self) -> set[str]:
        return {r.file for r in self.writers}

    @property
    def reader_files(self) -> set[str]:
        return {r.file for r in self.readers}


# --------------------------------------------------------------------------- #
# 1. schema from SQL
# --------------------------------------------------------------------------- #
_CREATE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"']?([a-z_][a-z0-9_]*)[\"']?\s*\(",
    re.IGNORECASE,
)


def _columns_from_block(sql: str, start: int) -> list[str]:
    """Pull column names from the paren block beginning at `start` (the '(')."""
    depth, i = 0, start
    while i < len(sql):
        if sql[i] == "(":
            depth += 1
        elif sql[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    body = sql[start + 1:i]
    cols, depth, cur = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            cols.append(cur.strip()); cur = ""
        else:
            cur += ch
    cols.append(cur.strip())
    out = []
    for c in cols:
        tok = c.split()[0].strip("\"'`,") if c.split() else ""
        if tok and tok.upper() not in {
            "CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "EXCLUDE", "INDEX"
        }:
            out.append(tok)
    return out


# template / example SQL whose CREATE TABLEs are placeholders, not real schema
_TEMPLATE_SQL = ("migration_template.sql", "template")


def _strip_sql_comments(sql: str) -> str:
    """Drop `-- ...` line comments and /* ... */ blocks so commented-out
    CREATE TABLE statements aren't counted as real tables."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return "\n".join(re.sub(r"--.*$", "", ln) for ln in sql.splitlines())


@lru_cache(maxsize=1)
def _schema() -> dict[str, dict]:
    out: dict[str, dict] = {}
    sql_files = list((REPO_ROOT / "migrations").glob("*.sql"))
    sql_files += list((REPO_ROOT / "docs").rglob("*.sql"))
    for f in sql_files:
        if any(t in f.name.lower() for t in _TEMPLATE_SQL):
            continue  # placeholder schema (e.g. `new_table` in migration_template.sql)
        try:
            sql = _strip_sql_comments(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        for m in _CREATE.finditer(sql):
            name = m.group(1).lower()
            rec = out.setdefault(name, {"files": set(), "columns": []})
            rec["files"].add(str(f.relative_to(REPO_ROOT)))
            if not rec["columns"]:
                rec["columns"] = _columns_from_block(sql, m.end() - 1)
    return out


# --------------------------------------------------------------------------- #
# 2. table access from code
# --------------------------------------------------------------------------- #
# REST-style access the sb_*/client scan misses: f-string URLs like
#   get(f"narrative_feedback?select=...")  ·  _request("PATCH", f"intel?id=eq.{x}")
#   "/rest/v1/companies"  ·  sb_get(f"drugs?select=id")
# A bare "<table>?<query>" inside a string is a Supabase REST path. PATCH/POST/DELETE
# in the same call → write; otherwise read. (Heuristic, but recovers the big class
# of false "unused" tables.)
_REST_PATH = re.compile(r"['\"]/?(?:rest/v1/)?([a-z_][a-z0-9_]*)\?(?:select|[a-z_]+=)")
_WRITE_HINT = re.compile(r"\b(PATCH|POST|PUT|DELETE|patch|post|delete|upsert|insert|update)\b")


@lru_cache(maxsize=1)
def _access() -> dict[str, list[Ref]]:
    out: dict[str, list[Ref]] = {}
    for base in ("src", "scripts"):
        for f in (REPO_ROOT / base).rglob("*.py"):
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(f.relative_to(REPO_ROOT))
            for m in _CALL.finditer(txt):
                func, table = m.group(1), m.group(2).lower()
                mode = "write" if func in WRITE_FUNCS else "read"
                line = txt.count("\n", 0, m.start()) + 1
                out.setdefault(table, []).append(Ref(rel, line, func, mode))
            # second pass: REST-path strings (f-string queries, /rest/v1/ URLs)
            for m in _REST_PATH.finditer(txt):
                table = m.group(1).lower()
                ctx = txt[max(0, m.start() - 40): m.start() + 20]
                mode = "write" if _WRITE_HINT.search(ctx) else "read"
                line = txt.count("\n", 0, m.start()) + 1
                out.setdefault(table, []).append(Ref(rel, line, "rest", mode))
    return out


# --------------------------------------------------------------------------- #
# 3. governance doc
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _governance() -> dict[str, dict]:
    out: dict[str, dict] = {}
    doc = REPO_ROOT / "docs" / "database" / "governance_table.md"
    if not doc.is_file():
        return out
    for ln in doc.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        m = re.match(r"`([a-z_]+)`", cells[0]) if cells else None
        if not m or len(cells) < 3:
            continue
        name = m.group(1)
        out[name] = {
            "owner": cells[1] if len(cells) > 1 else "",
            "writer": cells[2] if len(cells) > 2 else "",
            "validation": cells[3] if len(cells) > 3 else "",
            "source_hierarchy": cells[4] if len(cells) > 4 else "",
        }
    return out


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def load_tables() -> tuple[Table, ...]:
    schema, access, gov = _schema(), _access(), _governance()
    names = set(schema) | set(access) | set(CORE_TABLES) | set(gov)
    tables = []
    for name in sorted(names):
        t = Table(name=name)
        if name in schema:
            t.defined = True
            t.create_files = sorted(schema[name]["files"])
            t.columns = schema[name]["columns"]
        t.refs = access.get(name, [])
        t.governance = gov.get(name)
        tables.append(t)
    return tuple(tables)


def tables_for_workflow(table_index: dict[str, Table]) -> dict[str, set[str]]:
    """workflow name -> tables its entrypoint files directly read/write."""
    out: dict[str, set[str]] = {}
    for wf in load_workflows():
        ep_files = {ep.path for ep in wf.all_entrypoints if ep.path}
        touched = {t.name for t in table_index.values()
                   if (t.writer_files | t.reader_files) & ep_files}
        if touched:
            out[wf.name] = touched
    return out


def workflows_touching(table: Table) -> set[str]:
    ep_to_wf: dict[str, set[str]] = {}
    for wf in load_workflows():
        for ep in wf.all_entrypoints:
            if ep.path:
                ep_to_wf.setdefault(ep.path, set()).add(wf.name)
    files = table.writer_files | table.reader_files
    out: set[str] = set()
    for f in files:
        out |= ep_to_wf.get(f, set())
    return out


# --------------------------------------------------------------------------- #
# audit — the gaps
# --------------------------------------------------------------------------- #
@dataclass
class DBFinding:
    severity: str
    category: str
    title: str
    detail: str
    tables: list[str] = field(default_factory=list)


def _is_archive(path: str) -> bool:
    return any(h in path for h in ARCHIVE_HINTS)


def db_audit(tables) -> list[DBFinding]:
    findings: list[DBFinding] = []
    by_name = {t.name: t for t in tables}

    # A) core-table writes bypassing the designated Writer -------------------
    for name, (writer_file, cls) in CORE_TABLES.items():
        t = by_name.get(name)
        if not t:
            continue
        active, archived = [], []
        for r in t.writers:
            if writer_file in r.file or "database/" in r.file:
                continue  # the Writer itself (or the writer package) is allowed
            (archived if _is_archive(r.file) else active).append(r)
        if active:
            locs = ", ".join(f"`{r.file}:{r.line}`" for r in active[:8])
            extra = f" (+{len(active) - 8} more)" if len(active) > 8 else ""
            findings.append(DBFinding(
                "error", "Writer bypass",
                f"`{name}` written by {len(active)} ad-hoc path(s) outside {cls}",
                f"CLAUDE.md requires core tables go through their Writer. Active "
                f"writes not via `{writer_file}`: {locs}{extra}. "
                + (f"({len(archived)} more in archive/one-off — lower priority.)"
                   if archived else ""),
                [name]))
        elif archived:
            findings.append(DBFinding(
                "info", "Writer bypass (archived)",
                f"`{name}` has {len(archived)} bypassing write(s), all in archive/one-off",
                "Historical scripts write this core table directly; not on the live "
                "path, but worth retiring so they can't be re-run.",
                [name]))

    # B) no static reference found — a HINT to investigate, NOT a drop list.
    # Verified 2026-06-18: of the tables flagged here, several are real-but-empty
    # framework tables (correction_labels, target_known_drugs) referenced only in
    # SQL views, and the big trial tables are written via DYNAMIC table names that
    # a static scan can't follow. Never drop a table off this signal alone —
    # confirm against live row counts + SQL views + the dashboard first.
    for t in tables:
        if t.defined and not t.refs:
            findings.append(DBFinding(
                "info", "No static reference found",
                f"`{t.name}` is defined in SQL but no static code reference was found",
                f"CREATE TABLE exists ({', '.join(t.create_files)}) but no literal "
                "sb_*/client/REST call names it. This is a HINT, not proof it's dead: "
                "it may be accessed via SQL views, a dynamic table-name variable, or "
                "the dashboard. **Verify live row count + usage before any action.**",
                [t.name]))

    # C) undocumented schema: written in code but no CREATE TABLE in repo ------
    for t in tables:
        if t.refs and not t.defined and not t.is_core:
            findings.append(DBFinding(
                "info", "Schema not in repo",
                f"`{t.name}` is used in code but has no CREATE TABLE in migrations/docs",
                f"Referenced by {len(t.writer_files)} writer / {len(t.reader_files)} "
                "reader file(s). Likely created via the Management API or an un-tracked "
                "migration — schema isn't version-controlled here.",
                [t.name]))

    # D) write-only / read-only ----------------------------------------------
    for t in tables:
        if not t.refs:
            continue
        if t.writers and not t.readers:
            findings.append(DBFinding(
                "info", "Write-only table",
                f"`{t.name}` is written but never read in code",
                "Produced but not consumed by any pipeline — an output surface (read by "
                "the dashboard/SQL) or a possible orphan.",
                [t.name]))
        elif t.readers and not t.writers:
            findings.append(DBFinding(
                "info", "Read-only table",
                f"`{t.name}` is read but never written in code",
                "Consumed but no code producer — seed/reference data, or its producer "
                "is missing.",
                [t.name]))

    sev = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (sev.get(f.severity, 9), f.category, f.title))
    return findings


def db_summary(findings) -> dict[str, int]:
    out = {"error": 0, "warning": 0, "info": 0}
    for f in findings:
        out[f.severity] = out.get(f.severity, 0) + 1
    return out
