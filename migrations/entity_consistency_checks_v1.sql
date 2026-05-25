-- ============================================================
-- Meridian BD Platform — entity_consistency_checks
-- Migration Plan v1 — Session 53j — 2026-05-25
-- ============================================================
-- PURPOSE
--   Persistent evidence reconciliation layer.
--   Stores contradictions, suspected errors, proposed corrections,
--   and advisor review decisions that accumulate across Phase 4.
--   This is the durable counterpart to window.__MERIDIAN_PHASE4_COMPARE__.
--
-- DESIGN DOC:  docs/evidence_reconciliation_layer.md
-- PHASE:       Phase 4B complete → entity layer build
-- SEED:        7 known Phase 4A candidates
--
-- SAFETY
--   This migration ONLY creates a new table and its indexes.
--   No existing tables are altered.
--   Seed INSERTs use ON CONFLICT DO NOTHING — idempotent.
--
-- !! DO NOT EXECUTE until advisor approves this plan !!
-- ============================================================


-- ── 1. CREATE TABLE ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS entity_consistency_checks (

  -- Identity
  id                    SERIAL PRIMARY KEY,

  -- Entity being checked
  entity_type           TEXT NOT NULL,
    -- 'drug' | 'indication' | 'target' | 'trial'
  entity_id             TEXT NOT NULL,
    -- drug_id, indication_id, target_id, trial_id, etc.

  -- Classification
  check_type            TEXT NOT NULL,
    -- detection category: cross_table_inconsistency | source_conflict |
    -- ontology_scope_difference | normalized_gap | needs_manual_review
  classification        TEXT NOT NULL,
    -- resolution label (Phase 4A/4B language):
    --   legacy_noise_removed | normalized_gap | ontology_scope_difference |
    --   needs_manual_review | new_normalized_value | source_conflict |
    --   cross_table_inconsistency | ibd_indication_not_tl1a_target

  -- Severity and lifecycle state
  severity              TEXT NOT NULL DEFAULT 'medium'
    CHECK (severity IN ('high', 'medium', 'low')),
  status                TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'in_review', 'corrected', 'closed', 'deferred')),
    -- open       = detected, unresolved
    -- in_review  = actively under review
    -- corrected  = data fix applied to production tables
    -- closed     = resolved without data change (OOS, no action needed)
    -- deferred   = acknowledged, intentionally postponed

  -- Conflict detail
  conflicting_tables    TEXT[],
    -- e.g. ARRAY['drug_areas', 'drug_indications', 'drugs']
    -- enables: "which two tables disagree most often?"
  conflict_summary      TEXT,
    -- human-readable description of what disagrees and why

  -- Evidence (JSONB arrays of {table, field, value, note})
  evidence_for          JSONB,
    -- evidence supporting the legacy assignment
    -- schema: [{"table": "...", "field": "...", "value": "...", "note": "..."}]
  evidence_against      JSONB,
    -- evidence contradicting legacy / supporting the normalized correction
    -- same schema as evidence_for

  -- Proposed correction
  proposed_action       TEXT,
    -- what should be done, including any pre-conditions and status
  confidence_score      NUMERIC(4,3)
    CHECK (confidence_score IS NULL
        OR confidence_score BETWEEN 0.0 AND 1.0),
    -- 0.0–1.0
    -- >= 0.95 + auto-fixable type → candidate for auto-resolution in Phase 5
    -- < 0.70 → manual review required

  -- Advisor review decision
  review_status         TEXT NOT NULL DEFAULT 'proposed'
    CHECK (review_status IN ('proposed', 'accepted', 'rejected', 'resolved', 'held')),
    -- proposed  = waiting for review
    -- accepted  = advisor approved the classification and proposed action
    -- rejected  = advisor rejected the proposed action
    -- resolved  = fully resolved (either corrected or closed without action)
    -- held      = explicitly held pending more evidence
  reviewed_by           TEXT,
    -- 'advisor_phase4a' | 'kyle' | etc.

  -- Timestamps
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at           TIMESTAMPTZ,

  -- Idempotency: one row per entity × classification combination
  -- Prevents duplicate records for the same finding across re-runs
  CONSTRAINT uq_entity_classification
    UNIQUE (entity_type, entity_id, classification)

);


