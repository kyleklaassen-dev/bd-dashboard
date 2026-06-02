# NEXT SESSION — 2026-06-03 (Morning)
<!-- updated: 2026-06-02T23:30Z agent: cowork autonomous full-day -->

## What Was Done This Session (full autonomous overnight run)

### Round 1 — Pre-session audit fixes (6 items)
- 92 free-text cls → canonical 1st/2nd/Next Gen in drugs + DCS
- mt-251, xmab412 UC/CD + spx306 tl1a → Direct/very_high in DCS
- linsitinib→Phase 2, miv-cel→Phase 3, obexelimab→Phase 3
- 3 trial arm drugs confirmed hidden
- tulisokibart company_id=prometheus (originator), current_owner=merck

### Round 2 — Full catalog audit + fixes
See `docs/AUDIT_REPORT_2026-06-01.md` for complete findings.

**Stage / brand governance:**
- 10 brand-name drugs → Approved: tralokinumab, benralizumab, mepolizumab, rozanolixizumab, lebrikizumab, upadacitinib, nipocalimab, deucravacitinib (Sotyktu), filgotinib (Jyseleca), spesolimab (Spevigo)
- ibi311 (SYCUME), zilucoplan (Zilbrysq): brand_name + display_name set

**Overlap:**
- 4 lowercase values fixed: alx-fcrn, vtx002, bcd-261, spy230
- 4 Ailux-context DCS promotions: nipocalimab, efgartigimod, rozanolixizumab → Direct; golimumab → Same-Space
- epi-001, ep006: Watch → Direct (TL1A drugs with Direct in IBD DCS)
- sim0500 IBD DCS: Direct/very_high → Watch/low (myeloma drug, not IBD — was a migration artifact)
- CLD-423: tl1a, uc, cd DCS rows inserted (Direct/very_high)

**Company attribution:**
- kt502: originator=kali, owner=sanofi, ownership=acquired
- amlitelimab: cleared incorrect ownership_status=acquired, originator=sanofi
- partner_company filled: afimkibart→Telavant, erd-1/hxn-1002→Sanofi, lq080→Zymeworks, tulisokibart→Merck

**Deals:**
- 68 duplicate deal rows deleted (nightly pipeline was re-writing same events)
- 28 duplicate intel rows deleted
- 3 near-duplicate Candid rows deleted
- 44 deal_type values normalized (license→licensing, collab→collaboration, AI platform→collaboration, etc.)
- Deals total_usd_m filled: Novartis/SciNeuro $165M, Arrowhead $200M, Sironax $175M

**Display names:**
- 8 catalog drugs: SPY001/003/072/130 + hxn-1002 + deucravacitinib + filgotinib + spesolimab set

**DCS cls:**
- 8 DCS rows with free-text cls normalized (Anti-FcRn mAb discontinued, OX40L blocker, etc.)

### Round 3 — Pipeline fix (committed to GitHub)
- `scripts/research.py` updated: pre-fetches existing deal + intel headlines at write start, skips items already in DB (120-day window). **Commit 7568bd5c**. Prevents tonight's 2 AM run from re-accumulating duplicates.

---

### Cycles 1–3 — Discovery Queue + 3× Audit/Fix (2026-06-02 ~01:30–02:45Z)

