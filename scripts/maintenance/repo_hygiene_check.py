#!/usr/bin/env python3
"""
repo_hygiene_check.py — drift guardrail for the Meridian repo.

Run from repo root: `python3 scripts/maintenance/repo_hygiene_check.py`
Keeps the reorg from silently regressing. Exits non-zero on a HARD failure
(a workflow points at a path that doesn't exist) so it can gate CI.

Checks
  1. HARD  — every `python[3] <path>.py` in .github/workflows/ resolves to a real file.
  2. WARN  — top-level scripts/*.py that are NOT in scripts/archive/ (the flat-dump metric; should trend to ~0).
  3. WARN  — modules under src/meridian/** imported by nothing AND wired to no workflow (possible orphans).
"""
import os, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"
SRC = ROOT / "src"
hard, warn = [], []

# ---- Check 1: workflow run-paths exist ----
run_re = re.compile(r'python3?\s+([A-Za-z0-9_./-]+\.py)')
for yml in sorted(WF.glob("*.y*ml")) if WF.exists() else []:
    txt = yml.read_text(errors="ignore")
    for m in run_re.finditer(txt):
        p = m.group(1)
        if p.startswith(("http", "$")):  # skip vars/urls
            continue
        if not (ROOT / p).exists():
            hard.append(f"[workflow path missing] {yml.name}: '{p}' does not exist")

# ---- Check 2: flat scripts/ (outside archive) ----
sc = ROOT / "scripts"
flat = [p for p in sc.glob("*.py")] if sc.exists() else []
if flat:
    warn.append(f"[flat scripts] {len(flat)} top-level scripts/*.py remain (target: migrate to src/meridian/ or scripts/archive/)")

# ---- Check 3: orphan modules under src/meridian ----
def all_text():
    for base in [sc, SRC, WF]:
        if not base.exists(): continue
        for p in base.rglob("*"):
            if p.suffix in (".py", ".yml", ".yaml"):
                yield p
texts = {p: p.read_text(errors="ignore") for p in all_text()}
if SRC.exists():
    for p in (SRC / "meridian").rglob("*.py"):
        name = p.stem
        if name == "__init__":
            continue
        imported = any(re.search(rf'\b(import {name}\b|from {name} import|from meridian\.[\w.]*{name} import|{name}\.py)', t)
                       for q, t in texts.items() if q != p)
        if not imported:
            warn.append(f"[possible orphan] src/meridian/.../{name}.py — no importer and no workflow reference found")

print("=== Meridian repo hygiene ===")
print(f"HARD failures: {len(hard)}")
for h in hard: print("  ✗", h)
print(f"Warnings: {len(warn)}")
for w in warn: print("  •", w)
print("OK" if not hard else "FAIL")
sys.exit(1 if hard else 0)
