#!/usr/bin/env python3
"""
meridian_health_metrics.py — structural health metrics for Meridian.

Beats "language %": reports the things that actually predict maintainability.
Run from repo root: `python3 scripts/maintenance/meridian_health_metrics.py`

  1. DB write paths to CORE tables (drugs/companies/entity_edges/catalysts) — should be the 4 writers ONLY.
  2. Ingestion pipelines (external-data entry points).
  3. Entity-resolution implementations (should converge on ONE: entity_matcher).
  4. Files over 500 / 1000 lines.
  5. Module dependency graph (most-depended-on modules + any import cycles).
"""
import os, re, sys, pathlib, collections

ROOT = pathlib.Path(__file__).resolve().parents[2]
PYFILES = [p for base in ["src","scripts"] for p in (ROOT/base).rglob("*.py")
           if "/archive/" not in str(p)]
def rel(p): return str(p.relative_to(ROOT))
def read(p):
    try: return p.read_text(errors="ignore")
    except: return ""

# Single source of truth for core-table write detection: reuse the CI audit so the
# scoreboard and ci-quality-gate can NEVER diverge. The old narrow regex below only
# saw sb_upsert/sb_post/requests.* and missed sb_patch + raw-REST helpers — which is
# exactly why this scoreboard reported a false "drugs 0" while 20 bypasses existed.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from audit_core_writers import find_bypasses, BASELINE_FILES  # noqa: E402

# Root cause of write-path drift: ad-hoc write helpers scattered across the repo.
# Every one is a place a future bypass can hide. Target: consolidate onto
# meridian.database.client / the Writers and drive this toward 0.
_HELPER_DEF = re.compile(r'^\s*def (sb_patch|sb_post|sb_upsert|sb_insert|sb_delete|sb_write|rest|_req)\(')
write_helper_files = sorted({rel(p) for p in PYFILES
                             if "database/client.py" not in rel(p)
                             and any(_HELPER_DEF.search(l) for l in read(p).splitlines())})

# ---- 1. DB write paths to core tables ----
CORE = ["drugs","companies","entity_edges","catalysts"]
WRITERS = {"drug_writer.py","company_writer.py","edge_writer.py","catalyst_writer.py"}
# Verb-aware: only count an actual write (POST/PATCH/upsert/insert) whose target
# table URL/name appears within the same ~3 lines — NOT a GET/read. (Fixes the
# prior bug that flagged any file with a 'rest/v1/<core>' string + any post anywhere.)
WRITER_VERB = re.compile(r'requests\.(post|patch|put)\(|sb_upsert\(|sb_post\(|\.upsert\(|\.insert\(')
SUBTBL = re.compile(r'_areas|_sources|_targets|_safety|canonical_|_stage|_history|_modalities|_routes|_competition|_genetics|_disease')
write_sites=collections.defaultdict(list)
for p in PYFILES:
    lines=read(p).splitlines(); name=p.name; seen=set()
    for i,l in enumerate(lines):
        if not WRITER_VERB.search(l): continue
        if l.strip().startswith(("#", '"', "'", "*")): continue  # comment / docstring mention, not a call
        if re.search(r'\w*Writer\s*\([^)]*\)\s*\.(upsert|write)', l): continue  # writer-routed = governed, not raw
        ctx="\n".join(lines[i:i+3])
        if SUBTBL.search(ctx): continue
        for tbl in CORE:
            if re.search(rf'/rest/v1/{tbl}\b|["\']{tbl}["\']', ctx):
                if name in WRITERS:
                    tag=name
                else:
                    verb="POST" if re.search(r'\.post\(',l) else ("PATCH" if re.search(r'\.patch\(',l) else "UPSERT")
                    tag=f"{name}(raw {verb})"
                if (tbl,tag) not in seen:
                    seen.add((tbl,tag)); write_sites[tbl].append(tag)

# ---- 2. ingestion pipelines ----
ingestion_dir=[rel(p) for p in (ROOT/"src/meridian/ingestion").glob("*.py") if p.name!="__init__.py"] if (ROOT/"src/meridian/ingestion").exists() else []
integrations=[rel(p) for p in (ROOT/"scripts/integrations").glob("*.py")] if (ROOT/"scripts/integrations").exists() else []

# ---- 3. entity-resolution implementations ----
res_re=re.compile(r'(class\s+(\w*(Resolver|Registry|Matcher)\w*)|def\s+(resolve_\w+|match_\w+|_?canonical\w*|normalize_(name|company|drug)\w*))')
res_hits=collections.defaultdict(list)
for p in PYFILES:
    for m in res_re.finditer(read(p)):
        sym=m.group(2) or m.group(4)
        res_hits[p.name].append(sym)

# ---- 4. large files ----
sizes=sorted(((len(read(p).splitlines()), rel(p)) for p in PYFILES), reverse=True)
over1000=[(n,f) for n,f in sizes if n>=1000]
over500=[(n,f) for n,f in sizes if 500<=n<1000]

# ---- 5. dependency graph (imports among our modules) ----
# Keyed by FULL module id (dotted path under src/, or bare stem for scripts/), NOT basename —
# the §3 splits created many same-named submodules (common.py ×9, scoring.py ×3, …); keying by
# basename collapsed them into single nodes → bogus fan-in + phantom cycles. Full-path keying fixes both.
def _modid(p):
    r = p.relative_to(ROOT)
    if r.parts[0] == "src":
        parts = r.with_suffix("").parts[1:]                 # drop "src" → meridian.<...>
        if parts and parts[-1] == "__init__": parts = parts[:-1]   # __init__ → its package id
        return ".".join(parts)
    return p.stem                                            # scripts/: imported as a bare name
