# Modularization Plan (Phase 3)

**Status:** v2, 2026-06-17 — **8 of the in-package large files are now SPLIT.** v1 (2026-06-09) below is the original plan. **Rule:** target ≤300 lines/module; >300–400 triggers a split evaluation; larger only when justified + documented.

## ✅ EXECUTED (2026-06-17, branch `refactor/section3-company-enrichment-prompts`, not yet pushed)
Method: AST free-variable analysis → byte-identical relocation (every block diffed `== True`) → py_compile +
import-smoke + writer regression tests (6/0 + 8/0) per step. Star topology (everything imports `common`, 0 cycles).
Entrypoint paths + names unchanged → no workflow edits. External-import surfaces preserved + verified per module.

| Script | Before → After | Subpackage (modules) |
|---|---|---|
| `company_enrichment.py` | 4,377 → **937** | `enrichment/company/` — common, prompts, resolve, discovery, trials, catalysts, assessment, molecule, partnerships, deals, scoring (11) |
| `write_meridian.py` | 2,387 → **435** | `products/issue/` — common, fetch, blocks, prompts, factcheck, links, persist, deploy (9) |
| `ct_gov_sync.py` | 1,409 → **691** | `ingestion/ctgov/` — common, map, validate, fetch, write (5) |
| `research.py` | 1,539 → **913** | `ingestion/research_pipeline/` — common, pkpd, monitors (3; sources/extract/write still inline = follow-up) |
| `research_intelligence.py` | 1,379 → **413** | `scoring/research_intel/` — common, context, scoring, triggers, queue (5) |
| `company_intake.py` | 1,180 → **504** | `identity/intake/` — common, research, queue, edges (4) |
| `narrative_gen.py` | 1,123 → **405** | `products/narrative/` — common, atoms, triangulate (3) |

(`company_enrichment` was split first; the other 6 in the same overnight push. ≥1000-line health bucket: 9 → 3.)

## ⏸ REMAINING ≥1000 — flat `scripts/`, need DELIBERATE migration decisions (NOT done autonomously)
- `drug_intake.py` (1,627) — **home + naming decision required.** This v1 plan (#4 below) and REPO_LAYOUT put it at
  `identity/intake/`, but **`company_intake` already occupies `identity/intake/`** (its split landed there). drug_intake
  is also arguably `ingestion/` (it ingests drug data). Pick a non-colliding home (`identity/drug_intake/`? `ingestion/`?)
  before migrating. No workflow/importer references it (manual tool) → migration itself is low-risk once the home is chosen.
  Also fix its line-109 repo-root anchor (`dirname×2` → `×4`) on the move.
- `acquisition_scorer.py` (1,091) — manual scorer in `scripts/`; same migrate-from-scripts decision (home `scoring/`?).
- `weekend_sprint.py` (3,001) — **§2, not a clean split** — an orchestration mega-script; the call is whether it should
  *call into* the now-extracted modules rather than be split. Deliberate.

---
### v1 plan (2026-06-09, original — superseded by the EXECUTED table above)

> **Safety doctrine:** never split a live script blind. Each split (1) keeps the public entrypoint/CLI identical, (2) extracts cohesive modules behind it, (3) is verified by `py_compile` + an import smoke test + (where possible) a dry-run, (4) routes any DB writes through the `src/database` writers. Splits are reversible (git) and done one script at a time.

## Targets (ranked: value ÷ risk)

| # | Script | Lines | Extract into | Risk | Notes |
|---|---|---|---|---|---|
| 1 | `company_enrichment.py` | 4,422 | `enrichment/company/` → `prompts.py`, `ctgov.py`, `writers.py` (→ `src/database`), `core.py` | Med | 22 `sb_upsert` calls → route through writers; biggest single win |
| 2 | `write_meridian.py` | 2,391 | `products/meridian/` → `feed.py`, `prompt.py`, `render.py` | Med | reads-only on drugs; mostly assembly logic |
| 3 | `research.py` | 1,538 | `ingestion/research/` → `fetch.py`, `parse.py`, `write.py` | Med | external fetch + parse separable |
| 4 | `drug_intake.py` | 1,659 | `identity/intake/` → `resolve.py` (use `entity_matcher`), `queue.py`, `cli.py` | Med | its resolver should defer to the shared `entity_matcher` (dedup) |
| 5 | `ct_gov_sync.py` | 1,409 | `ingestion/ctgov/` → `fetch.py`, `map.py`, `write.py` | Low | clean fetch/map/write seams |
| 6 | `narrative_gen.py`, `acquisition_scorer.py`, `company_intake.py` | ~1,000–1,200 | per-layer split | Low/Med | follow the same pattern |

## Cross-cutting extractions (do first — they shrink everything)
1. **Shared Supabase client** (`src/database/client.py`) ✅ built — migrate the 30 ad-hoc `sb_upsert` helpers onto it. Each migration removes ~30–60 lines from a script.
2. **Writers** (`src/database/*_writer.py`) ✅ built — drug writes migrated. Routing company/edge/catalyst writes through writers removes governance code from scripts.
3. **Prompts/templates → `config/`** — the enrichment/meridian scripts carry large inline prompt strings; moving them to `config/*.md|.py` cuts hundreds of lines and makes them reviewable.

## Order of operations
1. Finish writer migrations (drug ✅ → company → edge → catalyst). *Each migration is also a de-bulking of the calling script.*
2. Extract the shared client into the top 5 writers' callers.
3. Then split the scripts above, #5/#6 first (lowest risk) to validate the pattern, then #1–#4.
4. `index.html` (33,983 lines) is **Phase 4**, not here — it's the highest-risk, highest-effort split and gets its own plan.

## Definition of done (per script)
- Entry CLI/behavior unchanged; `py_compile` + import smoke pass.
- No module >300 lines without a one-line justification at its top.
- All DB writes go through `src/database`.
- A smoke/regression test exists for the new module boundary.
