# scripts/ — Meridian BD Platform

All active scripts live flat in this directory. A subfolder reorganization is
planned (see **Future** at the bottom) — this README serves as the navigation
guide in the meantime.

---

## Quick reference

| Symbol | Meaning |
|---|---|
| ⚙️ | Called by a `.github/workflows/` file on a schedule |
| 🔁 | Dynamically imported by `weekend_sprint.py` |
| 🛠️ | Manual / on-demand — run by hand when needed |
| 🧩 | Imported as a library by other scripts |

---

## 1. Enrichment
AI-powered enrichment of entity data against external sources and LLMs.

| Script | Trigger | Description |
|---|---|---|
| `company_enrichment.py` | ⚙️ | Main company enrichment pipeline — strategy, stage, partnerships |
| `drug_enrichment.py` | 🔁 | Drug-level enrichment — mechanism, stage, trial links |
| `molecule_enrichment.py` | ⚙️ | Molecule characterization — modality, MW, ADME, IP |
| `research_intelligence.py` | ⚙️ | Research intelligence — gap analysis, coverage debt |
| `drug_intelligence_researcher.py` | ⚙️ | Per-drug deep research pass |
| `quick_profiles_enrich.py` | 🛠️ | Fast company profile enrichment (no LLM) |
| `backfill_bd_angle.py` | ⚙️ | Backfill BD angle / fit score for existing drugs |
| `enrich_trial_identity.py` | 🛠️ | Enrich trial → drug identity linking |

---

## 2. Intelligence & Research
News gathering, signal monitoring, and daily intelligence output.

| Script | Trigger | Description |
|---|---|---|
| `research.py` | ⚙️ | Nightly news pipeline — fetches and scores articles |
| `abstracts/fetch_abstracts.py` | ⚙️ | Weekly PubMed + Europe PMC abstract sweep + preprint monitor |
| `fetch_homepage_news.py` | ⚙️ | Homepage news intelligence pilot |
| `signal_monitor.py` | ⚙️ | Tier 1 signal monitor — catalysts, press releases |
| `pipeline_monitor.py` | ⚙️ | Monitors pipeline health and data freshness |
| `write_meridian.py` | ⚙️ | Writes daily Meridian issue to `meridian_today.html` via GitHub API |
| `morning_summary.py` | ⚙️ | Morning summary report (runs after Meridian Writer) |
| `strategic_brief.py` | 🛠️ | Generates a point-in-time strategic brief |

---

## 3. Scoring & Analytics
Computing scores, rankings, and competitive intelligence metrics.

| Script | Trigger | Description |
|---|---|---|
| `compute_coverage.py` | ⚙️ | Computes `coverage_scores` table |
| `compute_landscape_scores.py` | ⚙️ | Computes competitive landscape scores |
| `compute_landscape_coverage.py` | 🛠️ | Landscape coverage metrics (supplemental) |
| `compute_strategic_value.py` | 🛠️ | Strategic value scoring — self-commits via GitHub API |
| `compute_trust_score.py` | 🛠️ | Trust/confidence scoring for entities |
| `portfolio_conflict_scorer.py` | 🛠️ | Portfolio conflict scoring across companies |
| `acquisition_scorer.py` | 🛠️ | M&A acquisition fit scoring — self-commits via GitHub API |
| `rescore_completeness.py` | 🛠️ | Rescore completeness fields after enrichment |
| `write_ranking_snapshots.py` | ⚙️ | Writes ranking snapshot rows |
| `bd_recommender.py` | 🔁 | BD deal recommendations for Ailux |
| `update_area_knowledge_counts.py` | 🔁 | Updates knowledge count fields per area |
| `patch_competitive_scores_null.py` | 🔁 | Patches null competitive score records |
| `add_competitive_relevance.py` | 🛠️ | Adds competitive relevance scores to drugs |

---

## 4. Validation & Governance
Data integrity checks, source verification, and governance enforcement.

