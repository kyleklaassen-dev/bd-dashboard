# Phase 3 / Phase 4 — Execution Design (2026-06-16)

Derived from the actual code structure (not the outline). Ready to execute in a focused session with the harvester pipelines idle. Follows the modularization safety doctrine: entrypoint unchanged, extract cohesive modules, verify `py_compile` + import-smoke + a live workflow dispatch, route writes through `src/database`, one step at a time, reversible.

> **Why this is a design, not an executed refactor:** the Cowork mount deadlocks on Python reads/imports of the repo, so the only integration test available mid-session is dispatching the live pipeline — and ct_gov_sync feeds drug discovery, with related harvesters running. Executing a 1,400-line split that can only be verified post-hoc, unattended, is the wrong risk. Verification path that DOES work: Read each file → write copies to a scratch dir → `py_compile` + import-smoke there → deploy → dispatch `api-harvest-daily` → confirm green + that auto drugs still insert.

---

## Phase 3 — `ct_gov_sync.py` (1,409 lines) → `scripts/ingestion/ctgov/`

Confirmed function map (line numbers as of 2026-06-16):

| New module | Functions to move | Lines | External deps | Risk |
|---|---|---|---|---|
| `ctgov/map.py` | `parse_ct_study` (685), `_format_date_label` (811), `score_search_match` (837) | ~230 | **pure** (CT.gov JSON → records) | **none — extract FIRST** |
| `ctgov/validate.py` | `validate_drug_brand_name` (276), `validate_trial_study_acronym` (311), `validate_drug_field_consistency` (354), `run_field_validation` (420) | ~260 | `sb_get` (pass client) | low |
| `ctgov/fetch.py` | `ct_fetch_by_nct` (637), `ct_search_by_name` (662) | ~50 | `requests`, CT_API base | low |
| `ctgov/write.py` | `update_trial_registries` (541); **migrate `sb_get`/`sb_upsert`/`sb_patch` (580–636) → `src/database/client.py`** | ~60 saved | client | low (writer routing) |
| `ct_gov_sync.py` (stays as entrypoint) | `log`, `sync_drug` (1139), `step3a/b/c` (914/1001/1081), `run_sync` (1257), `get_trials_for_*` (1363/1371), `__main__` (1392) — now `from ctgov.map import …` etc. | ~750 | imports above | — |

**Order:** map.py (pure, zero-risk, validates the pattern) → validate.py → fetch.py → route writes to `client.py`. After each: py_compile + import-smoke + `api-harvest-daily` dispatch must stay green and still insert `discovery_status='auto'` drugs (now governed by the v162 rule).

**Gotchas:** functions reference module-level CT_API URL + area maps + an injected `resolver` — pass these explicitly into the moved functions (don't rely on shared module globals). `map.py` is genuinely pure → do it first to prove the seam with the least risk.

**Then** apply the same fetch/map/write pattern to the higher-value scripts in `docs/architecture/modularization_plan.md` order: company_enrichment.py (#1, biggest win — 22 `sb_upsert` → CompanyWriter once it exists), write_meridian.py (#2), research.py (#3), drug_intake.py (#4 — defer its resolver to the shared entity_matcher).

**Prereq that unblocks the most:** build `CompanyWriter` / `EdgeWriter` / `CatalystWriter` (only DrugWriter exists). Each writer migration de-bulks every calling script AND completes the single-writer story at the code layer (the DB layer is already enforced via v157–v162).

---

## Phase 4 — `index.html` (33,983 lines) — first-step scope only

Do NOT refactor the whole file. The safe first step: extract the largest **self-contained JS modules** into `/assets/js/*.js` loaded via `<script src>` (GitHub Pages serves them fine), one module per PR, verifying the dashboard still renders each time (load the page, check the 📡 Intelligence tab + an area PI + global search).

Highest-value, lowest-coupling first extractions (per `docs/architecture/INDEX_HTML_MAP.md`):
1. The `intel2` module (📡 Intelligence tab renderer, ~lines 31141–31395) — already self-contained, 14 template-literal fetches; clean to lift into `assets/js/intel2.js`.
2. `_makeAreaPI` / `_resolveStage` and the area-PI render helpers — cohesive, reused across 6 dashboards.
3. The Supabase client init + shared fetch helpers → `assets/js/sb.js`.

Each extraction must keep the same global function names (the inline `onclick=`/event handlers reference them) — so extract to plain `<script>` files, not ES modules, unless every call site is updated. Verify via a real page load (Chrome MCP) after each, not just a diff.

---

## What I executed this session vs designed
- **Executed:** all 3 decisions (9 hard-deletes, China stage flags, ambiguous-identity ack); governance 41→**0**; P1 mechanisms (5) + enrichment pipelines dispatched (firmographics running, sources collected).
- **Designed (ready to execute, not run tonight for the risk reason above):** the ct_gov_sync split (Phase 3) and the index.html first extractions (Phase 4).
- **Deferred with note:** canonicalize sl325/sl425/sl846 (needs the real entity_matcher — run in CI/non-mount env); 7 deal `source_url` backfills (need per-deal press URLs).