-- ── 2. INDEXES ────────────────────────────────────────────────

-- Primary lookup: all checks for a given entity
CREATE INDEX IF NOT EXISTS idx_ecc_entity
  ON entity_consistency_checks (entity_type, entity_id);

-- Severity filter (migration readiness: how many high-severity open items remain?)
CREATE INDEX IF NOT EXISTS idx_ecc_severity
  ON entity_consistency_checks (severity);

-- Classification filter (all legacy_noise_removed / all normalized_gap / etc.)
CREATE INDEX IF NOT EXISTS idx_ecc_classification
  ON entity_consistency_checks (classification);

-- Workflow filter (all open items / all in_review)
CREATE INDEX IF NOT EXISTS idx_ecc_status
  ON entity_consistency_checks (status);

-- Review queue (all items awaiting advisor decision)
CREATE INDEX IF NOT EXISTS idx_ecc_review_status
  ON entity_consistency_checks (review_status);

-- Composite: open high-severity items — primary Phase 5 gate query
CREATE INDEX IF NOT EXISTS idx_ecc_open_high
  ON entity_consistency_checks (status, severity)
  WHERE status IN ('open', 'in_review') AND severity = 'high';


-- ── 3. COLUMN COMMENTS ───────────────────────────────────────

COMMENT ON TABLE entity_consistency_checks IS
  'Persistent evidence reconciliation layer. Stores contradictions, suspected '
  'errors, proposed corrections, and advisor decisions across Meridian data layers. '
  'First self-healing layer of the platform. See docs/evidence_reconciliation_layer.md.';

COMMENT ON COLUMN entity_consistency_checks.check_type IS
  'How the inconsistency was detected: cross_table_inconsistency | source_conflict | '
  'ontology_scope_difference | normalized_gap | needs_manual_review.';

COMMENT ON COLUMN entity_consistency_checks.classification IS
  'Phase 4A/4B resolution label: legacy_noise_removed | normalized_gap | '
  'ontology_scope_difference | needs_manual_review | new_normalized_value | '
  'source_conflict | cross_table_inconsistency | ibd_indication_not_tl1a_target.';

COMMENT ON COLUMN entity_consistency_checks.evidence_for IS
  'JSONB array of {table, field, value, note} objects supporting the legacy '
  'or disputed assignment.';

COMMENT ON COLUMN entity_consistency_checks.evidence_against IS
  'JSONB array of {table, field, value, note} objects contradicting the legacy '
  'assignment or supporting the normalized correction.';

COMMENT ON COLUMN entity_consistency_checks.confidence_score IS
  '0.0–1.0. Auto-approve candidate: >= 0.95 + auto-fixable classification. '
  'Manual review required: < 0.70. Drives Phase 5 auto-resolution pipeline.';


-- ── 4. SEED DATA — 7 known Phase 4A candidates ───────────────
-- All inserts use ON CONFLICT DO NOTHING.
-- Safe to re-run after the table already has data.
-- IDs assigned by SERIAL — not hard-coded.
-- ─────────────────────────────────────────────────────────────


