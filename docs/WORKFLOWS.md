# Meridian BD Platform — Workflow Reference

Every scheduled GitHub Actions workflow, what triggers it, what it calls, and what it writes to.
37 total workflow files. Last updated from source June 2026.

---

## Master Schedule (UTC)

| UTC | ET | Cadence | Workflow | What runs |
|---|---|---|---|---|
| 01:00 Sat | Fri 9PM | Weekly | `weekend-sprint` | Block A (validation) |
| 01:00 Tue–Sat | 9PM Mon–Fri | Weeknights | `weekly-school-week-sprint` | Mon→profiles, Tue→mechanisms, Wed→100Q, Thu→profiles #2, Fri→scoring |
| 02:30 (4×/day) | varies | Daily | `daily-signal-monitor` | Tier 1 signal scan |
| 03:00 Sat | Fri 11PM | Weekly | `weekend-sprint` | Block B1 (enrichment #1) |
| 04:00–04:50 | midnight | Nightly | `daily-company-enrichment` | 6 areas in parallel (staggered 10 min) |
| 05:00 | 1AM | Daily | `daily-pipeline-monitor` | Pipeline health check |
| 06:00 Sun | 2AM Sun | Weekly | `weekly-refresh-company-verified` | Company status verification |
| 06:00 | 2AM | Daily | `chain-01-meridian-research` | RSS fetch → LLM extract |
| 07:00 Sat | 3AM Sat | Weekly | `weekend-sprint` | Block C1 (relationships) |
| 07:00 Sun | 3AM Sun | Weekly | `weekly-patient-briefs` | Patient population briefs |
| 07:00 Sun | 3AM Sun | Weekly | `weekly-validation-research` | Conflict detection + validation |
| 07:30 | 3:30AM | Daily | `chain-07-fetch-homepage-news` | Homepage news scan |
| 08:00 Mon, Thu | 4AM | 2×/week | `chain-02-source-verifier` | Source URL verification (Tier 3) |
| 08:00 Sun | 4AM Sun | Weekly | `weekly-audit-retention` | Prune `field_change_audit` table |
| 08:30 Tue, Fri | 4:30AM | 2×/week | `chain-03-content-verifier` | Page fetch + claim verification (Tier 4) |
| 09:00 Sun | 5AM Sun | Weekly | `weekly-bd-recommender` | BD deal recommendations |
| 09:30 | 5:30AM | Daily | `daily-completeness-scoring` | Research intelligence rescore |
| 09:30 Sun | 5:30AM Sun | Weekly | `weekly-landscape-briefing` | Landscape briefing document |
| 10:00 | 6AM | Daily | `daily-queue-processor` | Enrichment queue processor |
| 10:00 Sun | 6AM Sun | Weekly | `weekly-deal-edges` | Materialize deal edges |
| 10:00 Sun | 6AM Sun | Weekly | `weekly-narrative-generation` | Area competitive narratives |
| 10:30 | 6:30AM | Daily | `chain-05-meridian-write` | Write `meridian_today.html` |
| 10:30 | 6:30AM | Daily | `daily-execute-intel-actions` | Execute approved intel actions |
| 11:00 | 7AM | Daily | `chain-06-morning-summary` | Morning summary report |
| 11:00 | 7AM | Daily | `daily-ranking-snapshots` | Write ranking snapshot rows |
| 11:00 | 7AM | Daily | `daily-run-validation-tests` | Ground truth validation |
| 11:00 | 7AM | Daily | `daily-structural-edges` | Materialize parent/subsidiary edges |
| 11:00 | 7AM | Daily | `daily-verify-edges` | Verify competitive edge rules |
| 11:00 Sat | 7AM Sat | Weekly | `weekend-sprint` | Block D1 (synthesis #1) |
| 11:00 Mon | 7AM Mon | Weekly | `chain-04-compute-landscape-scores` | Landscape score computation |
| 11:00 Mon | 7AM Mon | Weekly | `weekly-trial-audit` | Trial → drug identity audit |
| 12:00 Tue | 8AM Tue | Weekly | `weekly-flywheel-phase2` | Drift detection + fine-tune pairs |
| 14:00 | 10AM | Daily | `daily-stock-prices` | Company stock prices |
| 14:00 Sat | 10AM Sat | Weekly | `weekend-abstract-fetcher` | PubMed + Europe PMC sweep |
| 15:00 Sat | 11AM Sat | Weekly | `weekend-evidence-collectors` | Drug evidence + patient evidence |
| 15:00 Sat | 11AM Sat | Weekly | `weekend-sprint` | Block E1 (QA #1) |
| every 6h | — | Daily | `daily-pipeline-health` | GitHub Actions health check |
| every 6h | — | Daily | `daily-review-submitted-intel` | Review submitted intel items |

---

## Nightly Core Pipeline

### `daily-company-enrichment` — Intelligence Pipeline
**File**: `daily-company-enrichment.yml`

**Triggers**
| Trigger | When |
|---|---|
| ⏰ Cron ×6 | 04:00–04:50 UTC daily — one cron per area, staggered 10 min |
| 👤 Manual | Single area (or `all` to run sequentially) with optional `--company` filter |

**What it does**
6 independent GitHub Actions jobs run in parallel (one per cron), each targeting one area:

```
04:00 UTC → tl1a job starts
04:10 UTC → tslp job starts
04:20 UTC → il4ra job starts    (all 6 running concurrently)
04:30 UTC → fcrn job starts
04:40 UTC → igf1r job starts
04:50 UTC → tcell job starts
```

Each job runs 4 steps in sequence:

```
Step 3: ct_gov_sync.py --area X
    ↓  (trial records must exist before catalysts are generated)
Steps 1,4,5,6: company_enrichment.py --area X
    ↓
Step 7: research_intelligence.py --area X
    ↓
Identity health check (continue-on-error)
    ↓
write_ranking_snapshots.py (continue-on-error)
```

**Scripts called**
| Script | What it does | Writes to |
|---|---|---|
| `sync/ct_gov_sync.py` | Syncs trial records from ClinicalTrials.gov API | `trials` |
| `enrichment/company_enrichment.py` | Entity discovery, catalyst gen, LLM enrichment, deal intelligence | `companies`, `drugs`, `catalysts`, `deals`, `company_profiles`, `company_intelligence`, +9 more |
| `enrichment/research_intelligence.py` | Scores completeness, detects triggers, determines next action | `research_queue`, `drugs` (completeness fields) |
| `identity/identity_health_check.py` | Flags orphaned/fuzzy entity links | stdout only |
| `scoring/write_ranking_snapshots.py` | Snapshots current rankings | `ranking_snapshots` |

**Timeout**: 120 min per job

---

### `chain-01-meridian-research` — Meridian Research
**File**: `chain-01-meridian-research.yml`

**Triggers**
| Trigger | When |
|---|---|
| ⏰ Cron | 06:00 UTC daily (2AM ET) — after company enrichment completes |
| 👤 Manual | `workflow_dispatch` |

**What it does**

Single job, single script:
```
research.py
  Phase 1: Fetch RSS feeds (PubMed, bioRxiv, company blogs, CT.gov alerts)
  Phase 2: Deduplicate against existing articles
  Phase 3: Full-text fetch for shortlisted items
  Phase 4: LLM extraction → structured intel items
  Phase 5: Write to Supabase
  Phase 6: CT.gov new-registration poll + EDGAR 8-K sweep (no LLM, ~10 min)
```

**Scripts called**
| Script | Writes to |
|---|---|
| `intelligence/research.py` | `articles`, `intelligence_items`, `company_intelligence` |

**Timeout**: 210 min (Phase 6 adds ~10 min vs. original 180 min limit)

---

## Daily Supporting Workflows

### `chain-02-source-verifier` — Source Verifier (Tier 3)
**Triggers**: 08:00 UTC Monday + Thursday  
**Script**: `validation/source_verifier.py`  
**What**: HTTP HEAD checks every source URL across drugs/deals/companies. Updates `url_status` field.  
**Writes to**: `drug_sources.url_status`, `deals.url_status`

---

### `chain-03-content-verifier` — Content Verifier (Tier 4)
**Triggers**: 08:30 UTC Tuesday + Friday  
**Script**: `validation/content_verifier.py`  
**What**: For URLs passing Tier 3, fetches page content and asks Claude whether the page actually supports the claimed fact.  
**Writes to**: `drug_sources.content_verified`, `drug_sources.content_confidence`

---

### `chain-04-compute-landscape-scores` — Landscape Scores
**Triggers**: 11:30 UTC Monday  
**Script**: `scoring/compute_landscape_scores.py`  
**What**: Recomputes competitive landscape scores across all entities.  
**Writes to**: `drug_competitive_scores`, `company_competitive_scores`

---

### `chain-05-meridian-write` — Meridian Writer
**Triggers**: 10:30 UTC daily  
**Script**: `intelligence/write_meridian.py`  
**What**: Assembles today's intelligence items into `meridian_today.html` and pushes via GitHub API.  
**Writes to**: `meridian_today.html` (via git commit)

---

### `chain-06-morning-summary` — Morning Summary
**Triggers**: 11:00 UTC daily  
**Script**: `intelligence/morning_summary.py`  
**What**: Generates a morning summary report from overnight intelligence.  
**Writes to**: `morning_summaries` table

---

### `chain-07-fetch-homepage-news` — Homepage News
**Triggers**: 07:30 UTC daily  
**Script**: `intelligence/fetch_homepage_news.py`  
**What**: Scrapes company homepage news sections for pipeline updates.  
**Writes to**: `company_intelligence`

---

### `daily-signal-monitor` — Signal Monitor (Tier 1)
**Triggers**: 02:30, 06:30, 12:30, 18:30 UTC (4×/day)  
**Script**: `intelligence/signal_monitor.py`  
**What**: Heuristic scan for Tier 1 signals (catalyst dates, press releases, ClinicalTrials status changes). No LLM.  
**Writes to**: `intelligence_items`, `catalysts` (status updates)

---

### `daily-completeness-scoring` — Completeness Rescore
**Triggers**: 09:30 UTC daily  
**Script**: `enrichment/research_intelligence.py` (all areas)  
**What**: Full completeness rescore across all entities — runs after morning enrichment and research settle.  
**Writes to**: `research_queue`, `drugs` (completeness fields)

---

### `daily-queue-processor` — Queue Processor
**Triggers**: 10:00 UTC daily  
**Script**: `intake/process_queue_item.py`  
**What**: Processes enrichment queue items (discovery → confirmed entity promotion).  
**Writes to**: `enrichment_queue`, `companies`, `drugs`

---

### `daily-execute-intel-actions` — Execute Intel Actions
**Triggers**: 10:30 UTC daily  
**Script**: `intake/execute_intel_actions.py`  
**What**: Executes approved intel actions (field patches, relationship inserts) from the intel action queue.  
**Writes to**: various tables per action type

---

### `daily-run-validation-tests` — Ground Truth Validation
**Triggers**: 11:00 UTC daily  
**Script**: `validation/validate_ground_truth.py`  
**What**: Validates entity fields against confirmed ground truth records. Flags regressions.  
**Writes to**: `drug_validation_results`

---

### `daily-structural-edges` — Structural Edges
**Triggers**: 11:00 UTC daily  
**Script**: `graph/materialize_structural_edges.py`  
**What**: Materializes parent/subsidiary company relationships into `entity_edges`.  
**Writes to**: `entity_edges`

---

### `daily-verify-edges` — Edge Verification
**Triggers**: 11:00 UTC daily  
**Script**: `validation/verify_competitor_edges.py`  
**What**: Rule-verifies competitive relationship edges (checks governance constraints).  
**Writes to**: `governance_violations`

---

### `daily-ranking-snapshots` — Ranking Snapshots
**Triggers**: 11:00 UTC daily  
**Script**: `scoring/write_ranking_snapshots.py`  
**What**: Writes point-in-time ranking snapshot rows for trend tracking.  
**Writes to**: `ranking_snapshots`

---

### `daily-stock-prices` — Stock Prices
**Triggers**: 14:00 UTC daily  
**Script**: `sync/stock_prices.py`  
**What**: Fetches current stock prices for tracked public companies.  
**Writes to**: `company_stock_prices`

---

### `daily-pipeline-health` — Pipeline Health
**Triggers**: Every 6 hours (00:15, 06:15, 12:15, 18:15 UTC)  
**Script**: `pipeline_health.py`  
**What**: Checks GitHub Actions recent run outcomes. Reports failures.  
**Writes to**: stdout / notifications

---

### `daily-pipeline-monitor` — Pipeline Monitor
**Triggers**: 05:00 UTC daily  
**Script**: `intelligence/pipeline_monitor.py`  
**What**: Monitors enrichment pipeline health and data freshness metrics.  
**Writes to**: `pipeline_health_log`

---

### `daily-review-submitted-intel` — Review Submitted Intel
**Triggers**: Every 6 hours  
**What**: Checks for new `submitted_intel` rows; if found, runs `intake/review_submitted_intel.py` to classify and route them. Skips silently if no new submissions.  
**Writes to**: `submitted_intel` (status updates), `intelligence_items`

---

## Weekend Batch

### `weekend-abstract-fetcher` — Abstract Fetcher
**File**: `weekend-abstract-fetcher.yml`

**Triggers**
| Trigger | When |
|---|---|
| ⏰ Cron | 14:00 UTC Saturday (10AM ET) |
| 👤 Manual | `workflow_dispatch` |

**What it does**  
Full PubMed + Europe PMC abstract sweep for all tracked drugs and targets. Broader than `research.py`'s daily RSS scan — goes directly to PubMed API.

**Scripts called**
| Script | Writes to |
|---|---|
| `abstracts/fetch_abstracts.py` | `company_documents` |

---

### `weekend-evidence-collectors` — Evidence Collectors
**File**: `weekend-evidence-collectors.yml`

**Triggers**
| Trigger | When |
|---|---|
| ⏰ Cron | 15:00 UTC Saturday (11AM ET) — scheduled 1 hour after abstract-fetcher |
| 👤 Manual | `workflow_dispatch` with optional `areas` and `dry_run` inputs |

**What it does**  
One job, two sequential phases:

```
backfill_sources.py --areas "tl1a il23p19 tslp il4ra fcrn igf1r a4b7"
  Phase 1: drug evidence loop (areas sequential, one failure does not stop the rest)
  Phase 2: patient evidence pass (runs after all areas complete)
```

**Scripts called**

| Script | What it does | External APIs | Writes to |
|---|---|---|---|
| `evidence/backfill_sources.py` | Orchestrator: loops areas, calls drug evidence then patient evidence | — | (delegates) |
| `evidence/drug_evidence.py` | Per drug: verify NCT links on CT.gov, search Europe PMC by drug name, build cited source rows | ClinicalTrials.gov v2, Europe PMC | `drug_sources` |
| `evidence/patient_evidence.py` | For 8 mapped diseases: find epidemiology papers on Europe PMC, patch source URLs | Europe PMC | `indication_patient_intelligence.source_urls` |

**Key design**: Pure API — no LLM, no fabricated URLs. Area loop, error isolation, and phase ordering live in `backfill_sources.py`, not in YAML.

**Timeout**: 45 min

---

### `weekend-sprint` — Autonomous Weekend Sprint
**File**: `weekend-sprint.yml`

**Triggers**: 13 scheduled crons across Friday night → Sunday afternoon. Manual `workflow_dispatch` for any single block.

**Block schedule**
| UTC | ET | Block | What runs |
|---|---|---|---|
| Sat 01:00 | Fri 9PM | A — Validation | Ground truth validation + governance checks |
| Sat 03:00 | Fri 11PM | B1 — Enrichment | Drug enrichment + molecule enrichment |
| Sat 07:00 | Sat 3AM | C1 — Relationships | Competitive scores + edge materialization |
| Sat 11:00 | Sat 7AM | D1 — Synthesis | Company enrichment (all areas) |
| Sat 15:00 | Sat 11AM | E1 — QA #1 | Completeness scoring + validation |
| Sat 17:00 | Sat 1PM | F1 — Reporting | BD recommender + ranking snapshots |
| Sat 19:00 | Sat 3PM | B2 — Enrichment #2 | Drug enrichment pass 2 |
| Sat 23:00 | Sat 7PM | D2 — Synthesis #2 | Company enrichment pass 2 |
| Sun 03:00 | Sat 11PM | E2 — QA #2 | Completeness rescore |
| Sun 07:00 | Sun 3AM | C2 — Relationships #2 | Edge refresh |
| Sun 11:00 | Sun 7AM | D3 — Synthesis #3 | Company enrichment pass 3 |
| Sun 15:00 | Sun 11AM | E3 — QA Final | Final validation pass |
| Sun 18:00 | Sun 2PM | F2 — Final Report | Final BD recommender + snapshots |

**Script**: `weekend_sprint.py` (master orchestrator — dynamically imports block-specific modules)

---

## Weekly Deep Work

### `weekly-school-week-sprint` — School Week Sprint
**File**: `weekly-school-week-sprint.yml`

**Triggers**: Monday–Friday 01:00 UTC (9PM ET previous evening)  
**Timeout**: 90 min per run

**Day-by-day schedule**
| Cron day | Sprint day | What runs |
|---|---|---|
| Mon 01:00 UTC | Monday | Company profile enrichment pass 1 (`company_enrichment.py`) |
| Tue 01:00 UTC | Tuesday | Mechanism + `source_url` enrichment (`drug_enrichment.py`) |
| Wed 01:00 UTC | Wednesday | 100Q drug intelligence seeding (`drug_intelligence_researcher.py`) |
| Thu 01:00 UTC | Thursday | Company profile enrichment pass 2 + `molecule_enrichment.py` |
| Fri 01:00 UTC | Friday | Competitive scoring sweep + `validate_ground_truth.py` |

**Scripts called** (varies by day — detected from `date +%u`)  
`enrichment/company_enrichment.py`, `enrichment/drug_enrichment.py`, `enrichment/drug_intelligence_researcher.py`, `enrichment/molecule_enrichment.py`, `scoring/compute_coverage.py`, `scoring/write_ranking_snapshots.py`, `sync/ct_gov_sync.py`, `validation/validate_ground_truth.py`

---

### Sunday Weekly Batch
All of these run independently on Sunday mornings:

| Workflow | UTC | Script | Writes to |
|---|---|---|---|
| `weekly-refresh-company-verified` | 06:00 | `sync/refresh_company_verified.py` + `validation/company_validator.py` | `companies.verified` |
| `weekly-patient-briefs` | 07:00 | `narrative/generate_patient_briefs.py` | `patient_briefs` |
| `weekly-validation-research` | 07:00 | `validation/conflict_detector.py` + `validation/validation_research.py` | `governance_violations`, `drug_validation_results` |
| `weekly-bd-recommender` | 09:00 | `scoring/bd_recommender.py` | `bd_recommendations` |
| `weekly-landscape-briefing` | 09:30 | `narrative/generate_landscape_briefing.py` | `landscape_briefings` |
| `weekly-narrative-generation` | 10:00 | `narrative/generate_area_narratives.py` | `area_narratives` |
| `weekly-deal-edges` | 10:00 | `graph/materialize_deal_edges.py` | `entity_edges` |

---

### Other Weekly Runs

| Workflow | Schedule | Script | What |
|---|---|---|---|
| `weekly-audit-retention` | Mon 08:00 UTC | `build/apply_sql_migration.py` | Prunes old `field_change_audit` rows |
| `weekly-trial-audit` | Mon 11:00 UTC | `identity/trial_id_audit.py` | Audits trial → drug identity links |
| `weekly-flywheel-phase2` | Tue 12:00 UTC | `ml/flywheel_phase2.py` | Drift detection + training pair generation |

---

## Manual-Only Workflows

| Workflow | Trigger | What |
|---|---|---|
| `manual-apply-migration` | `workflow_dispatch` | Applies a SQL migration via `build/apply_sql_migration.py` |
| `manual-backfill-bd-angle` | `workflow_dispatch` | Backfills `company_profiles.bd_angle` via `enrichment/backfill_bd_angle.py` |
| `manual-backfill-ailux-angle-watch` | `workflow_dispatch` | Watches for Ailux-specific BD angle completeness (monitoring only) |

---

## Retired

| Workflow | Status | Replaced by |
|---|---|---|
| `_retired-evening-update` | Retired 2026-05-21 | Duplicate of `chain-01-meridian-research` at 02:30 UTC Mon–Sat |

---

## How the Chains Connect

```
Nightly (04:00–04:50 UTC)        Weekend (Sat–Sun)
────────────────────────         ─────────────────────────────────────
ct_gov_sync (per area)           Fri 9PM  → weekend-sprint Block A
    ↓                            Fri 11PM → weekend-sprint Block B1
company_enrichment (per area)    Sat 3AM  → weekend-sprint Block C1
    ↓                            Sat 7AM  → weekend-sprint Block D1
research_intelligence            Sat 10AM → weekend-abstract-fetcher
                                 Sat 11AM → weekend-evidence-collectors
                                 Sat 11AM → weekend-sprint Block E1
Daily intelligence chain         Sat 1PM  → weekend-sprint Block F1
─────────────────────            Sat 3PM  → weekend-sprint Block B2
06:00 research.py (RSS+LLM)      ...
07:30 fetch_homepage_news.py
10:30 write_meridian.py          Weeknights (01:00 UTC Mon–Fri)
11:00 morning_summary.py         ─────────────────────────────────────
                                 Mon → company profiles enrichment
Verification (2×/week)           Tue → drug mechanisms + source_url
─────────────────────            Wed → 100Q drug intelligence
Mon/Thu 08:00 source_verifier    Thu → profiles pass 2 + molecules
Tue/Fri 08:30 content_verifier   Fri → competitive scoring + validation
```

---

## Secrets Required

| Secret | Used by |
|---|---|
| `ANTHROPIC_API_KEY` | `company_enrichment`, `research.py`, `content_verifier`, `write_meridian`, `morning_summary`, `weekend-sprint`, `school-week-sprint` |
| `SUPABASE_URL` | all workflows |
| `SUPABASE_SERVICE_KEY` | all workflows |
| `SUPABASE_PAT` | `weekly-audit-retention` (Management API for SQL execution) |
| `GITHUB_TOKEN` | `write_meridian.py` (GitHub API to commit `meridian_today.html`) |
