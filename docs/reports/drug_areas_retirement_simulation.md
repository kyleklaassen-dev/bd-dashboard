# Drug Areas Retirement Simulation
**Generated:** Session 58 — 2026-05-26  
**Status:** Governance sprint output — advisor review required  
**Purpose:** Simulate complete removal of the `drug_areas` table. Map every consumer. Classify each as: survives unchanged / survives after redirect / breaks / requires replacement. Determine retirement readiness by area.

---

## The Simulation Question

"Assume `drug_areas` (and by extension `drug_area_scores`) disappears tomorrow. What breaks?"

This simulation treats `drug_areas` and `drug_area_scores` together, since they are functionally paired — `drug_areas` provides membership, `drug_area_scores` provides competitive scoring. Both would need to be retired together.

---

## Consumer Inventory

### Dashboard (index.html) Consumers

**C1 — `_makeAreaPI()` — Primary drug list fetch**  
Location: Line 3595  
```javascript
_sb.from('drug_areas').select('drug_id, drugs(...)').eq('area_id', areaId)
```
Called by: All PI tabs (tl1a, tslp, il4ra-tslp, il4ra-ox40l, igf1r-tshr, fcrn, ace)  
Role: Fetches the member drugs for a competitive intelligence tab

| Area_id | Status | Verdict |
|---------|--------|---------|
| `tl1a` | Redirected (C4) | ✅ Survives — `_TL1A_NORM` path reads `drug_targets` |
| `ibd` | Redirected (C1) | ✅ Survives — `_IBD_NORM` path reads `drug_indications` |
| `igf1r` | Redirected (C2) | ✅ Survives — `_TED_NORM` path reads `drug_indications` |
| `il4ra` | Pending (C5/C6) | ⚠️ Breaks until `useUnifiedAtopy=true` activates |
| `tslp` | Pending (C5/C6) | ⚠️ Breaks until `useUnifiedAtopy=true` activates |
| `fcrn` | Planned (C7) | 🔴 Breaks — no normalized path yet |
| `tcell` | No migration | 🔴 Breaks — `ace` tab goes empty |

---

**C2 — `_makeAreaPI()` — Company drug list (combo/pipeline)**  
Location: Line 12705  
```javascript
_sb.from('drug_areas').select('drugs(id,company_id,indication_short)').in('area_id', this.areaIds).limit(500)
```
Called by: _makeAreaPI, alongside C1, for company-level pipeline display  
Role: Builds the company pipeline view within a PI tab

Status: **Same verdict as C1** — only areas with active feature flags survive. Applies to all 7 area_ids above.

---

**C3 — Research Queue drug discovery**  
Location: Line 11511  
```javascript
const { data: daRows } = await _sb.from('drug_areas').select('area_id').in('drug_id', drugIds)
```
Called by: Discovery queue population — identifies which areas a drug belongs to, used to route research results to the right tab  
Role: Maps discovered drugs to their tabs via area_id membership

| Status | Verdict |
|--------|---------|
| For redirected areas (tl1a, ibd, igf1r) | ⚠️ Breaks — after retirement, area routing must come from drug_targets.target_id + targets.disease_areas or drug_indications |
| For active areas (tcell, fcrn) | 🔴 Breaks |
| **Overall** | **Breaks** — requires replacement routing logic using normalized tables |

**Fix required:** Build a unified area-routing function that queries `drug_targets → targets.disease_areas` + `drug_indications → indications.disease_area` instead of `drug_areas`.

---

**C4 — Drug Entity Modal — Area membership display**  
Location: Lines 11675–11677  
```javascript
_sb.from('drug_areas').select('area_id').eq('drug_id', drugId),
_sb.from('drug_area_scores').select('area_id,overlap,overlap_rationale,strategic_role,cls,confidence_level,source_url').eq('drug_id', drugId),
```
Called by: Drug click → entity modal (shows which areas the drug belongs to + competitive scoring)  
Role: Displays area badges + overlap classification + rationale in the drug modal

| Flag state | Verdict |
|------------|---------|
| `useNormalizedDrugModal=true` (C3 active) | ⚠️ Partially survives — C3 reads `drug_targets` + `drug_indications` for area membership. BUT the modal still reads `drug_area_scores` for overlap/rationale display. Removing drug_area_scores breaks the competitive scoring display even with C3 active. |
| `drug_area_scores` specifically | 🔴 Breaks — overlap classification, rationale, cls, confidence_level all come from drug_area_scores. No normalized replacement exists for these enrichment outputs. |

