# BD Platform — Architecture v2
### Intelligence-First Competitive Research System
*Version: 2.0 — 2026-05-19*
*Purpose: Feed this document into an AI model for evaluation, critique, and iterative improvement.*

---

## DOCUMENT PURPOSE

This document describes the full architecture of the BD Platform as it stands after the intelligence layer implementation. It is structured to enable iterative AI-assisted critique. After reading this document, a model should be able to:

1. Evaluate whether the 7-stage research graph is coherent and complete
2. Identify gaps between the intended architecture and the current implementation
3. Propose improvements to scoring logic, trigger conditions, or data model
4. Suggest new research stages or decision-tree branches
5. Flag assumptions that may not hold in real biotech BD workflows

---

## SYSTEM OVERVIEW

The BD Platform is an internal competitive intelligence tool for Ailux Therapeutics, a clinical-stage biotech developing drugs for TL1A and related inflammatory disease targets. The system tracks competitor drugs, clinical trials, corporate events (catalysts), deals, and strategic positioning across 6 disease areas.

**The core mission:** Turn raw biotech data into a guided research system where the platform itself knows what it understands well, what is missing, and what should be researched next.

**Disease areas tracked:**
- `tl1a` — TL1A pathway (inflammatory bowel disease focus)
- `tslp` — Thymic stromal lymphopoietin
- `il4ra` — IL-4 receptor alpha
- `fcrn` — Neonatal Fc receptor
- `igf1r` — Insulin-like growth factor 1 receptor
- `tcell` — T-cell biology

---

## THE RESEARCH GRAPH — 7 STAGES

The platform models competitive intelligence as a directed acyclic graph. Each stage consumes outputs from earlier stages and produces inputs for later stages. Research can be triggered at any stage when new data arrives.

```
Stage 1 ──► Stage 2 ──► Stage 3 ──► Stage 4
Entity       Drug         Trial        Catalyst
Discovery    Mapping      Intelligence Engine
                              │
                              ▼
                          Stage 5 ──► Stage 6 ──► Stage 7
                          Strategic   Deal         Continuous
                          Positioning Intelligence Loop
```

### Stage 1 — Entity Discovery
**Goal:** Identify all competitive entities (companies + drug programs) in each disease area.

**Inputs:**
- Manual seeding (known competitors)
- Claude-assisted web search
- ClinicalTrials.gov discovery (new trial sponsors)

**Outputs (Supabase):**
- `companies` table: `company_id` (TEXT PK), `company_name`, `area_id`, `cls`
- `drugs` table: `drug_id` (TEXT PK), `drug_name`, `company_id`, `area_id`, `entity_id`

**Key fields populated:**
- `entity_id` — groups all drugs/programs for one competitive entity
- `cls` — competitive classification (see CLASS×RELEVANCE framework below)
- `discovery_status` on drugs: `manual | auto | unverified | verified`

**Trigger logic:** Stage 1 re-runs when a new sponsor appears in CT.gov trial data that has no matching company record.

**Completion criteria (Stage 2 prerequisite):** `entity_id` is set, `drugs` list is non-empty, at least one drug has a `company_id`.

---

### Stage 2 — Drug Mapping
**Goal:** For each drug, document its mechanism of action, molecular target, development stage, and differentiation thesis vs. the Ailux pipeline.

**Inputs:** Drug records from Stage 1 + Claude enrichment + public sources

**Outputs (Supabase — drugs table):**
- `mechanism` — TEXT: mode of action (e.g., "anti-TL1A monoclonal antibody")
- `target` — TEXT: molecular target (e.g., "TL1A", "IL-4Rα")
- `stage` — TEXT: development stage (preclinical | phase 1 | phase 1/2 | phase 2 | phase 2/3 | phase 3 | approved)
- `differentiation_thesis` — TEXT: how this drug differs from others in class
- `aliases` — JSONB: alternative names / internal codes
- `confidence_score` — INTEGER 0–100: data quality confidence

**Current implementation gap:** Stage 2 has no dedicated pipeline script step. Drug mapping relies on the Claude enrichment in `company_enrichment.py` Step 5, which is not systematically structured to fill all 4 fields.

**Completion criteria (Stage 3 prerequisite):** `mechanism`, `target`, `stage`, and `differentiation_thesis` are all non-empty on all drugs.

