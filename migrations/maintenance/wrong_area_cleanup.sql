-- wrong_area_cleanup.sql
-- Generated: 2026-05-23
-- Purpose: Remove stale drug_area_scores orphan rows where:
--   (a) drug has no matching drug_areas entry, AND
--   (b) the area assignment is clearly wrong (wrong target, wrong indication, oncology in IBD area, etc.)
--
-- DO NOT RUN until docs/wrong_area_audit.md has been reviewed.
-- This script deletes 56 rows. Run in a transaction and verify row count before committing.
-- After running: execute validate_ground_truth.py to confirm 64/64 tests still pass.
--
-- SEPARATE FOLLOW-UP (not in this script):
--   - Add drug_areas rows for correct-but-orphaned scores (sim0500/ibd, batoclimab/fcrn, etc.)
--   - Resolve cld-423 / cldr-001 identity question
--   - Investigate uncertain rows (autoimmune Novartis 6, upadacitinib/atopy, etc.)

BEGIN;

-- ── atopy deletes (21 rows) ───────────────────────────────────────────────────
-- abbv-382/atopy: α4β7 IBD drug, not atopy (Adjacent orphan)
DELETE FROM drug_area_scores WHERE drug_id = 'abbv-382' AND area_id = 'atopy';

-- abbv-668/atopy: RIPK1 IBD drug, not atopy
DELETE FROM drug_area_scores WHERE drug_id = 'abbv-668' AND area_id = 'atopy';

-- adalimumab/atopy: TNFα IBD/RA drug, not atopy
DELETE FROM drug_area_scores WHERE drug_id = 'adalimumab' AND area_id = 'atopy';

-- bemarituzumab/atopy: FGFR2b gastric cancer drug
DELETE FROM drug_area_scores WHERE drug_id = 'bemarituzumab' AND area_id = 'atopy';

-- blinatumomab/atopy: CD19×CD3 BiTE for B-cell ALL
DELETE FROM drug_area_scores WHERE drug_id = 'blinatumomab' AND area_id = 'atopy';

-- ciltacabtagene-autoleucel/atopy: BCMA CAR-T for myeloma
DELETE FROM drug_area_scores WHERE drug_id = 'ciltacabtagene-autoleucel' AND area_id = 'atopy';

-- guselkumab-golimumab/atopy: IBD combination trial
DELETE FROM drug_area_scores WHERE drug_id = 'guselkumab-golimumab' AND area_id = 'atopy';

-- daratumumab/atopy: CD38 mAb for myeloma
DELETE FROM drug_area_scores WHERE drug_id = 'daratumumab' AND area_id = 'atopy';

-- golimumab/atopy: TNFα IBD/RA drug
DELETE FROM drug_area_scores WHERE drug_id = 'golimumab' AND area_id = 'atopy';

-- guselkumab/atopy: IL-23p19 IBD/PsA drug, not atopy
DELETE FROM drug_area_scores WHERE drug_id = 'guselkumab' AND area_id = 'atopy';

-- inebilizumab/atopy: CD19 mAb for NMOSD (neurology)
DELETE FROM drug_area_scores WHERE drug_id = 'inebilizumab' AND area_id = 'atopy';

-- infliximab/atopy: TNFα IBD/RA drug
DELETE FROM drug_area_scores WHERE drug_id = 'infliximab' AND area_id = 'atopy';

-- lutikizumab/atopy: IL-1α/β, IBD combo context, not atopy
DELETE FROM drug_area_scores WHERE drug_id = 'lutikizumab' AND area_id = 'atopy';

-- m701/atopy: oncology drug (target field mislabeled in DB)
DELETE FROM drug_area_scores WHERE drug_id = 'm701' AND area_id = 'atopy';

-- nipocalimab/atopy: FcRn mAb — belongs in fcrn area, not atopy
DELETE FROM drug_area_scores WHERE drug_id = 'nipocalimab' AND area_id = 'atopy';