-- SEED 1: lm-302 — legacy IBD/TL1A membership vs gastric oncology biology
--   Phase 4A resolution: legacy_noise_removed — accepted
-- ─────────────────────────────────────────────────────────────
INSERT INTO entity_consistency_checks (
  entity_type, entity_id,
  check_type, classification, severity, status,
  conflicting_tables, conflict_summary,
  evidence_for, evidence_against,
  proposed_action, confidence_score,
  review_status, reviewed_by,
  created_at, resolved_at
) VALUES (
  'drug', 'lm-302',
  'cross_table_inconsistency', 'legacy_noise_removed', 'high', 'closed',
  ARRAY['drug_areas', 'drug_targets', 'drugs'],
  'Legacy drug_areas assigns lm-302 to tl1a and ibd. Three independent sources '
  '(drugs.target=Claudin 18.2, drugs.indication_short=gastric cancer/GEJ, '
  'modality=ADC) place this drug in gastric oncology. No IBD or TL1A biology present. '
  'CLDN18.2 is a gastric junction tight-junction protein — unrelated to TL1A/IBD axis.',
  '[
    {"table": "drug_areas", "field": "area_id", "value": "tl1a", "note": "legacy assignment only — no supporting molecular evidence"},
    {"table": "drug_areas", "field": "area_id", "value": "ibd",  "note": "legacy assignment only — no supporting molecular evidence"}
  ]'::jsonb,
  '[
    {"table": "drug_targets",   "field": "target_id",        "value": "CLDN18.2",          "note": "normalized target row — gastric junction protein"},
    {"table": "drugs",          "field": "target",           "value": "Claudin 18.2",       "note": "source intake field"},
    {"table": "drugs",          "field": "indication_short", "value": "gastric cancer/GEJ", "note": "source intake field — oncology"},
    {"table": "drugs",          "field": "modality",         "value": "ADC",                "note": "antibody-drug conjugate; anti-TL1A drugs are mAbs, not ADCs"}
  ]'::jsonb,
  'Exclude from IBD and TL1A normalized denominators. '
  'No drug_indications or drug_targets IBD/TL1A rows to add. '
  'APPLIED — Phase 4A advisor review.',
  0.970,
  'accepted', 'advisor_phase4a',
  '2026-05-25'::timestamptz, '2026-05-25'::timestamptz
) ON CONFLICT (entity_type, entity_id, classification) DO NOTHING;


-- SEED 2: sim0500 — legacy TL1A/IBD membership vs RRMM hematology biology
--   Phase 4A resolution: legacy_noise_removed — accepted
--   Note: drug_targets.tl1a row confirmed absent (Wave 2B error, never committed)
-- ─────────────────────────────────────────────────────────────
INSERT INTO entity_consistency_checks (
  entity_type, entity_id,
  check_type, classification, severity, status,
  conflicting_tables, conflict_summary,
  evidence_for, evidence_against,
  proposed_action, confidence_score,
  review_status, reviewed_by,
  created_at, resolved_at
) VALUES (
  'drug', 'sim0500',
  'cross_table_inconsistency', 'legacy_noise_removed', 'high', 'closed',
  ARRAY['drug_areas', 'drugs', 'drug_targets'],
  'Legacy drug_areas assigns sim0500 to tl1a and ibd. drugs.indication_short=RRMM '
  '(relapsed/refractory multiple myeloma) and modality=trispecific confirm hematology '
  'oncology. GPRC5D×BCMA×CD3 trispecific has no TL1A or IBD biology. '
  'drug_targets.tl1a row was confirmed absent from production (Wave 2B error — '
  'logged but never committed).',
  '[
    {"table": "drug_areas", "field": "area_id", "value": "tl1a", "note": "legacy assignment only"},
    {"table": "drug_areas", "field": "area_id", "value": "ibd",  "note": "legacy assignment only"}
  ]'::jsonb,
  '[
    {"table": "drugs",        "field": "indication_short", "value": "RRMM",        "note": "relapsed/refractory multiple myeloma — hematology oncology"},
    {"table": "drugs",        "field": "modality",         "value": "trispecific", "note": "GPRC5D×BCMA×CD3 — no TL1A or IBD targets in this construct"},
    {"table": "drug_targets", "field": "target_id",        "value": "(absent)",    "note": "tl1a row confirmed absent from production — never committed"}
  ]'::jsonb,
  'Exclude from IBD and TL1A normalized denominators. '
  'drug_targets.tl1a row confirmed absent — no data action required. '
  'APPLIED — Phase 4A advisor review.',
  0.970,
  'accepted', 'advisor_phase4a',
  '2026-05-25'::timestamptz, '2026-05-25'::timestamptz
) ON CONFLICT (entity_type, entity_id, classification) DO NOTHING;


