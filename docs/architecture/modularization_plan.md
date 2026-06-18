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
| `drug_intake.py` | 1,627 → **456** | migrated `scripts/`→`ingestion/`; `ingestion/drugintake/` — common, research, scoring, queue (4) |
| `acquisition_scorer.py` | 1,091 → **197** | migrated `scripts/`→`scoring/`; `scoring/acquisition/` — common, data, scoring, write (4) |

**All 9 splittable large files DONE. ≥1000-line health bucket: 9 → 1.** Flat `scripts/` 32 → 30 (the two
migrations). drug_intake → `ingestion/` (functional siblings ct_gov_sync, research; not `identity/` — that's
company-identity territory and `company_intake` already holds `identity/intake/`). acquisition_scorer → `scoring/`.
Both migrations fixed `__file__`-relative repo-root anchors for the new depth; acquisition_scorer also got a real
bug fix (dead `.github_token` → live `.github_token_workflow`, per CLAUDE.md).

## ⏸ REMAINING ≥1000 — only `weekend_sprint.py` (3,001), and it is **§2, NOT a clean §3 split**
An **active, scheduled** orchestration mega-script (`weekend_sprint.yml`, runs `python scripts/weekend_sprint.py
--block {A..F}` per job, `PYTHONPATH=src`, LLM). 73 functions in a clean phase structure (blocks A–F, ~`phase_X#_*`).

### ⚠️ Why it is NOT a byte-identical split (confirmed by inspection 2026-06-18)
There is a hard **shared-mutable-flag blocker**: `DRY_RUN` is a module global (`DRY_RUN = False`) **rebound by `main()`**
(`global DRY_RUN; DRY_RUN = args.dry_run`) and read at **41 sites** — in every phase AND in the `sb_post/sb_patch/
sb_upsert` write helpers (`if DRY_RUN: return …`). If the phases move to sub-modules, `from …common import DRY_RUN`
binds `False` at import; `main()` rebinding the orchestrator's copy does NOT propagate → **`--dry-run` silently makes
REAL DB writes.** Same hazard for `SPRINT_ID`. On an unattended weekend cron with no cheap dispatch-verify, that silent
failure mode is unacceptable to do blind. (Contrast `_RUN_TOKENS` in the company_enrichment split: a dict, shared by
reference, mutated-not-rebound — safe. `DRY_RUN` is an immutable bool that's rebound — not shareable as-is.)

### Executable plan (supervised, in-place — keeps `scripts/weekend_sprint.py` entrypoint + the workflow unchanged)
1. **PREREQUISITE — refactor the rebound globals to a shared accessor first, as its own commit.** Replace `DRY_RUN`
   (and `SPRINT_ID`) with a mutable holder shared by reference, e.g. `RUN = {"dry_run": False, "sprint_id": None}`;
   change the 41 reads to `RUN["dry_run"]` and `main()` to set `RUN["dry_run"] = args.dry_run`. Verify: `--help` loads;
   a `--dry-run --phase A1` (or a no-op phase) run shows `RUN["dry_run"]` True at a phase call site. This is the part
   that MUST be watched (its failure is silent real-writes).
2. **THEN split in place** into `scripts/wsprint/`: `common.py` (creds, `log`, `sb_*`, `table_exists`,
   `ensure_weekend_sprint_log_table`, `log_phase`, `_import_agent`, `_llm_enrich`, the `RUN` holder) +
   `phases_a.py`…`phases_f.py` (the phase fns — AST-confirmed they call only base, no cross-phase calls) +
   `weekend_sprint.py` keeps `PHASE_MAP`/`run_phase`/`run_block`/`main`. `_import_agent` already globs both
   `scripts/*.py` and `src/meridian/*/*.py` (migration-aware) — just fix its `_SCRIPTS_DIR`/`_REPO_ROOT` anchors for
   the `wsprint/` depth (→ `dirname(dirname(__file__))` / one more). Bare `from wsprint.X import …` resolves because the
   workflow runs the script from `scripts/` (script-dir on `sys.path`).
3. **Verify:** `PYTHONPATH=src python scripts/weekend_sprint.py --help` (full import chain) + byte-identical diffs +
   writer tests + a **watched `--block A --dry-run` dispatch** confirming zero writes. Only then is it safe.

> The deeper §2 win (dedupe: have phases *call into* the extracted `meridian.*` modules instead of duplicating
> `company_enrichment`/`compute_coverage`/`source_verifier`/`bd_recommender` logic) is a SEPARATE follow-up after the
> structural split lands — bigger, semantic, also supervised.

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