**Critical finding:** `drug_area_scores` is NOT safely retirable even after all feature flags are activated. It contains enrichment output (overlap classification, competitive rationale) that has no equivalent in drug_targets or drug_indications. It is an independent assessment layer.

---

**C5 — Drug Entity Modal — Related drug area membership**  
Location: Lines 11716–11717  
```javascript
_sb.from('drug_areas').select('area_id').eq('drug_id', rid),
_sb.from('drug_area_scores').select('area_id,...').eq('drug_id', rid),
```
Called by: Modal related drugs section — shows areas for "related" drugs  
Same verdict as C4.

---

**C6 — Competitive Areas filter in Drugs tab**  
Location: Line 9835  
```javascript
_sb.from('drug_areas').select('drug_id').eq('area_id', DRUG_AREA)
```
Called by: Company PI view — fetches which drugs in an area belong to a company  
Role: Filters drugs within a company profile for a specific competitive area

Status: **Same verdict as C1** — area-by-area: some survive via feature flags, fcrn and tcell break.

---

**C7 — Phase 4B Dual-Read Harness**  
Location: Lines 14575–14976  
```javascript
// _runPhase4BIBDDualRead, _runPhase4BTL1ADualRead, _runPhase4BAtopyDualRead
// Legacy set reads: drug_area_scores.area_id = 'ibd' / 'tl1a' / 'igf1r' / areaId
```
Called by: `window.showPhase4Compare()` — validation/comparison tool  
Role: Compares legacy vs normalized drug membership for validation  

Status: ⚠️ **Breaks (expected)** — the dual-read harness intentionally reads both legacy and normalized sources. Retiring drug_area_scores makes the "legacy" side of the comparison disappear. The harness should be deprecated before drug_area_scores retirement.

---

**C8 — Competitive scoring display (drug_area_scores)**  
Location: Lines 10771, 18796, 19055, 21546  
```javascript
// drug_area_scores.overlap, overlap_rationale, cls, confidence_level, source_url
// Used in: drug modal, audit tab scoring explanations, PI tab drug cards
```
Role: Every competitive classification displayed on the dashboard (Direct/Adjacent/Same-Space, overlap rationale, confidence) comes from drug_area_scores

Status: 🔴 **Breaks** — this is the most fundamental consumer. The competitive scoring layer has no normalized replacement. Drug_area_scores IS the enrichment output layer.

---

### Backend Script Consumers

**S1 — `company_enrichment.py`**  
Writes to: `drug_area_scores` (enrichment output)  
Reads from: `drug_areas` (to discover which drugs to enrich per area)  

Status: 🔴 **Breaks** — enrichment pipeline can't discover area drugs without drug_areas. Would need to pivot to querying drug_targets + drug_indications per target/indication, then mapping to areas.

**S2 — `research_intelligence.py`**  
Reads: `drug_areas` (to discover drugs for an area)  
```python
area_rows = _sb_get(sb_url, sb_key, "drug_areas", {"area_id": "eq.tl1a"})
```
Status: 🔴 **Breaks** — research intelligence can't enumerate area drugs.

**S3 — `seed_preclinical_competitors.py`**  
Writes to: `drug_areas` and `drug_area_scores`  
Status: 🔴 **Breaks** — the seeding script writes to both tables. Would need to be rewritten to write to normalized tables.

**S4 — `compute_landscape_coverage.py`**  
Reads: `drug_area_scores` (to compute coverage metrics)  
Status: 🔴 **Breaks** — coverage calculations depend on drug_area_scores counts and confidence levels.

**S5 — `audit_sources.py`**  
Reads: `drug_area_scores` source_urls  
Status: ⚠️ **Breaks partially** — the DAS audit mode breaks; other table audits survive.

---

### Supabase Schema Consumers (FK relationships)

From audit tab and ontology design docs:
- `company_areas.area_id` — references area_ids used in drug_areas (soft FK)
- `disease_areas.id` — the canonical area reference table; drug_area_scores.area_id → disease_areas.id
- `targets.disease_areas[]` — array of area_ids used for routing
- `target_pairs.area` — area context for target pairs
- `indications.disease_area` — indication → area mapping
- `intel.area_id` — intelligence items tagged to an area
- `catalysts.area_id` — catalyst events tagged to an area
- `company_profiles.area_id` — company landscape profiles per area

