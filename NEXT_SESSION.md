# NEXT SESSION — BD Platform

**Written:** 2026-05-24 (Session 32)  
**Last work:** Coverage Framework — migration v30 + compute_coverage.py  
**Validation:** 993 pass / 0 fail / 7 skip ✅

---

## Session 32 Summary — Coverage Framework

### What was built
- `coverage_scores` table (migration v30) — 137 rows, one per company/area
- `scripts/compute_coverage.py` — 9 deterministic dimensions + CLI report + recommended actions
- Validation test `coverage_scores_row_existence` (id=1078)

### Initial platform state (first run: 2026-05-24)
| Dimension | Score | Flag |
|-----------|-------|------|
| Molecule intelligence | 99.5 | ✅ |
| Deal linkage | 97.1 | ✅ |
| Target mapping | 91.7 | ✅ |
| Confidence coverage | 82.7 | ✅ |
| Enrichment recency | 70.4 | ok |
| Profile completeness | 68.3 | ok |
| Source coverage | 59.5 | ⚠ |
| Ownership coverage | 57.7 | ⚠ |
| Catalyst coverage | 43.1 | ⚠ |

**Platform average: 71.3 / 100**

### Three clear system-wide gaps
1. **Catalyst coverage (43.1)** — most clinical drugs have no catalyst entries
2. **Source coverage (59.5)** — drug_area_scores rows systematically lack source_url
3. **Ownership coverage (57.7)** — licensed-in drugs often lack ownership_edges

---

## Next Steps (in priority order)

### P0 — Wire compute_coverage.py into nightly schedule
The script should run nightly so coverage scores reflect fresh enrichment data.  
Pattern: add scheduled GitHub Action or scheduled task calling `compute_coverage.py`.

### P1 — Wire ACTIVE_IN into company_intake.py
When `company_intake.py` writes a new `company_areas` row, it must also write the corresponding `entity_edges ACTIVE_IN` row for graph consistency.  
Pattern: add `write_active_in_edge()` alongside `write_acquisition_edges()`.

### P2 — Close the three system-wide coverage gaps

**Catalyst coverage (43.1) — highest impact**  
Most clinical drugs have no catalyst entries. This is partially a collection problem (catalysts need manual entry or automated monitoring), but some are addressable by reviewing enrichment output.  
- Run enrichment for stale company/area pairs with 0 catalysts
- Review whether catalyst data exists in company_profiles but wasn't extracted

**Source coverage (59.5)**  
Many drug_area_scores rows lack source_url. The enrichment script should be setting this.  
- Check company_enrichment.py source_url write behavior
- Consider a backfill script for drug_area_scores rows with `confidence='confirmed'` and no source

**Ownership coverage (57.7)**  
Licensed-in drugs (drugs with partner_company set) should have ownership_edges.  
- Run `company_intake.py` with `--write-ownership-edges` on companies with gap
- Or build a backfill script from drugs.partner_company → ownership_edges

### P3 — Easy remaining drug target mappings
- `linsitinib` → `igf1r` (target exists, just add drug_targets row)
- `kyv-101` → `cd19` (target exists, just add drug_targets row)
- `ianalumab` → add `baffr` target, then drug_targets row

### P4 — Coverage dashboard (future, not next session)
Once scores are stable and nightly compute is running, build a coverage view into the Meridian dashboard. The recommended_actions_json already has the data — it just needs a surface.

---

## DB State (end of Session 32)
| Table | Rows |
|-------|------|
| entity_edges (COMPETES_WITH) | 600 |
| entity_edges (TARGETS) | 146 |
| entity_edges (ACTIVE_IN) | 137 |
| drug_targets | 182 |
| targets | 47 |
| coverage_scores | 137 |
| validation_tests | 992+ |
| validation suite | 993 pass / 0 fail / 7 skip |

---

## Collection Priority Order (Kyle's ranking — future sessions)
1. FDA regulatory feed
2. SEC/EDGAR monitoring
3. Pipeline page change detection
4. Conference abstract collection (DDW, ACR, EULAR, AAAAI, ATS)
5. PubMed ingestion
6. Patents (long-horizon)