-- SEED 3: spy072 — true TL1A target, but rheumatology indication (not IBD)
--   Phase 4A resolution: ontology_scope_difference — accepted
--   drug_targets.tl1a row is legitimate; exclude from IBD denominator only
-- ─────────────────────────────────────────────────────────────
INSERT INTO entity_consistency_checks (
  entity_type, entity_id,
  check_type, classification, severity, status,
  conflicting_tables, conflict_summary,
  evidence_for, evidence_against,
  proposed_action, confidence_score,
  review_status, reviewed_by,
  created_at, resolved_at
) VALUES (
  'drug', 'spy072',
  'ontology_scope_difference', 'ontology_scope_difference', 'medium', 'closed',
  ARRAY['drug_areas', 'drug_indications', 'drugs'],
  'TL1A mechanism is biologically correct for spy072. drugs.indication_short '
  '(PsA, axSpA) places this drug in rheumatology, not IBD. The legacy tl1a bucket '
  'contained both IBD-indication TL1A drugs and rheumatology-indication TL1A drugs — '
  'a scope conflation artifact of the catch-all bucket structure, not a data error. '
  'spy072 belongs in a future rheumatology disease area.',
  '[
    {"table": "drug_areas", "field": "area_id", "value": "tl1a", "note": "mechanism is correct — TL1A target biology confirmed"},
    {"table": "drugs",      "field": "target",  "value": "TL1A", "note": "source intake field confirms on-target biology"}
  ]'::jsonb,
  '[
    {"table": "drugs",            "field": "indication_short", "value": "PsA, axSpA",  "note": "psoriatic arthritis and axial spondyloarthritis — rheumatology"},
    {"table": "drug_indications", "field": "indication_id",    "value": "(absent)",    "note": "no uc or cd rows present"}
  ]'::jsonb,
  'Exclude from IBD normalized denominator. '
  'Do NOT remove drug_targets.tl1a row — TL1A mechanism is valid. '
  'Candidate for future rheumatology disease area. '
  'APPLIED — Phase 4A advisor review.',
  0.920,
  'accepted', 'advisor_phase4a',
  '2026-05-25'::timestamptz, '2026-05-25'::timestamptz
) ON CONFLICT (entity_type, entity_id, classification) DO NOTHING;


-- SEED 4: epi-001 — TL1A/IBD legacy membership, insufficient UC/CD evidence
--   Phase 4A resolution: needs_manual_review — held pending source evidence
--   2 rows in backfill_preview (wave2c_ibd_20260525_203134) as pending_review
-- ─────────────────────────────────────────────────────────────
INSERT INTO entity_consistency_checks (
  entity_type, entity_id,
  check_type, classification, severity, status,
  conflicting_tables, conflict_summary,
  evidence_for, evidence_against,
  proposed_action, confidence_score,
  review_status, reviewed_by,
  created_at, resolved_at
) VALUES (
  'drug', 'epi-001',
  'needs_manual_review', 'needs_manual_review', 'medium', 'open',
  ARRAY['drug_areas', 'drug_indications', 'backfill_preview'],
  'Legacy drug_areas assigns epi-001 to tl1a and ibd. Anti-TL1A mechanism class '
  'is IBD-validated as a category. However, this specific drug is preclinical only — '
  'no indication_short, no registered trials, no published IBD data. Confidence too '
  'low to auto-confirm UC or CD. 2 rows held in backfill_preview '
  '(wave2c_ibd_20260525_203134) as pending_review.',
  '[
    {"table": "drug_areas", "field": "area_id",   "value": "tl1a",      "note": "legacy assignment"},
    {"table": "drug_areas", "field": "area_id",   "value": "ibd",       "note": "legacy assignment"},
    {"table": "drugs",      "field": "mechanism", "value": "Anti-TL1A", "note": "mechanism class is IBD-relevant as a category"}
  ]'::jsonb,
  '[
    {"table": "drugs",             "field": "stage",           "value": "preclinical",   "note": "no clinical trial data available"},
    {"table": "drugs",             "field": "indication_short","value": "(absent)",      "note": "no indication on record"},
    {"table": "trial_indications", "field": "indication_id",   "value": "(absent)",      "note": "no trial evidence for uc or cd"},
    {"table": "backfill_preview",  "field": "preview_status",  "value": "pending_review","note": "held in wave2c_ibd_20260525_203134 — not committed"}
  ]'::jsonb,
  'Hold in backfill_preview as pending_review. Search published literature for '
  'source evidence confirming UC or CD indication for epi-001. '
  'If confirmed: commit uc + cd rows from wave2c preview. '
  'If no evidence: set review_status=rejected, status=closed. '
  'DO NOT commit without source evidence.',
  0.550,
  'held', 'advisor_phase4a',
  '2026-05-25'::timestamptz, NULL
) ON CONFLICT (entity_type, entity_id, classification) DO NOTHING;


