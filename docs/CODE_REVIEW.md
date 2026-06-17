# Ailux BD Platform — Code Review Brief
**For external model review · Produced 2026-05-19**

---

## Purpose of This Document

This document is a structured map of the entire Ailux BD Platform codebase. It is intended to give an external model (or reviewer) enough context to:
1. Understand what the system does and how it is architected
2. Trace data from source (ClinicalTrials.gov / Claude API) to display (dashboard)
3. Identify bugs, logic errors, or structural improvements
4. Assess consistency between the frontend expectations and the backend data model

Read the **Platform Context** and **Data Model** sections first, then use the **File Index** to navigate to the code sections most relevant to the review task.

---

## Platform Context

**What it is:** A single-page BD intelligence dashboard for Ailux Biotherapeutics, tracking 6 disease areas: TL1A, TSLP, IL-4Rα, FcRn, IGF1R, and T-cell. The platform tracks competitive drugs, clinical trials, upcoming catalysts, and BD deal activity across ~50 companies.

**Who uses it:** The BD team at Ailux — specifically to monitor competitive threats, identify partnership targets, and time BD outreach.

**Ailux's lead asset:** TL1A×IL-23p19 bispecific antibody for UC/CD.

**Live URL:** https://kyleklaassen-dev.github.io/bd-dashboard/

**Infrastructure:**
- Frontend: `index.html` — single-file SPA hosted on GitHub Pages (no build step)
- Backend: Supabase project `tghntyofptvfhmtchwcv` — PostgreSQL + PostgREST
- Pipeline: GitHub Actions → Python scripts → Claude Sonnet API → Supabase
- Credentials: Never committed. Loaded from `.supabase_anon_key` / `.supabase_service_key` / `.github_token` / `.supabase_pat` files at runtime

---

## Data Flow

```
ClinicalTrials.gov API v2
    ↓  ct_gov_sync.py (Step 3)
    ↓  → trials table (NCT IDs, phases, PCDs, arms, endpoints)
    ↓  → identity_resolution.py stamps canonical_drug_id on each trial

Claude API (Sonnet)
    ↓  company_enrichment.py (Steps 1, 4, 5, 6)
    ↓  → Step 1: entity discovery (new companies from recent intel)
    ↓  → Step 4: catalyst auto-generation from trial PCDs
    ↓  → Step 5: narrative enrichment (platform_summary, vs_ailux, bd_summary, etc.)
    ↓  → Step 6: deal intelligence (extract deals from intel items)
    ↓  → Writes to: company_profiles, drugs, catalysts, deals

research_intelligence.py (Step 7)
    ↓  Reads all data for each entity
    ↓  Scores completeness (0–100, 6 weighted stages)
    ↓  Detects triggers (stale profile, catalyst past-due, etc.)
    ↓  Calculates priority score (0–200)
    ↓  Writes to: research_queue, stamps drugs table

identity_resolution.py
    ↓  Resolves drug name strings → canonical_drug_id
    ↓  4-step cascade: exact → normalized → fuzzy-flag → create new
    ↓  Writes to: canonical_drugs, drug_aliases, identity_audit_log, resolver_errors

identity_health_check.py
    ↓  Read-only health report on the canonical identity layer
    ↓  CLI flags: --fail-on-orphans, --fail-on-fuzzy-pending (used in CI)

Frontend (index.html)
    ↓  Supabase anon key (read-only, RLS-enforced)
    ↓  Loads: companies, drugs, trials, catalysts, deals, intel, research_queue, identity stats
    ↓  Renders: Home tab, 6 molecule tabs, Drugs to Know, Market & Learning, Industry Insights
```

**Pipeline schedule:**
- Nightly Mon–Sat 04:00 UTC: `ct_gov_sync` + `company_enrichment` for TL1A; `research_intelligence` for all 6 areas
- Weekly Sun 05:00 UTC: Full pipeline for all 6 areas
- GitHub Actions workflow: `.github/workflows/company-enrichment.yml`

---

## Data Model (16-table Supabase schema)

