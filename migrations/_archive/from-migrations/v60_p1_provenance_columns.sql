-- =============================================================================
-- v60_p1_provenance_columns.sql
-- P1 Schema Fix: Provenance tracking columns across all intelligence tables
-- Adds enrichment_run_id, updated_at, source_url, confidence where missing
-- Also creates catalyst_calendar table and adds economic terms to deals
-- Applied: 2026-05-28
-- =============================================================================

-- BLOCK 1: drug_targets provenance
-- (source_url, updated_at already exist; adding enrichment_run_id + confidence)
ALTER TABLE drug_targets
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS confidence TEXT DEFAULT 'model' CHECK (confidence IN ('verified', 'model', 'inferred'));
UPDATE drug_targets SET updated_at = NOW() WHERE updated_at IS NULL;

-- BLOCK 2: drug_indications provenance
-- (source_url, updated_at already exist; adding enrichment_run_id + confidence)
ALTER TABLE drug_indications
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS confidence TEXT DEFAULT 'model' CHECK (confidence IN ('verified', 'model', 'inferred'));
UPDATE drug_indications SET updated_at = NOW() WHERE updated_at IS NULL;

-- BLOCK 3: drug_pk_parameters provenance
-- (source_url, updated_at already exist; adding enrichment_run_id)
ALTER TABLE drug_pk_parameters
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;
UPDATE drug_pk_parameters SET updated_at = NOW() WHERE updated_at IS NULL;

-- BLOCK 4: drug_pd_parameters provenance
-- (source_url already exists; adding enrichment_run_id + updated_at)
ALTER TABLE drug_pd_parameters
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
UPDATE drug_pd_parameters SET updated_at = NOW() WHERE updated_at IS NULL;

-- BLOCK 5: drug_biomarkers provenance
-- (source_url already exists; adding enrichment_run_id + updated_at)
ALTER TABLE drug_biomarkers
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
UPDATE drug_biomarkers SET updated_at = NOW() WHERE updated_at IS NULL;

-- BLOCK 6: non_responder_profiles provenance
-- (source_url already exists; adding enrichment_run_id + updated_at)
ALTER TABLE non_responder_profiles
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
UPDATE non_responder_profiles SET updated_at = NOW() WHERE updated_at IS NULL;

-- BLOCK 7: clinical_evidence_items provenance
-- (source_url already exists; adding enrichment_run_id + updated_at)
ALTER TABLE clinical_evidence_items
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
UPDATE clinical_evidence_items SET updated_at = NOW() WHERE updated_at IS NULL;

-- BLOCK 8: drug_competitive_scores provenance
-- (source_url, updated_at already exist; adding enrichment_run_id + model_version)
ALTER TABLE drug_competitive_scores
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS model_version TEXT;

-- BLOCK 9: drug_validation_results provenance
-- (source_url, updated_at, confidence already exist; adding enrichment_run_id)
ALTER TABLE drug_validation_results
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;

-- BLOCK 10: governance_violations provenance
ALTER TABLE governance_violations
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL;

-- BLOCK 11: payer_tpp_criteria provenance
-- (source_url already exists; adding enrichment_run_id + updated_at)
ALTER TABLE payer_tpp_criteria
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
UPDATE payer_tpp_criteria SET updated_at = NOW() WHERE updated_at IS NULL;

-- BLOCK 12: portfolio_conflict_matrix provenance
ALTER TABLE portfolio_conflict_matrix
  ADD COLUMN IF NOT EXISTS enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
UPDATE portfolio_conflict_matrix SET updated_at = NOW() WHERE updated_at IS NULL;

-- BLOCK 13: CREATE catalyst_calendar table (G-08, P1)
CREATE TABLE IF NOT EXISTS catalyst_calendar (
    id BIGSERIAL PRIMARY KEY,
    drug_id TEXT REFERENCES drugs(id) ON DELETE CASCADE,
    company_id TEXT REFERENCES companies(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'trial_readout', 'conference_presentation', 'regulatory_decision',
        'pdufa_date', 'ipo', 'deal_announcement', 'partnership_announcement',
        'phase_start', 'phase_completion', 'data_cutoff', 'earnings_call'
    )),
    event_name TEXT NOT NULL,
    expected_date DATE,
    expected_quarter TEXT,
    conference TEXT,
    description TEXT,
    strategic_significance TEXT CHECK (strategic_significance IN ('P0', 'P1', 'P2', 'watch')),
    ailux_impact TEXT,
    source_url TEXT,
    confidence TEXT DEFAULT 'model' CHECK (confidence IN ('verified', 'model', 'inferred')),
    enrichment_run_id UUID REFERENCES enrichment_runs(id) ON DELETE SET NULL,
    is_past BOOLEAN DEFAULT FALSE,
    actual_date DATE,
    actual_outcome TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS cc_drug_id_idx ON catalyst_calendar(drug_id);
