-- APPLIED 2026-06-19: seed the remaining 6 asset_programs (TSLP, IL-4Rα×TSLP,
-- IL-4Rα×OX40L, IGF1R×TSHR, FcRn, BCMA×CD19×CD3). Content migrated verbatim from
-- the hardcoded ailux-card blocks in index.html. Codes ALX002/ALX005 are real
-- (app.js asset switcher); the 4 platform concepts use descriptive ALX-* codes.
-- target_pair_id set only where a target_pairs row exists (tslp-il33, igf1r-tshr).
-- source_url null = flagged for curation, never fabricated. Idempotent on program_code.

INSERT INTO public.asset_programs
  (program_code, target_pair_id, indication_lead, modality, status, differentiators, updated_at)
VALUES
('ALX-TSLP-IL33', 'tslp-il33', 'Respiratory (asthma / COPD)', 'bispecific', 'preclinical',
 $j$[
  {"label":"Platform Relevance","value":"Cross-indication capability","sub":"Ailux's bispecific engineering platform — extended half-life, novel epitope targeting — is directly transferable from IBD to respiratory indications."},
  {"label":"Differentiation Angle","value":"Long-acting SC format","sub":"Monthly or Q6-week SC dosing would be a meaningful step-up from tezepelumab. Extended half-life is the clearest differentiation for respiratory markets."},
  {"label":"Bispecific Thesis","value":"TSLP×IL-33 dual blockade","sub":"QX031N→Roche deal validates the thesis. A TSLP×IL-33 bispecific with Ailux's extended half-life would have both mechanistic and PK differentiation."},
  {"label":"Partner Pool","value":"Major respiratory pharma","sub":"AZ, Roche, Regeneron/Sanofi, GSK, Novartis are all active in respiratory biologics and would evaluate differentiated alarmin-targeting assets."}
 ]$j$::jsonb, now()),

('ALX-IL4RA-TSLP', NULL, 'Type 2 (AD / asthma / food allergy)', 'bispecific', 'preclinical',
 $j$[
  {"label":"Competitive Position","value":"Upstream + downstream dual block","sub":"TSLP blocks alarmin initiation; IL-4Rα blocks IL-4/IL-13 downstream effector signaling. Covering both nodes eliminates the most common escape mechanisms in type-2 inflammation."},
  {"label":"Commercial Differentiation","value":"Q4W/Q8W vs dupilumab Q2W","sub":"Extended half-life + bispecific format could achieve less-frequent dosing than dupilumab — the most commercially meaningful differentiator in the IL-4Rα space."},
  {"label":"Multi-indication Story","value":"AD → asthma → food allergy","sub":"The atopic march means a TSLP×IL-4Rα bispecific can target patients at risk of progression across multiple type-2 indications — broadening the label strategy."},
  {"label":"BD Angle","value":"Dupilumab inadequate responders","sub":"A defined subpopulation of dupilumab partial responders who have elevated TSLP levels is the clearest registration pathway — enriched, de-risked, and commercially addressable."}
 ]$j$::jsonb, now()),

('ALX-IL4RA-OX40L', NULL, 'Atopic dermatitis', 'bispecific', 'preclinical',
 $j$[
  {"label":"Mechanism","value":"Memory + effector dual block","sub":"OX40L drives memory T cell survival and re-sensitization; IL-4Rα drives acute Th2 effector responses. Dual blockade addresses both chronicity and acute symptoms simultaneously."},
  {"label":"Clinical Target","value":"Dupilumab inadequate responders","sub":"~20–30% of dupilumab patients have inadequate itch control or secondary treatment failure. OX40L blockade may address the underlying memory T cell driver that dupilumab cannot reach."},
  {"label":"Deal Comparables","value":"Amlitelimab via Kymab → Sanofi (2021)","sub":"Sanofi acquired Kymab in 2021 (~$1.1B upfront, up to ~$1.45B with milestones); amlitelimab (KY1005) was the lead asset. An amlitelimab-equivalent in a bispecific format would attract major dermatology BD interest from AbbVie, Pfizer, Lilly, Leo Pharma."},
  {"label":"Format Advantage","value":"Q4W/Q8W SC vs dupilumab Q2W","sub":"Extended half-life bispecific can achieve more convenient dosing than dupilumab Q2W — the primary commercial differentiation in a market where patient compliance is a key driver."}
 ]$j$::jsonb, now()),