modid = {p: _modid(p) for p in PYFILES}
allids = set(modid.values())
id2rel = {modid[p]: rel(p) for p in PYFILES}
deps=collections.defaultdict(set)
for p in PYFILES:
    sid=modid[p]; txt=read(p)
    # package imports: edge to the longest real-module prefix of the dotted path
    for m in re.finditer(r'from\s+(meridian\.[\w.]+)\s+import', txt):
        parts=m.group(1).split(".")
        for k in range(len(parts),1,-1):
            cand=".".join(parts[:k])
            if cand in allids and cand!=sid: deps[sid].add(cand); break
    # bare imports of a scripts/ module (sys.path-style), e.g. `import write_meridian`.
    # Skip "meridian" — that's the package root (every `from meridian.X import` starts with it);
    # real package imports are already handled by the dotted branch above.
    for m in re.finditer(r'(?:^|\n)\s*(?:from|import)\s+(\w+)', txt):
        tgt=m.group(1)
        if tgt in allids and tgt!=sid and tgt!="meridian": deps[sid].add(tgt)
indeg=collections.Counter()
for src,tgts in deps.items():
    for t in tgts: indeg[t]+=1
# cycle detection (any length) via DFS over the full-path graph
def find_cycles():
    color={}; cyc=[]
    def dfs(u,stack):
        color[u]=1; stack.append(u)
        for v in sorted(deps.get(u,())):
            if color.get(v)==1:
                c=stack[stack.index(v):]+[v]
                if c not in cyc: cyc.append(c)
            elif color.get(v,0)==0: dfs(v,stack)
        color[u]=2; stack.pop()
    for n in sorted(deps):
        if color.get(n,0)==0: dfs(n,[])
    return cyc

print("="*70); print("MERIDIAN STRUCTURAL HEALTH"); print("="*70)
print(f"\nPython files analyzed (excl. archive): {len(PYFILES)}")

# Approval-gated maintenance/admin tools (FK-aware merges, deletes) — NOT pipeline write
# paths; CLAUDE.md already requires Kyle's approval for merges. Recognized, not flagged.
MAINTENANCE = {"dedupe_entities.py"}
def _base(s): return s.split("(")[0]
print("\n── 1. DB WRITE PATHS TO CORE TABLES (target: the writers ONLY) ──")
# drugs/companies/catalysts: authoritative detection from the CI audit (sb_* AND raw-REST).
_fb = collections.defaultdict(list)
for tbl, rl, ln, snip in find_bypasses():
    if rl not in BASELINE_FILES:
        _fb[tbl].append(f"{rl}:{ln}")
for tbl in ("drugs", "companies", "catalysts"):
    sites = sorted(set(_fb.get(tbl, [])))
    flag = f"  ⚠ {len(sites)} ad-hoc direct write(s)!" if sites else "  ✓ writer-only"
    print(f"  {tbl:14s}{flag}")
    for s in sites[:8]:
        print(f"       {s}")
# entity_edges: deterministic seeders grandfathered (DB UNIQUE constraint makes them idempotent).
ee = sorted(set(write_sites["entity_edges"]))
ee_adhoc = [s for s in ee if _base(s) not in WRITERS and _base(s) not in MAINTENANCE]
print(f"  {'entity_edges':14s}  {('⚠ ' + str(len(ee_adhoc)) + ' ad-hoc seeder(s) (grandfathered)') if ee_adhoc else '✓'}")
print(f"\n  ad-hoc write-helper defs (root cause — drive to 0): {len(write_helper_files)} files "
      f"define their own sb_*/rest/_req writer; consolidate onto meridian.database.")

print("\n── 2. INGESTION PIPELINES ──")
print(f"  src/meridian/ingestion: {len(ingestion_dir)} modules")
print(f"  scripts/integrations:   {len(integrations)} modules")

print("\n── 3. ENTITY-RESOLUTION IMPLEMENTATIONS (target: converge on entity_matcher) ──")
print(f"  files defining resolver/registry/matcher/normalize symbols: {len(res_hits)}")
for f,syms in sorted(res_hits.items()):
    print(f"    {f}: {sorted(set(syms))}")

print("\n── 4. LARGE FILES ──")
print(f"  ≥1000 lines: {len(over1000)}")
for n,f in over1000: print(f"     {n:5d}  {f}")
print(f"  500–999 lines: {len(over500)}")
for n,f in over500[:15]: print(f"     {n:5d}  {f}")

print("\n── 5. MODULE DEPENDENCY GRAPH ──")
print(f"  modules with internal deps: {len(deps)} | edges: {sum(len(v) for v in deps.values())}")
print("  most depended-on (fan-in):")
for mod,c in indeg.most_common(8): print(f"     {c:3d} <- {mod}")
cyc=find_cycles()
print(f"  import cycles: {[' → '.join(c) for c in cyc] if cyc else 'none ✓'}")

# CI gate: `--ci` makes a real structural regression (an import cycle) fail the build.
# Interactive runs (no flag) stay informational so the scoreboard is always readable.
if "--ci" in sys.argv and cyc:
    print("\n✗ CI GATE FAILED: import cycle(s) detected above.")
    sys.exit(1)