```
── Core entities ──────────────────────────────────────────
companies          id, name, ticker, exchange, company_type, ailux_angle,
                   stock_price, stock_change, last_verified, tagline

drugs              id, name, company_id, entity_id, entity_name, entity_type,
                   stage, target, mechanism, cls, overlap, route, dosing_type,
                   drug_format, indication_short, phase_display, half_life_note,
                   vs_ailux, vs_competitor, differentiation_thesis, results_summary,
                   drug_class, is_combo, dosing_schedule, canonical_drug_id,
                   identity_confidence, identity_method, completeness_score,
                   completeness_tier, missing_fields, missing_stages,
                   next_best_action, priority_score, trigger_flags, last_scored_at,
                   trial_data_status, sort_order, discovery_status, confidence_score,
                   last_synced_date

── Junction tables ─────────────────────────────────────────
company_areas      company_id, area_id
drug_areas         drug_id, area_id

── Clinical data ───────────────────────────────────────────
trials             id (NCT ID), drug_id, entity_id, trial_name, phase, status,
                   indication, n_enrollment, primary_endpoint, secondary_endpoints,
                   arms, start_date, primary_completion_date, pcd_label, readout_date,
                   source_url, sponsor, last_synced_date, discovery_status,
                   confidence_score, canonical_drug_id

── BD intelligence ─────────────────────────────────────────
catalysts          id, catalyst_date, sort_date, label, company_id, drug_id, area_id,
                   significance (high/medium/low), catalyst_type, notes, resolved,
                   related_trial_id, is_key_watch, confidence_source, canonical_drug_id

deals              id, deal_date, deal_date_label, from_company, to_company, company_id,
                   entity_id, area_id, deal_type, headline, detail, upfront_usd_m,
                   total_usd_m, source_url, ailux_signal, economics_royalties,
                   strategic_signal, ailux_relevance, geography_rights, canonical_drug_id

company_profiles   company_id, area_id, platform_summary, bd_summary, key_risk,
                   why_it_matters, vs_ailux, strategic_behavior, pipeline_url,
                   market_cap_usd_m, cash_runway, financing_history, key_investors,
                   competitive_position, key_differentiators, last_enriched_at,
                   enriched_by

── Intelligence ────────────────────────────────────────────
intel              id, intel_date, headline, body, source_url, source_name,
                   intel_type, importance
intel_areas        intel_id, area_id
intel_companies    intel_id, company_id

company_signals    company_id, dir (up/down/neutral), signal_text, sort_order

research_queue     id (uuid), entity_id, entity_name, company_id, area_id,
                   priority_score, reason, next_best_action, missing_stage,
                   missing_fields (jsonb), strategic_importance, completeness_score,
                   completeness_tier, trigger_events (jsonb), assigned_status
                   (pending/in_progress/done), last_updated
                   UNIQUE constraint: (entity_id, area_id)
                   RLS: SELECT + UPDATE for anon role

── Identity layer ──────────────────────────────────────────
canonical_drugs    canonical_id (CANON_DRUG_{sha256[:8]}), canonical_name,
                   drug_class, mechanism, target, is_active, merged_into,
                   confidence_score

drug_aliases       canonical_id, alias_name, alias_type, source, confidence_score,
                   is_primary, last_seen_at
                   ON CONFLICT: ignore-duplicates (no duplicate aliases per canonical)

identity_audit_log operation, canonical_id, related_id, old_value, new_value,
                   reason, performed_by, performed_at
                   Key operations: 'resolve_drug', 'create_canonical', 'flag_review'

resolver_errors    drug_name, source, source_table, source_row_id, error_message,
                   error_type, stack_trace, attempt_count, resolved_at,
                   resolved_canonical_id, last_attempted_at
```

---

## File Index

| File | Lines | Role |
|---|---|---|
| `index.html` | 10,497 | Single-page frontend — all CSS, HTML, JS |
| `scripts/company_enrichment.py` | 1,012 | Intelligence pipeline: entity discovery, catalyst gen, Claude enrichment, deal intel |
| `scripts/ct_gov_sync.py` | 951 | ClinicalTrials.gov sync: direct NCT fetch + search discovery |
| `scripts/research_intelligence.py` | 1,199 | Completeness scoring, trigger detection, priority queue |
| `scripts/identity_resolution.py` | 612 | Drug identity resolution: 4-step cascade, audit log, error persistence |
| `scripts/identity_health_check.py` | 222 | Read-only identity layer health report with CI flags |
| `scripts/one_time_migration.py` | 274 | Backfill canonical_drug_id on existing drug records |
| `scripts/research.py` | 414 | Meridian research scheduled task (runs nightly, writes intel) |
| `scripts/stock_prices.py` | 174 | Stock price refresh scheduled task |
| `.github/workflows/company-enrichment.yml` | 260 | GitHub Actions: nightly + weekly + manual pipeline triggers |

---

## CODE: scripts/ct_gov_sync.py

**Purpose:** Pipeline Step 3. Maintains `trials` as a current mirror of ClinicalTrials.gov for every tracked drug.

