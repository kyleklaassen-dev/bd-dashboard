# Meridian — Current Priority Stack

**Last updated:** 2026-06-02 (full-day autonomous session — Phase 2 close + Phase 3 start + BD readiness)  
**Rule:** Claude reads this at the start of every session before any other action. Claude updates this at the end of every session. Kyle reviews and corrects direction here, not mid-session.  
**Multi-agent:** Two agents active. Agent 2 owns 100Q Phase A. This agent takes everything else. Both append to AGENT_LOG.md. Neither overwrites PRIORITY.md mid-task.

---

## ▶ DOING NOW

**⚠️ KYLE ACTION REQUIRED: Run `migrations/fix_company_areas_trigger.sql` in Supabase SQL Editor**
Fixes broken trigger + adds candid/tcell + merck/tl1a rows. Unblocks 2 P1 validation failures. 30 seconds.

**Next autonomous priority: IBD coverage score improvement (LDS=50.83, below 60 threshold)**
Add missing drug-indication pairs, ensure all IBD drugs have complete DCS rows + catalysts.
Then: 100Q Phase B (waiting on Agent 2 Phase A validation).

---

## QUEUE (in order — do not skip ahead)

| # | Item | Source | Priority | Status | Notes |
|---|------|--------|----------|--------|-------|
| 1 | **Veligrotug June 30 auto-update** — dashboard + DB on FDA decision | Kyle 2026-06-01 | P1 | Timed | Kyle confirmed: auto-update dashboard. Run SQL from docs/veligrotug_pdufa_bd_prep.md on June 30. |
| 2 | **source_url backfill — 51 drugs missing** | v19 QA | P2 | In progress | Was 59→57→51. queue-processor.yml runs nightly. 3 Direct drugs legitimately unregistered (cld-423, lbl-051-s3, hxn-1002). |
| 3 | **drug_summary** | v19 QA | P2 | ✅ DONE | 0 drugs missing. Resolved 2026-06-02 autonomous session. |
| 8 | **Run all 1,000 validation tests** | v19 P3 | P3 | ✅ DONE | 986/1000 passing. 2 P1 blockers need SQL migration (see DOING NOW). Weekly run now scheduled. |
| 9 | **Wave 3 validation sprint** | v24 P1 | P1 | ✅ DONE | Tested as part of full 1000-test run. drug_validation_results clean. |
| 10 | **Coverage Diagnostics — landscape_dependency_score** | v24 P1 | P1 | ✅ DONE | Computed for all 5 areas: ibd=50.83, fcrn=82.5, atopy=72.67, autoimmune=46.65, igf1r=89.75. compute-landscape-scores.yml runs weekly. |
| 11 | **area_metadata table** | v24 P1 | P1 | ✅ DONE | 11 rows, all monitoring status, retirement ~June 26. |
| 12 | **indication_patient_intelligence** | v24 G-007 | P2 | ✅ DONE | 17/17 rows 100% filled (another agent completed this 2026-06-02). |
| 13 | **partner_company_ids[] co-developer sweep** | v24 P2 | P2 | Open | 6 new company_partnerships added by other agent. Remaining gaps: m701 partner unknown. |
| 14 | **IBD coverage score improvement** | v19 P3 | P1 | Open | LDS=50.83 (below 60). Improve: add more drug-indication pairs, ensure catalyst coverage. ibD drug_coverage=0.29 (main gap). |
| 15 | **intel_companies null** | v19 P3 | P3 | ✅ DONE | 0 null company_ids. |
| 16 | **SC Tepezza TPP update** | v19 P5 | P2 | ✅ DONE | Phase 3 OBI positive April 2026. payer_tpp_criteria updated. IV-only now disadvantaged. |
| 17 | **drug_competitive_scores WS3** | v24 P0 | P2 | ✅ DONE | 320+ rows. All Direct/Adjacent covered. No competitive_scoring.py needed. |
| 18 | **Fine-tuning flywheel** — extract kyle_reviews 109 items into structured signal | v24 P2 | P2 | Open | Design prompt improvement loop. |
| 19 | **drug_area_scores retirement** — table retirement after June 26 | Option C | P2 | Timer | 30-day monitoring window closes ~June 26. Then build area_metadata + retire. |
| 20 | **100Q Phase B** — research agents for 164+ drugs (after Phase A complete) | 100Q | P2 | Waiting | Do not start until Phase A validated by other agent. |

---

## HORIZON (not yet scheduled)

- **Drug card IA redesign** — 4-section canonical card around 100Q framework (Phase C)
- **Meridian Issue full automation** — write_meridian.py → fully AI-written, human-reviewed
- **enrichment_qa.py activation** — model comparison engine (planned in workflow schedule, not yet active)
- **Temporal SCD** — slowly changing dimensions for ownership history
- **Inference rules engine** — contradiction detection, automated rule firing
- **Fine-tuned enrichment models** — Phase 4 self-evolution
- **TL1A×α4β7 bispecific hypothesis** — spy120 Phase 2 risk, ALX004 candidate score 9.33
- **FcRn×CD19 mechanism validation** — CAR-T data for bispecific format support
- **Ownership lineage backfill** — historical CONTROLLED_BY edges pre-2026

---

## North Star (read before every architectural decision)

> "Which molecule should Ailux bring to the clinic, in which indication, with which differentiated clinical hypothesis — and where does the competitive landscape create or close that window?"

Intelligence hierarchy: **Patient → Indication → Target → Company.**  
Value flows upward from patients, not downward from deal activity.

