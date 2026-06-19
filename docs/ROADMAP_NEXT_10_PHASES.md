# Meridian — Next 10 Phases (2026-06-19)

Where we are after the modularization push: **34 → 23 large files**, 12 splits merged, the
DRY_RUN-global trio refactored, the read-first-docs button live in the Atlas, and a full audit of
the two "sprint" orchestrators. This roadmap sequences what's next. Each phase lists **why now**,
**what**, **risk/gate**, and **dependencies**.

---

## Sprint verdict (answers "keep valuable aspects vs. remove?")

**Both sprints can be retired — but 7 of `weekend_sprint.py`'s 54 phases carry unique value and
must be preserved first.** Audit (`scripts/weekend_sprint.py` phase registry vs. the ~50 dedicated
`.github/workflows/*.yml`):

- **33 REDUNDANT** — a dedicated cron workflow already runs the capability (company-enrichment,
  compute-landscape-scores, source-verifier, bd-recommender, meridian-free-ingest, etc.).
- **14 ONE-OFF / OBSOLETE** — stubs (C5 patent, D7 patient), backfills (C6, D3-null), low-value
  read-only metrics (A7, A8, E7, E8, F5), or sprint-only artifacts (F2 NEXT_SESSION.md, F3 summary,
  F6 commit, F8 .md).
- **7 UNIQUE-VALUABLE** — must be promoted to their own workflow before deleting the orchestrator:
  | Phase | Script / capability | Writes | Promote to |
  |---|---|---|---|
  | A6 | `coverage_gap_finder.py` (✅ already split, `run()`) | `research_queue` (feeds queue-processor) | own daily/weekly cron |
  | E5 | `consistency_checker.py` (✅ already split, `run()`) | `agent_disagreements`, `governance_violations` | own cron |
  | F4 | `human_queue_builder.py` (✅ already split, `run()`) | `enriched_field_log.review_queue_position` | own cron |
  | D6 | `update_area_knowledge_counts.py` | `area_knowledge` counts | fold into a derived-refresh wf |
  | D9 | inline → `target_pair_whitespace` | bispecific counts | fold into compute-landscape-scores |
  | D11 | inline → `asset_value_predictions.composite_score` | composite scores | fold into derived-rebuild |
  | F10 | `build_navigator_lookup.py` | `navigator_lookup.json` (frontend) | fold into a deploy wf |

`school-week-sprint.yml` is a **second** orchestrator that's almost entirely redundant with
`company-enrichment.yml` + the daily enrichment workflows — no unique phases; safe to delete outright.

---

