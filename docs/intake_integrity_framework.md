# Meridian Intake Integrity Framework

**Version:** 1.0  
**Written:** 2026-05-23  
**Status:** Active operating rule

---

## Core Principle

> **The dashboard is the view layer. Supabase is the source of truth.**

No information should live only in the frontend. Everything that appears in the dashboard must:

1. **Exist in Supabase** — in the correct canonical table, with a valid primary key
2. **Be verifiable** — source_url, confidence_level, and/or added_by populated
3. **Be findable** — consistently queryable using the same patterns across all tabs
4. **Be enrichable** — structured in a way that enrichment pipelines can update it

Manual corrections are not exempt. If Kyle notices something wrong and fixes it, that fix must still produce a structured Supabase record with a source, a validation test where appropriate, and a log entry.

---

## Canonical Tables

| Entity | Canonical Table | Rendering Source |
|--------|----------------|-----------------|
| Company | `companies` | All dashboard tabs, Pharma Landscape |
| Drug | `drugs` | Drugs to Know (via `catalog_category`), area tabs (via `drug_areas`) |
| Drug-Area relationship | `drug_areas` | Area tabs — which companies/drugs appear |
| Drug-Area score | `drug_area_scores` | Overlap tier badge, confidence level |
| Molecule intelligence | `molecule_intelligence` | Drug dossier — mechanism, endpoints, trial data |
| Company profile | `company_profiles` | Company dossier — platform summary, BD angle, key risk |
| Catalyst | `catalysts` | Timeline views, catalyst cards |
| Deal | `deals` | Deal history, BD intelligence |
| Clinical trial | `trials` | Trial cards, catalyst triggers |
| Validation test | `validation_tests` | Automated QA suite — ran via validate_ground_truth.py |

---

## The Invariants

These rules must hold at all times. Violations are bugs, not features.

1. **DKN Coverage**: If a drug has a `drug_areas` entry (appears in any area tab), it MUST have `drugs.catalog_category IS NOT NULL`.
2. **Area Consistency**: If a company appears in any disease-area tab, it must have a `company_areas` row for that area.
3. **Overlap Required**: If a drug appears in an area tab, it must have a `drug_area_scores` row with `overlap` set for that area.
4. **Catalyst Sourcing**: If a catalyst card displays data, that record must exist in `catalysts` with `company_id` + `label`.
5. **Deal Sourcing**: If a deal is displayed, it must exist in `deals` with `company_id` + `deal_type` + `headline`.
6. **Molecule Data**: If a drug card shows mechanism/targets/endpoints, that data must exist in `molecule_intelligence` or `drugs` fields — not be hardcoded in JS.
7. **Confidence Required**: All `drug_area_scores` rows must have `confidence_level` set (confirmed / supported / inferred).
8. **Source Required for Confirmed**: Any record with `confidence_level = 'confirmed'` must have a non-null `source_url`.

---

## The Five Intake Paths

Every piece of information entering Meridian must flow through one of these paths.

### Path 1: Company Intake

**Trigger:** A new company is identified (via signal, literature, web search, or manual discovery).

```
Signal / User identifies company
    → company_intake.py (or manual correction script)
    → discovery_queue (review stage)
    → Approve → companies table
    → company_areas (which therapeutic areas?)
    → company_profiles (enrichment via quick_profiles_enrich.py)
    → drug_areas (which drugs?)
    → drug_area_scores (overlap classification)
    → Dashboard rendering (automatic — no frontend changes needed)
```

**Required fields at intake:** `id`, `name`, `company_type`, `status`
**Required fields before area tab appears:** `company_areas` row for that area

### Path 2: Drug Intake

**Trigger:** A new drug is identified (new clinical filing, press release, licensing deal, enrichment discovery).

```
Signal / User identifies drug
    → drug_intake.py (or manual correction script)
    → discovery_queue (review stage)
    → Approve → drugs table (with catalog_category, target, stage, company_id)
    → canonical_drugs (canonical ID if not present)
    → drug_areas (which therapeutic areas?)
    → drug_area_scores (overlap tier, confidence, source_url)
    → molecule_intelligence (mechanism, endpoints, trial data)
    → Dashboard rendering (DKN shows automatically; area tab shows via drug_areas)
```

**Required fields at intake:** `id`, `display_name`, `company_id`, `target`, `stage`, `catalog_category`, `confidence_level`, `source_url`, `discovery_status`
**Validation test:** Should be added for any Direct/Adjacent drug in a core area

### Path 3: Evidence Intake

**Trigger:** A URL, press release, abstract, investor deck, or regulatory filing contains new intelligence.