---

### Stage 3 — Trial Intelligence
**Goal:** Synchronize all clinical trial data for all known drugs from ClinicalTrials.gov and additional sources. Ensure every trial has structured endpoint, arm, and timeline data.

**Inputs:**
- `NCT_SEED_MAP` — authoritative dict of `drug_id → [NCT IDs]` in `ct_gov_sync.py`
- ClinicalTrials.gov API v2: `https://clinicaltrials.gov/api/v2/studies/{nctId}`
- CT.gov full-text search for discovery (Step 3b)

**Outputs (Supabase — trials table):**
- `nct_id` — TEXT PK
- `drug_id` — TEXT FK
- `title`, `phase`, `overall_status`
- `primary_endpoint`, `secondary_endpoints` — TEXT
- `arms` — JSONB: arm names + sizes
- `start_date`, `primary_completion_date`, `estimated_completion_date` — DATE
- `sponsor`, `source_url`
- `discovery_status` — `manual | auto | unverified | verified`
- `confidence_score` — INTEGER 0–100
- `last_synced_date` — DATE
- `entity_id` — TEXT FK

**Pipeline script:** `ct_gov_sync.py`
- Step 3a: Direct fetch for known NCT IDs in NCT_SEED_MAP
- Step 3b: Search-based discovery for new trials not yet seeded
- Step 3c: Drug stage update — after syncing trials, update the drug's `stage` field if the trial phase is more advanced

**Completion criteria (Stage 4 prerequisite):** At least one trial per drug, trial has `arms` and `primary_endpoint`, `confidence_score >= 80`.

---

### Stage 4 — Catalyst Engine
**Goal:** Generate forward-looking catalysts from trial timelines — specific dates when trial readouts are expected, regulatory filings, or other binary events that will signal competitive progress.

**Inputs:** Trial `primary_completion_date` + `phase` + drug `stage` from Stage 3

**Outputs (Supabase — catalysts table):**
- `catalyst_id` — UUID PK
- `drug_id` — TEXT FK
- `title` — TEXT: catalyst description (e.g., "Phase 2 readout — TULIP-CD")
- `catalyst_type` — TEXT: `trial_readout | regulatory | corporate | partnership | investor_day`
- `expected_date` — DATE
- `outcome` — TEXT (filled after event occurs)
- `results_url` — TEXT
- `expected_impact` — TEXT: significance to competitive landscape
- `is_key_watch` — BOOLEAN: whether Ailux should prioritize monitoring
- `related_trial_id` — TEXT FK to trials
- `confidence_source` — TEXT: `estimated | announced | confirmed`

**Generation logic in `company_enrichment.py`:**
Step 4 — for each drug with trials but no existing catalyst, generate one catalyst per trial using Claude to infer expected date and impact from the trial timeline.

**Completion criteria (Stage 5 prerequisite):** At least one catalyst with `expected_date` and `title` exists.

---

### Stage 5 — Strategic Positioning
**Goal:** Assess each competitive entity's strategic position relative to Ailux. Populate the "vs. Ailux" analysis, competitive positioning, key differentiators, and overall threat level.

**Inputs:** Drug data from Stage 2, trial data from Stage 3, catalyst data from Stage 4, company financials from public sources

**Outputs (Supabase — company_profiles table):**
- `competitive_position` — TEXT: overall competitive assessment
- `vs_ailux` — TEXT: specific comparison to Ailux drug pipeline
- `key_differentiators` — JSONB: factors that distinguish this entity
- `strategic_behavior` — TEXT: observed M&A / partnership / financing patterns
- `market_cap_usd_m` — FLOAT
- `cash_runway` — TEXT
- `key_investors` — JSONB
- `hq_country` — TEXT
- `enriched_at` / `last_enriched_at` — TIMESTAMPTZ: when this profile was last updated

**Also written to drugs table:**
- `vs_competitor` — TEXT: drug-level competitive comparison (distinct from company-level `vs_ailux`)

**Current implementation gap:** `vs_ailux` is only on `company_profiles`, not at the drug level. The per-drug `vs_competitor` field is structurally present but rarely populated.

**Completion criteria (Stage 6 prerequisite):** `competitive_position`, `vs_ailux`, `key_differentiators` all non-empty.

