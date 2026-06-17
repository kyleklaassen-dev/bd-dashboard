<!-- update_log.md — recent entries only (most recent ~50). Older history archived to docs/reports/update_log_archive.md on 2026-06-15 to keep the repo root legible. -->


---

## 2026-06-06 — Graph connectivity: orphans connected + structural backbone built

Connectivity audit answered "is everything connected?": NO — 55 of 159 visible drugs were orphans (no edges), 66 companies orphan, and the graph had competitive edges but no STRUCTURAL edges. Fixes:
- **Connected all 55 orphan drugs** — rule-derived 1525 direct_competitor edges via shared area (all verified). 0 orphan drugs now.
- **Built the missing structural backbone in entity_edges** (the triple store, was scoped to drug/company/target/area + competitive predicates only). Extended it to allow `indication` + added predicates: **TREATS** (drug→indication, 280, from drug_indications), **ADDRESSES** (target→indication, 122, derived — the keystone that makes patient→target traversable), **DEVELOPED_BY** (drug→company, 148). The patient → indication → target → drug → company chain is now traversable as graph edges (verified: TL1A → {AD,CD,HS,RA,UC}). Durable via scripts/materialize_structural_edges.py + daily workflow.

---

## 2026-06-06 (overnight) — Patient batch 2, validation tests, Python 3.12, research-script doc

- **Patient layer 22 → 28 indications:** added Psoriatic Arthritis, Lupus Nephritis, COPD (Type-2), Chronic Spontaneous Urticaria, CRSwNP, Sjögren's — each researched with epidemiology, benchmarks, Ailux-framed why_it_matters, sources.
- **2 failing validation tests resolved correctly** (the column stores 'fail'/'pass' strings — earlier boolean filter missed them): J&J genuinely in tcell (cilta-cel/teclistamab TCE platform) → added company_areas(jnj,tcell); Amgen NOT in fcrn (empty stub profile, no FcRn asset) → removed spurious company_profile. 0 validation tests now failing.
- **Python 3.12 standardization:** bumped 16 workflows from 3.11 → 3.12 (only the retired one-shot left).
- **"Three overlapping research scripts" dissolved:** documented in docs/RESEARCH_SCRIPTS.md that they're complementary stages (ingest → assess → deep-dive), not redundant.
- Refreshed Atlas stats (deal edges 79, 88% competitor edges verified, 28 indications) + flipped the closed gaps.

---

## 2026-06-05 (cont. 15) — Relationship verification: graph 0% → 51% (competitor layer 88%)

Pushed the highest-value open Atlas gap: "100% of competitive relationships unverified." Insight — a direct_competitor edge whose two drugs share a CONFIRMED disease area (drug_areas) is a confirmable fact, not a guess. Rule-verified those (confidence 'medium', inference_method 'rule_inferred', evidence names the shared area): **competitor layer 0% → ~88% verified (1250/1426); overall graph 0% → 51%.** The 176 remaining are genuine cross-area edges that need a closer look. Built scripts/verify_competitor_edges.py (idempotent) + daily Verify Competitor Edges workflow so new edges get rule-checked. Also reconciled stale Atlas gaps to FIXED: field_change_audit retention, the 4 governance violations (researched + fixed earlier this session).

---

## 2026-06-05 (cont. 14) — Query/schema backlog COMPLETE (24 real mismatches fixed)

Finished the last 3: drug_area_scores `score`→`strategic_value_score`, drugs `company`→`company_id`, and rewrote drug_failure_cascade (no FK to drugs → replaced the impossible nested embed with flat columns affected_drug_name/affected_company/impact_rationale + updated the consumer). All verified 200 live — drug_failure_cascade now returns real data (the batoclimab/nipocalimab FcRn safety-differentiation cascade). Final sweep: **0 real mismatches remain**; the 6 still flagged are parser false-positives (legacy_area_ontology_map columns exist). Net for dimension 13: 49 flagged → 24 real mismatches all fixed, 25 false-positives. The dashboard read layer is no longer silently broken anywhere.

---

## 2026-06-05 (cont. 13) — Query/schema backlog: 17 more column mismatches fixed (21 total)

Worked the column-mismatch backlog. Technique: PostgREST aliasing (`wrong:real` in the select) revives the feature without touching rendering code, since any bad column 400s the whole query. Fixed + verified live (queries now return 200 w/ data): intel feeds (summary→body, dropped area_id/ailux_angle), company_profiles (dropped confidence_tier/assessment/competitive_position), catalyst_calendar, catalyst_bd_timing_window (bd_score→overall_bd_score), deal_sequencing_constraints (constraint_description→description etc. — revived the AbbVie/ABBV-701 timing analysis that was fully hidden), catalysts (catalyst_text→notes, catalyst_name→label), geographic_approvals (approval_status→approval_type), coverage_scores (coverage_score→overall_score), companies (dropped sector, market_cap_usd_m→market_cap, dropped stage), targets (name→label), target_pairs (name→pair_symbol), research_queue (priority→priority_score, status→assigned_status). **21 of 49 done.** Deferred: drug_failure_cascade (no FK to drugs — embed impossible, needs query rewrite; fails gracefully today), drug_area_scores legacy dual-read harness.

---

## 2026-06-05 (cont. 12) — Health reconcile, Atlas open-gap count, review resolve UX

- **"3 failures" reconciled to 1:** the health summary (computed live from GitHub) correctly said 1 failing, but the tile list showed 3 because pipeline_runs held stale rows for a retired workflow (v37 one-shot) + a renamed one (execute-intel-actions.yml → "Execute Intel Actions", green). Deleted the 3 stale rows; tile now matches. The 1 real failure (Weekend Sprint, last run 5-31) self-heals on tomorrow's Saturday cron (--block F argparse fix is in main).
- **Atlas "many gaps" fixed:** the per-layer gap count was counting ALL gaps (fixed + open), so solved layers looked unsolved. Now shows OPEN only ("N open →" / "✓ all fixed →").
- **Review-queue resolution UX:** added per-drug 🔍 web-verify links + clear guidance (dashboard is read-only public key → resolve by telling Claude or editing Supabase, not a button).

---

## 2026-06-05 (cont. 11) — Review queue, header fix, Lens→Atlas, query/schema sweep

