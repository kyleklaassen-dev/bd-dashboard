# NEXT SESSION — BD Platform

**Written:** 2026-05-23 (updated after Session 10)  
**Session focus:** Systemic DKN visibility fix, transaction intake rule, write-path enforcement

---

## Session 10 Completion Block

### ✅ Transaction Intake Principle Encoded
- `TRANSACTION_PIPELINE_EXPANSION` rule added to `LANDSCAPE_SEARCH_SYSTEM` prompt in `company_enrichment.py`
- Transaction Intake (Path 5) added to `docs/intake_integrity_framework.md` with checklists for acquisitions + licensing deals
- Memory: `project_transaction_intake.md` — company-centric first, asset-centric second

### ✅ infer_catalog_category() — Write-Path Enforcement
- Shared helper function in `company_enrichment.py`, `approve_discovery.py`, `drug_intake.py`
- Priority logic: Oncology (TCE/ADC targets) → Small Molecule (JAK, first) → Immunology/Pipeline (by stage) → Pipeline (fallback)
- Bug fixed in `drug_intake.py`: was setting `catalog_category = area_id` (e.g. "tl1a") — now uses proper inference
- Auto-stamp in `company_enrichment.py` enrichment loop: patches null values on existing drugs
- 17/17 spot-checks pass against known drug profiles

### ✅ Validation: 83/83 passing

---

## P0 — Next Session Priorities

| Priority | Task | Effort |
|----------|------|--------|
| P1 | **Enrich Lilly, Novartis, Pfizer** — missing from many area tabs | Medium |
| P1 | **Add company_area consistency validation** (Rule E3) | Low — new test type |
| P2 | **Run full company_enrichment.py for UCB/tcell** — quick_profiles done, drug-level summaries/overlap not yet enriched | Medium |
| P2 | **Run catalog_visibility test after any enrichment run** | Automated via validate_ground_truth.py |
| P3 | **Migrate tl1aPI static JS object to Supabase** | High effort, high long-term value |

**✅ UCB + Candid profiles done** — quick_profiles_enrich.py run for tcell + autoimmune. Profiles accurately reflect ATG-201 license, Candid acquisition, trispecific pipeline.

---

## Previous Sessions (preserved below)

---
**Previous NEXT_SESSION contents:**

**Session focus:** Quality & Trust Sprint — dossier bugs fixed, QA audit, ground truth expansion, provenance design

---

## What Was Accomplished This Session

### ✅ Bug Fix 1: Molecule Tab Always Shown
- `_buildDrugDossierBody` was hiding the Molecule tab when `molData=null`
- Fixed: tab always rendered; shows "Not yet profiled" message when no data

### ✅ Bug Fix 2: Trials + Overlap Populating Correctly
- `openDrugEntityModal` was fetching from `drug_areas` which has no overlap columns
- Fixed: now fetches from `drug_area_scores` in parallel and merges by area_id
- Added fallback to `drugs.overlap` when area scores return null (handles tl1a/ibd area_id mismatch)

### ✅ Task 1: Entity Dossier QA Audit
- Audited 6 companies + 6 drugs across all dossier tabs
- 9 bugs found; 6 fixed immediately in the same session
- Report: `docs/entity_dossier_qa_report.md`

### ✅ Task 2: Ground Truth Expansion
- Expanded validation_tests from 28 → 61 tests
- Added 23 cross-area tests (TSLP, FcRn, IL-4Rα)
- Added 10 `not_hallucinated` tests for partner_company and drug_name fields
- All 61 tests passing

### ✅ Task 3: Source Verification Coverage Audit
- Confirmed: source_url is 0% populated across all `drug_area_scores` rows
- 42 Direct-overlap drugs have no source URL
- Priority remediation ranking: TL1A (ibd) first, then FcRn, TSLP, IL-4Rα
- Report: `docs/source_verification_audit.md`

### ✅ Task 4: Company Coverage Audit
- 60 active companies; 37 enriched; 23 unenriched
- Top 20 enrichment priority companies identified
- Healthy/Medium/Critical tier classification
- Report: `docs/company_coverage_audit.md`

### ✅ Task 5: Hallucination Defense
- Added 10 `not_hallucinated` validation tests
- Covers: partner_company self-reference, acquired-company leakage, drug name accuracy
- Fixed 3 data issues found:
  - dupilumab.partner_company='Sanofi' (self-reference) → null
  - nipocalimab.partner_company='Momenta Pharmaceuticals' (acquired 2020) → null
  - tulisokibart.partner_company='Prometheus Biosciences' (acquired 2023) → null

