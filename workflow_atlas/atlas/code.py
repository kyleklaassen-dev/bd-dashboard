"""
Function-level anatomy of an entrypoint script.

`parse.py` tells you *which* file a workflow runs; this tells you what's *inside*
that file — every function, what it does (its docstring), what it calls, and which
tables it reads/writes — plus the intra-file call flow so you can see the script
execute top to bottom. Pure AST + regex, no import or execution.

Generalizes to any entrypoint, so the same "anatomy" view works for all workflows.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from functools import lru_cache

from .parse import REPO_ROOT

# table access inside a function body (reuse the db vocabulary, lightly)
_WRITE = ("sb_upsert|sb_insert|sb_insert_new|sb_post|sb_post_rows|sb_post_single|"
          "sb_patch|sb_patch_row|sb_patch_filter|sb_write|sb_update_where|sb_delete")
_READ = "sb_get|sb_get_all|sb_list|sb_all|select|select_all|count"
_W_CALL = re.compile(rf"\b(?:{_WRITE})\(\s*f?['\"]([a-z_][a-z0-9_]*)")
_R_CALL = re.compile(rf"\b(?:{_READ})\(\s*f?['\"]([a-z_][a-z0-9_]*)")
_REST = re.compile(r"/rest/v1/([a-z_][a-z0-9_]*)")
_REST_CTX = re.compile(r"(requests\.(get|post|patch|delete)|\.(get|post|patch|delete)\()")
_WRITER = re.compile(r"\b([A-Z][A-Za-z]*Writer)\s*\(")
WRITER_TABLE = {"DrugWriter": "drugs", "CompanyWriter": "companies",
                "EdgeWriter": "entity_edges", "CatalystWriter": "catalysts"}


@dataclass
class Func:
    name: str
    args: list[str]
    lineno: int
    end_lineno: int
    doc: str | None
    calls: list[str] = field(default_factory=list)      # intra-file calls, in order
    writes: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    writers_used: list[str] = field(default_factory=list)
    nested: bool = False


@dataclass
class Script:
    path: str
    doc: str | None
    loc: int
    funcs: list[Func] = field(default_factory=list)
    has_main: bool = False
    main_calls: list[str] = field(default_factory=list)
    main_writes: list[str] = field(default_factory=list)
    main_reads: list[str] = field(default_factory=list)
    main_writers: list[str] = field(default_factory=list)
    parse_error: str | None = None

    @property
    def entry_label(self) -> str:
        return "__main__ block" if self.has_main else "module top level"


def _first_line(doc: str | None) -> str | None:
    if not doc:
        return None
    for ln in doc.strip().splitlines():
        if ln.strip():
            return ln.strip()
    return None


def _segment(src: str, node: ast.AST) -> str:
    seg = ast.get_source_segment(src, node)
    return seg or ""


def _tables(seg: str) -> tuple[list[str], list[str], list[str]]:
    writes = list(dict.fromkeys(_W_CALL.findall(seg)))
    reads = list(dict.fromkeys(_R_CALL.findall(seg)))
    writers = list(dict.fromkeys(_WRITER.findall(seg)))
    # REST writes/reads to /rest/v1/<table>
    for m in _REST.finditer(seg):
        tbl = m.group(1)
        # crude: a POST/PATCH/DELETE near a /rest/v1 ref = write, else read
        window = seg[max(0, m.start() - 80): m.start()]
        if re.search(r"post|patch|delete", window, re.I):
            if tbl not in writes:
                writes.append(tbl)
        elif tbl not in reads and tbl not in writes:
            reads.append(tbl)
    # writer classes imply a write to their core table
    for w in writers:
        t = WRITER_TABLE.get(w)
        if t and t not in writes:
            writes.append(t)
    return writes, reads, writers


def _calls_in(node: ast.AST, local_names: set[str]) -> list[str]:
    out: list[str] = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            name = None
            if isinstance(f, ast.Name):
                name = f.id
            if name and name in local_names and name not in out:
                out.append(name)
    return out


@lru_cache(maxsize=256)
def analyze(path: str) -> Script:
    p = REPO_ROOT / path
    if not p.is_file():
        return Script(path=path, doc=None, loc=0, parse_error="file not found")
    src = p.read_text(encoding="utf-8", errors="replace")
    sc = Script(path=path, doc=_first_line(None), loc=src.count("\n") + 1)
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        sc.parse_error = str(e)
        return sc
    sc.doc = ast.get_docstring(tree)

    top_funcs = [n for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    local_names = {f.name for f in top_funcs}

    for fn in top_funcs:
        seg = _segment(src, fn)
        w, r, wr = _tables(seg)
        sc.funcs.append(Func(
            name=fn.name,
            args=[a.arg for a in fn.args.args],
            lineno=fn.lineno,
            end_lineno=getattr(fn, "end_lineno", fn.lineno),
            doc=_first_line(ast.get_docstring(fn)),
            calls=_calls_in(fn, local_names),
            writes=w, reads=r, writers_used=wr,
        ))

    # __main__ guard block (where many scripts actually orchestrate)
    for node in tree.body:
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "__name__"):
            sc.has_main = True
            seg = _segment(src, node)
            sc.main_writes, sc.main_reads, sc.main_writers = _tables(seg)
            sc.main_calls = _calls_in(node, local_names)
    return sc


def call_flow_dot(sc: Script) -> str:
    """Execution flow: the entry block at the top, then functions it calls, then
    the calls those make — a readable picture of how the script runs."""
    def nid(n: str) -> str:
        return "f_" + re.sub(r"\W", "_", n)

    lines = [
        "digraph anatomy {",
        '  rankdir=TB; bgcolor="transparent"; fontname="Helvetica";',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", '
        'fontsize=11, margin="0.16,0.1"];',
        '  edge [color="#5b6b7d", arrowsize=0.8];',
    ]
    entry = "__main__" if sc.has_main else "module"
    lines.append(f'  {nid(entry)} [label="{sc.entry_label}\\n(orchestrates)", '
                 f'fillcolor="#bcd4f6", color="#26487f"];')
    by_name = {f.name: f for f in sc.funcs}

    def fnode(f: Func) -> str:
        io = []
        if f.writes:
            io.append("✍ " + ",".join(f.writes))
        if f.reads:
            io.append("👁 " + ",".join(f.reads))
        sub = ("\\n" + " · ".join(io)) if io else ""
        fill = "#d2f2dc" if f.writes else "#e7eef7"
        return (f'  {nid(f.name)} [label="{f.name}(){sub}", '
                f'fillcolor="{fill}", color="#5b6b7d"];')

    seen = set()
    frontier = list(sc.main_calls)
    for f in sc.funcs:
        lines.append(fnode(f))
    for c in sc.main_calls:
        lines.append(f"  {nid(entry)} -> {nid(c)};")
    # intra-function edges
    while frontier:
        name = frontier.pop(0)
        if name in seen:
            continue
        seen.add(name)
        f = by_name.get(name)
        if not f:
            continue
        for c in f.calls:
            lines.append(f"  {nid(name)} -> {nid(c)};")
            frontier.append(c)
    # functions never reached from main (still show, dashed from entry)
    for f in sc.funcs:
        if f.name not in seen and f.name not in sc.main_calls:
            lines.append(f'  {nid(entry)} -> {nid(f.name)} [style=dotted, color="#9aa7b5"];')
    lines.append("}")
    return "\n".join(lines)
