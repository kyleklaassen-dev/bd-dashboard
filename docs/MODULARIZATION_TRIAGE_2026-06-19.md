# Large-File Modularization Triage (2026-06-19)

## PROGRESS LEDGER (updated 2026-06-19, overnight autonomous push)

**Done — split + verified + merged (under 500):**
| File | Was→Now | Split into | PR |
|---|---|---|---|
| `identity/model_comparison.py` | 727→412 | `model_comparison_report.py` | #42 |
| `identity/company_intake.py` | 504→276 | `intake/reaudit.py` | #43 |
| `scripts/compute_strategic_value.py` | 581→452 | `strategic_value_scoring.py` (pure) | #44 |
| `scripts/seed_targets.py` | 791→408 | `seed_targets_data.py` (pure data) | #45 |
| `scripts/seed_competes_with.py` | 692→394 | `competes_targets.py` + `competes_edges.py` | #47 |

Method proven headless: byte-identical relocation → `py_compile` + `check_undefined_names`
+ **runtime functional smoke** (catches missing stdlib imports the static check misses —
e.g. `defaultdict` in #47) + consumer-import + writer/entity tests. See [[section3-split-method]].

**LIB tier: COMPLETE.** 2 split (#42 model_comparison, #43 company_intake); 4 legitimately
skipped — `enrichment/company/assessment.py` (one 633-line `write_step5`, no inner defs →
nothing to relocate; needs *extraction* refactor, supervised), `enrichment/company/prompts.py`
(prompt text), `identity/identity_resolution.py` (converge on `entity_matcher`, don't split),
`scoring/acquisition/scoring.py` (already modular, test-covered).

**SEED tier deferred (need bespoke work, NOT unattended byte-identical):**
- `consistency_checker.py`, `coverage_gap_finder.py`, `human_queue_builder.py` — **mutable
  `DRY_RUN` global write-gate**: `run()` rebinds `global DRY_RUN`, `sb_post/upsert` read it.
  Splitting writers to a base module splits the global → dry-run could write prod. Needs the
  runtime-accessor refactor (semantic, supervised).
- `drug_enrichment.py` (876) — clean-ish seams but **scattered**, and `enrich_drug` is called
  nightly by weekend_sprint phase B1 → PIPE-level blast radius despite SEED filing.
- `compute_landscape_coverage.py` (543) — SAFE 3-file split available (base + metrics + inline
  main; its `DRY_RUN` is an import-time constant, not rebound). Good next target, slightly fiddly
  (no `main()`, inline bottom orchestration).
- `seed_preclinical_competitors.py` (527) — data blocks reference a **module-level live fetch**
  (`INNOVENT_ID = innovent_rows[0]...`) → not pure-data-extractable.
- `approve_discovery.py` (506) — only ~6 lines over; cleanest seam (DB helper layer) tangles
  creds + `sys.exit` + path-hacks + an interleaved `infer_catalog_category` import. Low ROI.

**Archive files (`scripts/archive/*`, 5 files >500) are OUT OF SCOPE** per CLAUDE.md (historical).

Count: 34 real targets (excl. archive) at session start → **30 remaining** after this push.

---

Every file > 500 lines, triaged by **how it's invoked** (= blast radius if a split
goes wrong), with a recommended split approach and the verification gate each needs.
This is the managed backlog for Phase 3. Method throughout: **§3 byte-identical
relocation** (move functions verbatim into new modules, re-import) — safe *by
construction*, the only risk being unresolved names, which a compile + import +
AST free-var check catches.

**Why these are not being auto-split + merged overnight:** the §3 safety gate is
"tests stay green," but our suite only covers the write layer. For PIPE/DASH files
a runtime break wouldn't be caught by anything I can run headless, and the code
runs unattended on a schedule / serves the live dashboard. So each tier below has a
**human-in-the-loop gate** matched to its risk. Execute in tier order (LIB → SEED →
PIPE → DASH); within a tier, biggest first.

---

## Tier LIB — imported libraries (6) · **safest, start here**
Import-verifiable; several have tests. A byte-identical split + `compileall` +
importing every consumer + the existing unit suite is a sufficient gate.

| Lines | File | Notes / seam |
|---|---|---|
| 780 | `enrichment/company/assessment.py` | drug/company assessment; split scoring vs prompt-assembly |
| 747 | `enrichment/company/prompts.py` | mostly prompt builders — split by prompt family (has `build_step5_prompt` test) |
| 727 | `identity/model_comparison.py` | enrichment-run logging vs model-diff scoring |
| 612 | `identity/identity_resolution.py` | ⚠ resolver — converge on `entity_matcher` rather than just split |
| 516 | `scoring/acquisition/scoring.py` | already covered by `test_pure_functions` → split is fully gated |
| 504 | `identity/company_intake.py` | intake vs validation halves |

**Gate:** `compileall` + import every consumer + `tests/run_all.py` green.

## Tier SEED — standalone scripts, no workflow (10) · low frequency
Not on any cron; run manually. A bug surfaces on next manual run, not unattended.

| Lines | File |
|---|---|
| 916 | `scripts/consistency_checker.py` |
| 876 | `scripts/drug_enrichment.py` |
| 791 | `scripts/seed_targets.py` |
| 725 | `scripts/coverage_gap_finder.py` |
| 692 | `scripts/seed_competes_with.py` |
| 635 | `scripts/human_queue_builder.py` |
| 581 | `scripts/compute_strategic_value.py` |
| 543 | `scripts/compute_landscape_coverage.py` |
| 527 | `scripts/seed_preclinical_competitors.py` |
| 506 | `scripts/approve_discovery.py` |

**Gate:** `compileall` + import + a `--dry-run`/`--help` smoke run where supported.

## Tier PIPE — scheduled-workflow code (19) · **dry-run gate required**
Each runs on a cron. Split one at a time; the owning workflow's entrypoint must be
exercised in dry-run before merge.

| Lines | File | Workflow |
|---|---|---|
| 3005 | `scripts/weekend_sprint.py` | weekend_sprint — **in progress** (globals decoupled, #34/#36) |
| 943 | `validation/conflict_detector.py` | validation-research |
| 938 | `enrichment/company_enrichment.py` | school-week-sprint |
| 913 | `ingestion/research.py` | validation-research / **nightly chain root** |
| 815 | `validation/source_verifier.py` | source-verifier |
| 773 | `identity/review_submitted_intel.py` | review_submitted_intel |
| 768 | `enrichment/drug_intelligence_researcher.py` | school-week-sprint |
| 745 | `ingestion/fetch_homepage_news.py` | fetch-homepage-news |
| 687 | `ingestion/ct_gov_sync.py` | (chain) |
| 680 | `identity/process_queue_item.py` | queue-processor |
| 665 | `ops/signal_monitor.py` | signal-monitor |
| 642 | `scoring/compute_coverage.py` | school-week-sprint |
| 607 | `products/bd_recommender.py` | bd-recommender |
| 604 | `validation/validate_ground_truth.py` | run-validation-tests |
| 599 | `products/issue/fetch.py` | patent-sweep |
| 569 | `validation/company_validator.py` | refresh-company-verified |
| 550 | `scoring/compute_attribute_completeness.py` | atlas-refresh |
| 549 | `scoring/score_foresight.py` | score-foresight |
| 509 | `integrations/patentsview_patents.py` | patent-sweep |

**Gate:** §3 split + `compileall` + import + **`python <entrypoint> --dry-run`** (or a
scoped run) confirming no errors/writes, then a watched first scheduled run.

## Tier DASH — live dashboard (9) · **browser-verified, supervised only**
Classic global-scope `<script>` files called by HTML `onclick`. A split must keep
the global-call contract + load order and be verified by exercising every UI path.

| Lines | File |
|---|---|
| 13554 | `assets/js/app.js` (plan in `STATUS_AND_GAPS_2026-06-19.md` §4) |
| 7124 | `index.html` (mostly markup; 78 lines inline JS to externalize first) |
| 2433 | `assets/js/core.js` |
| 1815 | `assets/js/ontology_explorer.js` |
| 1326 | `assets/js/ontology_audit.js` |
| 1289 | `assets/js/audit.js` |
| 745 | `assets/js/dkn.js` · 662 `discovery_queue.js` · 520 `company_database.js` |

**Gate:** split into same-scope ordered scripts; verify each in the browser preview
against live data before the next.

---

## Recommended execution order
1. **LIB tier** (6) — I can do these now as reviewed PRs; import + unit gate is sufficient.
2. **SEED tier** (10) — next; dry-run/smoke gate.
3. **PIPE tier** (19) — one at a time, **you dry-run before each merge**. Start with the safest (`compute_attribute_completeness`, `score_foresight`) before the chain root (`research.py`).
4. **DASH tier** (9) — supervised session; start by externalizing the 78 inline-JS lines, then `app.js` per §4.

Note: several LIB/PIPE "resolver" files (`identity_resolution`, parts of `company_intake`)
should **converge on `entity_matcher`**, not merely be split — see the entity-resolution
north-star (17 implementations → 1).
