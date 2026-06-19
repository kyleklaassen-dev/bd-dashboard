# Large-File Modularization Triage (2026-06-19)

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
