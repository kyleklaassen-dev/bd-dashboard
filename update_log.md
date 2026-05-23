
---
## 2026-05-23 — Canonical Entity Dossier

**`index.html` — Canonical Entity Modal (Phase 4: Trust)**

Every company and drug now opens the same unified intelligence dossier from any tab:

- **Company dossier** — 5 internal tabs: Overview · BD Intel · Pipeline · Catalysts · Activity
  - Overview: Assessment card (purple) + Platform Summary + BD Posture + BD Context (vs Ailux, Key Risk, Why It Matters)
  - BD Intel: Platform Intelligence (facts + inferred direction) + BD Intelligence (transactions + assessment)
  - Pipeline: Drug cards with stage, target, mechanism, drug summary + combo entries
  - Catalysts: Upcoming catalysts calendar
  - Activity: Deals + intel news feed
- **Drug dossier** — 3 internal tabs: Overview · Trials · Molecule (if available)
  - Overview: Drug profile (mechanism, target, cls, route, indication) + Summary + Differentiation Thesis + Competitive Position by area
  - Trials: Clinical trial cards with phase, status, enrollment, primary endpoint, results note
  - Molecule: Molecule intelligence (format, modality, IgG subclass, Fc engineering, epitope, affinity) with inferred/confirmed badges
- **Rich header chips**: Overlap badge (color-coded Direct/Adjacent/Same-Space/Watch) + Coverage score + BD profile pill + Last enriched date — all visible without scrolling
- **Dossier-mode body**: `entity-modal-body.dossier-mode` turns off padding and uses flexbox column so tab nav is fixed and only the panel content scrolls
- **"Appears in" footer**: company areas now fetched from `company_areas` table and shown as clickable area tags
- **Drug names** in Drugs to Know table now open the drug dossier on click (separate from row-expand)
- **Drug names** in all area PI expanded rows already wired to `openDrugEntityModal` — now show the new dossier
- Provenance-ready: header chip row (`entity-modal-hd-chips`) designed to accommodate confidence + source + enrichment-run fields as Phase 4 matures

---
## 2026-05-22 (Session 2) — 4-tier overlap classification + TL1A data audit fixes

