# Production-Readiness Review — Framework + Current Findings (2026-06-19)

Answers: *"How do I prepare for a full review and make sure everything has a start and
finish with no loose ends? What should I look for?"*

Two parts: **(1) the repeatable review framework** — the dimensions to audit and *how* to
check each (so any future review is mechanical, not vibes); **(2) current findings** — what a
full pass just turned up, with status. Run Part 1's checks; Part 2 is the live punch-list.

---

## Part 1 — The review framework (what to look for, and how)

A capability is "production-ready with no loose ends" when it has a **start** (a trigger), a
**finish** (a consumed output), and a **safety net** (a test or a dry-run). Audit along these 10
axes:

| # | Dimension | The question | How to check (mechanical) |
|---|---|---|---|
| 1 | **Every script has a START** | Is it triggered by a cron/workflow, imported, or a documented manual tool? | For each `.py`: grep `.github/workflows/` for `python <path>`; grep imports; check `scripts/README.md`/`REPO_LAYOUT.md`. None of the three → **orphan**. |
| 2 | **Every output has a FINISH** | Does something read what it writes? | For each table written (`sb_post/upsert/patch/insert`): grep the frontend (`assets/js`, `index.html`) and Python reads for that table name. Zero readers → **dead derived table**. |
| 3 | **Every workflow's script EXISTS** | Do all `python <path>` targets resolve? | Enumerate all `python(3) <path>` in workflows; `test -f` each. |
| 4 | **`--dry-run` actually means dry** | Does the flag gate writes, or is it cosmetic? | For each script with `--dry-run`: confirm `args.dry_run`/`is_dry_run()` is *referenced* in every write path. Monkeypatch `requests` to raise; run `--dry-run`; expect zero network. |
| 5 | **No dead credentials** | Any reference to a dead secret? | grep for `.github_token` (the dead file) vs `.github_token_workflow` (live); grep cred files that no longer exist. |
| 6 | **Flags do what they say** | Declared CLI flags all wired? | grep `add_argument` → confirm each `dest` is read somewhere. Unused = misleading. |
| 7 | **Schema matches queries** | Do the `select=` column lists match live tables? | Run each data script `--dry-run`; any `HTTP 400` = schema drift. Or `GET /rest/v1/<table>?limit=1` and diff columns. |
| 8 | **A safety net exists** | Is the *logic that decides truth* tested? | Map `tests/` coverage to modules. Scoring/enrichment/QA/resolvers untested = the riskiest gap. |
| 9 | **No silent failure** | Do `continue-on-error` / bare `except` hide breakage? | grep workflows for `|| echo`/`continue-on-error`; grep code for `except: pass`. Each masks a real error (this is how the school-week `--area` bug hid for months). |
| 10 | **One implementation per job** | Duplicate scoring/resolver paths? | grep for self-flagged `TODO (dedupe…)`; the entity-resolution "17→1" north-star; overlapping `compute_*`/`score_*`. |