### ✅ Task 6: Confidence Badges in Dossier Header
- Added ✓ Confirmed / ≈ Supported / ~ Inferred / ? Unverified badges to drug dossier header chips
- All drugs currently show `?` — will resolve as enrichment runs populate source_url
- Deployed: commit `577ba0e`

### ✅ Task 7: Provenance Schema Design (design only)
- Full architecture documented: `docs/provenance_architecture.md`
- Three new tables designed: `enrichment_runs`, `provenance_events`, `assertion_history`
- Migration file ready to apply: `migrations/v16_provenance.sql`
- **NOT yet applied to Supabase** — apply when ready to implement enrichment_run_id tracking

### ✅ Task 8: Dossier Enhancement Plan (design only)
- `docs/dossier_phase2.md` — full roadmap for transforming dossier into intelligence product
- Company dossier: Cross-Area Aggregation, Signals View, Evidence View, Validation Status
- Drug dossier: Coverage Score, Strategic Value Score, Evidence Sources Panel, Change History
- Implementation priority table with effort/value estimates

### ✅ Data Quality Fixes Applied (Supabase)
- 9 `drug_area_scores` classification corrections:
  - tulisokibart, duvakitug, afimkibart, spy002, spy072 → ibd: Watch → Direct
  - tezepelumab → tslp: Watch → Direct
  - nipocalimab, efgartigimod, rozanolixizumab → fcrn: Watch → Direct
  - astegolimab, itepekimab → tslp: Watch → Direct

---

## What Was Done Since This File Was Last Written

### ✅ v16 Migration Applied (2026-05-23 Session 3)
- `enrichment_runs` table created + run_id columns added to drugs / drug_area_scores / company_profiles

### ✅ SPY072 IBD Overlap Corrected (Session 3)
- Reverted Direct → Adjacent: anti-TL1A rheumatology program (PsA/axSpA), not IBD
- Rule documented: target-lens Direct ≠ disease-area-lens Direct

### ✅ P1: Source Evidence Tracking in Enrichment Pipeline (Session 4, commit `01141bf`)
- `source_url` + `confidence_level` now written to `drug_area_scores` on every enrichment run
- `enriched_model` written to `drug_area_scores` (v16)
- `last_enriched_model` written to `drugs` and `company_profiles` (v16)
- Prompt: `confidence_level` REQUIRED; inferred must explain why in `overlap_rationale`
- Tested on caldera/cld-423; 61/61 validation tests passing

### ✅ Drug Identity Audit + Merges (Session 5, commit `14df877`)
- Audited 4 suspected duplicate pairs; confirmed 2 as duplicates
- Merge A: `pf-06480605` → `afimkibart` (13 trials, 8 catalysts, mol_intel migrated)
- Merge B: `hxn1003` → `erd-1` (target updated to TL1A×IL-23p19; hxn1003 deleted)
- Data fix: `ep006` display_name → 'EP006 (Eprovaxia)' (naming collision with es302, not duplicate)
- Not merged: `qx030n` / `qx031n` (distinct molecules, different targets/areas/partners)
- Full audit documented: `docs/drug_identity_audit.md`

### ✅ P0: Source Verification Population (Session 6, commit `1e79552`)
- `scripts/source_verify.py` — new standalone source_url populator (no web search, ~5s/drug)
- `company_enrichment.py` — added `--skip-discovery` and `--skip-web-search` flags
- 48 drug_area_scores rows processed across all areas; 31 confirmed/supported URLs written
- Hallucinated URL detected + nulled (tozorakimab/tslp NCT05005chips)
- fg-m701 area_id fixed: atopy → tl1a + ibd
- risankizumab + upadacitinib stage regression fixed (Phase 3 → Approved)
- Validation suite: 61 → 64 tests (added 3 approved-drug stage guards)
- 64/64 passing

### ✅ Task #127: Molecule Intelligence Enrichment (Session 5b, commit `a4dc837`)
- `scripts/molecule_enrichment.py` — new standalone targeted enrichment script
- 20 priority TL1A/IBD drugs enriched: duvakitug, spy002, spy072, spy001, spy003, spy120, spy130, spy230, qx030n, ro7837195, fg-m701, abbv-382, abbv-668, lutikizumab, risankizumab, guselkumab, mirikizumab, upadacitinib, ustekinumab, golimumab
- molecule_intelligence records: 31 → 51 (+20)
- Known limitation: `ensure_canonical_id()` doesn't INSERT into canonical_drugs (FK issue — workaround applied for 3 affected drugs)

