# BD Platform — Architecture Status
**As of 2026-05-22 | For: Kyle Klaassen**

This document is the authoritative snapshot of platform state. Updated after each major hardening session.

---

## 1. Current Architecture Status

### What Has Been Built ✅

**Database (Supabase — 21 tables, v1–v20 migrations applied)**

| Table | Purpose | Status |
|---|---|---|
| `disease_areas` | 6 coverage pillars (TL1A, TSLP, IL-4Rα, FcRn, IGF1R, T-cell) | ✅ Seeded |
| `companies` | Pharma companies; `status='acquired'` hides from dashboard | ✅ Live |
| `company_areas` | Company ↔ area junction | ✅ Live |
| `company_aliases` | Canonical name resolution; 89 aliases, 19 companies (v17) | ✅ Live |
| `company_signals` | Individual intel bullets per company/area | ✅ Live |
| `company_profiles` | Enriched profiles (intelligence cards, completeness) | ✅ Live |
| `drugs` | Drug records; `data_source='catalog'` (100 DKN drugs) \| `'enriched'` | ✅ Live |
| `drug_area_scores` | Area-specific competitive scores per drug (v20); UNIQUE(drug_id, area_id) | ✅ Live — 119 rows |
| `drug_areas`, `drug_targets` | Drug junction tables | ✅ Live |
| `canonical_drugs`, `drug_aliases` | Drug identity spine (v5) | ✅ Live |
| `trials` | ClinicalTrials.gov records with `canonical_drug_id`, `area_fit` | ✅ Live |
| `deals` | BD deal log with `company_id` FK | ✅ Live |
| `intel` | News/data items; `primary_company_id` FK (v19) | ✅ Live — 345 rows |
| `intel_areas`, `intel_companies` | Intel junction tables | ✅ Live |
| `catalysts` | Upcoming readouts/filings; deduplicated via unique expression index (v18) | ✅ Live — 595 rows |
| `molecule_intelligence` | AI-generated per-drug molecular intelligence cards (intrinsic facts only) | ✅ Live |
| `discovery_queue` | Step 1 entity discoveries with relationship classification | ✅ Live |
| `research_queue` | Prioritised enrichment backlog (0–200 priority score) | ✅ Live |
| `identity_audit_log` | Append-only resolver decision log | ✅ Live |
| `resolver_errors` | Failed resolutions with retry tracking | ✅ Live |

**Pipeline scripts (GitHub Actions — nightly on all 6 areas)**

| Script | Role | Status |
|---|---|---|
| `ct_gov_sync.py` | Step 3 — syncs clinical trials from ClinicalTrials.gov; stamps `canonical_drug_id` | ✅ Running nightly |
| `company_enrichment.py` | Steps 1, 4, 5, 6 — entity discovery, catalyst generation, enrichment, deal intelligence, molecule intelligence | ✅ Running nightly (all 6 areas) |
| `research_intelligence.py` | Step 7 — completeness scoring, trigger detection, research queue update | ✅ Running nightly (all 6 areas) |
| `research.py` | Nightly news/intel harvest; writes `intel` with `primary_company_id` FK | ✅ Running nightly |

**Identity + Integrity layer**

| Script | Role | Status |
|---|---|---|
| `identity_resolution.py` + `DrugIdentityResolver` | Resolves any drug name → `canonical_drug_id` (4-step cascade) | ✅ Wired into ct_gov_sync + company_enrichment |
| `company_identity_resolver.py` + `CompanyIdentityResolver` | Resolves any company name → `company_id` (loads from `company_aliases`) | ✅ Built; wired into research.py |
| `one_time_migration.py` | Backfill scripts (canonical IDs, deals company_id) | ✅ Complete (53/53 drugs, deals backfilled) |
| `identity_health_check.py` | Weekly health report; includes `reconcile_profiles_areas()` | ✅ All green |
| `catalog_backfill.py` | One-time: parsed DRUGS_ALL → seeded 100 catalog drugs in Supabase | ✅ Complete |

**Dashboard frontend**

`index.html` — fully dynamic Supabase-driven dashboard on GitHub Pages. All sections fetch live from Supabase. No static data arrays remain in production code (DRUGS_ALL removed, P2-C complete).

---

### Data Integrity Hardening — Phase 0 + Phase 1 Complete ✅

All items from the hardening plan required before Tier 1 signal volume are done:

