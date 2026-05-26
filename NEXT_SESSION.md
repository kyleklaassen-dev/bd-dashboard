# NEXT SESSION — BD Platform

**Last session:** Session 61 (2026-05-26)

---

## ✅ MILESTONE CLOSED: Legacy Read Layer Elimination

All 6 feature flags permanently true. `drug_areas` no longer serves any biological dashboard tab.

| Surface | Source | Flag | Activated |
|---|---|---|---|
| IBD tab | `drug_indications` | `useNormalizedIBD` | 2026-05-25 |
| TED tab | `drug_indications` | `useNormalizedTED` | 2026-05-25 |
| Drug Modal | `drug_targets` + `drug_indications` | `useNormalizedDrugModal` | 2026-05-25 |
| TL1A tab | `drug_targets` | `useUnifiedTL1A` | 2026-05-25 |
| TSLP + IL-4Rα tabs | `drug_targets` | `useUnifiedAtopy` | 2026-05-26 |
| FcRn tab | `drug_targets` | `useUnifiedFCRN` | 2026-05-26 ← **Session 61** |

C7 FcRn validation: legacy=7, norm=7, overlap=6, scopeDiff=1 (atg-201=CD19×CD3), adj=100%, compare_pass_oos_adjusted. 8/8 gates. Commit `f8a17e7`.

---

## Phase 6 Workstream Status

| WS | Name | Status |
|---|---|---|
| WS1 | C5+C6+C7 activation | ✅ **COMPLETE** — all 7 surfaces migrated |
| WS2 | Wave 3 drug-indication pairs | ✅ **COMPLETE** — 49 rows, quality validated (6 C-grade rows flagged) |
| WS3 | drug_competitive_scores | ⏳ DDL written, **table not yet created**, migration not run |
| WS4 | Strategic views (autoimmune/respiratory/tcell) | Not started |
| WS-Gov | area_metadata governance table | ⏳ DDL written (`docs/area_metadata_ddl.sql`), **not yet applied to Supabase** |

---

## Session 62 Priorities

### P1 — Apply drug_competitive_scores DDL (FIRST THING)

**File:** `docs/drug_competitive_scores_ddl.sql` (deployed sha 702134c)

1. Supabase → SQL Editor → New Query
2. Paste full `docs/drug_competitive_scores_ddl.sql`
3. Run → confirm table created
4. Then run migration:

```bash
python3 scripts/migrate_drug_area_scores.py --audit
python3 scripts/migrate_drug_area_scores.py --dry-run
python3 scripts/migrate_drug_area_scores.py --commit
```

Expected: 212 source rows → ~220+ target rows (IBD expands to UC+CD per drug; ted+igf1r deduped).
Spot-checks: risankizumab/indication/cd, efgartigimod/target/fcrn, dupilumab/target/il4ra.
Do NOT delete drug_area_scores.

### P2 — Apply area_metadata DDL

**File:** `docs/area_metadata_ddl.sql` (deployed sha 6c86297)

1. Supabase → SQL Editor → New Query
2. Paste full `docs/area_metadata_ddl.sql`
3. Run → confirm 11 rows seeded
4. Verify: `SELECT area_id, lifecycle_state, retirement_status FROM area_metadata ORDER BY category, area_id`

### P3 — drug_competitive_scores Consumer Migration (WS3 continuation)

After P1 migration is committed and validated:
- Consumer inventory: 8 consumers in index.html read drug_area_scores
- Dual-write window design in `docs/drug_competitive_scores_design.md`
- Do NOT migrate consumers until migration committed + validated

---

## Wave 3 Quality Caveats (from Session 61 validation)

6 C-grade rows (confidence=40, Phase 1 evidence only) warrant monitoring:
- cizutamig/ted — already logged in entity_consistency_checks
- cln-978/sjogrens
- cnd261/ra
- risankizumab-lutikizumab-or-trosunilimab/uc
- zumilokibart/asthma
- zumilokibart/crswnp

Wave 3 is safe to treat as authoritative. C-grade rows should be upgraded to review_status='needs_review' in a future sprint.

---

## Data Layer State After Session 61

```sql
SELECT count(*) FROM drug_indications;            -- expect 246
SELECT count(*) FROM drug_targets;                -- expect ~170
SELECT count(*) FROM trial_indications;           -- expect ~540+
SELECT count(*) FROM drug_area_scores;            -- expect 212 (legacy — do not delete)
SELECT count(*) FROM area_metadata;               -- will error until DDL applied (P2)
SELECT count(*) FROM drug_competitive_scores;     -- will error until DDL applied (P1)
```

---

## Monitoring Windows (30-day rule)

Legacy code retained (not deleted) until:
- C1/C2/C3 (IBD/TED/Modal): ~2026-06-24 (30 days from 2026-05-25)
- C4 (TL1A): ~2026-06-24
- C5/C6 (Atopy): ~2026-06-25
- C7 (FcRn): ~2026-06-25

Inconsistencies during monitoring → `entity_consistency_checks`, not reverts.

---

## Active Constraints

1. **ontology_edges locked** — 25 rows. Do NOT unlock without advisor approval.
2. **30-day rule** — Keep legacy flag branches commented, not deleted, until monitoring window closes.
3. **drug_area_scores** — Do NOT delete. 212 rows. Replacement is drug_competitive_scores (WS3 in progress).
4. **drug_areas** — Do NOT delete. Serves autoimmune/respiratory/tcell (→ WS4 strategic views).
5. **drug_competitive_scores consumers** — Do NOT update index.html consumers until migration committed + validated. Dual-write window required.
6. **epi-001** — 2 rows in backfill_preview as pending_review. Do NOT commit without source evidence.

---

## Validation Checks at Session Start

```sql
-- Standing rule: check for validation failures first
SELECT entity_id, check_type, check_status, failure_reason
FROM drug_validation_results
WHERE check_status IN ('fail','warning','needs_review')
ORDER BY check_status, entity_id
LIMIT 20;

-- Drug indications (post-Wave 3):
SELECT count(*) FROM drug_indications;   -- expect 246
-- Open ECC items:
SELECT entity_id, issue_key, status FROM entity_consistency_checks WHERE status = 'open';
```

---

## Files

- `docs/drug_competitive_scores_ddl.sql` — Apply via Supabase SQL Editor (P1)
- `scripts/migrate_drug_area_scores.py` — Run after DDL applied (P1)
- `docs/area_metadata_ddl.sql` — Apply via Supabase SQL Editor (P2)
- `docs/phase6_master_plan.md` — Full session sequence and dependency map
- `docs/drug_competitive_scores_design.md` — Consumer migration plan, dual-write strategy
