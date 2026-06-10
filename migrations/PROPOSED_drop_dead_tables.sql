-- ============================================================================
-- PROPOSED — STAGED FOR REVIEW. DO NOT APPLY BLINDLY.
-- Dead-table/view cleanup from the 2026-06-09 stabilization audit.
-- Reversibility note: a DROP is unrecoverable without a backup. Take a schema +
-- data snapshot of each object before running. Confirm table-vs-view first
-- (several below are VIEWS). Apply in a transaction; verify the dashboard after.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- TIER A — SAFE DROP: empty, 0 frontend reads (index.html), 0 script references.
-- Confirm each is empty at apply time:  SELECT count(*) FROM <obj>;
-- Several are VIEWS — use DROP VIEW; the rest DROP TABLE.
-- ---------------------------------------------------------------------------
DROP VIEW  IF EXISTS effective_company_areas;          -- view, empty, unreferenced
DROP VIEW  IF EXISTS phase3_regulatory_risk_map;       -- view (non-updatable), unreferenced
DROP VIEW  IF EXISTS recent_field_changes;             -- view, unreferenced
DROP VIEW  IF EXISTS change_frequency_summary;         -- view (GROUP BY), unreferenced
DROP TABLE IF EXISTS company_area_detail;              -- table, empty, unreferenced
DROP TABLE IF EXISTS governance_change_alerts;         -- table, empty, unreferenced

-- ---------------------------------------------------------------------------
-- TIER B — DECIDE PER TABLE (DO NOT DROP YET): a script writes to these but the
-- table is EMPTY = the collector is paused or silently broken. For each: either
-- (a) revive the collector, or (b) retire BOTH the table and its script.
-- Listed here only as the review checklist — intentionally commented out.
-- ---------------------------------------------------------------------------
-- china_trials                 (scripts: 2)  -- CDE/NMPA harvest; known-hard source
-- patent_families              (scripts: 2)  -- patent sweep; was throttled
-- trial_identity               (scripts: 3)
-- drug_stage_history           (scripts: 5)
-- source_collection_gaps       (scripts: 3)
-- correction_labels            (scripts: 4)
-- model_validation_results     (scripts: 4)
-- fine_tune_dataset            (scripts: 4)
-- target_areas                 (scripts: 1)
-- trajectory_summary           (scripts: 1)
-- narrative_claim_triangulation(scripts: 1)
-- narrative_feedback           (scripts: 1)
-- narrative_source_diversity   (scripts: 1)

-- ---------------------------------------------------------------------------
-- TIER C — DO NOT DROP: empty BUT read by the dashboard (dark features / data
-- gaps to POPULATE, not remove): company_areas (28 reads), company_profiles (13),
-- drug_modalities (10), intel_areas (11), intel_companies (7),
-- indication_biology_tags (7), drug_routes (6), drug_areas (legacy, 23).
-- ---------------------------------------------------------------------------

-- Recommended companion (separate migration): make edge writes idempotent.
-- ALTER TABLE entity_edges ADD CONSTRAINT entity_edges_uniq
--   UNIQUE (subject_id, predicate, object_id);

ROLLBACK;  -- <- change to COMMIT only after review + backups + emptiness re-check
