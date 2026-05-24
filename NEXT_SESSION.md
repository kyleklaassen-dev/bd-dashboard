# NEXT SESSION — BD Platform

**Last updated:** 2026-05-24 (Session 41)  
**Session completed:** Preclinical competitor audit + seed; stale data patch ✅

---

## What Was Done This Session (Session 41)

### Preclinical Competitor Audit — completed ✅

Audited which preclinical TED × IGF-1R competitors exist in the DB:

| Bucket | Company | Drug | Status |
|--------|---------|------|--------|
| C (missing both) | Ollin Biosciences | OLN102 | Seeded ✅ |
| C | Septerna | SP-1351 | Seeded ✅ |
| C | Crinetics | CRN12755 | Seeded ✅ |
| C | Alumis | lonigutamab | Seeded ✅ |
| C | Minghui Pharma | MHB018A | Seeded ✅ |
| B (company exists, drug missing) | Innovent | ibi311 / SYCUME | Drug seeded ✅ |
| Already existed | Viridian | veligrotug, elegrobart | — |
| Already existed | Yarrow | yb-101 | — |

Script: `scripts/seed_preclinical_competitors.py`

### Stale Data Patched — completed ✅

- veligrotug: stage Regulatory Review → BLA Filed; route IV → SC
- elegrobart: stage Phase 3 → Phase 2
- yb-101: route SC → IV
- yarrow: name Yarrow Bioscience → Yarrow Biotechnology
- landscape_expected_competitors: drug_id linked for ibi311 + oln102

Script: `scripts/patch_stale_data.py`

### Coverage Score — stable at 89.75/100

Adding preclinical drugs didn't change the score (expected — they're not in
landscape_expected_competitors Tier 1 list). Score is limited by:
- Drug coverage 88.9% (OLN102 Tier 3 pending → will improve when IND confirmed)
- Staleness 27.3% (3 items needing real-world revalidation in Q3 2026)

---

## TED Coverage State (89.75/100 — live in DB)

| Dimension | Score | Detail |
|-----------|-------|--------|
| Drug coverage (×0.35) | 88.9% | 8/9 confirmed. OLN102 Tier 3 pending (IND unconfirmed) |
| Relationship coverage (×0.25) | 100% | 5/5 edges all populated |
| Catalyst coverage (×0.20) | 100% | 31/8 capped |
| Source validation (×0.15) | 100% | 13/13 sourced ← patched this session |
| Staleness penalty (×−0.05) | 27.3% | TSHR×TED mech, Japan geo, yb-101 edge |

Score ceiling without staleness improvement: ~90.5 (will increase to 100 when OLN102 confirmed + staleness items resolved Q3 2026)

---

## Drugs Now in DB for TED × IGF-1R Landscape

| Drug | Company | Stage | Target | Mechanism | In drug_areas |
|------|---------|-------|--------|-----------|---------------|
| teprotumumab | amgen | Approved | IGF-1R | Anti-IGF-1R mAb | igf1r, ted |
| ibi311/SYCUME | innovent | Approved | IGF-1R | Anti-IGF-1R mAb | igf1r, ted ← NEW |
| veligrotug | viridian | BLA Filed | IGF-1R | Anti-IGF-1R mAb SC | igf1r, ted |
| elegrobart | viridian | Phase 2 | IGF-1R | Anti-IGF-1R mAb SC | igf1r, ted |
| linsitinib | roche | Phase 2 | IGF-1R | Small molecule oral | igf1r, ted |
| yb-101 | yarrow | Phase 1 | TSHR | Anti-TSHR mAb | igf1r, ted |
| batoclimab | immunovant | Discontinued | FcRn | Anti-FcRn | fcrn, ted, autoimmune |
| efgartigimod | argenx | Discontinued | FcRn | Anti-FcRn | fcrn, autoimmune |
| oln102 | ollin | Preclinical | TSHR/IGF-1R | Bispecific mAb | igf1r, ted ← NEW |
| sp-1351 | septerna | Preclinical | TSHR | GPCR small molecule | ted, autoimmune ← NEW |
| crn12755 | crinetics | Preclinical | SST2 | SST2 agonist oral | ted ← NEW |
| lonigutamab | alumis | Preclinical | TSHR | Anti-TSHR mAb | ted, autoimmune ← NEW |
| mhb018a | minghui | Preclinical | IGF-1R | Anti-IGF-1R mAb | igf1r, ted ← NEW |

**Dashboard visibility:** All new drugs will appear under "All" pill on IGF-1R tab.
No filter change needed — `_makeAreaPI` fetches all drug_areas entries without stage filter.

---

## P1 Next: competitive_relevance column on drug_area_scores

Add `competitive_relevance TEXT` (enum: very_high / high / medium / low / monitor) to
`drug_area_scores` as a **second dimension** separate from development stage.

