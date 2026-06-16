# drug_competitive_scores Migration Report
**Session 62 — 2026-05-26**

---

## 1. DDL Execution Validation

| Check | Result |
|---|---|
| `drug_competitive_scores` table created | ✅ |
| 16 columns with correct types | ✅ |
| UNIQUE(drug_id, context_type, context_id) constraint | ✅ |
| FOREIGN KEY drug_id → drugs(id) | ✅ |
| CHECK constraint: context_type IN ('target','indication','strategic_view','platform_view') | ✅ |
| CHECK constraint: overlap IN ('Direct','Adjacent','Same-Space','Watch') | ✅ |
| CHECK constraint: confidence_level IN ('A','B','C','inferred') | ✅ |
| 4 performance indexes created | ✅ |
| RLS enabled: anon SELECT, service_role ALL | ✅ |
| updated_at trigger | ✅ |
| Initial row count: 0 | ✅ |
| drug_area_scores unmodified | ✅ |

---

## 2. area_metadata Validation

| Check | Result |
|---|---|
| `area_metadata` table created | ✅ |
| 11 area_ids seeded | ✅ |
| Redirected (ontology_biological): ibd, igf1r, ted, tl1a, il4ra, tslp, atopy, fcrn | ✅ all 8 |
| Preserved (curated_strategic): autoimmune, respiratory | ✅ both |
| Preserved (curated_platform): tcell | ✅ |
| lifecycle_state = 'redirected' for all 8 biological areas | ✅ |
| lifecycle_state = 'preserved_curated' for autoimmune, respiratory | ✅ |
| lifecycle_state = 'preserved_platform' for tcell | ✅ |
| retirement_status = 'flag_activated' for fcrn (activated this session) | ✅ |
| retirement_status = 'legacy_retained' for ibd, igf1r, ted, tl1a, il4ra, tslp, atopy | ✅ |
| retirement_status = 'not_started' for autoimmune, respiratory, tcell | ✅ |
| flag_activated_at: phase_5.3 areas = 2026-05-25, phase_5.4/5.5 = 2026-05-26 | ✅ |

---

## 3. Migration Audit Report

### Source: drug_area_scores

| area_id | source rows | context type | context id | output rows | note |
|---|---|---|---|---|---|
| ibd | 49 | indication | uc + cd | 89 | UC/CD expansion via drug_indications |
| igf1r | 9 | indication | ted | 0 | All deduped against ted area (ted kept as higher priority) |
| ted | 13 | indication | ted | 13 | |
| tl1a | 50 | target | tl1a | 50 | |
| il4ra | 9 | target | il4ra | 9 | +1 from atopy expansion = 10 total |
| tslp | 14 | target | tslp | 14 | |
| atopy | 10 | target | il4ra / tslp | 1 | 9 deduped against il4ra/tslp area rows |
| fcrn | 7 | target | fcrn | 7 | |
| autoimmune | 25 | strategic_view | autoimmune | 25 | |
| respiratory | 14 | strategic_view | respiratory | 14 | |
| tcell | 12 | platform_view | tcell | 12 | |
| **TOTAL** | **212** | | | **234** | |

### Confidence Level Mapping (legacy → new)

| Legacy value | Count | Mapped to | Rationale |
|---|---|---|---|
| `confirmed` | 67 | `A` | Direct primary-source evidence |
| `supported` | 76 | `B` | Secondary/indirect evidence |
| `inferred` | 42 | `inferred` | Kept as-is |
| NULL | 27 | NULL | Kept as-is |

---

## 4. Post-Commit Validation

| Check | Result |
|---|---|
| Total rows: 234 | ✅ |
| Context type distribution | ✅ |
| 0 NULL overlap rows | ✅ |
| 0 duplicate (drug_id, context_type, context_id) tuples | ✅ |
| 0 unmapped area_ids | ✅ |
| 0 NULL context_type or context_id | ✅ |
| **Spot-checks** | |
| risankizumab / indication/cd: overlap=Adjacent | ✅ |
| mirikizumab / indication/uc: overlap=Watch | ✅ |
| upadacitinib / indication/uc: overlap=Watch | ✅ |
| efgartigimod / target/fcrn: overlap=Direct | ✅ |
| dupilumab / target/il4ra: overlap=Direct | ✅ |

---

## 5. Old vs. New Comparison

### Row Counts
| Table | Rows | Distinct drugs |
|---|---|---|
| drug_area_scores (legacy) | 212 | 106 |
| drug_competitive_scores (new) | 234 | 106 |
| Delta | +22 | 0 |

The +22 comes from IBD expansion: 49 IBD drugs → 89 indication-context rows (46 UC + 40 CD + 3 fallback IBD).

### Context Type Distribution (new table)

| context_type | rows | % |
|---|---|---|
| indication | 102 | 43.6% |
| target | 81 | 34.6% |
| strategic_view | 39 | 16.7% |
| platform_view | 12 | 5.1% |

### Overlap Distribution

| overlap | legacy | new |
|---|---|---|
| Direct | 102 | 115 |
| Watch | 79 | 84 |
| Adjacent | 28 | 31 |
| Same-Space | 3 | 4 |

New counts are higher due to IBD expansion: each IBD drug's overlap propagates to both UC and CD contexts.

### Confidence Distribution

| value | legacy (label) | new (label) |
|---|---|---|
| confirmed / A | 67 | 70 |
| supported / B | 76 | 75 |
| inferred | 42 | 58 |
| NULL | 27 | 31 |

Counts shift slightly due to deduplication — where igf1r and atopy rows were replaced by ted/il4ra/tslp rows with different confidence, the better row was kept.

### Migration Losses
Zero true losses. All 212 source rows are represented in the output:
- igf1r (9 rows): collapsed into `indication/ted` context — ted rows had equal or better confidence
- atopy (9 rows): collapsed into `target/il4ra` or `target/tslp` — those area rows already tracked these drugs
- All source intelligence fields (overlap, overlap_rationale, cls, vs_ailux, source_url) carried over. Original area_id stored in `migrated_from` for full auditability.

### 3 indication/ibd Fallback Rows
3 IBD drugs have no drug_indications rows for UC or CD. They fall back to `indication/ibd`:

```sql
SELECT drug_id FROM drug_competitive_scores 
WHERE context_type='indication' AND context_id='ibd';
```

These are drugs in the IBD competitive landscape without UC/CD ontology entries yet. They should be reviewed in a future Wave 4 drug_indications sprint.

---

## 6. Recommended Next Steps for Dashboard Integration

**Not yet ready for consumer cutover.** drug_competitive_scores is a validated parallel-read layer. The dashboard still reads drug_area_scores for all competitive intelligence.

### Consumer Migration Sequence (WS3 continuation)

The migration plan is in `docs/drug_competitive_scores_design.md`. High-level:

1. **Identify 8 consumers** in index.html that read drug_area_scores
2. **Dual-write window**: update `company_enrichment.py` to write to both tables simultaneously
3. **Consumer-by-consumer migration**: move each dashboard read to drug_competitive_scores, validate, deploy
4. **Monitor**: 30-day window per consumer before legacy reads are removed
5. **drug_area_scores → read-only** when all consumers migrated

### Immediate action available
The 3 `indication/ibd` fallback drugs can be investigated now:
```sql
SELECT drug_id, migrated_from FROM drug_competitive_scores WHERE context_id = 'ibd';
```
If these drugs have UC/CD trial data, they should be backfilled in drug_indications before consumer migration.

---

*Generated Session 62 — 2026-05-26. drug_area_scores untouched as legacy provenance.*
