-- ============================================================
-- Ailux BD Platform — Schema Migration v2
-- Purpose: Enable rich per-company detail rows, drug popup cards,
--          and overnight Claude API enrichment pipeline
-- Run in Supabase SQL editor: https://supabase.com/dashboard/project/tghntyofptvfhmtchwcv/sql
-- Date: 2026-05-18
-- ============================================================

-- ── 1. company_profiles — area-scoped narrative content ──────────────────────
-- Stores the rich text blocks for each (company × disease area) combination.
-- A company can have separate profiles for TL1A·IBD, TSLP·Asthma, etc.
-- This is the primary target for overnight Claude API enrichment.

CREATE TABLE IF NOT EXISTS company_profiles (
  company_id         TEXT   NOT NULL REFERENCES companies(id)    ON DELETE CASCADE,
  area_id            TEXT   NOT NULL REFERENCES disease_areas(id) ON DELETE CASCADE,
  platform_summary   TEXT,   -- 2–4 sentence clinical overview of the company in this area
  bd_summary         TEXT,   -- 2–4 sentence BD/deal strategy narrative
  key_risk           TEXT,   -- 1–2 sentence primary risk
  why_it_matters     TEXT,   -- 1–2 sentence Ailux-relevance statement
  pipeline_url       TEXT,   -- link to public pipeline page
  research_sources   JSONB,  -- [{label, url}] array of sources used in last enrichment
  last_enriched_at   TIMESTAMPTZ,
  enriched_by        TEXT DEFAULT 'manual',  -- 'manual' | 'claude-enrichment-v1'
  created_at         TIMESTAMPTZ DEFAULT NOW(),
  updated_at         TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (company_id, area_id)
);

CREATE TRIGGER trg_company_profiles_updated
  BEFORE UPDATE ON company_profiles
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

ALTER TABLE company_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY anon_read_company_profiles ON company_profiles FOR SELECT TO anon USING (true);
-- Service role (enrichment pipeline) gets full write access via service key


-- ── 2. ALTER drugs — add clinical detail columns ─────────────────────────────
-- These columns power the drug pill popup cards (like the Spyre hover cards).
-- Enrichment pipeline fills these from CT.gov + Claude synthesis.

ALTER TABLE drugs
  ADD COLUMN IF NOT EXISTS route           TEXT,           -- 'SC' | 'IV' | 'SC/IV'
  ADD COLUMN IF NOT EXISTS dosing_type     TEXT,           -- 'Induction' | 'Maintenance' | 'Induction + Maintenance'
  ADD COLUMN IF NOT EXISTS drug_format     TEXT,           -- 'mAb' | 'bispecific' | 'nanobody' | 'YTE-modified mAb'
  ADD COLUMN IF NOT EXISTS is_combo        BOOLEAN DEFAULT FALSE,  -- TRUE = co-administered combo (not bispecific)
  ADD COLUMN IF NOT EXISTS dosing_schedule TEXT,           -- e.g. 'Q3M–Q6M SC'
  ADD COLUMN IF NOT EXISTS indication_short TEXT,          -- short label: 'UC · CD'
  ADD COLUMN IF NOT EXISTS phase_display   TEXT,           -- display string: 'Phase 3' / 'Phase 1/2'
  ADD COLUMN IF NOT EXISTS half_life_note  TEXT,           -- e.g. '~74 days (XTEND-Fc)'
  ADD COLUMN IF NOT EXISTS vs_ailux        TEXT,           -- how this drug compares to Ailux asset
  ADD COLUMN IF NOT EXISTS color_hex       TEXT,           -- '#0d9488' — pill accent color
  ADD COLUMN IF NOT EXISTS light_bg_hex    TEXT,           -- '#f0fdfa' — pill background
  ADD COLUMN IF NOT EXISTS sort_order      INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS sources_json    JSONB;          -- [{label,url}] verification sources


-- ── 3. ALTER trials — add display fields ─────────────────────────────────────
-- trial_name and n_enrollment were missing from the original schema.