---

### Stage 6 — Deal Intelligence
**Goal:** Track all partnerships, licensing agreements, M&A, and financing events for competitive entities. Understand the capital and partnership landscape.

**Inputs:** Public deal databases, press releases, SEC filings, Claude-assisted research

**Outputs (Supabase — deals table):**
- `deal_id` — UUID PK
- `entity_id` — TEXT FK
- `drug_id` — TEXT FK (optional — deal may be company-level)
- `deal_type` — TEXT: `licensing | acquisition | partnership | financing | co-development`
- `parties` — JSONB: companies involved
- `announced_date` — DATE
- `economics_royalties` — TEXT: financial terms
- `strategic_signal` — TEXT: what this deal signals about the entity's strategy
- `ailux_relevance` — TEXT: implications for Ailux
- `geography_rights` — TEXT

**Completion criteria:** At least one deal record with `economics_royalties` or `strategic_signal` populated.

---

### Stage 7 — Continuous Loop
**Goal:** Monitor all entities continuously for new data, trigger downstream updates when inputs change, and maintain the research priority queue.

**Mechanism:** The intelligence layer (`research_intelligence.py`) runs as the final step of the nightly pipeline. It scores every entity, detects triggers, and updates the `research_queue` table so the next pipeline run knows what to prioritize.

**Pipeline execution order:**
```
ct_gov_sync.py   → company_enrichment.py → research_intelligence.py
(Stage 3)          (Stages 1, 4, 5, 6)      (Stage 7 / all stages audit)
```

---

## DATA MODEL — COMPLETE SCHEMA

### Core Tables

#### companies
| Column | Type | Description |
|--------|------|-------------|
| company_id | TEXT PK | Slug identifier (e.g., "sanofi", "abbvie") |
| company_name | TEXT | Display name |
| area_id | TEXT | Disease area |
| cls | TEXT | CLASS×RELEVANCE classification (see below) |
| notes | TEXT | Free-form notes |
| created_at | TIMESTAMPTZ | Row creation time |

#### drugs
| Column | Type | Description |
|--------|------|-------------|
| drug_id | TEXT PK | Slug identifier (e.g., "tulisokibart", "afimkibart") |
| drug_name | TEXT | Display name |
| company_id | TEXT FK | Parent company |
| area_id | TEXT | Disease area |
| entity_id | TEXT | Groups drugs in the same competitive program |
| stage | TEXT | preclinical / phase 1 / phase 2 / phase 3 / approved |
| mechanism | TEXT | Mode of action |
| target | TEXT | Molecular target |
| aliases | JSONB | Alternative names |
| differentiation_thesis | TEXT | Key differentiating factors |
| vs_competitor | TEXT | Drug-level competitive vs. Ailux |
| results_summary | TEXT | Published results / outcomes |
| discovery_status | TEXT | manual / auto / unverified / verified |
| confidence_score | INT | 0–100 |
| trial_data_status | TEXT | populated / missing / searching / pending / unknown |
| last_synced_date | DATE | Last data sync from CT.gov |
| completeness_score | INT | 0–100 intelligence completeness |
| completeness_tier | TEXT | thin / partial / strong |
| missing_fields | JSONB | Field names with no data |
| missing_stages | JSONB | Stage names with gaps |
| next_best_action | TEXT | Recommended next research step |
| last_scored_at | TIMESTAMPTZ | When completeness was last computed |
| priority_score | INT | Research urgency 0–200 |
| trigger_flags | JSONB | Active trigger type strings |
| created_at | TIMESTAMPTZ | Row creation |
| updated_at | TIMESTAMPTZ | Last update |

#### trials
| Column | Type | Description |
|--------|------|-------------|
| nct_id | TEXT PK | NCT identifier |
| drug_id | TEXT FK | Parent drug |
| entity_id | TEXT | Parent entity |
| title | TEXT | Trial title |
| phase | TEXT | Phase 1 / 1/2 / 2 / 3 etc. |
| overall_status | TEXT | ClinicalTrials.gov status string |
| primary_endpoint | TEXT | Primary endpoint description |
| secondary_endpoints | TEXT | Secondary endpoints |
| arms | JSONB | Trial arms |
| start_date | DATE | |
| primary_completion_date | DATE | Readout date for catalyst generation |
| estimated_completion_date | DATE | |
| sponsor | TEXT | |
| source_url | TEXT | |
| discovery_status | TEXT | manual / auto / unverified / verified |
| confidence_score | INT | 0–100 |
| last_synced_date | DATE | |