-- risankizumab/atopy: IL-23p19 IBD/PsA drug, not atopy
DELETE FROM drug_area_scores WHERE drug_id = 'risankizumab' AND area_id = 'atopy';

-- risankizumab-lutikizumab-or-trosunilimab/atopy: IBD combo trial
DELETE FROM drug_area_scores WHERE drug_id = 'risankizumab-lutikizumab-or-trosunilimab' AND area_id = 'atopy';

-- risankizumab-vs-vedolizumab/atopy: IBD head-to-head trial
DELETE FROM drug_area_scores WHERE drug_id = 'risankizumab-vs-vedolizumab' AND area_id = 'atopy';

-- teclistamab/atopy: BCMA×CD3 BiTE for myeloma
DELETE FROM drug_area_scores WHERE drug_id = 'teclistamab' AND area_id = 'atopy';

-- teprotumumab/atopy: IGF-1R mAb for thyroid eye disease
DELETE FROM drug_area_scores WHERE drug_id = 'teprotumumab' AND area_id = 'atopy';

-- tezepelumab/atopy: TSLP mAb — belongs in tslp area, not atopy (duplicate coverage)
DELETE FROM drug_area_scores WHERE drug_id = 'tezepelumab' AND area_id = 'atopy';

-- ustekinumab/atopy: IL-12/23p40 IBD drug (Stelara), not atopy
DELETE FROM drug_area_scores WHERE drug_id = 'ustekinumab' AND area_id = 'atopy';


-- ── fcrn deletes (2 rows) ─────────────────────────────────────────────────────
-- argx-117/fcrn: target field mislabeled; actually anti-C2 complement mAb, not FcRn
DELETE FROM drug_area_scores WHERE drug_id = 'argx-117' AND area_id = 'fcrn';

-- bimekizumab/fcrn: IL-17A/F dual inhibitor; no FcRn connection
DELETE FROM drug_area_scores WHERE drug_id = 'bimekizumab' AND area_id = 'fcrn';


-- ── ibd deletes (20 rows) ─────────────────────────────────────────────────────
-- hxn-1003/ibd: drug was merged into erd-1 in Session 5 (commit 14df877); stale row
DELETE FROM drug_area_scores WHERE drug_id = 'hxn-1003' AND area_id = 'ibd';

-- abrocitinib/ibd: JAK1 inhibitor approved in atopic dermatitis; not an IBD drug
DELETE FROM drug_area_scores WHERE drug_id = 'abrocitinib' AND area_id = 'ibd';

-- amlitelimab/ibd: OX40L mAb; atopy/AD program. No IBD indication
DELETE FROM drug_area_scores WHERE drug_id = 'amlitelimab' AND area_id = 'ibd';

-- astegolimab/ibd: IL-33 mAb; COPD. Rationale explicitly excludes IBD
DELETE FROM drug_area_scores WHERE drug_id = 'astegolimab' AND area_id = 'ibd';

-- atezolizumab/ibd: PD-L1; cancer immunotherapy
DELETE FROM drug_area_scores WHERE drug_id = 'atezolizumab' AND area_id = 'ibd';

-- belzutifan/ibd: HIF-2α; VHL/ccRCC cancer
DELETE FROM drug_area_scores WHERE drug_id = 'belzutifan' AND area_id = 'ibd';

-- bevacizumab/ibd: VEGF-A; cancer
DELETE FROM drug_area_scores WHERE drug_id = 'bevacizumab' AND area_id = 'ibd';

-- dupilumab/ibd: IL-4Rα; atopy (AD, asthma). No approved IBD indication
DELETE FROM drug_area_scores WHERE drug_id = 'dupilumab' AND area_id = 'ibd';

-- glofitamab/ibd: CD20×CD3 BiTE; B-cell lymphoma
DELETE FROM drug_area_scores WHERE drug_id = 'glofitamab' AND area_id = 'ibd';

-- ibi333/ibd: IL-4Rα×TSLP bispecific; atopy/asthma
DELETE FROM drug_area_scores WHERE drug_id = 'ibi333' AND area_id = 'ibd';