| Script | Trigger | Description |
|---|---|---|
| `validate_ground_truth.py` | ⚙️ | Validates entities against confirmed ground truth |
| `validation_research.py` | ⚙️ | Research-backed validation of drug/company fields |
| `conflict_detector.py` | ⚙️ | Detects data conflicts across related entities |
| `consistency_checker.py` | 🔁 | Entity-level consistency checks (governance rules) |
| `source_verifier.py` | ⚙️ 🔁 | Tier 3: validates every source URL for liveness + trust |
| `content_verifier.py` | ⚙️ | Tier 4: fetches source pages, verifies claim support |
| `company_validator.py` | ⚙️ | Company-level validation pass |
| `source_verify.py` | 🛠️ | Populates `source_url` + `confidence_level` for `drug_area_scores` nulls |
| `verify_sources.py` | 🛠️ | Checks `drug_sources` URLs, updates `url_status` |
| `audit_sources.py` | 🛠️ | Manual source audit across all entities |
| `verify_competitor_edges.py` | ⚙️ | Rule-verifies competitive relationship edges |
| `verify_publication_values.py` | 🛠️ | Verifies publication-cited field values |
| `reconcile_drug_integrity.py` | 🛠️ | Reconciles drug identity + data integrity post-merge |
| `apply_governance_violations.py` | 🛠️ | Applies governance violation records manually |
| `apply_entity_consistency_checks.py` | 🛠️ | Applies entity-level consistency check rules |

---

## 5. Identity & Deduplication
Entity resolution, deduplication, and trial identity.

| Script | Trigger | Description |
|---|---|---|
| `identity_resolution.py` | 🛠️ | Resolves drug identity → `canonical_drugs` |
| `company_identity_resolver.py` | 🧩 | Library: company name normalization + deduplication |
| `identity_health_check.py` | ⚙️ | Reports identity resolution health metrics |
| `trial_id_audit.py` | ⚙️ | Audits trial → drug identity linking |

---

## 6. Intake & Review
Ingesting new entities and reviewing queued intelligence.

| Script | Trigger | Description |
|---|---|---|
| `company_intake.py` | 🛠️ | Interactive company intake → Supabase |
| `drug_intake.py` | 🛠️ | Interactive drug intake → Supabase |
| `conversation_intake.py` | 🛠️ | Parses conversation transcripts into structured intake |
| `approve_discovery.py` | 🛠️ | Promotes discovery queue items to confirmed entities |
| `process_queue_item.py` | ⚙️ | Processes single enrichment queue items |
| `review_submitted_intel.py` | ⚙️ | Reviews and routes submitted intel items |
| `execute_intel_actions.py` | ⚙️ | Executes approved intel actions against Supabase |
| `human_queue_builder.py` | 🔁 | Builds the human review queue (`kyle_reviews`) |

---

## 7. External Sync
Syncing data from external sources (ClinicalTrials, stock feeds, evidence).

| Script | Trigger | Description |
|---|---|---|
| `ct_gov_sync.py` | ⚙️ | Syncs ClinicalTrials.gov trial data |
| `stock_prices.py` | ⚙️ | Fetches company stock prices |
| `evidence/backfill_sources.py` | ⚙️ | Evidence source backfill entrypoint (drug + patient phases) |
| `refresh_company_verified.py` | ⚙️ | Refreshes `company.verified` status |
| `sync_collection_queue.py` | 🛠️ | Syncs collection queue from external triggers |

---

## 8. Graph & Edges
Building and materializing the entity relationship graph.

| Script | Trigger | Description |
|---|---|---|
| `materialize_deal_edges.py` | ⚙️ | Materializes deal/ownership edges into `entity_edges` |
| `materialize_structural_edges.py` | ⚙️ | Materializes structural edges (parent/subsidiary) |
| `coverage_gap_finder.py` | 🔁 | Finds coverage gaps in entity graph |
| `seed_company_edges.py` | 🛠️ | Seeds company → company relationship edges |
| `seed_partnership_edges.py` | 🛠️ | Seeds partnership edges from known deals |
| `seed_patient_edges.py` | 🛠️ | Seeds patient/indication edges |

---

## 9. Seeding
Seeding reference and initial data into Supabase.