#### catalysts
| Column | Type | Description |
|--------|------|-------------|
| catalyst_id | UUID PK | |
| drug_id | TEXT FK | |
| title | TEXT | Event description |
| catalyst_type | TEXT | trial_readout / regulatory / corporate / partnership |
| expected_date | DATE | When event is expected |
| outcome | TEXT | Actual result (filled post-event) |
| results_url | TEXT | Link to published results |
| expected_impact | TEXT | Significance to competitive landscape |
| is_key_watch | BOOLEAN | Priority monitoring flag |
| related_trial_id | TEXT FK | Link to trials table |
| confidence_source | TEXT | estimated / announced / confirmed |
| source_url | TEXT | |

#### company_profiles
| Column | Type | Description |
|--------|------|-------------|
| company_id | TEXT FK PK | |
| competitive_position | TEXT | Overall strategic assessment |
| vs_ailux | TEXT | Specific vs-Ailux analysis |
| key_differentiators | JSONB | Differentiating factors |
| strategic_behavior | TEXT | Observed M&A / partnership patterns |
| market_cap_usd_m | FLOAT | Market cap in $M |
| cash_runway | TEXT | Financing runway |
| financing_history | JSONB | Prior rounds |
| key_investors | JSONB | Notable investors |
| hq_country | TEXT | |
| website | TEXT | |
| enriched_at / last_enriched_at | TIMESTAMPTZ | Last enrichment time |

#### deals
| Column | Type | Description |
|--------|------|-------------|
| deal_id | UUID PK | |
| entity_id | TEXT | Parent entity |
| drug_id | TEXT | Optional drug-level association |
| company_id | TEXT FK | |
| deal_type | TEXT | licensing / acquisition / partnership / financing |
| parties | JSONB | Companies involved |
| announced_date | DATE | |
| economics_royalties | TEXT | Financial terms |
| strategic_signal | TEXT | Strategic interpretation |
| ailux_relevance | TEXT | Implications for Ailux |
| geography_rights | TEXT | |

#### research_queue
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| entity_id | TEXT | Grouped by entity |
| entity_name | TEXT | Display name |
| company_id | TEXT | Parent company |
| area_id | TEXT | Disease area |
| priority_score | INT | 0–200 urgency |
| reason | TEXT | Human-readable score explanation |
| next_best_action | TEXT | Recommended next step |
| missing_stage | TEXT | First missing stage |
| missing_fields | JSONB | Missing field names |
| strategic_importance | TEXT | high / medium / low |
| completeness_score | INT | 0–100 snapshot |
| completeness_tier | TEXT | thin / partial / strong |
| trigger_events | JSONB | Active trigger type strings |
| last_updated | TIMESTAMPTZ | |
| assigned_status | TEXT | pending / in_progress / done / skipped |
| created_at | TIMESTAMPTZ | |
| UNIQUE | (entity_id, area_id) | One row per entity per area |

---

## THE INTELLIGENCE LAYER

### Module: `scripts/research_intelligence.py`

This module implements Stage 7 — the continuous intelligence loop.

#### Function 1: `load_entity_context(entity_id, area_id, sb_url, sb_key) → dict`

Loads all Supabase data for one entity via 5 PostgREST queries:
1. `drugs` WHERE entity_id = X AND area_id = Y
2. `trials` WHERE drug_id IN (drug_ids)
3. `catalysts` WHERE drug_id IN (drug_ids)
4. `companies` WHERE company_id = (drugs[0].company_id)
5. `company_profiles` WHERE company_id = (drugs[0].company_id)
6. `deals` WHERE entity_id = X

Returns: `{entity_id, area_id, drugs[], trials[], catalysts[], company, profile, deals[]}`

---

#### Function 2: `score_entity_completeness(ctx) → dict`

Computes a 0–100 completeness score across 6 weighted research stages.