**Critical insight:** `area_id` is a pervasive metadata tag across MANY tables — not just drug_areas/drug_area_scores. Retiring drug_areas doesn't break these FKs; they reference `disease_areas.id` directly. But retiring the `area_id` concept entirely (which eventually it should be) would require a broader metadata migration.

---

## Retirement Readiness Matrix

| Consumer | area_id | Survives Removal? | Action Required |
|----------|---------|-------------------|----------------|
| _makeAreaPI drug list | tl1a | ✅ Yes (C4 active) | None |
| _makeAreaPI drug list | ibd | ✅ Yes (C1 active) | None |
| _makeAreaPI drug list | igf1r | ✅ Yes (C2 active) | None |
| _makeAreaPI drug list | il4ra, tslp | ⚠️ After C5/C6 | Activate useUnifiedAtopy |
| _makeAreaPI drug list | fcrn | 🔴 No | Implement + activate C7 |
| _makeAreaPI drug list | tcell | 🔴 No | Build company_platform_views |
| Drug modal area badges | all | ✅ After C3 (active) | Already migrated |
| Drug modal overlap/rationale | all | 🔴 No | drug_area_scores has NO replacement |
| Research queue routing | all | 🔴 No | Build normalized area routing |
| Phase 4B dual-read harness | ibd/tl1a/igf1r/atopy | ⚠️ Expected break | Deprecate harness first |
| company_enrichment.py | all | 🔴 No | Rewrite area discovery logic |
| research_intelligence.py | all | 🔴 No | Rewrite drug discovery logic |
| seed_preclinical_competitors.py | all | 🔴 No | Rewrite write targets |
| compute_landscape_coverage.py | all | 🔴 No | Rewrite coverage calculation |

---

## Critical Finding: drug_area_scores is NOT Retirable

The simulation reveals a fundamental asymmetry between `drug_areas` and `drug_area_scores`:

**`drug_areas`** = membership table (which drugs belong to which area). This IS being systematically replaced by `drug_targets` and `drug_indications`. Feature flags C1–C7 progressively make drug_areas redundant as a membership source.

**`drug_area_scores`** = enrichment output table (Claude's competitive assessment per drug per area). This is NOT being replaced by any normalized table. It is an independent intelligence layer that stores:
- `overlap` classification (Direct / Adjacent / Same-Space)
- `overlap_rationale` (Claude's reasoning text)
- `cls` (classification tag)
- `confidence_level` (A/B/C/inferred)
- `source_url` (evidence provenance)
- `vs_ailux` (comparison note)

There is no ontology table that captures this. The competitive intelligence layer (what makes Meridian valuable as a BD tool) lives in drug_area_scores. Retiring it without a replacement would delete Claude's competitive assessments.

**Conclusion:** The migration plan should be:
1. Retire `drug_areas` (membership table) — feasible after C1–C7 activations complete
2. Preserve `drug_area_scores` indefinitely as read-only enrichment history, OR migrate to a new `drug_competitive_scores` table with explicit foreign keys to normalized tables
3. Build `drug_competitive_scores` as Phase 5.5 — the explicit replacement for drug_area_scores with proper schema alignment

---

## Retirement Phases Summary

**Phase 5.3 — Complete (post C5/C6/C7):**  
Safe to delete: `drug_areas` rows for tl1a, ibd, igf1r (already redirected)  
Then delete: `drug_areas` rows for atopy, il4ra, tslp (after C5/C6)  
Then delete: `drug_areas` rows for fcrn (after C7)  
**NOT safe:** drug_area_scores rows — retain as scoring provenance

**Phase 5.4 — Strategic view migration:**  
Build + validate company_strategic_views + company_platform_views  
Delete: `drug_areas` rows for autoimmune, respiratory (after strategic views live)  
Delete: `drug_areas` rows for tcell (after platform views + ace tab migration)  
Delete: `drug_areas` rows for ted (after reconciliation audit)  
**Result:** drug_areas table is empty — can be dropped

**Phase 5.5 — Scoring layer migration:**  
Design `drug_competitive_scores` with FK to drug_id (TEXT) + area_id (area concept)  
Migrate drug_area_scores rows to new table  
Update all consumers (modal, PI tab cards, audit, enrichment scripts)  
Drop `drug_area_scores` once migration is validated  
**Result:** Enrichment intelligence preserved with proper normalized schema

**Timeline estimate:** Phase 5.3 = 2 sessions (C5/C6 + C7). Phase 5.4 = 3-4 sessions. Phase 5.5 = 4-5 sessions. Total: ~10 sessions to full drug_areas/drug_area_scores retirement.