| Script | Trigger | Description |
|---|---|---|
| `seed_competes_with.py` | 🛠️ | Seeds competition relationships in `entity_edges` |
| `seed_competitive_signals.py` | 🛠️ | Seeds competitive signal records |
| `seed_company_hq.py` | 🛠️ | Seeds company HQ / location data |
| `seed_indication_priorities.py` | 🔁 | Seeds `indication_priority_scores` + writes `data/indication_priority_scores.json` |
| `seed_kyle_reviews.py` | 🛠️ | Seeds Kyle review queue from enrichment log |
| `seed_preclinical_competitors.py` | 🛠️ | Seeds preclinical competitor records |
| `seed_strategic_views.py` | 🔁 | Seeds company strategic views |
| `seed_targets.py` | 🛠️ | Seeds drug target records |
| `seed_tl1a_companies.py` | 🛠️ | Seeds TL1A company pipeline from index.html |

---

## 10. Narrative Generation
Generating human-readable intelligence outputs.

| Script | Trigger | Description |
|---|---|---|
| `generate_area_narratives.py` | ⚙️ | Generates area-level competitive narratives |
| `generate_landscape_briefing.py` | ⚙️ | Generates landscape briefing documents |
| `generate_patient_briefs.py` | ⚙️ | Generates patient population briefs |
| `narrative_gen.py` | 🧩 | Library: shared narrative generation utilities |
| `landscape_narrative.py` | 🛠️ | Point-in-time landscape narrative |
| `patient_narrative.py` | 🛠️ | Patient population narrative |
| `run_pkpd_claude.py` | 🛠️ | PK/PD analysis with Claude |

---

## 11. ML & Fine-tuning
Machine learning tooling for enrichment quality improvement.

| Script | Trigger | Description |
|---|---|---|
| `extract_fine_tune_signal.py` | 🛠️ | Extracts fine-tuning signal from `kyle_reviews` → `output/` |
| `flywheel_phase2.py` | ⚙️ | Drift detection + auto-restore + training pair generation → `output/` |
| `apply_prompt_improvements.py` | 🛠️ | Applies training pair insights to enrichment prompts → `output/` |
| `model_comparison.py` | 🛠️ | Compares enrichment quality across model versions |

---

## 12. Build & Export
Building static assets and exporting schema/data.

| Script | Trigger | Description |
|---|---|---|
| `build_navigator_lookup.py` | 🛠️ | Builds `data/navigator_lookup.json` from Supabase |
| `export_schema_snapshot.py` | 🛠️ | Exports live schema to `migrations/v1_schema.sql` |
| `apply_sql_migration.py` | ⚙️ | Applies SQL migration files via Supabase Management API |
| `apply_drug_sources_migration.py` | 🛠️ | Applies drug sources schema migration |

---

## 13. Orchestration
| Script | Trigger | Description |
|---|---|---|
| `weekend_sprint.py` | ⚙️ | Master orchestrator — runs all sprint phases A–F in sequence |
| `pipeline_health.py` | ⚙️ | Reports GitHub Actions workflow run health |

---





company_enrichment.py
The key structural problems the inventory surfaces:

Call #4 is the highest blast radius in the codebase. One call writes to 15 tables. JSON truncation (stop_reason='max_tokens') is already detected — but not recovered from. Partial writes land silently. Pydantic validation covers only 7 drug fields; the company_profile narrative fields have no runtime enforcement.

Two prompts are invisible. _COVERAGE_SYSTEM (call #5) is a string literal inside a function body. enrichment_system_prompt() (call #4) is a 400-line dynamic function mixing governance rules, data quality constraints, and output format. Neither is discoverable from a prompt registry.

Calls #1 and #3 are free-text passthrough. Web-search output injects unvalidated narrative into call #4's prompt — a hallucinated fact from the web search arrives in the synthesis with the same weight as a Supabase-sourced fact.

The compounding value
None of these phases are independent. The progression matters:
ai/ layer           →  prompts + schemas are separate from business logic
PipelineState       →  inter-step data has names and types
Tier 1 extractions  →  nodes have no dependencies on the monolith
LangGraph           →  routing is explicit, resumable, and visual