**Cadence:** axes 1–6 are cheap greps → run every PR (CI could gate #3/#5/#6). Axes 7–10 are a
periodic deep pass (quarterly, or before a big release).

---

## Part 2 — Current findings (live punch-list)

Full evidence in this session's audit. Status: ✅ fixed · 🔧 chip queued · 📋 open · ⏸ needs Kyle.

### Axis 1 — Orphans (cleanup)
- ✅ Deleted (zero refs): `seed_strategic_views`, `sync_collection_queue`, `enrich_trial_identity`, `scripts/weekend/` (PR #64/#66).
- ⏸ **Capabilities that lost their scheduler** when the sprints died — *delete or re-schedule (your call)*: `drug_enrichment.py` (876 lines), `drug_intelligence_researcher.py`, `molecule_enrichment.py`. These aren't dead — they're real enrichment that no longer runs anywhere.
- 📋 `seed_indication_priorities.py` — superseded by `compute_indication_priority.py`; still listed as a tool in two docs. Delete + doc-update, or keep.

### Axis 2 — Dead derived tables (paying to write data nobody reads)
- ⏸ `asset_value_predictions` (no writer even remains), `drug_development_timelines`, `agent_disagreements`, `market_landscape`, `landscape_briefings`, `bd_recommendations`. Each is written (some weekly) and read by **nothing**. Decide per table: surface it in the dashboard, or stop writing it. `agent_disagreements` is notable — the consistency checker fills it every week and nothing looks at it.

### Axis 3 — Workflows → scripts: **CLEAN** ✅ (all 84 referenced paths resolve post-sprint-deletion).

### Axis 4 — `--dry-run` honesty
- ✅ `process_queue_item.py` — flag was parsed but ignored (wrote anyway); now gated across all 3 write paths (PR #65).
- 📋 Sweep the rest with the monkeypatch test (axis 4 method) — most are fine; this one wasn't.

### Axis 5 — Dead credentials
- ✅ `build_navigator_lookup.py` deploy → `$GITHUB_TOKEN`/`.github_token_workflow` (PR #66).
- 📋 `scripts/deploy_files.py:17` + `src/meridian/ops/pipeline_health.py:31` still fall back to `.github_token` (latent local breakage); update + their docstrings.

### Axis 6 — Misleading flags
- 📋 `rescore_completeness.py --null-only` (parsed, never used) and `ictrp_china_harvest.py --max-pages` ("reserved", no-op). Wire or remove.

### Axis 7 — Schema drift (broken QA — **highest correctness risk**)
- 🔧 `compute_coverage.py` **hard-crashes** on `drug_targets?role=eq.primary` → school-week coverage step has been failing (chip queued).
- 🔧 `consistency_checker` Check 1 400s on `trial_registries` → silently returns 0 (chip queued).
- 📋 Also 400-ing (silently → 0): `coverage_gap_finder` gaps on `coverage_scores`, `catalyst_calendar`, `deals`, `entity_relationships`, `drugs.bd_angle/risk_summary`. One schema-vs-query audit fixes the cluster.

### Axis 8 — Test coverage
- 📋 Covered: the 4 core-table **Writers** + ~10 pure leaf functions + the entity-matcher tables. **Untested:** all scoring, all enrichment, the entire QA/validation layer, and the resolvers — i.e. the code that decides what data is *true*. Add characterization tests here before refactoring it (the static import-checker proved unreliable during the splits).

### Axis 9 — Silent failure
- The school-week `--area` bug (steps erroring for months under `continue-on-error`) is the cautionary tale. 📋 Audit `|| echo "non-fatal"` steps: a step that *always* fails non-fatally is dead weight pretending to work.

### Axis 10 — Duplicate implementations
- 📋 Self-flagged `TODO (dedupe, supervised)` in `enrichment/company/scoring.py` and `…/resolve.py` (overlap the shared scoring + `entity_matcher`). Plus the **entity-resolution 17→1** north-star (`identity_resolution.py` 612 lines → converge on `entity_matcher`). Roadmap Phase 6/7.

### Structural (the large-file program, in flight)
- Python >500: **34 → 19** this session (16 splits + the 3005-line `weekend_sprint.py` deleted). `drug_enrichment.py` (876) remains pending the axis-1 keep/delete decision.
- **The real frontier is JavaScript:** `app.js` (13,554), `core.js` (2,433), 6 more JS files, + `index.html` (7,124). DASH tier — browser-supervised splitting (roadmap Phase 4).

---

## The 8 highest-leverage fixes (impact × ease)
1. **Schema-drift sweep** (axis 7) — restores broken QA + un-crashes coverage. *High / medium.*
2. **Decide the 6 dead tables** (axis 2) — stop writing, or surface. *High / medium.*
3. **Decide the 3 unscheduled enrichment scripts** (axis 1) — delete or re-home. *High / easy (a decision).*
4. **QA-layer characterization tests** (axis 8) — biggest correctness net. *High / medium.*
5. **`deploy_files`/`pipeline_health` dead-token fallbacks** (axis 5). *Med / trivial.*
6. **`--null-only` / `--max-pages` flags** (axis 6). *Low / trivial.*
7. **Audit `|| echo non-fatal` steps** (axis 9) — find the next silent school-week. *Med / easy.*
8. **Continue large-file splits → then DASH** (structural). *Med / ongoing.*