| Item | Done | What it fixed |
|---|---|---|
| P0-A: Workflow consolidation | 2026-05-21 | Retired duplicate nightly runs; reserved 02:30 UTC slot for signal_monitor |
| P0-B: reconcile_profiles_areas() | 2026-05-21 | Repairs orphaned company_profiles with no matching company_areas entry |
| P0-C: Backfill deals.company_id | 2026-05-21 | Stamped company_id FK on research.py-written deals; now surface in Company Database |
| P1-A: CompanyIdentityResolver | 2026-05-21 | Canonical company name resolution; 89 aliases seeded |
| P1-B: intel.primary_company_id | 2026-05-22 | Direct FK from intel to companies; eliminates junction JOIN on company intel queries |
| P1-C: Catalyst UNIQUE constraint | 2026-05-22 | Deduplicated 474 duplicate catalysts; expression index + pre-check prevents recurrence |
| P1-D: drug_area_scores table | 2026-05-22 | Area-specific overlap/cls/vs_ailux per drug; parallel write from enrichment |
| P2-C: DRUGS_ALL → Supabase | 2026-05-22 | DKN tab now live from `drugs?data_source=eq.catalog`; 45 KB static array removed |

---

### Remaining Hardening Items

| Item | Phase | Status | Notes |
|---|---|---|---|
| P2-A: molecule_intelligence split | P2 | ✅ Already correct | `write_molecule_intelligence()` already writes only intrinsic fields; area-specific competitive analysis lives in `drug_area_scores.vs_ailux_positioning` |
| P2-B: Remove drugs.overlap/cls columns | P2 | Pending | After dashboard is updated to read from `drug_area_scores` (Phase 2 of Molecule DB migration) |
| P3-A: Financial columns on companies | P3 | Pending | Add `revenue_usd_b`, `r_and_d_usd_b`, `market_cap_usd_b` to companies table; surface in Company Database panel |

---

## 2. Data Flow — Source to Dashboard

### Companies + Entity Discovery
```
Claude API + Supabase context (company_enrichment.py Step 1)
  → discovery_queue              (new entities for human review)
  → companies + company_areas    (on approval via approve_discovery_item())
    → PI table entity rows on all tabs
    → Company Database slide-over panel
```

### Drugs / Programs
```
Supabase catalog seed (catalog_backfill.py — one-time)
  → drugs (data_source='catalog')   → Drugs-to-Know tab (live Supabase query)

company_enrichment.py Step 5 (drug_updates in enrichment response)
  → drugs table                     (overlap, cls, vs_ailux, stage, drug_summary, etc.)
  → drug_area_scores                (parallel write: overlap, cls, vs_ailux_positioning per area)
    → PI table drug accordion rows
    → Drug popup overlays
```

### Trials
```
ClinicalTrials.gov API (ct_gov_sync.py — nightly)
  → trials (nct_id, phase, status, pcd, area_fit, canonical_drug_id)
    → Drug expanded rows (trial list)
    → Catalyst generation input (Step 4)
    → Completeness scoring Stage 3
```

### Catalysts
```
trials.primary_completion_date + Claude API (company_enrichment.py Step 4)
  → catalysts (deduped via expression unique index on company_id, drug_id, catalyst_type, sort_date)
    → Home tab: catalyst countdown badges
    → PI tabs: catalyst section in company expanded rows
```

### Company Profiles + Intelligence
```
Claude API web research (company_enrichment.py Step 5)
  → company_profiles (platform_intelligence JSONB, bd_intelligence JSONB, vs_ailux, strategic_behavior)
    → Company Database slide-over: Assessment card, BD card
    → PI table expanded rows
```

### Intel (News + Signals)
```
Claude API news harvest (research.py — nightly at 06:00 UTC)
  → intel (primary_company_id FK for direct lookups)
  → intel_companies junction
    → Company Database intel feed
    → Home tab intel stream
```

### Molecule Intelligence
```
Claude API molecular research (company_enrichment.py Step 5 molecule_updates)
  → molecule_intelligence (canonical_drug_id UNIQUE — one row per molecule)
    Intrinsic fields only: format, modality, valency, igg_subclass, fc_engineering,
    epitope, affinity_kd, safety_observations, differentiation_claim, field_status
    → Drug accordion: Molecule card with field_status badges
```

### Deals
```
Claude API deal research (company_enrichment.py Step 6)
  → deals (company_id FK — surfaces in Company Database)
    → BD Activity section on PI tabs
    → BD Deal Tracker on Industry Insights tab
```

### Completeness + Research Queue
```
All tables → research_intelligence.py (nightly, all 6 areas)
  → drugs.completeness_score / completeness_tier / next_best_action
  → research_queue (priority 0–200, reason, missing_fields, trigger_events)
    → Home tab: Research Queue panel (top 12 entities by priority)
    → Human review: bump status pending → in_progress → done
```

---

## 3. Identity Layer