**`ailux_positions` table (Supabase):**
- Added `same_space_criteria` + `same_space_examples` columns to schema
- Updated `ibd-tl1a` row with full 4-tier criteria: Direct → Adjacent → Same-Space → Watch
- `same_space_criteria`: approved SOC in IBD via fundamentally different pathway (not active combo target)
- Moved vedolizumab out of same_space_examples (it's Adjacent, listed in adjacent_examples)

**`scripts/company_enrichment.py` — overlap classification improvements:**
- `build_step5_prompt()`: ailux_block now renders Same-Space tier when column exists in DB
- Fallback prompt updated from 3-tier to 4-tier (Direct / Adjacent / Same-Space / Watch) with explicit definitions
- Both `drug_updates.overlap` and `combination_programs.overlap` field descriptions updated to reference 4-tier system

**TL1A drug data fixes (Supabase `drugs` table) — 28 total patches:**
- Overlap corrected from Watch → Direct: afimkibart, duvakitug, LQ080, SPY002, SPY072, SPX-306
- Overlap corrected from Watch → Adjacent: guselkumab, guselkumab+golimumab, risankizumab, mirikizumab, vedolizumab, SPY001, SPY003
- Overlap corrected from Adjacent → Same-Space: ustekinumab (IL-12/23p40, broader subunit, less active combo target)
- Null targets filled from mechanism fields: HXN-1003, HY8931, QX030N, HBM2001, SAB06, PR203, Generate-UC, Cantai-TL1A, ES302, SPX-306 → all `TL1A×IL-23p19`; LBL-053 → `TL1A×IL-12/23p40`; LQ082 → `TL1A×IL-23p19×α4β7`
- LM-302 target fixed: `TL1A` → `CLDN18.2` (oncology ADC, not TL1A-related)
- GB004 fixed: target `TL1A` → `PHD1/HIF-1α`, stage → `Terminated` (Gossamer Bio)

**Final TL1A drug tier breakdown (50 drugs):**
- Direct: 33 (TL1A mAbs and bispecifics)
- Adjacent: 8 (IL-23p19, α4β7 — combination candidates)
- Same-Space: 1 (ustekinumab)
- Watch: 8 (JAK, RIPK1, IL-1, CLDN18.2 ADC, terminated)

---
## 2026-05-22 — Discovery queue error fixes + enrichment hardening

**Data fixes (Supabase discovery_queue):**
- AK104 (Akeso): corrected target `PD-1/TIM-3` → `PD-1/CTLA-4`, stage `Phase 2` → `Approved` (cadonilimab; China approved 2022 for cervical cancer). Root cause: drug disambiguation failure confused AK104 with AK129.
- SHR0302 (Hengrui): corrected target `JAK1/JAK2` → `JAK1-selective` (ivarmacitinib). Root cause: mechanism misidentification conflated with dual JAK1/2 inhibitors.

**`scripts/company_enrichment.py` — prevention layer:**
- Added `VALID_AREA_IDS` set + `_AREA_ID_ALIASES` map (fixes tll1a→tl1a, il4r→il4ra, etc.)
- Added `normalize_area_id()` utility; called at top of `step1_discover_new_entities` — logs warning and aborts if unrecognised area_id
- Added `KNOWN_DRUG_TARGETS` table (AK104/112/129, SHR0302, JAK inhibitors) injected into discovery prompt as authoritative override
- Prompt now includes explicit JAK selectivity classification rules (JAK1-selective vs JAK1/2 dual vs pan-JAK)
- Added post-processing validation loop: if LLM returns a drug in `KNOWN_DRUG_TARGETS`, override target/stage with authoritative values and log the correction

**`index.html` — Discovery Queue UI (previous session):**
- Added ⚡ "Approve ≥80 conf" bulk button: approves all pending items with confidence_score ≥ 80 in one click
- Auto-approve threshold in enrichment script: items with confidence ≥ 90 now write status='approved' directly (skip queue)

---
## 2026-05-22 — Phase 3: Slide-over company card (commit 444007732aac)

**Changes:**
- Replaced centered `entity-modal-overlay` company modal with a right-side slide-over panel (`#co-slideover`, 560px, slides in via CSS `right` transition)
- New `openCompanySlideOver(companyId, companyName, sourceTabId)`: async function that fetches company data (profile, catalysts, deals, intel news, drugs, trials, combos, molecule intel) and renders via `tl1aPI._genericDetailHTML.call(tl1aPI, prog, sbData)` — the exact same rich card as the PI landscape inline expansion
- Area is determined from `sourceTabId` via `TAB_AREA_MAP`; drug area uses `tl1aPI._drugDisplayArea` for TL1A, area itself for other tabs
- Cache reuse: checks `piObj._profileCache[companyId]` before fetching; if cached from inline expansion, renders instantly
- `_openEntityByEl` now calls `openCompanySlideOver` instead of `openEntityModal`
- `closeCoSlideOver()` + Escape key listener (closes both slide-over and drug modal)
- New CSS: `.co-slideover`, `.co-slideover-overlay`, `.co-slideover-hd`, `.co-slideover-title`, `.co-slideover-sub`, `.co-slideover-close`, `.co-slideover-body`

---
## 2026-05-22 — Phase 2: Full entity modals — company all-areas + drug modal (commit fbf51b96e684)

**Changes:**
- `openEntityModal`: now fetches ALL `company_profiles` rows (removed area filter). Each profile rendered with a colored area label pill (TL1A, TSLP, IL-4Rα, etc.) and its Platform/BD Summary text
- Added `trials` fetch to company modal: pulls all trials for all company drug IDs via `IN` query, renders clinical trials table (Drug, Trial, Phase, Indication, PCD, Status)
- Pipeline pills in company modal are now clickable → open drug modal
- New `openDrugModal(drugId, drugName, evt)`: fetches drug record, `drug_areas` (overlap/overlap_rationale/strategic_role), trials. Renders Mechanism, Summary, Competitive Positioning (per area), Clinical Trials table. Footer shows disease area tabs.
- New `_phasePill(phase)` helper: colored inline badges for Phase 1/2/3 in modal tables
- New `_drugModalBodyHTML(drug, areas, trials)`: full drug card renderer
- Shared area/tab color constants (`_AREA_CLS`, `_AREA_LABEL`, `_TAB_CLS`) extracted as module-level consts — no more local `TAB_CLS` object duplication
- `pi-da-name` spans in drug accordion (`_genericDetailHTML`) wired to `openDrugModal` with `event.stopPropagation()` so accordion toggle doesn't also fire

---
## 2026-05-22 — Fix Indication column for non-IBD PI tabs (commit 0b64789)

**Changes:**
- Entity-level Indication column was showing `—` for all non-IBD tabs (TSLP, FcRn, TED, AD, ACE) because `indScope` derivation only checked UC/CD keywords
- Extended `indScope` fallback in `_makeAreaPI._renderTable()`: after UC/CD check fails, abbreviates first program's `indication_short` using a disease abbreviation map (COPD, AD, RA, gMG, TED, SLE, Asthma, CSU, EoE, AA, HS, PN, CRS)
- Extended `_makeAreaPI._loadEntityMeta()`: stores `_firstInd` (first non-null `indication_short` per company) during drug loop; uses same abbreviation map when resolving `indScope` at the end of async fetch
- TL1A tab unaffected (already defaults to `UC+CD` for all IBD programs)

---
## 2026-05-22 — Discovery Queue: BD PRI column + SVS badges; migration v24 applied (commit d64668683b)

**Changes:**
- Migration v24 applied to Supabase: `strategic_value_score INT` added to both `discovery_queue` and `drug_area_scores` (verified via information_schema)
- Discovery Queue table header: REL → BD PRI
- Row rendering: numeric relevance_score replaced with SVS badge (⚡ Critical 9–10 / ↑ High 7–8 / Med 5–6 / Low 1–4) + faint score below
- Row highlight: critical rows (`svs >= 9`) get red tint `#fff7f7`; user intake rows retain amber tint `#fffdf5`
- Default sort already set to "BD Priority ↓" (strategic_value_score DESC → relevance DESC → newest)
- Stats counters already using SVS for Critical/High/Medium/Low badge tallies

---
## 2026-05-22 — strategic_value_score: compute_strategic_value_score() in drug_intake.py (commits 98b3cd0de65b, 81951c65eab0)

**What it is:** Third enrichment metric alongside coverage_score and evidence_tier. Answers "how much should Kyle care?" from a BD perspective. Orthogonal to coverage — a 40%-coverage Direct competitor in a core area can outscore a 95%-coverage Watch drug.

**Scoring model (0-10):**
- Overlap × Area Primacy: 0–4 (Direct in tl1a/tslp/il4ra core = 4; Watch = 0.5)
- Stage Maturity: 0–2 (Phase 3/Approved = 2; Discovery = 0)
- Catalyst Proximity: 0–1.5 (catalyst within 90 days = 1.5)
- Evidence Confidence: 0–1 (Confirmed = 1; Hypothesis = 0.1)
- Deal Activity: 0–0.75 (has deals = 0.75)
- Company Importance: 0–0.5 (major pharma = 0.5)

**Calibration (validated):**
- Tulisokibart (Direct TL1A, Phase 3, catalyst, J&J, deals, Confirmed): 10/10
- Tozorakimab (Direct TSLP, Phase 3, catalyst, AZ, deals, Confirmed): 10/10
- Amlitelimab (Direct IL-4Rα, Phase 3, Sanofi, no fetched data): 8/10
- QX031N (Adjacent IL-4Rα, Preclinical, small company): 4/10

**Persisted in:** `discovery_queue.strategic_value_score` (review prioritization) + `drug_area_scores.strategic_value_score` (dashboard prioritization, via migration v24).

**Migration v24 SQL** (apply in Supabase SQL Editor):
```sql
ALTER TABLE discovery_queue ADD COLUMN IF NOT EXISTS strategic_value_score INT DEFAULT NULL;
ALTER TABLE drug_area_scores ADD COLUMN IF NOT EXISTS strategic_value_score INT DEFAULT NULL;
```

---
## 2026-05-22 — drug_intake.py: evidence_tier + combo component validator (commit 4b53fb464bd2)

**Evidence tier** (`compute_evidence_tier`): all drugs route through the same pipeline, but the reviewer now sees explicit confidence:
- `Confirmed` — named molecule + company + clinical stage (Phase 1–Approved), high data quality
- `Likely` — named molecule + company + preclinical/IND-enabling, or medium quality clinical
- `Emerging` — low data quality or Discovery/Undisclosed stage; manual verification required before promotion
- `Hypothesis` — no named molecule or no company anchor; stays as signal, no production row without manual approval

**Combo component validator** (`check_combo_components`): when a combination drug is area-linked, each component is checked for `drug_areas` and `drug_area_scores`. Missing links surface as warnings in Output A. Triggered this work: `guselkumab-golimumab` was in `drug_areas.tl1a` but `golimumab` mono was not.

**Golimumab mono patched** (Supabase, no deploy): added `drug_areas` (tl1a, ibd) and `drug_area_scores` (Same-Space, TNF inhibitor) with rationale. J&J now shows: golimumab · ustekinumab · guselkumab · guselkumab-golimumab in both TL1A and IBD tabs.

**Architecture rule captured**: if combo drug is in an area, check each component for existence, drug_areas, drug_area_scores, DKN visibility, molecule_intelligence.

---
## 2026-05-22 — Fix P0: entity_id/company_id split — ticker + profile identity for co-developed drugs (commit 39e021e6e98b)

**Root cause:** Co-developed drugs (e.g. tezepelumab) have `entity_id='astrazeneca'` (display entity) but `company_id='amgen'` (commercialization partner). Two rendering paths used `company_id` instead of `entity_id`, causing Amgen's intelligence data (rocatinlimab, MariTide, Horizon acquisition) and AMGN ticker to appear under the AstraZeneca profile.

**Three fixes applied to index.html:**
1. Added `companies` table as 4th parallel fetch in `_makeAreaPI.init()` — full company lookup by id
2. Built `companiesMap` from the fetch result; updated ticker assignment to `companiesMap.get(d.entity_id || d.company_id)?.ticker` — resolves via display entity first
3. `_loadDynamicDetail`: changed `const companyId = ent.company_id || entityId` → `const companyId = entityId` — profile queries now always use the display entity, never the partner company

**Architecture rule reinforced:** `entity_id` = who to display; `company_id` = commercialization/partnership structure. All profile, ticker, and catalyst lookups must use `entity_id`.

---
## 2026-05-22 — Build drug_intake.py — Drug-First Entity Graph Entry Point (commits b4f500f63ed3, 13e3e4f525ce)

**What was built:**
- `scripts/drug_intake.py` — 5-step drug intake pipeline: identity resolution → graph state fetch → Sonnet research → area scoring → coverage score + queue write
- `migrations/schema_migration_v23_drug_intake_queue.sql` — adds `coverage_score` INT, `completeness_gaps` JSONB, `promotion_payload` JSONB to `discovery_queue`

**Two outputs per run:**
- Output A: Routing Decision (areas + overlap tiers per drug)
- Output B: Completeness Audit (8-dimension coverage score: identity/company/target/trials/catalysts/MI/conference/deals)

**Coverage scoring:** 0/50/100 per dimension → numeric % that makes completeness prioritization objective

**Model-tier guard:** Haiku blocked for live writes (same rule as company_intake.py) — Sonnet required

**Validated:** Tozorakimab dry-run: identity 100% · 11 trials · 24 catalysts · MI exists · 87% coverage · Conference Intel correctly flagged as only gap

---
## 2026-05-22 — company_intake.py: model-tier guard + max_tokens fix (commits f7201eaeaae4, 42408034158d)

- `max_tokens` 4096 → 8192: prevents JSON truncation on large-pipeline companies (Akeso 8 drugs, Hengrui 10 drugs)
- Haiku blocked for live writes in `run_intake()`: clear error message + early exit if INTAKE_MODEL=haiku and --dry-run not set
- Root cause: Haiku fabricated Zenas BioPharma's pipeline (invented "ZEN3694" as TL1A inhibitor; Sonnet correctly found obexelimab/FcRn Direct 92%)

---
## 2026-05-22 — Fix _makeAreaPI: prefer drug_area_scores per-area overlap (commit c11cafc53356)

**Root cause fixed:** `_makeAreaPI` was reading `drugs.overlap` (global field) instead of `drug_area_scores.overlap` (area-specific competitive classification). The `drug_area_scores` table existed and was populated correctly but was orphaned from the rendering pipeline.

**What changed:**
- Added third fetch to `init()` Promise.all: `drug_area_scores(drug_id,area_id,overlap,cls,overlap_rationale,vs_ailux_positioning)` for current `areaIds`
- Built `areaScoreMap` keyed by `drug_id` (best tier per drug when tab spans multiple areas)
- Drug data mapping now prefers: `score.overlap`, `score.cls`, `score.overlap_rationale`, `score.vs_ailux_positioning`; falls back to `drugs.*` globals when no area score exists

**Design principle enforced:**
- `drugs` = global molecule facts
- `drug_area_scores` = area-specific competitive interpretation
- `_makeAreaPI` now renders area-specific overlap when available

**Validation:** tozorakimab Watch→Direct in TSLP tab ✓ · tezepelumab/astegolimab/itepekimab Watch in both sources (consistent, correct) · IL-4Rα/FcRn/IGF-1R/T-cell tabs: zero regressions ✓

---
## 2026-05-22 — Fix DKN false "Removed" alerts (commit 8127f10c7f2b)

**Root cause:** DKN query was filtering on `data_source='catalog'` but 13 drugs had `catalog_category` populated with `data_source='press_release'`/`'conference'`. They were in the localStorage snapshot but excluded from the live query → false "Removed" badges on every load.

**Fix:** Changed DKN Supabase query from `.eq('data_source','catalog')` to `.not('catalog_category','is',null)`. `catalog_category` is the correct intent signal for catalog membership; `data_source` is provenance only.

**Affected drugs now restored:** Imaavy (nipocalimab), Rystiggo (rozanolixizumab), Ebglyss (lebrikizumab), Tepezza (teprotumumab), Tezepelumab, Itepekimab, Astegolimab, Tulisokibart, APG279, QX031N, XmAb942, Sim0709, XmAb412

**DKN drug count:** 87 → 100

---
## 2026-05-22 — Tozorakimab data fix (Supabase patch, no deploy)

**Root cause of TSLP tab gap:** `drugs.overlap='Watch'` for tozorakimab while `drug_area_scores.overlap='Direct'` for tslp — `_makeAreaPI` reads `drugs.overlap` globally, not per-area scores. Also `drugs.target=null`.

**Fix:** PATCH `drugs SET target='IL-33 (anti-ST2)', overlap='Direct' WHERE id='tozorakimab'`

---
## 2026-05-22 — Company Intake (Add Company of Interest) — Phase 1 (commits 8ba83e13f066 + scripts)

**New: `company_intake.py` CLI script**
- `python scripts/company_intake.py --company "Akeso"` — research a company and route it to discovery_queue
- Full workflow: identity resolution → open-ended Claude research → area scoring → queue write
- Respects minimum evidence threshold (confidence ≥ 0.5), 30-day dedup, never auto-promotes
- Flags: `--dry-run`, `--verbose`, `--force` (for existing companies or fuzzy conflict override)

**Extended `CompanyIdentityResolver`**
- New `resolve_with_detail()` method: returns structured dict with `resolution_type`
- Types: `resolved_existing` | `alias_match` | `candidate_new` | `unresolved`
- Backward-compatible: `resolve()` unchanged

**New: `migrations/schema_migration_v22_discovery_source.sql`**
- Adds `source TEXT DEFAULT 'signal_monitoring'` column to `discovery_queue`
- Run in Supabase Dashboard: https://supabase.com/dashboard/project/tghntyofptvfhmtchwcv/sql/new

**Discovery Queue UI updates (commit 8ba83e13)**
- Source badge: "🔍 User Intake" (amber) or "📡 Signal Monitor" (blue) per row
- Intake row intelligence cell: shows overlap tier + rationale + why_discovered context box (amber left-border)
- Source filter dropdown: filter queue by All Sources / User Intake / Signal Monitor
- Intake rows: subtle amber `#fffdf5` row background to distinguish from signal rows

---
## 2026-05-22 — J&J added to TL1A entity table (commit faec7a265db4)

**TL1A Program Intelligence — J&J now present (17 companies):**
- Root cause discovered: TL1A tab uses a static `TL1A_PROGRAMS` JS array (not `_makeAreaPI`), so Supabase `drug_areas` inserts alone had no effect
- Added three `groupId:'jnj'` entries: Tremfya/guselkumab (Adjacent, IL-23p19 Approved CD+UC), guselkumab-golimumab combo (Adjacent, Phase 3 UC), Stelara/ustekinumab (Same-Space, IL-12/23 Approved CD+UC)
- Added `company_areas` row for jnj/tl1a (Market & Learning card filter)
- Supabase `drug_areas` + `drug_area_scores` entries for guselkumab/ustekinumab retained (serve other area tabs via `_makeAreaPI`)

---
## 2026-05-22 — Signals Panel (commit 8edacaad)

**Home Tab — Signals Panel (5th launcher):**
- Added 📡 Signals launcher button to home tab grid (purple `#5b21b6`)
- Panel loads from `signals` Supabase table — last 7 days, sorted by `relevance_score DESC`
- Includes company name (via `companies(name)` join), signal type pill, headline with source URL link, source name + event date
- Relevance score badge: ≥8 = purple/high, 6–7 = blue/notable, ≤5 = gray/watch
- Area filter bar (All / TL1A / TSLP / IL-4Rα / FcRn / IGF1R / T-cell) + ↻ force-refresh
- Items grouped by Today / This Week / Earlier
- Loaded at DOMContentLoaded (cached; force-reload on ↻ button)
- `HOME_PANEL_META` updated; CSS classes: `.sig-item`, `.sig-score`, `.sig-type`, `.sig-group-hd`

---
## 2026-05-21 — Company Database Phase 1 + Tiered Enrichment Architecture (commit 3af406730150)

**Company Database — Slide-over Profile Panel:**
- Added right-side slide-over panel for BD company profiles, opening from Pharma Landscape rows
- "⎘ Profile" button injected into PI table rows for all companies in PI_SLUG_TO_ID map (~33 companies)
- Panel header: company name, ticker, mkt cap/revenue/R&D (read from DOM), area pills, Ailux Angle
- Overview tab: molecules table with stage/overlap badges, upcoming catalysts, deals, BD assessment summary
- Per-area tabs (one per company_profiles row): completeness score bar, missing fields, platform intel JSONB, BD intel JSONB
- URL-addressable hash routing: `#/company/{id}` — persists on reload, browser back button closes panel
- Supabase queries fetched in parallel on panel open; financials from existing DOM (no extra API call)

**Tiered Enrichment Architecture:**
- New doc: `docs/tiered_enrichment_architecture.md`
- 4-tier design: Tier 1 (4hr signal monitoring, no LLM), Tier 2 (daily enrichment — current pipeline), Tier 3 (weekly strategic reassessment), Tier 4 (quarterly reference refresh)
- Specifies `signals` + `enrichment_queue` tables, signal relevance scoring algorithm, dedup strategy, alerting criteria
- Maps all 5 existing workflows to their tiers; flags `meridian-research.yml` + `evening-update.yml` as potentially duplicative

---
## 2026-05-21 Phase 4: UI cleanup — ticker inline, co-dev partner pill, drug name normalization (commit 8ce4c7f)

**Changes:**
- Ticker moved inline with company name (same line, lighter weight) — no more separate row below company name
- Removed dual-ticker display (`SNY/TEVA` → `SNY`; `Private/BI` → `Private`) — only lead entity ticker shown
- Partner pill label updated from `"w/ X"` to `"co-dev w/ X"` to match Spyre standard
- Static drug name cleanup across TL1A_PROGRAMS: stripped Fc-engineering suffixes (e.g., "(Xtend-Fc)"), enforced brand-first format for approved drugs, removed redundant coded suffixes
- `partnerCo` shorthands: Telavant (Roivant) → Telavant; Boehringer Ingelheim → BI; Qyuns Therapeutics → Qyuns

---
## 2026-05-21 Critical fix: MONTHS + fmtExactDate TDZ hoisting bug in _genericDetailHTML (commit dc6e5e0)

**Root cause**: `_genericDetailHTML` defined `MONTHS` and `fmtExactDate` at line ~10162, but both were called at lines ~9758/9851 inside `fmtPcd` and `renderNewsItem` — hundreds of lines before their declarations executed. JavaScript `const` is NOT hoisted (temporal dead zone), so every call to `_loadDynamicDetail` crashed inside `_genericDetailHTML`, the catch block fired, and the function fell back to fully static data. This is why drug names showed "Risankizumab" (not Skyrizi), stages showed Phase 3 (not Approved), no combo row, and no "formerly FG-M701" note — despite the Supabase queries returning correct data.

**Diagnosed via**: Chrome DevTools console log showed `ReferenceError: Cannot access 'MONTHS' before initialization` in `fmtPcd ← Array.map ← _genericDetailHTML ← _loadDynamicDetail`. Confirmed by inspecting `tl1aPI._profileCache['abbvie'] === null` (failed load).

**Fix (`index.html`, commit dc6e5e0):**
- Moved `const MONTHS` and `const fmtExactDate` to immediately before `const fmtPcd` (now declared in the correct execution order)
- Removed the duplicate declarations at old location, replaced with a comment noting the move

**Verified in browser (all pass):**
- ABBV-701 in accordion header (not FG-M701) ✓
- Skyrizi (risankizumab) / Rinvoq (upadacitinib) both Approved ✓
- ABBV-701 + Skyrizi combo row with Planned Ph2b ✓
- "formerly FG-M701 · acquired from FutureGen…" in expanded ABBV-701 detail ✓
- `tl1aPI._profileCache['abbvie']` → 3 drugs, profile loaded, not null ✓

---
## 2026-05-21 Acquired drug naming — show current name only, formerly-known-as in detail (commit d1054f6)

**Rule**: When a drug is acquired/licensed and renamed by the acquirer, the dashboard shows ONLY the current/acquirer name. The original name is surfaced contextually in the expanded detail view, not in the accordion header.

**Supabase DB updates:**
- `drugs.fg-m701`: `display_name` → `'ABBV-701'` (was `'ABBV-701 (FG-M701)'`)
- `canonical_drugs.CANON_DRUG_D7BA258E`: `canonical_name` → `'ABBV-701'`

**`index.html` (commit d1054f6):**
- Added `acquisitionNote` block in `_genericDetailHTML`: when `licensor_code` is set and differs from `display_name`, a small pill renders at the top of the drug detail body: `formerly FG-M701 · acquired from FutureGen Biopharmaceutical Co., Ltd.`. Appears PI dashboard-wide for any acquired drug.
- Applies automatically to any future drug where `licensor_code` is populated.

**`company_enrichment.py` (commit 8d985c9):**
- **DISPLAY NAME GUIDANCE** rewritten: `display_name` = acquirer's name ONLY (e.g. `"ABBV-701"`, NOT `"ABBV-701 (FG-M701)"`). Old name belongs in `licensor_code` + `licensor_name`.
- **Post-write guard** extended: now also warns if `display_name` still contains the old `licensor_code` in parentheses (catches previously-written stale entries).

---
## 2026-05-21 Critical fix: renderNewsItem hoisting bug + approved drug profile redesign (commit f913584)

**Root cause of three simultaneous regressions (combo disappeared, approved drugs showed "Phase 3", catalysts/news truncated):**
- `const renderNewsItem` was defined at ~line 10169 inside `_genericDetailHTML`, but called at ~line 10045 inside the `allItemsHTML.map()` callback for drug-level news.
- JS `const` is NOT hoisted — when any drug had news items with a matching `canonical_drug_id`, it threw `ReferenceError: Cannot access 'renderNewsItem' before initialization`.
- The `try/catch` in `_loadDynamicDetail` caught this and called `_genericDetailHTML(prog, null)`, discarding all DB data (`sbCombos=[]`, real drug stages gone, catalyst/news count reset to static fallback).

**`index.html` fixes (commit f913584):**
- **renderNewsItem hoisting fix**: Moved `typeMap` and `renderNewsItem` to just before `const allItemsHTML = allItems.map(...)` (line 9834 → now 9836). One canonical definition, always in scope.
- **Approved drug profile redesign**: Replaced monochrome green block with distinct colored section cards:
  - 3-column stat bar: Approval Date (blue left-border), Annual Revenue (green), Patients on Therapy (purple)
  - Pivotal Endpoints card (amber/yellow background)
  - Summary card (white/neutral)
  - Mechanism & Context card (light blue)
  - Differentiation card (light purple)
  - Each section has an uppercase label + body with independent color scheme for scannability
- **Stage column**: Fixed from `auto` to `104px` so stage pills always start at the same x-position regardless of pill text width
- All changes apply via `_genericDetailHTML` — PI dashboard-wide

---
## 2026-05-21 Fix: FG-M701 acquired-drug naming + Phase 1 trial insertion (enrichment 7ee85b3)

**Root causes found and fixed:**
- `fg-m701` had `display_name: "FG-M701"` — licensor fields were populated but acquirer code was never written. Drug `stage` was incorrectly "Phase 2" (that's the planned combo; the monotherapy is Phase 1).
- No trials existed in DB for AbbVie / fg-m701 — ct_gov_sync had never run for this entity.

**Supabase data fixes:**
- `drugs.fg-m701`: `display_name` → "ABBV-701 (FG-M701)", `stage` → "Phase 1"
- `canonical_drugs.CANON_DRUG_D7BA258E`: `canonical_name` → "ABBV-701 (FG-M701)"
- Trial inserted: NCT06895343 — Phase 1 SAD/MAD safety/PK study in healthy volunteers, AbbVie sponsor, Active Not Recruiting, PCD Nov 2026. `drug_id=fg-m701`, `canonical_drug_id=CANON_DRUG_D7BA258E`, `entity_id=abbvie`.

**`company_enrichment.py` (commit 7ee85b3):**
- **Display name guidance rewritten** as CRITICAL rule: acquired/licensed drugs must ALWAYS have `display_name` set to "AcquirerCode (OriginalCode)" — never null or equal to drug_id when a licensor exists.
- **Post-write guard added**: after patching each drug, if `licensor_code` is written but `display_name` is null or equals drug_id, script logs a hard `⚠ DATA QUALITY` warning visible in CI/GitHub Actions logs — catches the failure class before it reaches the dashboard.

---
## 2026-05-21 Fix: Drug accordion — dedicated stage column, indication wrapping fix (commit 0257662)

**`index.html`:**
- **Stage pill gets its own grid column**: `.pi-da-hd` grid changed from `11px minmax(0,200px) 100px 1fr` (4 cols) to `11px minmax(0,200px) 100px auto 1fr` (5 cols). The new `auto` column holds only the stage pill — it sizes to the widest pill across all rows (e.g. "Planned Ph2b") and is consistent for every drug row.
- **New `.pi-da-stage` wrapper**: Stage pill extracted from `pi-da-pills` flex container into its own `.pi-da-stage` grid cell for both regular drug rows and combo rows. Now indication tags can wrap freely in the `1fr` column without ever displacing the stage pill.
- **Indication tags left-aligned**: `.pi-da-pills` changed to `justify-content:flex-start` and `align-items:flex-start` — tags flow left and wrap naturally without pushing stage out of column.
- **Applies to all companies**: Logic is in `_genericDetailHTML`, the single shared renderer for all expanded rows across the entire PI dashboard.

---
## 2026-05-21 Fix: Combo row cleanup — name, + pill, source link, column alignment (commit 3cbf8b3)

**`index.html`:**
- **Name stripped of targets**: Combo header now shows only drug names (e.g. "FG-M701 + Skyrizi") — parenthetical target info stripped from display name via regex. Target column still shows the mechanism (e.g. "TL1A + IL-23p19").
- **Target cleaned**: Trailing " combo" word stripped from extracted target so the mech column shows "TL1A + IL-23p19" not "TL1A + IL-23p19 combo".
- **`[+]` pill removed**: The `+` badge has been removed from the combo header pill row — it was redundant given the name already uses `+`.
- **Source link moved to body**: `srcLink` removed from the header row entirely. Source now appears inside the accordion body as "BACKBONE ADDON · Source ↗" label, keeping the header clean.
- **Column alignment**: All drug rows (combo and regular) share the same `.pi-da-hd` grid — no structural difference, so names, targets, and pills all align in columns across the full list.

**Supabase `drug_combinations`:**
- Label cleaned: "FG-M701 + Skyrizi (TL1A + IL-23p19 combo)" → "FG-M701 + Skyrizi (TL1A + IL-23p19)"

---
## 2026-05-21 Feat: Planned combo accuracy — source link, prerequisite, anticipated start (commit a010a0d)

**Schema (`drug_combinations`):**
- Added `prerequisite_note TEXT` — what must happen before the study can begin (e.g. "Awaiting Phase 1 monotherapy completion")
- Added `anticipated_start TEXT` — company-guided start timing (e.g. "H2 2026")

**Supabase data — AbbVie combo:**
- `prerequisite_note`: "Awaiting FG-M701 Phase 1 monotherapy completion — data not yet reported"
- `anticipated_start`: "H2 2026"

**`index.html` — planned combo trial section:**
- Source link: planned combos now show a clickable "Source ↗" link (required field per enrichment rules); missing source renders as orange "⚠ No source" warning instead
- Anticipated start: shown inline as "· Anticipated: H2 2026"
- Prerequisite note: shown below as amber callout "⚠ Prerequisite: ..." when `prerequisite_note` is set

**`company_enrichment.py`:**
- Prompt schema for `combination_programs` updated: `stage` now accepts `Planned Ph1/Ph2/Ph2b` values; `anticipated_start`, `prerequisite_note`, and `source_url` all marked REQUIRED for planned studies
- Write path: `anticipated_start` and `prerequisite_note` now written to DB on every combo upsert/patch
- Logs a data quality warning if a planned combo has no `source_url`

---
## 2026-05-21 Fix: Planned Ph2b stage — dashed pill + accurate no-trials message (commit d268cb5)

**`index.html`:**
- **New `pi-stage-planned` CSS**: light blue dashed-border pill (`background:#f0f9ff;color:#0369a1;border:1px dashed #7dd3fc`) visually distinguishes planned/future studies from active phase pills.
- **Both `_stagePill` methods updated**: `"Planned Ph2b"`, `"Planned Ph1"`, `"Planned Phase 2"`, `"Planned Phase 1"` all map to `pi-stage-planned`. Any string starting with "Planned" also falls to the planned style as a catch-all.
- **Combo trial section contextual message**: combos with a "Planned" stage and no linked trials now show "Study planned — no trial registration yet" (in blue italic) instead of the generic "No trials linked yet" in gray.

**Supabase `drug_combinations`:**
- AbbVie FG-M701 + Skyrizi combo `stage` updated from `"Phase 2"` → `"Planned Ph2b"` (accurate — study disclosed but not yet initiated; anticipated H2 2026 per AbbVie investor comms).

---
## 2026-05-20 Fix: Drug names, combo targets, +N more count, display_name (commit be6e549)

**`index.html`:**
- **Drug name column widened, no truncation**: `.pi-da-hd` grid changed to `minmax(0,200px)` for the name column. `.pi-da-name` and `.pi-da-mech` now use `word-break:break-word` with no `white-space:nowrap`/`text-overflow` — full drug names always visible.
- **Combo target column fixed**: Combo rows now extract the mechanism from the label parenthetical (e.g. "FG-M701 + Skyrizi (TL1A × IL-23p19)" → "TL1A × IL-23p19") via regex instead of showing the indication there.
- **TL1A static table "+N more" corrected**: `_renderTable` for TL1A was still using `ge.length-1` (off by one). Changed to `ge.length` so AbbVie's "+2 more" and similar counts are accurate.
- **`display_name` used in drug accordion**: Drug name column now prefers `d.display_name` from DB over `d.name` — picks up AbbVie-assigned names once enrichment populates that field.

---
## 2026-05-20 Feat: Drug pipeline UX overhaul (commit dd0a30c)

**`index.html`:**
- **Drug accordion grid alignment**: `.pi-da-hd` changed from `display:flex` to `display:grid` with fixed columns (`11px | 140px | 110px | 1fr`). Drug name and target now align in consistent columns across all rows. Pills grouped into `.pi-da-pills` wrapper (flex, right-aligned) for stage pill + indication tag + overlap badge.
- **Combination rows normalized**: Combo accordion rows now look identical to drug rows — normal name color (no purple), indication shown in target column, small `+` badge in pills area, `+` sign is the only combo indicator. Verbose type label (e.g. "backbone + add-on") removed. Full accordion body with drug summary, intel panel, and linked clinical trials.
- **Drugs + combos sorted by relevance**: Drugs and combos merged into one unified list sorted by competitive overlap score (direct=100, adjacent=70, same-space=40, watch=20). Highest-relevance drugs appear first.
- **Direct competitor highlight**: Rows with `overlap='direct'` get a subtle orange left border (`3px solid #f97316`) to stand out visually.
- **Trial chevron moved to left**: Chevron `▼` is now the first column of every trial row (before the NCT number). Trial grid updated: `14px 88px 100px 140px 48px 70px 36px` (chev | NCT | acr | status | phase | PCD | relevance). Tighter right-side columns give more room for the drug intel panel.
- **"+N more" drug count**: PI table drug column now shows first drug name + `+N more` label for companies with multiple drugs (e.g., "+2 more"), instead of showing all drug names inline.
- **firstSentence hoisted**: Moved out of the per-drug map loop so it's accessible to both drug and combo rendering branches.

---
## 2026-05-20 Fix: AbbVie trials fallback + Meridian srcdoc/src conflict (commit b6f0ed8)

**`index.html`:**
- **AbbVie clinical trials restored**: Removed `!sbDrugs.length` guard from `allTrials` fallback — static `prog.trials` is now always used when `sbTrials` is empty, even if DB drugs exist for the company. Previously, AbbVie's enrichment (which created risankizumab/upadacitinib in the DB) caused the static FG-M701 Phase 1 trial to be silently suppressed.
- **`drugTrials` assignment updated**: When `sbTrials` is empty (static fallback in use), `__all__` keyed trials are now assigned to the first drug in `drugsToRender` (not just when there's a single drug). Prevents cross-row spillage while ensuring the static trial always renders.
- **Meridian iframe srcdoc/src conflict fixed**: When the iframe has an existing `srcdoc` attribute, browsers prioritize it over a JS-set `frame.src`. All four live-load paths now call `frame.removeAttribute('srcdoc'); frame.srcdoc = '';` before setting `frame.src`, ensuring today's live issue actually loads.

---
## 2026-05-20 Feat: hyperlinks required, hover tooltips, 5-item scroll threshold, 1-line items (commit ba333cc)

**`index.html`:**
- **Hyperlinks enforced**: Upcoming Catalysts and Related News now filter to only items with a verified `source_url` or `url`. Items without a link are hidden — every visible item is clickable.
- **Hover tooltips**: Hovering any catalyst or news item shows a brief summary via the native `title` attribute — `c.notes`/`c.label` for catalysts, `d.body`/`d.headline` for news. No click required.
- **Scroll threshold raised to 5**: Both Upcoming Catalysts and Related News show 5 items before scrolling (was 3). Drug-level Related News inside drug accordions also raised to 5.
- **1-line per item**: Catalyst label spans now get `white-space:nowrap;overflow:hidden;text-overflow:ellipsis` via flex layout — long event names truncate cleanly with `…` rather than wrapping.
- **Company-level news now single-line**: `renderNewsItem` called with `singleLine=true` in the company detail Related News section for consistency with drug-level news.
- **CSS**: `.pi-detail-cat-item` updated to `align-items:center;overflow:hidden` so all items in both catalysts and news sections are visually consistent.
- Applied across entire drug PI dashboard (both company-level and drug-level sections of `_genericDetailHTML`).

---
## 2026-05-21 Fix: clinical trial rows aligned with CSS grid (commit 32e73b9)

**`index.html`:**
- `.pi-tr-row` switched from `display:flex` to `display:grid` with fixed column widths: `92px 118px 1fr 58px 68px 16px` (NCT · Acronym · Status · Phase · Date · Chevron). All rows now align in straight columns regardless of content length.
- Acronym cell always rendered as `.pi-tr-acronym-cell` wrapper (even when empty) so grid column count stays constant across rows.
- `.pi-tr-acronym` updated: removed `flex-shrink:0`, added `overflow:hidden;text-overflow:ellipsis` so long acronyms don't overflow their column.

---
## 2026-05-21 Feat: enrichment now persists found news to intel table (commit db6819a)

### What changed

**`scripts/company_enrichment.py`:**
- Added `news_items[]` to the Claude enrichment prompt output schema. Claude now extracts 3-6 significant recent news items found during web research (readouts, deals, approvals, financings) and returns them with `intel_date`, `headline`, `body`, `source_url`, `source_name`, `importance`, `intel_type`.
- `write_step5()` now writes those items to the `intel` table and creates `intel_companies` junction rows. Deduplication by `source_url` — existing articles are skipped.
- This means the "Related News" section in the dashboard self-populates every time enrichment runs for a company, with no separate Meridian pipeline required.
- Items without a verified `source_url` are skipped (no fabricated articles).

### Before
- Enrichment found news articles during web research but discarded them — the intel/intel_companies tables were only populated by the separate Meridian research pipeline, meaning most companies had no Related News.

### Now
- Every enrichment run for any company automatically discovers and persists 3-6 news items. Runs for AbbVie will populate Skyrizi approval, Rinvoq data, FG-M701 deal, etc.

---
## 2026-05-21 Fix: drug_summary missing column + sb_patch error logging (commit dbb0e45)

### Root cause
Every drug PATCH during enrichment was silently failing. The `drugs` table was missing the `drug_summary` column, so PostgREST returned HTTP 400 (code 42703) for every drug update. The old `sb_patch` treated only status 200/204 as success and logged `✗` but swallowed the actual error message — making it invisible in logs.

### What changed

**Schema (applied directly to Supabase — v13 migration):**
- `drugs` table: added `drug_summary TEXT` column (was missing; blocked all drug PATCHes)

**`scripts/company_enrichment.py`:**
- `sb_patch()`: now logs full HTTP status + response body when status is not 200/204. Also detects 0-row matches (200 + empty `[]` body with `return=representation` header) and logs a WARNING.
- `write_step5()`: pre-validates every drug_id Claude returns against the actual DB drug IDs for that company. Logs a WARNING with the valid ID list if Claude returns an unknown ID, preventing silent no-ops.
- Drug log line now includes a preview of `drug_summary` so success is visually verifiable in logs.

### Next step
Re-run AbbVie enrichment (GitHub Actions → `area=tl1a`, `company=abbvie`). All three drugs (fg-m701, risankizumab, upadacitinib) should now populate drug_summary, key_data, strategic_role, approval_date, annual_revenue, patient_population, final_endpoints.

---
## 2026-05-21 Strategic intelligence layer — roles, combos, display names (commit 047ea46)

### What changed

**Schema (applied directly to Supabase):**
- `drugs` table: added `strategic_role`, `display_name`, `licensor_name`, `licensor_code`, `is_combination`, `combination_label`
- New `drug_combinations` table: models multi-drug combination programs with `label`, `component_drug_ids[]`, `combination_type`, `stage`, `strategic_significance`, `mechanism_detail`, `drug_summary`, `source_url`. RLS: anon SELECT.

**`scripts/company_enrichment.py`:**
- Enrichment prompt now asks Claude to classify every drug with a `strategic_role` (direct_competitor · franchise_anchor · combination_asset · same_space_defense · platform_expansion · watch)
- `display_name` populated when company uses a different code (e.g. "ABBV-701 (FG-M701)") or brand+INN format
- `licensor_name` / `licensor_code` populated for in-licensed assets
- New `combination_programs[]` section in Claude response — identifies all known multi-drug combos
- `write_step5()` now writes combination programs to `drug_combinations` table (patch-or-insert by company+label)

**`index.html`:**
- Drug pills show a color-coded strategic role badge at the bottom (DIRECT/ANCHOR/COMBO↗/DEFENSE/EXPAND/WATCH)
- Drug names use `display_name` when enrichment has set it
- Popup header shows role badge + licensor info ("🔗 Licensed from FutureGen (orig. FG-M701)")
- `_makeComboBtn()`: combination programs render as dashed-purple pills in the pipeline row, with their own popup showing mechanism, drug_summary, stage, significance, and source link
- `_buildDrugPipelineRow()` now accepts `combos` and appends them after standalone drugs with a "⊕ Combination Programs" divider
- `_genericDetailHTML` accordion also shows combo rows in the Drug Pipeline section
- `_loadDynamicDetail` fetches `drug_combinations` from Supabase and passes them through

### Next step
Re-run AbbVie enrichment (GitHub Actions → `area=tl1a`, `company=abbvie`) to populate all new fields. Every future enrichment run for any company will auto-populate strategic roles and combination programs.

---
## 2026-05-21 v12: Indication group completeness — full platform hardening (commit 0c12155)

### Root cause (full analysis)
The TL1A company tab uses `area_id='ibd'` (the indication_group) to fetch both eligible companies and the drug list. This is intentional: the TL1A tab shows ALL IBD-mechanism drugs (IL-23 inhibitors, JAK inhibitors, integrin antibodies), not just TL1A-specific ones. But the enrichment script and trial sync script both fetched drugs using only the specific `area_id='tl1a'`, missing the broader `ibd`-tagged set.

### Code changes (deployed commit 0c12155)
- **`scripts/ct_gov_sync.py`**: Mirrored the same `fetch_areas = [area_id, indication_group]` IN-query fix applied to `company_enrichment.py` in commit `00e2147`. Trial sync now covers all drugs the dashboard displays, including approved IBD drugs tagged `ibd`.

### Database migration (apply manually via Supabase SQL editor)
**File: `migrations/schema_migration_v12_indication_group_sync.sql`**

Three parts:
1. **Add grouping rows to `disease_areas`**: Inserts `respiratory`, `atopy`, `ted`, `autoimmune` as hidden grouping rows (sort_order 11-14). These mirror the `ibd` row that already exists. They satisfy the FK constraint so `drug_areas` can be tagged with these area_ids.
2. **Backfill `drug_areas`**: Inserts the 29 missing indication_group tags for existing drugs (TSLP, IL-4Rα, IGF1R, FcRn, T-cell areas). Idempotent via ON CONFLICT DO NOTHING.
3. **DB triggers**: Creates `trg_drug_areas_sync_ig` and `trg_company_areas_sync_ig` — whenever a drug or company is tagged with a specific area, the trigger auto-inserts the indication_group tag. Prevents the gap from ever recurring, including for manually-added entries.

### Audit results (as of May 21)
- `company_areas`: 25 TL1A companies all have `ibd` tag ✓
- `drug_areas`: 29 drugs across 5 areas missing IG tag → fixed by migration SQL
- Trigger makes future inserts self-healing

---
## 2026-05-21 Drug enrichment fix — indication_group drug fetch + mandatory drug_summary (commit 00e2147)

### What changed

**Root cause identified**: `fetch_company_context()` fetched drugs using only the specific `area_id` (e.g. `tl1a`), but the frontend fetches using the `indication_group` (`ibd`). AbbVie's approved drugs `risankizumab` and `upadacitinib` are tagged `ibd` in `drug_areas`, not `tl1a`, so they were invisible to the enrichment pipeline.

**Fix 1 — `scripts/company_enrichment.py` (`fetch_company_context`)**:
- Now fetches drugs using both `area_id` AND `indication_group` (e.g. `tl1a` + `ibd`) to mirror exactly what the dashboard displays
- Uses `in.(tl1a,ibd)` query so approved IBD drugs (Skyrizi, Rinvoq) are included in the Claude enrichment context

**Fix 2 — Enrichment prompt (`build_step5_prompt`)**:
- `drug_summary` changed from "null or 2-3 sentences" to REQUIRED — Claude must always populate this field; never return null
- `key_data` similarly made required for approved/late-stage drugs

**Fix 3 — `index.html`** (`company_profiles` query):
- Profile fetch now uses `.order('updated_at', { ascending: false }).limit(1)` to always get the most recent enrichment row

---
## 2026-05-20 Company card polish — exact dates, drug news, pipeline link removed (Tasks #313–315)

### What changed

**Exact dates everywhere:**
- Added `fmtExactDate()` helper: converts `YYYY-MM-DD` → "May 19, 2026"; passes through already-formatted strings (e.g. "Q3 2026", "April 28, 2028")
- Related News items now show exact date from `deal_date` field instead of `deal_date_label` (month-year only)
- Catalyst dates unchanged — already stored as formatted strings from enrichment prompt

**Catalyst + Related News scroll cap reduced to 5:**
- Scroll trigger was already >5; `max-height` adjusted from 210px → 165px (≈5 items @ ~33px each)
- Count note ("N upcoming · scroll for more") remains above the scroll container

**Drug-specific Related News in accordion:**
- Each drug row in the accordion now has a "📰 Related News" section at the bottom of its expanded body
- Filtered from `sbDeals` by `canonical_drug_id === drug.id` — only news linked to that specific drug
- Shows 3 items visible (78px max-height), scrollable to 10 total
- Single-line layout: date | type badge | title (clickable ↗ link, ellipsis if overflow)
- Populated as the enrichment pipeline links deals to canonical drug IDs via Step 6
- Added `renderNewsItem(d, singleLine)` helper used by both company-level and drug-level news sections

**Full Pipeline link removed:**
- Removed the `Full Pipeline ↗` link from the "Drug Pipeline" section header in every company card

---
## 2026-05-20 Study acronym support — full stack (Task #308)

### What changed

**schema_migration_v10.sql (run in Supabase SQL editor):**
- `trials.study_acronym TEXT` — branded program acronym (e.g. SKYLINE-UC, U-ACHIEVE, PURSUIT)
- `drugs.approval_date TEXT` — regulatory approval date + indication
- `drugs.annual_revenue TEXT` — latest reported annual revenue with year
- `drugs.patient_population TEXT` — estimated patients on therapy globally
- `drugs.final_endpoints TEXT` — pivotal trial primary endpoint results narrative
- Index: `trials_study_acronym_idx` on `trials(study_acronym)`

**scripts/ct_gov_sync.py:**
- `parse_ct_study()` now extracts `id_mod.get("acronym")` as `study_acronym`
- Included in the returned record dict and upserted to Supabase trials table

**scripts/company_enrichment.py:**
- `build_step5_prompt()` now includes `study_acronym` in trials context passed to Claude
- Added `trial_updates` output section to JSON schema: `trial_id` + `study_acronym` per trial
- Added approved drug fields to `drug_updates` schema: `approval_date`, `annual_revenue`, `patient_population`, `final_endpoints`
- Added STUDY ACRONYM GUIDANCE and APPROVED DRUG GUIDANCE to prompt RULES section
- `write_step5()` now handles `trial_updates` — patches `trials` table with `study_acronym`

**index.html — trial row UI:**
- Added `.pi-tr-acronym` CSS class: navy blue pill badge, small caps, blue tint background
- Trial rows now read `t.study_acronym` and render acronym badge between NCT link and status pill
- When present (e.g., SKYLINE, U-ACHIEVE), shows as compact `[ACRONYM]` badge in collapsed row
- Full study name still only appears in expanded detail on click

---
## 2026-05-20 Home tab redesign — 4 launcher buttons + overlay card — index.html: deployed 2a3d52e

### What changed

**Home tab layout (entire tab replaced):**
- Removed stacked full-width cards (Key Catalysts, BD Signal, Deal Activity, Essential Updates)
- Added 4 centered launcher buttons in a horizontal row: 📅 Key Catalysts, ◈ BD Signal, 💼 Deal Activity, ⚡ Essential Updates
- Each button: white card, 190px, accent top border, hover lift animation, accent color highlight on active

**Overlay card:**
- Click any launcher → full-width overlay (92%, max 1180px) appears centered with backdrop blur
- Colored header bar matching launcher accent (blue/navy/green/orange) with panel title + ✕ close
- Scrollable body (max-height 82vh, thin scrollbar)
- Click backdrop or press Escape to dismiss
- All existing IDs preserved: `#home-catalysts-anchor`, `#bd-signal-panel`, `#home-deals-anchor`, `#meridian-reader-anchor`, `#catalysts-list`, `#deals-list`, `#bd-signal-body`, `#meridian-reader-items`
- All existing JS load functions + filters continue working unchanged

**JS:** `openHomePanel(panel)` / `closeHomePanel()` with Escape key listener

---
## 2026-05-20 Fix target display in drug accordion + Drugs to Know — index.html: deployed 7457be5

### What changed

**Drug accordion (`_genericDetailHTML` line ~9397):**
- `const drugTarget = d.mechanism || d.target` → `d.target || d.mechanism`
- Ensures clean notation ("TL1A", "IL-23p19") appears in accordion headers, not verbose mechanism strings

**Drugs to Know table (line ~2661):**
- Was: `(d.mechanism || '').replace(...)` — showed "Anti-TL1A mAb", "Anti-IL-23p19 mAb" etc.
- Now: `const targetDisplay = d.target || d.mechanism` — shows "TL1A", "IL-23p19"

This completes the 3-location target display standardisation (pill, accordion, table all now prefer d.target).

**Supabase data fixes (same session):**
- Deleted ghost `abbvie-tl1a` drug record (stale record with no target, showing "AbbVie TL1A mAb")
- Patched risankizumab: target="IL-23p19", mechanism="Anti-IL-23p19 mAb"
- Patched upadacitinib: mechanism="JAK1 inhibitor (oral small molecule)"
- Patched fg-m701: mechanism="Anti-TL1A mAb"

---
## 2026-05-20 Related News panel + deal discovery broadening — index.html: pending

### What changed

**Root cause of Mirador Series B missing:** Step 6 keyword filter excluded financing/press-release events ("series b", "raises", "financing"). Fixed by expanding `deal_kws` to ~30 keywords covering financing rounds, regulatory events, clinical milestones, and PR markers.

**"Deal History" → "Related News" (all 3 renderer locations):**
- `_genericDetailHTML`: "Deal History" → "📰 Related News"
- `_detailHTML` (static fallback): same rename
- Spyre static renderer: same rename
- All "Upcoming Catalysts" sections now also use "📅 Upcoming Catalysts" consistently

**Frontend — scrollable 5+ item cap (both panels):**
- Catalysts: `max-height:210px; overflow-y:auto` when >5 items; count badge shows total
- Related News: same scroll behavior; count badge ("N items · scroll for more")

**Frontend — intel table merged into Related News:**
- `_loadDynamicDetail` now also queries `intel_companies` junction + `intel` table for company news
- Merges deals + intel items, deduplicates by headline prefix, sorts newest first
- Merged set passed to `_genericDetailHTML` as `sbData.deals`

**deal_type badge display added (Related News panel):**
- 💰 Funding, 📋 License, 🤝 Partnership, 🏢 Acquisition, 📰 News
- Type inferred from headline keywords in Step 6 (no longer always "license")
- Dollar amounts shown inline when `upfront_usd_m` is set

**company_enrichment.py Step 6 — broadened deal discovery:**
- `deal_kws` expanded: added "series a/b/c/d", "financing", "raises", "ipo", "offering", "approval", "clearance", "pdufa", "readout", "announces", "closes" etc.
- `deal_type` now inferred from headline: financing → "financing", merger → "acquisition", partner → "partnership", clinical → "clinical", approval → "regulatory", default → "news"
- RULE documented in code: "Related News = any notable company event, not just formal BD deals"

**Mirador $250M Series B seeded manually:**
- company_id='mirador', deal_type='financing', deal_date='2026-01-12', $250M
- Investors: T. Rowe Price, Adage Capital, Fidelity + existing
- Detail: 10+ clinical readouts expected by YE 2027; CD, UC, RA, IPF programs
- source_url: miradortx.com press releases

---
## 2026-05-20 Trial display redesign + Spyre route fix — index.html: 7a1710d0 | seed: b847e930

### What changed

**index.html — trial row redesign in drug popup:**
- Trial name now shown inline next to NCT number (linked) — no more redundant label text
- Compact badge row: Phase badge (blue) · Status (green/amber) · N=xxx · PCD date
- Primary endpoint shown as snippet in collapsed view
- Click anywhere on trial row to expand full details: indication, full endpoint, sponsor, CT.gov link
- Chevron (▼/▲) indicates expand state; click uses stopPropagation so popup stays open
- Status color-coded: green = recruiting/active, amber = completed/closed, grey = other

**Supabase + seed_tl1a_companies.py — Spyre route fix:**
- SKYLINE-UC (NCT07012395) explicitly states IV induction + SC maintenance
- All 6 SKYLINE platform drugs now show route="IV/SC", dosing_type="Induction + Maintenance"
  - SPY001, SPY002, SPY003 (monotherapies) + SPY120, SPY130, SPY230 (combinations)
- SPY072 (SKYWAY-RD rheumatology trial) unchanged — SC only, separate trial
- Patched directly in Supabase + updated seed script comments with NCT07012395 reference

---
## 2026-05-20 Data quality pass: Xencor fixes + notation standards — index.html: 734cfaa7 | seed: 4c0945cd | enrichment: 4f57c053

### What changed
Multi-layer data quality fixes addressing target notation precision, display priority bugs, enrichment standards, and seed script correctness.

**Supabase (patched in previous session):**
- XmAb412: target corrected to "TL1A × IL-23p19" (was "Anti-TL1A × IL-23"); modality="bispecific"; mechanism_detail added with XTEND-Fc + DDW 2026 preclinical data + FIH Q3 2026 timeline
- XmAb942: name corrected to "XmAb942" (Vudalimab alias removed — Vudalimab=XmAb20717 is a separate PD-1×CTLA-4 bispecific for oncology, completely unrelated); modality corrected to "mAb"; mechanism_detail added with XTEND-Fc ~74-day half-life, XENITH-UC trial details

**index.html display fixes:**
- `_makeDynamicDrugBtn` line ~9120: target priority fixed to `d.target || d.mechanism` (was `d.mechanism || d.target`). RULE: target field always shows clean notation (e.g. "TL1A × IL-23p19"); mechanism is for detail panel only.
- Mechanism & Context panel: now shows `d.mechanism_detail || d.mechanism` (was just `d.mechanism`). Richer clinical narrative now surfaces in popup.
- Drug popup: `drug_summary` field now rendered as highlighted summary block below indication — first thing user reads about the molecule.
- Brand name display comment added: if `name` = "BrandName (INN)", pill shows brand name; numbered codes suppressed.

**seed_tl1a_companies.py fixes:**
- XmAb412: target="TL1A × IL-23p19", stageKey="Pre-IND", mechanismDetail updated with XTEND-Fc + FIH timeline
- XmAb942: drug name = "XmAb942" (Vudalimab removed), modality = "mAb", mechanismDetail updated with XTEND-Fc half-life details and explicit note that Vudalimab is unrelated
- spyre-spy003: target corrected to "IL-23p19" (was "IL-23")
- spyre-spy230: target corrected to "IL-23p19 + TL1A" (was "IL-23 + TL1A")
- spyre-spy130: target corrected to "α4β7 + IL-23p19" (was "α4β7 + IL-23")
- abbvie-skyrizi, lilly-omvoh: target corrected to "IL-23p19" (was "IL-23 (p19)")
- Mechanism auto-generation bug fixed: was blindly prepending "Anti-" to all targets. Now modality-aware: bispecific → "{target} bispecific"; combination → "{target} combination"; mAb → "Anti-{target} mAb"

**company_enrichment.py — DATA QUALITY STANDARDS added to ENRICHMENT_SYSTEM:**
- TARGET NOTATION: Always use "IL-23p19" not "IL-23"; "×" for bispecifics; "+" for rational combos; no "Anti-" prefix in target field
- DRUG NAME FORMAT: Brand name first ("Skyrizi (Risankizumab)"); suppress numbered codes; pill auto-shows brand name
- PCD GRANULARITY: Must include specific day when known ("April 28, 2028" not "Apr 2028")
- VALIDATED REFERENCES: Every catalyst and deal must include source_url (CT.gov, press release, SEC 8-K); fabrication prohibited
- CHINA CDE AWARENESS: Programs registered on China CDE (chinadrugtrials.org.cn) but not CT.gov must be noted explicitly
- drug_summary field added to drug_updates schema: 2-3 sentence highlight of the most important molecule-level facts
- source_url added to catalysts and deal_updates schema; persisted to Supabase on write
- drug context sent to Claude now includes mechanism_detail, drug_summary, and aliases

---
## 2026-05-20 Spyre 7-drug pipeline correction — SHA: c0626b97

### What changed
Full correction of Spyre Therapeutics drug data across all layers (Supabase, seed script, index.html).

**CRITICAL CORRECTION — Spyre has NO bispecifics:**
- "+" in target = rational combination (two separate mAbs co-administered): SPY120, SPY130, SPY230
- "×" in target = bispecific (single molecule, two targets) — Spyre does NOT use this
- Previous errors: SPY002 labeled as "TL1A × IL-23 bispecific" (WRONG — it's anti-TL1A monospecific mAb); SPY230 labeled as "TL1A × FcRn bispecific" (WRONG — it's IL-23 + TL1A combination)

**Supabase — all 7 Spyre drugs correctly seeded:**
- spy001: anti-α4β7 mAb, Phase 2, Adjacent overlap, sort_order=6
- spy002: anti-TL1A mAb, Phase 2, Direct, sort_order=1
- spy003: anti-IL-23 mAb, Phase 2, Direct, sort_order=2
- spy072: anti-TL1A mAb (RA/PsA/axSpA rheumatic), Phase 2, Adjacent, sort_order=5
- spy120: α4β7 + TL1A combination (SPY001+SPY002), Phase 2, Direct, is_combo=true, sort_order=3
- spy130: α4β7 + IL-23 combination (SPY001+SPY003), Phase 2, Direct, is_combo=true, sort_order=4
- spy230: IL-23 + TL1A combination (SPY003+SPY002), Phase 2, Direct, is_combo=true, sort_order=5
- All 7 drugs tagged in drug_areas for both area_id='tl1a' AND area_id='ibd' (14 tags total)

**seed_tl1a_companies.py — Spyre entries corrected:**
- Replaced wrong `spyre-mono` (SPY002 as "TL1A × IL-23 bispecific") and removed old `spyre-230` entry
- Now has 7 correct entries: spyre-spy002/003/230/120/130 (Direct) + spyre-spy001/072 (Adjacent)
- Each entry has correct modality ('mAb' or 'combination'), route ('SC'), and mechanismDetail

**index.html TL1A_PROGRAMS — Spyre entries corrected:**
- Replaced 2 wrong entries with 7 correct entries grouped under groupId='spyre'
- Primary entry: spyre-spy230 (IL-23 + TL1A combination) — most directly relevant to Ailux TL1A×IL-23p19 bispecific
- Outer row now shows "SPY230 +6 more" with correct target display
- All SPYRE_PIPELINE drug button hover cards already had correct data (unchanged)
- Expanded view loads from Supabase → shows all 7 drugs correctly

---
## 2026-05-20 Schema v9 + Drug Characterisation + Truth State — SHA: scripts pushed

### What changed
Major schema and pipeline update to support competitive characterisation against Ailux's TL1A×IL-23p19 bispecific.

**schema_migration_v9.sql — applied to Supabase**
- Added `modality`, `route`, `drug_format`, `dosing_type`, `dosing_schedule`, `half_life_note`, `mechanism_detail`, `stage_detail`, `key_data`, `is_combo`, `aliases` to `drugs` table
- Added `confidence_level` TEXT (default 'inferred') and `data_source` TEXT (default 'claude_inferred') to `drugs` — Truth State framework
- Added `expected_evidence_stage` INTEGER to `drugs` — calibrates completeness scoring so preclinical companies aren't penalised for missing trial data; back-filled from existing stage values (Preclinical=1, Phase 1=2, Phase 2=3, Phase 3=4, Approved=5)
- Added `confidence_level` to `catalysts`; back-filled CT.gov-sourced catalysts to 'confirmed'
- All columns added with IF NOT EXISTS guards (migration is re-runnable)

**seed_tl1a_companies.py — all 18 TL1A programs re-seeded**
- All entries now carry `modality`, `route`, `mechanismDetail`, `confidence_level='confirmed'`, `data_source='manual'`, `expected_evidence_stage`
- Bispecifics (SPY002, XmAb412, SPY230) sorted first — highest overlap with Ailux asset
- Phase 3 monospecifics (Tulisokibart, Afimkibart, Duvakitug) next; oral small molecule (Upadacitinib) correctly typed

**company_enrichment.py — enrichment prompt updated**
- Step 5 `drug_updates` schema now requests: `modality`, `mechanism_detail`, `key_data`, `stage_detail`, `confidence_level`, `data_source` per drug
- Catalyst schema now requests `confidence_level` per catalyst event
- Step 1 discovery prompt now requests `modality` and `route` for newly found entities
- New drugs seeded in Step 1 now write `expected_evidence_stage` computed from stage field

**Pipeline triggered** — GitHub Actions dispatch fired for TL1A area; new fields will be enriched on the next pipeline run.

**Architecture doc updated to v2.1** (`BD_Platform_Architecture_v2.1.docx`) — minor corrections: Stage Cap (renamed from Floor), Phase A/B single-call note, Stage 0–5 clarification, vs_ailux gap description improved.

---
## 2026-05-20 IBD-Based Company Eligibility + Tulisokibart Fix — SHA: 43cc2c3 / cbcc78f / a898729

### Design change
A company belongs in the TL1A tab if it has **any drug in the IBD disease space**, not only if it has a TL1A-targeted program. IL-23, JAK1, α4β7, and future IBD mechanism entrants all qualify. This is now enforced at every layer: Supabase data, pipeline seeding, and frontend discovery.

### Tulisokibart data fix
- **Supabase `drugs` table**: `tulisokibart` was incorrectly seeded with `company_id='spyre'` — reassigned to `company_id='merck'`, `entity_id='merck'`, `entity_name='Merck & Co.'`. Drug name corrected from `"Tulisokibart (SPY001)"` to `"Tulisokibart (MK-7240/PRA023)"`. Tulisokibart was acquired by Merck via the $10.8B Prometheus Biosciences acquisition (Apr 2023) — it is not a Spyre asset.
- **`seed_tl1a_companies.py`**: Removed the incorrect Spyre-tulisokibart entry from `TL1A_PROGRAMS`. Merck's entry corrected to `drug="Tulisokibart (MK-7240/PRA023)"` at `stageKey="Phase 3"`. Added comment clarifying the attribution.

### Company eligibility — `index.html` → `43cc2c3`
- **`_loadSbDiscoveredRows()`** now queries `company_areas.area_id = this._drugDisplayArea` (resolves to `'ibd'`) instead of hardcoded `'tl1a'`. Any company with an IBD drug seeded to `company_areas.area_id='ibd'` will appear as a row in the TL1A tab automatically.

### Supabase data — company_areas for ibd
- All 21 companies already in `company_areas.area_id='tl1a'` also seeded to `company_areas.area_id='ibd'` (one-time backfill). Future companies discovered by the pipeline now land in both areas.

### Pipeline — `scripts/company_enrichment.py` → `cbcc78f`
- Step 1 now seeds `company_areas` for BOTH the specific target area (`tl1a`) AND the indication_group area (`ibd`) when creating a new entity. Ensures newly discovered IBD companies (regardless of mechanism) appear in the TL1A tab immediately.

### Seed script — `scripts/seed_tl1a_companies.py` → `a898729`
- All company groups seeded to both `company_areas.area_id='tl1a'` and `company_areas.area_id='ibd'`

---
## 2026-05-20 IBD Indication Group — Disease-Based Drug Display — SHA: 61e5d62 / da48112 / 74ed99f

### Design change
Previously, expanded rows in the TL1A PI table showed only drugs tagged to `drug_areas.area_id='tl1a'`. This incorrectly hid IBD-mechanism drugs that weren't TL1A-targeted (e.g. Spyre's SPY120 IL-23 and SPY130 α4β7 programs). The correct filter is **indication** (IBD), not **target** (TL1A).

### What changed

**Schema — `scripts/schema_migration_v8.sql` → `93da492`**
- Added `indication_group TEXT` column to `disease_areas` table
- Populated: `tl1a→ibd`, `tslp→respiratory`, `il4ra→atopy`, `igf1r→ted`, `fcrn→autoimmune`, `tcell→autoimmune`
- Added `ibd` as a formal `disease_areas` entry (id='ibd', sort_order=10)
- This column drives which area_id is used for drug display in expanded PI rows

**Data — 38 IBD drugs seeded to `drug_areas.area_id='ibd'`**
- All 36 existing `tl1a`-tagged drugs copied to `ibd`
- Plus 6 additional IBD-mechanism drugs not previously in tl1a: `spy120` (IL-23), `spy130` (α4β7), `risankizumab` (IL-23/Skyrizi), `upadacitinib` (JAK1/Rinvoq), `mirikizumab` (IL-23/Omvoh), `vedolizumab` (α4β7/Entyvio)

**Frontend — `index.html` → `61e5d62`**
- `_loadIndicationGroup()` — new async method on `tl1aPI.init()`. Reads `disease_areas.indication_group` for `tl1a` from Supabase, stores as `this._drugDisplayArea`. Defaults to `'tl1a'` if fetch fails.
- `_loadDynamicDetail` updated — drug fetch now uses `this._drugDisplayArea` ('ibd') as the area filter instead of 'tl1a'. TL1A-targeted drugs sorted first within the IBD set; other IBD drugs (IL-23, JAK, integrin) follow.
- This is data-driven: if `indication_group` changes in Supabase, the frontend adapts without a code deploy.

**Pipeline — `scripts/company_enrichment.py` → `da48112`**
- Step 1 now reads `indication_group` for the current area at runtime
- Newly discovered drugs are tagged to BOTH `area_id` (e.g. `tl1a`) AND `indication_group` (e.g. `ibd`) in `drug_areas`
- `seed_tl1a_companies.py` → `74ed99f` — also seeds `drug_areas` for `ibd` when seeding each drug

---
## 2026-05-20 Fix: Show All Company Drugs in Expanded Row — SHA: 3de2ce6

### Updated: `index.html` → `3de2ce6`
- **Fix: `_loadDynamicDetail` drug filter was too narrow** — previously filtered drugs to only those tagged in `drug_areas` for the current area (`tl1a`). This caused Spyre's `spy120` (IL-23) and `spy130` (α4β7) to be invisible in the expanded row even though they exist in Supabase, because they weren't in `drug_areas` for `tl1a`.
- **New behavior: fetch all drugs for the company, area-tagged first.** Area-matched drugs appear at the top (TL1A programs for a TL1A-area entry), then the rest of the company's pipeline follows. Drug fetch limit raised from 5 to 8 for trial hydration. Area filtering correctly belongs at the company-level table row (which companies appear), not at the drug level inside a company's expanded panel.

---
## 2026-05-20 Dynamic PI Table + Supabase Seeding Architecture — SHA: 4106c42 / 1988da9 / c247b42

### Updated: `index.html` → `4106c42`
- **`_loadSbDiscoveredRows()` added** — new async method called on `tl1aPI.init()`. Fetches all `company_areas` rows for `tl1a` from Supabase, identifies companies **not** in the static `TL1A_PROGRAMS` array (matched by `group_id`), synthesizes program entries for them, and merges into `this.data`. Pipeline-discovered companies now appear in the TL1A PI table automatically without any HTML edits.
- **`toggle()` updated** — now searches `this.data` (includes dynamically merged rows) instead of just `TL1A_PROGRAMS`. Supabase-discovered companies can be expanded and their detail loaded like any static entry.
- **`_loadIntelStatus()` updated** — uses `this.data` (includes merged rows) when computing the no-intel dot set, so pipeline-discovered companies also get the blinking green research dot.

### Updated: `scripts/company_enrichment.py` → `c247b42`
- **Step 1 now writes `group_id`, `partner_co`, `display_co`, `overlap`** — newly discovered entities get `group_id = co_id` (self-group by default), `display_co = co_name`, `partner_co` from Claude's JSON output (new field in discovery schema), `overlap` from Claude's classification (new field; defaults to `Watch`).
- **Discovery JSON schema extended** — two new fields added to the entity JSON Claude returns: `partner_co` (licensor/partner company name or null) and `overlap` (Direct / Adjacent / Same-Space / Watch classification).

### Updated: `scripts/seed_tl1a_companies.py` → `1988da9` *(new file)*
- **One-time (re-runnable) seeding script** — seeds all 14 TL1A companies + 19 drugs to Supabase with `partner_co`, `group_id`, `display_co`, `overlap` populated. Idempotent via upsert with merge-duplicates. Ensures Episcience, Caldera, Earendil, LaNova, Mirador, and all others are in Supabase so the pipeline can enrich them going forward.
- **Run result:** All 14 companies × `tl1a` area links + 19 drugs seeded successfully.

### New: `scripts/schema_migration_v7.sql` → `1e829ac`
- **Added `partner_co TEXT`, `group_id TEXT`, `display_co TEXT`, `overlap TEXT`** columns to `companies` table via Supabase Management API. Index added on `group_id`. Migration applied successfully.

---
## 2026-05-20 Drug Row Redesign + Spyre Standard Format + Episcience Fixes — SHA: ef5b8c8

### Updated: `index.html` → `ef5b8c8`
- **Drug row header redesigned** — Drug accordion rows now show: Drug Name | Target | Phase Pill | Indication tag. Partner company (Telavant, Teva, BI, etc.) shown as a blue "w/ [Partner]" tag inline with the drug name. All route/dosing/other detail stays in the expanded sub-row. Removes the "AbbVie TL1A mAb" style naming — shows just the drug name itself.
- **Spyre converted to standard accordion format** — Removed `_spyreDetailHTML` special case. Spyre now uses `_genericDetailHTML` like all other companies. SPY002 and SPY230 each appear as their own drug accordion rows with target/phase/indication. Supabase queries use `company_id='spyre'`.
- **Spyre toggle no longer excluded** from `_loadDynamicDetail` — all companies go through the same path. Toggle now uses `gid` (groupId) as the Supabase company_id for all queries, fixing the Supabase lookup mismatch for grouped companies.
- **Cache and DOM keys normalized** — `_profileCache` and placeholder div ids now keyed by `gid` (groupId) throughout `_renderTable` and `toggle`.
- **Partner subtext removed from company column** — No more "w/ [Partner]" italic text under the company name in the table row. Partner info now lives in the drug row header only.
- **Episcience static entry fixed** — `cls:'Direct'` → `'Next Gen'`; `overlap:'watch'` → `'Watch'`. Previously these wrong values caused the class pill and relevance badge to render incorrectly.

---
## 2026-05-20 Consolidate PI Table — One Row Per Company — SHA: e8d59b6

### Updated: `index.html` → `e8d59b6`
- **Consolidated PI table by lead company** — Each company now appears once in the table. Multiple programs from the same company (AbbVie × 3, Xencor × 2, Spyre × 2) collapse into a single row. Clicking expands to show all drugs under that company.
- **Added `groupId` field to all 18 `TL1A_PROGRAMS` entries** — Groups: `abbvie` (FG-M701 + Skyrizi + Rinvoq), `xencor` (XmAb942 + XmAb412), `spyre` (SPY002 + SPY230). All other entries have `groupId` = their own singleton.
- **Updated `co` display names** — Removed partner company from company name column. Partner company now shown as small italic "w/ [Partner]" subtext. Changes: Roche/Telavant→Roche, Sanofi/Teva→Sanofi, Simcere/BI→Simcere, Caldera/Qyuns→Caldera, LaNova/Zymeworks→LaNova, Earendil/Helixon(Sanofi)→Earendil/Helixon, Xencor(XmAb412)→Xencor, Spyre(SPY230)→Spyre Therapeutics. New `partnerCo` field added where applicable.
- **Drug column shows primary drug + "+N more" badge** for multi-drug groups (purple pill badge).
- **Stage + Relevance show best value across group** — most advanced stage, most direct overlap.
- **`_renderTable` rewritten** to group sorted entries by `groupId`, build one row per group with aggregate display values.
- **`toggle(gid)` updated** — toggle key is now `groupId`. Builds `combinedProg` with `_groupEntries` (all programs in group) for static drug fallback.
- **`_genericDetailHTML` static fallback updated** — when Supabase has no drugs, iterates `_groupEntries` to build one drug accordion row per program entry (with per-entry `_staticTrials`). Resolves trial spillover for multi-program statics.
- **Counter updated** — now shows "N companies" (unique group count) not "N programs".

---
## 2026-05-20 Fix: Trial Spillover + AbbVie FG-M701 Entry + Duvakitug NCT Seeds — SHA: 7ce41ac / c534d5b

### Updated: `index.html` → `7ce41ac`
- **Fix: trial spillover in multi-drug entities** — `_genericDetailHTML` was falling back to static `prog.trials` even when Supabase drugs had loaded but trials hadn't synced yet. All static trials had no `drug_id` so they fell into `trialsByDrug['__all__']`, which every drug row consumed, producing duplicate trial lists.
  - **Fix 1 (allTrials fallback):** Only use `prog.trials` when `sbDrugs.length === 0` (fully static mode). If Supabase drugs are present but trials are empty, use `[]` rather than spilling static trials across all drug rows.
  - **Fix 2 (`__all__` bucket):** Restrict `trialsByDrug['__all__']` lookup to single-drug entities only (`drugsToRender.length <= 1`). Multi-drug entities never fall back to `__all__`.
- **Added: AbbVie Direct TL1A entry (FG-M701)** — New `TL1A_PROGRAMS` entry `{ id:'abbvie', co:'AbbVie', drug:'FG-M701', overlap:'Direct', stageKey:'Phase 1' }` inserted before indirect competitors. Maps to Supabase `company_id='abbvie'` where `fg-m701` and `abbvie-tl1a` both exist. Fixes FG-M701 not appearing even though a deal row referenced it — root cause was prior `'abbvie-skyrizi'` entry ID not matching Supabase.

### Updated: `scripts/ct_gov_sync.py` → `c534d5b`
- **Added Duvakitug to NCT_SEED_MAP** — 5 NCT IDs now hardcoded: STARSCAPE-UC induction (NCT07184996), STARSCAPE-UC maintenance (NCT07185009), SUNSCAPE-CD induction (NCT07184931), SUNSCAPE-CD maintenance (NCT07184944), Phase 2b UC+CD completed (NCT05499130). Previously used search path ("use search: duvakitug") which failed to populate trials in Supabase.

---
## 2026-05-20 Cleanup: Remove Research Queue + Inline Edit — SHA: 6cf3ccc

### Updated: `index.html` → `6cf3ccc`
- **Removed: Research Queue home panel** (`#research-queue-panel`) — entire `home-card` block removed from home tab. Panel was premature; backend pipeline needs more work before surfacing to UI.
- **Removed: Inline edit on entity classifications** — stripped `class="pi-editable"`, `title="Double-click to edit"`, and `ondblclick="piStartEdit(...)"` from Drug, Target, and Class columns in `_renderTable`. Columns now display read-only.
- **Removed JS:** `piStartEdit()`, `piResearchValidate()`, `piApplyEdit()`, `loadResearchQueue()`, `loadAreaPulse()`, `rqSetStatus()`, `rqToggleGaps()` — all edit and queue functions deleted.
- **Removed CSS:** `.pi-editable`, `.pi-edit-*`, `.pi-cell-input`, `.rq-*`, `#rq-body`, `#rq-area-pulse`, area pulse strip, and queue gaps expansion classes.
- **Updated DOMContentLoaded:** Removed `loadResearchQueue()` and `loadAreaPulse()` call sites.

---
## 2026-05-20 Drug Accordion Rows + Remove Intelligence Button — SHA: d97caef

### Updated: `index.html` → `d97caef`
- **Redesign: entity expanded row** — Replaced card-based drug display in `_genericDetailHTML` with accordion row layout. Applies to all non-Spyre entities across all drug area tabs.
  - Drug rows: name | stage pill | mechanism (truncated) | route/dosing/indication tags — all in a single scannable row
  - Click to expand drug: shows differentiation thesis + trial sub-rows
  - Trial rows: NCT# (hyperlinked to `clinicaltrials.gov/study/NCTXXXX`) | trial name | status badge | phase pill | enrollment | PCD
  - Click to expand trial: condition, enrollment, dosing type, route, primary endpoint in a 3-col grid
  - Results sub-dropdown: shown for completed/reported trials with `results_summary`
  - Drug section renders at TOP of expanded row, above platform summary / BD summary / catalysts / deals
- **Added CSS classes:** `.pi-da-*` (drug accordion), `.pi-tr-*` (trial rows)
- **Added JS functions:** `piToggleDrugRow()`, `piToggleTrialRow()`, `piToggleTrialResults()`
- **Removed: ⚡ Intelligence nav button** — Removed `<a href="intelligence.html" class="intel-cmd-btn">` from header and its associated CSS rules (`.intel-cmd-btn`, `.intel-cmd-btn:hover`). Intelligence page link no longer exposed in the nav.

---
## 2026-05-20 Fix: Catalyst Deduplication — SHA: 667e51b

### Updated: `scripts/company_enrichment.py` → `667e51b`
- **Root cause:** Step 4 idempotency check was keyed on `related_trial_id` — one catalyst per trial record. Drugs with multiple NCT IDs sharing the same primary completion date (e.g. Afimkibart AD: adult/pediatric/site cohorts) each created a separate catalyst row, producing 6+ identical entries.
- **Fix:** Changed dedup key to `(company_id, canonical_drug_id OR drug_id, sort_date)`. Multiple trials for the same drug on the same date now collapse to one catalyst.
- **Data cleanup:** Deleted 291 duplicate catalyst rows from Supabase directly via REST API. 209 canonical rows remain.

---
## 2026-05-20 Step 1 Entity Discovery — Proactive Web Search — SHA: 552c01e

### Updated: `scripts/company_enrichment.py` → `552c01e`
- **Root cause fixed:** Step 1 previously only scanned intel already in Supabase to find new entities. If a company (e.g. Pfizer's PF-07261271 TL1A bispecific) had never appeared in the intel table, it was invisible to the pipeline.
- **Added `gather_landscape_intel(area_id)`** — Phase A of Step 1. Uses `web_search_20250305` (Sonnet) to proactively search for ALL companies with clinical-stage programs in the target area, including large pharma. Returns free-text landscape report.
- **Upgraded `step1_discover_new_entities()`** — now runs landscape web search first; falls back to local intel as secondary signal only. Claude Haiku diffs the web results against existing Supabase `company_areas` and creates records for new entities with `discovery_status='auto'`. Hard "No recent intel — skipping" failure removed.
- **Effect:** Pfizer (and any other large pharma/biotech) with relevant programs will now be auto-discovered and seeded on the next nightly/weekly pipeline run without any manual intervention.

---
## 2026-05-20 Layout Bug Fixes — SHA: d9fc75b

### Updated: `index.html` → `d9fc75b`
- **Fix: molecule dropdown z-index** — Raised `.tab-bar` z-index from 190 → 400. The tab-bar `position: sticky` was creating a stacking context at z-index 190, causing the molecule dropdown (z-index 600 within that context) to render below the fixed pill columns (z-index 300). Now dropdown correctly paints on top.
- **Fix: pill column overlap at narrow viewports** — Added `@media (max-width: 1440px) { .tl1a-pills-col { display: none !important; } }`. Pills are 148px wide + 14px gap = 162px each side; content is max 1100px, requiring ~1424px+ viewport for no overlap. Below this threshold pills now hide cleanly instead of bleeding over the PI table.

---
## 2026-05-20 BD Intelligence Command Center — SHA: 3d02814 + 7e615e0

### New File: `intelligence.html` → `3d02814`
- Standalone two-panel command center at `/intelligence.html` on GitHub Pages
- Left panel (380px fixed): ranked research queue with area filter pills, hide-done toggle, completeness bars, status cycle buttons (Pending → Active → Done), expandable gap chips grouped by stage
- Right panel: entity detail view with 6-stage completeness breakdown, missing field chips, next best action, five expanders: Drugs table, Clinical Trials, Upcoming Catalysts, BD Deals, Strategic Profile
- Stage analysis derived from `missing_fields` JSONB array — infers per-stage coverage % by matching field name patterns; counts unique drug prefixes for dynamic field totals
- Header: `◈ Intelligence` brand mark, identity health mini-stat, `← Dashboard` back link
- Same Supabase anon key as main dashboard; all reads via RLS-protected SELECT

### Updated: `index.html` → `7e615e0`
- Added `⚡ Intelligence` nav button to dashboard header (right side, before Submit Intel)
- Purple-accented styling (`.intel-cmd-btn`) consistent with the intelligence layer theme
- Links directly to `intelligence.html` for one-click access from main dashboard

---
## 2026-05-19 Dashboard Intelligence Upgrades — SHA: a906bce

### Updated: `index.html` → `a906bce`

**Area Completeness Pulse Strip (`#rq-area-pulse`):**
- Compact 6-tile strip rendered inside the Research Queue card header area
- Each tile shows area short name, average completeness %, mini fill bar (red/amber/green), entity count
- Tile tooltips show tier breakdown (strong ✓ / partial ~ / thin ✗)
- `loadAreaPulse()` queries research_queue grouped by area_id; added to `DOMContentLoaded`

**Expandable Missing Fields in Queue Rows:**
- Added `missing_fields` to the research_queue select query
- Each queue row with gaps shows a purple `▸ N gaps` expand button
- Click toggles inline grouped breakdown by intelligence stage:
  - Stage 2 · Drug Mapping (mechanism, target, differentiation_thesis)
  - Stage 3 · Trial Intelligence (has_trials, trial fields)
  - Stage 4 · Catalysts (catalysts_list)
  - Stage 5 · Strategic Position (company_profile, competitive_position, vs_ailux)
  - Stage 6 · Deal Intelligence (deals_list)
- Fields rendered as small red chips with human-readable labels
- `rqToggleGaps()` function handles open/close state

**BD Signal Panel Upgraded to Unified Signal Feed:**
- `loadBDSignal()` now fetches both deals AND high-importance intel (last 7d) in parallel
- Feed items sorted by date descending, blended from both sources
- Intel items show "Intel" green pill type badge; deals show "Deal" blue pill badge
- Intel items display `ailux_angle` commentary in a green-accented signal box
- Footer summary shows counts of each type
- Falls back gracefully if intel table has no recent high-importance items

**Company Enrichment Freshness Badges:**
- `loadStockCards()` now fetches `company_profiles.last_enriched_at` as 6th parallel query
- `_freshnessBadge(isoDate)` helper formats relative age: "enriched today" (<24h), "Nd ago" (≤7d fresh, ≤21d recent, >21d stale)
- Badge rendered at bottom-right of each stock card body, color-coded:
  - Green: enriched today or ≤7d ago
  - Amber: 8–21d ago
  - Red: >21d ago or "not enriched" if no profile exists

**Pipeline dispatch:**
- GitHub Actions `company-enrichment.yml` triggered for `area=all` via workflow_dispatch API
- Run queued at 2026-05-19T20:23:00Z — will populate missing strategic fields across all 43 entities

---
## 2026-05-19 UI Redesign — Decision-Flow Architecture — SHA: d42d542

### Updated: `index.html` → `d42d542`

**Home tab restructured — research queue promoted to primary surface:**
- Research queue moved to top of home tab with gradient header ("What needs attention today")
- Card order: Research Queue → Key Catalysts → BD Signal → Recent Deals → Essential Updates → Footnote
- Old Identity Health card removed (hidden `#ih-body` div retained for JS compat)

**Research Queue enhanced rows:**
- Left-border priority color coding: red (`rq-hi` >80), amber (`rq-mid` 50–80), slate (`rq-lo` <50)
- Completeness mini-bar (72px) with tier-colored fill (red/amber/green)
- Area color pill per row using `_AREA_PILL_COLORS` constants
- Completeness score + priority score displayed inline
- `next_best_action` shown as arrow-prefixed action text
- Entity names prettified (underscore → title case)

**PI score badges on all drug tabs:**
- `_injPIScores(tabId, areaIds)` post-render injects `.pi-score-chip` into `.pi-co-name` cells
- Chip color-coded by tier: thin (red), partial (amber), strong (green), unknown (gray)
- Chip click opens stage score drill-down modal

**Stage score drill-down modal (`#pi-score-modal-overlay`):**
- Shows entity name, area, completeness score + tier, animated fill bar
- Displays `next_best_action` and priority score
- Click-outside or × button to close; ESC key support
- `showPIScoreModal()` / `closePIModal()` JS functions

**Identity health footer bar (`#id-footer`):**
- Fixed `position:fixed; bottom:0` bar across all pages (height 28px)
- Color states: green (ok), amber (warn), red (bad), slate (loading)
- Dot indicator + status text + "click to view home tab ↑" hint
- `loadIdentityFooter()` reads orphan/unresolved counts from Supabase at page load
- `body { padding-bottom:28px }` prevents content overlap

**JS wiring:**
- `_injPIScores()` called from `loadAreaPI()` after `pi.init()` completes
- `loadIdentityFooter()` added to `DOMContentLoaded` handler

---
## 2026-05-19 Full Bug Fix Pass (Bugs #4–10) — SHAs: ba6dfc2 (company_enrichment), 4a5250c (ct_gov_sync), 299d716 (identity_health_check), 0ae7569 (index.html), 803e789 (CODE_REVIEW)

### Updated: `scripts/company_enrichment.py` → `ba6dfc2`
- **Bug #4 fixed:** `step6_deal_intelligence` dedup replaced `headline[:50]` shallow match with `_deal_signature()` helper — normalizes (lowercase, strip non-alphanumeric), compares first 100 chars. Eliminates false positives from punctuation/spacing differences.

### Updated: `scripts/ct_gov_sync.py` → `4a5250c`
- **Bug #8 fixed:** `--search-only` flag now actually works. `sync_drug()` accepts `search_only: bool = False`; when True, Step 3a (direct NCT fetch) is skipped and a skip log line is emitted. `run_sync()` passes `search_only=search_only` down to each `sync_drug()` call.

### Updated: `scripts/identity_health_check.py` → `299d716`
- **Bug #7 fixed:** `unresolved_count = int(r["unresolved"] or 0)` now saved from the first query (before `r` is overwritten by later queries). Summary line now correctly reports actual unresolved drug count instead of always printing "0 drugs unresolved".

### Updated: `index.html` → `0ae7569`
- **Bug #5 fixed:** Meridian Reader sort secondary key changed from `(date || '').replace(/-/g,'') * 0.0001` (NaN for ISO timestamps) to `new Date(date || 0).getTime() / 1e13` — handles both date-only and full ISO datetime strings. Applied to intel, deals, and catalyst sort expressions.
- **Bug #6 fixed:** `loadIdentityHealth()` now computes true FK orphan count in JS: fetches `canonical_id` from `canonical_drugs`, builds a Set, counts drugs with a `canonical_drug_id` that isn't in the Set. New `FK Orphans` stat tile added to the panel. The old `total - resolved` proxy (which measured "unresolved" not "orphaned") is preserved as a separate concept.

### Updated: `CODE_REVIEW.md` → `803e789`
- All 10 bugs marked ✅ FIXED with commit hashes
- Workflow deploy note added explaining `workflow` token scope requirement for Bugs #9/#10

### Workflow changes (local only — need `workflow` token scope to push)
- **Bug #9:** `pip install anthropic requests` → `pip install -r scripts/requirements.txt` (pins all deps via existing requirements.txt; also picks up feedparser, yfinance, pynacl)
- **Bug #10:** Added `[Manual] Identity health check (single area)` step so health check runs after single-area manual dispatches, not just `area=all` runs
- Apply via GitHub web editor at `.github/workflows/company-enrichment.yml`

---
## 2026-05-19 DeepSeek Recommendations — SHAs: 406f0ab9e2 (index.html), bc18f94bd5 (health_check), 19c120665a (playbook)

### Updated: `index.html`
- Research Queue: added **Hide done** checkbox in panel header; `loadResearchQueue()` passes `.neq('assigned_status','done')` when checked
- New **Identity Layer Health** panel (teal border, home tab below Research Queue): shows Canonical Coverage %, Active Canonicals, Fuzzy Pending, Resolver Errors; auto-loads on DOMContentLoaded; ↻ Refresh button
- CSS: `.ih-stat`, `.ih-stat-val`, `.ih-stat-lbl`, `.ih-stat.ok/.warn/.bad`, `.ih-divider`, `.ih-issue`
- `loadIdentityHealth()` JS function queries drugs/canonical_drugs/identity_audit_log/resolver_errors in parallel

### Updated: `scripts/identity_health_check.py`
- Added `argparse`; new flags: `--fail-on-orphans`, `--fail-on-fuzzy-pending`
- `health_check()` now returns exit code (0 = healthy, 1 = CI failure)
- CI failures printed as `[CI FAIL]` lines, separated from warnings in summary
- `sys.exit(code)` at bottom

### Updated: `.github/workflows/company-enrichment.yml` (local only — needs manual push, token lacks `workflow` scope)
- Added `[Nightly] Identity health check` step after Step 7 (nightly Mon–Sat)
- Added `[Weekly/All] Identity health check` step after weekly all-areas loop
- Added `[Manual/All] Identity health check` step after manual all-areas loop (skipped on dry_run)
- All use `SUPABASE_PAT: ${{ secrets.SUPABASE_PAT }}` — add this secret in GitHub repo settings

### New: `BD_ANALYST_PLAYBOOK.md`
- Daily operating guide: research queue usage, priority thresholds, next_best_action glossary, pipeline trigger instructions, status override guidance, identity health reference, script quick-reference

### Deferred (DeepSeek recommendation)
- EntityIdentityResolver (company-level) — defer until 200+ companies show real fragmentation
- research_queue pipeline auto-trigger — defer until queue proves its value for a few weeks

---
## 2026-05-19 Research Queue Status Toggle — SHA: 0eabd7de9e

### Updated: `index.html`
- RLS policies applied to `research_queue` table: `anon_select_research_queue` (SELECT) + `anon_update_research_queue_status` (UPDATE) — anon key can now read and write status
- `loadResearchQueue()` now selects `assigned_status`; renders a status button per row cycling `pending → in_progress → done → pending`
- `rqSetStatus(entityId, areaId, currentStatus)` — optimistic UI update + Supabase PATCH; reverts on error
- CSS: `.rq-status` badge with `.pending` / `.in_progress` / `.done` states; `.rq-row.done-row` fades completed rows
- `_RQ_STATUS_CYCLE` + `_RQ_STATUS_LABEL` constants drive the toggle logic

---
## 2026-05-19 resolver_errors Persistence Layer — SHAs: e11b144c85, 02aa6e6069, 29b69c233e, b9f9756933

### New: `schema_migration_v8.sql` (applied ✅)
- `resolver_errors` table: persists identity resolution failures for retry
- Fields: `drug_name`, `source`, `source_table`, `source_row_id`, `error_message`, `error_type`, `stack_trace`, `attempt_count`, `last_attempted_at`, `resolved_at`, `resolved_canonical_id`
- 5 indexes: unresolved (partial), drug_name, source, source_table+row, created_at

### Updated: `scripts/identity_resolution.py`
- `log_resolver_error(drug_name, source, error, source_table, source_row_id)` — classifies error type (network/supabase/value_error/unknown), persists to resolver_errors with stack trace
- `retry_errors(limit=50)` — re-attempts all `resolved_at IS NULL` rows; stamps source table on success; increments attempt_count on continued failure; returns `{resolved, failed, skipped}`
- CLI: `--retry-errors` flag (mutually exclusive with `--name`); `.supabase_service_key` file fallback added

### Updated: `scripts/ct_gov_sync.py`, `scripts/company_enrichment.py`
- Both circuit-breaker except-blocks now call `resolver.log_resolver_error(...)` after logging the warning
- Wrapped in try/except so error-logging itself never crashes the pipeline

---
## 2026-05-19 Full Pipeline Dispatch + research_queue Populated — SHAs: e7791a4ee2, 0ee38a177e

### Pipeline
- Triggered `company-enrichment.yml` workflow dispatch with `area=all` — runs ct_gov_sync + company_enrichment + research_intelligence across all 6 areas
- Fixed `research_intelligence.py` `_sb_upsert` for research_queue: added `?on_conflict=entity_id,area_id` query param so PostgREST correctly updates existing rows (previously 409'd because table PK is UUID, not the entity/area composite)
- Updated workflow Step 7 (scheduled) from `--area tl1a` to `--area all` — research_intelligence.py has no API calls so running all 6 areas is cheap

### research_queue — All 6 Areas Populated (23 entities total)
| Area  | Entities | Avg Score | Top NBA |
|-------|----------|-----------|---------|
| tl1a  | 20       | varies    | varies (already enriched) |
| tslp  | 5        | 26.4      | Run drug mapping |
| il4ra | 6        | 26.5      | Run drug mapping |
| fcrn  | 4        | 24.2      | Run drug mapping |
| igf1r | 3        | 23.7      | Run drug mapping |
| tcell | 5        | 21.8      | Run drug mapping |

All non-TL1A areas show thin scores with "Run drug mapping to fill mechanism + target fields" as top action — pipeline dispatch above will fix this.

---
## 2026-05-19 Canonical-Grouped Completeness Scoring — GitHub SHA: 6e6f330394

### `scripts/research_intelligence.py`
- **`_group_drugs_by_canonical(drugs)`** — groups drug rows by `canonical_drug_id`; drugs without a canonical each form their own group
- **`_merge_drug_rows(rows)`** — merges sibling rows into one representative: picks longest/most-populated text for each field, max confidence_score, `trial_data_status='missing'` only if ALL rows say missing; attaches `_all_drug_ids` for trial/catalyst lookups
- **Stage 2 (Drug Mapping)** — now iterates over canonical groups rather than raw drug rows; `_merge_drug_rows()` picks best values before scoring so two rows for the same canonical program count as one (was: avg of two independent scores)
- **Stage 3 (Trial Intelligence)** — builds dual lookup maps (by `drug_id` AND `canonical_drug_id`); for each canonical group, unions trials from all constituent `drug_id`s + canonical_drug_id and deduplicates by trial.id; scores the merged program
- **`load_entity_context()`** — computes `canonical_ids` early; also fetches trials by `canonical_drug_id in (...)` and deals by `canonical_drug_id in (...)`, deduplicates by id to avoid double-counting
- All tests pass (3 scenarios verified locally before deploy)

### Impact
- Programs with multiple drug DB rows (e.g. different formulations of the same canonical program) now score as ONE entity rather than averaging inflated/deflated per-row scores
- Trials written by `ct_gov_sync.py` to a different `drug_id` but same canonical are now correctly counted for the entity's Stage 3 score
- Deals written by `company_enrichment.py` via `canonical_drug_id` are now correctly counted in Stage 6

---
## 2026-05-19 Research Queue Panel + Intelligence Layer Completion — GitHub SHA: 01de2d16f4

### Dashboard
- **Research Queue panel** added to home tab between BD Signal and Deals sections
- Purple accent (`#7c3aed`), loads top 12 entities from `research_queue` table sorted by `priority_score` desc
- Shows entity ID, completeness tier badge (thin/partial/strong), area, score, and next best action per entity
- Wired into `DOMContentLoaded` alongside other home panel loaders

### Backend (prior commits this session)
- **`identity_resolution.py`** — Fixed alias 409 noise: removed `_add_alias_if_new` from Step 1 exact-match path (alias already in DB by definition); switched to `resolution=ignore-duplicates` Prefer header. SHAs: 6bd2b851f6 → c9d8317904
- **`schema_migration_v7.sql`** — Added `canonical_drug_id` FK to `catalysts` and `deals` tables with indexes. Applied to Supabase ✅ SHA: 9b011fb134
- **`ct_gov_sync.py`** — Identity resolver wired in: resolves `canonical_drug_id` per drug before trial sync, circuit-breaker on resolver failure. SHA: aff89a8d2f
- **`company_enrichment.py`** — Identity resolver wired into step4 (catalysts) and step6 (deals): canonical_drug_id stamped on all new catalyst/deal records. SHA: cb372d33b3
- **`research_intelligence.py`** — Major schema column fixes (drugs PK=`id`, no `area_id` column on drugs, companies PK=`id`, drug column=`name`); area query now routes through `drug_areas` junction; Stage 2 scoring adds `canonical_drug_id` sub-criterion (denominator 4→5); Stage 3 adds `trial_canonical_linked` (denominator 3→4); NBA engine adds priority 2b for missing canonical identity. Final SHA: beaa868f06

### Identity Spine — COMPLETE
- `drugs.canonical_drug_id` → 53/53 stamped ✅
- `trials.canonical_drug_id` → stamped live by ct_gov_sync.py ✅
- `catalysts.canonical_drug_id` → stamped by company_enrichment.py step4 ✅
- `deals.canonical_drug_id` → stamped by company_enrichment.py step6 ✅
- `research_queue` → 20/20 TL1A entities scored, top priority: spyre (score=23, tier=thin, priority=112)

---
## 2026-05-19 Canonical Drug Identity Layer — schema_migration_v5 + identity_resolution.py + one_time_migration.py

### New Files
- **`schema_migration_v5.sql`** — Canonical drug identity layer. Creates 3 new tables: `canonical_drugs` (one row per real-world drug program, canonical_id format: `CANON_DRUG_{8-char hash}`), `drug_aliases` (all known name variants mapped to a canonical drug, `UNIQUE(canonical_id, alias_name)`), `identity_audit_log` (immutable append-only audit trail). Adds 3 columns to `drugs`: `canonical_drug_id` (FK), `identity_confidence` (0-100), `identity_method` (`exact`|`normalized`|`fuzzy`|`new`|`unresolved`). 6 indexes. Applied to Supabase ✅ GitHub SHA: f21daf5f50
- **`scripts/identity_resolution.py`** — DrugIdentityResolver MVP class. 4-step resolution cascade: (1) exact alias match → confidence 100, (2) normalised name match → confidence 90, (3) fuzzy match ≥0.85 (SequenceMatcher) → **flagged for review, NOT auto-merged** → create new canonical, (4) create new canonical → confidence 100. `resolve()`, `resolve_batch()`, `_normalize_name()`, `_create_canonical_drug()`, `_add_alias_if_new()`, `_flag_fuzzy_review()`. In-memory alias cache refreshed per batch. GitHub SHA: 6c7d1d1c1d
- **`scripts/one_time_migration.py`** — Backfill script for all existing drugs. Iterates all `drugs` rows without `canonical_drug_id`, infers `drug_class` and `target` from mechanism text, resolves via `DrugIdentityResolver`, PATCHes `canonical_drug_id` + `identity_confidence` + `identity_method`. Prints fuzzy review flags at end. Idempotent (skips rows already resolved). GitHub SHA: 999732e1d5

### Architecture Decision (per ChatGPT review)
- **No auto-merge of fuzzy matches** — false merges are more dangerous than duplicate records
- Fuzzy near-misses write a `flag_review` entry to `identity_audit_log` and create a new canonical; human must approve merge
- Backfill first → then wire `ct_gov_sync.py` and `company_enrichment.py` to call `resolve()` before writes (next session)

---
## 2026-05-19 Intelligence Layer — schema_migration_v4 + research_intelligence.py + ARCHITECTURE_v2.md

### New Files
- **`schema_migration_v4.sql`** — Adds 8 completeness/trigger fields to `drugs` table (`completeness_score`, `completeness_tier`, `missing_fields`, `missing_stages`, `next_best_action`, `last_scored_at`, `priority_score`, `trigger_flags`). Creates `research_queue` table with `UNIQUE(entity_id, area_id)`, 9 indexes. Applied to Supabase ✅
- **`scripts/research_intelligence.py`** — Full intelligence layer engine. `load_entity_context()` → `score_entity_completeness()` (0-100 across 6 weighted stages) → `get_next_best_action()` (10-priority decision tree) → `check_research_triggers()` (7 trigger types) → `calculate_priority_score()` (0-200) → `upsert_research_queue()`. CLI: `--area`, `--entity`, `--dry-run`. SHA: ab65db4cf5
- **`ARCHITECTURE_v2.md`** — Comprehensive architecture specification. Full 7-stage research graph, complete schema tables, all function signatures + decision trees, CLASS×RELEVANCE framework, gap analysis P0/P1/P2. Formatted for feeding into AI model for iterative review. SHA: 1880f00ea8
- **`schema_migration_v4.sql`** — GitHub SHA: 9f14425443

### Updated Files
- **`.github/workflows/company-enrichment.yml`** — Added Step 7 (`research_intelligence.py`) after `company_enrichment.py` in all three pipeline sections (scheduled TL1A, manual single-area, manual all-areas loop). Step 7 runs with `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` only (no Anthropic key needed). Committed via GitHub web editor.

### Intelligence Layer Overview
- **Completeness scoring**: Stage weights sum to 100 — Entity Discovery (10), Drug Mapping (15), Trial Intelligence (20), Catalyst Engine (15), Strategic Positioning (25), Deal Intelligence (15)
- **Tiers**: `thin` (<40), `partial` (40–69), `strong` (≥70)
- **7 trigger types**: trial phase ahead of drug stage, trial PCD without catalyst, completed trial without results, catalyst date passed unresolved, profile stale >30 days, new deal since enrichment, strategic entity missing vs_ailux
- **Priority score**: 0–200 with +30 for strategic entity, +20 for active triggers, +15 for thin tier
- **Platform turns from database into guided research system** — every entity now answers: What do we know? What is missing? What changed? What should happen next?

---
## 2026-05-19 Intelligence Pipeline architecture — commits 86a4ca6e / 908640e2 / 68115f5b

### New Files
- **`schema_migration_v3.sql`** — Full intelligence architecture schema migration. Adds to: `trials` (arms, secondary_endpoints, start_date, primary_completion_date, source_url, sponsor, last_synced_date, discovery_status, confidence_score, entity_id), `drugs` (aliases, differentiation_thesis, discovery_status, confidence_score, trial_data_status, last_synced_date), `company_profiles` (market_cap_usd_m, cash_runway, financing_history, key_investors, strategic_behavior, vs_ailux, hq_country, website), `catalysts` (expected_impact, is_key_watch, related_trial_id, source_url, confidence_source), `deals` (parties, geography_rights, economics_royalties, strategic_signal, ailux_relevance, entity_id). **Must be applied manually in Supabase SQL editor.**
- **`scripts/ct_gov_sync.py`** — Step 3 of the intelligence pipeline. Direct NCT ID sync (3a), search discovery (3b), drug stage update from trials (3c). `NCT_SEED_MAP` seeds known NCT IDs per drug. Confidence scoring 0-100. Writes to Supabase `trials` table via service role key.

### Updated Files
- **`scripts/company_enrichment.py`** — Rebuilt as 7-step systematic intelligence pipeline (Step 1: entity discovery, Step 4: catalyst generation from CT.gov PCD dates, Step 5: company enrichment with vs_ailux/strategic_behavior/financing_history, Step 6: deal intelligence). Clear `# ══` section banners throughout. Model updated to `claude-sonnet-4-6`.
- **`.github/workflows/company-enrichment.yml`** — Renamed to "Intelligence Pipeline". Runs `ct_gov_sync.py` before `company_enrichment.py`. Added `skip_trial_sync` boolean input. Added `area=all` option that loops through all 6 areas. **Note: workflow file requires `workflow` scope token to push — update token at github.com/settings/tokens to push this file.**

### Architecture
- Central object: **Strategic Competitive Entity** (top-level competitive unit)
- Data quality tracked via `discovery_status` (`manual | auto | unverified | verified`) and `confidence_score` (0-100) on all trial/drug records
- Static data is always the fallback; dynamic pipeline takes over as records are populated and verified

---
## 2026-05-19 Static trial fallback in drug bubble popups — commit bc8fab0f

### Bug Fix — Drug Bubble Popup Trial Data
- **Root cause**: `_buildDrugPipelineRow` filtered `sbTrials` by `drug_id` but had no fallback when the Supabase `trials` table was empty — showed "Trial data loading" placeholder
- **Fix**: Added static fallback — when Supabase returns no trials for a drug, `prog.trials` (static data baked into `TL1A_PROGRAMS`) is used instead
- **Field normalization**: Static trial objects use `nct` field; popup code expects `t.id` for NCT links. Added `id: t.id || t.nct` normalization so `clinicaltrials.gov` links render correctly
- **Parity**: `_genericDetailHTML` already had this fallback for the expanded row trial section — this change makes the drug bubble popup consistent
- **Auto-upgrade**: Once the enrichment pipeline populates the `trials` Supabase table, live data takes over automatically (Supabase trials always preferred over static)

---
## 2026-05-18 Entity-grouped PI tables + Spyre expansion — commit 15026b546c

### Strategic Competitive Entity Architecture
- Added `entity_id`, `entity_name`, `entity_type` columns to `drugs` table (SQL migration)
- Seeded all 50 existing drug records with entity data — 39 distinct entities
- `entity_type` values: `platform` (multi-program company), `partnership` (cross-company deal), `standalone` (single asset), `licensed`
- Deleted duplicate records: `ro7837195` (= afimkibart INN) and `rese-cel` (= caba-201)
- Added 3 new Spyre programs: SPY002 (anti-TL1A, Ph2), SPY120 (anti-IL-23p19, Ph2), SPY130 (anti-α4β7, Ph2); SPY002 linked to TL1A area

### PI Table Renderer — `_makeAreaPI` Rebuilt
- Top-level rows now represent **strategic entities**, not individual drugs
- Platform/partnership entities show all programs as bubbles in expanded detail row
- Entity type badge (`Platform`, `Partnership`) appears in company column for multi-drug entities
- `_buildEntities()` groups drugs by `entity_id`; computes `bestStage`, `bestCls`, `bestOverlap` from most advanced program
- Filter pills now filter at entity level (entity passes if ANY of its programs match)
- Sort operates on `entity_name`, `bestStage`, `bestCls`, `bestOverlap`
- Column header renamed "Company" → "Entity"
- New CSS: `.pi-etype-badge`, `.pi-prog-bubbles`, `.pi-prog-bubble`, `.pi-drug-name-sm`, `.pi-stage-approved`

### Research Workflow
- New entities can be added by research team via INSERT into `drugs` with `entity_id/entity_name/entity_type` set — no code changes required

---
## 2026-05-18 Major platform restructure — commit 70f05dd9c5

### TL1A Tab
- Overlap badge system refactored: "Direct"/"high" → **High Overlap** (red), new **Indirect** (orange) for same-indication/different-target, **Watch** unchanged (yellow)
- Filter pills updated: removed "Adjacent"/"Same-Space", added "High Overlap" + "Indirect"
- `filter()` normalizer maps legacy overlap values to new taxonomy
- Added 4 Indirect competitors to `TL1A_PROGRAMS`: AbbVie/Skyrizi (IL-23), Lilly/Omvoh (IL-23), Takeda/Entyvio (integrin α4β7), AbbVie/Rinvoq (JAK1)
- Added "🤝 BD Activity" pill to left column — opens modal that lazy-loads `loadAreaBDActivity('tl1a')` on first open

### CSS Fixes
- Drug dropdown z-index: `.stock-card:hover { z-index:350 }` — drug popups now appear above fixed pill columns (z-index:300)
- AI Biotech card: `margin:0 16px 0` — matches side padding of ranking cards

### Drug Tab Restructuring (TSLP, IL-4Rα×TSLP, IL-4Rα×OX40L, IGF-1R×TSHR, FcRn, T-Cell)
- All 6 tabs now have left/right fixed pill columns matching TL1A layout
- Company list (cw-card) is primary center content
- Secondary content extracted to pill-triggered modals: Market Stats, BD Activity, Intel Feed, Drugs to Know
- Generic `openDrugModal(id)` + `_loadBdIntoModal(tabId, el)` functions
- `_showDrugPills(tid)` / `_hideDrugPills(tid)` wired into `registerTab` for all 6 tabs

### Search Bar Deep-linking
- Each search result (intel, deal, catalyst) now shows `→ [Tab]` navigation pill
- Clicking a result calls `_gsNavigate(areaId, type)` → switches to correct tab + opens relevant modal
- Source URLs moved to separate `↗` link (doesn't interfere with navigation)
- Area → tab mapping: `_GS_AREA_TO_TAB` + `_GS_TAB_LABEL` constants

---
## 2026-05-18 Industry Insights — collapsible intel feed + subtitle cleanup — commit 52c3f7fbfb

- BD Deal Tracker: removed subtitle "Reverse chronological · broad pharma + Ailux focus areas"
- Live Intelligence Feed: removed subtitle "Sourced from Meridian research pipeline · all focus are"
- Redesigned intel feed to compact rows: importance dot + area pills + headline + date + chevron
- Click to expand: `iiToggle(id)` toggles `.ii-item-detail.open` — shows body text + source link
- `event.stopPropagation()` on source links to prevent row collapse on link click
- Increased intel fetch limit from 20→40 rows (rows now compact)
- Added CSS classes: `.ii-item`, `.ii-item-row`, `.ii-item-dot`, `.ii-item-areas`, `.ii-item-headline`, `.ii-item-date`, `.ii-item-chevron`, `.ii-item-detail`, `.ii-item-detail.open`, `.ii-item-detail-body`, `.ii-item-detail-meta`

---
## 2026-05-18 Pharma Landscape — table width fix — commit e1eb07af6e

- Removed `max-width:1300px` from `.pi-two-col` — ranking tables now expand to full page width
- Added `table-layout:fixed;width:100%` via CSS to `#pi-tbl-cn` and `#pi-tbl-us` — no more horizontal scroll
- Added `overflow-x:hidden` to `.pi-scroll` to prevent bleed
- `#` column set to `width:3%` in both ranking tables — very narrow
- All other columns given explicit proportional widths so content distributes cleanly
- AI Biotech table: removed `min-width:900px` and `overflow-x:auto` wrapper — fills full page width cleanly

---
## 2026-05-18 Pharma Landscape — layout overhaul — commit 38093637

- Added `.pi-page-wrap` (max-width 1700px, centered) wrapping all pharma cards
- China + Global ranking cards: now side-by-side (`grid-template-columns: 1fr 1fr`), max-width 1300px, centered — tighter and easier to scan across
- AI Biotech card: `table-layout:fixed;width:100%` with proportional column widths — table fills full container width, rows shorter (less wrapping)
- `#` column header: `text-align:center` in both ranking tables
- `.pi-table` padding reduced (7px vs 8px), font 11.5px
- Thin scrollbar on `.pi-scroll`

---
## 2026-05-18 Home page — scrollable cards + wider layout + Essential Updates — commit 406ee273

### Card layout
- All `.home-card-body` elements now have `max-height: 340px; overflow-y: auto` — scroll inside the card, not the page
- `#bd-signal-body` same treatment
- `#meridian-reader-items` scrollable at 400px max-height with gold scrollbar
- `.content` padding reduced `24px → 10px` — cards extend nearly to viewport edges
- `.home-grid` changed to `grid-template-columns: 1fr` — catalysts full-width
- Top-5 items in Essential Updates get `.mr-top-item` highlight (faint yellow bg)

### Essential Updates (⚡ Essential Updates card)
- Now pulls from all 4 overnight pipeline sources in one parallel fetch:
  - `intel` — high/medium items from 10:30 PM + 2 AM research runs (40 rows)
  - `deals` — recent deal activity (15 rows, sorted by date)
  - `catalysts` — upcoming unresolved catalysts with countdown badges (20 rows)
  - `company_profiles` — today's enrichment updates with 🤖 pill (today only)
- Unified feed sorted by importance score + recency
- Top 5 highlighted; divider separates older items with count badge
- Type pills: IBD/Resp/etc area pill + Intel/Deal/Catalyst/🤖 Enriched type pill per row

---
## 2026-05-18 Overnight pipeline rescheduled — 10:30 PM → 5:30 AM — commits e3005e0b / 0e1973e9 / 37916f9f

### Full pipeline now runs while you sleep

| Step | Job | Time (ET) | Trigger |
|------|-----|-----------|---------|
| 1 | evening-update.yml | 10:30 PM | GH Actions `30 2 * * *` UTC |
| 2 | company-enrichment.yml | 12:00 AM | GH Actions `0 4 * * 1-6` UTC |
| 3 | meridian-research.yml | 2:00 AM | GH Actions `0 6 * * 1-6` UTC |
| 4 | the-meridian (Cowork) | 5:30 AM | Cowork `30 5 * * 1-6` local |

Each job has 60–90 min buffer before the next fires. Meridian writes the article from fresh research data, deploys to the dashboard before you wake up.

---
## 2026-05-18 Backend prep: schema migration v2 + enrichment pipeline + Meridian update — commit 076d15a2

### Overnight automation set up

**Supabase schema_migration_v2 (complete):**
- Created `company_profiles` table (company_id × area_id composite PK) with RLS + anon read + updated_at trigger
- Altered `drugs` (13 new columns), `trials` (3 new columns), `deals` (company_id FK + indexes)
- Created `company_area_detail` view with GRANT SELECT TO anon
- Inserted 6 missing program-level company rows (spyre-mono, spyre-230, xencor-942, xencor-412, mirador, lanova)
- Seeded 10 company_profiles rows for TL1A area
- Result: Migration v2 complete | 10 profiles seeded | 18 TL1A companies

**company-enrichment.yml schedule change:**
- Was: Sunday-only at 7 AM UTC (cron: `0 7 * * 0`)
- Now: Nightly Mon–Sat at midnight UTC (cron: `0 0 * * 1-6`)
- First manual enrichment run triggered immediately for area=tl1a

**Meridian SKILL.md updated:**
- Added Step 5: query `company_profiles` table and build `AREA_PROFILES` dict per area
- Old steps 5-10 renumbered to 6-11
- Meridian's 6:34 AM run tomorrow will incorporate AI-enriched company narratives

---
## 2026-05-18 CLAUDE_CONTEXT + TAB_REGISTRY isolation — commit 4c6de2a2

### Architecture guardrails: context embedding + tab isolation

**CLAUDE_CONTEXT block (index.html line 1):**
- Structured HTML comment at the very top of index.html, version-controlled alongside the code
- Documents: platform identity, Claude's roles, design principles, information hierarchy, Spyre Standard, CLASS×RELEVANCE framework, architecture rules, deploy conventions
- Ensures context is always present when the file is read, regardless of conversation history

**TAB_REGISTRY pattern (replaces hardcoded switchTab if-chains):**
- New `const TAB_REGISTRY = {}` + `registerTab(id, { onEnter, onLeave })` API
- Each tab self-registers its lifecycle hooks independently — editing one tab never touches `switchTab`
- `switchTab()` now dispatches through the registry with isolated try/catch per hook
- Errors in any tab's `onEnter`/`onLeave` are logged as `console.warn('[TAB:id:hook]', e)` — never propagated
- All DOM lookups use optional chaining (`?.`) — null elements never throw
- Current registrations: `meridian-issue`, `industry-insights`, `tl1a`
- Future tabs (tslp, il4ra, igf1r, fcrn, ace) register themselves when built — zero changes to `switchTab`

**Memory system updated:**
- `user_platform_context.md` — full product intent, Spyre standard, CLASS×RELEVANCE, architecture
- `feedback_claude_role.md` — working style, response format, code quality standards
- Both indexed in MEMORY.md so they load in every future session

---
## 2026-05-18 CLASS × RELEVANCE framework — commit a36d373f

### TL1A competitive table: two-dimensional company classification

**New dimensions:**
- **CLASS** (evolutionary sophistication): 1st Gen (mono antibody) | 2nd Gen (engineered/SC) | Next Gen (bispecific / dual-pathway)
- **RELEVANCE** (strategic overlap with Ailux): Direct | Adjacent | Same-Space | Watch

**Frontend changes (index.html):**
- New CSS pill classes: `pi-cls-1st` (blue), `pi-cls-2nd` (green), `pi-cls-next` (purple), `pi-overlap-direct` (red), `pi-overlap-adjacent` (orange), `pi-overlap-same` (teal), `pi-overlap-watch` (yellow)
- Filter bar updated: Class filter → All / 1st Gen / 2nd Gen / Next Gen; Relevance filter → All / Direct / Adjacent / Same-Space / Watch
- `_clsPill()` and `_ovBadge()` helpers rewritten with full 4-value support + legacy `'high'`/`'watch'` fallback
- All 10 TL1A_PROGRAMS entries reclassified: Sanofi (1st Gen / Direct), Spyre mono (2nd Gen / Direct), Xencor-942 (2nd Gen / Direct), Mirador (Next Gen / Direct), Simcere (Next Gen / Direct), Caldera (Next Gen / Watch), Earendil (Next Gen / Direct), Xencor-412 (Next Gen / Direct), Lanova (Next Gen / Watch), Spyre-230 (Next Gen / Direct)

---
## 2026-05-18 Async Supabase-fed company detail rows + enrichment pipeline — commits 41a73e9b / 9afb22d1

### Architecture: Dynamic expanded rows for all TL1A PI table companies

**Frontend — async Supabase loader (index.html commit 41a73e9b):**
- `toggle()` now fires async `_loadDynamicDetail(id, prog)` for any non-Spyre company being expanded
- Expanded rows show a loading spinner placeholder immediately; replaced with live Supabase data once fetched
- `_genericDetailHTML(prog, sbData)` renderer mirrors the Spyre layout: Platform Summary, BD Summary, Catalysts, Deal History, Active Clinical Trials, Key Risk, Why It Matters — in 2-column grid
- Falls back gracefully to static TL1A_PROGRAMS data if Supabase is unavailable
- `_profileCache` prevents repeat fetches when table re-renders (sort/filter)
- "🤖 YYYY-MM-DD" enrichment badge shows when data was last updated by the Claude API pipeline
- All Spyre rows unchanged — still use `_spyreDetailHTML()` with drug pill bubbles

**Backend — schema migration (schema_migration_v2.sql commit 9afb22d1):**
- New `company_profiles (company_id, area_id)` PK table: platform_summary, bd_summary, key_risk, why_it_matters, pipeline_url, research_sources, last_enriched_at
- ALTER `drugs`: added route, dosing_type, drug_format, is_combo, dosing_schedule, indication_short, phase_display, half_life_note, vs_ailux, color_hex, light_bg_hex, sort_order, sources_json
- ALTER `trials`: added trial_name, n_enrollment, pcd_label
- ALTER `deals`: added company_id FK + index
- `company_area_detail` helper view joining companies + company_profiles
- Seeded company_profiles for all 10 TL1A PI table companies from verified TL1A_PROGRAMS data
- RLS policies extended to new table

**Enrichment pipeline (scripts/company_enrichment.py commit e1ed36b3):**
- `python scripts/company_enrichment.py --area tl1a [--company sanofi] [--dry-run]`
- Per-company loop: fetch Supabase context → enrich trials via ClinicalTrials.gov v2 API → call Claude Sonnet → upsert results
- Outputs structured JSON: company_profile narrative, drug_updates, trial_updates, catalysts
- Writes to: company_profiles, drugs (detail cols), trials (display fields), catalysts (upcoming events)
- Estimated cost: ~$0.05 per company (~$0.50 per full TL1A area run)

**GitHub Actions — company-enrichment.yml (commit ec825e05):**
- Runs Sunday 2 AM ET (after weekday research.py runs)
- Manual trigger: choose area, optional company filter, dry-run flag
- Uses ANTHROPIC_API_KEY + SUPABASE_SERVICE_KEY secrets (already configured)

**To activate tonight:**
1. Run `schema_migration_v2.sql` in Supabase SQL editor to create tables + seed data
2. Trigger `company-enrichment.yml` manually in GitHub Actions → area: `tl1a`

---
## 2026-05-18 Critical Spyre data fix, inline edit + research validation — commit 27473ba2

### Critical data corrections (all verified against SEC 8-K Jan 2026 and ClinicalTrials.gov)

**Spyre pipeline was substantially wrong — now corrected:**
- SPY001: was "Anti-IL-23p19" → corrected to **Anti-α4β7** (same mechanism as vedolizumab/Entyvio but 3× longer half-life via YTE modification). Part A data April 2026: RHI -9.2pts primary endpoint met.
- SPY002: Anti-TL1A ✅ (name correct) but **cls changed 1st Gen → 2nd Gen** (YTE Fc modification = extended half-life engineering, same class as Xencor XmAb technology — user correctly flagged this)
- SPY003: was "TL1A × IL-23p19 bispecific" → corrected to **Anti-IL-23 monoclonal** (Phase 2, SKYLINE)
- SPY004: doesn't exist → removed
- Added **SPY072**: Anti-TL1A for RA/PsA/axSpA (Phase 2 SKYWAY trial NCT07148414; RA data Q3 2026, PsA/axSpA Q4 2026)
- Added **SPY120** (α4β7+TL1A), **SPY130** (α4β7+IL-23), **SPY230** (TL1A+IL-23) — all in SKYLINE Part B
- `spyre-003` table entry (TL1A bispecific — completely wrong) → replaced with **`spyre-230`** representing SPY230 TL1A+IL-23 combination arm

**Website URL corrected:** spyretherapeutics.com → **www.spyre.com/pipeline**

**Pipeline display in Spyre expanded row:**
- All 7 drugs shown as bubbles centered across top of card
- Full size: TL1A+IBD drugs (SPY002, SPY120, SPY230)
- Smaller/dimmed: IBD-only (SPY001, SPY003, SPY130) and Rheumatic-only (SPY072) — still fully hoverable
- Divider labels: "TL1A+IBD programs", "IBD non-TL1A", "TL1A/Rheumatic"
- Each bubble popup: summary card, 2-col detail grid, Ailux BD Lens, trials/proxy ref, verified sources

**Inline edit + Supabase research validation:**
- Double-click Drug, Target, or Class cell → inline input appears
- On Enter: row auto-expands; research panel slides in at top of expanded section
- Panel queries Supabase `companies` (insight_text, ailux_angle) and `intel_companies` for stored intel
- Text-match validation: if proposed new value found in stored intel → "✅ Consistent"; else → "⚠️ Queued for deep research"
- Proposed edit written to Supabase `pi_user_edits` table (async) for overnight research pipeline pickup
- "Apply Change Locally" button updates TL1A_PROGRAMS in-memory and re-renders table
- CSS: `.pi-editable` hover hint (✏), `.pi-edit-validation` panel with pending/supported/conflict states

---
## 2026-05-18 TL1A tab: blinking intel dot, 3-col layout, redesigned Spyre hover cards — commit 46a77ab2

### What was changed

**Blinking green dot for companies with no intel:**
- `_loadIntelStatus()` now called in `tl1aPI.init()` on page load
- Queries Supabase `intel_companies → companies(ticker)` to find which companies have any intel records
- Companies not found get a `<span class="pi-no-intel-dot">` — slow green pulse animation next to their name
- `@keyframes pi-dot-blink` with box-shadow pulse, 2.8s cycle; tooltip: "No intel on record yet — flagged for auto-research"

**TL1A tab 3-column layout (pill buttons + centered PI card):**
- `.tl1a-layout` CSS grid: `148px 1fr 148px` with sticky side pill columns
- Left pills: 📡 Intel Feed, 📅 Catalyst Calendar, 📐 Estimand Guide
- Right pills: 🧬 Ailux Profile, 💊 IBD Market, 🔬 China Programs, 🎯 BD Takeaways, 📖 IBD History
- Each pill opens a `.tl1a-modal-overlay` with full card content; `openTl1aModal()` / `closeTl1aModal()` JS functions
- Escape key closes all open modals; clicking overlay backdrop closes panel
- `#tl1a-pi-card` with `!important` overrides Pharma Intel tab's global `.pi-card` margin conflict

**SPYRE_PIPELINE redesign:**
- Added `sources[]` array to each drug with labeled verification links
- SPY001 sources: spyretherapeutics.com/pipeline, NCT07012395, Endpoints News data readout
- SPY002 sources: spyretherapeutics.com/pipeline, NCT07012395, NCT06672718
- SPY003 sources: spyretherapeutics.com/pipeline, NCT07012395 (combo arm proxy)
- SPY004 sources: spyretherapeutics.com/pipeline
- Added `comboRef` field to SPY003: SKYLINE combination arm as proxy trial data reference
- Combo drug names now use × symbol: "TL1A × IL-23p19", "IL-6 × IL-23p19"

**Spyre hover popup redesign (per-drug buttons):**
- Removed "COMBO" badge — combo drugs now show target pair (e.g., "TL1A + IL-23p19") as subtitle under drug code
- New summary card at top of each popup: drug code, name, phase badge, indication (distinct colored background)
- 2-column detail grid: left = Drug Details (format/stage/half-life/dosing/target); right = Mechanism & Context
- Ailux BD Lens section: full-width yellow highlight block
- Trials section: Active Trials with NCT links for mono drugs; "Proxy data" amber block for SPY003 (SKYLINE combo arm)
- SPY004 (no trials registered): "No trials registered — IND in progress" note
- 🔗 Sources section at bottom of each popup with all verification links
- Popup CSS: fixed 340px width, max-height 80vh with overflow scroll

---
## 2026-05-18 TL1A tab: polish pass — color pills, clean header, Spyre card enrichment — commit ff124220

### What was changed

**Header cleanup:**
- Removed TOP BAR div (molecule title "TL1A × IL-23p19 · IBD (UC / CD)" + "Competitive intelligence · Live from Supabase · Updated May 2026")
- Removed `⚔ Program Intelligence · All TL1A Companies & Drugs` pi-title span
- Moved Biology Deep Dive button into the pi-hd alongside the filters

**Color-coded filter pills with group labels:**
- Added `.pi-pill-lbl` (grey uppercase label before each group)
- Class group: blue (#2563eb active/hover)
- Stage group: purple (#7c3aed active/hover)
- Relevance group: crimson (#dc2626 active/hover)
- Labels: "Class", "Stage", "Relevance"

**Spyre SPYRE_PIPELINE enrichment:**
- Added `isCombo`, `indication`, `trials[]` fields to each drug entry
- SPY001/SPY002: `indication: 'Ulcerative Colitis (UC)'`; SPY003: `UC / CD (planned)`; SPY004: `Crohn's Disease (CD)`
- SPY002 has 2 trials (NCT07012395 SKYLINE + NCT06672718 Phase 1); SPY001 has SKYLINE
- SPY003/SPY004 flagged `isCombo:true` → show red "COMBO" badge on pipeline button

**Spyre hover card popup improvements:**
- Shows disease indication (`📍 d.indication`)
- Shows "Active Trials" sub-section with NCT links, status, phase, N, PCD
- TBD half-life/dosing tags hidden for Pre-IND/Preclinical drugs

**Links everywhere in Spyre expanded row:**
- Catalysts: url field added to all 3 entries (CT.gov or spyretherapeutics.com); rendered as `↗` hyperlinks
- Deals: url field added; rendered as `↗` hyperlink
- Website: `spyretherapeutics.com ↗` link in expanded row header
- "hover each drug to explore" label removed
- Combo drugs (SPY003, SPY004) get a red "COMBO" chip on their pipeline button

---
## 2026-05-18 TL1A tab: compact PI card, pill filters, Spyre rich row — commit 3ef77a9f

### What was changed

**Program Intelligence card layout:**
- `.pi-card` now `max-width:1100px;margin:0 auto 20px` — centered and constrained
- Table `min-width` reduced from 700px → 620px; `_colWidths` from `[220,150,100,90,80,80]` → `[175,130,85,80,75,75]`
- `.pi-table th` padding: `8px 10px` → `6px 8px`; `.pi-table td` padding: `9px 10px` → `7px 8px`

**Filter pill buttons:**
- Replaced three `<select>` dropdowns with `.pi-pill-group` + `.pi-pill` button groups
- Groups: Class (All / 1st Gen / 2nd Gen / Direct), Stage (All / Ph 3 / Ph 2 / Ph 1 / Pre-IND / Preclinical), Relevance (All / High Overlap / Watch)
- Added `piPillClick()` global function; updated `tl1aPI.filter()` to read active pill `data-val`
- CSS: `.pi-pill`, `.pi-pill.active`, `.pi-pill:hover`, `.pi-pill-divider`

**Spyre rich expanded row:**
- `SPYRE_PIPELINE` const: 4 drug entries (SPY001–SPY004) with target, format, phase, half-life, dosing, mechanism, Ailux BD Lens
- `_spyreDetailHTML(p)`: renders header (SYRE stock chip with live price/arrow from Supabase), pipeline drug buttons with hover popup cards, 2-col grid (summary, trials, catalysts, deals, risk, diff)
- `_loadSpyreStock()`: async Supabase fetch of `companies` table for SYRE; populates price + direction arrow on expand
- `_renderTable()`: routes Spyre (id=`spyre-mono`) to `_spyreDetailHTML()`, all others to standard detail
- CSS: `.spyre-hd`, `.spyre-stock-chip`, `.spyre-drug-btn`, `.spyre-drug-popup`, `.spyre-popup-*`, `.spyre-section-lbl`

---
## 2026-05-18 Bug fix: loadAreaCompanies / loadAreaDrugs undefined — commit cd5a122

### What was fixed

**Root cause:** `loadMoleculeTab()` called `loadAreaCompanies(tabId)` and `loadAreaDrugs(tabId)` but neither function was defined anywhere in the file. Every molecule tab navigation (TSLP, IL-4Rα, IL-4Rα/OX40L, IGF1R/TSHR, FcRn) threw a `ReferenceError` on load, preventing `loadAreaBDActivity` from running and leaving all molecule tabs blank.

**Fix:** Added both functions as async stubs in the head script block (before `loadMoleculeTab`). Each function checks for its target element (`tabId + '-companies'` / `tabId + '-drugs'`) and returns early if not found — so no visible change on current tabs, but the `ReferenceError` is resolved and all molecule tab content now renders correctly.

---
## 2026-05-18 Bug fix: dead TL1A Grid.js containers in initGrids — commit 27d653e

### What was fixed

**Root cause:** The TL1A redesign removed `#grid-tl1a-landscape` and `#grid-tl1a-tech` container divs, but `initGrids()` still called `.render()` on both. Grid.js throws `Container element cannot be null` synchronously, halting `initGrids()` before any TSLP, IL-4Rα, or other molecule tab grids could initialize — leaving all Drugs to Know and molecule tabs blank.

**Fix:** Removed both dead grid initialization blocks (`grids.tl1aLandscape` and `grids.tl1aTech`) from `initGrids()`. Replaced with a comment noting they were superseded by the `tl1aPI` Program Intelligence table.

---
## 2026-05-18 TL1A tab full redesign (Tasks #97–#99) — commit 1ee24b80

### What was changed

**Removed from TL1A tab:**
- Top stat bar (UC/CD prevalence, biologic failure rate, etc.) — moved biology context to deep dive modal
- Companies to Watch card (hardcoded 7 companies)
- Drugs to Know card (hardcoded 14 drugs, now unified)
- Separate competitive landscape card (tl1a-live-competitive-card)
- Separate BD activity card (tl1a-bd-activity)
- Live Meridian Updates card (tl1a-live-intel-card)
- Static "Latest Field Intelligence" card (tl1a-intel-anchor)
- Deal Spotlight card (most recent transaction)
- Deals by Total Value chart
- Competitive Analysis section (redundant with new table)
- Bispecific Technical Deep-Dive section (content now in expandable row detail panels)
- Related News & Precedent Transactions section (now in unified intel feed)
- Inline Biology Deep-Dive edu-section (moved to modal)

**Added to TL1A tab:**
- **Biology Deep Dive button** (top-right): small green card-button that opens a full-screen modal with all TL1A biology content (TL1A/DR3 mechanism, IBD disease biology, TL1A×IL-23 synergy, IBD drug dev endpoints). ESC to close.
- **Unified Program Intelligence Table** (`tl1aPI` object, `#pi-tl1a-wrap`):
  - 13 companies with full data: Roche, Merck, Sanofi/Teva, Spyre (mono), Xencor (XmAb942), Mirador, Simcere/BI, Caldera/Qyuns, Earendil/Helixon, Xencor (XmAb412), LaNova/Zymeworks, Spyre (SPY003), Episcience
  - Classifications: **1st Gen** (monospecific TL1A mAb), **Direct** (exact TL1A×IL-23p19 bispecific = direct Ailux competitors), **2nd Gen** (enhanced mono, e.g. Xencor's XTEND extended half-life)
  - Filter by Classification, Stage, Relevance (High Overlap / Watch)
  - Sortable columns (Company, Drug, Target, Class, Stage, Relevance)
  - Resizable columns (drag right edge of any column header)
  - Expandable rows: click any row to reveal Summary, Upcoming Catalysts, Deal History, Key Risk, Why It Matters/Differentiation
- **Live Intel Feed** (`loadTL1AIntelFeed()`): queries Supabase `intel_areas` for `area_id='tl1a'`, then fetches matching `intel` rows ordered by date — single unified chronological stream of deals, clinical, regulatory, and news items
- Tab load: `tl1aPI.init()` and `loadTL1AIntelFeed()` called when TL1A tab is opened via `switchTab()`; also initialized on `DOMContentLoaded`
- Updated TOC_MAP for `tl1a`: Program Intelligence, Intel Feed, Ailux Profile, Estimand Guide, Catalyst Calendar, IBD Market & SOC, Chinese Programs

**Kept (unchanged or lightly trimmed):**
- Ailux Asset Profile (with deal valuation estimates)
- Estimand Intelligence card
- Catalyst Calendar (live from Supabase, tl1a-live-catalysts)
- IBD Market & Standard of Care (collapsible)
- BD Intelligence Key Takeaways (insight-box)
- China Domestic Read-Through
- IBD Target History (collapsible)

---
## 2026-05-18 Supabase intel submission + centered search bar (Tasks #94–#95) — commit 8f01318

### What was changed

**Supabase intel submission (Task #94):**
- Added `INTEL_TAG_AREA` map: tag label → Supabase `area_id` (IBD→tl1a, Resp→tslp, Type 2→il4ra, AD→il4ra, TED→igf1r, AI→fcrn, Immune Reset→tcell)
- New `_saveIntelToSupabase(url, text, tag)` async helper: inserts to `intel` table with `intel_type='user_submitted'`, `importance='medium'`, `source_name='User Submission'`; then inserts to `intel_areas` junction table for non-General tags
- Both `saveFromModal()` (modal submit) and `submitIntel()` (inline panel submit) now call `_saveIntelToSupabase()` alongside the existing localStorage write
- localStorage retained as a local backup; Supabase is the persistent record for the next research update cycle

**Centered header search bar (Task #95):**
- `.header-search-wrap` changed from `flex: 1` flow layout to `position: absolute; left: 50%; transform: translateX(-50%)` with `width: clamp(280px,36%,540px)`
- Search bar is now truly centered in the header regardless of unequal left (title) and right (buttons) column widths
- Mobile override (line ~694) retains `order: 3; flex-basis: 100%` so the bar drops to its own row on narrow screens

---
## 2026-05-18 Nav fix + home tab cleanup + dynamic Meridian Reader (Tasks #87–#90) — commit 2674800

### What was changed

**Tab navigation fix (Task #87):**
- Root cause identified: the home tab HTML block had 1 more `</div>` than `<div>` openers, causing it to consume the `.content` wrapper's closing tag
- The orphan `</div><!-- end tab-home inner -->` (left over from earlier content removals) was removed
- Home tab section now perfectly balanced: 48 opens, 48 closes, depth returns to 0
- All subsequent tabs (`tab-industry-insights`, drug tabs, etc.) are now correctly inside `.content` at the same DOM level as the home tab

**Remove Key Concepts card (Task #88):**
- Removed the entire "Key Concepts — What to Know Across Coverage Areas" card (`id="learning-anchor"`) from the home page
- Card contained 6 hardcoded concept mini-cards for IBD, Resp, Type 2, TED, FcRn, Immune Reset
- Removed stale `learning-anchor` and `ailux-pipeline-anchor` entries from TOC_MAP; replaced with `bd-signal-panel` entry

**Dynamic Meridian Reader card (Task #89):**
- Yellow top-of-home card now loads live from Supabase `intel` table instead of 7 hardcoded items
- New `loadMeridianReader()` function: queries top 20 high/medium importance intel by date, joins `intel_areas` for area labels, prioritises `importance = 'high'`, takes top 7
- Area-aware pill styling: `MR_AREA_STYLE` maps area_id → color/label (IBD, Resp, Type 2, TED, FcRn, Immune Reset); falls back to `MR_TYPE_STYLE` for intel_type (deal, clinical, regulatory, etc.)
- Called in `DOMContentLoaded` alongside other home tab loaders

**Key Watch pill under date (Task #90):**
- `KEY WATCH` pill moved from the right-side pill group to below the date text in the left 80px column of catalyst rows
- High-significance rows now show: date (top-left) → KEY WATCH badge (below date) → label/notes (center) → countdown + significance/area pills (right)

---
## 2026-05-18 Pharma sort/filter + 8-across stock grid (Tasks #79–#80) — commit 122b5cd

### What was added

**Pharma Landscape table sort + filter (Task #79):**
- Both China and Global pharma tables now have clickable sortable column headers with ↑/↓ indicators
- China table: sort by Company (alpha), Mkt Cap, Revenue, R&D Spend, R&D %, TA #1, TA #2
- Global table: sort by Company (alpha), Mkt Cap, Revenue, R&D, R&D %, TA #1, TA #2
- Numeric parser handles `~$60B`, `$700B`, `~$3.9B`, `29%`, `<1%` etc.
- Sort moves paired `pi-main-row` + `pi-dr-row` together as a unit (expanded details follow their row)
- Filter search bar above each table — searches all visible text (company, TA, type, notes) and hides non-matching row pairs

**Market & Learning stock cards 8-across (Task #80):**
- Changed `.stock-cards-grid` from `repeat(auto-fill,minmax(310px,1fr))` to `repeat(8,1fr)` for consistent 8-across layout
- Uniform gap on all sides between cards (no margin/padding asymmetry)

---
## 2026-05-18 Home tab enhancements + pipeline intel_companies (Tasks #65–#69) — commit d227118

### What was added

**Drugs to Know — rich expandable dropdowns (Task #65):**
- Every drug row now expands on click to reveal a detail panel: class/mechanism, stage, key trials, primary endpoints, differentiation insight, key risk, and live Supabase data (trial data + Ailux BD signal)
- `dknLoadSbData()` fetches the Supabase `drugs` table at page load and caches it in `_dknSbMap` for fuzzy matching
- Default filter changed from "All" to "◈ Ailux Focus" — shows only drugs relevant to Ailux's 6 coverage areas

**BD Signal panel on home tab (Task #66):**
- New `◈ BD Signal` card between catalysts and deals on the home tab
- `loadBDSignal()` fetches top 5 recent deals (prioritizing deals with ailux_signal), renders synthesized intelligence cards with area badge, deal value, parties, headline, and the Ailux BD Signal commentary

**Catalyst countdown badges (Task #67):**
- `catDaysTag(sort_date)` helper added — computes days to each catalyst event
- Badges auto-color: red "TODAY", red "Nd" (≤7 days), yellow "Nd" (≤30 days), grey "Nd" (>30 days), "Nd ago" for resolved
- Each open catalyst card now shows the countdown badge inline

**Company watchlist enrichment — Supabase (Task #68):**
- UCB: full rozanolixizumab/Rystiggo profile + FcRn competitive angle
- Cullinan: CLN-978 CD19×CD3 TcE detail + dual lineage BCMA differentiation narrative
- Pfizer: insight_text added (PF-07261271 + Telavant position)
- Roivant: full Telavant/afimkibart origin story + $7.25B benchmark
- J&J: nipocalimab expanded; daratumumab autoimmune parallel noted
- Regeneron: Dupixent $13B benchmark + itepekimab COPD AERIFY read-through

**research.py — intel_companies junction writes (Task #69):**
- `get_company_map()` fetches all companies from Supabase at startup; builds lowercase name → id lookup with 20+ aliases (J&J, Roche/Genentech, Eli Lilly, etc.)
- `resolve_company_id()` does exact then substring fuzzy match
- `write_to_supabase()` now accepts `company_map` and writes `intel_companies` rows for every company Haiku extracts in `company_names`
- Pharma tab `loadAreaIntel` can now be extended to filter intel by company_id — the data pipeline is ready

---
## 2026-05-18 Dashboard audit + fixes (Tasks #61–#64) — commit bc48040

### What was fixed
**BD Activity section on all 7 molecule tabs:**
Previously only TL1A had the BD Activity section. Added placeholder + JS wiring to TSLP, IL-4Rα × TSLP, IL-4Rα × OX40L, IGF1R × TSHR, FcRn, and ACE tabs.

**Stock prices column mismatch fixed:**
`scripts/stock_prices.py` was writing to `stock_change_pct` and `price_updated_at` — neither column exists in Supabase. Corrected to `stock_change` and `last_price_update`. Prices will now update correctly at 10 AM ET daily via GitHub Actions.

**27 companies seeded with current prices:**
Used yfinance to seed current stock prices for all public tracked companies. Market tab now shows live prices immediately.

**Duplicate T-cell deal removed; 8 new landmark deals seeded:**
- FcRn: J&J/Momenta $6.5B acquisition (nipocalimab), argenx/Halozyme ENHANZE collaboration, HanAll/Immunovant batoclimab license
- IGF1R: Amgen/Horizon $27.8B acquisition (Tepezza), River Vision/Horizon teprotumumab rights
- IL-4Rα: AZ/Aiolos Bio $1.06B acquisition (AIO-001 long-acting anti-TSLP), Apogee $200M Series B (APG279 IL-4Rα×TSLP bispecific)
- TSLP: AZ/Aiolos duplicate (long-acting TSLP perspective)

---
## 2026-05-18 GitHub Actions pipeline (Tasks #59–#60) — commits 0255a3f + c676af0

### What was built
Full automated background pipeline — runs on GitHub's servers, no computer needed, no Cowork needed.

**Scripts added:**
- `scripts/research.py` — RSS feed aggregator (10 feeds, 6 focus areas), Claude Haiku extraction, writes to Supabase `intel`/`intel_areas`/`deals`/`catalysts`
- `scripts/write_meridian.py` — reads Supabase intel, calls Claude Sonnet to generate HTML briefing, commits `meridian_today.html` to GitHub Pages
- `scripts/stock_prices.py` — yfinance price fetch for all tracked companies, upserts to Supabase `companies`
- `scripts/requirements.txt` — feedparser, anthropic, requests, yfinance, pynacl

**Workflows added:**
- `.github/workflows/meridian-research.yml` — 4 AM ET Mon–Sat (09:00 UTC)
- `.github/workflows/meridian-write.yml` — 6:30 AM ET Mon–Sat (10:30 UTC)
- `.github/workflows/stock-prices.yml` — 10 AM ET daily (14:00 UTC)
- `.github/workflows/evening-update.yml` — 7 PM ET daily (23:00 UTC)

**GitHub Actions secrets (all set):** ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY, GH_DEPLOY_TOKEN

**Test run:** Meridian Research #1 — Success, 42s

**New token:** `bd-actions-workflow-deploy` (repo+workflow, no expiry) stored at `.github_token_workflow`

---
## 2026-05-18 Meridian Issue layout fix + SKILL.md CSS update (Tasks #56–#57) — commit 818325b

### Changes
- `index.html`: Meridian Issue tab now wraps iframe in a card (max-width 880px, centered, white card on #edf1f7 grey background, 10px border-radius, box-shadow)
- `meridian_today.html`: body changed from `max-width:100%; margin:0` to `max-width:780px; margin:0 auto` so content and tables sit at a readable width
- `the-meridian` scheduled task SKILL.md: CSS template body line updated to match — future issues will generate with constrained width automatically

---
## 2026-05-18 TL1A BD Activity Section (Tasks #53–#55) — commit 765ed56

### Data seeded (12 TL1A deals, 9 new companies, 2 new drugs)
**Key deals:** Prometheus→Merck $10.8B (tulisokibart), Telavant→Roche $7.25B (afimkibart), Roivant→Roche $7B (afimkibart), Teva/Sanofi $1.5B (duvakitug), AbbVie/FutureGen $1.71B (FG-M701), Earendil/Sanofi $1.85B (HXN-1003), Simcere/BI €1.04B (SIM0709), plus Qyuns/Caldera, Pfizer/Roche PF-07261271 (option + co-dev), Roche/Chugai Japan rights
**New companies:** earendil, chugai, futuregen, telavant, roivant, prometheus, vant, caldera, pfizer
**New drugs:** pf07261271 (Pfizer IL-12p40/TL1A BsAb), fg-m701 (AbbVie TL1A mAb from FutureGen)

### BD Activity UI — `loadAreaBDActivity(tabId)`
- Live-query all deals for the area (no limit — full history)
- **Summary bar**: deal count, disclosed total value, acquisition/license breakdown, year range
- **Filter bar**: All / Acquisition / License / Collab / Option type buttons + inline search
- **Compact rows**: Year | From→To | Drug tag | Type badge (color-coded) | Value | Stage-at-deal
- **Click to expand**: full detail text, milestone info, region, Ailux Lens box, source link
- Section minimizable via header click
- Added CSS: `.bda-section`, `.bda-row`, `.bda-compact`, `.bda-detail`, `.bda-ailux-box`, animation
- Wired into `loadMoleculeTab()` — fires for all tabs (only renders where `#tabId-bd-activity` div exists)
- HTML placeholder added to TL1A tab (between competitive landscape and intel card)
- Pattern established for other 5 areas: add `#tabId-bd-activity` div to any tab to activate

---
## 2026-05-18 TL1A Competitive Landscape Expansion (Tasks #50–#52)

### Source: Competitive product analysis slide (IL-23 × TL1A bispecifics)
**Before:** 7 TL1A drugs in Supabase (tulisokibart, duvakitug, afimkibart, SIM0709, HXN-1003, ABS-101, AbbVie TL1A mAb)
**After:** 22 TL1A drugs — 15 new programs added

### New drugs inserted (all linked to `tl1a` area):
| ID | Name | Company | Stage | Direct? |
|---|---|---|---|---|
| ro7837195 | RO7837195 | Roche/Genentech/Pfizer | Phase 2 | ✓ |
| hy8931 | HY8931 | Newsoara Biopharma | Phase 1 | ✓ |
| qx030n | QX030N | Qyuns/Caldera | Phase 1 | ✓ |
| hbm2001 | HBM2001 | Harbour BioMed | Preclinical (IND) | ✓ |
| sab06 | SAB06 | Santa Ana Bio | Preclinical | ✓ |
| lbl053 | LBL-053 | Nanjing Leads Biolabs | Preclinical | ✓ |
| pr203 | PR203 | Shandong BoAn | Preclinical | ✓ |
| xmab412 | XmAb412 | Xencor | Preclinical | ✓ |
| lq080 | LQ080 | Shanghai Novamab | Preclinical | ✓ |
| generate-uc | Generate UC TL1A/IL-23 | Generate:Biomedicines | Preclinical | ✓ |
| cantai-tl1a | Cantai TL1A/IL-23 | Cantai Therapeutics | Preclinical | ✓ |
| spy230 | SPY230 | Spyre/Paragon | Preclinical | ✓ |
| lq082 | LQ082 | Shanghai Novamab | Preclinical | ✓ |
| es302 | ES302 | Elpiscience Biopharma | Preclinical | ✓ |
| spx306 | SPX-306 | Sparx Therapeutics | Preclinical | ✗ (oncology) |

### New companies inserted (12):
harbourbiomed, santaana, leads, shboan, xencor, helixon, novamab, cantai, spyre, elpiscience, sparx (newsoara was already present)

### meridian-research search terms updated:
- Area 1 now has 20 targeted search strings covering all tracked TL1A programs
- Drug-company attribution section updated with all 15 new pairings + confusion-prone notes
- RO7837195 vs afimkibart distinction explicitly noted (different drugs, both Roche but different targets)
- SIM0709 licensor/licensee split documented (Simcere originator / BI ex-China)

---
## 2026-05-18 Global Search → Supabase (Task #49)

### Deploy: commit 305d171
- **Problem:** `globalSearch()` filtered static DOM content only — all intel, deals, and catalysts in Supabase were invisible to search
- **Fix:** Added `_gsSbSearch()` async function that fires parallel Supabase queries (intel, deals, catalysts) debounced 280ms after the user stops typing
- **UI:** Floating dropdown panel (`#gs-sb-panel`) positioned below the search bar; sections for Intel (≤8), Deals (≤5), Catalysts (≤5 unresolved); type/area badges; clickable items open source URLs in new tab
- **Highlight:** Matched term highlighted in dropdown results with `<mark class="gs-hl">` styling
- **Close behaviour:** Panel hides on click outside the search wrap, on clear, or when term drops below 2 characters
- **DOM search unchanged:** Existing static-content filtering continues to run in parallel
- `data-ts` refreshed to 1779112306

---
## 2026-05-18 Full Dashboard Live-Data Wiring (Tasks #42–#47)

### Deploy: commit fdbd54a — 8 changes in one shot
- **Restored `loadAreaCompanies` + `loadAreaDrugs`** to all molecule tabs — Companies to Watch and Drugs to Know sections now render live from Supabase `company_areas`, `company_signals`, `drug_areas`, `drugs` tables
- **Industry Insights tab** replaced: removed ~2MB of static hardcoded HTML articles; replaced with 30-line dynamic shell populated by new `loadIndustryInsights()` function querying `intel` table (limit 300, order by `intel_date` desc)
- **Industry Insights stat bar** added: shows total items, deals, clinical entries, BD items, and date range — all computed from Supabase at load time
- **Home stat bar** added at top of `tab-home`: live counts for companies tracked, drugs tracked, intel items, upcoming catalysts
- **Submit Intel → Supabase**: `saveFromModal()` now writes to `intel` table (`verified=false`) in addition to localStorage; morning task can review and confirm
- **`header-date` fix**: JS-computed dynamically on page load (always shows today's date)
- **`data-ts` refreshed**: reset to current Unix timestamp; all task prompts updated to refresh on every deploy
- **`DOMContentLoaded`** updated to call `loadHomeStats()` and `loadIndustryInsights()` on every page load
- **Size reduction**: index.html shrank from ~2.75MB to ~765KB (72% reduction) by removing static Industry Insights content

### Task #46: meridian-evening-update skill updated
- Added STEP 5: drug stage patching (mirrors meridian-research STEP 5b)
- Fixed blob API fetch pattern (was using Contents API which truncates large files)
- Added `data-ts` refresh in STEP 6 deploy
- Updated architecture notes: Companies to Watch, Drugs to Know, Competitive Landscape, Industry Insights all now Supabase-driven (do not edit HTML directly)

### Task #47: bd-dashboard-weekly-update skill updated
- WEEKLY TASK 5 (validate drug data) now includes explicit stage PATCH pattern with exact stage values
- Added `ailux_competes_directly` flag review instruction
- Fixed blob API fetch pattern throughout
- Added `data-ts` refresh to WEEKLY TASK 6
- Updated architecture notes

---
## 2026-05-18 Header Timestamp Fix + New Area Onboarding Runbook

### Header "Last Updated" — now always current
- **Problem:** `header-date` was hardcoded "Saturday, May 16, 2026" in HTML; `data-ts` was a stale Unix timestamp
- **Fix 1 (one-time):** Cleared static text from `<strong id="header-date">` — JS now computes and writes today's date on every page load
- **Fix 2 (one-time):** Reset `data-ts` to `int(time.time())` (May 18 2026, ~7:01 AM)
- **Fix 3 (ongoing):** Updated `meridian-morning-update` task to refresh `data-ts` on every deploy — "Last updated" will always reflect the most recent 7 AM run
- **Deployed:** 8cd4515

### New area onboarding runbook created
- **Task:** `onboard-focus-area` (manual/ad-hoc, no cron schedule)
- **Location:** `/Users/kyleklaassen/Documents/Claude/Scheduled/onboard-focus-area/SKILL.md`
- **Covers 9 steps:** research pass → seed companies → seed drugs (with `drug_areas` link) → seed catalysts → seed intel → update meridian-research search terms → add dashboard tab → update the-meridian content architecture → verify + log
- **Key rules:** every drug verified against primary source before insert; `ailux_competes_directly` flag set explicitly; smaller biotech programs treated with same priority as pharma
- **Invoke:** manually from the Scheduled sidebar when a new focus area is added

---
## 2026-05-18 Pipeline Hardening — Drug Stage Auto-Update + Competitive Snapshot at Write Time

### Task #36: meridian-research — auto-patch drug stages (STEP 5b added)
- Research task now PATCHes `drugs.stage` in Supabase when a phase advance is confirmed by primary source
- Stage values: `Approved | BLA Filed | Phase 3 | Phase 2/3 | Phase 2 | Phase 1/2 | Phase 1b | Phase 1 | Preclinical`
- Rules: GET first to confirm drug_id, primary source required, two-source rule for demotions
- Stage updates logged in research notes file with `⚡ Stage updated:` marker
- Keeps competitive landscape table current without manual intervention

### Task #37: the-meridian — Supabase competitive context at write time (Step 3 added)
- Writing task now queries `drug_areas → drugs → companies` at the start of each run (before drafting)
- Builds `AREA_DRUGS` dict keyed by area_id, sorted by phase, flagged 🔴/🟡 by `ailux_competes_directly`
- Writer cross-checks competitor stage claims against live Supabase data (not just stale notes)
- Explicit instruction: if research notes mention a stage change not yet in Supabase, note it in the section narrative
- Both tasks updated via `update_scheduled_task`

---
## 2026-05-18 Architecture Overhaul — Research Pipeline + Meridian Issue + Pharma Intel

### 1. Research pipeline consolidated (meridian-research task)
- **Before:** `meridian-research` (4 AM) wrote notes only; `meridian-morning-update` (7 AM) did all Supabase writes
- **After:** `meridian-research` now does both — writes verified intel/deals/catalysts to Supabase AND saves the structured notes file organized by the 6 dashboard areas (TL1A, TSLP, IL-4Rα, IGF1R, FcRn, T-cell)
- `meridian-morning-update` is now lightweight: late-breaking sweep only + Meridian reader widget update
- Net result: Supabase gets populated 3 hours earlier each morning

### 2. Meridian Issue restructured — area-led (the-meridian writing task)
- **Before:** broad biopharma newsletter format (general landscape news, conference recaps)
- **After:** every issue is organized around the 6 dashboard focus areas — each content section maps to one area (TL1A, TSLP, IL-4Rα, IGF1R, FcRn, T-cell Engineering)
- JHU concept is now load-bearing (tied to a specific story), not appended generically
- No broad market recaps unless directly relevant to one of the 6 areas
- Writing task now explicitly skips areas with no new verified news (no padding)
- Schedule: 6:30 AM Mon–Sat (unchanged)

### 3. Pharma Intel tab — live Supabase intel injection
- Added `injectPharmaIntel()` JS function that runs on page load
- Fetches Supabase `intel_companies` JOIN `intel` for last 30 days, filtered to 35 pharma companies shown in the tab
- Maps Supabase `company_id` → piToggle slug (e.g. `merck` → `us-merck`, `abbvie` → `us-abbvie`)
- Injects a blue "🔴 Live Intel" section at the top of each company's expandable drawer
- Static financial data (market cap, revenue, R&D %, TAs) stays as-is — live intel prepended above it
- Deployed: commit fedfb07

---
## 2026-05-18 Pre-morning QA — PASS (0 issues found) — see qa_report_20260518.md

---
## 2026-05-18 Meridian Issue Tab — wired and live
- **Tab:** dedicated 📰 nav button → `tab-meridian-issue` with `<iframe>` loading `meridian_today.html` from GitHub Pages
- **Root cause fixed:** `the-meridian` task was saving HTML to The Meridian workspace but deploy script read from BD Platform (wrong path) — token was also missing from The Meridian folder
- **Fixes applied:**
  - Copied `.github_token` to The Meridian workspace
  - Updated `the-meridian` scheduled task prompt — deploy now reads from `/mnt/The Meridian/meridian_today.html` (correct workspace) and deploys via GitHub Contents API
  - Deployed today's issue manually (Monday, May 18, 2026) — verified live in browser
- **From tomorrow:** every 5 AM run auto-deploys the new issue; dashboard tab always shows the current day

---
## 2026-05-18 Morning Intelligence Update
- **Searched:** TL1A/IBD, TSLP/IL-33/Respiratory, IL-4Rα/Atopy, IGF1R/TED, FcRn/Autoimmune, T-cell Engineering/ACE, BD Deals
- **Intel written to Supabase:** 9 items with area tags
  - `tslp`: AZ tozorakimab OBERON+TITANIA Ph3 positive (Mar 27), MIRANDA Ph3 positive (Apr 20)
  - `igf1r`: Amgen SC Tepezza Ph3 positive — 77% proptosis response (Apr 6)
  - `fcrn`: argenx VYVGART expanded to all gMG serotypes (May 8), J&J Imaavy Priority Review for wAIHA (May 12)
  - `tcell`: UCB acquires Candid Therapeutics $2.2B (May 3), Kyverna miv-cel rolling BLA initiated (Apr 25)
  - `il4ra`: Dupilumab FDA approval CSU ages 2–11 (Apr 22), Amlitelimab Ph3 AAD data (Mar 28)
- **Deals written to Supabase:** 1 — UCB acquires Candid Therapeutics $2B up / $2.2B total (tcell, acquisition)
- **Catalysts added:** 3 — Amgen SC Tepezza sBLA (igf1r, H2 2026), IMVT-1402 D2T RA topline (fcrn, H2 2026), AZ tozorakimab NDA/MAA filing (tslp, H2 2026)
- **Catalysts resolved:** 2 — id=46 AZ tozorakimab OBERON interim (POSITIVE), id=3 AZ OBERON/MIRANDA Ph3 (POSITIVE three-for-three)
- **Company signals updated:** 3 — AZ signal id=2 (tozorakimab POSITIVE three-for-three), AZ signal id=3 (updated alarmin narrative), Amgen signal id=21 (SC Tepezza Ph3 positive)
- **HTML changes:** Meridian reader updated — replaced KT501/Sanofi (Mar 2026) item with UCB/Candid $2.2B acquisition (May 3 2026)
- **Deployed:** f136d6a
- **Sources:** AstraZeneca press releases, Amgen press release, argenx press release, UCB press release, Sanofi/Regeneron press release, J&J/PR Newswire, FierceBiotech, BioPharma Dive

---
## 2026-05-18 Schema Migration + Live Stock Prices
- **Problem:** `companies` table missing `stock_price`, `stock_change`, `market_cap`, `last_price_update` columns — daily price refresh task had been saving to JSON fallback only
- **Fix:** Ran ALTER TABLE via Supabase SQL editor — added all 4 columns
- **Backfilled:** 21 companies updated with today's prices from `stock_prices_2026-05-18.json` (0 skipped)
- **Sample data:** Eli Lilly $1004.92 (−1.07%), argenx $799.32 (−0.42%), Regeneron $698.25 (−3.00%)
- **Frontend:** Updated `buildStockCard()` to display live `$price` and `%change` badge in tile header (green/red color-coded)
- **Deployed:** 91a650475bf98fa5f0a7de87ea884e67e13e602d

---
## 2026-05-18 Drugs to Know → Supabase
- **Drug counts by area (from drug_areas junction):** tl1a: 6, tslp: 7, il4ra: 6, igf1r: 3, fcrn: 5, tcell (ace tab): 5
- **Tabs updated:** all 7 (tl1a, tslp, il4ra-tslp, il4ra-ox40l, igf1r-tshr, fcrn, ace)
- **Changes made:**
  - Added CSS block for `.live-drugs-grid`, `.drug-card-live`, `.dcl-header`, `.dcl-name`, `.dcl-company`, `.dcl-stage`, `.dcl-mech`, `.dcl-detail`
  - Added `loadAreaDrugs(tabId)` async function — fetches via drug_areas junction, uses `mechanism` field (actual schema), stage-colored badges
  - Updated `loadMoleculeTab()` to call `loadAreaDrugs(tabId)` as 5th loader
  - Inserted `<div id="{tabId}-live-drugs">` placeholder before each of the 7 static dkn-card sections
  - Schema note: drugs table uses `mechanism` field (no target/format/moa); area mapping is entirely via `drug_areas` junction table
- **Deployed:** ca8fe2ea7762fbf8b72090ce620f4fa3d826d596

---
## 2026-05-18 Companies to Watch → Supabase
- **company_areas table:** already existed (30 rows pre-seeded across 6 areas)
- **Areas covered:** tl1a (8 co), tslp (5 co), il4ra (6 co), igf1r (3 co), fcrn (4 co), tcell (4 co)
- **Tabs updated:** all 7 (tl1a, tslp, il4ra-tslp, il4ra-ox40l, igf1r-tshr, fcrn, ace)
- **Changes made:**
  - Added CSS block for `.company-watch-card`, `.cw-header`, `.insight-up/down/neutral`, `.signal-item` etc.
  - Added `loadAreaCompanies(tabId)` async function with area→tab mapping
  - Updated `loadMoleculeTab()` to call `loadAreaCompanies(tabId)` as 4th loader
  - Inserted `<div id="{tabId}-live-companies">` placeholder at top of each CW body (static cards remain as fallback)
- **Deployed:** 3eb476c80de63139669de7fa90b9047d575a0ff3

---
## 2026-05-18 Stocks Tab Audit
- **Status found:** functional — fully wired, no stub
- **Structure verified:**
  - `id="tab-stocks"` exists at line 5344 (8,160-line file)
  - Contains: 4 prediction rule chips, area filter bar (All / TL1A / TSLP / IL-4Rα / IGF1R / FcRn / T-cell), `#stock-cards-grid` div
  - `loadStockCards()` defined at line 1066; called at `DOMContentLoaded` (line 7369)
  - `buildStockCard()` renders company name, ticker, exchange, tagline, area tags, insight direction/text from `company_signals`, Ailux BD Lens text
  - `stockFilter()` toggles `stock-card-hidden` on cards by `data-areas` attribute
  - `navTo('stocks')` correctly activates tab via nav-icon-btn; tab-btn hidden (display:none) as expected
- **Supabase data verified:**
  - 27 companies, 30 company_areas, 49 company_signals — all IDs consistent (string slugs)
  - 7 companies have no area or signal data (Astellas, Cullinan, Galderma, Kali, LEO Pharma, PTC, Windward Bio) — data gap, not a code bug; cards still render in "All" view
  - `market_cap`, `stock_price`, `stock_change` columns do not exist in DB; current implementation correctly uses `company_signals` for insight direction/text instead
- **Action taken:** no changes made — tab is functional as-is
- **Deployed:** no (no changes)

---
## 2026-05-17 Molecule Tab Migration — Build Session

### Architecture Changes
- **All 7 molecule tabs** (TL1A, TSLP, IL-4Rα×TSLP, IL-4Rα×OX40L, IGF1R×TSHR, FcRn, ACE) now Supabase-driven for intel, catalysts, and deals
- **HTML shells** added to each tab: `{tabId}-live-intel`, `{tabId}-live-catalysts`, `{tabId}-live-deals` sections
- **Molecule JS renderer** added: `TAB_AREA_MAP`, `loadMoleculeTab()`, `loadAreaIntel()`, `loadAreaCatalysts()`, `loadAreaDeals()` — uses `_sb` (supabase-js) directly
- **Tab structure bug fixed**: missing `</div>` after `tab-home` caused all molecule tabs to nest inside it; added correct closing tag
- **Loader bug fixed**: rewrote three loader functions to use `_sb.from().in().eq().order().limit()` directly instead of incompatible `sbFetch` wrapper

### Supabase Enrichment Seeded
- 27 companies, 30 drugs, 24 catalysts, 13 deals in Supabase
- All 7 areas populated with area-tagged data

### Scheduled Tasks Updated
- `meridian-morning-update`, `meridian-evening-update`, `bd-dashboard-weekly-update` — all updated with:
  - Area ID reference table (`tl1a`, `tslp`, `il4ra`, `igf1r`, `fcrn`, `tcell`)
  - Intel type reference (`news`, `data`, `deal`, `regulatory`, `conference`, `other`)
  - Explicit "NEVER edit molecule tab HTML" instructions (Supabase-driven)
  - Blob API deploy pattern for large files

### Verification
- All 7 molecule tabs verified rendering: catalysts ✓, deals ✓, intel (graceful empty state) ✓
- Home tab: stock cards ✓, deal tracker ✓, catalysts feed ✓
- Commits: e91c4a5 (loader fix), 1dffe2f (tab-home structure fix)

---
## Evening Run — May 16, 2026 (~18:00 PT)

### Sources Checked
1. Bispecific antibody press releases (general) — via WebSearch
2. ClinicalTrials.gov / TL1A / IL-23 — Xencor XmAb412 + XmAb942 DDW 2026 (May 2–5); Merck tulisokibart expansion (Oct 2025); Spyre SKYWAY-RD
3. TSLP / IL-33 bispecific — Roche/QX031N (Oct 2025, already in dashboard); Odyssey Therapeutics pipeline
4. FcRn autoimmune — Nipocalimab JASMINE Ph2b SLE (J&J, Jan 6, 2026); VRDN-008 HV data expected
5. BCMA / CD19 / CD3 trispecific — UCB/Candid acquisition $2.2B (May 3, 2026); IBI3003 Fast Track (Jan 2026, oncology focus)
6. IGF1R / TSHR / TED — Elegrobart (VRDN-003) Ph3 initiated Aug 2024; no new data today
7. IL-4Rα / OX40L / atopic dermatitis — Amlitelimab Phase 3 AAD data (Mar 2026, already in dashboard); Belenos BEL536 Ph1 planned Q1 2026
8. BD deals — UCB/Candid $2.2B (May 3, 2026); Curacle/Mabtics MT-103 retinal bispecific (May 12, 2026 — retinal vascular, out of scope)
9. Conference abstracts — Xencor XmAb412 poster at DDW (May 2–5, 2026) — already in dashboard; Nature Medicine 2026 paper on TCEs for autoimmune CTDs

### Changes Made
- **Body 7 (BCMA/CD19/CD3 TCE tab)**: Added UCB/Candid $2.2B acquisition (May 3, 2026) — CND460 BCMAxCD19xCD3 trispecific; second major pharma validation of the format after Sanofi/HXN-1031 ($2.56B). intel-dot-red.
- **Body 6 (FcRn tab)**: Added Nipocalimab (J&J) JASMINE Ph2b primary endpoint met in active SLE (Jan 6, 2026) — first FcRn inhibitor to succeed in SLE; J&J advancing to Ph3, FDA Fast Track granted Mar 2026. intel-dot-blue.

### Skipped (already in dashboard)
- Xencor XmAb942 Ph1 HV final data at DDW (already Body 1)
- Xencor XmAb412 DDW preclinical poster (already Body 1, within XmAb942 item)
- Windward Bio $165M round (already Body 2)
- Dupilumab / amlitelimab AD data (already Bodies 3–4)

### Deployed
- Commit: 3191c23
- 2 new intel items added; no layout, CSS, JS, or Ailux Pipeline Overview changes

## Evening Run — Sun May 17, 2026 (~6:00 PM)

**Searches conducted:**
1. Bispecific antibody press release today May 2026
2. ClinicalTrials.gov TL1A / IL-23 update
3. TSLP / IL-33 bispecific news May 2026
4. FcRn autoimmune clinical trial news May 2026
5. BCMA / CD19 / CD3 trispecific news May 2026
6. IGF1R / TSHR thyroid eye disease antibody news 2026
7. IL-4Ra / OX40L atopic dermatitis news May 2026
8. Bispecific antibody licensing deal announced May 2026
9. DDW 2026 conference abstracts IBD immunology results
10. Xencor XmAb942 / XmAb412 DDW 2026 (validation)
11. Aclaris ATI-052 Phase 1a full results (validation)
12. UCB / Antengene ATG-201 deal (validation)
13. Merck tulisokibart expansion date (Oct 2025 — already pre-dashboard scope)
14. Sanofi lunsekimig Phase 2 results (validation)

**Dashboard changes (commit e3ada8c):**

### Added — TSLP tab
- **Sanofi lunsekimig Phase 2 data (Apr 7, 2026)**: TSLP×IL-13 bispecific Nanobody met primary endpoints in asthma (AIRCULES Ph2b) and CRSwNP (DUET Ph2a); missed AD (VELVET Ph2b). First Phase 2 validation of TSLP×IL-13 bispecific in respiratory. Source: sanofi.com PR.

### Added — IL-4Rα/TSLP tab
- **Aclaris ATI-052 full Phase 1a topline results (Apr 28, 2026)**: ~45-day half-life, dose-proportional PK, no safety signals. Phase 1b AD + asthma ongoing (data 2H 2026). Phase 2b asthma planned Q4 2026. Source: investor.aclaristx.com PR.

### Added — ACE tab
- **UCB/Antengene ATG-201 deal (Mar 3, 2026)**: CD19×CD3 masked bispecific TCE for B-cell autoimmune. $80M upfront / >$1.1B total milestones. AnTenGager™ steric-masking platform. FIH China/Australia. Source: ucb.com PR.

**Not added (already in dashboard):** Xencor XmAb942/XmAb412 DDW data, UCB/Candid $2.2B, Windward Bio $165M, tulisokibart ATLAS-UC, nipocalimab SLE.
**Not added (pre-dates relevance window):** Merck tulisokibart expansion (Oct 2025).
**Not added (target mismatch):** iBio IBIO-610 (metabolic), Boehringer/Immunitas (undisclosed target).

## Morning Update — May 17, 2026

### News Feed Sources
- Fierce Biotech RSS: Unable to fetch directly (URL not in provenance); 1 BD-relevant article sourced via WebSearch (Boehringer/Simcere SIM0709 deal)
- Endpoints News (news-briefing channel): ~23 articles scanned, 1 BD-relevant selected (Bristol Myers/Hengrui 13-asset deal, UCB/Candid TCE deal)
- Endpoints News (deals channel): ~25 articles scanned, 2 BD-relevant selected
- Endpoints News (R&D channel): ~23 articles scanned, 1 BD-relevant selected (Sanofi immunology CEO)
- WebSearch (7 targeted queries): 1 additional policy item (FDA 1-trial approval policy)

### Articles Added to Industry Insights Daily Feed (5 total)

1. **Endpoints News — Bristol Myers joins Hengrui party in 13-asset deal worth up to $15.2B** (May 15)
   - Tags: deals | Reason: Landmark China-to-West deal; Hengrui immunology/oncology pipeline; BD signal for outbound licensing

2. **Endpoints News — UCB bets $2B on Candid's T cell engager ambitions** (May 3)
   - Tags: deals, bd | Reason: China-founded TCE autoimmune company; validates bispecific B-cell depleting format for autoimmune; directly relevant to BCMA/CD19 tab

3. **Fierce Biotech — Boehringer pens €1.05B deal for Simcere's TL1A×IL-23p19 IBD bispecific SIM0709** (Jan 2026)
   - Tags: deals, bd | Reason: Directly relevant to TL1A×IL-23p19 tab; first major pharma validation of dual-target IBD bispecific from China

4. **Endpoints News — Sanofi's new CEO faces a reckoning on immunology-focused R&D strategy** (Apr 23)
   - Tags: market | Reason: Amlitelimab pipeline and BD implications; dupilumab franchise context; signals Sanofi BD appetite

5. **BioPharma Dive — FDA shifts to single-trial approval standard** (May 2026)
   - Tags: policy | Reason: Major regulatory policy shift affecting approval timelines for bispecific antibodies and immunology drugs

### Articles Rejected

- Boehringer/Zealand obesity shot (today, Endpoints R&D): Not relevant — GLP-1/obesity, not immunology/bispecific
- Erasca vs Revolution Medicines RAS drugs (today, Endpoints R&D): Not relevant — oncology/RAS, not target area
- Intellia CRISPR Phase 3 (yesterday, Endpoints R&D): Not relevant — gene therapy/TTR, not immunology
- Veradermics oral Rogaine (yesterday, Endpoints R&D): Not relevant — alopecia/minoxidil, not bispecific
- Pfizer/Arvinas breast cancer drug (2 days, Endpoints Deals): Not relevant — oncology PROTAC
- Bayer M&A return announcement (2 days, Endpoints Deals): Not relevant — no immunology focus specified
- Avalyn IPO / WHO malaria drug / Grace CRL (yesterday, Endpoints Briefing): Not relevant — respiratory/malaria/non-immunology
- Oruka Phase 2 psoriasis (Endpoints R&D): Marginally relevant (IL-17 psoriasis) but non-bispecific mAb; excluded to keep feed focused

### Intel Card Updates
None — no new validated press release / ClinicalTrials.gov / SEC filing data today for specific target tabs. All relevant deal data (UCB/Candid, BMS/Hengrui, Boehringer/Simcere) already captured in prior runs or in today's feed cards.

### Deployed
- Commit: e5fd65f
- 5 new ii-cards added to Industry Insights Today's Feed block
- Article counter updated: 64 → 69

### SKILL.md Update
- Skipped: /Users/kyleklaassen/Documents/Claude/Scheduled/meridian-morning-update/SKILL.md path not accessible in workspace mount. User should manually add STEP 1b to that file per task instructions.

---
## May 17, 2026 — Market & Learning Tab Redesign (Manual)

**Changes made to index.html:**

### Market & Learning Tab (`id="tab-stocks"`)
- **Removed** the "Market Signal Framework" banner header (`meridian-reader` div)
- **Replaced** 4 full `predict-card` sections with compact collapsible `.rule-chip` divs
  - Each chip shows: rule number badge + one-line brief summary + ▾ toggle
  - Expanded body reveals the full predict rules (same content, collapsible)
  - Functions: `toggleRuleChip(id)`
- **Replaced** 6 full-height `.stock-card` divs with compact grid tiles
  - New layout: `.stock-cards-grid` (CSS grid, auto-fill 310px min columns)
  - Each card shows: company + ticker + target-area tags + single key insight line
  - Click to expand full analysis (`.stock-body`)
  - Function: `toggleStockCard(el)`
- **Added** filter bar above the grid (All / TL1A·IBD / TSLP·Resp. / IL-4Rα / FcRn / T-cell Eng.)
  - Each card has `data-areas` attribute for JS filtering
  - Function: `stockFilter(btn, area)`

### CSS Added (earlier session, confirmed present)
- `.rules-grid`, `.rule-chip`, `.rule-chip-hd`, `.rule-num`, `.rule-brief`, `.rule-toggle-icon`
- `.stock-filter-bar`, `.stock-fbtn`, `.stock-cards-grid`, `.stock-card`, `.stock-tile-hd`
- `.stock-tile-left/right/name/sub/tags`, `.stag` variants, `.stock-insight`, `.stock-body`
- `.stock-card.expanded` states, `.stock-card-hidden`

### JS Added
- `toggleRuleChip(id)` — toggles `.open` on rule chip
- `toggleStockCard(el)` — toggles `.expanded` on stock card
- `stockFilter(btn, area)` — filters stock cards by `data-areas` attribute

**Deployed:** commit c456cae

---
## 2026-05-17 — Supabase Backend + Dynamic Rendering

### Infrastructure
- Created Supabase project: **Ailux BD Project** (`tghntyofptvfhmtchwcv.supabase.co`)
- Stored credentials: `.supabase_anon_key`, `.supabase_service_key`, `.supabase_config`
- Saved schema SQL: `supabase_schema.sql`
- Saved seed script: `supabase_seed.py`

### Schema (16 tables created)
`disease_areas` · `targets` · `target_areas` · `companies` · `company_areas` · `company_signals` · `drugs` · `drug_targets` · `drug_areas` · `trials` · `deals` · `intel` · `intel_areas` · `intel_companies` · `catalysts` · `meridian_issues`

RLS enabled on all tables; anon key granted SELECT only; service_role key for writes.

### Seed Data Loaded
- 6 disease areas (TL1A, TSLP, IL-4Rα, IGF1R, FcRn, T-cell)
- 11 targets with ailux_program flags
- 20 companies with 30 area mappings and 49 individual signals
- 17 key drugs with target + area mappings
- 10 catalysts (including 1 resolved: Immunovant batoclimab TED failure Apr 2026)

### Dashboard Changes
- Added `@supabase/supabase-js@2` CDN to `<head>`
- Replaced 363 lines of static stock card HTML with 3-line loading shell
- Added `buildStockCard()`, `loadStockCards()`, `sbFetch()` helper functions
- `loadStockCards()` fires on `DOMContentLoaded` alongside existing handlers
- Filter bar (`stockFilter()`) still works — cards rendered with correct `data-areas`
- **Result:** 20 company cards now render live from Supabase on every page load

## 2026-05-18 Home stats → Supabase: companies, drugs, catalysts, deals, intel counts — deployed 79797a8

## 2026-05-18 Industry Insights → Supabase: replaces static monthly entries with live intel feed — deployed c58546f9d801945fed18b4057babd6dff83774e7

---
## 2026-05-18 Supabase Data Audit (Scheduled — Automated)

### Scope
Full data quality pass against primary sources (ClinicalTrials.gov, company press releases, FDA.gov). Verified 27 companies, 30 drugs, 23 unresolved catalysts, 13 deals.

### Companies verified: 27
No corrections required — all insight_text and insight_dir values consistent with known pipeline status.

### Drugs verified: 30, updated: 5

| Drug | Field | Old Value | New Value | Source |
|------|-------|-----------|-----------|--------|
| duvakitug | stage_detail | "STARSCAPE (UC) + SUNSCAPE (CD)" | "SUNSCAPE (UC) + STARSCAPE (CD)" | ClinicalTrials.gov — SUNSCAPE-1/2 = UC; STARSCAPE-1 = CD |
| kt501 | mechanism | "BCMA × CD3 bispecific" | "BCMA × CD19 × CD3 tri-specific T-cell engager" | Kali/Sanofi press release (Mar 23 2026, prnewswire) |
| kt501 | key_data | "$150M upfront / $1.8B total" | "$180M upfront / $1.23B total Sanofi deal (Mar 2026)" | Kali/Sanofi press release; fiercebiotech; pharmaphorum |
| amlitelimab | stage_detail | "EU approved AD; FDA filing 2025" | "EU approved AD (Jun 2024); US regulatory submission planned H2 2026" | Sanofi press releases Jan 2026, Mar 2026; clinicaltrialsarena |
| teprotumumab | stage_detail | "SC formulation in development" | "SC Ph3 POSITIVE Apr 2026; sBLA planned late 2026" | Amgen press release Apr 2026; clinicaltrialsarena |
| miv-cel | stage_detail | "BLA filing H1 2026 for SPS" | "Rolling BLA initiated May 2026 for SPS; BLA completion targeted Q4 2026" | Kyverna IR May 12 2026; globenewswire |

### Catalysts verified: 23, resolved: 1

- **Catalyst 6 — RESOLVED**: "Kyverna miv-cel BLA filing for SPS" — rolling BLA submission initiated May 12, 2026. BLA completion targeted Q4 2026.

### Deals verified: 13, corrected: 1, flagged: 1

- **Deal ID 1 (Kali/Sanofi Mar 2026)**: Corrected `deal_type` from "collab" → "license" (confirmed exclusive worldwide license agreement).
- **Deal ID 17 — FLAGGED FOR MANUAL REVIEW**: Record shows "Sanofi licenses KT501 from Kali for $150M up / $1.8B total" dated Jan 2025. No press release or secondary source confirms a Jan 2025 Kali/Sanofi deal. The only confirmed Kali/Sanofi deal for KT501 was announced March 23, 2026 at $180M/$1.23B (already correctly captured in Deal ID 1). Deal ID 17 likely represents a duplicate seed entry with wrong date and wrong amounts. Recommend deletion after manual review.

### Confirmed accurate (no change needed)
- tulisokibart ATLAS-UC: Phase 3 ongoing, no topline data yet — readout ~Nov 2026 ✓
- nipocalimab (Imaavy): FDA approved gMG Apr 30, 2025 ✓ — brand name "Imaavy" confirmed ✓
- efgartigimod: expanded to all gMG serotypes confirmed ✓
- duvakitug Ph2b 48% UC remission signal ✓
- afimkibart AMETRINE (UC) + SIBERITE (CD) trial names ✓
- Earendil/Sanofi deal HXN-1003: $125M upfront / ~$1.85B total confirmed ✓
- Simcere/BI SIM0709: €42M upfront / €1.05B total confirmed ✓

### Flagged for manual review
1. **Deal ID 17** — Phantom duplicate record (see above). Recommend deletion.
2. **Catalyst 48** — "Sanofi amlitelimab FDA approval decision (AD)" sort_date 2026-10-01. FDA submission is not yet filed as of May 2026 (planned H2 2026); regulatory approval by Oct 2026 is not feasible. Catalyst date should be moved to 2027 or left open pending US filing.

### Not changed (could not verify)
- argenx efgartigimod Q8W SC Ph3 results timing — unverified specific date; left as-is.
- Specific clinical trial NCT enrollment completion dates — taken at face value from existing entries.


## 2026-05-18 Monthly task SKILL.md updated for Supabase architecture

---
## 2026-05-18 Submit Intel + Search Upgrade
- Submit Intel modal: replaced localStorage-only modal with full Supabase-backed form (headline, body, source URL/name, type, importance, area checkboxes); writes to `intel` table + `intel_areas` junction
- Global search: added `supabaseSearch()` async function that queries `drugs`, `companies`, and `intel` tables in parallel; result count appended to gs-count element
- Deployed: 8540cd5c8ff0478c38d305c1e1c8cd074c9488a7

## 2026-05-18 Stock Price Refresh

- **Status:** PARTIAL — prices fetched from Yahoo Finance but **NOT written to Supabase** (columns missing)
- **Root cause:** `companies` table lacks `stock_price`, `stock_change`, `market_cap`, `last_price_update` columns
- **Action required:** Add these columns to Supabase (see migration note below)
- **Fetched successfully:** 21 companies
- **Failed (fetch error):** 3 — Astellas Pharma (HTTP Error 404: Not Found), Boehringer Ingelheim (HTTP Error 404: Not Found), Galderma (HTTP Error 404: Not Found)
- **No/invalid ticker:** 3 — Kali Therapeutics, LEO Pharma, Windward Bio

**Sample prices (first 5):**
  - AbbVie (ABBV): $210.39 (+0.91%)
  - Amgen (AMGN): $326.31 (-3.01%)
  - Apogee Therapeutics (APGE): $81.14 (-3.34%)
  - argenx (ARGX): $799.32 (-0.42%)
  - AstraZeneca (AZN): $181.58 (-3.27%)

**Full price snapshot saved to:** `stock_prices_2026-05-18.json`

**Migration SQL (run in Supabase SQL editor to enable future writes):**
```sql
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS stock_price NUMERIC,
  ADD COLUMN IF NOT EXISTS stock_change NUMERIC,
  ADD COLUMN IF NOT EXISTS market_cap TEXT,
  ADD COLUMN IF NOT EXISTS last_price_update DATE;
```

## 2026-05-18 Intel Read modal + Drug detail modal: wired to Supabase, NCT auto-linking — deployed 1d99a3db3d8bd4f5d9fdf8721ed8ecf5cb208ec4

---
## 2026-05-18 Market watchlist → Supabase + Past Catalysts history section added — deployed 4eba801044483d8b77a4341ea4e2566e280ead20

---

## 2026-05-18 — Fix: Blank Molecule Tabs and Drugs to Know
**Commit:** `27d653e`

### Root Cause
The TL1A tab redesign (commit `1ee24b80`) removed the `#grid-tl1a-landscape` and `#grid-tl1a-tech` Grid.js container elements, replacing them with the new `tl1aPI` program intelligence table. However, the `initGrids()` function still tried to call `.render(document.getElementById('grid-tl1a-landscape'))` — which returned `null` — causing Grid.js to throw `Container element cannot be null`. Since this threw synchronously inside the function, all subsequent grid initializations (TSLP catalyst calendar, TSLP competitive landscape, IL-4Rα, IGF1R, FcRn, ACE grids) never executed. Result: every molecule tab appeared blank.

### Fix
Removed the dead `grids.tl1aLandscape` and `grids.tl1aTech` initialization blocks from `initGrids()` (lines 7777–7807 in the prior version). These are superseded by the `tl1aPI` Program Intelligence table introduced in the redesign.

### Verified
- No console errors on fresh page load
- `grid-tslp-readouts`, `grid-tslp-landscape`, `grid-tl1a-readouts` all render ✓  
- Drugs to Know tab activates correctly with 118 rows ✓

## 2026-05-18 — Commit d5f01cfa58cd (Task #125)
### TL1A Tab UX Overhaul (12 improvements)
**Layout / Navigation:**
- Side pill buttons moved to `position:fixed` — left and right columns no longer scroll with page
- Removed pills from CSS grid; `tl1a-layout` simplified to single centered column
- Pills auto-show when TL1A tab is active, hide on all other tabs
- Biology Deep Dive moved from inside PI card header to left pill column

**New pills:**
- "🏥 Standard of Care" added as separate pill (right column)
- "IBD Market" pill now opens market-only modal (size, benchmarks, AbbVie/Skyrizi data)
- Standard of Care modal has UC + CD escalation ladders + endpoint reference tables

**Modals:**
- All modals auto-expand collapsed sections when opened (no extra click needed)

**Drug pills redesign:**
- All pills equal size (86×64px) — removed opacity/scale differences
- Phase badge (P1/P2/P3/IND) in top-right corner of each pill
- Disease-area color: IBD = blue (#2563eb), Rheumatic/RA = purple (#9333ea)
- Target name(s) shown inside each pill (multi-line for combos)

**Hover cards:**
- Fixed disappearing card: replaced CSS :hover with JS mouseenter/mouseleave + 130ms debounce
- Active Clinical Trials section moved to top of card (highest priority info)
- Popup widened to 490px
- Sources removed as separate section — embedded as inline link chips in mechanism text
- Trials section styled with blue border for prominence

**Company row:**
- Expanded row highlighted blue background
- Chevron turns blue when open
- "click to close" hint text appears in last cell when expanded

## 2026-05-21 — commit 420c46a8974bd60afb465e9bdde4cd3c7d833d65
- Moved Meridian Archive picker (label + issue count + select dropdown) from above the iframe in the tab pane into the header bar, right of the Submit Intel button
- Archive bar is hidden by default; shown via `onEnter` / hidden via `onLeave` in the meridian-issue registerTab hooks
- Iframe wrapper border-radius updated from `0 0 10px 10px` to `10px` now that the control bar above it is gone
