# ✅ index.html decomposition COMPLETE + §B safety net hardened (2026-06-18)

**All §3 work merged to `main`** (PR #4) along with the completeness-scorer fix, CI quality gate,
governance 38→0, and §B fail-soft credentials. Then this session took **index.html 34,847 → 7,124
lines (−79.6%)** by externalizing **all JavaScript and all top-level CSS** to `assets/`:
- `assets/js/` (16 modules): `core.js` (shared Supabase layer + globals every consumer needs) ·
  `app.js` (loadData + all rendering + the BRIDGE template, 13.5k lines) · 14 tab/feature modules
  (reads, home_preview, changes_feed, saved_views, ontology_explorer, ontology_audit, audit, intel2,
  program_board, dkn, discovery_queue, company_database, pi_toggle, pharma_intel).
- `assets/css/` (12 files): each `<style>` → a `<link>` at the **same document position** (cascade preserved).

Method = byte-identical relocation (Python slice + reconstruction proof + `node --check`), each batch
**verified via the Claude Code preview tools** (`preview_start` on the `dashboard-static` launch config →
load the full dashboard → HTTP 200 + tab render + globals/computed-styles intact + **0 console errors**).
This RESOLVED the old "index.html can't be verified headless" blocker — the loop is repeatable. PRs #6–#12,
all merged to protected `main` (Kyle authorized; live GitHub Pages deploy).

**§B safety net** (PRs #4, #5): added `ci-quality-gate.yml`, `check_undefined_names.py`, `check_import_clean.py`
(static guard — fails CI on any module-level `os.environ[...]` subscript), the shared `src/meridian/credentials.py`
`read_key` (env→file→default, never raises; retires the per-file `__file__`-depth-anchor bug class), grew unit
tests 11→16, and made all eager-cred modules import test-clean.

**Open / next (all SUPERVISED — see ROADMAP):** §A.2 UI/logic separation (move `_resolveStage`/`_score`/`_dedup`
server-side — the deeper goal behind the index split) · `weekend_sprint.py` §2 decompose (DRY_RUN blocker) ·
entity-resolution §E convergence (17 resolvers → `entity_matcher`) · routing relocated `sb_*` writes → Writers.
Marginal index.html leftovers: small inline glue scripts + the in-JS `<style>` string in app.js (low value).

---

# ✅ §3 large-file splits — write_meridian + ct_gov_sync FULLY SPLIT (2026-06-17, overnight cont.)

Continued the §3 work autonomously (same proven method — see [[section3-split-method]]). Branch
`refactor/section3-company-enrichment-prompts` (now ~20 commits, NOT pushed — `main` protected).
**The ≥1000-line health bucket dropped 9→7** (company_enrichment, write_meridian, ct_gov_sync all removed).

- **`write_meridian.py` 2,387 → 435** (orchestrator: generate_editorial_plan / format_plan_block /
  generate_html / main) + **9 modules** under `src/meridian/products/issue/`: `common` (creds, client,
  headers, log, AREA_NAMES, fact-check gate), `fetch` (12 Supabase fetch_* + 3 render blocks), `blocks`
  (8 build_*_block + enrich), `prompts` (SYSTEM/PLAN/DRAFT), `factcheck` (4 verification gates), `links`
  (first-mention hyperlinker), `persist` (save_to_supabase + plan helpers), `deploy` (GitHub Pages + catalyst
  sync + priority bump). **External-coupling guard:** `dryrun_meridian.py` does a bare `import write_meridian
  as wm` + 32 `wm.*` accesses — verified every name still resolves and dryrun_meridian imports clean after
  each step. Also consolidated all 8 scattered `issue.*` imports into one top-of-file block.
- **`ct_gov_sync.py` 1,409 → 691** (orchestrator: step3a/b/c, sync_drug, run_sync, get_trials_*) + **5 modules**
  under `src/meridian/ingestion/ctgov/`: `common` (creds/constants/log/sb_*), `map` (PURE parse_ct_study/
  score_search_match), `validate`, `fetch`, `write`. Per the documented PHASE3_4 fetch/map/write design.
  parse_ct_study functional smoke verified (NCT→Recruiting/Phase 2 via the status/phase maps).

Every extraction: AST free-var analysis → byte-identical relocation (all diffs == True) → py_compile +
import-smoke + writer regression tests (6/0 + 8/0). Entrypoint paths unchanged → no workflow edits.

- **`research.py` 1,539 → 913** (out of the ≥1000 bucket) + 3 modules under `src/meridian/ingestion/research_pipeline/`
  (named to avoid a `research.py`↔`research/` package collision): `common` (creds/client/log), `pkpd` (the GAP-1
  PK/PD queue processor), `monitors` (Phase 9/10 competitive monitors). The sources/extract/write helpers + RSS/focus
  constants stay in research.py (follow-up). NOTE: research.py needs CI-only deps (feedparser/BeautifulSoup) so it
  can't be import-smoked locally — verified the 3 new modules import standalone + byte-identical + writer tests.

## §3 STATUS: ALL 9 splittable large files SPLIT — ≥1000-line bucket 9 → 1. Full table in
`docs/architecture/modularization_plan.md` (v2). Done across this arc: company_enrichment, write_meridian,
ct_gov_sync, research, research_intelligence, company_intake, narrative_gen, **drug_intake** (migrated `scripts/`→
`ingestion/` + `ingestion/drugintake/`), **acquisition_scorer** (migrated `scripts/`→`scoring/` + `scoring/acquisition/`;
also fixed a dead-`.github_token` import bug). Flat `scripts/` 32 → 30.

## The ONLY remaining ≥1000 file — `weekend_sprint.py` (3,001) = §2, NOT a clean §3 split
It's an **active, scheduled** orchestrator (`weekend_sprint.yml`, ~8 Sat crons, LLM). Decompose it to *call into* the
now-extracted modules rather than duplicate them — a deliberate refactor of live scheduled code → **supervised**, with
a dispatch-verify. Not the byte-identical relocation pattern.

## ✅ Health scoreboard FIXED (2026-06-18): `meridian_health_metrics.py` keyed the dep graph by file basename,
so the §3 splits' many same-named submodules (common.py ×9, scoring.py ×3, …) collapsed into single nodes →
bogus fan-in (ctgov/common showed 36 vs true 5) + ~18 PHANTOM import cycles. Re-keyed to full module path +
any-length DFS cycle detector → now reports **import cycles: none ✓** and true fan-in. (Verified 0 real cycles
via an independent full-path import graph.) Branch pushed to origin.

## Remaining = SUPERVISED or marginal (NOT done autonomously — by design):
- `weekend_sprint.py` (3,001) — §2 decompose of an active scheduled orchestrator (call into the extracted modules). Supervised + dispatch-verify.
- Route the relocated `sb_*` raw writes (`company/common.py`, `issue/common.py`, `ctgov/common.py`, etc.) → the `src/meridian/database` writers. Semantic write-path change → watched `company-enrichment --dry-run`.
- index.html Stage-2 extraction — recipe ready in `INDEX_HTML_DECOMPOSITION_PLAN.md`; needs a human browser-verify.
- (Marginal) finish `research.py` (913) — its sources/extract/write helpers + scattered prompt consts are still inline.
  Left as-is: zero large-file-metric gain (already <1000), scattered constants raise the error surface, and it's an
  active 3-workflow pipeline not fully runtime-verifiable locally (feedparser). Do it with feedparser installed if at all.
- (Bigger) Metric #3 — entity-resolution convergence: 17 files define resolver/matcher symbols; target = converge on `entity_matcher`. Architectural, supervised.

## index.html (§4 / §A.2) — PREP DONE, extraction is supervised-only (2026-06-17)
Refreshed the tail-module map (line numbers had drifted) + wrote a ready-to-run Stage-2 recipe for the safest first
target, **Reads** (34754–34844, 91 lines, fully IIFE + typeof-guarded), in `INDEX_HTML_DECOMPOSITION_PLAN.md`.
**Did NOT mutate index.html** — a local static-server + headless preview could not reliably load the 2.5 MB dashboard
(landed on chrome-error), empirically confirming the plan's "JS extraction must be browser-verified by a human"
doctrine. Next session: run the recipe live (a few minutes), glance at the Reads tab, then continue Stage 2 by size.
A static-server preview config is at `.claude/launch.json`.
## ⏸ Deferred (supervised): route the `sb_*` raw writes in `company/common.py` + `issue/common.py` +
`ctgov/common.py` through the `src/meridian/database` writers — a semantic change needing watched `--dry-run` dispatch.

---

# ✅ §3 large-file split — company_enrichment FULLY SPLIT (2026-06-17, cont.)

**`company_enrichment.py` 4,377 → 937 lines** (a thin orchestrator + CLI) by extracting **11 focused
modules** into a new `src/meridian/enrichment/company/` subpackage. The 4am nightly Intelligence
Pipeline core is now legible. Branch: `refactor/section3-company-enrichment-prompts` (8 commits,
9117540 → 5457650 — NOT pushed; `main` is protected, fast-forward when ready).

Modules (none over 940 lines): `common.py` (462 — shared base: creds, LLM client, `_RUN_TOKENS`,
`sb_*` I/O, `log`, URL/confidence validation, `AREA_LABELS_MAP`) · `prompts.py` (747 — Step-5 prompt
construction) · `resolve.py` (99) · `discovery.py` (495 — Step 1) · `trials.py` (348 — CT.gov sync +
context fetch) · `catalysts.py` (150 — Step 4) · `assessment.py` (779 — Step 5 web intel + write_step5) ·
`molecule.py` (174) · `partnerships.py` (125) · `deals.py` (152 — Step 6) · `scoring.py` (185).

**How it was kept safe (every commit):**
- **Byte-identical relocations** — each moved block was diffed against the original (all `True`). Method:
  AST free-variable analysis (`/tmp/freevars.py`) to compute the exact import set + detect any sibling/
  forward-ref calls before moving, so I never broke a call edge.
- **Clean star topology** — everything imports `common`; `common` imports no feature module → 0 cycles.
- **One real bug fixed in flight:** `_catalyst_upsert`'s repo-root anchor `parents[3]→[4]` (the new
  `company/` dir is one level deeper than the old home). Verified it now resolves to the true repo root.
- **`_RUN_TOKENS` shared-object identity preserved** (token accounting spans modules — verified `is` same dict).
- **Verified per step:** py_compile + import-smoke (every relocated name resolves to its module) + writer
  regression tests **6/0 + 8/0**. Final: full CLI `--help` exercises the whole import chain through all 11
  modules; repo hygiene 0 hard-fails; health scoreboard — company_enrichment dropped out of the ≥1000-line bucket.
- Entrypoint path unchanged → `company-enrichment.yml` / `school-week-sprint.yml` need no edits. No external
  importers of any moved symbol.

## ⏸ Deferred (supervised — needs a watched dispatch, NOT an unattended run):
- **Route `common.py`'s `sb_*` writes through the `src/meridian/database` writers/client.** This is a
  *semantic* write-path change (the design's "remove last ad-hoc writes" goal) — verify with a watched
  `company-enrichment.yml --dry-run` before the real nightly run. Left as a verbatim relocation for now.

## NEXT §3 large-file targets (same method — byte-identical, AST-guided, writer-test-gated):
`write_meridian.py` (2,387) · `drug_intake.py` (1,627) · `research.py` (1,539) · `ct_gov_sync.py` (1,409).
`write_meridian` is the next-biggest and feeds the unattended Issue generator (`meridian-preview.yml` has a
`--dry-run`) → good verifiability. Then §A.2 (index.html UI/logic separation — highest risk, do last).

---

# ✅ §A.4 AUDIT + §A.5 EDGE-CASE TESTS + §3 dedup (2026-06-17, cont.)

- **§A.4 audit — DONE & verified.** v163 migration (APPLIED via Management API): all 4 core tables now audited on
  INSERT+UPDATE in `field_change_audit` (v63 was UPDATE-only + missed entity_edges/catalysts). New fn is
  error-swallowing + AFTER triggers (can NEVER block a write); shared v63 fn untouched. `client.set_audit_context()` +
  the 4 Writers send `X-Meridian-Actor`/`X-Meridian-Reason` headers → audit captures WHO (the writer) + WHY. Verified
  end-to-end: CatalystWriter write → changed_by="CatalystWriter". (commit 5a299b1)
- **§A.5 edge-case tests — DONE.** `tests/database/test_edge_cases.py` (9/9): tulisokibart=MK-7240 canonical identity
  (originator=Prometheus not Merck), VTX002/Ventyx, Roche/Telavant acquisition, LBL-053 bispecific. (b5e4ffd)
- **§3 (large files) — STARTED.** Extracted the triplicated `infer_catalog_category` → `meridian.enrichment.catalog_category`
  (-123 lines across company_enrichment/drug_intake/approve_discovery). (aeeda58)

## REMAINING = the two big dedicated-session refactors (designed, NOT yet executed):
- **§3 full large-file splits** — company_enrichment (4,377 now), write_meridian (2,391), drug_intake (1,627), per
  `docs/architecture/PHASE3_4_EXECUTION_DESIGN.md`. Each is a careful module extraction of a LIVE pipeline (the 4am core);
  do supervised + dispatch-verify. NOT a tail-of-session task.
- **§A.2 UI/logic separation** (`index.html`, 34k lines: `_resolveStage`/`_score`/`_dedup`/`canonical`×61) — surgery on the
  LIVE dashboard; pair with §4 index.html decomposition; page-load-verify each extraction. Highest risk → dedicated session.

Everything else (full migration, §A.1 write-path, §A.4 audit, §A.5 tests) is DONE, verified, and on main.

---

# ✅ §A.1 ONE WRITE PATH — COMPLETE at code layer (2026-06-17, cont.)

**Gating question now essentially YES.** All 4 core tables route pipeline writes through their Writer
(scoreboard `drugs/companies/entity_edges/catalysts` all ✓). Routed this session:
- `execute_intel_actions` (drugs+companies+catalysts creates) → Drug/Company/CatalystWriter (commit 1aa1536).
- All 6 `entity_edges` seeders (seed_api_edges, connect_ctgov_raw, unify_graph, seed_target_edges, seed_targets,
  company_intake ACTIVE_IN) → EdgeWriter(verify_endpoints=False) (eaeba31). Predicates/node-types pre-checked.
- `research` catalyst create + `write_meridian` catalyst-resolve → CatalystWriter; `verify_sources`(data_confidence)
  + `stock_prices`(stock fields) → Drug/Company `update_fields` (added CompanyWriter.update_fields) (46ec92e).
- `dedupe_entities` = the one remaining non-writer — an approval-gated FK-aware MERGE tool (not a pipeline path;
  merges need Kyle's approval per CLAUDE.md). Recognized as the maintenance exception in the scoreboard (3541f36).
- **Fixed the health metric**: it was counting READS as writes (matched `/rest/v1/<table>` strings, any verb).
  Now verb-aware + skips comments/docstrings + writer-routed + recognizes maintenance tools (2c19162, 8b3c916).

**Writer tests green throughout (6/0 + 8/0).** DB-layer enforcement (v157–162) still backs this.

## NEXT (correctness spine, ROADMAP §A): A.4 audit (cheap now — all writes funnel through 4 writers → log there) ·
A.2 UI/logic split (with index.html §4) · A.5 codify edge-case tests (VTX002, MK-7240, Roche/Telavant, HLX36/LBL-053).
Also open: §3 large-file splits (company_enrichment 4,437 etc.); §A.1 optional DB-layer hardening of the write boundary.

---

# ✅ PACKAGE MIGRATION STRUCTURALLY COMPLETE + architecture spine defined (2026-06-17, cont.)

**`src/` is now ONE unified `meridian` package** (database, enrichment, graph, identity, ingestion, ops, products,
scoring, validation — 91 modules; flat scripts 47→32; dep graph 0 cycles).

- **Narrative cluster migrated** (11 files, 4 domains): seed_company/partnership/patient_edges→graph/ (ab3a70a);
  verify_publication_values+reconcile_drug_integrity→validation/ (8c0827a); collect_evidence→ingestion/ (001c310);
  generate_area_narratives/generate_patient_briefs/patient_narrative/strategic_brief/landscape_narrative→products/ (baf49c7).
  Fixed generate_area_narratives's subprocess orchestration (cwd→repo-root parents[3] + repointed moved targets).
- **Writers moved** src/database/ → **src/meridian/database/** (f97e4ef): client + 4 writers. Fixed internal path
  anchors (parents[2]→[3], src/database→src/meridian/database for client+entity_matcher sys.path); updated ALL importers
  (8 `from database import client`, bare writer imports, tests, seed_competes_with). **Live writer tests green (6/0 + 8/0).**
- **§A PRODUCT ARCHITECTURE added to ROADMAP** (fe32853): the correctness spine. Gating question — _can ONE approved
  path create/modify a drug ingestion→database→dashboard?_ **Today NO** (drug_intake/company_intake/write_meridian/
  verify_sources raw-REST write `drugs`). **Freeze dashboard features until §A.1 clean.**

## NEXT: §A.1 — one write path (the chosen direction). Writers now in final home → route consumers through them.
Start: `drug_intake.py` (primary intake, 3 raw `POST /rest/v1/drugs`) → `DrugWriter`; then company_intake/write_meridian/
verify_sources. Gate each with tests/database/. This also completes stabilization Stage 4.
Remaining migration tail: LLM stragglers (few); most of the 32 flat scripts are manual tools + weekend_sprint (§2 decompose).

---

# ✅ enrichment-core CONSUMERS migrated + root cleanup (2026-06-17)

**Supervised session on the real local clone — native git works here** (git pull/commit/push all fine;
the old "git broken → deploy via API" note was Cowork-sandbox-only and is now corrected in CLAUDE.md + START_HERE).
Local↔GitHub kept in sync via native `git push` after every commit.

## Sub-batch B DONE — enrichment-core web fully migrated (flat scripts 47→43)
- `company_intake` (1,185) → `identity/` (commit 37ea2ac). Repointed approve_discovery + pipeline_monitor.
- `ct_gov_sync` (1,409) → `ingestion/` (d730b33). Repointed company-enrichment + school-week-sprint. Pure relocation (env creds, package imports).
- `research` (1,538) → `ingestion/` (e5e3419). Leaf; meridian-research dispatch ran past startup ✓. (Note: pre-existing dead Phase-6 ctgov_poller/edgar_fetcher imports — those modules don't exist in the repo — still degrade gracefully; tracked, not fixed here.)
- `company_enrichment` (4,437, the 4am core) → `enrichment/` (8b20097). Fixed `__file__`-depth anchors: `_catalyst_upsert` parents[1]→[3] (catalyst_writer resolution) + `_HINTS_PATH` repo-root (3 dirnames up); repointed 11 workflow invocations + `weekend_sprint` B2 subprocess path (+PYTHONPATH=src). Static-verified (py_compile, find_spec, path math, catalyst_writer reachable). **company-enrichment dry-run dispatch (area=tl1a, company=spyre) queued at hand-off — confirm it went green.**
- Leaf libs (identity_resolution, model_comparison, company_identity_resolver, source_verifier) were done the prior session → enrichment-core web is now 100% migrated.

## Other fixes this session
- **`.gitignore` bug:** a bare `enrichment/` pattern was silently ignoring `src/meridian/enrichment/` (the source package!). Removed it (commit 50a4a5a); verified all 9 `src/meridian/<domain>` dirs are tracked; `__pycache__` still covered by lines 24-25.
- **Writer test fix** (bc1d411): `test_writers.py` CatalystWriter anchor assertion was stale (checked old `drug_id or company_id` substring); writer correctly rejects unanchored catalysts with the v160 message. Now 8/0; test_drug_writer 6/0.
- **Root cleanup (ROADMAP §5):** 4 secondary docs (ARCHITECTURE, BD_ANALYST_PLAYBOOK, CODE_REVIEW, SESSION_PROTOCOL) → `docs/`; 13 static dashboards → `web/` (index.html refs repointed, 4 back-links → ../index.html, local HTTP load verified 200s). Root files 38→22; root HTML 15→2 (index.html + generated meridian_today.html). **meridian_today.html left at root** — it's auto-published by write_meridian.py; moving it would mean touching the 4am-core generator. **NOTE: sub-page URLs changed** (e.g. /meridian_atlas.html → /web/meridian_atlas.html); add redirects if any external bookmark matters.

## Next
- Confirm the queued company-enrichment dry-run went green (run 27725621871).
- Migration remaining (ROADMAP §1): **narrative cluster** (narrative_gen consumers: generate_area_narratives, generate_patient_briefs, landscape_narrative, patient_narrative, strategic_brief, collect_evidence, seed_*_edges, reconcile_drug_integrity, verify_publication_values), LLM stragglers, then writers → `src/meridian/database/`.
- Then §2 (decompose weekend_sprint) + §3 (large-file splits — company_enrichment 4,437 is the top target).
- **Health scoreboard (Kyle's 5 metrics):** large-file count still 10 (moves don't split); write-paths unchanged (still many ad-hoc raw-REST writers on all 4 core tables — the next big lever per [[repo-health-north-star]]); dep graph 29 modules/41 edges, 0 cycles.

---

# ✅ enrichment-core LEAF LIBS migrated via package imports (2026-06-16) — commit f01fcd12

identity_resolution + model_comparison + company_identity_resolver → identity/; source_verifier → validation/.
All 6 importers (company_enrichment, ct_gov_sync, drug_enrichment, company_intake, drug_intake, research) converted to
`from meridian.<domain>.<mod> import ...`. weekend_sprint._import_agent patched to resolve src/meridian/** (its dynloads
now survive migration). source-verifier.yml re-pointed. Verified: sandbox package-import of all 4 libs + every importer
symbol; live source-verifier + company-enrichment dispatches = 0 import errors (package imports resolve). Flat scripts 47.

## enrichment-core SUB-BATCH B (next — now straightforward, all consumers already use package imports):
Move the consumers to domains (file move + own path-hack fix + workflow path repoint):
  - company_enrichment(4435) → enrichment/  (also a large-file-split target, §3)
  - ct_gov_sync(1409) → ingestion/  (split target)
  - company_intake(1185) → identity/  (split target)
  - research(1538) → ingestion/  — ALSO convert its scripts/integrations imports (ctgov_poller, edgar_fetcher); package
    scripts/integrations/ OR keep an absolute path. (research also dynloads edgar_fetcher/ctgov_poller in try-blocks.)
Then: move the 11 narrative importers to their domains (trivial — narrative_gen import already package-style).
Run tests/database/ writer tests after (writers import entity_matcher; unaffected by this batch but good gate).

---

# ✅ PACKAGE-IMPORT FOUNDATION LANDED + narrative_gen decoupled (2026-06-16)

**`meridian` is now an importable package.** Added `pyproject.toml` + `PYTHONPATH=$GITHUB_WORKSPACE/src` to all 51
workflows (481913b4, each YAML re-parsed/validated; pipeline-health dispatch GREEN = additive change is safe).
**First package-import migration:** narrative_gen → products/ + all 11 importers converted to
`from meridian.products.narrative_gen import ...` (e92edaf3). **PROVEN end-to-end: evidence-collectors dispatch GREEN**
(collect_evidence resolves narrative_gen via the package path + workflow PYTHONPATH). narrative-generation/patient-briefs
import-clean (0 import errors) + running.

## Remaining is now straightforward (use package imports — pattern proven):
1. **Move the 11 narrative importers to their domains** (products/ingestion/graph/validation) — trivial now: their
   narrative_gen import is already location-independent; just move file + fix own path-hacks + repoint workflow path.
2. **enrichment-core web** (company_enrichment(4435)+ct_gov_sync+company_intake+identity_resolution+model_comparison+
   company_identity_resolver+source_verifier+research): convert their cross-imports to `from meridian.<domain>.<mod>`,
   move to domains. PYTHONPATH already everywhere. Run tests/database/ writer tests after (writers also import these via sys.path).
3. Convert the writers' (src/database/) entity_matcher sys.path-hack to a package import too (consistency) — optional.

CONVENTION (now in START_HERE/pyproject): new cross-package imports use `from meridian.<domain>.<module> import ...`;
workflows already export PYTHONPATH=src. Legacy own-dir sibling imports still work (additive).

---

# ✅ CONT. — write_meridian + research_intelligence migrated; 5 one-offs archived (flat 57→52)

This push: **write_meridian cluster** (write_meridian + meridian_integrations_feed + dryrun_meridian → products/; meridian-preview dry-run GREEN — the Issue generator now lives in the package) · **research_intelligence** → scoring/ (completeness-scoring GREEN) · archived 5 spent one-offs → scripts/archive/. ~56 scripts migrated total, 0 failures.

**Next (ROADMAP §1 — read it):** the final two coupled webs (**narrative** 12 files/4 domains; **enrichment-core** 8 files) are densely cross-coupled. Recommended: introduce **package imports** first (PYTHONPATH=$GITHUB_WORKSPACE/src in workflows or pyproject + pip install -e .), convert cross-package imports to `from meridian.<domain>.<mod>`, THEN move both webs cleanly. research.py is in the enrichment-core web (sibling-imports company_identity_resolver + source_verifier).

---

# ✅ SESSION 2026-06-16 (cont.) — 52 scripts migrated, org scaffolding built, freeze LIFTED

**Kyle lifted the spend freeze** → LLM workflows can now be dispatch-verified. **`ROADMAP.md` is now the single
source of all future work — read it for the detailed remaining plan.** `START_HERE.md` is the new session reading guide.

This session added: products/3 + enrichment/2 + ops/3 self-contained · disposition (deleted 4 redundant + 1 spent
backfill, wired payer_pricing) · stragglers refresh_company_verified/sync_catalyst_calendar/seed_data_sources ·
fact-graph/identity cluster (entity_matcher↔writer coupling RESOLVED + sandbox-verified) · docstring sweep (39 files) ·
LLM leaves execute_intel_actions/process_queue_item/review_submitted_intel (dispatch-verified green).
**Bugs/breakages fixed:** execute_intel_actions None-slice (failing since 06-16 → green); removed dead school-week-sprint v56 line + deleted dead backfill-ailux-angle-watch.yml (caught by the new guardrail).

**NEW guardrail:** `scripts/maintenance/repo_hygiene_check.py` (run it every session end; HARD-fails on workflow→missing-path).

## REMAINING = the dense LLM-core web (ROADMAP §1) — do cluster-by-cluster, dispatch-verify each:
write_meridian(+integrations_feed+dryrun; research DYNLOADS write_meridian) · research(+research_intelligence) ·
company_enrichment(4435, referenced by 12 scripts)+ct_gov_sync+company_intake+identity_resolution+model_comparison+
company_identity_resolver+source_verifier · narrative_gen(+collect_evidence+generate_area/patient) · writers→src/meridian/database.
⚠️ These are densely cross-referenced — run the FULL-repo importer sweep + classify each ref (dynload/subprocess/docstring) before moving.
Regression gate: run tests/database/test_drug_writer.py + test_writers.py (live read-only) after any writer/identity move.

---

# ✅ BIG MIGRATION SESSION (2026-06-16) — 49 scripts in packages, 5 deleted, 1 wired, 0 failures

## Commits this session
products 619f33e6 · enrichment 4a68cfed · ops d83d9c7e · cleanup/wire 2438013d · stragglers 6bb6dd42 · fact-graph/identity f6675cdb · docstring-sync ba367813.

## Packages now populated (49 scripts)
graph/9 · scoring/7 · ingestion/12 (+payer_pricing_agent, sync_catalyst_calendar, seed_data_sources) · validation/9 (+refresh_company_verified) · products/3 · enrichment/2 · ops/3 · identity/4.

## ✅ DISPOSITION (Kyle's 'wire or delete' call — executed)
DELETED (redundant; capability covered by active pipelines; zero importers, verified full-repo sweep):
  quick_profiles_enrich + patient_population_agent (company_enrichment already writes company_profiles + patient_population),
  run_pkpd_claude (drug_pk_parameters written by active collect_efficacy_apis + process_queue_item),
  deep_enrich_intel (superseded by backend PDF ingestion), backfill_bd_angle + its workflow (spent one-time backfill).
WIRED IN: payer_pricing_agent -> src/meridian/ingestion/ + non-fatal step in meridian-free-ingest.yml
  (free CMS/Medicaid data; sole populator of the live payer_pricing feature read by 3 dashboards). free-ingest dispatched.

## 🔑 KEY FIX: entity_matcher coupling (the shared resolver) — RESOLVED & VERIFIED
entity_matcher is imported by the GOVERNED WRITERS (drug_writer + company_writer) + tests + maintenance/link_extras.
Moved to src/meridian/identity/; redirected all importer sys.path lines. VERIFIED FREE: in-sandbox both writers
import with entity_matcher resolved from the new path; 4 cluster scripts import-exercised. ⚠️ tests/database/ are NOT
on any workflow — RUN test_drug_writer.py + test_writers.py at session start (live read-only) as the regression gate.

## ⏸️ REMAINING = the entangled LLM 4am-core (~20 scripts) — NEEDS A VERIFICATION DECISION
Every remaining mover is on an LLM (Claude) workflow → under the spend freeze I cannot cheaply dispatch-verify, and
import-exercise is thin assurance for the platform's unattended nightly Issue. Per the standing safeguard I PAUSED here.
Clusters (each = one atomic move; full-repo importer sweep first — depmap misses src/database + maintenance + dynloads):
  - write_meridian + meridian_integrations_feed + dryrun_meridian  (Issue generator; research.py DYNLOADS write_meridian)
  - research + research_intelligence
  - company_enrichment(4435) + ct_gov_sync + company_intake + identity_resolution + model_comparison + company_identity_resolver + source_verifier
  - narrative_gen + collect_evidence + generate_area_narratives + generate_patient_briefs
  - LLM stragglers: execute_intel_actions, process_queue_item, review_submitted_intel
  - apply_sql_migration -> move WITH the writers into a src/meridian/database consolidation (writers still at src/database/)
DISPOSITION FLAGS (could NOT safely auto-decide — both coupled/active): 
  - weekend_sprint(2999, active 8 Sat crons, LLM) + drug_enrichment(its sole dynload dep): archive or delete? (active scheduled)
  - flywheel_phase2 + apply_prompt_improvements: apply_prompt_improvements is referenced by ACTIVE company_enrichment -> move/decide with that cluster.
DECISION FOR KYLE: for the LLM-core moves — (a) proceed import-exercise-only (flagged, no dispatch), (b) authorize one-off
verification dispatches (small Claude cost) per cluster, or (c) do them supervised. Recommend (b): one preview + one research
+ run writer tests = real verification at minimal cost.

## Tiny cosmetic backlog: none outstanding (docstring usage paths synced across all 39 moved files in ba367813).

---

# ⚠️ FINDING (2026-06-16, live 221-file sweep) — entity_matcher is WRITER-COUPLED

`entity_matcher` is imported by **`src/database/drug_writer.py` + `src/database/company_writer.py`** (the governed single-writers) and `scripts/maintenance/link_extras.py` — NOT just build_fact_graph/link_entities as the active/util depmap implied. **Moving entity_matcher edits the writer layer that every core write routes through → supervised only.** Lesson: depmap.json covers active/util scripts; it does NOT capture src/database/ or scripts/maintenance/ importers — for the coupled clusters, ALWAYS run the live full-repo importer sweep first (the snippet that scanned 221 files: all scripts/ subdirs + src/ + workflows). Same caution applies before moving identity_resolution/model_comparison/source_verifier (likely writer- or research-coupled too).

---

# ✅ PACKAGE MIGRATION — ops/ DONE (2026-06-16) — commit d83d9c7e — 3 monitors, dispatch-verified GREEN

pipeline_health, pipeline_monitor, signal_monitor → `src/meridian/ops/` (no sibling imports, no LLM). Path anchors → repo root; import-exercised + all 3 workflow_dispatch runs SUCCESS.

## RUNNING TALLY: 41 scripts migrated, 7 groups, 0 engine failures.
graph/9 · scoring/7 · ingestion/9 · validation/8 · products/3 · enrichment/2 · ops/3.

## ⏸️ STOPPED HERE (autonomous) — REMAINDER IS THE COUPLED CORE → needs a SUPERVISED session
Per Kyle's safeguard (pause before any 4am-core mover whose only real verification is the unattended run). The remaining ~30 scripts are 4 coupled clusters + a few one-offs. Execution plan (each cluster = ONE atomic commit: move all members + update EVERY importer + update all workflows from main + import-exercise):

1. **fact-graph cluster** (lowest risk, do first): entity_matcher → build_fact_graph (imports entity_matcher) → link_entities (imports both; wf chunk_extract.yml) + ontology_map_drugs (wf chunk_extract.yml). Verify: import-exercise + chunk_extract dispatch.
2. **write_meridian cluster**: meridian_integrations_feed + write_meridian (imports it) + dryrun_meridian (imports both; wf meridian-preview.yml). **Verify via meridian-preview = the built-in --dry-run.** Best-verifiable of the hard ones.
3. **narrative cluster**: narrative_gen + collect_evidence + generate_area_narratives + generate_patient_briefs (all import narrative_gen). Workflows are cost-gated LLM → verify by import-exercise only (flag).
4. **🔴 4am-core cluster (MOST CAUTION, Kyle present)**: identity_resolution + model_comparison + company_identity_resolver + source_verifier (leaves) → company_enrichment, ct_gov_sync, company_intake, research, research_intelligence (consumers). Feeds the unattended 4am run; ct_gov_sync has --dry-run; company_enrichment/research verified by import-exercise + a watched live run.

## DECISIONS NEEDED FROM KYLE
- **6 dead enrichment scripts** (no workflow, no importer): drug_enrichment, deep_enrich_intel, quick_profiles_enrich, run_pkpd_claude, patient_population_agent, payer_pricing_agent → archive to scripts/archive/ or keep? (deletes need approval)
- **4 archive-candidates still wired** (one-off naming per REPO_LAYOUT §4/§5): backfill_bd_angle, flywheel_phase2, seed_data_sources, weekend_sprint(2999 lines) → archive vs keep-in-package?
- **Self-contained stragglers** (safe to move once domains confirmed): apply_sql_migration(→database util), execute_intel_actions, process_queue_item, refresh_company_verified, review_submitted_intel, sync_catalyst_calendar.

## METHOD (proven on 41 scripts) — reuse exactly
snapshot at outputs/repo_snapshot; depmap.json + script_to_workflows.json; path-depth fix (scripts/ depth-1 → src/meridian/X/ depth-3 = +2 dirname / parents[1]→parents[3]); import-exercise w/ dummy env; atomic Git Data API commit (move + delete old sha:null + update ALL workflows READ FROM main + __init__.py); stale-ref sweep; dispatch light wf.

---

# ✅ PACKAGE MIGRATION — enrichment/ (self-contained) DONE (2026-06-16) — commit 4a68cfed

2 self-contained active enrichment scripts → `src/meridian/enrichment/`: molecule_enrichment (parents[1]→parents[3]) and drug_intelligence_researcher (BASE_DIR .parent.parent → parents[3]). Both import-exercised OK (env-confirmed). school-week-sprint.yml: only the 2 moved-script lines re-pointed; company_enrichment + ct_gov_sync left as scripts/ (deferred). Stale-ref sweep: NONE.
**Verification = import-exercise only.** school-week-sprint is a heavy LLM + cost-gated workflow (API-spend paused), so no cheap green dispatch — flagged, not blocked (both modules load clean).

**DEFERRED to the final utilities+identity group:**
- company_enrichment (ACTIVE, 4,435 lines, 2 workflows) — imports identity_resolution + model_comparison (both still in scripts/). Feeds the 4am core → move WITH its deps, --dry-run + synthetic-exercise before push.

**FLAGGED for disposition (not moved, not deleted — need Kyle's call):** 6 enrichment scripts wired to NO workflow and imported by nothing — drug_enrichment, deep_enrich_intel, quick_profiles_enrich, run_pkpd_claude, patient_population_agent, payer_pricing_agent. Likely abandoned → archive, but deletes need approval. Left in scripts/ for now (won't pollute the clean package with dead code).

**Running tally: graph/9 + scoring/7 + ingestion/9 + validation/8 + products/3 + enrichment/2 = 38 scripts migrated. 0 engine failures throughout.**
**NEXT = the final utilities+identity group** (the hard one): entity_matcher, identity_resolution, model_comparison, company_identity_resolver, narrative_gen, meridian_integrations_feed, source_verifier, build_fact_graph, company_intake + all deferred coupled products (write_meridian, generate_area_narratives, generate_patient_briefs, dryrun_meridian) + company_enrichment + ct_gov_sync. These feed the 4am core → synthetic-exercise + --dry-run, PAUSE/FLAG before pushing any 4am-core mover.

---

# ✅ PACKAGE MIGRATION — products/ (self-contained) DONE (2026-06-16)

3 self-contained active products scripts → `src/meridian/products/`: generate_landscape_briefing (its `docs/` OUTPUT path fixed → parents[3]/docs), bd_recommender (`_REPO_ROOT` key-search path fixed), morning_summary (the artifact-file `repo_root` fixed). Import-verified; 3 workflows updated (from main).
**Dispatch-verified green:** morning-summary (confirms the artifact-file path fix), bd-recommender. landscape-briefing (Claude, slow) running + import-exercised. Engine 0 failures.

**DEFERRED to the utilities group (all import narrative_gen / meridian_integrations_feed):**
- active: write_meridian, generate_area_narratives, generate_patient_briefs, dryrun_meridian
- manual: patient_narrative, landscape_narrative, strategic_brief
These move together with the utilities `narrative_gen` (imported by 11) + `meridian_integrations_feed` (imported by 2), updating every importer. Utilities also feed the 4am core (write_meridian) → synthetic exercise + --dry-run before push.

**Running tally: graph/9 + scoring/7 + ingestion/9 + validation/8 + products/3 = 36 scripts migrated.**
Next per §6: enrichment group, then the big utilities+identity+coupled group (last).

---

# ✅ PACKAGE MIGRATION — validation/ group DONE (2026-06-16)

8 active validation scripts → `src/meridian/validation/`: validate_ground_truth, validation_research, conflict_detector, content_verifier, verify_competitor_edges, company_validator, trial_id_audit, identity_health_check. Self-contained; paths fixed (incl. identity_health_check's repo-root key fallback); import-verified. Updated all 8 workflows (from main).
**Dispatch-verified green:** run-validation-tests, content-verifier, verify-edges, refresh-company-verified, validation-research (validation_research+conflict_detector). trial-audit (trial_id_audit) running/import-OK; identity_health_check import-exercised (its company-enrichment step is continue-on-error → can't dispatch-confirm). Engine 0 failures.
Deferred to utilities group: **source_verifier** (utility, imported by `research`).

**Running tally: graph/ (9) + scoring/ (7) + ingestion/ (9) + validation/ (8) = 33 scripts migrated.**
Next per §6: products (write_meridian, narrative gen, briefs, summary), then enrichment, then utilities+identity (last).

---

# ✅ PACKAGE MIGRATION — ingestion/ group DONE (2026-06-16)

9 self-contained ingestion scripts → `src/meridian/ingestion/`: abstract_fetcher, api_harvester, fetch_homepage_news, collect_efficacy_apis, collect_patient_evidence, refresh_orange_purple_book, stock_prices, chunk_extract, enrich_pub_stubs. Paths fixed; import-verified; 9 workflows updated (from main).
**Dispatch-verified green:** abstract-fetcher, orange-purple-book, efficacy-verification, stock-prices, fetch-homepage-news, evidence-collectors. api_harvester+enrich_pub_stubs (api-harvest-daily, long harvest) and chunk_extract (heavy LLM) import-exercised. Engine 0 failures.
Deferred to the utilities group: **ct_gov_sync** (imports identity_resolution), **collect_evidence** (imports narrative_gen).

**Running tally: graph/ (9) + scoring/ (7) + ingestion/ (9) = 25 scripts migrated into src/meridian/.**
Next per §6: validation, then products, enrichment, then utilities+identity (coupled, last).

---

# ✅ PACKAGE MIGRATION — scoring/ group DONE (2026-06-16)

7 active scoring scripts → `src/meridian/scoring/`: compute_attribute_completeness, compute_coverage, compute_indication_priority, compute_landscape_scores, compute_patient_whitespace, score_foresight, write_ranking_snapshots. All self-contained (no sibling imports); `__file__`-relative paths fixed for the new depth; import-verified. Updated all 8 referencing workflows (read from main).
**Dispatch-verified green:** compute-landscape-scores, score-foresight, ranking-snapshots, meridian-free-ingest (compute_indication_priority+patient_whitespace), atlas-refresh (compute_attribute_completeness). **compute_coverage** verified by import-exercise only (its sole workflow, school-week-sprint, is a heavy 8-script LLM run — not worth a full dispatch; the script is self-contained + path-verified). Engine 0 failures.
Deferred: `acquisition_scorer` (manual; reads a runtime data file from repo-root — needs its own check) and the other manual scorers (compute_strategic_value/trust_score/landscape_coverage, portfolio_conflict_scorer, etc.).

Groups migrated so far: **graph/ (9) + scoring/ (7)**. Next per §6: ingestion, then validation, products, enrichment, and the utilities+identity coupled group last.

---

# ✅ PACKAGE MIGRATION — graph/ group DONE (2026-06-16, supervised-equivalent)

Executed the first package migration from REPO_LAYOUT §6. **9 graph scripts moved** to `src/meridian/graph/`, each verified, engine green (0 failures):
- `materialize_structural_edges`, `materialize_deal_edges` (stdlib-only) — verified via workflow dispatch (structural-edges, deal-edges --dry-run both green).
- `build_institution_intel`, `project_patient_author_graph`, `derive_ownership_rights` (read `.supabase_service_key` via `__file__`-relative repo-root) — path depth fixed +2 levels; import-exercised; meridian-graph-rebuild + meridian-derived-rebuild dispatched green.
- `unify_graph`, `seed_target_edges` (env-key + repo-root fallback) and `seed_api_edges`, `graph_health_guard` (`sys.path`→`src` for `from database import client`) — path hacks fixed for the new depth; import-exercised. (chunk_extract is heavy LLM → verified by import-exercise, not a full dispatch; api-harvest dispatched.)

**Two process lessons (both caught by my own post-move stale-ref check):**
1. A script can be wired into MULTIPLE workflows — `materialize_structural_edges` was in BOTH structural-edges and chunk_extract. Use the script→ALL-workflows reverse index (`outputs/script_to_workflows.json`) for every move.
2. **Read workflow YAML from `main`, NOT the tarball snapshot** — editing chunk_extract from the stale snapshot silently reverted an earlier fix. Scripts are safe from the snapshot (unchanged); workflows are not (they change as you edit).

**Remaining in graph/:** `link_entities` + `build_fact_graph` — COUPLED (import `entity_matcher`, a shared utility). Do these together with the identity-utility move (`entity_matcher`, `narrative_gen`, etc.), updating every importer. Utilities are imported by the 4am core (company_enrichment, write_meridian) — synthetically exercise (import-test + `--dry-run` dispatch) before pushing.

**Next groups (REPO_LAYOUT §6 order):** scoring (compute_* — mostly self-contained), ingestion, validation, products, enrichment, then the utilities+identity (hardest, last).

---

# 🗂 REPO REORGANIZATION — day pass (2026-06-16)

Goal: standard-SWE structure, smaller files, legible for an engineer. Approach: **understand fully first** (the Cowork mount silently drops files in bulk reads, so all analysis was done on a tarball snapshot of `main` — reliable), then only **safe, self-verified** changes (the risky active-code moves wait for a supervised session).

## Done safely (engine verified green throughout)
- **Reliable dependency map** (`docs/architecture/DEPENDENCY_MAP.md`): the pipeline DAG (which workflow runs which scripts, in order), the 8 shared-utility modules, and all 26 import-coupling edges. THIS is the trustworthy what-relates-to-what reference.
- **Archived 17 one-off scripts** → `scripts/archive/` (verified not workflow-run + not imported; session backfills, wave2/3 backfills, one-run table migrations). One atomic commit.
- **Consolidated the two migration dirs** → single `migrations/` (moved 12 SQL, dropped 1 identical dup, updated the 2 manual seeders that referenced the old path). One atomic commit.
- **Docs organized**: `docs/architecture/README.md` index (orients an engineer + lists current-vs-historical docs); `REPO_LAYOUT.md` (target layout + safe migration sequence); `scripts/README.md` (domain map of the flat dir, with the authoritative active-script caveat).
- **Split designs (deep-read, executable)** in `PHASE3_4_EXECUTION_DESIGN.md`: `ct_gov_sync.py` (fetch/map/write) and `company_enrichment.py` (4,435 lines → enrichment/company/* by its existing sections).

## Reliable inventory
- 135 flat scripts → **63 active** (workflow-run), **8 utility** (imported: entity_matcher, narrative_gen ×11 importers, identity_resolution, model_comparison, company_identity_resolver, build_fact_graph, company_intake, meridian_integrations_feed), **17 archived**, rest = manual on-demand tools.

## NOT done — needs a SUPERVISED session (edits live pipeline code; can't watch CI while away)
1. Move active scripts into `src/meridian/<domain>/` packages — per `REPO_LAYOUT.md` §6, one group per PR, each gated by a green workflow run. Move the 8 utilities first (update every importer). Start with `graph/`.
2. Split the 10 large files (designs ready for the top 2) + `index.html` (Phase 4).
Why not now: e.g. `company_enrichment.py` is the 4am nightly core — a subtle import error would only surface when the unattended run fails. Verify each move with `--dry-run` dispatch + a green CI run, supervised.

---

# 🧹 CLEANUP PASS (2026-06-16, per Kyle: keep the repo legible)

- Wired `seed_competes_with.py` through **EdgeWriter** (508 edges, 0 rejections — governs against phantom edges) and fixed a `status`->`stage` KeyError in it.
- Deleted superseded `migrations/PROPOSED_drugwriter_enforcement.sql` (now implemented + applied as v157–v162).
- Dropped 5 dead, unreferenced VIEWS (`phase3_regulatory_risk_map`, `recent_field_changes`, `change_frequency_summary`, `company_area_detail`, `governance_change_alerts`) — all verified empty/unreferenced; dashboard re-verified healthy after. Moved the remaining dead-object backlog (Tier B/C) to **`docs/audits/SCHEMA_CLEANUP_BACKLOG.md`** and removed the stale `PROPOSED_drop_dead_tables.sql`.
- KNOWN minor wart (left, non-fatal): `seed_competes_with.py`'s separate `validation_tests` insert 409s on re-run (expression-unique constraint vs PostgREST upsert) — cosmetic; the edge seeding (the point) is clean. Worth a 1-line idempotency fix next pass.

STANDING: keep deleting dead/superseded code as we go; migrations/ should hold only real applied migrations; backlogs live in docs/.

---

# 🔧 WRITERS HARDENED (Phase 3 prereq DONE, 2026-06-16)

Single-writer **code layer is now complete + verified**. All 4 writers exist in `src/database/` (DrugWriter was already live). Found+fixed real bugs in 2:
- **EdgeWriter**: allowed only 13 predicates / 6 node types — would have REJECTED TESTED_IN (326), PRESENTED (442), CO_AUTHORED_WITH (4,979), MANUFACTURES, INVESTIGATES (1,808), and all abstract/author/kol/trial/patent edges. Expanded to the full **35 predicates / 18 node types** in the live graph. Verified: TESTED_IN/PRESENTED now accepted, bad predicate + missing node still rejected.
- **CatalystWriter**: still required drug/company only — out of sync with the broadened v160 `must_link`. Aligned to drug/company/**area/target/indication**. Verified area-anchored now passes.
- CompanyWriter verified OK (defaults subsidiary; rejects acquired-without-parent). All py_compile + dry-run smoke tests green.

**NEXT increment (the actual de-bulking):** wire the writers into the seeders/enrichers — route the ad-hoc `sb_upsert('entity_edges'/'catalysts'/'companies', …)` calls through Edge/Catalyst/CompanyWriter (start with the edge seeders — lowest risk, highest call-count). Each wiring de-bulks the script AND completes single-writer at the code layer (DB layer already enforces via v157–v162). Then the ct_gov_sync split per `docs/architecture/PHASE3_4_EXECUTION_DESIGN.md`.

NOTE: the Supabase **Management API** had a transient 504 outage around 12:25–12:30 UTC (Cloudflare); the project **REST endpoint stayed up** the whole time, so this work used REST. If DDL/migrations error with 504, just retry.

---

# ✅ EXECUTED OVERNIGHT (after the morning-review audit, 2026-06-16)

Kyle approved all 3 decisions + P1–P3. Done since the audit:
- **Governance 3 → 0.** Hard-deleted the 9 dropped records (off-domain oncology + phantoms incl. nvx-360/calt-100; full ref cleanup, 0 orphans, drugs 189→180). China stage flags resolved: GB-3250/generate-uc Phase 3→Preclinical (no trial evidence); LBL-053 already Preclinical (flag stale). ab001/sm-101 acknowledged (by-design ambiguous-identity).
- **P1:** 5 well-known mechanisms backfilled (certolizumab-pegol/etanercept/etrasimod/tildrakizumab/tofacitinib); SHR-1905→Hengrui; dispatched company-enrichment (firmographics — 58 country/strategic-value gaps, running in CI), evidence-collectors + refresh-company-verified (both green).
- **P2/P3:** delivered a code-validated execution design — `docs/architecture/PHASE3_4_EXECUTION_DESIGN.md` — for the ct_gov_sync split and the index.html first extractions. NOT executed live: the mount can't integration-test a 1,400-line refactor of a core pipeline mid-run; the design makes a focused session fast + safe.
- **Deferred (note):** canonicalize sl325/sl425/sl846 (needs entity_matcher in CI); 7 deal source_url backfills.

**Morning decisions left:** none blocking. Optional: review the 10 submitted_intel `needs_review` items; pick a focused session to execute the Phase 3 ct_gov_sync split (design ready).

---

# ☀️ MORNING REVIEW READY (2026-06-16 overnight)

Read **`docs/audits/MORNING_REVIEW_2026-06-16.md`** first. TL;DR: DB healthy (0 orphans/dups/validation-fails), enforcement live (4 rules + Layer B), engine green, governance 41→3, submitted-intel now 4-hourly (10 items in needs_review for you). Batch self-verified; 2 over-removed trial links were caught and restored. 3 decisions await you (see audit §3): hard-delete vs keep the 8 reversibly-dropped records; purge nvx-360/calt-100?; China-CDE check for generate-uc/lbl-053. Next-steps roadmap in audit §4 (quick data fixes → company firmographics → Phase 3 modularization).

---

# NEXT_SESSION — addendum (2026-06-16 PM, Stage 4 DONE)

Continued from the entry below. **Single-writer enforcement is now REAL (channel + invariant); the freeze can lift.**

## Added this block
- **Catalysts:** linked 17/26 unlinked catalysts to a specific drug/company; the other 9 are area-anchored (their company isn't in the DB yet — Denali/Odyssey/Abivax/NewLimit). Found+fixed one true duplicate (3124/3125 ATI-052, shared default sort_date). `migrations/v160` broadens `catalysts.must_link` to "drug OR company OR area" and **enforces** it.
- **Layer B (`migrations/v161`):** REVOKE INSERT/UPDATE/DELETE/TRUNCATE on drugs/companies/catalysts/entity_edges from anon+authenticated. Discovery: anon previously had FULL write on all core tables (could rewrite any field) + an `anon_update_drugs_partnership` RLS policy used by the dashboard partnership-pill (index.html ~L21171). Kept that feature via a column-scoped `GRANT UPDATE (partnership_verified, partner_company) ON drugs TO anon`. Verified: anon writing `mechanism` → 401; anon INSERT company → 401; pill toggle → 204; service_role/writers unaffected.
- **apg TARGETS edges re-synced:** apg777→`il13` only; apg279→`il13`+`ox40l` (were il4ra/ox40l from the pre-correction target).
- **drug_sources backfill:** missing-source drugs 20→11 (promoted 9 drugs' existing `source_url` into `drug_sources`); dispatched evidence-collectors for the rest. The 11 remaining are the known obscure code-named assets (resolve as they disclose).
- **Startup reliability:** fixed CLAUDE.md + README on `main` (stale `BD Platform` path → bd-dashboard; dead `.github_token` → `.github_token_workflow`) and corrected the memory-index paths.

## Now-open (not freeze-blocking) — see PRIORITY.md
1. Drug-discovery `company_id` policy → then enforce `drugs.company_id_required` (12 company-less code drugs).
2. Add Denali/Odyssey/Abivax/NewLimit companies → link the 9 area-only catalysts.
3. Optional: route the partnership-pill write through an RPC and drop the anon column grant.

---

# NEXT_SESSION — handoff (2026-06-16, Stage 4 enforcement ON)

**Session goal:** turn on Stage 4 single-writer enforcement and clear the Stage 1 residual data fixes. Both done (enforcement is partial-by-design). Operated on LIVE `main` + Supabase via the GitHub/Management APIs (git still deadlocks on the mount; key in `.github_token_workflow`).

## What got done
1. **Stage 4 WARN → EXCEPTION.**
   - `migrations/v157_writer_enforcement_warn.sql` — observe-only BEFORE INSERT/UPDATE triggers on drugs/companies/catalysts/entity_edges, logging every invariant breach to **`governance_enforcement_log`** (REST-queryable). Mode switch in `governance_enforcement_config`.
   - Watched a live write cycle (completeness-scoring, stock-prices, free-ingest, structural-edges) → only soft `brand_implies_approved` warnings, **zero hard violations**.
   - `migrations/v159_writer_enforcement_escalate.sql` — **per-rule** enforcement allow-list `governance_enforced_rules`. The two edge referential rules (`edges.subject_drug_orphan`, `edges.object_drug_orphan`) now **RAISE EXCEPTION**. Verified: phantom-edge insert rejected, valid edge accepted, all edge seeders green, 0 real writes blocked.
2. **Stage 1 residual data fixes (all via governed paths / Kyle-approved).**
   - **apg777 / apg279 were MIS-TARGETED** (review doc had it backwards). Primary sources: APG777 = zumilokibart = anti-IL-13 mAb; APG279 = IL-13×OX40L fixed-dose combination. Corrected target/mechanism/drug_format via DrugWriter, with Apogee sources.
   - **CLD-423 is REAL** (Caldera/Qyuns IL-23p19×TL1A bispecific, a direct Ailux competitor) and already existed as `cldr-001`. The 16 `cld-423` edges were wrong-id duplicates → deleted + code aliased onto cldr-001 (`migrations/v158`).
   - **Phantoms purged:** mk-1718, mdr-018 (no real-world asset; like the v80 mk-1695 purge) — ~54 edges deleted.
   - **Company-as-drug edges deleted** (abbvie/amgen/aurinia/jnj/ucb/orukatherapeutics, 6 edges).
   - **Duplicate molecules merged** (FK-aware `dedupe_entities.py`): ati-045→bosakitug, xmab5871→obexelimab. Codes aliased; bare rows retired. drugs 194→192.
   - **7 stale approved stages flipped** to `approved` (Fasenra, Rinvoq, Ebglyss, Imaavy, Rystiggo, Adbry, Nucala) — all verified marketed. brand⇒approved violations → 0.
   - Net: **orphan drug-edges 74 → 0.**

## ⚠️ Validate / watch
- Engine still healthy after enforcement (edge seeders re-ran green). If a NEW pipeline ever emits an edge to a not-yet-created drug, it will now hard-fail with `governance violation [edges.*_drug_orphan]` — that's intended; fix the writer to create the drug first.
- One known accepted side effect of the merges: a few `drug_sources`/`drug_targets`/`trial_registries` rows attached to the duplicate code-rows were dropped on unique-collision (regenerable derived data).

## Next (see PRIORITY.md queue)
1. **Link the 26 unlinked catalysts** (all real) → then add `catalysts.must_link` to `governance_enforced_rules`.
2. **Layer B permission boundary** (REVOKE INSERT/UPDATE on core tables from anon/authenticated + write RPC) — the real physical single-writer; confirm pipelines use service_role first.
3. **Drug-discovery `company_id` policy** → then enforce `drugs.company_id_required` (12 company-less codes remain).
4. **Backfill `drug_sources`** for the 58 drugs (run evidence-collectors, free).
5. **apg777/apg279 `TARGETS` edge re-sync** to il13/ox40l so the corrected target reaches the graph.

## Carried over
- 4 mechanism/target flags needing a primary source: `mk-1695`, `shr0817`, `hlx36`, `abs-101`.
- Service-role key rotation is Kyle's (standing security item).

---

# NEXT_SESSION — handoff (overnight 2026-06-15 → 06-16)

**Autonomous legibility + stabilization pass.** Goal: make the repo ready for morning review and friendly to an outside engineer, and refresh the planning docs to TRUE current state. Operated on the LIVE repo (`kyleklaassen-dev/bd-dashboard`, `main`) via the GitHub Contents + Git Data APIs. `index.html` was deliberately NOT touched (another task owns it).

## What got done tonight
1. **`update_log.md` trimmed** 495 KB → ~79 KB (most recent ~50 entries, 943 lines). Older history moved to `docs/reports/update_log_archive.md` (~410 KB). Both verified live.
2. **`docs/` root organized** 66 → 10 files. Moved 56 dated reports/audits/memos/DDL into `docs/reports/`, `docs/audits/`, `docs/database/`, `docs/frameworks/`, `docs/decisions/` in batch commits (git history preserves the moves). **Kept at docs root** (intentionally): the governance/read-first docs (`constitution.md`, `decisions.md`, `STABILIZATION_PLAN.md`) and the **script-referenced** docs (`foresight_review_queue.md` is a *write target* of `score_foresight.py`; `phase4_comparison_harness.md` is the default `--output` of the phase4 compare script; plus `drug_competitive_scores_ddl.sql`, `catalyst_quality_diagnosis.md`, `dashboard_dependency_inventory.md`, `evidence_reconciliation_layer.md`, `drug_area_scores_retirement_plan.md`).
3. **`README.md` reconciled to reality** — fixed the repository map (removed nonexistent `supabase/` and root `archive/` rows and `migrations/legacy/`; corrected `src/` to "only `database/` populated, rest staged"; corrected `scripts/` subdirs to integrations/maintenance/migrations; `docs/` subdir list now includes `decisions/`; added the 📡 Intelligence tab; deploy section now reflects the single protected `main`).
4. **Planning docs refreshed to TRUE state** — `PRIORITY.md` rewritten around the stabilization stage board (Engine on, Stage 0/1/2 done, Stage 3/5 in progress, Stage 4 blocked); this `NEXT_SESSION.md` section; a session-log entry appended to `docs/STABILIZATION_PLAN.md`. Live counts cited from anon read: drugs 194, companies 191, deals 218, governance unresolved 41, validation non-pass 35 (0 fail).

## ⛔ BLOCKED — needs you (the gating items)
The **Supabase service key and a working GitHub PAT were lost** — tonight had **read-only anon** DB access only. The following can't proceed until you **rotate + re-share the service key and a PAT, or remount `bd-dashboard`**:
- **Stage 4 enforcement DDL** — apply `migrations/PROPOSED_drugwriter_enforcement.sql` (the permission boundary that makes single-writer real). Needs the service key + a watch window.
- **Stage 1 residual data fixes** — the 41 governance + 35 validation rows that are *real* (wrong-asset trial links, stage-confidence, source gaps), not false-positives. Triage detail in `docs/audits/GOVERNANCE_TRIAGE_2026-06-15.md` + `docs/audits/VALIDATION_TRIAGE_2026-06-15.md`.
- **Stage 5 table backfills** — the dark/empty tables + missing links in `docs/audits/CONNECTIVITY_GAP_AUDIT_2026-06-15.md`.
- **Rotate the previously-exposed service-role key** (standing security item) — do this as part of the key refresh.

## ⏳ Carried over (still open from prior sessions)
- **4 mechanism/target flags** needing a primary source: `mk-1695`, `shr0817`, `hlx36`, `abs-101`.
- **11 obscure company-less drug codes** (`ab001`, `calt-100`, `eta1001`, `mg-k10`, `sm-101`, `xb3217`, …) — resolve as they disclose.

---

# NEXT_SESSION — handoff (overnight 2026-06-05 → 06)

Two-part overnight session. **Part 1** finished the narrative depth-of-trust stack; **Part 2** ("do all of these, especially patient") built four big new layers on top. All deployed to `main` via the GitHub Git Data API (local git can't commit on this mount; use `outputs/gh_commit.py "<msg>" <files...>`; for `.github/workflows/*` files set `GH_TOKEN_FILE=.github_token_workflow`).

## PART 2 — the four big pushes (newest)
1. **Patient-intelligence depth (North Star)** — `scripts/patient_narrative.py` + `generate_patient_briefs.py` + `.github/workflows/patient-briefs.yml`. Cited "Meridian Patient Brief" + "Meridian Patient Analysis" (molecule×patient fit) per indication, `entity_type='indication'`. Reuses the full provenance/independence/gap machinery. Generated UC/CD/IBD live. **Key fact:** the patient table is rich but UNSOURCED (`source_urls` NULL), so all patient facts land INTERNAL-tier → independence view shows 0 independent → **138 patient facts now queued for collection**. (commits dd634ef, 338a2ed)
2. **Autonomous evidence collector (the flywheel)** — `scripts/collect_evidence.py`. Works the gap queue by fetching VERIFIABLE independent sources — ct.gov registry records (per NCT) + Europe PMC publications (relevance-checked) — and writing cited `drug_sources` rows (never fabricates a URL; idempotent). **Proven closed loop:** collected 12 sources for tulisokibart / 8 for duvakitug → regen → independent_claims 3→5, peer-reviewed 14; duvakitug multi-domain 8→10. Wired as the first batch step. (commit 70420af)
3. **Go wide — all areas** — dispatched the narrative workflow on CI for **il23p19, tslp, il4ra, fcrn, igf1r** (limit=0) and the patient-briefs workflow for all 28 indications. Running now. (the competitive + patient layers go wide server-side overnight)
4. **Strategic decision layer (apex)** — `scripts/strategic_brief.py`. Ranked, cited BD brief per landscape, `entity_type='target', section='business'`. Each asset carries stage + overlap + DATA-TRUST grade; the brief **discounts low-trust profiles** and honors deal-sequencing. TL1A brief written: XmAb412 "call now" (A/94), SPY120 caveated (C/67), AbbVie timing-gated to ABBV-701 Oct-2026. First time trust actively shapes a recommendation. Wired into the batch driver. (commit 8788aa6)

## PART 1 — depth-of-trust stack (earlier tonight)
- **Stateful collection queue** (v76 + `sync_collection_queue.py`); **cross-publication value agreement** (v77 + `verify_publication_values.py` — NEJM abstract confirms tulisokibart 26%); **dashboard surfacing** (independence badge / disagreement chip / gap count / tier dots / ✓N× in `index.html`); **CI key fix** (scripts read `SUPABASE_SERVICE_KEY` from env — the weekly Narrative job had been failing); **full TL1A field populated** (72 narratives).

## ⚠️ Validate in the morning
- **Check the CI fleet finished green**: 5 area Narrative Generation runs + 1 Patient Briefs run were in_progress at write time. https://github.com/kyleklaassen-dev/bd-dashboard/actions — re-dispatch any that failed (key fix + collector are in `main`).
- **Eyeball a card** (tulisokibart): independence badge, ⚠ disagreement chip (26% vs 49.1%), tier dots, ✓N×.
- **Read the TL1A Strategic Brief**: `entity_narratives WHERE entity_type='target' AND entity_id='tl1a' AND section='business'` — this is the new decision layer; tell me if the ranking/logic matches your read (feedback goes in `narrative_feedback`, honored on regen).
- Migrations this session: **v72–v77** applied.

## Still open (next increments)
- Surface the **patient brief** + **strategic brief** on the dashboard (the card loader currently renders drug overview/intelligence; add indication briefs to area tabs and the `business` section to the landscape view).
- Feed cross-pub `confirmed` values + collected sources back as confidence boosts to the trust score.
- `sync_collection_queue --all` is heavy (per-row resolves); fine on schedules but could be batched.
- Collector v2: patient/epidemiology source discovery for the 138 indication gaps (currently it handles drug gaps).

---
## ⏳ STILL WAITING ON YOU (carried over, unresolved)
- **4 mechanism/target flags** needing a primary source (⚑ queue / `governance_violations`): `mk-1695`, `shr0817`, `hlx36`, `abs-101`.
- **11 obscure company-less drug codes** (`ab001`, `calt-100`, `eta1001`, `mg-k10`, `sm-101`, `xb3217`, …) — resolve as they disclose.
