# BD Platform — Architecture v3
### Intelligence-First Competitive Research System
*Version: 3.0 — 2026-05-19*
*Prepared for: External AI model review (DeepSeek, ChatGPT, etc.)*

---

## HOW TO USE THIS DOCUMENT

This document describes the complete architecture of a biotech competitive intelligence platform. It is written to enable a reviewing model to:

1. **Evaluate architectural soundness** — Is the 7-stage research graph the right model for biotech BD intelligence?
2. **Critique scoring logic** — Are the completeness weights and tier thresholds calibrated correctly?
3. **Challenge assumptions** — What does this system assume about how biotech BD research works that may not hold?
4. **Identify blind spots** — What data, signals, or research stages are missing?
5. **Propose concrete improvements** — Specific changes to schema, scoring, triggers, or pipeline logic
6. **Evaluate decision trees** — Is the next-best-action priority order correct?

Specific review questions are at the end of each major section and consolidated at the bottom.

---

## 1. SYSTEM CONTEXT

### What Is This

An internal competitive intelligence platform for **Ailux Therapeutics**, a clinical-stage biotech in the TL1A/inflammatory disease space. The platform tracks competitor drugs, clinical trials, catalysts (binary readout events), deals, and company positioning across 6 disease areas.

**The fundamental problem this solves:** A BD analyst manually researches 40+ competitive entities across 6 disease areas. Without tooling, research is uneven — some entities are deeply documented, others barely touched. There's no systematic way to know what's well-researched vs. what has critical gaps, and no automatic detection when a competitor's situation changes in a way that requires updating Ailux's strategy.

**The core mission:** Make the platform self-aware — so it knows what it knows, what it's missing, and what changed.

### Technology Stack

- **Database:** Supabase (PostgreSQL via PostgREST REST API)
- **Pipeline scripts:** Python 3.11 (GitHub Actions, nightly + manual trigger)
- **AI enrichment:** Anthropic Claude Sonnet (`claude-sonnet-4-6`) via API
- **Trial data source:** ClinicalTrials.gov API v2 (`https://clinicaltrials.gov/api/v2/studies/{nctId}`)
- **Frontend:** Vanilla JS + Supabase JS client (static GitHub Pages site)
- **CI/CD:** GitHub Actions (`.github/workflows/company-enrichment.yml`)