**100Q frame:** Every drug should answer 100 questions across 8 domains: Molecule / Clinical / Patient / Payer / Competitive / Regulatory / IP / Strategic BD.

---

## Phase Status (from v24 18-month roadmap)

| Phase | Theme | Status |
|-------|-------|--------|
| Phase 1 | Foundation Build | ✅ 100% |
| Phase 2 | Intelligence Layer | 🔄 90% |
| Phase 3 | Production Intelligence Products | 🔄 15% |
| Phase 4 | Self-Evolution & BD Prep | ⬜ 0% |
| Phase 5 | Autonomous Intelligence | ⬜ 0% |

---

## Update Rules

- Claude updates `## ▶ DOING NOW` and queue at end of every session
- Completed items move to COMPLETED table with date + notes
- Kyle corrects sequencing here — not mid-session in chat
- New items go to HORIZON first; promotion requires Kyle approval
- Second agent: update your items with [Agent2] prefix so edits are attributable

---

## COMPLETED (as of 2026-06-01)

| Item | Completed | Notes |
|------|-----------|-------|
| v43 migration + bd_angle enrichment | 2026-06-01 | next_gen_rankings exists. bd_angle null dropped from 78 → 4. Enrichment succeeded. |
| Xencor XTEND-Fc promoted to P1 | 2026-06-01 | Kyle confirmed. Now DOING NOW. |
| Veligrotug June 30 auto-update | 2026-06-01 | Kyle confirmed auto-update. Added as queue item #1 (timed). |
| Mirador violations resolved | 2026-06-01 | MT-251 confirmed real, fabricated NCT removed. MDR-018 flagged as unverified (wrong prefix — Mirador uses MT- only). |
| XPF005/ALX001 half-life story | 2026-05-31 | Resolved. YTE Fc ~37d vs XTEND ~74d documented. Not a data error — a BD strategy question. See docs/xpf005_halflife_resolution.md. |
| Veligrotug PDUFA BD prep | 2026-05-31 | Written. June 30 decision. DB update SQL documented. See docs/veligrotug_pdufa_bd_prep.md. |
| CLD-423 mechanism + stage | 2026-05-31 | Stage → Phase 1. Mechanism added (TL1A×IL-23p19 bispecific, Caldera/Qyuns, $112.5M launch). |
| catalog-53 (Newsoara) mechanism | 2026-05-31 | Anti-TSLP mAb mechanism added. |
| SPY120 display_name | 2026-05-31 | "SPY120 (SPY001 + SPY002)" added. |
| XmAb942 Phase 1 data | 2026-05-31 | Human t½=74.1d, Q12W dosing — added to mechanism_detail. |
| XmAb412 mechanism | 2026-05-31 | XTEND-Fc bispecific, NHP t½ >20d, FIH Q3 2026 — documented. |
| alx-fcrn drug_targets | 2026-05-31 | FcRn (primary) + albumin (secondary) rows added. albumin target created. |
| intel primary_company_id | 2026-05-31 | 2 of 3 fixed. BioMarin not in DB (id=14 remains null). |
| drug_validation_results needs_review | 2026-05-31 | 0 remaining (was 4). ep006, obinutuzumab, linsitinib, voclosporin all resolved. |
| indication_patient_intelligence sparse | 2026-05-31 | biologic_nonresponse_rate filled: gMG 30%, Gastric/FGFR2b 55%, MM 20%. |
| Validation tests | Healthy | 1,000 rows, 34/34 P1 TL1A passing. Not broken — earlier count was RLS false-zero. |
| Option C (drug_area_scores migration) | 2026-05-27 | competitive_relevance migrated to DCS. DAS retirement on timer → ~June 26. |
| C7 FcRn activation | 2026-05-26 | useUnifiedFCRN=true. All 7 flags live. *(v24 incorrectly shows IN PROGRESS)* |
| company_strategic_views | ~2026-05-27 | 168 rows live. *(v24 incorrectly shows PLANNED)* |
| company_platform_views | ~2026-05-27 | 71 rows live. *(v24 incorrectly shows PLANNED)* |
| All 7 Phase 5 feature flags (C1–C7) | 2026-05-26 | Legacy read layer eliminated. |
| Wave 3 drug-indication backfill | ~2026-05-27 | drug_indications = 305 rows. |
| drug_competitive_scores migration (WS3 schema) | 2026-05-27 | 311 rows, context_type schema, competitive_relevance migrated. |
| internal_pipeline_conflicts | ~2026-05-29 | 6 rows seeded (Ailux, AbbVie, Sanofi, Lilly). |
| indication_patient_intelligence (17 rows) | ~2026-05-27 | Rich schema. 5 indications still sparse (queue item #12). |
| Phase 5 QA sprint P1–P3 | 2026-05-23 | Catalyst dedup, score=0 fix, 28-test ground truth. |
| Governance violations sweep | 2026-05-29 | 0 unresolved. All 30 historical violations closed. |
| drug_intelligence_qa + drug_clinical_benchmarks schema | 2026-05-31 | Tables created. Seeding owned by second agent. |
| v24 Master Review Excel | 2026-05-29 | 33 tabs. Full live data. |
| Phase 5 Identity Program | 2026-05-26 | 150/154 drugs (97.4%), 540/543 trials (99.4%). |
| Meridian pipeline (GitHub Actions, 12 workflows) | 2026-05-21 | All running. enrichment_qa.py still planned. |