-- ixekizumab/ibd: IL-17A; IL-17 pathway contraindicates IBD
DELETE FROM drug_area_scores WHERE drug_id = 'ixekizumab' AND area_id = 'ibd';

-- lebrikizumab/ibd: IL-13; atopic dermatitis. No IBD/TL1A connection
DELETE FROM drug_area_scores WHERE drug_id = 'lebrikizumab' AND area_id = 'ibd';

-- lenvatinib/ibd: multikinase TKI; cancer
DELETE FROM drug_area_scores WHERE drug_id = 'lenvatinib' AND area_id = 'ibd';

-- linsitinib/ibd: IGF-1R inhibitor; oncology
DELETE FROM drug_area_scores WHERE drug_id = 'linsitinib' AND area_id = 'ibd';

-- mosunetuzumab/ibd: CD20×CD3 BiTE; B-cell lymphoma
DELETE FROM drug_area_scores WHERE drug_id = 'mosunetuzumab' AND area_id = 'ibd';

-- obinutuzumab/ibd: CD20; CLL/lymphoma
DELETE FROM drug_area_scores WHERE drug_id = 'obinutuzumab' AND area_id = 'ibd';

-- ocrelizumab/ibd: CD20; multiple sclerosis
DELETE FROM drug_area_scores WHERE drug_id = 'ocrelizumab' AND area_id = 'ibd';

-- pembrolizumab/ibd: PD-1; cancer immunotherapy
DELETE FROM drug_area_scores WHERE drug_id = 'pembrolizumab' AND area_id = 'ibd';

-- riliprubart/ibd: C1q complement; neurology/rare
DELETE FROM drug_area_scores WHERE drug_id = 'riliprubart' AND area_id = 'ibd';

-- rituximab/ibd: CD20; RA/lymphoma
DELETE FROM drug_area_scores WHERE drug_id = 'rituximab' AND area_id = 'ibd';

-- retatrutide/ibd: triple incretin; metabolic/obesity
DELETE FROM drug_area_scores WHERE drug_id = 'retatrutide' AND area_id = 'ibd';

-- rocatinlimab/ibd: OX40; atopic dermatitis program
DELETE FROM drug_area_scores WHERE drug_id = 'rocatinlimab' AND area_id = 'ibd';

-- tirzepatide/ibd: dual incretin; T2D/obesity
DELETE FROM drug_area_scores WHERE drug_id = 'tirzepatide' AND area_id = 'ibd';

-- tocilizumab/ibd: IL-6R; RA/COVID. Not an IBD mechanism
DELETE FROM drug_area_scores WHERE drug_id = 'tocilizumab' AND area_id = 'ibd';


-- ── il4ra deletes (2 rows) ────────────────────────────────────────────────────
-- itepekimab/il4ra: IL-33 mAb; upstream alarmin but not IL-4Rα
DELETE FROM drug_area_scores WHERE drug_id = 'itepekimab' AND area_id = 'il4ra';

-- linvoseltamab/il4ra: BCMA×CD3 BiTE for myeloma; no il4ra connection
DELETE FROM drug_area_scores WHERE drug_id = 'linvoseltamab' AND area_id = 'il4ra';


-- ── respiratory deletes (2 rows) ─────────────────────────────────────────────
-- qx030n/respiratory: TL1A×IL-23p19 — tl1a/ibd area, not respiratory (Direct orphan)
DELETE FROM drug_area_scores WHERE drug_id = 'qx030n' AND area_id = 'respiratory';

-- belimumab/respiratory: BAFF mAb; SLE. No respiratory program
DELETE FROM drug_area_scores WHERE drug_id = 'belimumab' AND area_id = 'respiratory';


-- ── tcell deletes (1 row) ─────────────────────────────────────────────────────
-- nipocalimab/tcell: FcRn mAb — belongs in fcrn area, not tcell
DELETE FROM drug_area_scores WHERE drug_id = 'nipocalimab' AND area_id = 'tcell';