### Disease Areas Tracked
| area_id | Target | Primary indication |
|---------|--------|--------------------|
| `tl1a` | TL1A pathway | IBD (Crohn's, UC) |
| `tslp` | TSLP | Atopic dermatitis, asthma |
| `il4ra` | IL-4Rα | Atopic dermatitis |
| `fcrn` | FcRn | Autoimmune (IgG-mediated) |
| `igf1r` | IGF1R | Oncology |
| `tcell` | T-cell biology | Oncology / autoimmune |

---

## 2. THE RESEARCH GRAPH — 7 STAGES

The platform models competitive intelligence as a **directed 7-stage research graph**. Each stage produces structured outputs that feed the next stage. The system now tracks completeness at each stage and knows what's missing.

```
Stage 1 ──► Stage 2 ──► Stage 3 ──► Stage 4
Entity       Drug         Trial        Catalyst
Discovery    Mapping      Intelligence Engine
                                         │
                         ┌───────────────┘
                         ▼
                     Stage 5 ──► Stage 6 ──► Stage 7
                     Strategic   Deal         Continuous
                     Positioning Intelligence Audit Loop
```

### Stage 1 — Entity Discovery
**Goal:** Identify all competitive entities in each disease area.

**Inputs:** Manual seeding, Claude-assisted web search, ClinicalTrials.gov sponsor discovery

**Key outputs (Supabase):**
- `companies`: `company_id` (slug), `company_name`, `area_id`, `cls` (CLASS×RELEVANCE classification)
- `drugs`: `drug_id`, `drug_name`, `company_id`, `area_id`, `entity_id`
- `entity_id` — the top-level grouping key. One entity = one competitive program (may span multiple drugs)
- `discovery_status` on drugs: `manual | auto | unverified | verified`

**Completion criteria for Stage 2:** `entity_id` set, `drugs` list non-empty, at least one drug has `company_id`

---

### Stage 2 — Drug Mapping
**Goal:** For each drug, document mechanism, target, stage, and differentiation vs. Ailux.

**Key outputs (Supabase — drugs table):**
| Field | Type | Description |
|-------|------|-------------|
| `mechanism` | TEXT | Mode of action (e.g., "anti-TL1A mAb") |
| `target` | TEXT | Molecular target |
| `stage` | TEXT | preclinical / phase 1 / phase 1/2 / phase 2 / phase 2/3 / phase 3 / approved |
| `differentiation_thesis` | TEXT | How this drug differs from others in class |
| `aliases` | JSONB | Alternative names |
| `confidence_score` | INT 0–100 | Data quality |

**⚠️ Current gap:** Stage 2 has no dedicated pipeline step. Drug mapping relies on general Claude enrichment in `company_enrichment.py` Step 5, which doesn't systematically fill all 4 core fields.

---

### Stage 3 — Trial Intelligence
**Goal:** Sync all clinical trial data from ClinicalTrials.gov.

**Pipeline script:** `ct_gov_sync.py`
- **3a:** Direct fetch for known NCT IDs from `NCT_SEED_MAP` dict
- **3b:** Search-based discovery for new trials not yet seeded
- **3c:** Drug stage update — if trial phase > current drug stage, update drug

**Key outputs (Supabase — trials table):**
| Field | Type | Description |
|-------|------|-------------|
| `nct_id` | TEXT PK | NCT identifier |
| `drug_id` | TEXT FK | Parent drug |
| `phase` | TEXT | Trial phase |
| `overall_status` | TEXT | ClinicalTrials.gov status |
| `primary_endpoint` | TEXT | Primary endpoint |
| `arms` | JSONB | Trial arms |
| `primary_completion_date` | DATE | Key date for catalyst generation |
| `discovery_status` | TEXT | `manual | auto | unverified | verified` |
| `confidence_score` | INT | 0–100 |

**Completion criteria for Stage 4:** At least one trial per drug, trial has `arms` and `primary_endpoint`, `confidence_score ≥ 80`

---

### Stage 4 — Catalyst Engine
**Goal:** Generate forward-looking catalysts from trial timelines.

**Pipeline logic:** For each drug with trials but no existing catalyst, Claude generates one catalyst per trial using the `primary_completion_date` as the trigger.

**Key outputs (Supabase — catalysts table):**
| Field | Type | Description |
|-------|------|-------------|
| `title` | TEXT | Event description |
| `catalyst_type` | TEXT | `trial_readout | regulatory | corporate | partnership` |
| `expected_date` | DATE | When readout expected |
| `outcome` | TEXT | Actual result (post-event) |
| `results_url` | TEXT | Link to published data |
| `expected_impact` | TEXT | Significance to Ailux strategy |
| `is_key_watch` | BOOLEAN | Priority monitoring flag |
| `confidence_source` | TEXT | `estimated | announced | confirmed` |

---

### Stage 5 — Strategic Positioning
**Goal:** Assess each entity's strategic position relative to Ailux.

**Key outputs (Supabase — company_profiles table):**
| Field | Type | Description |
|-------|------|-------------|
| `competitive_position` | TEXT | Overall assessment |
| `vs_ailux` | TEXT | Specific Ailux comparison |
| `key_differentiators` | JSONB | Differentiating factors |
| `strategic_behavior` | TEXT | Observed M&A / partnership patterns |
| `market_cap_usd_m` | FLOAT | |
| `enriched_at` | TIMESTAMPTZ | Last enrichment time |

**⚠️ Current gap:** `vs_ailux` only exists at company level (`company_profiles`). Drug-level competitive comparison (`drugs.vs_competitor`) is structurally present but rarely populated.

---

### Stage 6 — Deal Intelligence
**Goal:** Track all partnerships, licensing, M&A, financing.

**Key outputs (Supabase — deals table):**
| Field | Type | Description |
|-------|------|-------------|
| `deal_type` | TEXT | `licensing | acquisition | partnership | financing | co-development` |
| `parties` | JSONB | Companies involved |
| `economics_royalties` | TEXT | Financial terms |
| `strategic_signal` | TEXT | What deal signals about strategy |
| `ailux_relevance` | TEXT | Implications for Ailux |
| `entity_id` | TEXT | Links deal to competitive entity |

---

### Stage 7 — Continuous Audit Loop *(newly implemented)*
**Goal:** After every pipeline run, score all entities, detect triggers, and update the research priority queue.

**Pipeline script:** `research_intelligence.py` (runs last in every pipeline execution)

This is the core of the intelligence layer. See Section 4 for full detail.

---

## 3. PIPELINE EXECUTION ARCHITECTURE

### Execution Order (per area, every pipeline run)

```
GitHub Actions: Intelligence Pipeline
  │
  ├── 1. ct_gov_sync.py --area {area}
  │      Stages 3a, 3b, 3c
  │      No Anthropic API needed
  │
  ├── 2. company_enrichment.py --area {area}
  │      Steps 1 (entity discovery), 4 (catalyst gen),
  │      5 (company enrichment), 6 (deal intelligence)
  │      Uses Claude Sonnet via Anthropic API
  │
  └── 3. research_intelligence.py --area {area}
         Full completeness audit
         No Anthropic API needed — pure logic
```

### Schedule
- **Nightly (Mon–Sat, 4:00 UTC):** TL1A area only (most active)
- **Manual dispatch:** Any single area or all 6 areas with `area=all`
- **Manual inputs:** `area`, `company` (filter), `dry_run` (boolean), `skip_trial_sync` (boolean)

### Credential Architecture
- `ANTHROPIC_API_KEY` — only needed by `company_enrichment.py`
- `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` — all three scripts
- Files read at runtime: `.supabase_service_key`, `.github_token` (not committed to git)

---

## 4. THE INTELLIGENCE LAYER (Stage 7)

### Module: `scripts/research_intelligence.py`

This module implements the self-awareness layer. It answers four questions for every entity, every run:

| Question | Function |
|----------|----------|
| What do we know? | `score_entity_completeness()` |
| What is missing? | `missing_fields` / `missing_stages` in score result |
| What changed? | `check_research_triggers()` |
| What should happen next? | `get_next_best_action()` |
| Why does this matter for Ailux? | `priority_score` + `strategic_importance` |

---

### Function 1: `load_entity_context(entity_id, area_id, sb_url, sb_key) → dict`

Loads all data for one entity via 6 Supabase REST queries:
1. `drugs` WHERE entity_id = X AND area_id = Y
2. `trials` WHERE drug_id IN (drug_ids from step 1)
3. `catalysts` WHERE drug_id IN (drug_ids)
4. `companies` WHERE company_id = (from drugs[0])
5. `company_profiles` WHERE company_id = (from drugs[0])
6. `deals` WHERE entity_id = X

Returns: `{entity_id, area_id, drugs[], trials[], catalysts[], company, profile, deals[]}`

---

### Function 2: `score_entity_completeness(ctx) → dict`

**Stage weights (sum = 100):**
```
Stage 1 — Entity Discovery:       10 pts
Stage 2 — Drug Mapping:           15 pts
Stage 3 — Trial Intelligence:     20 pts
Stage 4 — Catalyst Engine:        15 pts
Stage 5 — Strategic Positioning:  25 pts  ← highest (vs_ailux double-weighted)
Stage 6 — Deal Intelligence:      15 pts
```

**Per-stage scoring (0.0–1.0, multiplied by weight):**

**Stage 1** (3 checks, equal weight):
- entity_id set ✓/✗
- drugs list non-empty ✓/✗
- at least one drug has company_id ✓/✗

**Stage 2** (per drug, 4 checks, equal weight — averaged across all drugs):
- mechanism populated ✓/✗
- target populated ✓/✗
- stage populated ✓/✗
- differentiation_thesis populated ✓/✗

**Stage 3** (per drug — averaged across all drugs):
- has_trials: 1/3 credit
- any trial has arms OR primary_endpoint: 1/3 credit
- any trial has confidence_score ≥ 80: 1/3 credit
- **Penalty:** −0.5 if trial_data_status == 'missing'

**Stage 4:**
- has any catalysts: 0.5 credit
- any catalyst has expected_date AND title: +0.5 credit

**Stage 5** (5 checks, capped at 1.0):
- profile exists: 0.2
- competitive_position populated: 0.2
- vs_ailux on profile OR vs_competitor on any drug: **0.4** (double weight)
- key_differentiators populated: 0.2

**Stage 6:**
- has any deals: 0.6 credit
- any deal has economics_royalties OR strategic_signal: +0.4 credit

**Final score:** `Σ(stage_score × stage_weight)`, rounded to nearest integer

**Completeness tiers:**
```
thin    → score < 40
partial → 40 ≤ score < 70
strong  → score ≥ 70
```

**Returns:**
```python
{
  "completeness_score":  int,         # 0–100
  "completeness_tier":   str,         # "thin" | "partial" | "strong"
  "stage_scores":        dict,        # {stage_name: 0–100}
  "missing_fields":      list[str],   # deduplicated field names
  "missing_stages":      list[str],   # stages with score < 50%
  "populated_fields":    list[str],
  "last_scored_at":      str,         # ISO 8601
}
```

---

### Function 3: `get_next_best_action(ctx, score_result) → str`

Returns **one** plain-English action. First-match priority:

| Priority | Condition | Action returned |
|----------|-----------|-----------------|
| 1 | No drugs | "Map drugs/programs for this entity" |
| 2 | Any drug missing mechanism or target | "Run drug mapping to fill mechanism + target fields" |
| 3 | Any drug with no associated trials | "Run CT.gov search to find clinical trials for unmapped drugs" |
| 4 | Trial has primary_completion_date but drug has no catalysts | "Generate catalyst from trial primary completion date" |
| 5 | Any catalyst expected_date < today, no outcome/results_url | "Search for results — catalyst '{title}' date has passed" |
| 6 | vs_ailux empty on profile AND vs_competitor empty on all drugs | "Run strategic enrichment to fill vs. Ailux competitive assessment" |
| 7 | No deals for this entity | "Search deal history for {company_name}" |
| 8 | profile.enriched_at > 30 days ago | "Re-run company enrichment — profile is {N} days old" |
| 9 | completeness_score ≥ 70 | "Entity well-researched — verify data quality and freshness" |
| 10 | Default | "Continue enrichment — gaps in {missing_stages[:2]}" |

---

### Function 4: `check_research_triggers(ctx) → list[str]`

Returns all active trigger types (can be multiple simultaneously):

| Trigger key | Condition | Downstream action needed |
|-------------|-----------|--------------------------|
| `trial_phase_ahead_of_drug_stage` | trial.phase rank > drug.stage rank | Update drug stage |
| `trial_pcd_without_catalyst` | trial has primary_completion_date, no catalyst exists | Generate catalyst |
| `completed_trial_without_results` | trial.status contains "complet", drug.results_summary empty | Search for results |
| `catalyst_date_passed_unresolved` | catalyst.expected_date < today, no outcome/results_url | Search what happened |
| `profile_stale` | enriched_at > 30 days ago OR profile exists with no enriched_at | Re-enrich company profile |
| `new_deal_since_enrichment` | any deal.created_at > profile.enriched_at | Update competitive profile |
| `strategic_entity_missing_vs_ailux` | cls contains "direct" or "1st gen" AND vs_ailux empty | Run strategic enrichment |

**Phase/stage rank mapping used for T1:**
```
Trial:  Phase 1→2, Phase 1/Phase 2→3, Phase 2→4, Phase 2/3→5, Phase 3→6, Phase 4→7
Drug:   preclinical→1, phase 1→2, phase 1/2→3, phase 2→4, phase 2/3→5, phase 3→6, approved→7
```

---

### Function 5: `calculate_priority_score(ctx, score_result, triggers) → (int, str)`

```
base = 100 − completeness_score

Adjustments:
  +30  cls contains "direct" or "1st gen"  (strategic entity)
  +20  any triggers active
  +10  per additional trigger beyond first, capped at +40
  +15  completeness_tier == "thin"
  +10  "profile_stale" in triggers
  +10  "catalyst_date_passed_unresolved" in triggers
  −10  completeness_tier == "strong" AND no triggers

Final = clamp(0, base, 200)
```

---

### Function 6: `upsert_research_queue(...)`

Writes to two tables:
1. `research_queue` — upsert on `UNIQUE(entity_id, area_id)` with full snapshot
2. `drugs` — PATCH all drug rows with completeness fields

**Strategic importance mapping from `cls` field:**
- "direct" or "1st gen" in cls → `"high"`
- "adjacent" or "2nd gen" → `"medium"`
- Anything else → `"low"`

---

## 5. DATA MODEL — KEY TABLES

### drugs (extended)
```
drug_id              TEXT PK
drug_name            TEXT
company_id           TEXT FK
area_id              TEXT
entity_id            TEXT          ← groups programs into one competitive entity
stage                TEXT          ← preclinical / phase 1 / ... / approved
mechanism            TEXT
target               TEXT
aliases              JSONB
differentiation_thesis TEXT
vs_competitor        TEXT          ← drug-level vs-Ailux (often empty — P0 gap)
results_summary      TEXT
discovery_status     TEXT          ← manual | auto | unverified | verified
confidence_score     INT           ← 0–100
trial_data_status    TEXT          ← populated | missing | searching | pending | unknown
last_synced_date     DATE

-- Intelligence layer fields (added schema_migration_v4):
completeness_score   INT           ← 0–100
completeness_tier    TEXT          ← thin | partial | strong
missing_fields       JSONB         ← list of field names
missing_stages       JSONB         ← list of stage names
next_best_action     TEXT          ← recommended next research step
last_scored_at       TIMESTAMPTZ
priority_score       INT           ← 0–200 urgency
trigger_flags        JSONB         ← active trigger type strings
```

### research_queue
```
id                   UUID PK
entity_id            TEXT NOT NULL
entity_name          TEXT
company_id           TEXT
area_id              TEXT
priority_score       INT DEFAULT 0    ← 0–200
reason               TEXT             ← human-readable score explanation
next_best_action     TEXT
missing_stage        TEXT             ← first missing stage
missing_fields       JSONB
strategic_importance TEXT             ← high | medium | low
completeness_score   INT              ← snapshot at queue time
completeness_tier    TEXT
trigger_events       JSONB            ← list of trigger type strings
last_updated         TIMESTAMPTZ DEFAULT NOW()
assigned_status      TEXT DEFAULT 'pending'  ← pending | in_progress | done | skipped
created_at           TIMESTAMPTZ DEFAULT NOW()
UNIQUE (entity_id, area_id)
```

---

## 6. CLASS × RELEVANCE FRAMEWORK

The `cls` field on `companies` classifies competitive entities on two axes:

**Class (mechanism maturity):**
- `1st Gen` — established/validated mechanism
- `2nd Gen` — improved/next-generation mechanism
- `Next Gen` — differentiated / novel mechanism

**Relevance (overlap with Ailux):**
- `Direct` — same target, same indication
- `Adjacent` — same target, different indication OR different target, same indication
- `Same-Space` — same disease area, different mechanism
- `Watch` — early/speculative overlap

**Priority interpretation:** "1st Gen Direct" is highest-priority competitor; "Next Gen Watch" is lowest-priority.

The intelligence layer uses this field to:
1. Set `strategic_importance` on research_queue rows
2. Add +30 to priority_score for "direct" or "1st gen" entities
3. Trigger `strategic_entity_missing_vs_ailux` when a strategic entity lacks vs_ailux analysis

---

## 7. CURRENT IMPLEMENTATION STATUS

### Fully Implemented ✅
- All 6 database tables with complete schema (migrations v1–v4 applied)
- `ct_gov_sync.py` — Stage 3 full sync including discovery and stage updates
- `company_enrichment.py` — Stages 1, 4, 5, 6 with Claude enrichment
- `research_intelligence.py` — Full Stage 7 with all 6 functions + CLI
- GitHub Actions pipeline with nightly + manual dispatch for all 6 areas
- `ARCHITECTURE_v2.md` and this document for external review

### Partially Implemented ⚠️
- **Stage 2 drug mapping** — fields exist in schema, Claude enrichment populates them via Step 5 of `company_enrichment.py`, but not systematically across all 4 required fields. No dedicated `step2_map_drugs()` function.
- **`drugs.vs_competitor`** — field exists but almost never populated. `vs_ailux` only lives at `company_profiles` level.
- **Trigger-based re-enrichment** — triggers are detected and written to `research_queue`, but nothing automatically re-runs enrichment in response to a trigger.

### Not Yet Built ❌
- Dashboard display of `completeness_score` or `research_queue` — no frontend visualization yet
- Ailux's own pipeline as a record — no Ailux drug entries exist for comparison
- Drug-level `cls` field — classification is company-level only
- Stage 2 dedicated pipeline step
- Trigger resolution tracking (marking triggers "resolved" when addressed)

---

## 8. DESIGN PRINCIPLES

1. **Stages feed stages.** Data flows forward through the pipeline. No stage reads from a table that a later stage exclusively owns.

2. **Every field has an owner.** Each field is populated by a specific pipeline step. Orphaned fields (no owning step) are explicit gaps — not acceptable long-term.

3. **Completeness is computable.** The system knows what it knows. `completeness_score` is derived entirely from observable field state — no subjective human input required.

4. **The queue drives work.** `research_queue` is the authoritative list of what to research next. Priority is deterministic from the scoring formula.

5. **Dry-run everywhere.** Every script supports `--dry-run`. No Supabase writes without the ability to simulate first.

6. **Static data is always the fallback.** When Supabase returns no trials for a drug, the static `TL1A_PROGRAMS` data is used. Once the pipeline populates Supabase, live data takes over automatically.

---

## 9. REVIEW QUESTIONS FOR EXTERNAL MODELS

These are the most important open questions. A reviewing model should evaluate each one and propose specific changes.

### A. Scoring Logic

**A1.** Stage 5 (Strategic Positioning) carries the highest weight at 25 points. `vs_ailux` has double weight within that stage (0.4 of 1.0). Is this appropriate given that `vs_ailux` is typically the last field populated — meaning entities will remain `thin` or `partial` for a long time even when the underlying clinical and trial data is strong?

**A2.** Stage 3 (Trial Intelligence) scores a drug as "has trials" even if all trials are completed with no results. Should completed trials without results_summary be scored differently (e.g., partial credit rather than full credit for `has_trials`)?

**A3.** The staleness threshold for `profile_stale` is 30 days. Given that this is a nightly pipeline, should it be 14 days? Or should the threshold vary by entity tier (e.g., 7 days for `thin` entities that are actively being enriched, 30 days for `strong` ones)?

**A4.** Priority score starts from `base = 100 - completeness_score`. This means a newly discovered entity with score=0 starts at 100, then adds adjustments for strategic importance (+30), triggers (+20), and thin tier (+15) — potentially reaching 165 before any context-specific factors. Does this correctly prioritize undiscovered strategic entities over well-known ones that just have a single trigger?

### B. Trigger Coverage

**B1.** The 7 defined triggers cover data-state conditions. What *event-based* triggers are missing — i.e., things that happen in the outside world that should re-trigger enrichment? Examples: competitor files an IND, press release about a Phase 3 start, FDA approval, stock price movement >20%, M&A announcement.

**B2.** `trial_phase_ahead_of_drug_stage` compares phase rank to stage rank. But a trial can have multiple phases (e.g., "Phase 1/Phase 2"). Should the trigger use the *lower* phase (more conservative) or the *upper* phase? Currently it uses a rank mapping that treats "Phase 1/Phase 2" as rank 3, which is higher than "Phase 1" (rank 2) — is this right?

**B3.** There is no trigger for "competitor published a journal article or press release with new clinical data." This is arguably the most important signal in BD intelligence. How should this be incorporated?

### C. Next Best Action Decision Tree

**C1.** The decision tree returns a *single* action. In practice, an entity might have multiple equally urgent gaps. Is returning one action (first match) the right UX, or should it return a ranked list of 2–3 actions?

**C2.** Priority 6 (missing vs_ailux) comes after priority 5 (passed catalyst date). Is this right? A missing strategic assessment might be more urgent for BD purposes than a past catalyst for a non-strategic entity.

**C3.** Priority 8 (stale profile) triggers at 30 days. But if an entity has `strategic_importance = "high"` and no triggers, the system returns "Entity well-researched" (priority 9) before checking staleness. Should strategic entities have a lower staleness threshold?

### D. Data Model

**D1.** `entity_id` groups all drugs for one competitive program. But some companies have both a monotherapy program and a combination program in the same area — are these one entity or two? The current model groups by `entity_id` at the company level, which may conflate distinct competitive programs.

**D2.** `vs_ailux` is a free-text field on `company_profiles`. This means the competitive comparison is unstructured and not queryable. Would a structured comparison table (e.g., `competitive_comparisons` with fields like `mechanism_similarity`, `indication_overlap`, `stage_gap`, `differentiation_score`) be more analytically useful?

**D3.** `deals` has `entity_id` as a foreign key, but many deals are company-wide (not drug-specific). The current structure conflates company-level deals with drug-specific deals. Should there be separate `company_deals` and `drug_deals` tables?

### E. Pipeline Architecture

**E1.** `company_enrichment.py` handles 4 different stages (1, 4, 5, 6) in one script. As the pipeline grows, should each stage have its own script? What are the tradeoffs?

**E2.** `research_intelligence.py` currently only *detects* triggers — it doesn't act on them. Should a trigger automatically re-queue enrichment for the affected entity (e.g., `trial_pcd_without_catalyst` trigger → automatically call Step 4 catalyst generation on next run)? What would the implementation look like?

**E3.** The `NCT_SEED_MAP` in `ct_gov_sync.py` is a hardcoded dict. As the system discovers new trials automatically (Step 3b), they should be added to this map persistently. Where should this state live — in Supabase, in a local file, or in the GitHub repo?

### F. Biotech BD Workflow Assumptions

**F1.** This architecture assumes that competitive intelligence follows a linear 7-stage progression. In practice, BD analysts often work backwards — starting from a deal signal and then investigating the underlying science. Does the architecture accommodate this reverse-lookup pattern?

**F2.** The system focuses heavily on clinical trials as the primary signal for competitive activity. For earlier-stage competitors (preclinical, platform companies), what alternative data sources should stage 3 use when ClinicalTrials.gov has no records?

**F3.** The `completeness_score` treats all companies as equally important to track in depth. In reality, a "Watch" entity needs far less depth than a "1st Gen Direct" competitor. Should completeness thresholds (`thin`, `partial`, `strong`) vary by `cls` classification?

---

## 10. APPENDIX — FILE MAP

```
BD Platform/
├── .github/workflows/company-enrichment.yml    ← CI pipeline (3 scripts in order)
├── scripts/
│   ├── ct_gov_sync.py              ← Stage 3: trial sync (3a direct, 3b discovery, 3c stage update)
│   ├── company_enrichment.py       ← Stages 1, 4, 5, 6: entity discovery, catalysts, enrichment, deals
│   └── research_intelligence.py   ← Stage 7: completeness audit, triggers, priority queue
├── schema_migration_v1.sql         ← Initial schema
├── schema_migration_v2.sql         ← Schema extension v2
├── schema_migration_v3.sql         ← Intelligence architecture (20+ new columns)
├── schema_migration_v4.sql         ← Completeness scoring + research_queue table  ← LATEST
├── ARCHITECTURE.md                 ← Stage definitions (v1)
├── ARCHITECTURE_v2.md              ← Full spec with function signatures (v2)
├── ARCHITECTURE_v3.md              ← This document (v3, for external review)
└── update_log.md                   ← Changelog with commit SHAs
```

---

*End of ARCHITECTURE_v3.md — prepared for external AI model review*
