# Ailux BD Platform — Intelligence Architecture

> **Last updated:** 2026-05-19
> **Purpose:** Canonical specification for the platform's research intelligence graph — how information is discovered, structured, enriched, and compounded into BD-grade competitive intelligence.

---

## Core Principle

The platform operates as a **continuously compounding research graph**, not a static biotech database.

Every validated piece of information triggers the next logical research step. Data flows directionally through seven stages, each building on the last. The goal is not to collect data — it is to progressively understand competitive entities deeply enough to inform Ailux's BD strategy.

```
Entity Discovery
    → Drug / Program Mapping
        → Trial Intelligence
            → Catalyst Engine
                → Strategic Positioning
                    → Deal & Financial Intelligence
                        → Continuous Discovery Loop
```

The system compounds: more entities → more drugs → more trials → more catalysts → deeper strategy → better deal intelligence → discovery of new entities.

---

## Research Object Hierarchy

```
Strategic Competitive Entity            ← top-level unit of competitive tracking
    └── Company                         ← legal entity behind the asset
    └── Drugs / Programs                ← one or many per entity
          └── Trials                    ← one or many per drug
                └── Catalysts           ← generated from trial timelines
    └── Deals                           ← linked to entity + company + drug
    └── Company Profile                 ← narrative intelligence per area
```

**Why Entity is the top-level object, not Company:**
A single competitive threat can span multiple companies (partnerships, co-developments, licensing structures). Grouping by entity — not by company — reflects how real BD analysis works. You track *the asset and its story*, not just the corporate parent.

---

## Stage Definitions

---

### Stage 1 — Entity Discovery

**Goal:** Identify strategic competitive entities in a disease or target space. Answer: who exists, what are they building, and why do they matter?

**Inputs:**
- Company pipeline pages (web)
- Press releases and news feeds
- Investor decks and conference abstracts (ASCO, DDW, UEGW, etc.)
- ClinicalTrials.gov searches by target/indication
- Deal announcements (licensing, M&A)
- Prior-stage intelligence (a deal referencing an unknown asset)

**Outputs (Supabase records created/updated):**

| Table | Fields Set |
|---|---|
| `companies` | `id`, `name`, `ticker`, `company_type`, `hq_country` |
| `company_areas` | `company_id`, `area_id` |
| `drugs` | `id`, `name`, `company_id`, `entity_id`, `entity_name`, `entity_type`, `target`, `mechanism`, `indication_short`, `stage`, `discovery_status`, `confidence_score` |

**Trigger logic:**
```
IF confidence_score >= 85 → create with discovery_status = 'auto'
IF 60 <= confidence_score < 85 → create with discovery_status = 'unverified'
IF confidence_score < 60 → log only, do not write
IF entity already exists → skip creation, flag for enrichment check
```

**Downstream trigger:**
```
IF entity created → Stage 2 (drug mapping)
```

**Questions this stage answers:**
- Who exists in this space?
- What biology are they targeting?
- Is this a platform, partnered asset, or standalone drug?
- How confident are we in this discovery?

**Current implementation status:** ✅ Partially implemented
- `step1_discover_new_entities()` in `company_enrichment.py` uses Claude Haiku to scan for new competitors
- Creates company + drug + company_areas records on discovery
- Confidence scoring and `discovery_status` fields are on the schema
- **Gap:** No structured parsing of press releases or investor decks as input sources
- **Gap:** No CT.gov-driven entity discovery (searching by target/indication to find unknown entities)
- **Gap:** No deal-driven entity discovery (if a deal references an unknown company)

---

### Stage 2 — Drug / Program Mapping

**Goal:** Fully characterize every asset connected to a known entity. Answer: what exactly is the drug, what makes it different, and how does it fit the competitive landscape?

**Inputs:**
- Company pipeline pages
- Drug label / INN registration
- Published trial protocols
- Patent filings
- Conference presentations

**Outputs (Supabase records updated):**

| Table | Fields Set |
|---|---|
| `drugs` | `name`, `aliases` (JSONB array), `mechanism`, `target`, `drug_format`, `route`, `dosing_type`, `indication_short`, `stage`, `stage_detail`, `cls`, `overlap`, `differentiation_thesis` |