**Routing logic (sync_drug):**
1. Approved products (`APPROVED_DRUGS`) → mark `trial_data_status='populated'`, skip deep sync
2. Pre-IND drugs (`PENDING_TRIAL_DRUGS`) → mark `trial_data_status='pending'`, skip
3. Drugs in `NCT_SEED_MAP` → Step 3a: direct NCT fetch (confidence=100, status='manual')
4. Drugs not in seed map → existing trial IDs from DB, then Step 3b: search discovery
5. Step 3b always runs even when seed NCT IDs exist (finds expansion trials)
6. Step 3c: update `drugs.stage` to most advanced active trial phase

**Identity integration (circuit-breaker pattern):**
- Calls `DrugIdentityResolver.resolve()` before syncing each drug
- On any failure: logs error via `log_resolver_error()`, continues with `canonical_drug_id=None`
- Resolver failures never crash the sync

**Key constants:**
- `NCT_SEED_MAP`: ~15 manually-verified drugs with known NCT IDs
- `APPROVED_DRUGS`: 8 approved products that skip deep sync
- `PENDING_TRIAL_DRUGS`: 3 pre-IND drugs expected to have no trials yet

**Confidence scoring (score_search_match):**
- +50: drug name in trial brief title
- +25: drug name words in title (partial)
- +30: drug name in interventions
- +15: indication matches condition
- -20: trial is Terminated/Withdrawn
- ≥85 → `discovery_status='auto'`; 60–84 → `'unverified'`; <60 → skip

```python
# KEY PATTERN: circuit-breaker identity resolution
canonical_drug_id = None
if _IDENTITY_RESOLVER_AVAILABLE and not dry_run:
    try:
        resolver = DrugIdentityResolver(SUPABASE_URL, SUPABASE_KEY)
        canon_id, conf, method = resolver.resolve(drug_name, source="ct_gov", ...)
        canonical_drug_id = canon_id
    except Exception as exc:
        log(f"  ⚠ Identity resolver failed: {exc} — proceeding without canonical_drug_id")
        try:
            resolver.log_resolver_error(drug_name, "ct_gov_sync", exc, "drugs", drug_id)
        except Exception:
            pass  # never let error-logging crash the sync
```

**Known issues / review points:**
- `step3b_search_discovery` runs even when seed NCT IDs exist (`if not dry_run or not known_ncts`). The condition is slightly inverted — on dry_run with known NCTs, it skips 3b, which means dry-run doesn't fully simulate production behavior.
- `run_sync` passes `search_only` flag to function signature but never reads it inside `sync_drug` — the flag has no effect.
- Rate limiting: 0.5s between NCT fetches (3a), 0.3s between search results (3b), 1.0s between drugs. These are hardcoded; no backoff on 429 responses.
- The `NCT_SEED_MAP` is static and in-code. New drugs discovered by Step 1 won't have entries here and will always go through the lower-confidence search path.

---

## CODE: scripts/company_enrichment.py

**Purpose:** Steps 1, 4, 5, 6 of the intelligence pipeline. Entity discovery, catalyst generation, Claude enrichment of narrative fields, deal intelligence.

**Architecture: 7-step model**
- Step 1 (discovery): Claude Haiku scans recent intel for new competitors → creates company + drug + company_areas records
- Step 2 (drug mapping): handled by Supabase schema, not this script
- Step 3 (trial sync): handled by `ct_gov_sync.py` — must run BEFORE this script
- Step 4 (catalyst gen): auto-creates catalyst records from trial `primary_completion_date` fields
- Step 5 (Claude enrichment): Claude Sonnet generates all narrative + structured fields
- Step 6 (deal intel): scans recent intel for deal keywords → creates deal records
- Step 7 (dashboard): frontend reads Supabase directly

**Step 5 prompt (build_step5_prompt):** Sends company context (drugs, trials, catalysts, deals, recent intel, existing profile) to Claude Sonnet. Expects structured JSON with `company_profile`, `drug_updates`, `catalysts`, and `deal_updates` keys. Uses exponential backoff (3 attempts, 10s/20s/30s delays).

**Cost tracking:** Each Step 5 call logs token usage and estimated cost (`$3/Mtok input, $15/Mtok output`) — visible in GitHub Actions logs.

**COMPANY_ALIASES:** Static dict mapping common name variants → Supabase company IDs (e.g., `"genentech" → "roche"`). Used by `resolve_company_id()` for fuzzy name matching during entity discovery.

```python
# KEY PATTERN: Step 5 retry with backoff
for attempt in range(1, 4):
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=4096,
            system=ENRICHMENT_SYSTEM,
            messages=[{"role": "user", "content": prompt}]
        )
        text = resp.content[0].text
        break
    except Exception as e:
        log(f"  Claude error (attempt {attempt}/3): {e}")
        if attempt < 3:
            time.sleep(10 * attempt)
```

