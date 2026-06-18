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
modnames={p.stem:rel(p) for p in PYFILES}
deps=collections.defaultdict(set)
imp_re=re.compile(r'(?:from\s+meridian\.[\w.]+\s+import|from\s+(\w+)\s+import|import\s+(\w+))')
for p in PYFILES:
    for m in re.finditer(r'from\s+meridian\.([\w.]+)\s+import', read(p)):
        target=m.group(1).split(".")[-1]
        if target in modnames and target!=p.stem: deps[p.stem].add(target)
    for m in re.finditer(r'(?:from|import)\s+(\w+)', read(p)):
        tgt=m.group(1)
        if tgt in modnames and tgt!=p.stem: deps[p.stem].add(tgt)
indeg=collections.Counter()
for src,tgts in deps.items():
    for t in tgts: indeg[t]+=1
# crude cycle detection
def find_cycles():
    cyc=[]
    for a in deps:
        for b in deps[a]:
            if a in deps.get(b,()): 
                if (b,a) not in cyc: cyc.append((a,b))
    return cyc

print("="*70); print("MERIDIAN STRUCTURAL HEALTH"); print("="*70)
print(f"\nPython files analyzed (excl. archive): {len(PYFILES)}")

print("\n── 1. DB WRITE PATHS TO CORE TABLES (target: the 4 writers only) ──")
for tbl in CORE:
    sites=sorted(set(write_sites[tbl]))
    nonwriter=[s for s in sites if s not in WRITERS]
    flag = "  ⚠ ad-hoc writers!" if nonwriter else "  ✓"
    print(f"  {tbl:14s} writers/sites: {sites or '-'}{flag}")

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
for mod,c in indeg.most_common(8): print(f"     {c:3d} <- {mod}  ({modnames.get(mod,'?')})")
cyc=find_cycles()
print(f"  import cycles (2-node): {cyc or 'none ✓'}")
