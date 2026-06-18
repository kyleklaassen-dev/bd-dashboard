#!/usr/bin/env python3
"""
check_undefined_names.py — catch the missing-import bug class statically.

The §3 module splits exposed a failure mode neither `py_compile` nor import-smoke catches:
a module USES a stdlib module (e.g. `json.dumps`, `os.environ`) inside a function/branch but
never IMPORTS it. It compiles fine and imports fine (the name is only resolved when that branch
runs), then NameErrors at runtime — often in an error path or an unattended pipeline run.

This scans every module under `src/meridian/` for references to a known stdlib/common module
that isn't imported (or otherwise bound) anywhere in the file. Exit 1 on any finding (CI-gateable).
Conservative: a name bound ANYWHERE in the module (import/assign/def/param) counts as defined, so
scope-shadowing won't false-positive — it only flags genuinely-absent module imports.

Run: `python scripts/maintenance/check_undefined_names.py`
"""
import ast
import sys
import builtins
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
# stdlib / common third-party modules that, if referenced as `<name>.attr` without an import,
# are almost certainly a missing import rather than a local variable.
WATCH = {
    "json", "re", "os", "sys", "time", "datetime", "requests", "urllib", "base64", "hashlib",
    "math", "collections", "difflib", "argparse", "anthropic", "random", "itertools",
    "functools", "pathlib", "glob", "subprocess", "csv", "io", "traceback", "feedparser",
}
BUILTINS = set(dir(builtins)) | {
    "__file__", "__name__", "__doc__", "__loader__", "__spec__", "__package__",
    "__builtins__", "__future__",
}


def _bound_and_loads(tree):
    bound, loads = set(), set()

    class V(ast.NodeVisitor):
        def _args(self, a):
            for x in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs):
                bound.add(x.arg)
            if a.vararg:
                bound.add(a.vararg.arg)
            if a.kwarg:
                bound.add(a.kwarg.arg)

        def visit_FunctionDef(self, n):
            bound.add(n.name); self._args(n.args); self.generic_visit(n)
        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Lambda(self, n):
            self._args(n.args); self.generic_visit(n)

        def visit_ClassDef(self, n):
            bound.add(n.name); self.generic_visit(n)

        def visit_Import(self, n):
            for a in n.names:
                bound.add((a.asname or a.name).split(".")[0])

        def visit_ImportFrom(self, n):
            for a in n.names:
                bound.add(a.asname or a.name)

        def visit_Global(self, n):
            bound.update(n.names)

        def visit_Nonlocal(self, n):
            bound.update(n.names)

        def visit_ExceptHandler(self, n):
            if n.name:
                bound.add(n.name)
            self.generic_visit(n)

        def visit_Name(self, n):
            if isinstance(n.ctx, ast.Store):
                bound.add(n.id)
            elif isinstance(n.ctx, ast.Load):
                loads.add(n.id)

    V().visit(tree)
    return bound, loads


def main():
    findings = []
    for p in sorted((ROOT / "src" / "meridian").rglob("*.py")):
        if "__pycache__" in str(p):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError as e:
            findings.append((p, f"SYNTAX ERROR: {e}"))
            continue
        bound, loads = _bound_and_loads(tree)
        missing = sorted((loads - bound - BUILTINS) & WATCH)
        if missing:
            findings.append((p, f"uses but never imports: {missing}"))
    if findings:
        print("✗ undefined-name check FAILED — missing imports:")
        for p, msg in findings:
            print(f"   {p.relative_to(ROOT)}: {msg}")
        sys.exit(1)
    print("✓ undefined-name check: no missing imports")


if __name__ == "__main__":
    main()