**Known issues / review points:**
- `step6_deal_intelligence` uses keyword matching (`{"license","acqui","partner",...}`) on intel headlines. False positives are likely (any headline mentioning "$" or "million" qualifies). There's no deduplication against actual deal content — only headline text[:50] matching against existing headlines[:50].
- `build_step5_prompt` passes `financing_history` as a JSON array field for private companies. If Claude returns a non-list value for this, `write_step5` will write it directly to Supabase without validation, potentially breaking the JSONB column.
- `COMPANY_ALIASES` is hardcoded. New companies discovered by Step 1 won't be in this map and will create new Supabase IDs based on `re.sub(r'[^a-z0-9]', '', co_name.lower())[:20]`. This can produce collisions for company names that normalize to the same 20-char slug.
- There's a 2-second sleep between companies (`time.sleep(2)`) — appropriate for rate-limiting but means a full TL1A run (~20 companies) takes ~40+ seconds just in sleep time.
- `parse_enrichment_response` handles markdown-fenced JSON (```` ```json ```) but uses split-on-fence logic that could fail if the response has multiple code blocks.

---

## CODE: scripts/research_intelligence.py

**Purpose:** Step 7. Scores every entity 0–100 across 6 research stages, detects triggers, calculates priority score, writes to `research_queue`.

**Stage weights (must sum to 100):**
| Stage | Weight | Key fields scored |
|---|---|---|
| Stage 1 — Entity Discovery | 10 | entity_id present, drugs list, company_id |
| Stage 2 — Drug Mapping | 15 | mechanism, target, stage, differentiation_thesis, canonical_drug_id |
| Stage 3 — Trial Intelligence | 20 | has trials, arms/endpoints populated, confidence ≥80, canonical linked |
| Stage 4 — Catalyst Engine | 15 | has catalyst, catalyst has expected_date + title |
| Stage 5 — Strategic Positioning | 25 | profile exists, competitive_position, vs_ailux (double weight), key_differentiators |
| Stage 6 — Deal Intelligence | 15 | has deals, deals have economics_royalties or strategic_signal |

**Canonical grouping:** Drugs are grouped by `canonical_drug_id` before scoring. Multiple drug rows sharing one canonical are merged via `_merge_drug_rows()` (best-populated value per text field) so a company doesn't score higher just by having more DB rows.

**Priority score formula:**
```
base = 100 - completeness_score
+ 30 if strategic entity (cls = 'direct' or '1st gen')
+ 20 if any triggers
+ 10 per additional trigger (capped at +40)
+ 15 if 'thin' tier
+ 10 if 'profile_stale' trigger
+ 10 if 'catalyst_date_passed_unresolved' trigger
- 10 if 'strong' tier with no triggers
result: clamped to [0, 200]
```

**Trigger types detected:**
- `trial_phase_ahead_of_drug_stage`: trial phase rank > drug stage rank
- `trial_pcd_without_catalyst`: trial has PCD but drug has no catalyst
- `completed_trial_without_results`: trial status completed but drug has no results_summary
- `catalyst_date_passed_unresolved`: catalyst expected_date < today, no outcome/results_url
- `profile_stale`: profile enriched_at > 30 days ago, or profile exists but no enriched_at
- `new_deal_since_enrichment`: deal created_at > profile last_enriched_at
- `strategic_entity_missing_vs_ailux`: cls contains 'direct' or '1st gen' AND vs_ailux empty

**Research queue write:** Uses explicit `on_conflict=entity_id,area_id` to upsert without resetting `assigned_status`. The pipeline intentionally never resets user-set statuses — only updates scores and action.

**Known issues / review points:**
- Stage 4 scoring checks `c.get("expected_date")` and `c.get("title")` — but the catalysts table uses `sort_date` and `label`, not `expected_date` and `title`. These fields will always be falsy. Stage 4 will always score 0.5 (has catalysts) and never the additional 0.5 for "detail." This is a field name mismatch.
- `get_next_best_action()` checks catalyst dates using `c.get("expected_date")` (line 699), same wrong field. Trigger T4 in `check_research_triggers()` also uses `c.get("expected_date")` (line 828). Both should use `sort_date`.
- `_merge_drug_rows()` picks the "best" text field value by `max(..., key=len)` — longest string wins. This means a stale long string beats a short but accurate one. No recency weighting.
- `load_entity_context()` fetches company from `drugs[0].get("company_id")` — silently returns wrong company if the first drug has a null or stale `company_id`.
- `upsert_research_queue()` sets `assigned_status: "pending"` on every upsert. But because the on_conflict resolves with `merge-duplicates`, this will overwrite a user-set status of `in_progress` or `done` on every pipeline run. **This is a critical UX bug** — the status toggle in the dashboard will be reset by every nightly pipeline run. The field should be excluded from the upsert payload if the row already exists.
- `calculate_priority_score()` checks `cls_field` for `"direct"` or `"1st gen"` but the `cls` field on `companies` may be `None` — coerced to empty string so this is safe, but the field is not documented in the schema overview above.

