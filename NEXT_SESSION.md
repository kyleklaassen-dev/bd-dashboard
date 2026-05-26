# NEXT SESSION — BD Platform

**Last session:** Session 62 (2026-05-26)

---

## ✅ MILESTONE CLOSED: Legacy Read Layer Elimination (Session 61)

All 6 feature flags permanently true. drug_areas no longer serves any biological dashboard tab.

---

## Phase 6 Workstream Status

| WS | Name | Status |
|---|---|---|
| WS1 | C5+C6+C7 activation | ✅ **COMPLETE** |
| WS2 | Wave 3 drug-indication pairs | ✅ **COMPLETE** — 49 rows, quality validated |
| WS3 | drug_competitive_scores | ✅ **Table created + 234 rows migrated** — consumers not yet updated |
| WS3 (next) | Dashboard consumer migration | ⏳ 8 consumers in index.html to migrate off drug_area_scores |
| WS4 | Strategic views (autoimmune/respiratory/tcell) | Not started |

---

## Session 63 Priority: WS3 Consumer Migration

### Context

`drug_competitive_scores` is live with 234 rows. The dashboard still reads `drug_area_scores` for competitive intelligence. Consumer migration is the next step to retire the legacy table.

### Open Items from Migration

**3 indication/ibd fallback drugs** — these IBD drugs have no UC or CD entries in drug_indications:
- `epi-001` (held in backfill_preview — do not touch without source evidence)
- `sim0500` (Simcere/AbbVie — should have UC/CD entries)
- `spy072` (should have UC/CD entries)

Action: backfill sim0500 and spy072 into drug_indications for UC and/or CD. Do NOT touch epi-001.

### Consumer Migration (WS3 continuation)

Full plan in `docs/drug_competitive_scores_design.md`.

High-level:
1. Identify the 8 consumers in index.html that query drug_area_scores
2. Update `company_enrichment.py` for dual-write (drug_area_scores + drug_competitive_scores)
3. Migrate consumers one at a time — validate each before proceeding
4. 30-day monitoring per consumer before legacy reads removed
5. drug_area_scores → read-only when all consumers migrated

### P1 — Backfill sim0500 + spy072 UC/CD in drug_indications

```sql
-- Verify what's missing
SELECT drug_id, indication_id FROM drug_indications 
WHERE drug_id IN ('sim0500','spy072') AND indication_id IN ('uc','cd');
```

If missing, add via Wave 4 drug_indications backfill (check trial_indications first).

---

## Data Layer State After Session 62

```sql
SELECT count(*) FROM drug_indications;            -- expect 246
SELECT count(*) FROM drug_competitive_scores;     -- expect 234
SELECT count(*) FROM drug_area_scores;            -- expect 212 (legacy — do not delete)
SELECT count(*) FROM area_metadata;               -- expect 11
-- 3 indication/ibd fallback rows:
SELECT drug_id FROM drug_competitive_scores WHERE context_id = 'ibd';
-- expect: epi-001, sim0500, spy072
```

---

## Monitoring Windows (30-day rule)

| Candidate | 30-day window closes |
|---|---|
| C1/C2/C3 (IBD/TED/Modal) | ~2026-06-24 |
| C4 (TL1A) | ~2026-06-24 |
| C5/C6 (Atopy) | ~2026-06-25 |
| C7 (FcRn) | ~2026-06-25 |

---

## Active Constraints

1. **ontology_edges locked** — 25 rows. Do NOT unlock without advisor approval.
2. **30-day rule** — Keep legacy flag branches until monitoring window closes.
3. **drug_area_scores** — Do NOT delete. Legacy provenance for 212 rows.
4. **drug_areas** — Do NOT delete. Serves autoimmune/respiratory/tcell.
5. **drug_competitive_scores consumers** — Do NOT update dashboard reads yet. Need dual-write window first.
6. **epi-001** — Do NOT commit to drug_indications without source evidence.

---

## Validation Checks at Session Start

```sql
-- Standing rule: check for validation failures first
SELECT entity_id, check_type, check_status, failure_reason
FROM drug_validation_results
WHERE check_status IN ('fail','warning','needs_review')
ORDER BY check_status, entity_id LIMIT 20;

-- Open ECC items:
SELECT entity_id, issue_key, status FROM entity_consistency_checks WHERE status = 'open';
```

---

## Files

- `docs/drug_competitive_scores_design.md` — Consumer migration plan, dual-write strategy
- `docs/drug_competitive_scores_migration_report.md` — Full migration audit (Session 62)
- `scripts/migrate_drug_area_scores.py` — Migration script (committed, idempotent)
- `docs/phase6_master_plan.md` — Full session sequence and dependency map
