# NEXT SESSION — BD Platform

**Last updated:** 2026-05-24 (Session 42b)
**Session completed:** Relevance sort wired into `_makeAreaPI` — competitive_relevance default sort + left-border color indicator ✅

---

## What Was Done This Session (Session 42b)

### Relevance Sort — `_makeAreaPI` ✅
- `drug_area_scores` select includes `competitive_relevance`
- `bestRelevance` computed per entity (most relevant across programs)
- Default `sortCol` changed from `'stage'` → `'relevance'`
- Sort: relevance tier first (very_high→monitor), nulls last, stage as tiebreaker
- Left-border color on each entity row: red/orange/amber/blue/slate/none
- Graceful degradation: tabs without `competitive_relevance` data behave identically to previous stage sort
- Deployed: commit a27bff05

---

## What Was Done This Session (Session 42)

### Preclinical Blind Spot Audit ✅
Full audit confirming root cause: `gather_landscape_intel` was hardcoded to "Phase 1 or later" /
"clinical-stage programs". Preclinical excluded by design across all areas. TL1A exception was
one-time manual curation. Renderer confirmed clean (no stage filter; Preclinical renders correctly).

### Enrichment Prompt Fix ✅ — company_enrichment.py
- `LANDSCAPE_SEARCH_SYSTEM`: Removed "Phase 1 or later" restriction
- `gather_landscape_intel` prompt: All stages from Preclinical through Approved; source matrix
  expanded to pipeline pages, IR presentations, conference abstracts, ChiCTR registry
- Next enrichment run for atopy, fcrn, respiratory, tslp will now surface preclinical programs

### Respiratory / TSLP Type B Backfill ✅
3 drugs in DB with 0 area assignments — fixed:
- **WIN378** (Windward Bio, Phase 3): drug_areas + drug_area_scores × respiratory, tslp
- **BSI-045B** (Biosion, Phase 1): Added Biosion company; drug_areas + drug_area_scores × both
- **APG333** (Apogee, Phase 1): New drug added to DB; drug_areas + drug_area_scores × both

Respiratory/tslp: 11 → 14 drugs; Apogee + Biosion added to company_areas for both areas.

---

## What Was Done This Session (Session 41)

### Preclinical Competitor Seed ✅
5 companies + 6 drugs added (Ollin/OLN102, Septerna/SP-1351, Crinetics/CRN12755,
Alumis/lonigutamab, Minghui/MHB018A, Innovent/ibi311). 11 drug_areas + 11 drug_area_scores.

### Data Quality Corrections ✅
- veligrotug (VRDN-001) = **IV**, BLA Filed, PDUFA June 30 2026 — confirmed via Viridian IR
- elegrobart (VRDN-003) = **SC** autoinjector, **Phase 3** — REVEAL-1 ✅ (active TED, Mar 2026)
  and REVEAL-2 ✅ (chronic TED, May 2026) both positive; BLA submission Q1 2027

  > Note: patch_stale_data.py from earlier this session introduced errors — reversed here.
  > These corrections are now live in DB and verified against Viridian press releases.

### competitive_relevance Column ✅
Added `competitive_relevance TEXT` + `relevance_rationale TEXT` to `drug_area_scores`.
28 rows seeded for TED × IGF-1R landscape.

---

## Current Drug_Area_Scores: competitive_relevance Distribution

| Level | Drugs | Rationale |
|-------|-------|-----------|
| 🔴 very_high | veligrotug (×igf1r,ted), elegrobart (×igf1r,ted), oln102 (×igf1r,ted) | PDUFA imminent / Phase 3 positive / bispecific disruptor |
| 🟠 high | yb-101 (×igf1r,ted), sp-1351 (×ted,autoimmune), crn12755 (×ted) | Mechanism differentiation or oral route advantage |
| 🟡 medium | lonigutamab (×ted,autoimmune), linsitinib (×igf1r,ted), mhb018a (×igf1r,ted) | Adjacent or limited-geography assets |
| 🔵 low | teprotumumab (×igf1r,ted), ibi311 (×igf1r,ted) | Approved benchmarks; Ailux partners with/around, not against |
| ⚫ monitor | batoclimab (×fcrn,ted,igf1r,autoimmune), efgartigimod (×fcrn,ted,autoimmune) | Failed FcRn; negative data as signal |

---

## Drugs in DB — Corrected State (2026-05-24)