### ✅ Intake Integrity Framework + DKN Gap Fix + UCB/Candid TCE (Session 9)
- **Principle established:** Dashboard = view layer. Supabase = source of truth. 4 intake paths documented in `docs/intake_integrity_framework.md`.
- **DKN audit:** 45 of 91 area-tab drugs had `catalog_category = null` → invisible in Drugs to Know. Fixed 38 legitimate drugs (Pipeline/Immunology). Deleted 4 duplicate records (batoclimab-fcrn, imvt1402, abs101, hxn-1003). Merged batoclimab_ted into batoclimab. Fixed ep006 display_name + orilanolimab company (ucb → astrazeneca).
- **catalog_visibility test type** added to validate_ground_truth.py — enforces the DKN coverage invariant going forward.
- **UCB + Candid TCE pipeline added:** cizutamig (BCMA×CD3), CND319 (CD19×CD20×CD3), CND460 (BCMA×CD19×CD3), ATG-201 (CD19×CD3 licensed from Antengene March 2026). UCB and Candid added to tcell+autoimmune company_areas. 2 deals added.
- **Validation: 83/83 passing** — 6 new tests, 1 stale deleted

### ✅ LQ080/ZW191 Identity Fix + Validation Framework Hardening (Session 8b)
- **Root cause:** enrichment runs assigned lanova as LQ080's company and merged "LQ080 / ZW191" as display_name (slash in comparison table misread as alias)
- **Data fixes:** lq080.company_id → novamab; display_name → "LQ080"; lq080/ibd overlap → Direct; added lq080/tl1a drug_area_scores row
- **validate_ground_truth.py:** new `company_check` + `display_name_check` test types; `not_contains` operator; `drugs_all` cache extended with display_name+target
- **company_enrichment.py:** SLASH PROHIBITION rule in display name guidance; LQ080 + LQ082 added to KNOWN_DRUG_TARGETS (company=novamab, explicit ZW191 do-not-alias note)
- **Validation: 71 → 78/78 passing**

### ✅ Regeneron Enrichment + quick_profiles_enrich.py (Session 8)
- New script: `scripts/quick_profiles_enrich.py` — lightweight company_profiles updater
  - Drug + deal context only (no trials, no intel); ~5s/company×area; ~$0.003/call
  - Solves 45s bash timeout constraint: full pipeline fails for companies with 10+ trials
  - `company_enrichment.py` also got `--skip-trial-refresh` and `--fast` flags for future use
- Enriched `regeneron/tslp` and `regeneron/il4ra` with Haiku-generated summaries
- **Validation: 71/71 passing** — no regressions

### ✅ CLD-423 / CLDR-001 Identity Resolution (Session 7c)
- Confirmed: cld-423 and cldr-001 are the same molecule (CLD-423/QX030N, Caldera licensed from Qyuns)
- cldr-001 is canonical; cld-423 deleted (drug record + 2 drug_area_scores)
- qx030n (Qyuns TL1A×IL-23) and qx031n (Qyuns TSLP×IL-33 → Roche) confirmed distinct
- cldr-001/tl1a upgraded: source_url → NCT05906563 (CT.gov), confidence_level → confirmed
- cld-423-tl1a-overlap test replaced with cldr-001-tl1a-overlap + cldr-001-ibd-overlap + qx031n-tslp-overlap
- **Validation: 71/71 passing**

### ✅ Wrong-Area Audit + Full Cleanup (Sessions 7 + 7b)
- Full audit of 76 orphaned `drug_area_scores` rows (in scores but not in `drug_areas`)
- Root cause: early enrichment runs used company-level context → oncology/atopy/IBD crossover artifacts
- **57 rows deleted** (Session 7): oncology drugs in IBD/atopy, IBD drugs in atopy, hxn-1003 (merged drug)
- **14 missing `drug_areas` rows added** (Session 7b): correct-area orphans where drug_areas was incomplete
- `drug_area_scores`: 152 → 95 rows; `drug_areas`: 160 → 174 rows
- 5 remaining orphans deferred: cld-423 (identity pending), omalizumab+tisagenlecleucel (marginal), benralizumab/tslp (downstream)
- Identity fixes: argx-117 target (C2 complement, not FcRn×CD131); cendakimab company (AbbVie, not AZ) + target (IL-13Rα1) + cls (oral SM, not IgG)
- Data fixes: efgartigimod/fcrn Watch→Direct, mirikizumab Approved, lebrikizumab/il4ra Watch→Adjacent
- **Validation: 69/69 passing** (64→69: added imvt-1402, apg777, zumilokibart overlaps; dupilumab+efgartigimod stage guards)
- Files: `docs/wrong_area_audit.md`, `migrations/wrong_area_cleanup.sql`

