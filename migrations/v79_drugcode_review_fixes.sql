-- v79 — Drug-code review fixes (chat + DeepSeek consensus, 2026-06-06)
-- 5 "safe fix" codes with unambiguous sponsor-attributed public disclosures.
-- company_id = ORIGINATOR per governance rule 1. Every fact sourced in drug_sources.
BEGIN;

-- ── Originator company records (did not exist) ───────────────────────────────
INSERT INTO companies (id,name,company_type,status,geography,hq_country,tagline,last_verified,enriched_by)
VALUES
 ('bambusa','Bambusa Therapeutics','biotech','active','North America','US',
   'Half-life-extended multi-specific antibodies for Type 2 inflammation; lead BBT001 (IL-4Rα×IL-31) in AD','2026-06-06','claude-drugcode-review'),
 ('belenos','Belenos Biosciences','biotech','active','North America','US',
   'Long-acting bispecifics for chronic inflammation; lead BEL512 (TSLP×IL-13, =CM512 w/ Keymed) in AD','2026-06-06','claude-drugcode-review'),
 ('mabgeek','Mabgeek Biotech','biotech','active','China','CN',
   'Long-acting anti-IL-4Rα mAb MG-K10 (comekibart); NMPA filing accepted, US Phase 3','2026-06-06','claude-drugcode-review')
ON CONFLICT (id) DO NOTHING;

-- Kymab: acquired by Sanofi (2021); no independent pipeline/leadership >3y → acquired (governance rule 2)
INSERT INTO companies (id,name,company_type,status,geography,hq_country,parent_company_id,acquired_by,tagline,last_verified,enriched_by)
VALUES ('kymab','Kymab','biotech','acquired','Europe','UK','sanofi','sanofi',
   'Acquired by Sanofi 2021; originator of KY1044 (alomfilimab, anti-ICOS, oncology) and KY1005 (amlitelimab, OX40L)','2026-06-06','claude-drugcode-review')
ON CONFLICT (id) DO NOTHING;

-- ── 1. ABS-101 — Absci, anti-TL1A (mechanism contradicted target=TL1A) ───────
UPDATE drugs SET
  mechanism='ABS-101 is an AI-designed monoclonal antibody that binds both monomeric and trimeric TL1A (TNF-like ligand 1A) with high potency, blocking TL1A–DR3 signaling to suppress pro-inflammatory and pro-fibrotic cascades in inflammatory bowel disease. Engineered for low immunogenicity and quarterly subcutaneous dosing.',
  updated_at=now()
WHERE id='abs-101';

-- ── 2. BBT001 — Bambusa, IL-4Rα×IL-31 bispecific ─────────────────────────────
UPDATE drugs SET
  company_id='bambusa',
  target='IL-4Rα × IL-31',
  mechanism='BBT001 is a half-life-extended (2+2 format) bispecific antibody that simultaneously blocks IL-4Rα (the shared IL-4/IL-13 receptor subunit) and IL-31, combining suppression of Type 2 inflammation with direct inhibition of the IL-31 itch axis. ~33-day half-life supports dosing up to every 3 months in atopic dermatitis and CSU.',
  updated_at=now()
WHERE id='bbt001';

-- ── 3. BEL512 — Belenos (originator) + Keymed (China partner), TSLP×IL-13 ─────
UPDATE drugs SET
  company_id='belenos',
  partner_company='Keymed Biosciences',
  target='TSLP × IL-13',
  mechanism='BEL512 (=CM512) is a long-acting bispecific antibody targeting TSLP (an upstream epithelial alarmin) and IL-13 (a downstream Type 2 effector), blocking both ends of the Type 2 inflammatory cascade. ~70-day dosing interval; Phase 1b EASI-75 of 50–58% in moderate-to-severe atopic dermatitis.',
  updated_at=now()
WHERE id='bel512';

-- ── 4. KY1044 — Kymab/Sanofi, anti-ICOS (alomfilimab), ONCOLOGY → hide ────────
-- target was wrongly OX40L (that is KY1005/amlitelimab — a different Kymab asset)
UPDATE drugs SET
  company_id='kymab',
  target='ICOS',
  dashboard_visible=false,
  updated_at=now()