**Stage weights (must sum to 100):**
```
Stage 1 — Entity Discovery:       10 pts
Stage 2 — Drug Mapping:           15 pts
Stage 3 — Trial Intelligence:     20 pts
Stage 4 — Catalyst Engine:        15 pts
Stage 5 — Strategic Positioning:  25 pts
Stage 6 — Deal Intelligence:      15 pts
```

**Per-stage scoring (each stage scores 0.0–1.0, multiplied by weight):**

Stage 1: 3 checks — entity_id set (⅓), drugs list non-empty (⅓), company_id present (⅓)

Stage 2: Per drug — mechanism (¼), target (¼), stage (¼), differentiation_thesis (¼). Averaged across all drugs.

Stage 3: Per drug — has_trials (⅓), trial has arms or primary_endpoint (⅓), any trial confidence_score ≥ 80 (⅓). Averaged across drugs. -0.5 penalty if trial_data_status == 'missing'.

Stage 4: has catalysts (0.5) + catalyst has expected_date AND title (0.5).

Stage 5: profile_exists (0.2) + competitive_position (0.2) + vs_ailux (0.4, double weighted) + key_differentiators (0.2). Capped at 1.0.

Stage 6: has deals (0.6) + deal has economics_royalties OR strategic_signal (0.4).

**Completeness tiers:**
- `thin` → score < 40
- `partial` → 40 ≤ score < 70
- `strong` → score ≥ 70

**Returns:**
```python
{
  "completeness_score": int,          # 0–100
  "completeness_tier": str,           # "thin" | "partial" | "strong"
  "stage_scores": {                   # 0–100 per stage
    "stage1_entity_discovery": int,
    "stage2_drug_mapping": int,
    "stage3_trial_intelligence": int,
    "stage4_catalyst_engine": int,
    "stage5_strategic_position": int,
    "stage6_deal_intelligence": int,
  },
  "missing_fields": [str, ...],       # deduplicated field names
  "missing_stages": [str, ...],       # stages with score < 50%
  "populated_fields": [str, ...],     # confirmed non-empty fields
  "last_scored_at": str,              # ISO 8601 timestamp
}
```

---

#### Function 3: `get_next_best_action(ctx, score_result) → str`

Returns a single plain-English recommended next action. **First-match priority order:**

| Priority | Condition | Action |
|----------|-----------|--------|
| 1 | No drugs | "Map drugs/programs for this entity" |
| 2 | Any drug missing mechanism or target | "Run drug mapping to fill mechanism + target fields" |
| 3 | Any drug with no associated trials | "Run CT.gov search to find clinical trials for unmapped drugs" |
| 4 | Trial has primary_completion_date but no catalyst | "Generate catalyst from trial primary completion date" |
| 5 | Catalyst expected_date < today, no outcome/results_url | "Search for results — catalyst '{title}' date has passed" |
| 6 | vs_ailux empty on both profile and drugs | "Run strategic enrichment to fill vs. Ailux competitive assessment" |
| 7 | No deals for this entity | "Search deal history for {company_name} — no partnerships or licensing found" |
| 8 | profile enriched_at > 30 days ago | "Re-run company enrichment — profile is {N} days old" |
| 9 | completeness_score ≥ 70 | "Entity well-researched — verify data quality and freshness" |
| 10 | Default | "Continue enrichment — gaps in {missing_stages[:2]}" |

---

#### Function 4: `check_research_triggers(ctx) → list[str]`

Returns all active trigger type strings. Multiple triggers can fire simultaneously.

**Trigger definitions:**

| Trigger | Condition | Why it matters |
|---------|-----------|----------------|
| `trial_phase_ahead_of_drug_stage` | Trial phase rank > drug stage rank | Drug stage field is stale; should be updated to match trial progress |
| `trial_pcd_without_catalyst` | Trial has primary_completion_date, drug has no catalysts | Missing forward-looking catalyst — readout will occur untracked |
| `completed_trial_without_results` | Trial overall_status contains "complet" AND drug results_summary is empty | Results may be published; should be retrieved |
| `catalyst_date_passed_unresolved` | Catalyst expected_date < today AND no outcome AND no results_url | Past event not captured; need to search for what happened |
| `profile_stale` | enriched_at > 30 days ago OR profile exists with no enriched_at | Profile data may be outdated |
| `new_deal_since_enrichment` | Any deal.created_at > profile.enriched_at | New deal activity not incorporated into competitive profile |
| `strategic_entity_missing_vs_ailux` | cls contains "direct" or "1st gen" AND vs_ailux empty | High-priority competitor lacks key competitive analysis |