('ALX-IGF1R-TSHR', 'igf1r-tshr', 'Thyroid eye disease / Graves'' disease', 'bispecific', 'preclinical',
 $j$[
  {"label":"Mechanism","value":"Dual IGF1R + TSHR receptor block","sub":"Teprotumumab blocks IGF1R on orbital fibroblasts. TSHR cross-signaling amplifies the fibroblast response. A bispecific blocking both receptors simultaneously eliminates the cross-talk escape mechanism."},
  {"label":"Safety Differentiation","value":"SNHL risk reduction","sub":"Teprotumumab is associated with sensorineural hearing loss (~10%). TSHR is expressed on cochlear hair cells; TSHR blockade may reduce the auditory side effect risk. Clinical validation would be a major label advantage."},
  {"label":"Dosing Differentiation","value":"SC + extended half-life vs IV infusions","sub":"Teprotumumab requires 8×IV infusions (specialty pharmacy). SC bispecific with extended half-life achieves home self-administration — transformative for a rare disease where treatment access is a barrier."},
  {"label":"Market Expansion","value":"Graves' Disease (3M US patients)","sub":"TED affects ~60K/yr; Graves' Disease affects ~3M. IGF1R×TSHR bispecific addressing both indications has 10× the patient volume — the key BD angle for why this is not just an orphan TED drug."}
 ]$j$::jsonb, now()),

('ALX005', NULL, 'IgG-mediated autoimmune (gMG / CIDP)', 'bispecific', 'preclinical',
 $j$[
  {"label":"Mechanism","value":"FcRn + disease-specific second arm","sub":"FcRn inhibition depletes pathogenic IgG by 60–85%. Adding a disease-specific second arm (e.g., CD19 for B cell depletion) could achieve both IgG clearance AND long-term B cell suppression for durable remission."},
  {"label":"Albumin Safety","value":"Albumin-sparing design is mandatory","sub":"First-gen FcRn inhibitors had albumin loss. IMVT-1402 redesigned for albumin sparing. Any new FcRn bispecific must demonstrate albumin-sparing in pre-clinical and IND-enabling studies."},
  {"label":"BD Opportunity","value":"Multi-indication platform","sub":"FcRn mechanism applies to 5–7 IgG-mediated autoimmune diseases. A differentiated bispecific with clean safety profile can be sequentially registered across gMG → CIDP → ITP → pemphigus → NMOSD — each adding incremental value."},
  {"label":"Competitive Moat","value":"Second arm differentiates from monoAb FcRn","sub":"argenx, J&J, UCB, Immunovant are all competing with FcRn monoAbs. A bispecific with a disease-specific second arm carves out a differentiated position that monoAb FcRn inhibitors cannot easily replicate."}
 ]$j$::jsonb, now()),

('ALX002', NULL, 'Refractory autoimmune immune reset (SLE / SSc)', 'trispecific', 'preclinical',
 $j$[
  {"label":"Platform Angle","value":"Trispecific antibody vs. CAR-T","sub":"Ailux's antibody engineering platform can target BCMA + CD19 + CD3 in a single trispecific molecule — achieving the same B cell + plasma cell depletion as CAR-T without cell manufacturing, apheresis, or lymphodepletion. This is the 'drug, not cell therapy' differentiation angle."},
  {"label":"Commercial Advantage","value":"Scalable manufacturing","sub":"An antibody trispecific can be manufactured at scale in commercial bioreactors — unlike autologous CAR-T which requires individual patient manufacturing. This dramatically broadens patient access and reduces cost-of-goods."},
  {"label":"Target Patient Population","value":"Severe, refractory autoimmune disease","sub":"SLE, SSc, inflammatory myopathy, refractory MG — patients who have failed 2+ standard lines of therapy and have life-threatening or organ-threatening disease. This is the 'immune reset' population where the risk-benefit of aggressive B cell depletion is most favorable."},
  {"label":"BD Partners","value":"Autoimmune + hematology pharma","sub":"BMS, AbbVie, Roche, J&J, Novartis all have stakes in this space via CAR-T, B cell depletion, or autoimmune platforms. A differentiated trispecific antibody would attract BD interest as a next-generation alternative to CAR-T."}
 ]$j$::jsonb, now())

ON CONFLICT (program_code) DO UPDATE SET
  target_pair_id  = EXCLUDED.target_pair_id,
  indication_lead = EXCLUDED.indication_lead,
  modality        = EXCLUDED.modality,
  status          = EXCLUDED.status,
  differentiators = EXCLUDED.differentiators,
  updated_at      = now();