---

## CODE: scripts/identity_resolution.py

**Purpose:** Resolves drug name strings to `canonical_drug_id` values using a 4-step cascade.

**Resolution cascade:**
1. Exact alias match (case-insensitive trim) → confidence 100, method `'exact'`
2. Normalised alias match (strip anti-/mab/antibody/inhibitor, collapse punctuation) → confidence 90, method `'normalized'`
3. Fuzzy match ≥0.85 (SequenceMatcher) → **flag review, create NEW canonical** → confidence 70, method `'new'`
4. No match → create new canonical drug → confidence 100, method `'new'`

**Critical design decision:** Fuzzy matches are flagged to `identity_audit_log` with `operation='flag_review'` but are NOT merged. A new canonical is created and a human must explicitly merge via Supabase SQL editor. This prevents false merges.

**Alias cache:** Loaded from `drug_aliases` table on first `resolve()` call. In-memory dict keyed by both `alias_lower` and `normalize(alias)`. Not refreshed between individual calls — only on `resolve_batch()`.

**Error persistence:** `log_resolver_error()` writes failures to `resolver_errors` table. `retry_errors()` re-attempts all unresolved rows, stamps source table rows on success.

**Known issues / review points:**
- The cache is loaded once per `DrugIdentityResolver` instance. Each call to `ct_gov_sync.py` and `company_enrichment.py` creates a new `DrugIdentityResolver` instance **per drug** (inside the per-drug loop). This means the full alias table is fetched from Supabase once per drug — potentially 50+ API calls per pipeline run just for the cache. Should be instantiated once per script run, not per drug.
- `_normalize_name()` removes the suffix `mab$` and `antibody$` from the end of strings. This could over-normalize: `"tulisokibart"` → `"tulisokibart"` (fine), but `"anti-TL1A antibody"` → `"tl1a"` (too aggressive — drops the meaningful drug name part).
- Fuzzy matching uses `SequenceMatcher` over the full alias cache on every Step 3 call. With 500+ aliases this is O(n) per resolve call — acceptable now but will become slow at scale.
- `_add_alias_if_new()` uses `"Prefer": "resolution=ignore-duplicates"` which silently ignores conflicts rather than updating `last_seen_at`. The intent was to refresh `last_seen_at` but this header prevents the update.
- `_log_audit("create_canonical", ...)` passes `old_value=None` and `new_value={"canonical_name": ..., "source": ...}` via a positional arg that maps to the `new_value` parameter — but this is `_log_audit(operation, canonical_id, related_id, old_value, new_value)`. The call at line 294 passes `None` for `new_value` and a dict as the 5th argument without a keyword — actually maps to `new_value` correctly, but the `old_value` parameter receives `None` explicitly. This is correct but fragile positional arg usage.

---

## CODE: scripts/identity_health_check.py

**Purpose:** Read-only health report on the canonical identity layer. Used in CI via `--fail-on-orphans` and `--fail-on-fuzzy-pending` flags.

**Checks performed:**
1. Drug identity coverage (total vs. resolved, target: 100%)
2. Identity confidence distribution (high ≥85, medium 70–84, low <70; target: 95% high)
3. Resolution method breakdown (exact / normalized / fuzzy / new)
4. Canonical drug table (active count, merged/retired count)
5. Alias coverage (total aliases, drugs with aliases)
6. Fuzzy review queue (`identity_audit_log` where `operation='flag_review'`, target: 0)
7. Orphaned records (drugs with `canonical_drug_id` FK pointing to non-existent canonical)

**CI failure conditions:**
- `--fail-on-orphans`: exit 1 if any orphaned FK refs
- `--fail-on-fuzzy-pending`: exit 1 if any fuzzy reviews pending

**Auth:** Uses `SUPABASE_PAT` (personal access token) to call the Supabase Management API `POST /v1/projects/{id}/database/query` endpoint — bypasses PostgREST/RLS entirely. Falls back to reading `.supabase_pat` file.

**Known issues / review points:**
- `issues.append(f"{int(r['orphans'] if False else 0)} drugs unresolved...")` at line 165 — the expression `r['orphans'] if False else 0` always evaluates to `0`. The intent was to show the unresolved count but it will always print "0 drugs unresolved." Bug: should be `int(total) - int(resolved)`.
- The script uses the Management API (PAT-based) rather than PostgREST (anon/service key). This requires `SUPABASE_PAT` secret in GitHub Actions but the README/playbook says to use `SUPABASE_SERVICE_KEY` for most scripts. The two auth paths are inconsistent.