## Phase 1 — Wind down the sprints (promote 7, delete 2 orchestrators)
**Why now:** directly answers the open question, and **deletes the 3005-line `weekend_sprint.py`
(the single biggest file) + a redundant orchestrator** — the largest clarity win available.
**What:** (a) create 3 small cron workflows for A6/E5/F4 (they already have clean `run()`
entrypoints from the recent splits); (b) fold D6/D9/D11/F10 into existing scoring/derived/deploy
workflows; (c) delete `weekend_sprint.yml`, `school-week-sprint.yml`, and `scripts/weekend_sprint.py`
(+ its `scripts/weekend/` runtime helper if now unused).
**Risk/gate:** new crons are a production change → **Kyle approves the promotion plan first**; verify
each promoted workflow with one `workflow_dispatch` manual run before deleting the orchestrator.
**Depends on:** the A6/E5/F4 splits (done, #51/#52/#53).

## Phase 2 — Schema-drift sweep (fix the silent/hard 400s)
**Why now:** the dry-run smokes during splitting surfaced **broken data-layer queries** — some
silently return 0 (dead QA checks), one **hard-crashes `compute_coverage`** (school-week coverage
step has been failing). These are correctness holes masquerading as "green."
**What:** one audit that diffs each check's `select=` column list against the live table schema
(via REST `?limit=1`), then fix: `drug_targets.role`, `trial_registries`, `coverage_scores`,
`catalyst_calendar`, `deals`, `entity_relationships`, `drugs.bd_angle/risk_summary`.
**Risk/gate:** read-only investigation + small query fixes; re-run each affected script `--dry-run`.
**Depends on:** none (3 chips already queued for the worst offenders).

## Phase 3 — Finish the PIPE-tier large-file splits
**Why now:** the proven recipe (base-module + `--dry-run` smoke + byte-identical relocation) clears
the rest of the >500 backlog. **Phase 1 already removes the 3005-line file**, so this is the long tail.
**What:** remaining PIPE files via the recipe — safest leaves first (`signal_monitor`,
`process_queue_item`, `fetch_homepage_news`, `bd_recommender`, `company_validator`,
`validate_ground_truth`, `products/issue/fetch`, `drug_intelligence_researcher`, `source_verifier`,
`conflict_detector`, `ct_gov_sync`, `review_submitted_intel`), then `research.py` (913, **nightly
chain root**) last and carefully.
**Risk/gate:** each on a cron → byte-identical + `--dry-run`/dynamic-load smoke per file, one PR each.
**Depends on:** nothing; can run in parallel with Phase 2.

## Phase 4 — DASH tier (the frontend monolith)
**Why now:** `assets/js/app.js` (13.5k) + `index.html` (7.1k) are the last and largest structural
debt; can't be done headless.
**What:** externalize the remaining inline JS in `index.html` first, then split `app.js` into
same-scope ordered modules per `STATUS_AND_GAPS_2026-06-19.md §4`.
**Risk/gate:** **browser-verified, supervised** — each split checked against live data in the preview
before the next.
**Depends on:** a supervised session with Kyle.

## Phase 5 — Workflow consolidation & DAG documentation
**Why now:** ~50 workflows with overlapping schedules and responsibilities (the sprint audit exposed
how much duplicated). After Phase 1 the count drops; rationalize the rest.
**What:** map the canonical daily/weekly DAG (who writes what, in what order), merge/retire
duplicate crons, and surface the DAG in the Streamlit Atlas (it already parses live YAML).
**Risk/gate:** schedule changes are low-risk but production-facing → review before disabling any cron.
**Depends on:** Phase 1 (removes the sprint nodes from the DAG).

## Phase 6 — Entity-resolution convergence (17 → 1)
**Why now:** the north-star metric. Scattered resolvers (`identity_resolution.py` 612 + others) risk
mis-attributing facts across the graph; one resolver is both correctness and a large-file win.
**What:** converge the duplicate resolution implementations onto the single `entity_matcher.py`
(ambiguity-guarded), deprecate the rest.
**Risk/gate:** **semantic** change to entity linking → characterization tests + supervised; not a
byte-identical split. Builds on `test_entity_matcher_pure.py`.
**Depends on:** Phase 7 (need resolver tests first).

## Phase 7 — Test coverage beyond the write layer
**Why now:** the splitting exposed that `check_undefined_names.py` is unreliable (missed 8 imports)
and the suite **only covers the write layer** — QA/scoring scripts have no regression gate.
**What:** characterization tests for the consistency checks, coverage scoring, foresight, and the
resolvers — fast, deterministic, CI-gated — so future refactors have a real safety net.
**Risk/gate:** additive; no production impact.
**Depends on:** none; unblocks Phase 6.

## Phase 8 — Flip core-write enforcement to hard-block
**Why now:** single-writer is currently **audit-mode** (logs bypasses, doesn't block). After a clean
`core_write_audit` watch, make it enforced.
**What:** apply `migrations/PROPOSED_drugwriter_enforcement.sql` once `select * from core_write_audit`
is empty over a real window; extend to companies/catalysts/edges.
**Risk/gate:** **DDL on core tables → Kyle's approval**; staged, reversible.
**Depends on:** a clean audit window (the trigger is already live).

## Phase 9 — Repo-health scoreboard in CI
**Why now:** large-file count is dropping fast — lock the gains so they don't regress.
**What:** wire `meridian_health_metrics.py` (the 5 structural metrics) into `ci-quality-gate.yml` as
a tracked trend that **fails on regression** (new >500 file, new ad-hoc writer, etc.).
**Risk/gate:** CI-only; tune thresholds to avoid false failures.
**Depends on:** Phases 1/3 (so the baseline reflects the cleaned state).

## Phase 10 — Documentation & onboarding refresh
**Why now:** with the sprints gone and structure modular, the docs should match reality so "any
engineer can step in" (the stated north star).
**What:** refresh `CLAUDE.md`, `constitution.md`, `governance_table.md`, and the read-first canon;
confirm the Atlas's read-first-docs button + workflow DAG reflect the new world; archive the
stabilization/sprint-era docs that no longer apply.
**Risk/gate:** docs-only.
**Depends on:** Phases 1–5 (document the end state, not a moving target).

---

### Sequencing at a glance
- **Immediate, unblocked, high-value:** Phase 1 (sprint wind-down — needs Kyle's go), Phase 2
  (schema-drift), Phase 3 (PIPE splits). Run 2 & 3 in parallel.
- **Supervised sessions:** Phase 4 (DASH), Phase 6 (resolver convergence), Phase 8 (enforcement flip).
- **Foundational/locking-in:** Phase 7 (tests, unblocks 6), Phase 9 (health CI), Phase 10 (docs).