ALTER TABLE trials
  ADD COLUMN IF NOT EXISTS trial_name    TEXT,         -- e.g. 'STARSCAPE UC — induction'
  ADD COLUMN IF NOT EXISTS n_enrollment  INTEGER,      -- planned enrollment N
  ADD COLUMN IF NOT EXISTS pcd_label     TEXT;         -- human-readable PCD: 'May 2028' or 'Part A: Apr 2026'


-- ── 4. ALTER deals — add company_id FK ───────────────────────────────────────
-- Allows direct company→deals lookup without string matching on from_company/to_company.

ALTER TABLE deals
  ADD COLUMN IF NOT EXISTS company_id TEXT REFERENCES companies(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_deals_company ON deals(company_id);
CREATE INDEX IF NOT EXISTS idx_deals_company_area ON deals(company_id, area_id);


-- ── 5. Indexes for new tables ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_company_profiles_area   ON company_profiles(area_id);
CREATE INDEX IF NOT EXISTS idx_company_profiles_enrich ON company_profiles(last_enriched_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_trials_drug_area        ON trials(drug_id);
CREATE INDEX IF NOT EXISTS idx_drugs_sort              ON drugs(sort_order ASC);


-- ── 6. Helper view — company_area_detail ─────────────────────────────────────
-- Joins companies + company_profiles for a given area.
-- Frontend can query: GET /rest/v1/company_area_detail?area_id=eq.tl1a

CREATE OR REPLACE VIEW company_area_detail AS
  SELECT
    c.id            AS company_id,
    c.name,
    c.ticker,
    c.company_type,
    c.insight_text,
    c.ailux_angle,
    ca.area_id,
    cp.platform_summary,
    cp.bd_summary,
    cp.key_risk,
    cp.why_it_matters,
    cp.pipeline_url,
    cp.last_enriched_at,
    cp.enriched_by
  FROM companies c
  JOIN company_areas   ca ON ca.company_id = c.id
  LEFT JOIN company_profiles cp ON cp.company_id = c.id AND cp.area_id = ca.area_id;

-- Grant anon read on the view
GRANT SELECT ON company_area_detail TO anon;


-- ── 7. Seed: company_profiles for all TL1A PI table companies ────────────────
-- Initial data sourced from TL1A_PROGRAMS static array in index.html (May 2026).
-- Enrichment pipeline will overwrite these with fresher Claude-synthesized text.

INSERT INTO company_profiles (company_id, area_id, platform_summary, bd_summary, key_risk, why_it_matters, pipeline_url, enriched_by)
VALUES

-- Sanofi / Teva
('sanofi', 'tl1a',
 'Duvakitug (TEV-48574) is a monospecific anti-TL1A mAb developed by Teva and co-developed with Sanofi. Phase 2b in UC demonstrated 48% composite clinical remission at Wk 14 — the highest TL1A monotherapy efficacy signal reported. Phase 3 is the largest TL1A program: STARSCAPE (UC, N=1,651) and SUNSCAPE (CD, N=1,731), totaling ~3,382 patients across 4 trials. Sanofi separately licensed HXN-1003, Earendil''s TL1A×IL-23p19 bispecific ($125M upfront, Apr 2025), demonstrating conviction in both mono and bispecific TL1A strategies.',
 'Sanofi/Teva co-development and co-commercialization of duvakitug; financial split undisclosed. Blackstone Life Sciences committed $400M (Apr 2025) financing duvakitug Phase 3 in exchange for royalties. In parallel, Sanofi licensed HXN-1003 ($125M upfront, $1.845B total) — making Sanofi the only company with TWO TL1A programs (mono + bispecific) and representing the largest combined TL1A BD commitment in the industry. Primary deal window for Ailux: post-Phase 3 data (2028–2029) or bispecific differentiation argument pre-data.',
 'Largest Phase 3 program in the class but latest readouts (UC primary May 2028, CD Aug 2029). Merck ATLAS-UC data (Nov 2026) lands 2+ years earlier and may shift market positioning before duvakitug reads out.',
 'Sets the monotherapy efficacy ceiling (48% UC remission) that Ailux and other bispecifics must beat. Sanofi''s dual investment in both mono (duvakitug) and bispecific (HXN-1003) validates the TL1A×IL-23 combination hypothesis at the highest BD level.',
 'https://www.sanofi.com/en/science-and-innovation/pipeline',
 'manual'),

-- Spyre Therapeutics (spyre-mono maps to Spyre TL1A mono program)
('spyre-mono', 'tl1a',
 'Spyre Therapeutics (NASDAQ: SYRE) is an Agenus IBD spinout (Feb 2024) running a 7-program IBD and rheumatic disease platform with YTE-Fc modified antibodies. SPY002 (anti-TL1A, Ph2) and SPY001 (anti-α4β7, Ph2 data April 2026: RHI −9.2 pts) are in SKYLINE, a platform Phase 2 trial (NCT07012395) testing all three monotherapies and three combinations in UC. SPY072 is a separate TL1A program for RA/PsA/axSpA in the SKYWAY basket trial. All antibodies target Q3M–Q6M SC dosing via extended half-life.',
 'No pharma partners — deliberate pre-partnering strategy to advance all programs through Phase 2 data. $783M raised (Series A: Farallon, Foresite, RA Capital + ATM) provides cash runway into H2 2028. Agenus retained ~25% equity plus tiered royalties. Primary BD window: 2027 SKYLINE combination readouts (SPY120, SPY130, SPY230). Deal optionality includes single-program licensing, indication-specific co-development, or full platform acquisition.',
 '7-program parallel execution risk. SKYLINE Part B combination data (2027) could show mono suffices, reducing combination asset value. YTE safety profile still being established in IBD populations.',
 'Only company with YTE-modified antibodies across TL1A, α4β7, and IL-23 in IBD plus TL1A in rheumatic diseases. SKYLINE directly tests combination vs. mono — most informative IBD platform study ever designed. April 2026 SPY001 data already suggests best-in-class potential.',
 'https://www.spyre.com/pipeline',
 'manual'),

-- Spyre SPY230 combo arm
('spyre-230', 'tl1a',
 'SPY230 is Spyre''s TL1A + IL-23 dual-blockade combination program — the SPY002 + SPY003 co-administration arm in SKYLINE Part B (NCT07012395). This is a rare direct test of combination vs. mono TL1A and IL-23 blockade within the same platform study. Part B enrollment opened in 2026; data expected 2027. SPY003 Part A IL-23 monotherapy data expected Q3 2026, establishing the IL-23 monotherapy ceiling before combination data land.',
 'SPY230 is funded under Spyre''s $783M platform raise — no separate deal structure. SKYLINE Part B combination data (2027) represent the primary evidence base for whether TL1A+IL-23 co-blockade provides additive benefit over either mono. A positive result would strongly validate the bispecific hypothesis and create significant M&A/partnership interest in Spyre as well as Ailux.',
 'If combination data show no additive benefit over mono TL1A or IL-23 alone, bispecific valuations across the class (including Ailux) would be negatively affected.',
 'SKYLINE is the definitive head-to-head test of the bispecific hypothesis. SPY230 2027 data will be the most important clinical evidence set for valuing Ailux''s TL1A×IL-23 asset.',
 'https://www.spyre.com/pipeline',
 'manual'),

-- Xencor XmAb942
('xencor-942', 'tl1a',
 'XmAb942 is an XTEND-Fc anti-TL1A mAb with a ~74-day half-life confirmed in Phase 1 healthy volunteers (April 2025). The XENITH-UC study (NCT06619990) is a combined Phase 1/2b trial in UC (N=270) with primary completion April 2028. Xencor is also advancing XmAb412, a TL1A×IL-23p19 bispecific using the same XTEND platform, with FIH planned Q3 2026.',
 'No pharma partner announced — Xencor self-funding both XmAb942 (Ph2b) and XmAb412 (FIH) in parallel. If XENITH-UC interim data (YE 2026) are strong, Xencor is well-positioned to partner both assets simultaneously. XTEND-Fc has existing licensing relationships with AstraZeneca and Amgen, providing potential partnership pathways.',
 'No partner backing; funding two simultaneous programs (Ph2b mono + pre-clinical/FIH bispecific) creates capital allocation tension. If Ph2b efficacy is modest, ultra-long PK alone may not justify premium partnering interest.',
 '74-day half-life — the longest in the TL1A class. Q13W+ dosing could differentiate on convenience. Running both mono and bispecific simultaneously provides unique data optionality.',
 'https://www.xencor.com/pipeline/',
 'manual'),

-- Mirador Therapeutics
('mirador', 'tl1a',
 'Mirador Therapeutics is developing MT-251, an FcRn-recycling TL1A×IL-23p19 bispecific — the most clinically advanced dedicated bispecific in this class. Phase 1 FIH (NCT07423299) in healthy volunteers started Jan 2026, N=70, primary completion March 2027. Backed by A16z Bio, Foresite Capital, and Atlas Venture.',
 'No pharma partner — actively seeking. Pre-IND deal comps set the floor: Simcere→BI €42M upfront (Jan 2026), Earendil→Sanofi $125M upfront (Apr 2025). Mirador Phase 1 safety/PK data (2026–2027) could trigger a major licensing event. Phase 1 data are the primary BD catalyst.',
 'First-in-human — Phase 1 safety and PK entirely unknown. FcRn-recycling bispecific format adds regulatory and manufacturing complexity vs. standard IgG. No pharma partner backing creates capital risk.',
 'Most advanced dedicated TL1A×IL-23p19 bispecific in the clinic. Phase 1 data (2027) will set the first human PK/safety benchmark for this bispecific format — primary deal-watch target for 2026–2027.',
 NULL,
 'manual'),

-- Simcere / Boehringer Ingelheim
('simcere', 'tl1a',
 'SIM0709 is a long-acting SC IgG bispecific targeting TL1A×IL-23p19, licensed to Boehringer Ingelheim in Jan 2026 (€42M upfront, €1.05B total) before first-in-human dosing — the deal was executed on preclinical data alone. FIH expected H2 2026. Simcere retains all Greater China rights. BI brings deep IBD infrastructure (10+ ongoing IBD trials), global manufacturing scale, and commercial reach.',
 'BI deal fully funds the program — low capital risk for Simcere. BI''s €42M pre-IND investment sets the deal floor for TL1A bispecifics and signals institutional conviction in the mechanism. Simcere retaining China rights means a separate China-specific deal could still emerge.',
 'BI''s deep IBD experience means aggressive timelines and high competitive pressure. Pre-IND deal comp at €42M sets a high market expectation for other bispecific deals including Ailux.',
 'Sets the pre-IND deal floor for TL1A×IL-23p19 bispecifics at €42M upfront / €1.05B total. BI partnership is the strongest institutional validation of the bispecific approach from a commercial-stage pharma.',
 NULL,
 'manual'),

-- Caldera / Qyuns
('caldera', 'tl1a',
 'CLD-423 (QX030N) is a TL1A×IL-23p19 bispecific developed by Qyuns Therapeutics. Caldera is the US vehicle holding global ex-China rights. First subjects dosed January 2026. No ClinicalTrials.gov registration as of May 2026.',
 'Deal structure illustrates the China-to-global commercialization model: Qyuns sold ex-China rights to Caldera for $10M + ~25% equity and up to $545M milestones. Small company, limited capital vs. BI-backed SIM0709. Seeking global pharma partner.',
 'Caldera is a small company with limited capital and no big-pharma backing. Phase 1 data quality and timeline are key unknowns vs. better-capitalized competitors.',
 'Deal structure ($10M + equity, $545M total) illustrates how Chinese companies monetize TL1A bispecifics globally while retaining China rights. FIH Jan 2026 puts it ahead of several pre-IND competitors.',
 NULL,
 'manual'),

-- Earendil / Helixon (Sanofi deal)
('earendil', 'tl1a',
 'HXN-1003 is an AI-designed tetravalent (2+2) bispecific targeting TL1A and IL-23p19, licensed to Sanofi (Apr 2025, $125M upfront, $1.845B total) — the highest-value preclinical TL1A deal ever and one of the largest preclinical IBD deals in history. IND filing expected 2026, FIH 2026–2027.',
 '$125M upfront at preclinical stage with Sanofi: highest pre-IND deal in TL1A class. Represents Sanofi''s second TL1A investment (alongside duvakitug) and the strongest signal of conviction in dual TL1A+IL-23 blockade from a major pharma.',
 'Tetravalent (2+2) format — more complex manufacturing and potentially higher immunogenicity vs. standard bispecific formats. Pre-IND stage with no human data.',
 '$125M preclinical deal with Sanofi is the highest bar set in the TL1A space. Sets Ailux''s deal expectation ceiling for a bispecific program with Phase 1 data: significantly above $125M upfront.',
 NULL,
 'manual'),

-- Xencor XmAb412
('xencor-412', 'tl1a',
 'XmAb412 is Xencor''s TL1A×IL-23p19 bispecific using the XTEND-Fc half-life extension platform validated in XmAb942 (74-day t½ in Phase 1). FIH in healthy volunteers planned Q3 2026. Preclinical data presented at DDW 2026.',
 'No pharma partner — Xencor self-funding. XTEND platform already licensed to AstraZeneca and Amgen in other indications. If XmAb942 Ph2b interim data (YE 2026) are strong, XmAb412 deal interest could follow rapidly.',
 'No partner backing while funding two programs simultaneously. If XmAb942 Ph2b is modest, XmAb412 loses its primary de-risking argument.',
 'XTEND platform already yields 74-day t½ in XmAb942 — strongest half-life data in TL1A class. Bispecific version targets same ultra-long PK advantage at Q13W+ dosing.',
 'https://www.xencor.com/pipeline/',
 'manual'),

-- LaNova / Zymeworks
('lanova', 'tl1a',
 'LQ080 (ZW191) is a VHH nanobody-based TL1A×IL-23p19 bispecific developed by LaNova, partnered to Zymeworks for ex-China rights. Phase 1 appears ongoing (likely China CDE registration). VHH format is smaller than conventional IgG bispecifics, with potential tissue penetration advantages.',
 'LaNova and Zymeworks are seeking a global pharma partner. No big-pharma deal announced. VHH format is an emerging platform with limited clinical validation in IBD.',
 'VHH nanobody format is clinically unvalidated in IBD — unknown immunogenicity risk vs. standard IgG. Tissue penetration advantage is theoretical in the IBD context.',
 'Unique molecular format (smallest in TL1A class). Seeking global partner — could be acquired before Phase 2 at significant premium if Phase 1 data are clean.',
 NULL,
 'manual')

ON CONFLICT (company_id, area_id) DO UPDATE SET
  platform_summary  = EXCLUDED.platform_summary,
  bd_summary        = EXCLUDED.bd_summary,
  key_risk          = EXCLUDED.key_risk,
  why_it_matters    = EXCLUDED.why_it_matters,
  pipeline_url      = EXCLUDED.pipeline_url,
  enriched_by       = EXCLUDED.enriched_by,
  updated_at        = NOW();


-- ── 8. Seed: company_id on existing deals where from_company matches ──────────
-- Maps known company name strings to their Supabase IDs.
-- Run after seeding to wire up existing deal rows.

UPDATE deals SET company_id = 'sanofi'     WHERE lower(from_company) LIKE '%sanofi%' OR lower(to_company) LIKE '%sanofi%';
UPDATE deals SET company_id = 'sanofi'     WHERE lower(from_company) LIKE '%teva%' OR lower(to_company) LIKE '%teva%';
UPDATE deals SET company_id = 'spyre-mono' WHERE lower(from_company) LIKE '%spyre%' OR lower(to_company) LIKE '%spyre%';
UPDATE deals SET company_id = 'xencor-942' WHERE lower(from_company) LIKE '%xencor%' OR lower(to_company) LIKE '%xencor%';
UPDATE deals SET company_id = 'mirador'    WHERE lower(from_company) LIKE '%mirador%' OR lower(to_company) LIKE '%mirador%';
UPDATE deals SET company_id = 'simcere'    WHERE lower(from_company) LIKE '%simcere%' OR lower(to_company) LIKE '%simcere%';
UPDATE deals SET company_id = 'earendil'   WHERE lower(from_company) LIKE '%earendil%' OR lower(from_company) LIKE '%helixon%';


-- ── Done ─────────────────────────────────────────────────────────────────────
-- Next step: Run scripts/company_enrichment.py --area tl1a
-- to populate all fields with overnight Claude API research.
