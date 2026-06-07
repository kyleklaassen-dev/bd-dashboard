-- Field-change audit retention: drop non-governance, non-correction rows older
-- than 30 days. Governance-relevant + correction rows are kept indefinitely.
-- Run weekly by .github/workflows/weekly-audit-retention.yml.
-- Table grows ~10k rows/day; this bounds it without losing the audit trail that matters.
SELECT public.fn_prune_field_change_audit(30) AS rows_pruned;