---

## Highest Priority for Next Session

### 🟡 P0: Enforce catalog_category in enrichment pipeline writes
`company_enrichment.py` and `molecule_enrichment.py` never set `catalog_category` when inserting new drug records → drugs become invisible in DKN. Rule: all enrichment drug inserts must write a `catalog_category` value. Simple default logic:
- Immunology biologic (approved) → `'Immunology'`
- Clinical pipeline → `'Pipeline'`
- Small molecule → `'Small Molecule'`
- Oncology → `'Oncology'`

### 🟡 P1: Run quick_profiles_enrich.py for UCB/Candid
UCB and Candid now have company_areas entries. Run enrichment to populate company_profiles:
```bash
python3 scripts/quick_profiles_enrich.py --area tcell --company ucb
python3 scripts/quick_profiles_enrich.py --area tcell --company candid
```

### 🟡 P1: Enrich Priority Companies (company_coverage_audit.md)
✅ Regeneron done (tslp + il4ra, Session 8).  
Next: **Lilly, Novartis, Pfizer** — use `scripts/quick_profiles_enrich.py` for each.

**How to run each company:**
```bash
# Find which area_ids a company has in company_profiles:
# GET /company_profiles?company_id=eq.lilly&select=area_id
python3 scripts/quick_profiles_enrich.py --area tslp --company lilly
python3 scripts/quick_profiles_enrich.py --area il4ra --company lilly
# etc per area
```
Top remaining unenriched: Lilly, Novartis, Pfizer, Gilead, J&J, BMS, Amgen, Takeda, Boehringer Ingelheim

### 🟡 P3: Dossier Phase 2 — Coverage + Strategic Value Chips (low effort, high value)
From `docs/dossier_phase2.md`:
- **Coverage Score chip** — client-side computation, no schema change needed
- **Strategic Value Score chip** — client-side computation from overlap+stage+BD profile
- Both are "Ship next session" priority in the roadmap table

### 🟡 P4: Roche Catalyst Deduplication
Roche has ~10 near-duplicate catalysts: AMETRINE appears 3×, QX031N appears 4×.  
Use the same dedup pattern from `docs/catalyst_quality_diagnosis.md`:
- Preview: `SELECT COUNT(*) WHERE company_id='roche'` grouped by label
- Delete duplicates keeping highest `id`
- Add unique constraint on `(company_id, area_id, label)`

### 🟡 P5: Fix `ensure_canonical_id` in molecule_enrichment.py
The function generates a canonical ID and patches drugs table but doesn't INSERT into canonical_drugs, causing FK violations for drugs not already in that table. Fix:
1. Look up canonical_drugs by name first
2. If not found, INSERT into canonical_drugs before patching drugs table
3. Then proceed with mol_intel insert as normal

### 🟢 P6: Remaining ~12 uncovered drugs (lower priority)
These TL1A drugs still have no mol_intel: cantai-tl1a, generate-uc, hbm2001, hy8931, lbl053, lq080, lq082, pr203, sab06, spx306, es302 (Elpiscience). Run after P5 fix is applied.

---

## Architecture State (as of 2026-05-23)

```
DB (Supabase):
  enrichment_runs         ← live (v16 applied 2026-05-23)
  provenance_events       ← DESIGN ONLY (v17 not designed yet)  
  assertion_history       ← DESIGN ONLY (v18 not designed yet)
  drugs                   ← live; last_enriched_model written on every enrichment (v16)
  drug_area_scores        ← live; 93 rows (was 152); clean — 3 intentionally-deferred orphans remain
  drug_areas              ← live; 179 rows (was 160)
  company_profiles        ← live; 37/60 enriched (regeneron tslp+il4ra freshly populated, Session 8)
  validation_tests        ← live; 71 tests, all passing
  catalysts               ← live; Roche dedup pending
  molecule_intelligence   ← live; 51 records; ~12 uncovered TL1A drugs remain

UI (GitHub Pages - commit 577ba0e):
  Entity dossier          ← live; molecule tab + overlap bugs fixed
  Confidence badges       ← live; showing ? until source_url populated
  Company dossier         ← live; 5 tabs
  Drug dossier            ← live; 3 tabs (Phase 2 features in design)
```