CREATE INDEX IF NOT EXISTS cc_company_id_idx ON catalyst_calendar(company_id);
CREATE INDEX IF NOT EXISTS cc_expected_date_idx ON catalyst_calendar(expected_date);
CREATE INDEX IF NOT EXISTS cc_event_type_idx ON catalyst_calendar(event_type);
CREATE INDEX IF NOT EXISTS cc_is_past_idx ON catalyst_calendar(is_past) WHERE is_past = FALSE;

-- BLOCK 13b: Seed catalyst_calendar with known events
INSERT INTO catalyst_calendar (drug_id, company_id, event_type, event_name, expected_date, expected_quarter, description, strategic_significance, ailux_impact, source_url, confidence)
VALUES
('fg-m701', 'abbvie', 'trial_readout', 'ABBV-701 Phase 1 Safety/PK Readout',
 '2026-10-01', 'Q4 2026',
 'Phase 1 first-in-human dose escalation readout for ABBV-701 (TL1A mAb). AbbVie-licensed from FutureGen. P0 BD timing constraint: do not target AbbVie for TL1A bispecific BD until after this readout.',
 'P0',
 'Canonical deal sequencing constraint. AbbVie cannot be approached for TL1A bispecific partnership until Phase 1 data de-risks or disproves their internal asset. Monitor for dose escalation completion, SAE signals, and any early efficacy hints in UC/CD.',
 'https://clinicaltrials.gov/search?term=ABBV-701',
 'model'),
('duvakitug', 'sanofi', 'trial_readout', 'duvakitug Phase 3 UC Readout',
 NULL, 'H2 2026',
 'Phase 3 readout for duvakitug (TL1A x IL-23p19 bispecific) in UC. Most direct competitive overlap with Ailux XPF005 mechanism.',
 'P0',
 'Highest-priority competitive readout. Positive data validates TL1A x IL-23 bispecific mechanism and increases market value of Ailux asset. Negative data requires mechanistic interpretation. Watch endpoint selection, patient population, and safety profile vs mono agents.',
 'https://clinicaltrials.gov/search?term=duvakitug',
 'model'),
('tulisokibart', 'merck', 'trial_readout', 'tulisokibart Phase 3 IBD Readout',
 NULL, 'H1 2027',
 'Phase 3 readout for tulisokibart (PRA023, TL1A mAb) in UC and CD. Merck-acquired via Prometheus Biosciences ($10.8B, 2023). Most advanced TL1A mono agent.',
 'P0',
 'Merck Phase 3 data sets precedent for TL1A clinical bar. Positive: validates target, raises Ailux bispecific valuation. Watch whether Merck separately pursues TL1A bispecific or considers in-licensing Ailux XPF005 to complement mono program.',
 'https://clinicaltrials.gov/search?term=tulisokibart',
 'model'),
('afimkibart', 'roche', 'trial_readout', 'Afimkibart Phase 3 UC/CD Readout',
 NULL, 'H2 2027',
 'Phase 3 readout for afimkibart (RG7880, anti-TL1A mAb) in UC and Crohn''s disease.',
 'P1',
 'Roche already has RO7837195 (TL1A x IL-23 bispecific) in Phase 2. Afimkibart Phase 3 data will inform whether Roche pursues bispecific as portfolio expansion or replacement.',
 'https://clinicaltrials.gov/search?term=afimkibart',
 'model'),
('ro7837195', 'roche', 'trial_readout', 'RO7837195 Phase 2 Proof-of-Concept Readout',
 NULL, 'H1 2027',
 'Phase 2 readout for RO7837195 (Roche TL1A x IL-23p19 bispecific) in IBD. Direct mechanism competitor to Ailux XPF005.',
 'P0',
 'Direct competitive overlap with XPF005. Watch: efficacy vs duvakitug, dose/frequency, whether Roche positions this alongside or instead of afimkibart mono. Positive data reduces Ailux differentiation window; watch for safety signals or subgroup advantages.',
 'https://clinicaltrials.gov/search?term=RO7837195',
 'model'),
('spy002', 'spyre', 'trial_readout', 'SPY002 Phase 2 TL1A Readout',
 NULL, 'H2 2026',
 'Phase 2 readout for SPY002 (anti-TL1A mAb, half-life extended) in UC/CD.',
 'P1',
 'Spyre developing multiple IBD assets simultaneously (SPY001 a4b7, SPY002 TL1A, SPY003 IL-23). SPY002 data informs Spyre TL1A confidence and whether combination approach is viable vs a bispecific. Potential BD target for Ailux bispecific.',
 'https://clinicaltrials.gov/search?term=SPY002',
 'model'),
('spy072', 'spyre', 'trial_readout', 'SPY072 Phase 2 TL1A x IL-23 Bispecific Readout',
 NULL, 'H2 2026',
 'Phase 2 proof-of-concept for SPY072 (TL1A x IL-23 bispecific) in IBD. Spyre own bispecific program, direct mechanism competitor.',
 'P0',
 'Most direct competitive comparison to Ailux XPF005 after duvakitug. Same mechanism, same indication. Watch construct design differences, dosing interval claims, Phase 2 endpoints. Negative data or DLT opens BD opportunity; positive accelerates Spyre toward independent filing.',
 'https://clinicaltrials.gov/search?term=SPY072',
 'model'),