-- SEED 5: batoclimab — normalized gap resolved (ted + gmg committed Phase 4A)
--   Phase 4A resolution: normalized_gap corrected — drug_indications rows committed
--   cidp deferred to Wave 2D FcRn batch
-- ─────────────────────────────────────────────────────────────
INSERT INTO entity_consistency_checks (
  entity_type, entity_id,
  check_type, classification, severity, status,
  conflicting_tables, conflict_summary,
  evidence_for, evidence_against,
  proposed_action, confidence_score,
  review_status, reviewed_by,
  created_at, resolved_at
) VALUES (
  'drug', 'batoclimab',
  'cross_table_inconsistency', 'normalized_gap', 'high', 'corrected',
  ARRAY['drug_areas', 'drug_indications', 'drug_targets'],
  'Legacy assigned batoclimab to 4 areas (fcrn, igf1r, autoimmune, ted). '
  'drug_targets correctly identifies FcRn/FCGRT as target. drug_indications '
  'was missing ted and gmg rows despite Phase 3 trial evidence for both. '
  'Multi-area legacy assignment (igf1r, autoimmune) was a curation artifact of '
  'the legacy catch-all bucket structure. cidp remains under review for Wave 2D.',
  '[
    {"table": "drug_areas",   "field": "area_id",   "value": "ted",   "note": "legacy assignment — indication is correct"},
    {"table": "drug_areas",   "field": "area_id",   "value": "fcrn",  "note": "legacy assignment — mechanism is correct"},
    {"table": "drug_targets", "field": "target_id", "value": "fcrn",  "note": "normalized target row — confirmed correct"}
  ]'::jsonb,
  '[
    {"table": "drug_indications", "field": "indication_id", "value": "(absent pre-fix)", "note": "ted and gmg rows missing before Phase 4A correction"},
    {"table": "drug_areas",       "field": "area_id",       "value": "igf1r",            "note": "legacy curation artifact — no IGF-1R biology in batoclimab"},
    {"table": "drug_areas",       "field": "area_id",       "value": "autoimmune",       "note": "legacy catch-all bucket — not a specific indication"}
  ]'::jsonb,
  'APPLIED — Phase 4A: committed ted (confidence_score=95, Ph3) and '
  'gmg (confidence_score=92, Ph3) to drug_indications. '
  'cidp deferred to Wave 2D FcRn batch (re-evaluate with imvt-1402 context). '
  'Legacy igf1r/autoimmune assignments flagged for cleanup.',
  0.880,
  'resolved', 'advisor_phase4a',
  '2026-05-25'::timestamptz, '2026-05-25'::timestamptz
) ON CONFLICT (entity_type, entity_id, classification) DO NOTHING;


-- SEED 6: upadacitinib — atopy/AD normalized gap (queued for Wave 2D)
--   Phase 4A resolution: normalized_gap — proposed, approved, pending Wave 2D
-- ─────────────────────────────────────────────────────────────
INSERT INTO entity_consistency_checks (
  entity_type, entity_id,
  check_type, classification, severity, status,
  conflicting_tables, conflict_summary,
  evidence_for, evidence_against,
  proposed_action, confidence_score,
  review_status, reviewed_by,
  created_at, resolved_at
) VALUES (
  'drug', 'upadacitinib',
  'normalized_gap', 'normalized_gap', 'medium', 'open',
  ARRAY['drug_areas', 'drug_indications'],
  'drug_areas assigns upadacitinib to atopy. drug_indications has no row for ad '
  '(atopic dermatitis). Upadacitinib (Rinvoq) is FDA-approved for atopic dermatitis '
  'as a JAK1 inhibitor — strong regulatory and published evidence for the missing '
  'relationship. No contradicting evidence. Classification: normalized_gap.',
  '[
    {"table": "drug_areas", "field": "area_id", "value": "atopy",          "note": "legacy assignment — correct scope"},
    {"table": "drugs",      "field": "target",  "value": "JAK1",           "note": "confirmed mechanism"},
    {"table": "drugs",      "field": "stage",   "value": "Approved (AD)",  "note": "FDA-approved for atopic dermatitis"}
  ]'::jsonb,
  '[
    {"table": "drug_indications", "field": "indication_id", "value": "(absent)", "note": "no ad row in drug_indications — gap confirmed"}
  ]'::jsonb,
  'Backfill drug_indications: upadacitinib → ad, confidence_score=0.97 (approved). '
  'Queue for Wave 2D atopy batch alongside imvt-1402 and batoclimab cidp. '
  'Phase 4A classification accepted. Commit pending Wave 2D run.',
  0.970,
  'proposed', 'advisor_phase4a',
  '2026-05-25'::timestamptz, NULL
) ON CONFLICT (entity_type, entity_id, classification) DO NOTHING;