| Drug | Company | Stage | Route | competitive_relevance |
|------|---------|-------|-------|-----------------------|
| teprotumumab | amgen | Approved | IV | low |
| ibi311/SYCUME | innovent | Approved | IV | low |
| veligrotug | viridian | **BLA Filed** | **IV** | very_high |
| elegrobart | viridian | **Phase 3** | **SC** | very_high |
| linsitinib | roche | Phase 2 | oral | medium |
| yb-101 | yarrow | Phase 1 | IV | high |
| oln102 | ollin | Preclinical | IV | very_high |
| sp-1351 | septerna | Preclinical | oral | high |
| crn12755 | crinetics | Preclinical | oral | high |
| lonigutamab | alumis | Preclinical | IV | medium |
| mhb018a | minghui | Preclinical | IV | medium |
| batoclimab | immunovant | Discontinued | IV | monitor |
| efgartigimod | argenx | Discontinued | SC | monitor |

---

## ✅ DONE: Dashboard sort by competitive_relevance (Session 42b)

TED tab now renders entities sorted by relevance tier with left-border color indicator.
Left-border colors: very_high=red, high=orange, medium=amber, low=blue, monitor=slate.
All other tabs degrade gracefully to stage sort (no `competitive_relevance` data yet).

---

## P2 Later: competitive_signals table

For conference/patent/financing signal tracking. Schema:
```sql
CREATE TABLE competitive_signals (
    id           BIGSERIAL PRIMARY KEY,
    company_id   TEXT REFERENCES companies(id),
    drug_id      TEXT REFERENCES drugs(id),
    signal_type  TEXT NOT NULL,  -- 'conference','patent','financing','publication','licensing'
    title        TEXT NOT NULL,
    description  TEXT,
    source_url   TEXT,
    source_date  DATE,
    confidence   NUMERIC(3,2) DEFAULT 0.8,
    area_id      TEXT,
    created_at   TIMESTAMPTZ DEFAULT now()
);
```

---

## Coverage Score: 89.75/100 (stable)

| Dimension | Score |
|-----------|-------|
| Drug coverage (×0.35) | 88.9% — OLN102 pending IND |
| Relationship coverage (×0.25) | 100% |
| Catalyst coverage (×0.20) | 100% |
| Source validation (×0.15) | 100% |
| Staleness penalty (×−0.05) | 27.3% — 3 items need Q3 2026 revalidation |

---

## Q3 2026 Revalidation Queue

| Item | Date | Action |
|------|------|--------|
| Veligrotug PDUFA | 2026-06-30 | Approved or CRL — update stage + entity_edges |
| Elegrobart BLA | 2026-Q1-2027 | Confirm submission; update stage to BLA Filed |
| OLN102 IND | 2026-10-01 | CT.gov; if filed → promote to Tier 1 confirmed, drug coverage → 100% |
| YB-101 Phase 1b | 2026-10-01 | Data → update TSHR×TED mechanism staleness |
| Tepezza Japan PMDA | 2026-10-01 | Confirm exact date; update geo_approvals staleness |

---

## Script Reference

| Script | Status | Purpose |
|--------|--------|---------|
| `scripts/migrations/v31_competitive_landscape.sql` | ✅ Applied | DDL for competitive layer |
| `scripts/migrations/v32_coverage_diagnostics.sql` | ✅ Applied | Coverage scoring schema |
| `scripts/run_v31_seed.py` | ✅ Run | TED mechanism/landscape/edges/catalysts |
| `scripts/seed_missing_igf1r_entities.py` | ✅ Run | Viridian + veligrotug/elegrobart/yb-101 |
| `scripts/seed_ted_expected_competitors.py` | ✅ Run | 9-row Tier 1 expected list |
| `scripts/compute_landscape_coverage.py` | ✅ Live | Re-run after enrichment |
| `scripts/patch_source_validation.py` | ✅ Run | Source URLs for 6 drug_area_scores rows |
| `scripts/seed_preclinical_competitors.py` | ✅ Run | 5 companies + 6 drugs + drug_areas |
| `scripts/patch_stale_data.py` | ✅ Run | LEC drug_id links; Yarrow name |
| `scripts/add_competitive_relevance.py` | ✅ Run | competitive_relevance + relevance_rationale seeded |
| `scripts/validate_ted_landscape.sql` | ✅ Passed | Acceptance test A–F |