Strategic rationale: Ailux is preclinical. OLN102 (preclinical bispecific) is more
strategically relevant than teprotumumab (approved, known). Stage ≠ relevance.

| Drug | Stage | competitive_relevance | Reason |
|------|-------|-----------------------|--------|
| oln102 | Preclinical | very_high | Bispecific → potential class disruption |
| veligrotug | BLA Filed | very_high | PDUFA June 30; SC route advantage → immediate market threat |
| elegrobart | Phase 2 | high | Next Viridian asset; SC autoinjector |
| yb-101 | Phase 1 | high | Upstream TSHR mechanism → changes paradigm if works |
| sp-1351 | Preclinical | high | Oral TSHR SM → route + mechanism differentiation |
| linsitinib | Phase 2 | medium | Oral IGF-1R SM; differentiated but Roche not TED-focused |
| lonigutamab | Preclinical | medium | TSHR mAb crowded (YB-101 ahead); watch space |
| crn12755 | Preclinical | medium | SST2 adjacent mechanism; watch |
| mhb018a | Preclinical | low | China IGF-1R; minimal US impact |
| teprotumumab | Approved | low | Market leader; Ailux would partner with/around, not compete |
| ibi311 | Approved | low | China-only; reference for Asia market |
| batoclimab | Discontinued | monitor | Failed FcRn; negative data is signal |
| efgartigimod | Discontinued | monitor | Failed FcRn; confirms mechanism failure |

**Implementation:**
1. `ALTER TABLE drug_area_scores ADD COLUMN competitive_relevance TEXT`
2. `patch_competitive_relevance.py` — seeds the above values
3. Dashboard: surface competitive_relevance badge alongside stage pill

---

## P2 Next: competitive_signals table

Dedicated table for conference/patent/financing signals per asset. Schema discussed:
```sql
CREATE TABLE competitive_signals (
    id              BIGSERIAL PRIMARY KEY,
    company_id      TEXT REFERENCES companies(id),
    drug_id         TEXT REFERENCES drugs(id),
    signal_type     TEXT NOT NULL,  -- 'conference', 'patent', 'financing', 'publication', 'licensing'
    title           TEXT NOT NULL,
    description     TEXT,
    source_url      TEXT,
    source_date     DATE,
    confidence      NUMERIC(3,2) DEFAULT 0.8,
    area_id         TEXT REFERENCES drug_areas(area_id),
    created_at      TIMESTAMPTZ DEFAULT now()
);
```
Seed with known signals: Viridian ASCO 2025 poster, OLN102 preclinical presentation (if any),
Crinetics ENDO 2025, etc.

---

## P3 Later: Re-enrich with area-aware prompt

Run area-aware enrichment for igf1r companies to validate the updated prompt framing:
```bash
python3 scripts/company_enrichment.py --company amgen --area igf1r --step 5
```

---

## Q3 2026 Revalidation Queue

| Item | Date | Action |
|------|------|--------|
| Veligrotug PDUFA | 2026-06-30 | Update stage → Approved or CRL; update entity_edge basis_tags |
| OLN102 IND check | 2026-10-01 | CT.gov; if filed, promote to Tier 1 confirmed=TRUE, drug coverage → 100% |
| TSHR × TED (YB-101 Phase 1b) | 2026-10-01 | Update staleness_status → fresh after data |
| Tepezza Japan PMDA exact date | 2026-10-01 | Update geographic_approvals staleness_status |
| yb-101 UPSTREAM_MECHANISM edge | 2026-10-01 | Revalidate after Phase 1b data |

---

## Script Reference

| Script | Status | Purpose |
|--------|--------|---------|
| `scripts/migrations/v31_competitive_landscape.sql` | ✅ Applied | DDL for 3 new tables + extensions |
| `scripts/migrations/v32_coverage_diagnostics.sql` | ✅ Applied | Coverage scoring tables + columns |
| `scripts/run_v31_seed.py` | ✅ Run | TED mechanism/landscape/geo/edges/catalysts |
| `scripts/seed_missing_igf1r_entities.py` | ✅ Run | Viridian + veligrotug/elegrobart/yb-101 |
| `scripts/seed_ted_expected_competitors.py` | ✅ Run | 9-row Tier 1 list + expected counts |
| `scripts/compute_landscape_coverage.py` | ✅ Live | Re-run after any enrichment |
| `scripts/patch_source_validation.py` | ✅ Run | source_url + confidence for 6 drug_area_scores rows |
| `scripts/seed_preclinical_competitors.py` | ✅ Run | 5 companies + 6 drugs + 11 drug_areas + 11 drug_area_scores |
| `scripts/patch_stale_data.py` | ✅ Run | veligrotug/elegrobart/yb-101 fields; ibi311+oln102 drug_id links |
| `scripts/validate_ted_landscape.sql` | ✅ Passed | Acceptance test A–F |