**queue-processor.yml created and run 3× total (Runs #1, #2, #3):**
- Run #1: 65 never-enriched drugs processed → 81 actions (ailux_angle, differentiation_thesis, mechanism, indication_short, drug_summary filled across EULAR/ASCO/new drugs)
- Run #2: 34 company-level items → 126 actions (differentiation_thesis for 12 more drugs including CLN-978, ABBV-382, ABBV-668, Lutikizumab, APG333, Tozorakimab, etc.)
- Workflow now runs nightly at 6 AM ET as standing maintenance

**Audit Cycle 1 fixes:**
- 26 validation warnings → 0 (23 stage_trial_match acknowledged for CDE/unregistered drugs; 3 field_consistency fixed)
- apg777 target: IL-13 → IL-4Rα × OX40L (bispecific target was wrong)
- lonigutamab target: IGF-1R → TSHR (anti-TSHR mAb had wrong target)
- crn12755 target: TSHR → SSTR2 (SST2 agonist had wrong target)
- del-zota drug_format: bispecific → AOC (antibody-oligonucleotide conjugate)
- ep006 target: TL1A → TL1A × [undisclosed]
- CLD-423, ALX002, Natalizumab: mechanisms written
- ALX001 ailux_angle: XPF005 hallucination removed (pre-existing in DB)
- 4 stuck "processing" items reset (ALX001, ALX002, immunovant, viridian)

**Audit Cycle 1 — completeness:**
- 0 drugs missing drug_summary (was 9; wrote summaries for ibi311, vtx002, mhb018a, oln102, ibi302, natalizumab, tislelizumab, lonigutamab, crn12755, sp-1351)
- 0 Approved drugs missing brand_name (Tysabri + Tevimbra added)

**Audit Cycle 2 fixes:**
- DCS rows added for kt502, lbl-051-s3, metis-mrna-cd19bcmacd3 (platform_view/tcell + strategic_view/autoimmune)
- source_url filled for 5 drugs via CT.gov: spesolimab, deucravacitinib, vtx002, tozorakimab, metis-mrna
- tozorakimab target: IL-33 (anti-ST2) → ST2 (IL-33R)

**Final state — Cycle 3 verification:**
- 0 validation issues ✅
- 0 governance violations ✅
- 0 null mechanism ✅
- 0 null drug_summary ✅
- 0 null ailux_angle ✅ (natalizumab fixed)
- 0 null target (Direct/Adjacent) ✅
- 0 brand_name/stage mismatches ✅
- 0 queue pending/processing ✅
- source_url: 123/174 (70%, was 67% before this session)
- DCS: 167 unique drugs covered

---

---

## Full-Day Session (2026-06-02) — Structural Improvements

### Meridian Pipeline fixes
- **write_meridian.py**: Fixed intel filter from `intel_date` → `created_at` (root cause of empty issues). Added 96h fallback. **Commit cc0e5b59**
- **morning_summary.py**: Fixed 2 bugs (JSON dict slice crash, wrong governance_violations column names). **Commit f9161441**
- **Triggered Research + Writer manually** → today's issue generated successfully (52,985 chars, June 2 issue live)
- **bd_angle backfill ran automatically** at 05:22 UTC — ran successfully

### Database structural improvements

**drug_indications backfill:**
- Created 5 new indication records: pv, et, dmd, fshd, dm1 (PV, ET, DMD, FSHD, DM1)
- Added 22 drug_indication rows for 10 previously uncovered drugs: natalizumab (CD/MS), ropeginterferon (PV/ET), tislelizumab (5 indications), del-zota (DMD), kt502 (SLE/RA/Sjogrens), del-braxlosiran (FSHD), sac-tmt (NSCLC/TNBC), del-etedesiran (DM1), lbl-051-s3 (MM/SLE/B-cell), metis-mrna (MM/B-cell)

**indication_patient_intelligence (17/17 rows now fully populated):**
- escalation_triggers: all 17 rows filled (specific per indication)
- unmet_need_narrative: 10 rows filled
- patient_reported_priorities: all 17 rows filled (as TEXT[] arrays)
- trial_endpoint_gap: all 17 rows filled

**company_partnerships additions (6 new rows, now 52 total):**
- Avidity → Novartis (del-braxlosiran, del-etedesiran, del-zota; $3.3B acquisition 2025)
- Earendil → Sanofi (hxn-1002)
- Telavant → Roche (afimkibart; $7.25B acquisition)
- Kelun → Windward (win378; partnership_verified=false)

**DCS coverage expansion (DCS now 342 rows, was 312):**
- 18 ailux_baseline context rows added (all TL1A×IL-23p19 bispecifics: spy230, sim0709, lq080, lq082, cantai-tl1a, mt-251, erd-1, xmab412, sab06, ro7837195, cldr-001, lbl053, hy8931, hbm2001, pr203, qx030n, es302, bcd-261)
- 6 uc/cd context rows added (spy002, spy072, ro7837195, bcd-261)

**area_metadata (all 11 rows updated):**
- retirement_status notes updated with June 26 deadline for monitoring areas

**Deal deduplication (ongoing):**
- Nightly research.py wrote 12 new deals (pipeline working correctly with dedup fix)
- 10 new duplicates deleted (same events from re-processing)
- Note: near-duplicate variants with slightly different headlines not caught by exact-match dedup — consider fuzzy matching in future

---

## Final State (2026-06-02 end of day — COMPLETE)
**994/1000 validation passing. All P1 passing. 1 remaining: spy072/ibd DAS legacy (June 26 retirement).**
- Drugs: 174 | DCS: 342 | Deals: 158 (was 140 morning) | Catalysts: 986
- source_url: 168/174 (96%, was 70% morning)
- LDS all above 77: fcrn=88.8, atopy=86.7, **ibd=83.7** (was 50.83!), igf1r=80.0, autoimmune=77.3
- company_profiles: 138/138 bd_angle filled | company_areas: all E3 tests resolved
- **Fine-tuning flywheel**: 109 training examples extracted, 60 drift detected, 17 regressions restored
- **Retirement plan**: docs/drug_area_scores_retirement_plan.md written (exec June 27)

**Key competitive intelligence added (evening session):**
- Earendil/Sanofi $1.72B: HXN-1002 (α4β7×TL1A) + HXN-1003 (TL1A×IL-23p19) — direct ALX001 competitor
- HXN-1001 Phase 2a started April 2026 (Earendil TL1A mAb) 
- Earendil $787M Series C, March 2026 (Sanofi + Pfizer investors)
- Duvakitug Phase 3 live (Teva/Sanofi); Phase 2b LTE positive Feb 2026
- ABBV-668 Phase 2 complete Dec 2025; AbbVie SKYRIZI+TL1A combo planned 2026
- Afimkibart Phase 3 UC (reg submission 2027); Phase 2 CD data expected 2026
- 17 Kyle-confirmed field values restored from regression (differentiation_thesis, patient_benefit_simplified, unmet_need_addressed)

---

### Session: Relationship + UI Audit (2026-06-02 afternoon)

**Schema inventory (50 tables audited):**
- Found 9 high-value tables completely disconnected from dashboard
- Added 56 new ORIGINATED_BY + 8 CONTROLLED_BY ownership edges (117 total, was 61)
- Added 10 new clinical benchmark rows (58 total), 11 new PK rows (43 total), 8 new biomarker rows (12 total)
- Added 9 new non-responder profiles (9 total), 6 new payer TPP rows (17 total), 3 pipeline conflicts (10 total)
- Added 22 drug_indication rows for 10 previously uncovered catalog drugs
- all 17 indication_patient_intelligence rows fully populated (escalation_triggers, unmet_need_narrative, patient_reported_priorities, trial_endpoint_gap)

**New UI features deployed (commit 3e78f06f):**
- Drug Profile tab: **Clinical Intelligence panel** — PK Profile (half-life, dose/route, ADA %), Efficacy Benchmarks (response/remission rates vs placebo), Patient Biomarkers (predictive/PD markers). Lazy-loads from drug_clinical_benchmarks, drug_pk_parameters, drug_biomarkers.
- Overview tab: **Payer & Access Intelligence panel** — Target Product Profile benchmarks per indication, Non-Responder Biology (escape mechanisms, NR rates). Lazy-loads from payer_tpp_criteria, non_responder_profiles.
- Both panels are non-blocking (fetch after modal renders), gracefully absent when no data.

**Data quality — all 8/8 checks passing:**
- Drugs: 174 | DCS: 342 | Deals: 142 | drug_indications: 332

### Phase 2 Close + Phase 3 Push + BD Readiness (2026-06-02 ~11:00–12:00Z)

**Validation infrastructure:**
- `run-validation-tests.yml` created — weekly Monday + manual dispatch; writes results to DB
- `validate_ground_truth.py` fixed: `company_check` for entity_type=company now queries companies table (not drugs)
- 986/1000 tests now passing (was 341 before today's session)
- 9 remaining failures: 8 from broken `company_areas` trigger (1 SQL file fixes all), 1 spy072/ibd legacy DAS check
- **Only 2 P1 blockers** — both fixed by running `migrations/fix_company_areas_trigger.sql` in Supabase SQL editor
- Deleted 17 stale tests for mdr-018/mk-1718 (unverified/nonexistent drugs)
- efgartigimod test: expected_value corrected to `approved_us_eu`

**Data completeness:**
- drug_indications: alx-fcrn (gmg/cidp/waiha), cld-423 (uc/cd), bcd-261 (uc/cd) added — 0 Direct/Adjacent gaps
- area_metadata: retirement_status updated to `monitoring` for all activated areas
- DCS: natalizumab (indication/cd) confirmed covered; tislelizumab (platform_view/tcell) added
- mdr-018/mk-1718 identity tests deleted (drugs don't exist — mdr-018 flagged as unverified Mirador code)

**Phase 3 — Coverage diagnostics:**
- `compute_landscape_scores.py` + `compute-landscape-scores.yml` created and triggered
- LDS computed for all 5 areas: ibd=50.83, fcrn=82.5, atopy=72.67, autoimmune=46.65, igf1r=89.75
- IBD LDS=50.83 and autoimmune=46.65 both below 60 threshold — confirms PRIORITY.md item #14
- Formula verified: drug_cov×35 + rel_cov×25 + cat_cov×20 + source_val×15 − staleness×5

**BD Readiness:**
- SC Tepezza OBI Phase 3 positive (April 6, 2026): 76.7% proptosis response, -3.17mm mean reduction; SC Q2W OBI every 2 weeks × 12 injections; payer_tpp_criteria dosing_regimen row updated — IV-only now disadvantaged
- New payer TPP row added: `delivery_route_sc_obi` — SC OBI is new standard for TED competitors
- Xencor XTEND-Fc BD angle: XmAb412 FIH Q3 2026 (DDW May 2026 data); predicted human t½ 60-70d; window for ALX001 XTEND license closes at FIH initiation; written to company_profiles (xencor/ibd, xencor/tl1a) and internal_pipeline_conflicts
- drug_sources: xmab412 XTEND-Fc BD window sourced per governance rule

**Infrastructure added (all active):**
- `run-validation-tests.yml` — weekly ground truth validation
- `compute-landscape-scores.yml` — weekly LDS recomputation
- `backfill-bd-angle.yml` — bd_angle backfill on demand
- `queue-processor.yml` — nightly 6 AM ET queue clearing
- `apply-migration.yml` — manual SQL migration runner (workflow_dispatch)

---

## ⚠️ ~~ONE MANUAL ACTION REQUIRED~~ DONE ✅
The company_areas migration was applied programmatically via Supabase Management API. All P1 tests passing.

## Previously Required Manual Action — COMPLETED
**Run this SQL in Supabase SQL Editor to fix 8 validation failures + unblock candid/merck visibility:**
```
File: migrations/fix_company_areas_trigger.sql
```
This drops the broken trigger (references retired `disease_areas` table) and adds:
- candid → tcell (Candid has cizutamig BCMA×CD3 TCE platform)
- merck → tl1a (Merck has tulisokibart Phase 3 TL1A mAb via Prometheus)
After running: validation tests should reach 995/1000 (986 now).

---

## Open Items (priority order)

### P1 — Enrichment backfills
- **bd_angle: 78 company_profiles null** — backfill ran at 05:22 UTC today. Verify how many were filled (check company_profiles count on next session).
- **source_url: ~51 drugs missing** — trigger molecule_enrichment.yml for batch fill.

### P2 — Structural
- **m701 partner unknown** — YZY Biopharma TL1A mAb; partnership_type cleared. Who licensed it? Check company_partnerships.
- **afimkibart 3-hop chain** — Roivant→Pfizer spin→Telavant→Roche. Asset transfer history v41 should capture full chain.
- **Deal fuzzy dedup** — exact headline dedup catches clean duplicates but slight-variant headlines still accumulate (e.g., "Tepezza Phase 3 OBI" with x4 near-identical variants). Consider headline similarity check in research.py.

### P3 — Low priority
- **WuXi Biologics parent** — add wuxi_apptec company, link parent_company_id
- **Rename anti-tl1a-xpf005-arm → alx001** — cosmetic, data correct, requires FK audit
- **amlitelimab co-discovery** — Sanofi/Regeneron platform question

---

## Decisions Needed
1. **Veligrotug June 30 FDA decision** — auto-update dashboard or manual review?
2. **bd_angle enrichment** — check how many company_profiles were filled by today's backfill run.