---

## CODE: .github/workflows/company-enrichment.yml

**Purpose:** CI/CD pipeline for the intelligence graph. Three trigger modes: nightly TL1A, weekly all-areas, manual dispatch.

**Pipeline sequence (per area):**
1. `ct_gov_sync.py --area <area>` (Step 3)
2. `company_enrichment.py --area <area>` (Steps 1, 4, 5, 6)
3. `research_intelligence.py --area <area>` (Step 7)
4. `identity_health_check.py --fail-on-orphans --fail-on-fuzzy-pending` (post-pipeline CI check)

**Secrets required:**
- `ANTHROPIC_API_KEY` (company_enrichment.py)
- `SUPABASE_URL` (all scripts)
- `SUPABASE_SERVICE_KEY` (ct_gov_sync, company_enrichment, research_intelligence)
- `SUPABASE_PAT` (identity_health_check.py only) — ⚠ must be added to GitHub repo settings separately

**Known issues / review points:**
- `pip install anthropic requests` — no pinned versions. A breaking change in either package will silently break the pipeline. Should use `requirements.txt` with pinned versions.
- Timeout is 120 minutes. With `area=all` (6 areas × 3 scripts), real runtimes for large runs with Claude API could approach this limit.
- The `[Manual]` identity health check step runs only when `area=all` AND `dry_run != 'true'`. There's no health check after single-area manual runs. Inconsistency with the nightly and weekly runs which always run the health check.
- No artifact upload — GitHub Actions logs are the only record of pipeline runs. If a run fails silently (non-zero exit not caught), there's no alert mechanism.

---

## CODE: index.html — Frontend Architecture

**Structure:** 10,497 lines, single file. No build toolchain. CSS in `<style>` blocks, JS in `<script>` blocks, HTML in between.

**Tab system:** Icon nav bar with a molecule dropdown (center). Tabs managed via `switchTab(id)` / `switchTabTo(id, sectionId)`. Tab state isolated via `TAB_REGISTRY` pattern — each tab registers `onEnter`/`onLeave` hooks wrapped in try/catch. Errors in one tab never crash others.

**Supabase client:**
```javascript
const SUPABASE_URL  = "https://tghntyofptvfhmtchwcv.supabase.co";
const SUPABASE_ANON = "eyJhbGci..."; // anon key — read-only, RLS-enforced, safe to expose
const _sb = supabase.createClient(SUPABASE_URL, SUPABASE_ANON);
```

**Key JS functions and their data dependencies:**

| Function | Tables read | Key behavior |
|---|---|---|
| `loadMeridianReader()` | intel, intel_areas, deals, catalysts, company_profiles | Unified feed — 5 parallel queries, score+sort, top 5 highlighted |
| `loadStockCards()` | companies, company_areas, company_signals, intel, intel_companies | Sort by recency of intel; builds HTML per company |
| `loadCatalysts()` | catalysts | Sort by date; filter by area; countdown badges |
| `loadDeals()` | deals | Filter by area; expandable rows |
| `loadResearchQueue()` | research_queue | Priority-sorted; status toggle per row; hide-done filter |
| `loadIdentityHealth()` | drugs, canonical_drugs, identity_audit_log, resolver_errors | 4 parallel queries; color-coded stats |
| `loadBDSignal()` | deals | Top 5 deals with ailux_signal; area color coding |
| `loadAreaCompetitors(tabId)` | drugs, drug_areas | Entity-grouped PI table; CLASS × RELEVANCE framework |
| `loadAreaIntel(tabId)` | intel, intel_areas | Area-filtered intel feed |
| `loadAreaCatalysts(tabId)` | catalysts | Area-filtered catalyst list |
| `loadAreaDeals(tabId)` / `loadAreaBDActivity(tabId)` | deals | Expandable BD activity table per molecule tab |
| `loadMoleculeTab(tabId)` | (orchestrates all area loaders) | Lazy-loads on first visit; all loaders run in parallel |
| `dknLoadSbData()` | drugs, company_profiles | Live data for Drugs to Know detail panels |

**CLASS × RELEVANCE framework (all molecule tabs):**
- CLASS: `1st Gen` (blue) / `2nd Gen` (green) / `Next Gen` (purple) — therapeutic sophistication
- RELEVANCE: `Direct` (red) / `Adjacent` (orange) / `Same-Space` (teal) / `Watch` (yellow) — overlap with Ailux
- Stored on `drugs.cls` and `drugs.overlap` fields; rendered as pill tags in PI tables