**Trigger logic:**
```
IF drug.name exists but mechanism is NULL → run drug mapping
IF drug.aliases is NULL → check INN registry + prior names
IF drug.differentiation_thesis is NULL → run Stage 5 (positioning)
IF drug.stage is NULL or 'unknown' → prioritize for trial sync (Stage 3)
```

**Downstream trigger:**
```
IF drug exists with a target → Stage 3 (trial sync)
```

**Questions this stage answers:**
- What exactly is the asset (antibody, small molecule, bispecific, CAR-T)?
- What pathways does it combine?
- Is it monospecific or multispecific?
- What prior names or aliases exist?
- What disease positioning does it have?
- What makes it mechanistically distinct?

**Current implementation status:** ✅ Schema supports, ⚠️ pipeline partial
- Schema has all fields: `aliases`, `mechanism`, `target`, `drug_format`, `route`, `dosing_type`, `differentiation_thesis`, `cls`, `overlap`
- `company_enrichment.py` Step 5 fills `differentiation_thesis` during enrichment
- **Gap:** No dedicated Stage 2 step — drug mapping is bundled into manual seeding + Step 5 enrichment
- **Gap:** No alias resolution (detecting that "CLD-423" = "QX030N" = same molecule)
- **Gap:** No INN registry check
- **Gap:** No structured patent / protocol parsing

---

### Stage 3 — Trial Intelligence

**Goal:** Build a complete, structured clinical evidence record for every tracked drug. Primary source: ClinicalTrials.gov.

**Inputs:**
- ClinicalTrials.gov API v2 (`/api/v2/studies/{nctId}`)
- ClinicalTrials.gov search (`/api/v2/studies?query.term=...`)
- NCT_SEED_MAP (curated known NCT IDs per drug)

**Outputs (Supabase records created/updated):**

| Table | Fields Set |
|---|---|
| `trials` | `id` (NCT ID), `drug_id`, `entity_id`, `trial_name`, `phase`, `status`, `n_enrollment`, `arms` (JSONB), `primary_endpoint`, `secondary_endpoints` (JSONB), `start_date`, `primary_completion_date`, `readout_date`, `source_url`, `sponsor`, `last_synced_date`, `discovery_status`, `confidence_score` |
| `drugs` | `trial_data_status` updated (`populated` / `missing` / `searching`), `stage` updated from trial phase |

**Trigger logic:**
```
IF drug has known NCT IDs in NCT_SEED_MAP → Step 3a: direct fetch (confidence = 100)
IF drug has no NCT IDs AND trial_data_status != 'pending' → Step 3b: search by name
    IF search confidence >= 85 → upsert discovery_status = 'auto'
    IF 60 <= confidence < 85 → upsert discovery_status = 'unverified'
    IF confidence < 60 → skip
IF drug.stage is outdated vs trial phases → Step 3c: update drug stage
IF trial.primary_completion_date is set → trigger Stage 4 (catalyst generation)
```

**Downstream trigger:**
```
IF trial.primary_completion_date exists → Stage 4 (catalyst engine)
IF trial results_note populated → Stage 5 (strategic positioning update)
```

**Questions this stage answers:**
- How advanced is the program clinically?
- What endpoints matter and at what timeframes?
- What data is upcoming, and when?
- What risks exist in the trial design (enrollment, endpoints, comparators)?
- How competitive is the study design vs. Ailux's asset?

