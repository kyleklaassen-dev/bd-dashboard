-- APPLIED 2026-06-19: seed asset_programs with the TL1A/ALX001 program (pilot for #6).
-- Content migrated verbatim from the hardcoded #tl1a-ailux-anchor card in index.html.
-- source_url is null: the original dashboard content carried no source — flagged for curation,
-- NOT fabricated (constitution: never invent URLs). Differentiators stored as jsonb [{label,value,sub}].
-- Idempotent: ON CONFLICT (program_code) updates.

INSERT INTO public.asset_programs
  (program_code, target_pair_id, indication_lead, modality, status, clinical_target, format_advantage, differentiators, notes, source_url, updated_at)
VALUES (
  'ALX001',
  'tl1a-il23p19',
  'IBD (UC / CD)',
  'bispecific',
  'preclinical',
  'TL1A + IL-23p19 dual blockade — exceed monotherapy efficacy in moderate-to-severe IBD',
  'High-concentration subcutaneous formulation in development',
  $json$[
    {"label":"Mechanism of Action","value":"Trimer Destabilization","sub":"Engineered mutations disrupt TL1A trimer assembly — distinct from all competitors' DR3 blockade. Attacks the target at the source, not just the receptor."},
    {"label":"Half-Life","value":"37-Day t½ (Mono)","sub":"~37-day monotherapy half-life vs. 14–21 day class average. Extended PK enables less-frequent dosing (monthly or longer), meaningful for patient convenience and payer acceptance."},
    {"label":"Epitope & Immunogenicity","value":"Novel Epitope → Low ADA","sub":"Binds a novel epitope via stoichiometric mechanism. Low predicted anti-drug antibody (ADA) risk — important for chronic IBD dosing where ADA-driven loss of response is a major clinical issue."},
    {"label":"Formulation","value":"High-Conc. SC","sub":"High-concentration subcutaneous formulation in development. SC delivery is strongly preferred by IBD patients and payers vs. IV infusion, and commands premium reimbursement."}
  ]$json$::jsonb,
  $note$4 structural differentiators vs. Mirador, Caldera, Xencor, Helixon, and Simcere/BI programs.$note$,
  NULL,
  now()
)
ON CONFLICT (program_code) DO UPDATE SET
  target_pair_id = EXCLUDED.target_pair_id,
  indication_lead = EXCLUDED.indication_lead,
  modality = EXCLUDED.modality,
  status = EXCLUDED.status,
  clinical_target = EXCLUDED.clinical_target,
  format_advantage = EXCLUDED.format_advantage,
  differentiators = EXCLUDED.differentiators,
  notes = EXCLUDED.notes,
  updated_at = now();
