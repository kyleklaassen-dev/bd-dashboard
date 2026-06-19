# Meridian — Status & Gap Analysis (2026-06-19)

Written during an overnight autonomous session. Grounds every claim in a live check
of the repo / DB so the picture is real, not aspirational. Companion to
`STABILIZATION_PLAN.md` (which this corrects in places).

---

## 1. What changed this session (verified, merged unless noted)

| # | Change | State |
|---|---|---|
| Single-writer migration | all 20 core-table writes (17 `sb_*` + 3 REST) routed through Writers; debt = 0 | ✅ merged (#29, #30) |
| Audit hardened | catches `sb_*` **and** raw-REST writes; one detector shared with the scoreboard | ✅ merged (#30, #31) |
| CI ratchets | new direct writes **and** new ad-hoc helpers both fail CI | ✅ merged (#32) |
| Dead code | 3 unused `sb_patch` defs removed | ✅ merged (#33) |
| **DB enforcement (audit mode)** | `core_write_audit` trigger on **drugs + companies + catalysts** — logs non-Writer writes, **blocks nothing** | ✅ **applied + verified live** |
| weekend_sprint decouple | `DRY_RUN` (#34, merged) + `SPRINT_ID` (#36, open) moved to `weekend/runtime.py` | 🔄 split unblocked |

**The enforcement watch is now running.** Over the next few real runs, query
`select * from core_write_audit;`. If it stays empty, that's *runtime* proof nothing
bypasses the Writers — then flip the trigger from log-only to `RAISE EXCEPTION`
(see `PROPOSED_drugwriter_enforcement.sql`). That one change closes Phase 2.

---

## 2. Corrections to the plan (doc-vs-reality drift)

A recurring theme this session: **the docs lag the code.** Found and corrected:

- **"Direct-write audit: drugs 0"** — was incomplete (only checked `sb_upsert`). Reality was 20 bypasses. Now actually 0 + ratcheted.
- **Phase 4: "decompose index.html (33,983 lines)"** — **stale.** `index.html` is **7,124 lines**; the JS is already externalized into `assets/js/` (16 modules). Phase 4 *as written is essentially done.* The new monolith is **`assets/js/app.js` — 13,554 lines, 211 functions** (see §4).
- **`PROPOSED_drugwriter_enforcement.sql` / `PROPOSED_drop_dead_tables.sql`** — referenced as staged but didn't exist; the enforcement one is now authored + applied (audit mode).
- **"dead tables"** — live-DB check showed the flagged tables are real-but-empty framework tables; none safe to drop.

**Recommendation:** treat doc drift as a first-class risk. The CI scoreboard now
reflects reality for write-paths; the same discipline should extend to the plan.

---

## 3. What's missing — prioritized

### P0 — finish what's in flight
- **Flip enforcement to hard-block** after a clean watch window (drugs first). *Owner: Kyle.*
- **Merge the weekend_sprint decouple (#36)** after a `--dry-run` confirms zero writes. *Owner: Kyle.*

### P1 — the real reliability gap: **test coverage**
Only **4 test files** exist (`test_writers`, `test_drug_writer`, `test_edge_cases`,
`test_pure_functions`) — they cover the **write layer + pure functions only**. The
ingestion pipelines, the entity matcher, scoring, and the published products
(briefs/summaries/recommendations) have **no automated tests**. A pipeline can break
silently until the unattended nightly fails. This is the highest-leverage missing
safety net after single-writer.
- Start with characterization tests for `entity_matcher` (the shared resolver — a bug here corrupts linking everywhere) and the scoring functions.

### P2 — structural debt (Phase 3 modularization)
- **`assets/js/app.js` (13,554 lines)** — the largest single file in the repo; the true Phase-4 successor (§4).
- **`scripts/weekend_sprint.py` (3,003)** — split unblocked; PR-B pending.
- **34 more files 500–999 lines** (`conflict_detector` 943, `company_enrichment` 938, `consistency_checker` 916, `research` 913, …).
- **17 entity-resolver implementations** — converge on `entity_matcher` (plan north-star; partly done per the §E equivalence audit).
- **46 ad-hoc write helpers** — consolidate onto `meridian.database`; ratcheted (can't grow) but not yet reduced.

### P3 — observability & tooling
- **Wire the Workflow Atlas into CI** — a static check on `.github/workflows` changes would catch broken `workflow_run`/path references automatically (it's currently a manual tool).
- **Alerting on nightly failures** — `pipeline_health`/`pipeline_monitor` exist; confirm they alert (not just log).

---

## 4. Phase 4 reality + `app.js` decomposition plan

`index.html` (7,124 lines) is now mostly HTML markup + **78 lines of inline JS** (5
small `<script>` blocks). The work moved into `assets/js/`, but `app.js` grew into a
**13,554-line, 211-function** classic global-scope script (loaded via
`<script src>`, called from HTML `onclick` handlers).

**Why it can't be split unattended:** every function is a browser global referenced
by inline handlers; a split must preserve load order and be verified by exercising
**every** modal/tab/grid against live data. That needs a human at the browser.

**Decomposition plan (for a supervised session):** `app.js` already has clean
thematic seams (from its own section comments) — split into same-scope `<script>`
files loaded in order, one per concern:
- `app_grids.js` (loadData, formatters, initGrids — lines ~1–290)
- `app_tabs.js` (tab meta / titles / toggles)
- `app_meridian.js` (Meridian issue bridge + archive)
- `app_company_modal.js` (company slide-over / CEM — the largest block, ~570–1830)
- `app_drug_modal.js` (drug dossier / intelligence)
- `app_entity_modal.js` (canonical entity modal renderer)
Keep them as classic scripts (not ES modules) to preserve the global-call contract,
load in the current order, and verify each extraction in the browser preview before
the next. Quick win first: externalize the 5 inline `<script>` blocks from `index.html`.

---

## 5. Suggested next sequence
1. **Kyle:** flip enforcement to hard-block (after clean watch) + dry-run-merge #36.
2. **Claude (supervised or low-risk):** characterization tests for `entity_matcher` + scoring (P1).
3. **Claude (supervised):** `app.js` split per §4, browser-verified.
4. **Claude:** weekend_sprint PR-B (block extraction) once #36 lands.
5. **Claude:** wire Atlas into CI; resolver convergence; helper consolidation.