**Phase rank mapping (for T1 comparison):**
```
Trial:  Phase 1 → 2, Phase 1/Phase 2 → 3, Phase 2 → 4, Phase 2/3 → 5, Phase 3 → 6, Phase 4 → 7
Drug:   preclinical → 1, phase 1 → 2, phase 1/2 → 3, phase 2 → 4, phase 2/3 → 5, phase 3 → 6, approved → 7
```

---

#### Function 5: `calculate_priority_score(ctx, score_result, triggers) → (int, str)`

Returns `(priority_score: int 0–200, reason: str)`.

**Formula:**
```
base = 100 - completeness_score

Adjustments:
  +30  if cls contains "direct" or "1st gen" (strategic entity)
  +20  if any triggers are active
  +10  per additional trigger beyond the first, capped at +40 total
  +15  if completeness_tier == "thin"
  +10  if "profile_stale" in triggers
  +10  if "catalyst_date_passed_unresolved" in triggers
  -10  if completeness_tier == "strong" AND no triggers

Final = clamp(0, result, 200)
```

---

#### Function 6: `upsert_research_queue(ctx, score_result, triggers, next_action, priority_score, reason, dry_run, sb_url, sb_key)`

Writes to two tables:
1. `research_queue` — upsert on `(entity_id, area_id)` with full score snapshot
2. `drugs` — PATCH all drug rows with completeness fields

**Strategic importance mapping from cls field:**
- `"direct"` or `"1st gen"` in cls → `"high"`
- `"adjacent"` or `"2nd gen"` in cls → `"medium"`
- Anything else → `"low"`

---

#### Function 7: `run_intelligence_audit(area_id, entity_filter, dry_run)`

Main entry point. Discovers all entities for an area from the `drugs` table, runs the full 5-step pipeline for each, prints a summary table.

**CLI usage:**
```bash
python scripts/research_intelligence.py --area tl1a
python scripts/research_intelligence.py --area tl1a --entity sanofi
python scripts/research_intelligence.py --area all --dry-run
```

---

## CLASS×RELEVANCE FRAMEWORK

The `cls` field on the `companies` table classifies competitive entities along two axes:

**Class (maturity of approach):**
- `1st Gen` — first-generation mechanism (established, well-validated)
- `2nd Gen` — second-generation / improved mechanism
- `Next Gen` — next-generation / differentiated mechanism

**Relevance (overlap with Ailux):**
- `Direct` — same target, same indication
- `Adjacent` — same target, different indication OR different target, same indication
- `Same-Space` — same disease area, different mechanism
- `Watch` — early/speculative overlap

**Examples:**
- `"1st Gen Direct"` → highest priority; direct competitor
- `"Next Gen Adjacent"` → worth watching but not immediate threat
- `"2nd Gen Same-Space"` → relevant context but not direct competition

---

## PIPELINE ARCHITECTURE

### Execution Order (nightly + manual)

```
GitHub Actions: Intelligence Pipeline
  │
  ├── Step 3:  ct_gov_sync.py --area {area}
  │            Syncs all trials from ClinicalTrials.gov
  │            Stages 3a (direct fetch), 3b (discovery), 3c (drug stage update)
  │
  ├── Steps 1,4,5,6:  company_enrichment.py --area {area}
  │            Step 1: Entity discovery (new companies/drugs)
  │            Step 4: Catalyst generation from trial PCDs
  │            Step 5: Company enrichment (profile, vs_ailux, deals)
  │            Step 6: Deal intelligence
  │
  └── Step 7:  research_intelligence.py --area {area}
               Completeness scoring
               Trigger detection
               Research queue update
               (Not yet wired into workflow — pending)
```

### Workflow File
`.github/workflows/company-enrichment.yml` (named "Intelligence Pipeline")

Triggers: Schedule (Mon–Sat midnight ET) and `workflow_dispatch` with inputs:
- `area`: tl1a | tslp | il4ra | fcrn | igf1r | tcell | all
- `company`: optional entity filter
- `dry_run`: boolean
- `skip_trial_sync`: boolean