```
User provides URL or text
    → evidence_intake.py (entity extraction)
    → Extracts: company names, drug names, trial IDs, deal terms, catalyst events
    → Routes each entity to discovery_queue
    → Review: confirm entity matches, classification
    → Supabase writes: drugs, drug_area_scores, catalysts, deals, trials
    → Enrichment: company_profiles, molecule_intelligence updated
    → Validation: relevant tests run
    → Dashboard renders from Supabase
```

**Source tracking:** Every evidence extraction must write `source_url` to all affected records.

### Path 5: Transaction Intake

**Trigger:** A company acquisition, licensing deal, merger, option exercise, platform collaboration, or spin-in/spin-out is identified.

**Core principle:** Acquisitions and licensing deals are **pipeline import events**, not single-asset additions. When a company acquires another entity or signs a major deal, the correct response is to ingest the entire acquired pipeline — all stages — not just the headline asset.

**Wrong pattern (what many databases do):**
```
UCB acquires Candid → add cizutamig → stop
```

**Correct pattern (what Meridian does):**
```
UCB acquires Candid
→ ingest all Candid assets (cizutamig, CND319, CND460, discovery programs)
→ ingest all targets and modalities
→ ingest all trials and catalysts
→ ingest all deals that transferred
→ re-map company_areas for UCB
→ refresh company profile (platform_summary, bd_summary, key_risk)
→ re-score strategic relevance
```

```
Transaction identified
    → Identify acquired company / licensed asset / deal scope
    → Company Intake (if new company): companies table + company_areas
    → Drug Intake (for ALL acquired assets, all stages):
        drugs table → drug_areas → drug_area_scores → molecule_intelligence
    → Deals Intake: deals table (deal_type, headline, value, date)
    → Catalyst Intake: any upcoming readouts or option windows
    → Acquirer re-enrichment: company_areas re-mapped, company_profiles refreshed
    → Validation: run catalog_visibility + overlap tests for all new drugs
    → Log: update_log.md entry documenting scope of pipeline import
```

**Acquisition intake checklist:**
1. What assets did the acquired company own? (all stages, not just clinical)
2. What preclinical / discovery programs existed?
3. What platform technologies transferred?
4. What partnerships and rights transferred?
5. Which disease areas are newly impacted?
6. Which area tabs should gain the acquirer as a company?
7. Which drugs should get `partner_company` updated to the acquirer?
8. Does the acquirer now appear in new competitive landscapes?

**Licensing deal intake checklist:**
1. Is the licensed asset new to Meridian?
2. Does the licensor have related follow-on programs?
3. Is the deal asset-specific or platform-wide?
4. Are options included (could expand scope later)?
5. Does this deal move the licensee into a new area?
6. Update: `drugs`, `company`, `company_areas`, `drug_areas`, `deals`, `catalysts`, `company_profiles`

**Canonical example — UCB acquires Candid Therapeutics (May 2026):**
- Added: cizutamig (BCMA×CD3), CND319 (CD19×CD20×CD3), CND460 (BCMA×CD19×CD3)
- UCB added to: `tcell` + `autoimmune` company_areas
- Deals logged: UCB/Candid acquisition, UCB/Antengene ATG-201 license
- UCB profile: flagged for refresh to reflect TCE platform addition

**Why this matters:** CND460 (BCMA×CD19×CD3 trispecific) is more strategically interesting than the lead asset cizutamig because it covers the exact target combination of the BCMA×CD19×CD3 area tab. Asset-centric intake would have left CND460 invisible.

---

### Path 4: Manual Correction Intake

**Trigger:** Kyle notices something wrong while reviewing the dashboard.

```
Kyle notices issue
    → Identify the canonical table and field that's wrong
    → Write correction via script (sb_patch call or Python one-liner)
    → Add source_url and confidence_level to corrected record
    → Add validation test to prevent regression (when appropriate)
    → Write entry to update_log.md
    → Commit to GitHub
    → Dashboard re-renders from Supabase (no frontend changes needed)
```

**Rule:** Manual corrections must never remain as informal notes or frontend-only edits. The correction is not done until it's in Supabase, logged, and optionally validated.

---

## Current Violations (Audited 2026-05-23)

### Frontend-Only Data Sources

| Location | Data | Status |
|----------|------|--------|
| `index.html` TL1A tab — `tl1aPI` object | ~1700-line static JS object with legacy TL1A data | ⚠️ Partially superseded by Supabase; flagged for future refactor |
| `index.html` static HTML in Drugs to Know area tabs | Per-area drug lists (TSLP, FcRn, IL-4Rα, etc.) | ⚠️ Static backup views — Supabase is now primary |
| `index.html` valuation cards | Deal value estimates hardcoded in HTML | ❌ Not in Supabase |
| `index.html` Ailux positioning cards | AI differentiation narrative | ❌ Not in Supabase (`ailux_positions` table exists but not fully used) |