**Known issues / review points:**
- **`loadIdentityHealth()` orphan proxy:** The dashboard approximates orphan count as `total - resolved` (unresolved drugs). This is NOT the same as orphans (broken FK refs). A drug can be unresolved without having a broken FK. The accurate orphan count requires a JOIN query that PostgREST can't easily express — the Python health check does this correctly but the dashboard shows the wrong metric.
- **`loadResearchQueue()` RLS:** `research_queue` table requires explicit SELECT and UPDATE policies for the `anon` role. If policies are missing, `_sb.from('research_queue').select(...)` returns 0 rows silently (no error). The policies were added via DO/EXCEPTION blocks (not `IF NOT EXISTS` which PostgreSQL doesn't support for policies).
- **`rqSetStatus()` status reset race:** The pipeline's `upsert_research_queue()` always writes `assigned_status: "pending"` (see issue noted in research_intelligence.py above). User-set statuses will be overwritten on every nightly run.
- **`loadMeridianReader()` sort score:** Intel items sorted by `importanceScore + dateStr * 0.0001`. The date string is a YYYY-MM-DD string multiplied as a number — JavaScript coerces this to NaN. The recency sort component is silently broken; only importance score determines order.
- **Inline event handlers in research queue rows:** `onclick="rqSetStatus('${r.entity_id}','${r.area_id}','${status}')"`. If `entity_id` or `area_id` contains a single quote (unlikely given slugs but possible), this produces broken JS.
- **`loadBDSignal()` calls `fmtMoney()` and `rdtFmtDate()`** which are defined elsewhere in the file. The functions are defined lower in the file than their first use in `loadBDSignal`. This works in practice (all `<script>` runs before DOMContentLoaded) but is a maintenance hazard.
- **`buildStockCard()` signals:** `const insightSignal = signals.find(s => true)` — the predicate `s => true` always matches, so it's just `signals[0]`. Minor: could be `signals[0]` for clarity.
- **`loadAreaCompetitors()` phase ordering:** `PHASE_ORDER` map used for sorting competitors by stage. The map keys must exactly match `drugs.stage` values. Any staging string not in the map defaults to sort position 99 (end of list). New stage strings from pipeline (e.g., `"Phase 2/3"`) must be added to this map or they'll always sort last.
- **No global error boundary:** Individual functions catch errors and display them inline. But if the Supabase client itself fails to initialize (network issue on page load), all functions will throw `_sb is undefined` — no graceful fallback.
- **`DOMContentLoaded` load order:** The home tab loads `loadMeridianReader()`, `loadCatalysts()`, `loadDeals()`, `loadBDSignal()`, `loadResearchQueue()`, `loadIdentityHealth()`, `loadStockCards()` — 7 parallel top-level async calls on page load. On slow connections this creates 20+ concurrent Supabase queries.

---

## Cross-Cutting Issues

### 1. assigned_status reset (CRITICAL)
**Files:** `research_intelligence.py` (line 998) + `index.html` (`rqSetStatus`)
`upsert_research_queue()` always includes `"assigned_status": "pending"` in the upsert payload. Because `merge-duplicates` updates all provided fields on conflict, every nightly pipeline run resets user-set statuses to `pending`. The fix is to exclude `assigned_status` from the upsert and only set it on row creation (i.e., use a separate INSERT with `on_conflict=do_nothing` for the status field, or PATCH separately).

### 2. Wrong field names in scoring (MEDIUM)
**File:** `research_intelligence.py` (lines 558-559, 699, 828)
Stage 4 catalyst scoring checks `expected_date` and `title`. The `get_next_best_action()` and `check_research_triggers()` functions also check `expected_date`. The actual Supabase catalysts table uses `sort_date` and `label`. These checks always return `False`, meaning Stage 4 never gets full credit and trigger T4 never fires.

### 3. Identity resolver instantiated per-drug (MEDIUM)
**Files:** `ct_gov_sync.py` (~line 741), `company_enrichment.py` (~line 794)
`DrugIdentityResolver` is created fresh inside each per-drug loop iteration. Each instantiation fetches the full `drug_aliases` table. Fix: instantiate once at the script level and pass to per-drug functions.

### 4. Meridian Reader sort NaN (LOW)
**File:** `index.html` (`loadMeridianReader`, line ~1816)
`(item.intel_date || '').replace(/-/g,'') * 0.0001` — string × number in JavaScript produces NaN when the date string is non-numeric. The entire sort secondary key is broken; only `importanceScore` differentiates items.

### 5. Summary bug in identity_health_check.py (LOW)
**File:** `scripts/identity_health_check.py` (line 165)
`int(r['orphans'] if False else 0)` always evaluates to `0`. The message always says "0 drugs unresolved" regardless of actual coverage.

### 6. No requirements.txt pinning in CI (LOW)
**File:** `.github/workflows/company-enrichment.yml`
`pip install anthropic requests` — no version pinning. A semver bump in the Anthropic SDK (which has broken interfaces between versions) could silently break the pipeline.

---

## Structural Patterns Worth Noting

### Supabase helper duplication
`ct_gov_sync.py` and `company_enrichment.py` both define identical `sb_get()`, `sb_upsert()`, `sb_patch()` helper functions. `research_intelligence.py` defines its own versions `_sb_get()`, `_sb_upsert()`, `_sb_patch()` with slightly different signatures. No shared module. Changes to error handling (e.g., adding retry logic) must be made in 3 places.

### Error swallowing pattern
Almost every pipeline function wraps Supabase calls in `try/except Exception as e: log(...); return []`. This means a Supabase outage during a pipeline run produces a silent partial run — some entities enriched, some not, with no failure signal to GitHub Actions. The run exits 0. The identity health check is the only step that actively fails CI.

### Dry-run consistency
`ct_gov_sync.py`, `company_enrichment.py`, and `research_intelligence.py` all implement `--dry-run` but with different semantics. `ct_gov_sync.py` still makes CT.gov API calls; `company_enrichment.py` still makes Claude API calls; only Supabase writes are skipped. A dry run with `company_enrichment.py` will consume Claude API credits.

### Frontend data freshness
The dashboard has no staleness indicator except `company.last_verified` shown in company cards. If the nightly pipeline silently fails (error swallowed), the dashboard shows stale data with no visual indication. The only indicator is the Meridian Reader enrichment items which only show today's profiles — their absence is a passive signal but not surfaced as an alert.

---

## Summary: Top Issues by Priority

| # | Severity | File | Issue | Status |
|---|---|---|---|---|
| 1 | **Critical** | `research_intelligence.py` | `assigned_status: "pending"` always written on upsert — resets user workflow status on every pipeline run | ✅ **FIXED** `6d50305` |
| 2 | **Medium** | `research_intelligence.py` | Stage 4 and trigger T4 use wrong field names (`expected_date`/`title` instead of `sort_date`/`label`) — Stage 4 never fully scores, T4 never fires | ✅ **FIXED** `6d50305` |
| 3 | **Medium** | `ct_gov_sync.py` + `company_enrichment.py` | `DrugIdentityResolver` instantiated per drug — full alias table fetched N times per run | ✅ **FIXED** `fa1c12c` + `93e39cd` |
| 4 | **Medium** | `company_enrichment.py` | `step6_deal_intelligence` headline[:50] dedup is too shallow; false positive deal creation likely | ✅ **FIXED** `ba6dfc2` |
| 5 | **Low** | `index.html` | Meridian Reader sort secondary key (date × 0.0001) produces NaN — sort is effectively single-dimension | ✅ **FIXED** `0ae7569` |
| 6 | **Low** | `index.html` | `loadIdentityHealth()` shows `total - resolved` as orphan count — metric is wrong (should be broken FK count) | ✅ **FIXED** `0ae7569` |
| 7 | **Low** | `identity_health_check.py` | Line 165 summary bug — always prints "0 drugs unresolved" | ✅ **FIXED** `299d716` |
| 8 | **Low** | `ct_gov_sync.py` | `--search-only` flag has no effect (never read inside `sync_drug`) | ✅ **FIXED** `4a5250c` |
| 9 | **Low** | workflow | `pip install anthropic requests` unpinned — silent breakage risk | ✅ **FIXED** (needs `workflow` token to deploy — see note below) |
| 10 | **Low** | workflow | Identity health check only runs for `area=all` manual dispatches, not single-area manual runs | ✅ **FIXED** (needs `workflow` token to deploy — see note below) |

**Schema action required:** Run `schema_migration_v7.sql` in the Supabase SQL editor to add `DEFAULT 'pending'` to `research_queue.assigned_status`. Without this, the Bug #1 fix will fail on new row inserts (NOT NULL violation).

**Workflow deploy note (Bugs #9 + #10):** The GitHub token currently has `repo` scope only. Modifying `.github/workflows/` requires `workflow` scope. The fixed `company-enrichment.yml` is ready in the workspace — apply via GitHub web editor or create a new PAT with `workflow` scope and re-run the deploy script. Changes: `pip install -r scripts/requirements.txt` (Bug #9) and a new `[Manual] Identity health check (single area)` step (Bug #10).
