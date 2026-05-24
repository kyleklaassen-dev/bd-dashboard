# NEXT SESSION — BD Platform

**Last updated:** 2026-05-24 (Session 46)
**Session completed:** HQ display + column widths + no-resize + default relevance sort ✅

---

## What Was Done This Session (Session 46)

### Company HQ Data + Ticker Fix ✅
- Migration v34: added `hq_city` + `hq_country` TEXT columns to `companies` table
- `scripts/seed_company_hq.py`: seeded 95 companies with city/country; fixed NULL tickers (PFE, ROIV, 4519.T, 6996.HK, rest → 'Private')
- Commits: `feef5362c5` (seed script), `cb946667a2` (UI)

### PI Tab Entity Rows — Ticker + City, Country ✅
- Every entity subline now shows `TICKER — City, Country` or `Private — City, Country`
- `hq_city`/`hq_country` threaded through `_makeAreaPI` data model + render

### Column Widths + No-Resize + Default Sort ✅
- Indication column widened: 9% → 13%; full colgroup: `19% 11% 13% 17% 11% 14% 15%`
- Indication badge: `white-space:nowrap;display:inline-block` — no second-row wrapping
- Target td: `white-space:nowrap;overflow:hidden;text-overflow:ellipsis`
- All tabs default to relevance sort (`sortCol:'relevance'`)
- No column resizing on any tab (col-resize handles fully removed via tl1aPI migration)

### seed_competitive_signals.py: area_id fix ✅
- Rewritten with `area_id='igf1r'` throughout (was `'ted'`). Commit: `1d89542ef1`

---

## What Was Done This Session (Session 45)

### tl1aPI → _makeAreaPI Migration ✅
- Removed `TL1A_PROGRAMS`, `TL1A_STAGE_ORDER`, `SPYRE_PIPELINE`, `AILUX_MOLECULES` static data
- Removed `piPillClick` standalone function and entire `tl1aPI` object (~1,800 lines)
- Moved `_genericDetailHTML(prog, sbData, tabId)` (969 lines) into `_makeAreaPI` factory as a native method
- All `tl1aPI._genericDetailHTML.call(tl1aPI, ...)` references → `this._genericDetailHTML(...)`
- TL1A card HTML rewired: `tl1a-pi-card` → `tl1a-area-pi-wrap` + `tl1a-area-pi` inner target
- `registerTab('tl1a')`: removed `tl1aPI.init()`, added `loadAreaPI('tl1a')`
- Removed from DOMContentLoaded: `tl1aPI.init(); tl1aPI._initialized = true;`
- All 9 drug tabs now use identical `_makeAreaPI` factory architecture
- File: 15,976 → 14,222 lines (-1,754 lines)
- Commit: `b4355353`

---
## What Was Done This Session (Session 44)

### UI Alignment Fixes ✅
- **`.tl1a-layout` padding-top:10px**: All drug tabs now have consistent 10px gap at top, aligned with BD Takeaways / Ailux Profile pill buttons. Previously TL1A tab was flush against tab bar.
- **IGF1R×TSHR filter pills**: Replaced coverage panel div (`id="igf1r-tshr-coverage-pills"`) with standard `class="pi-pills-wrap"`. Class/Stage/Relevance filter pills now render correctly, matching all other drug tabs.
- **`TAB_LANDSCAPE_MAP` igf1r-tshr entry commented out**: Prevents `loadLandscapeCoverage` from overwriting the pills div. Coverage data remains in DB; can be restored to a dedicated panel in a future session.
- **Commit**: `0a704446`

---

## What Was Done This Session (Session 43)

### competitive_signals — Full Stack ✅
- **Migration v33**: table created (Supabase) — 12 cols, 5 indexes, 3 CHECK constraints
- **Seed**: 17 TED landscape signals (veligrotug/elegrobart/OLN102/SP-1351/CRN12755/YB-101/linsitinib/teprotumumab/batoclimab)
- **Enrichment**: `competitive_signals` array in Step 5 prompt + write block in `write_step5()` with dedup + validation
- **UI**: `📡 Competitive Signals` card in entity expand panel — date | type badge | linked title | description; scrollable >4; hidden when empty
- Signal type badge palette: CONF=blue, READOUT=green, REG=red, $=emerald, PATENT=purple, PUB=indigo, DEAL=orange

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