- **"Needs Your Review" queue:** header ⚑ badge + panel reading open governance_violations — the flagged drugs/questions now have a real review surface (was only a Supabase table + blank footer badge). Fixed loadGovernanceViolations' wrong columns (entity_id/violation_description → row_id/description).
- **Header overlap fixed:** the centered search was `position:absolute` and collided with the right-side tools; made it in-flow (flex:1), single clean row.
- **Lens button → Atlas:** the "◎ Lens" launcher now opens meridian_atlas.html — the "everything" hub — instead of just the strategic lens. Deployed Atlas + workflow map + docs to the repo (were 404) and added Atlas links (← Dashboard, workflow map, strategic lens, data-quality audit, standards, value brief, execution plan). All resolve 200.
- **Query↔schema sweep (requested):** scanned 303 `_sb.from().select()` calls across 78 tables vs information_schema → **49 column mismatches** (queries selecting columns that don't exist = silently-broken features). Fixed 4 high-impact (deals value_usd→total_usd_m, indications search synonyms→abbreviation, drug_validation_results status/detail/checked_at→check_status/details/verified_at, governance display). Remaining ~45 documented as a backlog in docs/DATA_QUALITY_AUDIT.md (dimension 13).

---

## 2026-06-05 (cont. 10) — Originator-research round + 4 phantom competitors removed

Researched the 20 company-less drugs + mechanism flags.
- **Caught 4 mis-ingested junk records** sitting in the FcRn/TL1A/T-cell landscapes as phantom competitors, each verified to be a real drug with a WRONG target, out of Ailux scope → hidden + area mappings removed: **RGX-181** (REGENXBIO AAV gene therapy for CLN2 Batten disease, DB said FcRn), **LBP-EC01** (Locus CRISPR phage for UTI, DB said TL1A/IBD), **GB1275** (Gossamer CD11b oncology, DB said FcRn), **SRF-231** (Surface anti-CD47 oncology, discontinued, DB said CD47×CD3 autoimmune).
- **Attributed originators** (with company creation where needed): tapinarof→Dermavant, hlx36→Henlius, ionis-tslp-25rx→Ionis, ati-052→Aclaris, mk-1695→Merck (+ prior batch Innovent/Hengrui/Zai Lab/Akeso/Novartis). Company attribution now **93% (148/159)**.
- 11 obscure early-stage codes (ab001, calt-100, eta1001, mg-k10, sm-101, xb3217, …) have no searchable web presence — flagged for primary-source/CDE follow-up rather than guessed.

---

## 2026-06-05 (cont. 9) — Data Quality Audit framework + Tier 1 & 3 sweep

Created `docs/DATA_QUALITY_AUDIT.md` — a 12-dimension, 3-tier audit with repeatable scans + tracked status, so gap-hunting is ordered.
- **Tier 1 (5/5):** mechanism↔target (prior round); trial-attribution (52 "foreign codes" = each drug's own dev-code, no new misattributions); duplicates (**BSI-045B/ATI-045/bosakitug** — 3 records of one TSLP mAb merged); target-hygiene (kyv-101 "(CAR-T)" stripped); indication-hygiene (**28** target-codes in indication_short → diseases).
- **Tier 2:** skipped per Kyle.
- **Tier 3 (3/3):** brand-name (benralizumab approval_date added); null-fields (company_id 27→20, attributed 7 confident originators); area-classification (**SIM0500** — a GPRC5D×BCMA×CD3 myeloma TCE wrongly in IBD/TL1A and inflated to #1 in IBD ranking — removed + hidden).
- 20 company-less drugs + the 4 mechanism flags + ab001 remain flagged in governance_violations for per-drug research.

---

## 2026-06-05 (cont. 8) — Mechanism/target corruption cluster + root-cause prevention

Fresh data-integrity scan found a cluster of **mechanism↔target mismatches** (same hallucination pattern as lu-ag22515 — mechanism text describing a TL1A/IL-23/FcRn drug when the target field says otherwise). Of ~7 found:
- **Fixed with research + sources (4):** CND319 (CD19×CD20×CD3 TCE) + CND460 (BCMA×CD19×CD3 TCE) — mechanism wrongly said FcRn; IBI3002 (IL-4Rα×TSLP, Innovent) + bosakitug (TSLP, Biosion) — mechanism wrongly said TL1A. Targets were correct; mechanisms corrected.
- **Flagged for verification (4):** mk-1695, shr0817, hlx36, abs-101 — couldn't confirm which field is correct via web search; logged to governance_violations rather than guess.
- **Root-cause fix (durable):** added a "MECHANISM ↔ TARGET CONSISTENCY" rule to the enrichment system prompt (company_enrichment.py) — mechanism must describe the exact target named in `target`; never default to a TL1A/IL-23 description; sparse-but-correct beats confident-wrong.
- Confirmed the 7 brand_name-set-but-stage-Phase-3 drugs (Fasenra, Rinvoq, etc.) are NOT a bug — approved drugs in new-indication trials, handled by _resolveStage for display.

---

## 2026-06-05 (cont. 7) — Patient/indication layer + search bugfix

- **+5 sourced Ailux-relevant indications** added to indication_patient_intelligence (17→22): Plaque Psoriasis (ALX001 indication; IL-23 clearance gap), SLE (ALX002 CD19×BCMA space; CD19 CAR-T drug-free remission), Severe Asthma (TSLP/tezepelumab; non-Type-2 segment), Hidradenitis Suppurativa (IL-17/emerging TL1A-IL-23), EoE (IL-4Rα/IL-13). Each with epidemiology, remission benchmarks, unmet-need narrative, Ailux-framed why_it_matters, and 2 source URLs from current literature.
- **Improvement found along the way:** the global search queried indication_patient_intelligence with columns that don't exist (patient_count / unmet_need_summary / key_patient_insight) → patient intel NEVER surfaced. Fixed to patient_count_us / unmet_need_narrative / why_it_matters; verified live ("lupus" now returns SLE patient intel).

---

## 2026-06-05 (cont. 6) — Deal-edge layer deepened (19 → 79)

The graph was thick in competitive edges (968 direct_competitor) but thin in the BD-bearing layer (19 deal/ownership edges) because company_partnerships / asset_transfer_history / deals were never mirrored into entity_relationships. Built `scripts/materialize_deal_edges.py` (idempotent dedup on source+target+type) + weekly "Materialize Deal Edges" workflow. Backfill: **19 → 79** deal/ownership edges (56 licensor_licensee, 11 parent_subsidiary, 10 co_developer, 2 combination), each carrying a source_url; verified ones at confidence "high", inferred at 0.6–0.65. Direction handled per type (licensed_in vs out, acquirer=parent). Self-maintaining going forward.

---

## 2026-06-05 (cont. 5) — Governance violations resolved with research

- **lu-ag22515** — record was corrupted (target=TSHR, mechanism described TL1A, stage=Preclinical, igf1r area). Verified via Lundbeck PR + NCT06557850: it's **Lu AG22515**, an anti-CD40L SAFA fusion protein (AprilBio-originated, licensed to Lundbeck 2021), **Phase 2 for Thyroid Eye Disease**. Fixed target→CD40L, mechanism, stage→Phase 2, company_id→aprilbio (created), partner→Lundbeck, indication→TED, removed the wrong igf1r area mapping. 2 sources logged.
- **mt-251** — trial misattribution. CT.gov ground truth: NCT07219368=MT-201, NCT06762457=MT-501, NCT07113522=MT-501/MT-201 platform — all wrongly attached. Removed those 3; kept the genuine NCT07423299 (intervention=MT-251). MT-251 itself confirmed real (Mirador TL1A×IL-23 bispecific, Phase 1 healthy volunteers — a direct Ailux competitor).
- **batoclimab** — the licensing claim (HanAll→Immunovant) is factually correct (1997... 2017 deal, IMVT-1401); the original source just didn't support it. Attached AdisInsight as the confirming source, set content_confirms_claim=true.
- All 4 governance_violations now resolved (0 unresolved).

---

## 2026-06-05 (cont. 4) — Gap burn-down batch 1 (Atlas 16→20 fixed)

- **Revived 2 inert tables**: bd_recommendations (bd_recommender.py) + landscape_briefings (generate_landscape_briefing.py) now have weekly producer workflows. Dispatched once to verify — bd_recommendations 20→35, landscape_briefings 1→2. (3 other "inert" tables already refresh weekly via weekend_sprint; 3 are static strategic reference.)
- **field_change_audit retention**: fn_prune_field_change_audit(30d) + weekly Audit Retention workflow (keeps governance + correction rows forever). Bounds a table growing ~10k rows/day.
- **field_consistency validator false-positives fixed**: the bispecific target-counter only recognized "×"; now also recognizes x / spaced-x / compact AxB. Cleared 4 false warnings (eta1001, sm-101, ibi3002, xb3217). Validation warnings 57→53 (remaining 53 are all the known China-CDE stage_trial_match gap).
- **apply_sql_migration.py**: added a User-Agent (Cloudflare error 1010 was blocking the default urllib UA on the Management API from CI runners).
- Atlas refreshed to 20 fixed / 14 open.

---

## 2026-06-05 (cont. 3) — Wave 2 finish + workflow refine + Atlas

- **Wave 2d** — global search now resolves prior/code names via `drug_aliases` (e.g. "AMG 729" → Obexelimab, with a "↳ prior name" badge). Verified live.
- **Wave 2c** — Strategic Lens (TL1A Race) deployed to the repo + "◎ Lens" launcher added to the dashboard header (data-trusted so the link interceptor doesn't hijack it). Verified live.
- **Workflow refinement** — retired the obsolete one-shot `apply-drug-sources-migration` workflow (v37 long applied); confirmed the weekend sprint is code-fixed (`--block F` now in argparse); 27/29 latest-green.
- **Atlas** — `meridian_atlas.html` gap registry refreshed: 16 gaps → FIXED, metrics + layer statuses updated to current state.

---

## 2026-06-05 (cont. 2) — Wave 2 modal surfacing + RLS read regression fix

- **CRITICAL RLS fix:** my own security lockdown had enabled RLS on 47 tables to block anon writes but never added anon SELECT policies → those tables returned `200 + 0 rows` to the dashboard (silently invisible). Many "DARK tables" were dark for THIS reason. Added `anon_read_<t>` SELECT policies (USING true) to all 47; writes still blocked (verified anon write → 401/42501). Audit query for regressions in [[project_rls_read_policies]].
- **Wave 2a — drug_sources provenance** now surfaced in the drug modal's "Sources & provenance" section: claim-level sources with ✓ confirmed / ✗ unconfirmed / unverified / removed badges. Verified live on mt-251 (14 documented, 6 content-verified).
- **Wave 2b — company_partnerships** surfaced in the company modal "Partnerships" section: structured relationships (partner, type, asset, geography, ✓ verified pill, source link), both sides of each relationship. Verified live on UCB (5 relationships).

---

## 2026-06-05 (cont.) — Health-tile link fix + alias persistence

- **Health-tile links fixed (root cause):** a global capture-phase click interceptor (index.html ~24943) rewrites *every* external link click into a Google search of the link text (legacy: stored URLs were unreliable). My GitHub run links got swept up. Fix: marked health links `data-trusted="1"` and taught BOTH the interceptor and `_fixGenericLinks` to skip `data-trusted` links. Verified live: clicks now open the GitHub run page.
- **Always-save-prior-names (Kyle request):** DB trigger `trg_drugs_capture_aliases` → `fn_capture_drug_aliases()` captures name/id/inn_name/brand_name + `aliases` jsonb into `drug_aliases` on every `drugs` insert/update (ON CONFLICT DO NOTHING, EXCEPTION-safe). Backfill: drug_aliases 183→574 rows, canonical coverage 172→240/248. Renames now keep old names permanently. Open follow-up: global search reads `drugs.aliases`, not the table.

---

## 2026-06-05 — Catalog-tail cleanup, drug_areas trigger fix, Wave 2 health tile, obexelimab dedup

**Catalog tail (90 unmapped real drugs) classified — indication decides, not target:**
- 64 mapped to areas; 22 out-of-scope (oncology/metabolic/ophthalmology) hidden via `dashboard_visible=false`; flagged-6 resolved by evidence (rituximab+daratumumab→autoimmune, xb3217+lbl-051-s3→tcell, m701 hidden, xmab5871→dedup).
- 6 unreferenced phantom placeholders hidden (incl. tislelizumab leaking onto the dashboard); apg777 (alias→drug) + catalog-53 (catalog_entry→drug) record_type fixed.

**Structural fix — `drug_areas` inserts were 404-ing for everyone:** the `fn_sync_drug_indication_group()` AFTER INSERT trigger queried a non-existent `disease_areas` table, blocking *all* ontology growth. Guarded with `to_regclass`. Also minted 42 singleton `canonical_drugs` for never-resolved tail drugs (the upstream reason they were unmapped).

**Wave 2 — pipeline health indicator (index.html):** header health dot + click-through panel reading the previously-dark `pipeline_runs` + `system_status.health_summary`. Green/amber dot, latest run per workflow, failing-first, links to GitHub runs.

**Workflow fix:** `apply-migration.yml` had never been valid YAML (un-indented inline python heredoc broke the block scalar) → startup_failure on every push. Moved logic to `scripts/apply_sql_migration.py`; cleared stale failure rows; dispatched a green dry-run.

**Dedup (Kyle-confirmed):** XmAb5871 = XMAB-5871 = AMG 729 = **obexelimab** (Xencor pre-INN code names; CD19 mAb Fc-engineered to co-engage FcγRIIB — inhibits B cells without depleting). Folded xmab5871 into `CANON_DRUG_CA5E6284`; registered all 6 names in `drug_aliases`; research_queue resolved.

---

## 2026-06-03 (overnight) — IGF-1R relationship coverage + data-integrity finds

- **IGF-1R landscape_dependency_score 83.5 → 93.5.** Relationship coverage 0.6 → 1.0 after adding two *real, sourced* Viridian deals covering veligrotug (VRDN-001) and elegrobart (VRDN-003): Kissei Japan license (Jul 30 2025; $70M upfront, up to $315M, 20s–mid-30s% royalties) and DRI Healthcare US synthetic royalty (Oct 2025; up to $300M). 4 deal rows + 4 `drug_sources` rows. Directly relevant to veligrotug's June 30 PDUFA (queue #1).
- **Data-integrity flag (governance_violations):** `lu-ag22515` record corrupted — stored target=TSHR, mechanism text describes TL1A/DR3 (hallucinated), company_id null, indication_short="IGF1R", stage=Preclinical. Verified reality: AprilBio-originated **anti-CD40L SAFA** fusion protein, licensed to Lundbeck, **Phase 2 TED** (NCT06557850). Mis-placed in target/igf1r context. Logged for Kyle review (not auto-edited). Sources in `drug_sources`.
- **PRIORITY.md correction:** the "autoimmune 0.31 / IGF-1R 0.40" relationship-coverage figures were stale. Actual current: autoimmune LDS 94.48 (rel 1.0), igf1r now 93.5 (rel 1.0).
- **Bugfix:** `scripts/compute_landscape_scores.py` — `_apply_lds_priority_feedback` called undefined `log()` (crashed at tail after writes). Added `log = print` alias.

---

## 2026-06-03 — Flywheel close (S1 option 1) + Fresh-data banner (S3)

**S1 — Enrichment hints now consumed at runtime (closes the flywheel loop):**
- `scripts/company_enrichment.py`: added `load_enrichment_hints()` + `enrichment_system_prompt()`. The Phase B synthesis call now appends `data/enrichment_prompt_hints.md` (auto-generated from Kyle's confirmed ground truth by `apply_prompt_improvements.py`) to `ENRICHMENT_SYSTEM`. Previously the hints file was generated but never read at enrichment time — now it reaches the model on every run. `prompt_snapshot` also captures the effective (hints-included) prompt. Hints are memoized per process; missing file is a no-op.

**S3 — Dashboard fresh-data banner (last-updated, polling approach):**
- New Supabase table `system_status` (singleton id=1) via `migrations/schema_migration_system_status_v1.sql`: `last_enrichment_at`, `last_research_at`, `last_pipeline_label`, `updated_record_count`, `note`, `updated_at`. RLS: anon/authenticated SELECT only.
- `scripts/company_enrichment.py`: `update_system_status()` helper; stamps `last_enrichment_at` + record count at end of the enrichment run (non-fatal).
- `scripts/research.py`: `stamp_system_status_research()`; stamps `last_research_at` at end of the nightly research pipeline.
- `index.html`: fixed-position soft banner that baselines `system_status` server timestamps at page load, polls every 5 min, and shows a dismissable "New intelligence has arrived — refresh" prompt when a newer enrichment/research timestamp appears. Server-to-server timestamp comparison (no client-clock skew). Does not auto-reload; user-initiated refresh only. Complements the per-area freshness badge (Task 23) by proactively signaling new data arriving after page open.

## 2026-05-31 (Session 98) — Intelligence Brain: 4 New Tables, Bispecific Race Dashboard, Conversation Intake Agent

**New Supabase tables created:**
- `drug_bispecific_landscape` — 10 rows; all TL1A×IL-23 programs ranked by clinical advancement; format, valency, IL-23 arm selectivity, Sanofi conflict flag, vs-ALX001 comparisons
- `conversation_intelligence_intake` — auto-capture table with auto-promote trigger (>0.85 confidence → governance_violation flag)
- `drug_cdx_strategy` — 3 rows; tulisokibart ARTEMIS-UC CDx (clinical_validation), ALX001 dual biomarker UC (hypothetical), ALX001 CD CDx (discovery)
- `bispecific_clinical_hypothesis` — 1 row; formal "30% Both-Arms Needed Hypothesis" with patient population math, mechanistic rationale, expected remission rates

**Dashboard update (index.html):**
- Added "Bispecific Race" pill button in TL1A left pills column (purple/violet styling)
- Added `tl1a-modal-bispecific-race` modal overlay with live Supabase table load
- Race table: rank badge, phase chip, format badge (single-mol vs co-form), IL-23 arm color coding (p19=green, p40=red), Sanofi conflict callout
- `_loadBispecificRace()` JS function with `_bispecificRaceLoaded` guard

**New script:**
- `scripts/conversation_intake.py` — session-end intelligence capture agent; uses Claude API (claude-opus-4-5) for fact extraction; --review/--promote/--reject CLI; stores to conversation_intelligence_intake

**Key intelligence formalized:**
- RO7837195 p40-blocking IL-23 arm = mechanistic disadvantage vs ALX001 p19-selective
- SPY230 co-formulation (NOT single molecule) — different IP and PK profile
- HXN-1003/Sanofi internal conflict: duvakitug Phase 3 vs HXN-1003 bispecific simultaneously
- HY8931 = direct 2+2 format competitor to ALX001 (only other confirmed 2+2)
- 30% hypothesis: ~30% UC patients need both arms; dual biomarker (TNFSF15 TAG + IL-23p19 mucosal) identifies them

**Commit:** 3ecb9bb6b8 (index.html) + fb537f1c4d (conversation_intake.py)

---

## 2026-05-31 (Session 97) — TL1A×IL-23 Bispecific Landscape: Complete competitive picture, two new intelligence tables, BCD-261 added

**Research completed:**
- ClinicalTrials.gov systematic search for all TL1A×IL-23p19 bispecifics globally
- Confirmed 7 true bispecifics and 1 co-formulation (Spyre SPY230) ahead of ALX001
- Discovered BCD-261 (Biocad, Russia): Phase 2 UC + CD simultaneously (NCT07080034/NCT07078994), FIH March 2024 — NOT previously in database

**New company/drug added:**
- `biocad` company record added
- `bcd-261` drug record added: Phase 2, TL1A×IL-23p19 bispecific, UC + CD, FIH March 2024
- drug_targets rows for bcd-261 (tl1a + il23p19, both co_primary)
- drug_development_timelines: FIH actual=2024-03-29, phase2_start actual=2025-08-14

**RO7837195 record updated:**
- differentiation_thesis updated with p40-blocking IL-23 arm as key disadvantage vs p19-selective
- FIH estimated date set to ~2022 (backward projection from Phase 2b timeline)

**Tables created (`migrations/v43_bispecific_differentiation_tables.sql`):**
- `bispecific_differentiation_factors` — 18 rows covering format, binding, PK, PD, patient_selection, regulatory, clinical_design, manufacturing, safety factors. Each row: mechanistic_rationale, clinical_significance, ailux/mirador/roche/spyre positions, importance_rank 1-10, evidence_quality.
- `nonresponder_bispecific_bridge` — 8 rows mapping UC patient phenotypes to bispecific rescue mechanisms. Covers the complete patient math for ALX001's addressable population.

**Key findings:**
- TRUE bispecifics ahead of ALX001 (Phase order): RO7837195 (Phase 2b, Roche/Pfizer, p40-blocking), BCD-261 (Phase 2, Biocad), QX030N/CLD-423 (Phase 1, Qyuns/Caldera), MT-251 (Phase 1 FIH Jan 2026, Mirador), SIM0709 (Phase 1, Simcere/BI), HY8931 (Phase 1, Newsoara, 2+2), LQ080 (Phase 1, Novamab, VHH nanobody)
- Top 3 differentiation factors (rank 9/10): (1) p19-selective vs p40-blocking IL-23 arm — PROVEN, ALX001 wins; (2) dual target biomarker strategy for patient selection — EMERGING; (3) Phase 2 trial design with monoAb arms vs placebo-only — EMERGING, Spyre is gold standard
- Core bispecific hypothesis population: 30% of UC (Th1/Th17 mixed, co-elevated TL1A+IL-23)
- ALX001 addressable: ~60% of UC (excludes TSLP-dominant 15% and fibrostenotic 10% + TNF-innate 5%)
- ALX001 engineering advantage on 3 key factors: DR3-selectivity (spares DcR3), p19-selective IL-23 arm, 2+2 symmetric format (easier manufacturing + maximum ILC3 co-engagement)

---

## 2026-05-31 (Session 96) — Three new intelligence systems: non-responder phenotypes, IND-to-FIH knowledge base, Ailux BD context

**Tables created:**
- `drug_nonresponder_profiles` — who fails TL1A mono (52%), IL-23 mono (60%), and the dual non-responder pool (~42% theoretical). 3 rows seeded for ALX001 / UC with escape mechanisms, biomarkers, and bispecific rescue hypothesis.
- `drug_development_steps` — complete 16-step IND-to-FIH knowledge base for biologics. Steps 1-16 from IND submission to FIH dose. Bispecific-specific notes for ALX001.
- `ailux_bd_context` — 14 strategic context rows across bd_strategy/geographic/regulatory/financing/pipeline/competitive_position. Covers: deal timing (Q4 2028 optimal window), partner ranking (J&J > Takeda), deal precedents ($42-125M preclinical range → $150-400M post-Phase 1), China vs. global options, negotiation leverage drivers, BTD opportunity.

**Dashboard changes (index.html):**
- Added "ALX001 Position" button to TL1A left pill column
- ALX001 modal now loads 4 BD strategy cards from `ailux_bd_context` on open (deal timing, partner profile, leverage drivers, China strategy)
- Knowledge Folder "Ailux Position" tab now shows dynamic BD strategy context from `ailux_bd_context` for deal timing, partner profile, and leverage

**Key research findings captured:**
- TL1A non-responders: TNFSF15 low-expression haplotype + mucosal TL1A IHC Q1-Q2; escape via IL-12/IFN-gamma, TSLP/ILC2, stromal CAF, DcR3 competition
- IL-23 non-responders: bio-exposed patients ~28% vs bio-naive ~45-50% (INSPIRE data); escape via IL-12 bypass, TSLP/ILC2, epithelial barrier defect
- Population math: TL1A 48% + IL-23 40% - ~30% overlap = ~58% bispecific ceiling (synergy could push to 65-70%)
- Dual non-responders (~42%): require JAK, TNF, or barrier-repair approaches — not addressable by bispecific

---

## 2026-05-30 (Session 95) — Competitive relevance scoring correction (database-only, no deploy)

**Problem:** Direct-overlap competitors showing as "Low" or null in drug_competitive_scores.competitive_relevance — blocking correct color-bar rendering in PI tabs and company bestRelevance sort.

**Root cause:** Rules treated Direct+Preclinical as medium and many context-specific rows had null.

**New scoring rules applied:**
- Direct + late stage (Ph2/Ph3/Approved) → very_high (score 88)
- Direct + early stage + key Ailux target (TL1A/IL-23/FcRn/CD19/BCMA/IGF-1R) → very_high (score 82)
- Direct + early stage, non-key target → high (score 72)
- Adjacent + late stage → high (score 68); Adjacent + early → medium (score 45)
- Same-Space + late → medium (score 40); Same-Space + early → low (score 22)
- Watch + discontinued → monitor (score 10); Watch all others → low (score 15–22)
- Discontinued in any overlap → low or monitor

**Results — drug_competitive_scores (311 rows):**
- very_high: 37 → 128 (+91)
- high: 46 → 28 (−18)
- medium: 103 → 14 (−89)
- low: 25 → 137 (+112, from Watch/Same-Space/discontinued)
- monitor: 14 → 4 (−10, only true discontinued Watch)
- null: 86 → 0 (−86, all filled)

**Direct-overlap rows (131 total): 128 very_high + 3 high (cnd261 CD20×CD3, apg333 TSLP — both Phase 1, non-key targets)**

**drug_area_scores: 132 rows updated for consistency (legacy field)**

**43 companies now have ≥1 very_high drug** (was ~15). Key gains: duvakitug (Sanofi, Ph3 TL1A), afimkibart (Roche, Ph3 TL1A), tulisokibart (Merck, Ph3 TL1A), hbm2001/sab06/es302 (preclinical TL1A×IL-23p19 bispecifics), ibi311 (Innovent, Approved IGF-1R corrected from low→very_high).

**No index.html changes — dashboard reads live from Supabase, auto-updated.**

---

## 2026-05-29 (Session 94) — Full enrichment audit + pipeline repair (11 commits)

**Commits:** ccf99dbf → 912e7735 (11 commits this session)

### Workflow Fixes (Agent 1)
- **Submitted Intel Auto-Review root cause:** `review_submitted_intel.py` was never committed to the repo — every run crashed immediately. Script committed (SHA ccf99dbf). Next 4-hour run will process 2 pending `status=new` submissions.
- **morning_summary.py:** Fixed 4 wrong column names against `drug_validation_results` (`result_type`→`check_status`, `rule_name`→`check_type`, `detail`→`details`, `checked_at`→`updated_at`). Script was deployed but column mismatch silently returned 0 validation rows.
- **refresh_company_verified.py:** Also missing from repo. Added before the Sunday workflow first fires (Jun 1).
- **Research pipeline timing:** Confirmed GitHub Actions queue delay — cron `0 6 * * *` consistently fires ~12h late (~17:53 UTC / 1:53 PM ET). Root cause is GitHub's peak-hour scheduler queue at 06:00 UTC. Not a config error; documented. No cron change made.
- **Weekend Sprint + Abstract Fetcher + Validation Research:** All confirmed properly configured — these fire on their first eligible day (Weekend Sprint: May 30, Abstract Fetcher: May 30, Validation Research: Jun 1).

### Enrichment Pipeline Fixes (Agent 3)

**Bug fixes (DB state before → after):**
- `drug_biomarkers.drug_id = NULL` 7/7 → 0/7 ✅ (UC→spy002, CD→afimkibart)
- `non_responder_profiles.drug_id = NULL` 4/4 → 0/4 ✅ (anti-TNF→infliximab, anti-TL1A→tulisokibart, anti-IL-23→risankizumab)
- `drug_competitive_scores NULL total_competition_score` 203/311 → 0/311 ✅ (all 12 context_ids scored)
- `area_knowledge drug_count_direct/total = NULL` 13/13 → 0/13 ✅ (TL1A=35, UC=50, IBD=52, bispecific=36, etc.)
- `enrichment_runs status='running'` 14/14 → 0/14 ✅ (all patched to 'completed'; future runs will close correctly)

**Pipeline connections added:**
- `company_enrichment.py`: dual-write new catalysts to BOTH `catalysts` AND `catalyst_calendar` going forward
- `research.py`: Phase 7 added — `process_pkpd_queue()` reads research_queue PK/PD items, fetches PubMed abstracts, writes to `drug_pk_parameters`
- `research.py`: Phase 8 added — `source_verifier.run()` wired into nightly pipeline (will populate `source_validation_log` from next run)
- `model_comparison.py`: `update_enrichment_run()` now sets `status='completed'` + `completed_at` when run finishes

**New scripts created and committed:**
- `scripts/backfill_biomarker_drug_ids.py` — links drug_biomarkers to drugs via indication
- `scripts/patch_competitive_scores_null.py` — scores 203 rows across 12 context_ids
- `scripts/update_area_knowledge_counts.py` — populates drug_count_direct/total per area slug
- `scripts/seed_strategic_views.py` — seeds company_strategic_views (54 rows, 4 view types: competitive/partnership/licensing_candidate/acquisition_target)

### Full Workflow Audit Table
| Workflow | Schedule | Script | Last Run | Status |
|---|---|---|---|---|
| Meridian Research | `0 6 * * *` (~17:53 UTC actual) | research.py | May 28 | success |
| Meridian Writer | `30 10 * * 1-6` (~19:46 UTC actual) | write_meridian.py | May 28 | success |
| Intelligence Pipeline | 6 area crons | company_enrichment.py | May 28 | success |
| Homepage News | `30 7 * * *` | fetch_homepage_news.py | May 28 | success |
| Signal Monitor | 4x/day | signal_monitor.py | May 28 | success |
| Stock Prices | `0 14 * * *` | stock_prices.py | May 28 | success |
| Submitted Intel | `0 */6 * * *` | review_submitted_intel.py | May 28 | **FIXED** |
| Morning Summary | `0 11 * * *` | morning_summary.py | first run today | **FIXED** |
| Weekend Sprint | 13 crons Sat-Sun | weekend_sprint.py | first run May 30 | OK |
| Company Freshness | `0 6 * * 0` (Sunday) | refresh_company_verified.py | first run Jun 1 | **FIXED** |
| Validation Research | `0 7 * * 0` (Sunday) | validation_research.py | first run Jun 1 | OK |
| Abstract Fetcher | `0 14 * * 6` (Saturday) | abstract_fetcher.py | first run May 30 | OK |

---

## 2026-05-29 (Session 92–93) — Research pipeline expansion, Files tab, writing standards, stage filter fix

**Commits:** b4e6ae4c (Files tab + pipeline), a3daae6c (stage filter fix)

**Deploy:** index.html fully deployed to GitHub Pages. Two commits this session.

**Stage filter bug fixed (critical):**
- `drugs.stage` uses display-case strings ("Phase 2", "Approved") not snake_case
- DKN filter lines 8815-8816 now use `_resolveStage(d)` instead of `d.stage` directly
- 13 drugs with `approved_us` / `approved_us_eu` / `bla_under_review` now correctly match the "Approved" filter
- DB fix: ALX005 lowercase `preclinical` → `Preclinical` patched

**Company Files tab (Agent 4):**
- 7th tab added to company entity modal: 📁 Files
- Loads from `company_documents` table; supports type filter (All / 8-K / Abstract / Poster / Slides / Press Release / Patent)
- 156 abstract documents seeded from Europe PMC + PubMed across 16 drugs

**Research pipeline expansion (Agents 2-3):**
- `ctgov_poller.py` — new standalone CT.gov API v2 poller (378 lines); 7 areas, 32 search terms
- `abstract_fetcher.py` — Europe PMC + PubMed abstract ingestion (310 lines); writes to `company_documents`
- `research.py` extended: Phase 6 adds CT.gov + EDGAR sweep; timeout extended 180→210 min
- GitHub Actions: `abstract-fetcher.yml` workflow added (Saturday 10 AM ET)

**CT.gov trial linkage (Agent 1):**
- `trial_link_sync.py` — links all Phase 1+ drugs to CT.gov; 120 new records, coverage 127/136 (93.4%)
- 9 Chinese programs flagged for ChiCTR (no CT.gov registration)

**Validation sprint (Agent 5):**
- 57 new `drug_competitive_scores` seeded (total 311)
- 34 partnerships missing source_url → 19 `governance_violations` written
- 23 PK/PD literature research_queue entries added
- CIDP added to `indication_patient_intelligence`

**Feedback UI (Agent 6):**
- `meridian_feedback_ui.html` recreated from scratch with correct schema
- Column fix: `field_value` → `enriched_value`; `correction_labels` schema corrected

**Meridian Issue writing standards:**
- `write_meridian.py` system prompt updated with 7 rules (no speculation, no contradictions, first-mention hyperlinks, scientific MoA precision, patient numbers required, fix errors before publishing)
- Memory: `project_meridian_writing_standards.md`

**Morning enrichment status (as of 03:40 UTC May 29):**
- GitHub Actions research pipeline (2 AM ET / 06:00 UTC) has not yet fired — runs in ~2.5 hrs
- 20 news articles collected; 20 PK/PD literature queue items (nipocalimab, dupilumab, efgartigimod, veligrotug)
- 20 governance_violations unresolved (all `codev_requires_source_url`)

---

## 2026-05-28 (Session 91) — Drug favorites, pill bar removal, About Meridian rewrite, search-as-database, birthday

**Commit:** 004d7638daef

**Meridian Birthday confirmed:** May 18, 2026 — oldest drug record (nipocalimab) created at 2026-05-18T00:36:08 UTC. "Intelligence gathering since May 18, 2026" stamp added to homepage bottom. Saved as key memory.

**Agent A — Birthday stamp:**
- Queried Supabase: oldest record = `drugs.created_at` 2026-05-18 (nipocalimab)
- Added `.hw-since` div below `#hw-breakdown` on homepage
- Memory: `project_meridian_birthday.md` saved

**Agent B — Pill bar + favorites:**
- KF chip bar REMOVED entirely (lines 4729–4744 HTML, 8368–8372 CSS)
- Removing chip bar also fixed the filter bar visibility issue (chip bar height was offsetting the sticky top)
- Drug favorites ⭐: star column added to DKN table header and every row
- Favorites stored in `localStorage['meridian_drug_favorites']`, pinned to top on every render
- `toggleDrugFav()` + `_dknSortFavoritesToTop()` functions added
- `data-drug-id` added to each `<tr>` row for stable identification

**Agent C — About Meridian + drag-drop + LEAD TARGET:**
- About Meridian panel completely rewritten: "A knowledge graph for biotech business development" — 4 prose sections (What it tracks / How it learns / What makes it useful / datestamp). Dark gradient hero, no numbered lists, no generic descriptions.
- Submit Intel: drag-and-drop zone added (`si-drop-zone`) — drop a file or click to browse. Files read via FileReader; text files auto-populate the intel textarea. Drop feedback: active state on hover.
- LEAD TARGET column: entity-link `onclick` removed from PI table cells — targets are plain text again. KF access only through search bar.

**Agent D — Search-as-database:**
- KF results: now first in search dropdown with `_KF_TAGLINES` map (all 13 slugs), icon + tagline + "Open folder →" CTA
- News results: headline = `<a href>` hyperlink direct to article; source label badges (Fierce/Endpoints/STAT/etc.); deduplication by 60% token overlap; "+N sources" expandable list; link quality indicator (🔗 vs ⚠)
- Patient intelligence: `indication_patient_intelligence` table queried on indication search terms — results appear second in dropdown (after KFs)
- `_gsSourceLabel()` + `_gsDedupeNews()` + `_gsShowSources()` functions added

**v21 Excel built:**
- 7 sheets: Action Tracker (58 items P0-P3), Session Log (38 sessions), Schema Status (32 tables), Ailux Pipeline, Dashboard Features Audit, Kyle Requests Status, Governance Rules
- P0 critical items surfaced: v62_agent_validation_tables.sql needs manual apply; entity_edges RLS; research.py timeout issue

---

## 2026-05-28 (Session 90) — Major overhaul: Ailux pipeline rename, filter system, entity click-through, saved views

**Commit:** 9967214f5c8a

**Agent 1 — Ailux pipeline + memory:**
- ACE name retired. ALX002 is the official name (CD19 × BCMA TCE, B cell-driven I&I, IND by 2027)
- Supabase: XPF005 → ALX001, ALX-FcRn → ALX005, ALX002 row created
- `ailux_positions` table updated to reference ALX001 and ALX005
- 7 memory files updated (ACE/XPF005 references removed)
- New memory: `project_ailux_pipeline.md` — full ALX001/002/005 pipeline table
- MEMORY.md updated with pipeline pointer

**Agent 2 — Submit Intel + Add Doc merge:**
- Single "Submit Intel" button replaces two separate buttons
- Paperclip icon (📎) on the button opens file attachment directly
- Modal gains: file attach zone, auto-extraction of drug codes/company names/dollar amounts from text files
- "Questions for Kyle" section appears when gaps are detected in submitted doc
- `detected_fields` and `attached_file` included in Supabase intel payload

**Agent 3 — Filter system redesign:**
- Old chip-based filter bar → thin pill-shaped `<select>` dropdowns in one row
- Groups: [Ther. Area | Indication | Target] · [Modality | Stage] · [Company]
- Cascading TA → Indication: selecting Immunology hides irrelevant indications
- Indication dropdown now has real indications: UC, CD, RA, PsA, SLE, TED, Graves, CIDP, etc.
- `DKN_TARGET_MAP` rewritten as keyword-set arrays — TL1A filter no longer pulls unrelated IL-23 drugs
- `dknSetTaDrop()` + `dknSetTargetDrop()` functions added

**Agent 4 — Row fixes + display labels:**
- Relevance bar: now ALL rows have a colored left border (default grey if no relevance data)
- Colors: Very High = indigo, High = green, Medium = amber, Low = slate, null = light grey
- Top stats block (4 numbers) removed — single "Tracking N · next readout in X days" line remains
- ACE display labels updated throughout: `TAB_PORTFOLIO_LABELS`, `IIF_AREA_LABELS`, intel panel prose, first-pass guide
- XPF005 → ALX001 at line 29042

**Agent 5 — Right panel cleanup + Saved Views:**
- 7 right-side pill panels removed across all area tabs (Biology Deep Dive, SoC, Ailux Profile, TED History, Estimand Guide)
- `[id$='-pills-right'] { display:none !important }` guard added
- Saved Views feature: 🔖 bookmark button in header
- Opens slide-over panel listing saved dashboard configurations
- `saveCurrentView()` → prompts for name → saves tab + all filter states to localStorage
- `loadSavedView(id)` → restores tab + filters
- `deleteSavedView(id)` → removes from localStorage

**Agent 6 — Indication KFs + click-through:**
- 5 new indication rows in `area_knowledge` Supabase table: CD, RA, Graves, gMG, CIDP
- KF chip bar expanded to 13 chips (added CD, Graves, gMG, CIDP, RA)
- Indication search results now route to Knowledge Folder panel
- LEAD TARGET column: all target text is now an `entity-link` → clicking opens target's KF
- Drug dossier modal: Target + Indication fields are now clickable → open KF
- `openKFFromTarget(str)` + `openKFFromIndication(str)` functions added
- `.entity-link` CSS: dotted underline, turns indigo on hover

---

## 2026-05-28 (Session 89) — Dashboard v2: Card redesign, Discovery Queue, enhanced search, About panel

**Commit:** e462e80a51da

**Agent 2 — Card redesign + progressive disclosure:**
- `buildStockCard` extended with 3 new chips on card face: BD Signal badge (Hot/Active/Monitor/Quiet mapped from bdMomentum), Next Catalyst chip (days until readout from `catalyst_calendar`), Confidence Tier chip (Verified/Model/Inferred from `company_profiles.confidence_tier`)
- `loadStockCards` now fetches `catalyst_calendar` (next 180 days) and `confidence_tier` in parallel with existing card data
- `openCompanyEntityModal` now fetches `drug_validation_results` + `field_change_audit` for each company
- New **Data Quality tab** in company entity modal: validation issues per drug (color-coded pass/warn/fail) + recent field change log (old→new with strikethrough)
- New CSS: `.sc-bd-badge`, `.sc-cat-chip`, `.sc-conf-chip`, `.cem-dq-row`, `.cem-audit-row`

**Agent 3 — Discovery Queue + search:**
- `dq-nav-badge` activated (was `display:none`) — now shows live count of `research_queue WHERE status='pending'`
- `#dq-nav-count` span added inside badge for live number
- `openDQPanel()` / `closeDQPanel()` — slide-over panel showing pending research items grouped by P0/P1/P2/P3 priority with entity name, gap type, age
- `openAboutDataPanel()` — "About This Data" slide-over explaining the 3 data intake paths in plain language
- ℹ️ info button added to header next to DQ badge
- `_gsSbSearch()` enhanced: now also queries `indications` table by name/synonyms + matches Knowledge Folder slugs; results show new "Knowledge Folders" and "Disease Areas" sections; clicking a KF result calls `openKnowledgeFolder(slug)`
- New CSS: `.dqp-overlay`, `.dqp-panel`, `.dqp-group-hd`, `.dqp-badge` (P0-P3 variants), `.atd-overlay`, `.atd-panel`, `.meridian-info-btn`

**Supabase tables newly surfaced:**
- `catalyst_calendar` → card face next catalyst chip
- `drug_validation_results` → Data Quality modal tab
- `field_change_audit` → Data Quality modal tab (change log)
- `research_queue` → DQ badge count + Discovery Queue panel
- `indications` → enhanced global search

---

## 2026-05-27 (Session 88) — Ontology Stabilization Audit: observability panel + shutdown checklist + stale comment cleanup

**Purpose:** Operational maturity pass — no migrations, no new tables. Finalize session 88 mandate: wire live health diagnostics, document legacy shutdown sequences, clean stale comments, produce stabilization report.

**index.html changes:**
- Added `loadOntologyHealth()` function (~line 3504): queries all 9 operational tables for `target_id` coverage, fallback context inventory, legacy structure row counts; builds coverage table + summary panel
- Added `ont-sec-health` HTML panel to Ontology Audit tab: Ontology Health — Live Diagnostics section with Refresh button
- Wired `loadOntologyHealth()` to TAB_REGISTRY `onEnter` for 'ontology' tab (line 26489): auto-fires on tab open
- Replaced 4 stale comments "pending DB FK teardown" → "DB teardown complete Session 84" (disease_areas was dropped Session 84)

**New docs:**
- `docs/ontology_legacy_shutdown_checklist.md` — kill conditions, blocker dependencies, safe retirement sequences for drug_area_scores (gate 2026-06-27), drug_areas (Phase 5 activations), area_id fallback columns
- `docs/ontology_stabilization_report.md` — full architecture map (5 layers), coverage data, observability infrastructure, outstanding items, session verdict

---

---
## 2026-05-27 (Session 87) — Ontology Acceleration Sprint: batch Group D migration (commit 5cc73e3edd)

**Purpose:** Batch-migrate all 5 remaining Group D operational tables (`research_queue`, `competitive_signals`, `company_profiles`, `discovery_queue`, `signals`) to ontology-native dual-filter routing. Completes the Group D wave started in Session 86.

**SQL (Supabase) — 5 tables, identical pattern:**
- `ALTER TABLE {table} ADD COLUMN target_id text, indication_id text, therapeutic_area_id text, context_type text` × 5
- `UPDATE {table} SET target_id = lam.target_id, ... FROM legacy_area_ontology_map WHERE area_id = legacy_area_id` × 5

**Backfill results:**
- `research_queue`: 60/60 rows updated — tcell→null/platform_view, 5 target contexts mapped
- `competitive_signals`: 252/252 rows updated — same pattern
- `company_profiles`: 137/137 rows updated — 11 area_ids (5 target + 2 indication + 3 strategic/platform view)
- `discovery_queue`: 64/64 rows updated — same as research_queue pattern
- `signals`: 0/63 rows updated — area_id was never populated; columns added for schema consistency

**Code changes (10) in index.html:**
- Line 3509–3510: `research_queue` select expand + dual-filter `.or('target_id.in.(...),area_id.in.(...)')`
- Lines 10514–10515, 14242–14243: `competitive_signals` company modal + card — dual-filter with `company_id` AND `target_id/area_id`
- Line 17238: `competitive_signals` bulk select expansion (added `target_id,context_type`)
- Lines 10472–10473, 10493–10494, 14103–14104: `company_profiles` 3 filter reads — dual-filter
- Line 9541: `discovery_queue` client-side JS filter — `r.area_id !== areaF && r.target_id !== areaF`
- Line 13279: `discovery_queue` Morning Report select — added `target_id`
- Line 3731: `signals` client-side JS filter — `r.area_id === _sigAreaFilter || r.target_id === _sigAreaFilter`

**Validation — zero console errors:**
- `research_queue` dual-filter: tl1a→ontology path ✅, tcell→area_id fallback ✅
- `company_profiles` dual-filter: fcrn→ontology path ✅, tcell→area_id fallback ✅
- `discovery_queue`: 64 rows loaded, tl1a→target_id='tl1a' ✅, tcell→null ✅
- `signals`: 57 rows loaded, all area_id/target_id null (expected — never populated)
- `competitive_signals`: RLS restricts anon reads (pre-existing, not a regression)

**Output doc:** `docs/ontology_acceleration_sprint_report.md`

---

---
## 2026-05-27 (Session 86) — intel_areas ontology migration (commit 9635495a3f)

**Purpose:** Migrate `intel_areas` from legacy `area_id`-only routing to ontology-native routing. First migration in the Group D operational tables wave.

**SQL (Supabase):**
1. `ALTER TABLE intel_areas ADD COLUMN target_id text, indication_id text, therapeutic_area_id text, context_type text`
2. `UPDATE intel_areas SET target_id = lam.target_id, ... FROM legacy_area_ontology_map WHERE area_id = legacy_area_id` → **18/18 rows updated**

**Backfill result:** fcrn→target_id='fcrn', igf1r→'igf1r', il4ra→'il4ra', tslp→'tslp', tcell→null (platform_view — area_id fallback)

**Code changes (6) in index.html:**
- Lines 3145, 17235, 17615: Added `target_id,context_type` to bulk select strings
- Line 3847: Flipped critical `loadAreaIntel` filter from `.in('area_id', areas)` → `.or('target_id.in.(...),area_id.in.(...)')` dual-filter
- Line 18015: Flipped TL1AIntelFeed from `.eq('area_id','tl1a')` → `.or(...)` dual-filter
- Line 18412: Added `target_id` to search embedded sub-select `intel_areas(area_id,target_id)`

**Validation — all 4 intel-bearing tabs passing, zero console errors:**
- FcRn: 3 items via ontology path (target_id='fcrn') ✅
- IGF-1R×TSHR: 6 items via ontology path ✅
- IL-4Rα×TSLP: 6 items via ontology path (il4ra+tslp) ✅
- ACE/tcell: 3 items via area_id fallback (target_id=null — platform_view) ✅

**Pattern established** for Group D wave: same 4-step sequence applies to research_queue, competitive_signals, company_profiles, signals.

**Output doc:** `docs/intel_areas_ontology_migration.md`

---
## 2026-05-27 (Session 85) — Post-retirement ontology integrity audit (analysis only, no code/DB changes)

**Purpose:** Confirm `disease_areas` removal left no hidden schema, code, or ontology inconsistencies. Produce prioritized migration queue for remaining legacy area structures.

**Schema audit:** 27 tables have `area_id` columns. All classified. No orphaned reads, no broken joins.

**Code audit:** 25 `disease_areas` references remain in `index.html` — all static HTML or stale comments (say "pending DB FK teardown"; teardown is now done). Zero live DB reads on `disease_areas`. All live `area_id` reads target tables that exist with data.

**Ontology bridge:** `legacy_area_ontology_map` intact — all 11/11 legacy contexts mapped. All child table data confirmed intact after CASCADE drop.

**Key findings:**
- Tables already Phase 3-migrated (dual-filter complete): catalysts, company_areas, deals, mechanism_status, target_areas
- Legacy tables pending retirement: drug_areas (Phase 5 activation blocker), drug_area_scores (harness decommission gate 2026-06-27)
- Not-yet-migrated Group D tables: intel_areas (18 rows), research_queue (60 rows), competitive_signals (252 rows), company_profiles (137 rows), discovery_queue (64 rows), signals (63 rows)
- 9 stale comments in index.html say "pending DB FK teardown" — cosmetic, non-blocking

**Prioritized migration list:** P1 drug_area_scores → P2 drug_areas → P3 intel_areas → P4 research_queue → P5 competitive_signals → P6 company_profiles → P7 discovery_queue

**No code changed. No DB touched.**

**Output doc:** `docs/post_disease_areas_integrity_audit.md`

---
## 2026-05-27 (Session 84) — disease_areas DB retirement complete (no code commit — DB-only)

**Purpose:** Drop `disease_areas` from Supabase now that all code reads were cleaned in Session 80.

**Pre-flight:** `grep -n "from('disease_areas')" index.html` → CLEAN. Dashboard loads correctly at `?v=84`.

**FK discovery:** Retirement doc anticipated 3 FK constraints; actual count was **13**. All 13 are legacy `area_id` FKs on child tables (drug_areas, company_areas, deals, catalysts, company_partnerships, ailux_positions, etc.) — superseded by Phase 3 ontology columns but never cleaned up at DB level. Dropping FK constraints removes referential integrity only; no data affected.

**SQL executed:**
```sql
DROP TABLE public.disease_areas CASCADE;
```
Single statement; `CASCADE` removes all 13 FK constraints automatically.

**Verification:** `table_exists = false`, `remaining_fks = 0` — confirmed via Supabase Management API.

**Dashboard validation — all tabs + OEX, zero console errors:**
- TL1A: 24 entities, 5 badges, 6 borders ✅
- FcRn: 5 entities, 4 badges, 4 borders ✅
- IL-4Rα×TSLP: 11 entities, 9 badges, 9 borders ✅
- IGF-1R×TSHR: 13 entities, 8 badges, 8 borders ✅
- OEX: 100 tree nodes, 72 matrix cells, renders correctly ✅

**No code change.** No deploy needed. Dashboard commit remains `2c889eda61e3`.

**Output doc:** `docs/disease_areas_db_retirement_execution.md`

---
## 2026-05-27 (Session 83) — competitive_relevance + relevance_rationale restored in DCS (commit 2c889eda61e3)

**Purpose:** Execute Option C (hybrid migration) from Session 81 decision memo — restore the strategic relevance layer that went dark when `_makeAreaPI` was switched to DCS reads in Session 78.

**SQL executed (Supabase SQL Editor):**

1. `ALTER TABLE public.drug_competitive_scores ADD COLUMN IF NOT EXISTS competitive_relevance text CHECK (competitive_relevance IN ('very_high','high','medium','low','monitor')), ADD COLUMN IF NOT EXISTS relevance_rationale text;`

2. `UPDATE public.drug_competitive_scores dcs SET competitive_relevance = das.competitive_relevance, relevance_rationale = das.relevance_rationale FROM public.drug_area_scores das WHERE dcs.drug_id = das.drug_id AND dcs.context_id = das.area_id AND das.competitive_relevance IS NOT NULL;` → **166 rows backfilled** (87 DCS-only rows remain null — newer drugs not in DAS, expected)

**Code change:** `_makeAreaPI` DCS select (line ~13614) — added `competitive_relevance,relevance_rationale` to select string. Two other DCS selects (drug card modal, lines ~12623/~12697) intentionally left unchanged.

**UI validation — all 4 tabs passing, zero console errors:**
- TL1A: 24 entities, 5 badges, 5 colored borders (high×4, medium×1)
- FcRn: 5 entities, 4 badges, 4 borders (very_high×2, medium×1, monitor×1)
- IGF-1R×TSHR: 13 entities, 8 badges, 8 borders (very_high×2, high×1, medium×2, low×2, monitor×1)
- IL-4Rα×TSLP: 11 entities, 9 badges, 9 borders (very_high×3, high×2, medium×1, low×3)

**competitive_relevance distribution after backfill:** medium:56, high:44, very_high:27, low:25, monitor:14 (total 166)

**28 curated rationales confirmed transferred** — batoclimab, crn12755, yb-101, teprotumumab, sp-1351 verified.

**Remaining DAS retirement blockers:**
1. Five dual-read harnesses (`_runPhase4BDualRead` et al.) still active — need 30+ days clean matching logs before decommission
2. 87 DCS-only rows have `competitive_relevance = null` — will fill naturally via enrichment pipeline, not a blocker

**Output doc:** `docs/drug_area_scores_option_c_execution.md`

---
## 2026-05-27 (Session 82) — Partner pill co-dev inversion + erd-1 data fix (commit 7c6315305b)

**Purpose:** Complete partner pill fixes left over from Session 79 — erd-1 (HXN-1003) missing pill and itepekimab showing wrong partner on Sanofi's card.

**Root causes found and fixed:**

1. **erd-1 / HXN-1003 missing "w/ Earendil" pill** — Data bug: `drugs.partner_company = "Sanofi"` on erd-1 (set from Regeneron's POV). `_partnerCo` chain hit this first, self-attribution guard (Sanofi = Sanofi) killed the pill before reaching `display_partner_name = "Earendil"`. Fix: cleared `partner_company` to null via Supabase PATCH. Now falls through to `display_partner_name = "Earendil"`. No code change needed.

2. **itepekimab showing no "w/ Regeneron" on Sanofi's card** — Co-dev inversion problem. `partner_company = "Sanofi"` (correct from Regeneron's POV), but self-attribution guard fires when viewing Sanofi's card. Previously no fallback existed. Code fix: added co-dev inversion logic in `_genericDetailHTML` — when self-attribution suppresses `partner_company` AND `d.company_id ≠ prog.company_id`, derive the alternative pill from `d.entity_name` (the drug's originator). For itepekimab: `entity_name = "Regeneron"` → shows "w/ Regeneron" on Sanofi's card; guard confirms "Regeneron" ≠ "Sanofi" so no suppression.

**Verified safe for existing correct cases:**
- Duvakitug "w/ Teva" on Sanofi: `company_id = "sanofi"` = `prog.company_id` → inversion condition false → no change ✓
- HXN-1002 "w/ Earendil": `partner_company = null` → no self-attribution → no change ✓
- Itepekimab "w/ Sanofi" on Regeneron: `_partnerCo = "Sanofi"` ≠ "Regeneron" entity → guard doesn't fire → shows ✓

**Code change location:** `_genericDetailHTML` in index.html, after `_partnerMatchesEntity` computation.

---
## 2026-05-27 (Session 81) — drug_area_scores decision memo (analysis only, no code written)

**Purpose:** Produce a product/ontology decision memo for `drug_area_scores` retirement path before any code is touched.

**Key finding:** `competitive_relevance` and `relevance_rationale` are the only substantive fields in DAS that were not migrated to `drug_competitive_scores`. Both are currently dead in the UI — the `_makeAreaPI` DCS select doesn't fetch them, so all relevance badges, entity row borders, and strategic sort are no-ops in production. The feature is fully designed and coded in the UI; it just needs these two columns added to DCS.

**Recommendation: Option C — Hybrid.** Add `competitive_relevance` + `relevance_rationale` to `drug_competitive_scores`, backfill 166 rows from DAS, add two field names to the DCS select in `_makeAreaPI`. Two SQL statements + one line of code change. Full feature comes back to life.

**Not recommended: Option B (deprecate).** The 28 curated rationales are high-quality strategic intelligence. The UI infrastructure is complete. Deprecating removes meaningful signal permanently.

**Output:** `docs/drug_area_scores_decision_memo.md` — full field-by-field comparison, 10-question analysis, backfill SQL, and execution plan.

**No code changed. No table modified.**

---
## 2026-05-27 (Session 80) — disease_areas code retirement complete (commit fba9f390cc53)

**P0: disease_areas active DB reads removed (8 changes):**
- `OEX_ALL_TABLES` — removed `'disease_areas'` from schema explorer table array
- `ALL_TABLES` homepage row-count poller — removed `'disease_areas'` from 60s poll array
- Admin row-count fetch (line ~24939) — replaced `_sb.from('disease_areas').select('*')` with `Promise.resolve({ data: [] })` stub
- `_loadOntologyExplorer` (line ~26388) — replaced `_sb.from('disease_areas').select('id,label,...')` with `Promise.resolve({ data: [] })` stub
- `OEX_JOIN_MAP` (primary + fallback copies) — removed `disease_areas` key; set mechanism_status/competitive_landscapes/area_metadata to `[]`
- `OEX_FK_MAP` — removed all `disease_areas:'area_id'` entries from all child-table FK definitions
- `SEED_CAT_DATA` — removed disease_areas entry from ontology tables catalog list

**Final grep result:** `grep -n "from('disease_areas')" index.html` → CLEAN (zero hits)

**OEX validation:** Matrix renders correctly — TL1A 94%, IBD 96%. Ontology group now shows 5 tables (was 6). Zero console errors.

**Retirement doc written:** `docs/disease_areas_retirement_ready.md` — full checklist of cleaned code, remaining FK constraints, and drop sequence.

**Not done (intentional):** Table not dropped. FK constraints not touched. `drug_area_scores`, dual-read harnesses, `drug_areas`, `area_metadata` all untouched per session scope.

---
## 2026-05-27 (Session 79) — Phase 3 dual-filter (catalysts/deals) + Phase 4 area_metadata update (commit 2749f90d9974)

**Phase 3A — catalysts ontology columns**: Added `target_id`, `indication_id`, `therapeutic_area_id` to `catalysts` table via Supabase SQL Editor. Backfilled from `legacy_area_ontology_map` — all 8 active areas populated. `indication_id` intentionally null for group-level areas (ibd, atopy, autoimmune, respiratory, tcell) since those don't map 1:1 to an indication row.

**Phase 3B — company_areas ontology columns**: Added `therapeutic_area_id`, `target_id`, `context_type` to `company_areas` (134 rows). Backfilled from `legacy_area_ontology_map`. Validation confirmed all 134 rows mapped cleanly.

**Phase 3B — deals ontology columns**: Added `target_id`, `therapeutic_area_id` to `deals` (190 non-null area_id rows). Backfilled from `legacy_area_ontology_map`. Biological/indication-type areas intentionally left null for `target_id`.

**Phase 3 code flip — dual-filter pattern**: 4 production reads in `index.html` updated to use `.or('target_id.in.(...),area_id.in.(...)')` dual-filter instead of `.in('area_id', areas)`:
- `loadAreaCatalysts` (line ~3891)
- `loadAreaDeals` (line ~3926)
- `loadAreaBDActivity` (line ~3968)
- `_loadBdIntoModal` (line ~13433)

All four now pick up rows via the new `target_id` column OR the legacy `area_id` column — forward-compatible without breaking existing data.

**Phase 4 — disease_areas dependency audit**: Confirmed zero active production reads on `disease_areas`. Only remaining reference is an admin stats counter (non-blocking). Table is retirement-ready pending final grep + runtime validation session.

**Phase 4 — area_metadata lifecycle updates**: 
- `tl1a` and `ibd`: `legacy_retained` → `flag_activated` (Phase 2 flip complete Session 78, now fully on drug_competitive_scores)
- All 8 active areas: notes appended documenting Phase 3 completion (2026-05-27)
- `il4ra`, `ted`, `tslp`: remain `legacy_retained` — biological drug reads still on drug_area_scores pending their own Phase 2 flip
- `autoimmune`, `respiratory`, `tcell`: remain `not_started` — preserved strategic/platform views, not targeted for retirement

**legacy_area_ontology_map**: Created and seeded with 11 rows (all legacy area_ids mapped to therapeutic_area_id, target_id, indication_ids, context_type). This table is the backbone of all Phase 3 backfills.

---
## 2026-05-27 (Session 78) — Phase 2 code flip: drug_area_scores → drug_competitive_scores for scoreRows + OEX matrix (commit 23736d8f5e94)

**Phase 2 code flip (scoreRows)**: The main area tab parallel fetch (line ~13595 in `_makeAreaPI`) now reads `drug_competitive_scores` instead of `drug_area_scores`. Key changes:
- `area_id` → `context_id` throughout
- Column set updated: removed `vs_ailux_positioning`, `competitive_relevance`, `relevance_rationale` (don't exist in DCS); added `vs_ailux`, `confidence_level`
- IBD expansion: when `this.areaIds` includes `'ibd'`, `context_id` filter expands to `['ibd','uc','cd']` to capture both legacy-backfilled rows and indication-based enriched rows
- `score?.vs_ailux_positioning` → `score?.vs_ailux` in the drug data-builder (line ~13676)
- `competitive_relevance` / `relevance_rationale` gracefully null since DCS doesn't carry those fields

**Phase 2 code flip (OEX matrix)**: `oexLoadMatrix` (line ~22834) now reads `drug_competitive_scores` instead of `drug_area_scores` for area→drug membership. Added remapping: `context_id∈{uc,cd} → byArea['ibd']` so the OEX area matrix still groups IBD drugs under the 'ibd' area key.

**TL1A dual-read harness self-fetch**: Added fallback self-fetch to `_runPhase4BTL1ADualRead` (mirrors existing pattern in IBD/TED/Atopy/FCRN harnesses). After the scoreRows flip, `legacyScoreRows` no longer contains `area_id` field, so the harness filter always returned empty. Fallback fetches directly from `drug_area_scores` to keep comparison metrics valid.

**What didn't change**: The four `_runPhase4B*DualRead` comparison harnesses for IBD, TED, Atopy, and FCRN intentionally still read `drug_area_scores` as their "legacy set" — these are validation tools, not production reads. Drug card primary fetch was already on `drug_competitive_scores` (completed Session 64).

---
## 2026-05-27 (Session 77) — OEX matrix FK fix, symmetric adjacency matrix, Quick View → new ontology (commit 9c1328cbb873)

**OEX matrix FK bug fixed**: Replaced flat `OEX_FK_COL[table]` with context-aware `OEX_FK_MAP[childTable][parentTable]`. The old map returned one FK per table regardless of which parent was being measured (e.g., `drug_area_scores` only had `drug_id`, so the `area_id` relationship to `disease_areas` always showed 0%). The new two-level map correctly routes: `drug_area_scores×drugs → drug_id`, `drug_area_scores×disease_areas → area_id` (reverse path), etc. Added forward/reverse FK path detection in `_oexTableStrength`.

**Symmetric adjacency matrix**: When rows and cols contain the same items (the typical checkbox case), columns are now sorted to match the row order so item N always appears at row N and column N. Uses `displayCols = sameItems ? sorted : cols`. Matrix cells pre-load over the union of rows+cols.

**OEX Quick View → new ontology**: `oexLoadTree` now reads from `therapeutic_areas → indications → drug_indications` (same source as Navigator) instead of the old `disease_areas + drug_area_scores` pipeline buckets. Disease Areas section renamed to Therapeutic Areas with nested TA → Indication hierarchy, colors from `therapeutic_areas.color`. Target-based items (TL1A, FcRn, etc.) correctly show under Molecular Targets only. `oexInitCatalog` updated to read `indications` not `disease_areas`.

**OEX_JOIN_MAP updated**: Now accurately reflects actual schema FK relationships. `drugs` lists all 10+ child tables. Old `disease_areas` entries for `company_areas`, `catalysts`, `deals` trimmed since those relationships are now implicit via the drug/company anchor.

**Old table audit**: `disease_areas` has 11 rows (column is `label` not `name` — prior queries were broken). `drug_area_scores` (212 rows) and `drug_competitive_scores` (234 rows) both active. Neither retirable: `disease_areas` still used as FK parent by multiple tables; `drug_area_scores` retirement blocked by Phase 5.5 per roadmap.

---
## 2026-05-27 (Session 76) — OEX fixes: clearGlobalSearch, News column, CPM, Navigator DA hierarchy, homepage layout (commits 6e96d255, 4adf73ca, bb9726ae)

**Root cause of OEX blank**: `clearGlobalSearch()` in `switchTab` was calling Grid.js `forceRender()` on unrendered grids, throwing synchronously before `onEnter` ever fired. Fixed with `try { clearGlobalSearch(); } catch(e) {}` at line 16333.

**Navigator double-TA bug** ("Respiratory > Respiratory > Asthma"): DA nodes were using `name: ta.name` (the TA name) instead of a disease-area label. Fixed by adding `_HIER_DA_LABEL` constant mapping disease_area keys to readable labels ("IBD", "Airway Diseases", etc.) and grouping indications by `ind.disease_area` field before building DA nodes.

**Homepage layout**: breakdown numbers now pinned to `position:absolute; bottom:40px` via `#hw-breakdown` CSS; date/time centers naturally above it.

**RLS policies**: Ran `CREATE POLICY "anon_select"` for 6 tables that were blocking anon reads: entity_edges, drug_targets, drug_indications, ailux_positions, competitive_landscapes, therapeutic_areas. All now return correct row counts.

**OEX News column = 0%**: Two-part bug. (1) Original query only selected `matched_drug_ids` — fixed to also select `matched_area_ids` and expand area tags to all drug IDs in that area via `byArea`. (2) Browser cache was serving old JS — news fix was deployed in `4adf73ca` but browser served cached version until hard reload / `?nocache=1`. After fresh load: IGF-1R 100%, FcRn 100%, T-Cell 100%, TED 77%, Autoimmune 68%.

**CPM blank on first load**: (1) ResizeObserver stored as local `var ro` → GC'd before firing. Fixed by saving to `canvas._cpmRO`. (2) Canvas width = 0 when tab still transitioning — added 150ms setTimeout fallback for `buildCanvas`. (3) `onEnter` timing: wrapped `oexRender` in `setTimeout(oexRender, 80)`.

---
## 2026-05-27 (Session 67) — Task #31 + #32: Submit Intel traceability + Ventyx/AbbVie ownership chain (commit a333451)

**Task #32 — Ventyx/AbbVie Ownership Chain UI (two fixes):**

Fix A — Company card acquired subsidiaries banner:
- `_cemCompanyBody`: added `_acquiredSubs` filter from `sbSubs` (already fetched via parallel query)
- Renders a green banner above stats if any acquired subsidiaries exist: clickable pill per subsidiary with red "ACQUIRED" badge
- Clicking pill opens the subsidiary's company card via `openCompanySlideOver`

Fix B — Drug card ownership chain:
- `openDrugEntityModal`: added async fetch for `current_owner_company_id` when it differs from `company_id`
- Populates `ownerData = { ownerName, ownerCompanyId, originatorName, originatorCompanyId }`
- `_cemDrugBody`: new optional 10th param `ownerData`; renders blue banner above drug stats showing "Current owner: AbbVie · originator: Ventyx Biosciences" with clickable company links
- Defensive: banner only shows when `current_owner_company_id` is set and differs from `company_id`

**Task #31 — Submit Intel Traceability Panel:**
- Added 7th column header (empty, for chevron) to `si-table`
- Updated `siRender()`: each row now has a "▶ Details" / "▼ Details" chevron in column 7
- `siToggleDetail()`: now also toggles chevron text between ▶ and ▼
- Detail panel enhanced with four new sections:
  1. Status timeline: Submitted → Processed → Published/Rejected dots+line with timestamps; green=done, red=rejected, grey=pending
  2. Matched entity pills: `matched_company_ids` → clickable company pills (openCompanySlideOver); `matched_drug_ids` → clickable drug pills (openDrugEntityModal)
  3. Source display: truncated clickable link (80 char max)
  4. Rejection reason: red banner shown only if `status='rejected'` and `rejection_reason` field present
- All new fields are defensive (`if (r.matched_company_ids)` pattern) — UI works even if schema columns are missing

---
## 2026-05-27 (Session 66) — Co-development drug attribution schema + pipeline card fix (commit 57e928a)

**Schema: v35_codev_attribution — new fields on drugs table:**
- Added `lead_company_id TEXT` — company sponsoring pivotal trial / holding primary commercial rights
- Added `co_developer_ids TEXT[]` — array of all companies with active co-dev agreements
- GIN index on `co_developer_ids` for fast PostgREST array-contains queries
- Index on `lead_company_id` for fast equality lookups

**Data: populated 6 co-developed drugs from company_partnerships:**
- `ro7837195` (RO7837195): Roche + Pfizer co-dev; lead=roche
- `dupilumab`: Sanofi + Regeneron co-dev; lead=sanofi
- `itepekimab`: Regeneron + Sanofi co-dev; lead=regeneron
- `tezepelumab`: Amgen + AstraZeneca co-dev; lead=amgen
- `duvakitug`: Sanofi + Teva co-dev; lead=sanofi
- `rademikibart--cbp-201`: ConnectBioPharma + Simcere co-dev; lead=connectbiopharma

**index.html — pipeline card query fixes (6 changes):**
- `openCompanySlideOver` idsToFetch: now OR-includes `lead_company_id.eq.${companyId}` + `co_developer_ids.cs.{companyId}`
- Drug filter loop: marks co-dev assets with `_is_codev = true`, `_codev_originator = company_id`
- Pipeline drugItems HTML: adds purple **CO-DEV** badge when `_is_codev` is true
- Entity dossier within PI tab (idsToFetch2): same co-dev OR logic + marks `_is_codev`
- Simple entity modal drug query: updated from `.eq('company_id', id)` to `.or(company_id/lead_company_id/co_developer_ids)`

**Docs:**
- `docs/governance_codev_attribution.md` — permanent governance rule doc
- `scripts/migrations/v35_codev_attribution.sql` — idempotent migration SQL

**Governance rule:**
- `drugs.company_id` = originator, NEVER changes
- `drugs.lead_company_id` = lead developer (mutable)
- `drugs.co_developer_ids[]` = all co-devs (mutable, synced from company_partnerships)
- Drug appears in pipeline card if company matches any of the three fields

## 2026-05-27 (Session 75) — Fix OEX matrix checkboxes: embedded at render time (commit dccc8a4)

**Root cause identified**: `oexInjectTreeButtons` tried to match rendered tree items via `OEX_LABEL_MAP` (built from async `OEX_CAT`). The tree is built from its own independent Supabase queries — the two data sources never reliably matched, so checkboxes were never correctly injected.

**Fix — checkboxes embedded in `oexLoadTree` at render time:**
- `bioSections` array: added `type` field per section (`areas`/`targets`/`stages`/`companies`) + `id` field per child (area slug, target_id, stage string, company.id)
- Each `.oex-tv` leaf now has `data-type`, `data-id`, `data-label` attributes inline in the HTML string
- Each leaf has `<span class="oex-leaf-chks" onclick="event.stopPropagation()"><input type="checkbox" class="oex-node-chk">` embedded at render time
- Database table `.oex-tv` rows get the same treatment (`data-type="tables"`)
- Change event listener wired on `tree` element after `innerHTML` set (guarded by `tree.dataset.chkWired` so it fires once even across polling re-renders)
- `oexInjectTreeButtons`: now a no-op (calls `oexRefreshChks()` + returns)
- `oexRefreshChks`: simplified to directly set `.checked` on `.oex-node-chk` inputs by matching against `OEX_MS.rows`
- Empty-state message updated: "Check items in the sidebar to add them to the matrix"

## 2026-05-27 (Session 74c) — CPM type labels per row (commit e870933)

**CPM — ontological type subtext added:**
- `AREA_META`: added `type` field to all 11 entries — `TARGET` (tl1a/igf1r/fcrn/il4ra/tslp), `INDICATION` (ibd/atopy/ted), `PLATFORM` (tcell), `AREA` (respiratory/autoimmune)
- `draw()`: main label y-offset shifted from `rowMidY+5` → `rowMidY+1`; type subtext rendered at `rowMidY+13` in 8px/500-weight Inter, color `#3a5a7a`
- Each row now shows label (colored) + type tag (muted) so TARGET vs INDICATION is immediately visible

## 2026-05-27 (Session 74b) — Remove total count, fix checkbox stopPropagation (commit 8368c7c)

**OEX — checkbox click-through fix:**
- Added `chks.addEventListener('click', function(e){e.stopPropagation();})` to both injection sites (`oexInjectTreeButtons` and `_oexInjectDbTableCheckboxes`)
- Checkbox clicks no longer bubble to parent `.oex-tv` tree item handler (which was expanding the subtree instead of toggling the matrix node)

**Homepage:**
- Removed `#hw-count-num` and `#hw-count-label` divs entirely — the large animated total count is gone; the breakdown strip (Drugs, Companies, Trials, etc.) remains live

## 2026-05-27 (Session 74) — Single checkbox, CPM dot column, subtitle removal (commit 320a07f)

**OEX — checkbox system simplified to single-axis:**
- `_oexChkHtml`: replaced two R/C checkboxes with one `oex-node-chk` checkbox per node
- `oexToggleNode`: new `'both'` axis — checking an item adds it to BOTH `OEX_MS.rows` and `OEX_MS.cols` simultaneously; unchecking removes from both. Symmetric NxN matrix from any N checked items.
- `_oexSetGroupAll`: "All" group checkbox now adds/removes to both axes (no more separate R/C group buttons)
- Group header: collapsed to single "All" checkbox per section (was "All R" + "All C")
- `oexRefreshChks`: syncs group checkbox state against rows only (rows/cols always mirror each other)
- Matrix populate fix: any 1+ checked item now guarantees both axes populated → matrix always renders

**CPM — dots aligned to fixed column:**
- Added `maxLW` pre-computation at start of `draw()` (measures all area labels once)
- `DOT_X = LEFT_MARGIN - 14 - maxLW - 14` — single constant x for all dots
- All dots now land in a perfect vertical column regardless of label width variation

**Homepage:**
- Removed "data points across N tables · live" subtitle that was overwriting the label on each refresh

## 2026-05-27 (Session 73) — OEX checkboxes, quartile row-hide, Cmd+click, DB table nodes, homepage card removal (commit 200af10)

**OEX — oex-main-script full rewrite (new_oex_features.js, 756 lines injected into good base bbd4a86):**
- **Checkbox selection**: Replaced R/C buttons with paired ☑ R / ☑ C checkboxes per tree node; checked = included in matrix axis; event delegation handles change events
- **All 25 DB tables in tree**: `OEX_ALL_TABLES` array + Database Tables section in Quick View gets injected checkboxes for every table, enabling table×table cross-reference matrix
- **Quartile row-hiding**: `≤25%/≤50%/≤75%/All` buttons now `display:none` entire rows where ALL cells exceed the ceiling — no more ghost rows polluting the view
- **Cmd+click multi-cell comparison**: Replaced inline `onclick="oexClickCell(this, event)"` with event delegation (`wrap.addEventListener('click', ...)`) passing real DOM event — `e.metaKey` / `e.shiftKey` now correctly captured for multi-select inspector
- **Table×table strength**: `_oexTableStrength()` via `OEX_JOIN_MAP`/`OEX_FK_COL` FK intersection — coverage score between any two DB tables
- **CPM dot fix re-applied**: `LEFT_MARGIN - 14 - labelWidth - 7` → `- 14` (dots column-aligned left of labels)

**Homepage:**
- Removed 3 static metric tiles (`#hw-bd-metrics`: DATA POINTS 9,389 / CONNECTIONS 3,139 / INTELLIGENCE SIGNALS 57) — hardcoded values replaced by live center total + animated breakdown strip already in place

## 2026-05-27 (Session 72) — OEX tree R/C integration, quartile filter, multi-cell inspector; CPM dot fix (commit 4a63f4f)

**OEX — Matrix Builder removed, R/C buttons injected directly into tree:**
- Removed the separate "Matrix Builder" panel and `#oex-node-catalog` section from OEX left panel
- `oexInjectTreeButtons()` runs after tree renders; adds R/C (row/column) toggle buttons to each leaf item in Quick View (Disease Areas, Molecular Targets, Drug Pipeline, Companies)
- "All R" / "All C" buttons on each section header add/remove the entire category at once
- Button states (✓R / ✓C) update live as matrix changes
- `oexToggleGroup()` handles category-level toggling; `oexToggleNode()` handles individual items
- OEX_LABEL_MAP: label→node lookup built from OEX_CAT for fast tree injection matching
- `oexLoadTree` patched: re-injects buttons after each polling refresh

**OEX — Quartile filter buttons (replace slider):**
- Removed `<input type="range">` slider entirely
- Four buttons in toolbar: ≤25% / ≤50% / ≤75% / All (active state in green)
- Clicking a button sets `OEX_MS.ceiling`; cells above threshold get `opacity:0.15` + strikethrough
- Active button highlighted: green background + border; inactive: dark/muted
- `oexSetCeiling()` handles both button state updates and matrix re-render

**OEX — Multi-cell inspector (Shift/Cmd+click):**
- Single click: inspect one cell (detailed area×layer drill with covered/missing drug chips)
- Shift or Cmd+click: add up to 6 cells to selection (gold outline on selected cells)
- Multi-cell view: comparison table (row × col × coverage% × count)
- Gap analysis: auto-highlights cells <40% in the comparison panel
- `oexClearInspector()` button in inspector header resets selection + outlines
- Inspector shows initial hint text: "Shift or ⌘Cmd+click to compare multiple"

**CPM — Dot/label overlap fix:**
- Changed arc x position: `LEFT_MARGIN - 14 - labelWidth - 7` → `LEFT_MARGIN - 14 - labelWidth - 14`
- Gap between dot right edge and text left edge: 3.5px → 10.5px — no more overlap

---

## 2026-06-16 — Security: RLS enabled on 24 exposed public tables
Supabase advisory rls_disabled_in_public. Applied anon read-only policy pattern (RLS ON + anon_read_<t> SELECT USING(true)) to: author_institution_focus, co_authorship, company_events, company_ownership, company_personnel, conference_abstract_signals, drug_safety, drug_trust_scores, entity_narratives, eu_approvals, governance_enforced_rules, governance_enforcement_config, governance_enforcement_log, kol_metrics, manufacturing_profile, manufacturing_sites, narrative_provenance, narrative_revisions, patient_unmet_need_competition, prediction_factors, prediction_revisions, publication_authors, target_disease_assoc, target_genetics. Anon writes/deletes now blocked; reads preserved. Migration: migrations/APPLIED_2026-06-16_rls_enable_24_exposed_tables.sql. OPEN: rotate leaked service_role key.
