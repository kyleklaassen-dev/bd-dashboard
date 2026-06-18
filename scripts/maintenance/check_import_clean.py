#!/usr/bin/env python3
"""
check_import_clean.py — guard the "every module imports test-clean" invariant (ROADMAP §B).

The §3 splits + the fail-soft credential refactor established that a module should IMPORT
without secrets present: a pure function (e.g. ctgov.map.parse_ct_study) must be importable
on a fresh checkout / in a plain unit test, with no SUPABASE/ANTHROPIC/GITHUB env set. The
failure mode this prevents:

    SUPABASE_URL = os.environ["SUPABASE_URL"]   # module scope → KeyError at import time

That crashes `import` for anyone without the env — breaking unit tests, REPL exploration, and
CI's static gate. The fix is always the house pattern: a fail-soft `_read_key(env, file, default)`
(env → repo-root file → default, never raises), and guarding any SDK client to None when key-less.

This checker is STATIC (no importing — so it needs no deps and triggers no import side effects).
It flags a subscript read of `os.environ` / `environ` that executes AT IMPORT — i.e. at module
scope or class-body scope, but NOT inside a function/method body (those are lazy and fine). Use
`os.environ.get("X")` or a fail-soft reader for anything needed at import. Exit 1 on any finding.

Run: `python scripts/maintenance/check_import_clean.py`
"""
import ast
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCAN = ROOT / "src" / "meridian"


def _eager_environ_reads(tree):
    """Return [(lineno, ...)] for os.environ[...] / environ[...] subscripts that run at import.

    We descend the module body and class bodies (both execute on import) but treat any
    Function/AsyncFunction/Lambda as a boundary we do NOT enter — code inside them is lazy.
    """
    hits = []

    def is_environ_subscript(node):
        if not isinstance(node, ast.Subscript):
            return False
        v = node.value
        # matches os.environ["X"] (Attribute) and a bare environ["X"] (Name)
        return (isinstance(v, ast.Attribute) and v.attr == "environ") or \
               (isinstance(v, ast.Name) and v.id == "environ")

    def walk_eager(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue  # function body is lazy — not executed at import
            if is_environ_subscript(child):
                hits.append(child.lineno)
            walk_eager(child)

    walk_eager(tree)
    return hits


def main():
    findings = []
    for p in sorted(SCAN.rglob("*.py")):
        if "__pycache__" in str(p):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError as e:
            findings.append((p, f"SYNTAX ERROR: {e}"))
            continue
        for ln in _eager_environ_reads(tree):
            findings.append((p, f"line {ln}: module-level os.environ[...] subscript — "
                                "crashes import without env; use a fail-soft reader or .get()"))
    if findings:
        print("✗ import-clean check FAILED — modules that crash on import without env:")
        for p, msg in findings:
            print(f"   {p.relative_to(ROOT)}: {msg}")
        sys.exit(1)
    print("✓ import-clean check: no module-level os.environ[...] subscripts")


if __name__ == "__main__":
    main()