-- SEED 7: gb004 — drugs.mechanism field data error (PHD inhibitor, not Anti-TL1A)
--   Status: held — requires separate advisor approval before applying fix
--   DO NOT resolve during Phase 4B work
-- ─────────────────────────────────────────────────────────────
INSERT INTO entity_consistency_checks (
  entity_type, entity_id,
  check_type, classification, severity, status,
  conflicting_tables, conflict_summary,
  evidence_for, evidence_against,
  proposed_action, confidence_score,
  review_status, reviewed_by,
  created_at, resolved_at
) VALUES (
  'drug', 'gb004',
  'source_conflict', 'source_conflict', 'medium', 'open',
  ARRAY['drugs'],
  'drugs.mechanism="Anti-TL1A" is incorrect for gb004. GB004 is a PHD inhibitor '
  '(HIF-1α stabilizer), an oral small molecule that stabilizes HIF-1α by inhibiting '
  'PHD enzymes to reduce gut inflammation via oxygen-sensing pathway modulation. '
  'drugs.target="PHD1/HIF-1α" and drugs.modality="oral HIF-1α stabilizer (PHD '
  'inhibitor, small molecule)" are both correct — the mechanism field is the sole '
  'outlier. Anti-TL1A drugs are biologics (mAbs); GB004 is an oral small molecule.',
  '[
    {"table": "drugs", "field": "mechanism", "value": "Anti-TL1A", "note": "this field is the error — the only field claiming TL1A biology"}
  ]'::jsonb,
  '[
    {"table": "drugs", "field": "target",           "value": "PHD1/HIF-1α",
      "note": "correct — cross-field consistent with PHD inhibitor class"},
    {"table": "drugs", "field": "modality",         "value": "oral HIF-1α stabilizer (PHD inhibitor, small molecule)",
      "note": "correct — confirms oral small molecule, not biologic"},
    {"table": "drugs", "field": "indication_short", "value": "UC (terminated)",
      "note": "IBD indication is correct; mechanism field is the outlier"},
    {"table": "drugs", "field": "modality",         "value": "oral HIF-1α stabilizer",
      "note": "Anti-TL1A antibodies are biologics — an oral small molecule cannot be an Anti-TL1A mAb"}
  ]'::jsonb,
  'Update drugs.mechanism for gb004 from "Anti-TL1A" to '
  '"PHD inhibitor (HIF-1α stabilizer)". '
  'Single-field UPDATE — no relationship tables affected. '
  'Requires advisor approval before applying. '
  'DO NOT fix during Phase 4B work — separate evidence review required.',
  0.950,
  'held', NULL,
  '2026-05-25'::timestamptz, NULL
) ON CONFLICT (entity_type, entity_id, classification) DO NOTHING;


-- ── 5. VERIFICATION QUERIES (run after execution to confirm) ─

-- Row count (expect 7 after seed)
-- SELECT count(*) FROM entity_consistency_checks;

-- Severity distribution
-- SELECT severity, count(*) FROM entity_consistency_checks GROUP BY severity ORDER BY severity;

-- Review status distribution
-- SELECT review_status, count(*) FROM entity_consistency_checks GROUP BY review_status ORDER BY review_status;

-- Open high-severity items (Phase 5 gate — expect 0 before migration)
-- SELECT entity_id, classification, conflict_summary
--   FROM entity_consistency_checks
--  WHERE status IN ('open', 'in_review') AND severity = 'high';

-- All held items (pending advisor decision)
-- SELECT entity_id, classification, proposed_action
--   FROM entity_consistency_checks
--  WHERE review_status = 'held'
--  ORDER BY confidence_score DESC;

-- ── END OF MIGRATION PLAN ─────────────────────────────────────