### Drug Identity (DrugIdentityResolver)
- **4-step cascade:** exact alias match → normalised match → fuzzy flag (≥0.85, does NOT auto-merge) → create new canonical
- **Wired into:** `ct_gov_sync.py` (all trial writes) + `company_enrichment.py` (catalysts + deals)
- **Coverage:** 53/53 drugs resolved; trials + catalysts + deals all stamped with `canonical_drug_id`
- **Health:** run `python scripts/identity_health_check.py` — all green

### Company Identity (CompanyIdentityResolver)
- **Same 4-step pattern** as DrugIdentityResolver; loads aliases from `company_aliases` table
- **89 aliases** covering 19 companies (seeded from ticker, common names, subsidiaries)
- **Wired into:** `research.py` (intel writes set `primary_company_id`)
- **Future:** wire into signal_monitor.py when built

### Identity Rules
- **NO auto-merge on fuzzy matches** — human must verify; all flagged in `identity_audit_log`
- **Manual merge workflow:** `SELECT * FROM identity_audit_log WHERE operation='flag_review'` → verify → `UPDATE drugs SET canonical_drug_id = 'CANON_DRUG_CORRECT' WHERE id = ?`

---

## 4. Key Schema Facts (current state)

- `drug_area_scores.UNIQUE(drug_id, area_id)` — area-specific competitive classification; safe to write per enrichment run without overwriting cross-area data
- `catalysts.idx_catalysts_dedup` — expression index on `(company_id, COALESCE(drug_id,''), catalyst_type, sort_date)` prevents duplicates; enrichment uses sb_get pre-check (PostgREST can't use expression indexes as on_conflict targets)
- `intel.primary_company_id` — direct FK for O(1) company intel lookups (replaces junction join)
- `drugs.data_source` — `'catalog'` = 100 DKN drugs from original DRUGS_ALL; `'enriched'` = pipeline-written
- `company_aliases.company_id` FK + `UNIQUE(company_id, alias_name)` — CompanyIdentityResolver loads from this on init
- `companies.status='acquired'` — hides company from all dashboard views; drug folds into acquirer with licensor pill

---

## 5. Remaining Work (in priority order)

### Phase 2 — During Molecule Database Migration
1. **P2-B:** Update dashboard drug accordion to read `overlap`/`cls` from `drug_area_scores` instead of `drugs` → then drop `drugs.overlap`, `drugs.cls`, `drugs.overlap_rationale` columns
2. **Combination programs:** `drug_combinations` table is populated but not yet rendered in the dashboard

### Phase 3 — Post Tier 1
3. **P3-A:** Add financial columns to `companies` table (`revenue_usd_b`, `r_and_d_usd_b`, `market_cap_usd_b`, `employee_count`); surface in Company Database slide-over
4. **Research queue feedback loop:** have `company_enrichment.py` read priority scores from `research_queue` to decide enrichment depth per entity (close the loop)

### Tier 1 — Signal Monitor (next major build)
5. **`signal_monitor.py`** — lightweight nightly scanner (no LLM): watch RSS/APIs for FDA filings, press releases, ClinicalTrials new registrations. Routes signals to companies via CompanyIdentityResolver. Feeds intel table. Triggers enrichment for high-priority signals. This is the "early warning system" that separates Meridian from a news archive.

---

## 6. Nightly CI Schedule (UTC)

| Time | Job | Script | Areas |
|---|---|---|---|
| 02:00–02:30 | CT.gov sync | `ct_gov_sync.py` | tl1a |
| 04:00 | Intelligence Pipeline | `company_enrichment.py` | tl1a |
| 04:10 | Intelligence Pipeline | `company_enrichment.py` | tslp |
| 04:20 | Intelligence Pipeline | `company_enrichment.py` | il4ra |
| 04:30 | Intelligence Pipeline | `company_enrichment.py` | fcrn |
| 04:40 | Intelligence Pipeline | `company_enrichment.py` | igf1r |
| 04:50 | Intelligence Pipeline | `company_enrichment.py` | tcell |
| 06:00 | Meridian Research | `research.py` | (all) |

*02:30 UTC slot reserved for future `signal_monitor.py`*

---

## 7. Deployment

- **Frontend:** single `index.html` → GitHub Contents API PUT (base64) → GitHub Pages auto-deploys
- **Scripts:** committed to `/scripts/` → GitHub Actions picks up on next scheduled run
- **Migrations:** `migrations/` directory, applied via Supabase Management API (`/v1/projects/{id}/database/query` with PAT token)
- **Credentials:** `.supabase_anon_key` (frontend read-only), `.supabase_service_key` (backend writes), `.supabase_pat` (DDL migrations), `.github_token` (non-workflow files), `.github_token_workflow` (workflow files)