('xmab942', 'xencor', 'trial_readout', 'XmAb942 Phase 2 TL1A x IL-23 Readout',
 NULL, 'H1 2027',
 'Phase 2 readout for XmAb942 (anti-TL1A x IL-23p19 bispecific) in UC/CD. Xencor platform-derived bispecific.',
 'P1',
 'Xencor known BD partner. XmAb942 positive data may drive Xencor to seek larger pharma partner. Watch for conference presentations at DDW or ECCO.',
 'https://clinicaltrials.gov/search?term=XmAb942',
 'model'),
('mdr-018', 'mirador', 'trial_readout', 'MDR-018 Phase 2 TL1A Readout',
 NULL, 'H1 2027',
 'Phase 2 readout for MDR-018 (anti-TL1A mAb) in UC/CD. Mirador Therapeutics TL1A program.',
 'P1',
 'Mirador has MT-251 in Phase 1 (bispecific) and MDR-018 (mono). Track whether Mirador builds towards bispecific or mono strategy. Potential BD target.',
 'https://clinicaltrials.gov/search?term=MDR-018',
 'model'),
('mt-251', 'mirador', 'trial_readout', 'MT-251 Phase 1 Safety/PK Readout',
 NULL, 'H2 2026',
 'Phase 1 first-in-human for MT-251 (Mirador bispecific TL1A program) in IBD.',
 'P1',
 'Mirador running both mono (MDR-018) and bispecific (MT-251) TL1A programs simultaneously. Phase 1 completion and biomarker signals will inform platform strategy.',
 'https://clinicaltrials.gov/search?term=MT-251',
 'model'),
('risankizumab', 'abbvie', 'regulatory_decision', 'Risankizumab Label Expansion — CD/Pediatric',
 NULL, 'H2 2026',
 'Potential label expansion or new sNDA for risankizumab in CD perioperative setting or pediatric IBD.',
 'P2',
 'Risankizumab IBD franchise expansion strengthens AbbVie rationale for adding TL1A dimension via ABBV-701 or bispecific partnership post-Oct 2026 constraint.',
 'https://www.abbvie.com/our-science/pipeline.html',
 'model'),
('mirikizumab', 'lilly', 'trial_readout', 'Mirikizumab Phase 3 Crohn''s Disease Readout',
 NULL, 'H1 2026',
 'Phase 3 readout for mirikizumab (Omvoh, IL-23p19 mAb) in Crohn''s disease. Already approved in UC.',
 'P1',
 'Positive CD data validates IL-23 in CD and broadens Lilly IBD footprint. Increases Lilly strategic interest in TL1A combinations/bispecifics to differentiate from AbbVie risankizumab.',
 'https://clinicaltrials.gov/search?term=mirikizumab',
 'model'),
('vtx002', 'astrazeneca', 'trial_readout', 'VTX002 Phase 2 TL1A Readout',
 NULL, 'H2 2026',
 'Phase 2 readout for VTX002 (anti-TL1A mAb) in UC/CD. Ventyx Biosciences asset, acquired by AstraZeneca 2024.',
 'P1',
 'AstraZeneca with two TL1A assets (VTX002 + tozorakimab) may pursue bispecific strategy. Watch for AZ internal bispecific program announcement or BD move.',
 'https://clinicaltrials.gov/search?term=VTX002',
 'model'),
('tozorakimab', 'astrazeneca', 'trial_readout', 'Tozorakimab Phase 3 IBD Readout',
 NULL, 'H2 2026',
 'Phase 3 readout for tozorakimab (anti-IL-33 mAb) in IBD indication.',
 'P2',
 'Tozorakimab positive IBD data validates IL-33/ST2 pathway. If combined with TL1A (VTX002), AstraZeneca could pursue bispecific strategy targeting both pathways.',
 'https://clinicaltrials.gov/search?term=tozorakimab',
 'model')
ON CONFLICT DO NOTHING;

-- BLOCK 14: ALTER deals — add economic terms (G-09)
ALTER TABLE deals
  ADD COLUMN IF NOT EXISTS upfront_value NUMERIC,
  ADD COLUMN IF NOT EXISTS total_potential_value NUMERIC,
  ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'USD',
  ADD COLUMN IF NOT EXISTS milestone_structure JSONB,
  ADD COLUMN IF NOT EXISTS royalty_rate_low NUMERIC,
  ADD COLUMN IF NOT EXISTS royalty_rate_high NUMERIC,
  ADD COLUMN IF NOT EXISTS geographic_rights TEXT,
  ADD COLUMN IF NOT EXISTS economic_terms_source TEXT,
  ADD COLUMN IF NOT EXISTS economic_terms_verified BOOLEAN DEFAULT FALSE;