### Supabase Tables Bypassing Enrichment

| Table | Issue |
|-------|-------|
| `drugs` — `catalog_category` | Never set by enrichment pipelines — must be set manually. Causes DKN invisibility. |
| `companies` — `added_by`, `added_at` | No tracking of how/when a company was added |
| `drug_areas` — `source_url` | Not consistently populated; enrichment doesn't always set this |
| Manual SQL inserts (all tables) | Bypass all tracking — no `added_by`, no validation test |

### Enrichment Gaps Without Validation

| Gap | Status |
|-----|--------|
| Drugs with `drug_areas` but `catalog_category = null` | Fixed 2026-05-23 (38 drugs patched); validation test `catalog_visibility` added |
| Company with drug_areas but no `company_areas` | No validation test — should be added |
| Drug with `drug_area_scores.overlap` set but no `source_url` | Partial — `source_verify.py` helps but not complete |

---

## Proposed Enforcement Rules

### Rule E1: catalog_visibility invariant
```
Every drugs.id that appears in drug_areas must have drugs.catalog_category IS NOT NULL
```
**Validation test type:** `catalog_visibility`  
**Current status:** Test type implemented in validate_ground_truth.py

### Rule E2: drug_area_scores completeness
```
Every drug_areas row must have a corresponding drug_area_scores row with overlap, confidence_level set
```
**Not yet enforced.** Recommend adding `area_coverage_check` test type.

### Rule E3: company_area consistency
```
Every company that has drugs in drug_areas for area X must have company_areas(company_id, area_id=X)
```
**Not yet enforced.** Recommend adding check to enrichment pipeline.

### Rule E4: catalog_category must be set at drug creation
**Implementation:** Update `company_enrichment.py` and `molecule_enrichment.py` to always write `catalog_category` when inserting a new drug record. Suggested defaults:
- Immunology biologics (mAb, bispecific, protein): `'Pipeline'` (if clinical) or `'Immunology'` (if approved)
- Small molecules: `'Small Molecule'`
- Oncology agents: `'Oncology'`
- Combo studies: `'Combo Study'`

---

## Admin Workflow for Manual Corrections

When Kyle notices an issue:

1. **Identify** — which table, which row, which field
2. **Fix** — Python patch script (never raw SQL without tracking)
3. **Source** — add `source_url` + `confidence_level` to patched record
4. **Test** — add `validation_tests` row if this type of error can recur
5. **Log** — add entry to `update_log.md` with root cause
6. **Commit** — push scripts + logs to GitHub

Example pattern (from Session 8b — LQ080 company fix):
```
Issue: lq080.company_id = 'lanova' (wrong)
Fix: PATCH drugs SET company_id='novamab' WHERE id='lq080'
Source: https://www.novamab.com/pipeline (confidence='supported')
Test: company_check test — entity_id=lq080, expected_value=novamab, P1
Log: update_log.md entry — root cause was enrichment misattributing drug from comparison table
Commit: pushed validate_ground_truth.py + company_enrichment.py
```

---

## Implementation Priority

| Priority | Rule | Effort | Impact |
|----------|------|--------|--------|
| P0 (done) | DKN coverage: catalog_category on all area-tab drugs | Low | High — 38 drugs now visible |
| P0 (done) | catalog_visibility validation test type | Low | High — prevents future gaps |
| P1 | Set catalog_category in enrichment pipeline writes | Medium | High — prevents regression |
| P2 | drug_area_scores completeness validation | Low | Medium |
| P2 | company_area consistency validation | Medium | Medium |
| P3 | Migrate tl1aPI static JS object to Supabase | High | High (long-term) |
| P3 | Add `added_by` / `added_at` columns to all canonical tables | Medium | Medium |
| P4 | Evidence intake pipeline (evidence_intake.py) | High | High (long-term) |

---

## Related Documents

- `docs/provenance_architecture.md` — Provenance schema design (enrichment_runs, assertion_history)
- `docs/source_verification_audit.md` — Source URL coverage audit
- `docs/company_coverage_audit.md` — Enrichment priority ranking
- `migrations/v16_provenance.sql` — Provenance schema migration (not yet applied to all tables)
- `scripts/validate_ground_truth.py` — Automated validation suite
- `scripts/company_enrichment.py` — Main enrichment pipeline
- `scripts/quick_profiles_enrich.py` — Lightweight company profile enricher
- `update_log.md` — Session-by-session change log