**Current implementation status:** ✅ Fully implemented
- `ct_gov_sync.py` implements Steps 3a (direct NCT fetch), 3b (search discovery), 3c (stage update)
- Full CT.gov API v2 parsing: arms, endpoints, enrollment, dates, sponsor
- Confidence scoring (0–100) on all synced trials
- `discovery_status` / `confidence_score` written on every record
- `NCT_SEED_MAP` provides authoritative starting point for all known programs
- **Gap:** No results parsing (when a trial completes, results aren't auto-extracted)
- **Gap:** No interim analysis detection
- **Gap:** No head-to-head comparison parsing (identifying trials where Ailux's target appears as comparator)

---

### Stage 4 — Catalyst Engine

**Goal:** Convert clinical timelines into forward-looking strategic watchpoints. Transform "trial data" into "what matters next and when."

**Inputs:**
- `trials.primary_completion_date` (from Stage 3)
- `trials.status` (active vs. completed)
- Company-disclosed timelines (press releases, investor guidance)
- Conference calendars (ASCO, DDW, UEG, ACR)
- PDUFA calendar (for approved/submitted programs)

**Outputs (Supabase records created/updated):**

| Table | Fields Set |
|---|---|
| `catalysts` | `id`, `catalyst_date`, `sort_date`, `label`, `company_id`, `area_id`, `drug_id`, `related_trial_id`, `catalyst_type`, `significance`, `notes`, `expected_impact`, `is_key_watch`, `source_url`, `confidence_source` |

**Trigger logic:**
```
IF trial.primary_completion_date is within 24 months → create catalyst
IF catalyst already exists for this trial (via related_trial_id) → update date, skip creation
IF catalyst date has passed AND resolved = FALSE → flag for results check
IF significance >= 'High' AND strategic impact is clear → set is_key_watch = TRUE
IF company-disclosed date differs from CT.gov PCD by >90 days → flag discrepancy
```

**Downstream trigger:**
```
IF catalyst.significance = 'High' OR is_key_watch = TRUE → Stage 5 (strategic analysis)
IF catalyst resolved with positive data → Stage 6 (deal tracking, valuation shift)
```

**Questions this stage answers:**
- What events matter next for this entity?
- When will data shift the competitive landscape?
- Which catalysts could validate or threaten the TL1A / Ailux thesis?
- Are company-disclosed timelines consistent with CT.gov data?
- What's the delta between company guidance and registered PCD?

**Current implementation status:** ✅ Partially implemented
- `step4_generate_catalysts_from_trials()` in `company_enrichment.py` creates catalysts from PCD dates
- Idempotent via `related_trial_id` check (no duplicates)
- `is_key_watch`, `expected_impact`, `confidence_source` fields on schema
- **Gap:** No company-disclosure override logic (press release dates don't auto-update catalysts)
- **Gap:** No PDUFA calendar integration
- **Gap:** No conference calendar integration (ASCO abstract deadline → likely presentation date)
- **Gap:** No resolved catalyst result detection (when a catalyst passes, no auto-search for results)
- **Gap:** No discrepancy flagging (CT.gov PCD vs. company guidance)

---

### Stage 5 — Strategic Positioning

**Goal:** Interpret what the clinical and competitive data means for Ailux. This is the synthesis layer — turning structured data into BD-grade intelligence.

**Inputs:**
- All Stage 1–4 data for the entity (company profile, drugs, trials, catalysts)
- Ailux's asset profile (TL1A×IL-23p19, mechanism, stage, differentiation)
- Disease landscape context (who else is in the space, at what stage)
- Recent news / intel from daily research pipeline
- Deal history (what structures have been used in this space)

**Outputs (Supabase records created/updated):**

| Table | Fields Set |
|---|---|
| `company_profiles` | `platform_summary`, `bd_summary`, `key_risk`, `why_it_matters`, `vs_ailux`, `strategic_behavior`, `market_cap_usd_m`, `cash_runway`, `key_investors`, `financing_history`, `last_enriched_at` |
| `drugs` | `differentiation_thesis`, `cls`, `overlap` |

**Trigger logic:**
```
IF company_profile.last_enriched_at is NULL → run full enrichment
IF company_profile.last_enriched_at > 30 days ago → re-enrich
IF significant new trial data since last enrichment → re-enrich
IF new deal involving this company → re-enrich (deal context changes positioning)
IF drug stage advanced since last enrichment → re-enrich (competitive pressure changed)
```

**Downstream trigger:**
```
IF company is strategically important (cls = '1st Gen Direct' or 'Partnership') → Stage 6 (deal tracking)
IF enrichment reveals a previously unknown deal → Stage 6 (create deal record)
```

**Questions this stage answers:**
- Why does this entity matter to Ailux's BD strategy?
- Is it direct competition, adjacent competition, or a validation signal?
- What is mechanistically differentiated vs. Ailux's asset?
- What validates or threatens the TL1A × IL-23p19 mechanism?
- What is this company's BD posture (acquirer, licensor, partner-seeker)?
- How does their cash position affect urgency to deal?

**Current implementation status:** ✅ Substantially implemented
- `step5_enrich_company()` in `company_enrichment.py` using Claude Sonnet
- Writes all `company_profiles` fields including `vs_ailux`, `strategic_behavior`, `financing_history`
- `differentiation_thesis` on drugs written during enrichment
- CLASS × RELEVANCE framework applied via `cls` / `overlap` fields
- **Gap:** No trigger-based re-enrichment (always runs on schedule, not triggered by data changes)
- **Gap:** `vs_ailux` is on `company_profiles` only — should also exist at `drug` level (drug-level differentiation vs. Ailux's specific asset)
- **Gap:** No enrichment freshness check with automatic skip if recently run
- **Gap:** No structured Ailux context injection (the enrichment prompt uses Ailux's strategy but doesn't pull live Ailux asset data)

---

### Stage 6 — Deal & Financial Intelligence

**Goal:** Understand commercial validation, capital flows, and strategic movement in the space. Track who is transacting, at what valuations, and what it signals.

**Inputs:**
- Press releases (licensing, M&A, collaborations)
- SEC filings (8-K, 10-K for deal terms)
- BioPharma Catalyst / Evaluate Pharma / Fierce Biotech
- Company investor days and earnings calls
- Stage 5 enrichment output (which companies are strategically active)

**Outputs (Supabase records created/updated):**

| Table | Fields Set |
|---|---|
| `deals` | `deal_date`, `deal_date_label`, `from_company`, `to_company`, `area_id`, `drug_id`, `entity_id`, `deal_type`, `upfront_usd_m`, `total_usd_m`, `headline`, `detail`, `geography_rights`, `economics_royalties`, `strategic_signal`, `ailux_relevance`, `source_url`, `parties` |
| `company_profiles` | `market_cap_usd_m`, `cash_runway`, `financing_history`, `key_investors` updated |

**Trigger logic:**
```
IF new deal involving tracked company/drug → create deal record
IF deal upfront_usd_m > $200M → set significance = 'High', flag for strategic review
IF deal involves Ailux's target (TL1A, IL-23p19) → flag ailux_relevance
IF company raises financing → update cash_runway, financing_history
IF company acquired → update company_type, flag entity for re-positioning
```

**Downstream trigger:**
```
IF major deal in space → Stage 1 (check if new entities entered via deal)
IF deal prices a comparable asset → update competitive positioning context
IF company acquired → re-run Stage 5 (positioning changes under new parent)
```

**Questions this stage answers:**
- Who is validating this target/mechanism with capital?
- What deal structures are emerging (option, license, acquisition)?
- What are benchmark valuations for assets at this stage?
- Which companies are vulnerable (low cash) or aggressive (active acquirers)?
- How does deal activity shift Ailux's BD strategy or urgency?

**Current implementation status:** ⚠️ Partially implemented
- Deal records exist in Supabase with `ailux_signal`, `headline`, `detail`
- Stage 5 enrichment writes `deal_updates` as part of company profile
- New schema fields: `geography_rights`, `economics_royalties`, `strategic_signal`, `ailux_relevance`, `entity_id`, `parties`
- **Gap:** No automated deal discovery (deals are seeded manually or found during Step 5 enrichment)
- **Gap:** No SEC filing parsing
- **Gap:** No structured news-to-deal pipeline (news from daily research → deal extraction)
- **Gap:** `strategic_signal` and `ailux_relevance` fields exist but not yet populated by pipeline

---

### Stage 7 — Continuous Discovery Loop

**Goal:** Run the entire graph forward every night. Expand outward from validated information, identify gaps, refresh stale data, and score completeness.

**Nightly actions (per area):**
1. **New entity scan** — search for new competitors not yet in the database
2. **Drug completeness check** — flag drugs missing mechanism, target, stage, or differentiation_thesis
3. **Trial sync** — fetch all CT.gov updates for tracked drugs
4. **Catalyst refresh** — update dates, mark resolved, flag upcoming high-impact events
5. **Company enrichment** — re-enrich companies where profile is stale (>30 days) or data has changed
6. **Deal detection** — surface new deals from news feeds and Stage 5 synthesis
7. **Completeness scoring** — score each entity 0–100 based on populated fields per stage

**Completeness scoring model:**

| Stage | Weight | Key fields checked |
|---|---|---|
| Stage 1 — Entity exists | 10 pts | `entity_id`, `company_id`, `drug.name` |
| Stage 2 — Drug mapped | 15 pts | `mechanism`, `target`, `drug_format`, `stage`, `differentiation_thesis` |
| Stage 3 — Trials synced | 20 pts | ≥1 trial with `primary_completion_date` set |
| Stage 4 — Catalysts generated | 15 pts | ≥1 catalyst with `catalyst_date` within 24 months |
| Stage 5 — Profile enriched | 25 pts | `platform_summary`, `vs_ailux`, `strategic_behavior` set |
| Stage 6 — Deal intelligence | 15 pts | ≥1 deal record OR `financing_history` populated |
| **Total** | **100 pts** | |

**Trigger logic:**
```
IF completeness_score < 40 → entity is in early stage, prioritize for enrichment
IF completeness_score 40-70 → entity has gaps, queue for targeted fill
IF completeness_score > 70 → entity is well-researched, only refresh on trigger
IF any field has been NULL for >14 days → escalate to manual review flag
```

**Current implementation status:** ✅ Loop exists, ⚠️ completeness scoring missing
- Nightly GitHub Actions workflow runs both scripts sequentially
- New entity discovery, trial sync, catalyst generation, enrichment all run nightly
- **Gap:** No completeness scoring (no way to see which entities are well-researched vs. thin)
- **Gap:** No missing-field detection or escalation
- **Gap:** No "what changed since last run" delta reporting
- **Gap:** No prioritization logic (all companies enriched equally regardless of research depth)

---

## Data Model → Stage Mapping

| Supabase Table | Stage | Role |
|---|---|---|
| `companies` | Stage 1 | Created on entity discovery |
| `company_areas` | Stage 1 | Links company to disease area |
| `drugs` | Stages 1–3 | Core research object; enriched across all stages |
| `trials` | Stage 3 | CT.gov mirror; primary clinical evidence layer |
| `catalysts` | Stage 4 | Generated from trial timelines; strategic watchpoints |
| `company_profiles` | Stage 5 | Narrative intelligence per company × area |
| `deals` | Stage 6 | Commercial validation and deal structures |
| `intel` | Stage 7 | Daily news input; feeds Stages 1 and 5 |
| `company_area_detail` | View | Joins Stage 5 + Stage 1 for dashboard rendering |

**Key cross-stage fields:**

| Field | Table | Set By | Used By |
|---|---|---|---|
| `entity_id` | drugs, trials, deals | Stage 1 | All stages |
| `discovery_status` | drugs, trials | Stages 1, 3 | Stage 7 completeness |
| `confidence_score` | drugs, trials | Stages 1, 3 | Stage 7 prioritization |
| `trial_data_status` | drugs | Stage 3 | Stage 4 trigger |
| `related_trial_id` | catalysts | Stage 4 | Stage 4 dedup |
| `last_synced_date` | trials, drugs | Stage 3 | Stage 7 freshness |
| `last_enriched_at` | company_profiles | Stage 5 | Stage 7 staleness |
| `vs_ailux` | company_profiles | Stage 5 | Dashboard BD panel |
| `is_key_watch` | catalysts | Stage 4 | Dashboard Key Watch |

---

## Pipeline Script → Stage Mapping

| Script | Stages Implemented |
|---|---|
| `scripts/ct_gov_sync.py` | Stage 3 (Steps 3a, 3b, 3c) |
| `src/meridian/enrichment/company_enrichment.py` | Stages 1, 4, 5, 6 |
| `.github/workflows/company-enrichment.yml` | Stage 7 orchestration (nightly loop) |
| `index.html` (frontend) | Stage 7 display (reads all stages from Supabase) |

**Execution order per run:**
```
ct_gov_sync.py (Stage 3)
    → company_enrichment.py (Stages 1 → 4 → 5 → 6)
        → Supabase updated
            → index.html reads live data
```

Stage 2 (drug mapping) is currently handled through a combination of manual seeding at initial onboarding and Stage 5 enrichment filling in detail fields. There is no dedicated Stage 2 pipeline step.

---

## Gap Analysis — Priority Order

### P0 — Critical gaps (block intelligence quality)

| Gap | Stage | Impact |
|---|---|---|
| No completeness scoring per entity | Stage 7 | Can't see where intelligence is thin or prioritize enrichment |
| `vs_ailux` exists only on `company_profiles`, not `drugs` | Stage 5 | Drug-level Ailux differentiation not tracked |
| No trigger-based re-enrichment (always runs on schedule) | Stage 5/7 | New data (deal, trial result) doesn't auto-update positioning |
| Stage 2 has no dedicated pipeline step | Stage 2 | Drug mapping quality depends on manual seeding |

### P1 — Important gaps (reduce intelligence depth)

| Gap | Stage | Impact |
|---|---|---|
| No CT.gov-driven entity discovery (search by target) | Stage 1 | Unknown competitors with no press coverage won't be found |
| No company-disclosed timeline override for catalysts | Stage 4 | Catalyst dates may lag company guidance by months |
| No resolved catalyst results detection | Stage 4 | Passed catalysts don't auto-update with outcome |
| `strategic_signal` and `ailux_relevance` not yet populated | Stage 6 | Deal records lack strategic interpretation |
| No deal-driven entity discovery | Stage 1 | Deals referencing unknown companies don't create new entities |

### P2 — Future capabilities (expand intelligence breadth)

| Gap | Stage | Impact |
|---|---|---|
| No SEC filing parser | Stage 6 | Detailed deal economics not captured |
| No conference abstract detection | Stage 1/3 | Unpublished data not tracked until publication |
| No interim analysis detection from CT.gov | Stage 3 | Key interim readouts not auto-identified |
| No alias resolution pipeline | Stage 2 | Same molecule under different names tracked as separate assets |
| No structured Ailux asset profile in DB | Stage 5 | Ailux context hardcoded in prompt, not queryable |
| No head-to-head comparator detection | Stage 3 | Trials using Ailux's target as comparator not flagged |

---

## Future Feature Hooks

Each stage is designed to receive new input sources and output destinations without restructuring the core pipeline. New features should plug in as follows:

| Feature | Stage | Hook Point |
|---|---|---|
| Press release parser | Stage 1 | New input to `step1_discover_new_entities()` |
| Conference abstract monitor | Stage 1/3 | New input source alongside CT.gov |
| INN registry check | Stage 2 | New `step2_map_drug()` function in `company_enrichment.py` |
| Alias resolver | Stage 2 | Post-Step-2 dedup pass on `drugs` table |
| Completed trial results parser | Stage 3 | New Step 3d: parse `results_section` from CT.gov |
| PDUFA calendar | Stage 4 | New input to `step4_generate_catalysts_from_trials()` |
| SEC 8-K parser | Stage 6 | New input to `step6_deal_intelligence()` |
| Completeness scorer | Stage 7 | New `score_entity_completeness()` function |
| Enrichment trigger engine | Stage 7 | New `check_enrichment_triggers()` — fires Stage 5 on data change |
| Ailux asset DB record | Stage 5 | New `ailux_assets` table queried by enrichment prompt |

---

## Design Principles

**1. The graph is append-only at first, corrective over time.**
New entities start at Stage 1 with low completeness scores. The pipeline progressively fills gaps. Nothing is deleted until a human verifies it's wrong.

**2. Confidence degrades gracefully.**
`discovery_status` (manual → auto → unverified → verified) and `confidence_score` (0–100) prevent low-quality data from being treated as authoritative. The dashboard can surface confidence visually.

**3. Triggers are preferred over schedules.**
Ideally, new data triggers the next pipeline step immediately rather than waiting for the nightly run. Schedules are a fallback. As the system matures, trigger-based enrichment should replace blanket nightly runs.

**4. Every write is idempotent.**
All pipeline steps use upsert semantics. Re-running the same stage on the same data should produce identical results. This makes the pipeline safe to re-run after failures.

**5. Ailux context is always the output lens.**
Every Stage 5 output field (`vs_ailux`, `strategic_behavior`, `ailux_relevance`) is framed relative to Ailux's specific asset and BD situation. The platform's purpose is not to map the landscape in the abstract — it is to tell Ailux where to focus.

---

*This document is the canonical reference for all pipeline development. When adding new features, update this document first. When something doesn't behave as expected, check this document against the code.*