-- ── tslp deletes (4 rows) ─────────────────────────────────────────────────────
-- generate-uc/tslp: TL1A×IL-23p19 — tl1a/ibd area, not tslp (Direct orphan)
DELETE FROM drug_area_scores WHERE drug_id = 'generate-uc' AND area_id = 'tslp';

-- anifrolumab/tslp: IFNAR1 mAb; SLE. No TSLP connection
DELETE FROM drug_area_scores WHERE drug_id = 'anifrolumab' AND area_id = 'tslp';

-- cendakimab/tslp: IL-33/EoE drug (data quality issue — wrong company in DB); not TSLP
DELETE FROM drug_area_scores WHERE drug_id = 'cendakimab' AND area_id = 'tslp';

-- ravulizumab/tslp: C5 complement; PNH/aHUS. No TSLP connection
DELETE FROM drug_area_scores WHERE drug_id = 'ravulizumab' AND area_id = 'tslp';


-- ── Verification ─────────────────────────────────────────────────────────────
-- Expected: 56 rows deleted
-- Run this SELECT before committing to confirm:
-- SELECT COUNT(*) FROM drug_area_scores; -- should be 152 - 56 = 96

-- If count looks right, COMMIT. Otherwise ROLLBACK.
-- After committing: run python3 scripts/validate_ground_truth.py

COMMIT;


-- ═══════════════════════════════════════════════════════════════════════════════
-- PHASE 2 — drug_areas additions (run after Phase 1 + review)
-- These are score rows where the area assignment is CORRECT but drug_areas is missing.
-- Do NOT run until cld-423/cldr-001 identity is resolved.
-- ═══════════════════════════════════════════════════════════════════════════════

-- UNCOMMENT AND RUN AFTER REVIEW:

-- sim0500/ibd — TL1A Phase 1 IBD drug, clearly correct
-- INSERT INTO drug_areas (drug_id, area_id) VALUES ('sim0500', 'ibd') ON CONFLICT DO NOTHING;

-- abs-101/ibd — TL1A Phase 1 IBD drug
-- INSERT INTO drug_areas (drug_id, area_id) VALUES ('abs-101', 'ibd') ON CONFLICT DO NOTHING;

-- mt-251/ibd — TL1A×IL-23p19 bispecific (Mirador), IBD correct
-- INSERT INTO drug_areas (drug_id, area_id) VALUES ('mt-251', 'ibd') ON CONFLICT DO NOTHING;

-- batoclimab/fcrn — Immunovant discontinued FcRn mAb; still FcRn-relevant for comp landscape
-- INSERT INTO drug_areas (drug_id, area_id) VALUES ('batoclimab', 'fcrn') ON CONFLICT DO NOTHING;

-- imvt-1402/fcrn — Immunovant next-gen FcRn mAb (Phase 3)
-- INSERT INTO drug_areas (drug_id, area_id) VALUES ('imvt-1402', 'fcrn') ON CONFLICT DO NOTHING;

-- apg777/il4ra — Apogee IL-4Rα×OX40L bispecific
-- INSERT INTO drug_areas (drug_id, area_id) VALUES ('apg777', 'il4ra') ON CONFLICT DO NOTHING;

-- upadacitinib/atopy — JAK1 inhibitor approved in atopic dermatitis (Rinvoq)
-- INSERT INTO drug_areas (drug_id, area_id) VALUES ('upadacitinib', 'atopy') ON CONFLICT DO NOTHING;

-- mepolizumab/respiratory — IL-5 mAb approved in asthma (Nucala)
-- INSERT INTO drug_areas (drug_id, area_id) VALUES ('mepolizumab', 'respiratory') ON CONFLICT DO NOTHING;

-- cld-423/tl1a and cld-423/ibd — ONLY add after resolving cld-423/cldr-001 identity
-- INSERT INTO drug_areas (drug_id, area_id) VALUES ('cld-423', 'tl1a') ON CONFLICT DO NOTHING;
-- INSERT INTO drug_areas (drug_id, area_id) VALUES ('cld-423', 'ibd') ON CONFLICT DO NOTHING;