---

## Known Issues

| Issue | Severity | Status |
|-------|----------|--------|
| 3 remaining `drug_area_scores` orphans | Low | omalizumab/autoimmune, tisagenlecleucel/autoimmune (both marginal), benralizumab/tslp (downstream mechanism) — intentionally deferred |
| drug_area_scores.source_url null (some rows) | Low | Genuinely inferred — early-stage/private pipelines; acceptable |
| Roche catalyst near-duplicates (~10) | Medium | AMETRINE appears 3×, QX031N appears 4× — needs P4 dedup |
| ensure_canonical_id() doesn't insert into canonical_drugs | Medium | Workaround applied for 3 drugs; fix in P5 |
| ~12 TL1A drugs still have no mol_intel | Low | Lower-priority; enrich after P5 fix |
| Confidence badges all show '?' | Low | Will resolve once enrichment re-run populates source_url |
| argx-117 target field mislabeled in drugs table | Low | Shows FcRn×CD131 but is actually anti-C2 complement mAb |
| cendakimab company mislabeled in drugs table | Low | Shows astrazeneca; drug belongs to AbbVie/Receptos |

---

## Code Deployed This Session

**Commit `577ba0e`** on `kyleklaassen-dev/bd-dashboard` (GitHub Pages):
- Drug dossier Molecule tab always shown
- Drug dossier overlap now reads from `drug_area_scores` (not `drug_areas`)
- Overlap fallback to `drugs.overlap` when area scores return null
- Confidence badges (✓ ≈ ~ ?) in drug dossier header chips
- All 9 QA bugs patched

**Commit `01141bf`** on `scripts/company_enrichment.py`:
- `_AREA_SCORE_FIELDS` expanded: `source_url` + `confidence_level` now flow to `drug_area_scores`
- `enriched_model` written to `drug_area_scores` on every enrichment write (v16 column)
- `last_enriched_model` written to `drugs` and `company_profiles` on every write (v16 columns)
- Prompt hardened: `confidence_level` REQUIRED; `inferred` must explain why in `overlap_rationale`
- `source_url` prompt clarified: priority order CT.gov → company IR → press release; never fabricate

**Commit `14df877`** — Drug identity audit + merges:
- `docs/drug_identity_audit.md` — full audit of 4 duplicate candidates
- Supabase: Merge A (pf-06480605→afimkibart), Merge B (hxn1003→erd-1), data fix C (ep006)
- `update_log.md` — Session 5 entry

**Commit `1e79552`** — Source verification + enrichment script flags:
- `scripts/source_verify.py` — new standalone source_url populator (no web search)
- `scripts/company_enrichment.py` — `--skip-discovery` and `--skip-web-search` flags
- `timeout=90s` added to both web search API calls (prevents infinite hang)

**Commit `a4dc837`** on `scripts/molecule_enrichment.py` — new:
- Standalone targeted molecule enrichment (per-drug, not per-company)
- 20 priority drugs enriched; mol_intel: 31 → 51
- delete-then-insert write pattern; canonical_drug_id FK handling

---

## Quick Reference

**Deploy to GitHub Pages:**
```bash
WS="/sessions/wonderful-dazzling-pasteur/mnt/BD Platform"
TMP=$(mktemp -d)
TOKEN=$(cat "$WS/.github_token")
git clone "https://$TOKEN@github.com/kyleklaassen-dev/bd-dashboard.git" "$TMP"
cp "$WS/index.html" "$TMP/index.html"
cd "$TMP" && git add index.html && git commit -m "..." && git push
```

**Supabase REST PATCH:**
```bash
SUPA_URL="https://[project-ref].supabase.co"
KEY=$(cat "$WS/.supabase_service_key")
curl -s -X PATCH "$SUPA_URL/rest/v1/[table]?[filter]" \
  -H "apikey: $KEY" -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" -H "Prefer: return=representation" \
  -d '{"field": "value"}'
```

**Validate ground truth:**
```bash
cd "$WS" && python3 scripts/validate_ground_truth.py
```

**Supabase dashboard:** [Dashboard → SQL Editor for v16 migration]

**Files to read before editing index.html:**
- `memory/MEMORY.md` → `user_platform_context.md` → design principles
- `docs/dossier_phase2.md` → Phase 2 roadmap
- `docs/provenance_architecture.md` → planned schema
