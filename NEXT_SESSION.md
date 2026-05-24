# NEXT SESSION — BD Platform

**Last updated:** 2026-05-24 (Session 39 cont.)  
**Session completed:** v32 Coverage Diagnostics — first live score + dashboard coverage panel deployed ✅

---

## What Was Done This Session (Sessions 38–39)

### v31 (TED × IGF-1R_TSHR competitive layer) — completed ✅
- Migration applied: mechanism_status, competitive_landscapes, geographic_approvals, entity_edges extensions, catalysts extensions
- TED seed complete: 5 mechanism_status rows, 1 landscape, 3 geographic_approvals, 5 entity_edges, catalyst updates
- entity_edges unblocked: Added Viridian/Yarrow/GenSci companies + veligrotug/elegrobart/yb-101 drugs; ran run_v31_seed.py to populate all 5 edges

### v32 (Coverage Diagnostics) — completed ✅
- Migration applied: `v32_coverage_diagnostics.sql` (11 columns + landscape_expected_competitors + coverage_computation_log)
- TED seed: 9 rows in `landscape_expected_competitors` (8 Tier 1 confirmed, 1 Tier 3 OLN102 pending)
- Script: `scripts/compute_landscape_coverage.py` — derives all 5 sub-scores, applies formula, writes to DB
- First compute run: TED **82.82/100** (vs self-reported 87.0) — written live to DB
- Deployed to GitHub: `compute_landscape_coverage.py` + `v32_coverage_diagnostics.sql`

---

## TED Coverage State (82.82/100 — live in DB)

| Dimension | Score | Detail |
|-----------|-------|--------|
| Drug coverage (×0.35) | 88.9% | 8/9 confirmed. Missing: oln102 (Tier 3 pending revalidation) |
| Relationship coverage (×0.25) | 100% | 5/5 edges (veligrotug↔tepezza, elegrobart SUBSTITUTES, linsitinib SUBSTITUTES, yb-101 UPSTREAM) |
| Catalyst coverage (×0.20) | 100% | 31 catalysts vs 8 expected (capped at 1.0) |
| Source validation (×0.15) | 53.8% | 7/13 drug_area_scores have source_url + confidence_level |
| Staleness penalty (×−0.05) | 27.3% | 3 stale: TSHR×TED mechanism, Japan geo approval, yb-101 edge |

**Score formula:** 0.35×drug + 0.25×relationship + 0.20×catalyst + 0.15×source − 0.05×staleness

---

## P1 Next: Source Validation Backfill

Source validation is at 53.8% — the main drag on the score. The unsourced rows are:
- `batoclimab` drug_area_scores — 4 rows missing source_url (igf1r + ted × 2)
- `efgartigimod` drug_area_scores — missing source_url
- `linsitinib` drug_area_scores — missing source_url

**Backfill sources:**
- batoclimab failure: Immunovant April 2026 Ph3 TED failure press release
- efgartigimod: argenx UplighTED discontinuation Dec 2025 press release
- linsitinib: Roche pipeline page or ClinicalTrials.gov NCT ID for TED trial

After backfilling these 6 rows, source_validation → ~85%, score moves to ~86.

Script: `patch_source_validation.py` — PATCH drug_area_scores with source_url + confidence_level for these 3 drugs.
Then re-run `compute_landscape_coverage.py` to see score movement.

---

## ✅ DONE: Dashboard Coverage Panel (Session 39 cont.)

Coverage panel is live on the IGF1R × TSHR tab. Shows above the PI table on tab enter:
- Score badge: "TED Coverage 82/100" (color-coded green/amber/red)
- Dimension pills: Drug 89% · Edges 100% · Catalyst 100% · Source 54%
- Staleness warning: "⚠ 27% stale"
- Missing drug chips (currently: OLN102)

Commit: `cbf7de22` (index.html)

`TAB_LANDSCAPE_MAP = { 'igf1r-tshr': { area_id: 'igf1r' } }` — extend for future landscapes.

---

## Data Quality Notes (from this session)

The veligrotug/elegrobart/yb-101 records in the DB have stale field values from a prior session:
- veligrotug: stage=Regulatory Review, route=IV (correct: stage=Filed, route=SC)
- elegrobart: stage=Phase 3 (correct: stage=Phase 2)
- yb-101: route=SC (correct: route=IV)
- yarrow: name=Yarrow Bioscience (correct: Yarrow Biotechnology)

These don't affect entity_edges or coverage scoring but should be patched before any dashboard display of drug-level detail. Write `patch_viridian_drug_fields.py` if needed (PATCH drugs table via PostgREST).

---

## ibi311 Drug ID Gap

`ibi311` is confirmed Tier 1 in `landscape_expected_competitors` but has `drug_id=NULL` — not in the `drugs` table under that ID. May be stored as `sycume` or another identifier. Check:
```python
get("drugs", {"name": "ilike.*IBI311*", "select": "id,name,company_id"})
get("drugs", {"name": "ilike.*SYCUME*", "select": "id,name,company_id"})
```
If found, PATCH landscape_expected_competitors.drug_id for the ibi311 row.

---

## Q3 2026 Revalidation Queue

| Item | Date | Action |
|------|------|--------|
| Veligrotug PDUFA | 2026-06-30 | Update stage → Approved or CRL; update entity_edge basis_tags |
| OLN102 IND check | 2026-10-01 | CT.gov search; if filed, promote from Tier 3 → Tier 1, confirmed=TRUE |
| TSHR × TED (YB-101 Phase 1b) | 2026-10-01 | GenSci/Yarrow enrollment update |
| Tepezza Japan PMDA exact date | 2026-10-01 | Update geographic_approvals, staleness_status → fresh |
| yb-101 UPSTREAM_MECHANISM edge | 2026-10-01 | Revalidate after YB-101 Phase 1b data |

---

## Script Reference

| Script | Status | Purpose |
|--------|--------|---------|
| `scripts/migrations/v31_competitive_landscape.sql` | ✅ Applied | DDL for 3 new tables + entity_edges/catalysts extensions |
| `scripts/migrations/v32_coverage_diagnostics.sql` | ✅ Applied | 11 new columns + landscape_expected_competitors + coverage_computation_log |
| `scripts/run_v31_seed.py` | ✅ Run | Seeds mechanism_status, competitive_landscapes, geo_approvals, entity_edges, catalysts |
| `scripts/seed_missing_igf1r_entities.py` | ✅ Run | Idempotent: adds Viridian + veligrotug/elegrobart/yb-101 if missing |
| `scripts/seed_ted_expected_competitors.py` | ✅ Run | Seeds 9-row Tier 1 list + sets expected counts on landscape |
| `scripts/compute_landscape_coverage.py` | ✅ Run | Derives scores, writes to competitive_landscapes + log. Re-run after any enrichment. |
| `scripts/validate_ted_landscape.sql` | ✅ Passed | Acceptance test — all sections A–F pass |