WHERE id='ky1044';

-- ── 5. MG-K10 — Mabgeek, anti-IL-4Rα (comekibart) ────────────────────────────
UPDATE drugs SET
  company_id='mabgeek',
  updated_at=now()
WHERE id='mg-k10';

-- ── Source documentation (governance rule 5 — one row per claim per source) ───
INSERT INTO drug_sources
 (drug_id,drug_name,claim_type,claim_value,source_url,source_type,source_domain,content_confirms_claim,confidence,added_by,session_label)
VALUES
 ('abs-101','ABS-101','mechanism','anti-TL1A monoclonal antibody (IBD)','https://investors.absci.com/news-releases/news-release-details/absci-announces-first-participants-dosed-phase-1-clinical-trial','company_ir','investors.absci.com',true,'confirmed','claude-drugcode-review','whitespace-2026-06-06'),
 ('bbt001','BBT001','company_pipeline','Bambusa Therapeutics — IL-4Rα×IL-31 bispecific','https://bambusatx.com/bambusa-therapeutics-announces-first-subject-dosed-in-phase-1-clinical-trial-of-bbt001-a-novel-multi-targeting-half-life-extended-bispecific-antibody-for-the-treatment-of-atopic-dermatitis-and-other/','company_ir','bambusatx.com',true,'confirmed','claude-drugcode-review','whitespace-2026-06-06'),
 ('bbt001','BBT001','mechanism','IL-4Rα × IL-31 bispecific antibody','https://www.dermatologytimes.com/view/dual-il-4r-il-31-blockade-advances-into-patient-trials','news','dermatologytimes.com',true,'confirmed','claude-drugcode-review','whitespace-2026-06-06'),
 ('bel512','BEL512','company_pipeline','Belenos Biosciences (originator) + Keymed Biosciences (China partner) — TSLP×IL-13','https://www.businesswire.com/news/home/20251110761345/en/Belenos-Pipeline-Updates-First-Clinical-Data-from-Lead-Asset-BEL512','press_release','businesswire.com',true,'confirmed','claude-drugcode-review','whitespace-2026-06-06'),
 ('bel512','BEL512','mechanism','TSLP × IL-13 long-acting bispecific antibody (=CM512)','https://www.biospace.com/press-releases/belenos-pipeline-updates-first-clinical-data-from-lead-asset-bel512-a-long-lasting-bispecific-targeting-tslp-and-il-13-second-asset-bel336-a-first-in-class-long-acting-bispecific-targeting-ox40l-and-il-13-phase-1-to-start-1q2026','press_release','biospace.com',true,'confirmed','claude-drugcode-review','whitespace-2026-06-06'),
 ('ky1044','KY1044','company_pipeline','Kymab (originator, acq. Sanofi 2021) — anti-ICOS alomfilimab, oncology','https://clinicaltrials.gov/study/NCT03829501','ct_gov','clinicaltrials.gov',true,'confirmed','claude-drugcode-review','whitespace-2026-06-06'),
 ('ky1044','KY1044','mechanism','anti-ICOS antibody (alomfilimab); target corrected from OX40L (=KY1005/amlitelimab)','https://adisinsight.springer.com/drugs/800054070','other','adisinsight.springer.com',true,'confirmed','claude-drugcode-review','whitespace-2026-06-06'),
 ('mg-k10','MG-K10','company_pipeline','Mabgeek Biotech — long-acting anti-IL-4Rα mAb (comekibart)','https://www.prnewswire.com/news-releases/chime-biologics-and-mabgeek-achieve-mg-k10-ppq-milestone-advancing-atopic-dermatitis-and-asthma-therapies-antibody-drug-mg-k10-late-stage-clinical-trials-and-commercialization-302341683.html','press_release','prnewswire.com',true,'confirmed','claude-drugcode-review','whitespace-2026-06-06');

COMMIT;