---

## GAP ANALYSIS

### P0 — Missing, Highest Impact

| Gap | Impact | Resolution |
|-----|--------|------------|
| Stage 2 has no dedicated pipeline step | Drug `mechanism`, `target`, `differentiation_thesis` often unpopulated | Add `step2_map_drugs()` to company_enrichment.py |
| `vs_ailux` only at company level | Cannot assess competitive threat at drug level | Populate `drugs.vs_competitor` systematically in Stage 5 |
| research_intelligence.py not in workflow | Intelligence audit never runs automatically | Add to GitHub Actions YAML after company_enrichment.py |
| schema_migration_v4.sql not yet applied | completeness_score, research_queue table don't exist | Apply to Supabase via SQL editor |

### P1 — Important, Medium Effort

| Gap | Impact | Resolution |
|-----|--------|------------|
| No trigger-based re-enrichment | Triggers detected but not acted upon | Add `run_triggered_enrichment()` that calls company_enrichment.py for entities with active triggers |
| No drug-level `cls` field | All competitive classification is at company level; individual drugs can't be classified | Add `cls` to drugs table; populate in Stage 2 |
| Stage 6 deals not systematically searched | Deals table sparsely populated | Add structured deal discovery step in company_enrichment.py |
| `completeness_score` not displayed in UI | Platform cannot show users what's well-researched vs. thin | Add completeness badges to company_area_detail view and front-end |

### P2 — Future Enhancements

| Enhancement | Notes |
|-------------|-------|
| Inter-entity comparison view | Show all entities ranked by priority_score for one area |
| Trigger resolution tracking | Mark triggers as "resolved" when downstream action is taken |
| Confidence decay over time | Reduce confidence_score of stale records automatically |
| Source citation tracking | `source_url` populated on all records; visible in UI |
| Ailux pipeline record | Add Ailux's own drugs to the system to make vs_ailux a structured comparison |

---

## DESIGN PRINCIPLES

1. **Stages feed stages.** No stage should write to a table that an earlier stage reads without a clear versioning/trigger mechanism. Data flows in one direction through the pipeline.

2. **Every field has an owner.** Each field in the schema is populated by a specific pipeline step. Orphaned fields (no owning step) are gaps that must be assigned.

3. **Completeness is computable.** The system knows what it knows. `completeness_score` is derived entirely from observable field state — it does not rely on subjective human input.

4. **The queue drives work.** The `research_queue` table is the authoritative list of what to research next. Manual research decisions should consult or update this table.

5. **Dry-run everywhere.** Every pipeline script supports `--dry-run`. No writes to Supabase should occur without the ability to simulate and inspect the output first.

---

## QUESTIONS FOR EVALUATION

When feeding this document into an AI model for critique, suggested evaluation prompts:

1. **Completeness scoring logic:** "Review the Stage 5 scoring. vs_ailux has double weight (0.4 of 1.0). Is this weighting appropriate given that vs_ailux is often the last field populated in a research workflow?"

2. **Trigger coverage:** "Are there important research trigger conditions that are missing from the 7 defined triggers? What would a senior biotech analyst monitor that isn't captured here?"

3. **Next best action coverage:** "Is the 10-priority decision tree in get_next_best_action() complete? What edge cases would cause it to return an unhelpful action?"

4. **Stage ordering:** "Should Stage 6 (Deal Intelligence) come before Stage 5 (Strategic Positioning)? Deals often inform strategic positioning, suggesting a dependency."

5. **Entity model:** "The entity_id groups drugs under one competitive program. Is this the right grouping level, or should some entities be split (e.g., early vs. late phase programs from the same company)?"

6. **Priority score formula:** "The priority_score formula gives +30 for strategic entities and starts from (100 - completeness_score). Does this mean a 'thin' strategic entity (score=20) gets priority 80+30+20+15 = 145, while a 'thin' non-strategic entity gets 80+20+15 = 115? Is that spread sufficient to differentiate?"

7. **Stale data definition:** "30 days as the profile staleness threshold — is this appropriate for a nightly pipeline? Should it be 14 days?"

---

*End of ARCHITECTURE_v2.md*
