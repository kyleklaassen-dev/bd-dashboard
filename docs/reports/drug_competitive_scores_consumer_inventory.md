# drug_competitive_scores — Consumer Inventory
**Session 63 — 2026-05-26**
**WS3: Consumer migration planning**

---

## 1. Full Consumer Inventory

Ten distinct `drug_area_scores` consumers identified in `index.html` plus one write consumer in `company_enrichment.py`. Static text references in the Audit tab (narrative/documentation) are excluded — they are not Supabase queries.

---

### C1 — Drug Modal: Primary Fetch

**Function:** `loadDrugModal()` / entity modal init block  
**Lines:** 11677, 11684–11699  
**Query:**
```js
_sb.from('drug_area_scores')
   .select('area_id,overlap,overlap_rationale,strategic_role,cls,confidence_level,source_url')
   .eq('drug_id', drugId)
```
**Fields read:** `area_id`, `overlap`, `overlap_rationale`, `strategic_role`, `cls`, `confidence_level`, `source_url`  
**How used:** Builds `scoreMap0[area_id]` lookup dict. Merges with `drug_areas` membership array to produce `areas[]`, which populates:
- Overlap tier badge per area in modal header
- Overlap rationale text in competitive context section
- Source confidence panel (per-area primary source links)

**User surface:** Drug entity modal — Competitive context section, Source confidence panel  
**Risk level:** MEDIUM  
**Can migrate now:** Yes (display-only, no filtering/ranking)

---

### C2 — Drug Modal: Name-Search Fallback

**Function:** Entity modal name-resolution fallback  
**Lines:** 11718–11736  
**Query:** Identical to C1, on resolved drug ID after name search  
**Fields read:** Same as C1  
**How used:** Same display path as C1, triggered when drug not found by ID  
**User surface:** Same as C1  
**Risk level:** MEDIUM (same as C1)  
**Can migrate now:** Yes — same migration as C1; both paths updated together

---

### C3 — PI Tab: scoreRows Fetch

**Function:** `_makeAreaPI().init()` — main tab data loader  
**Lines:** 12548–12550  
**Query:**
```js
_sb.from('drug_area_scores')
   .select('drug_id,area_id,overlap,cls,overlap_rationale,vs_ailux_positioning,competitive_relevance,relevance_rationale')
   .in('area_id', this.areaIds)
```
**Fields read:** `drug_id`, `area_id`, `overlap`, `cls`, `overlap_rationale`, `vs_ailux_positioning`, `competitive_relevance`, `relevance_rationale`  
**How used:** Builds `areaScoreMap[drug_id]` keyed on best overlap tier across areaIds. Each drug's display row is then populated at lines 12625–12631:
- `overlap` → Direct/Adjacent/Same-Space/Watch tier badge on PI card
- `cls` → 1st Gen / 2nd Gen / Bispecific class pill
- `overlap_rationale` → expanded rationale on hover/expand
- `vs_ailux` → Ailux positioning note in card detail
- `competitive_relevance`, `relevance_rationale` → secondary scoring display

Affects tabs: **TL1A, IBD, TED, IGF1R, IL-4Rα, TSLP, Atopy, FcRn, Autoimmune, Respiratory, T-Cell** (all PI tabs)

**User surface:** All PI tab drug cards — tier badge, class pill, rationale, positioning note  
**Risk level:** HIGH — behavioral consumer. `overlap` drives card ordering within entity groups; the overlap tier is rendered as the primary competitive classification badge. Wrong data here breaks the core competitive view.  
**Can migrate now:** No — requires dual-read validation first. areaIds → context mapping is non-trivial for multi-area tabs (atopy spans il4ra + tslp contexts).

---

### C4 — Phase 4B IBD Dual-Read

**Function:** `_runPhase4BDualRead(legacyScoreRows)`  
**Lines:** 14594–14685  
**Query (self-fetch fallback):**
```js
_sb.from('drug_area_scores').select('drug_id,area_id').eq('area_id', 'ibd')
```
**Fields read:** `drug_id`, `area_id` (membership only — no score fields)  
**How used:** Governance monitoring only. Compares drug_area_scores(ibd) count vs drug_indications(uc/cd). Writes to `window.__MERIDIAN_PHASE4_COMPARE__`, console log only.  
**User surface:** None — console/window object only  
**Risk level:** VALIDATION — no user output  
**Can migrate now:** Never — this is intentional legacy comparison infrastructure. Should remain on drug_area_scores permanently. Its purpose is to verify the legacy count.

---

### C5 — Phase 4B TL1A Dual-Read

**Function:** `_runPhase4BTL1ADualRead(legacyScoreRows)`  
**Lines:** 14695–14793  
**Query (self-fetch fallback):** `drug_area_scores.area_id = 'tl1a'`  
**How used:** Same pattern as C4 — governance monitoring vs drug_targets(tl1a)  
**Risk level:** VALIDATION  
**Can migrate now:** Never — same rationale as C4

---

### C6 — Phase 4B TED Dual-Read

**Function:** `_runPhase4BTEDDualRead(legacyScoreRows)`  
**Lines:** 14820–14888  
**Query (self-fetch fallback):** `drug_area_scores.area_id = 'igf1r'`  
**How used:** Governance monitoring vs drug_indications(ted)  
**Risk level:** VALIDATION  
**Can migrate now:** Never — same rationale as C4

---

### C7 — Phase 4B Atopy Dual-Read

**Function:** `_runPhase4BAtopyDualRead(legacyScoreRows, areaId, targetIds)`  
**Lines:** 14939–14992  
**Query (self-fetch fallback):** `drug_area_scores.area_id = areaId` (called for 'il4ra' and 'tslp')  
**How used:** Governance monitoring vs drug_targets(il4ra) and drug_targets(tslp,tslpr)  
**Risk level:** VALIDATION  
**Can migrate now:** Never — same rationale as C4

---

### C8 — Phase 4B FcRn Dual-Read

**Function:** `_runPhase4BFCRNDualRead(legacyScoreRows)`  
**Lines:** 15019–15085  
**Query (self-fetch fallback):** `drug_area_scores.area_id = 'fcrn'`  
**How used:** Governance monitoring vs drug_targets(fcrn)  
**Risk level:** VALIDATION  
**Can migrate now:** Never — same rationale as C4

---

### C9 — Ontology Audit: Live Count

**Function:** Ontology Audit tab impact section  
**Lines:** 21139–21147  
**Query:**
```js
_sb.from('drug_area_scores')
   .select('*',{count:'exact',head:true})
   .eq('area_id', id)
```
**Fields read:** COUNT only (no row data returned)  
**How used:** Displays "💊 N drugs (drug_area_scores)" pill on each area impact card in the Ontology Audit hidden tab  
**User surface:** Ontology Audit tab (hidden developer tab — not user-facing production)  
**Risk level:** LOW — hidden tab, count display only  
**Can migrate now:** Yes, but lowest business value

---

### C10 — Ontology Audit: Area Inspector

**Function:** `ontInspectArea(id)`  
**Lines:** 21655–21664  
**Query:**
```js
_sb.from('drug_area_scores')
   .select('drug_id, overlap, score')
   .eq('area_id', id)
   .order('score', { ascending: false })
   .limit(60)
```
**Fields read:** `drug_id`, `overlap`, `score`  
**How used:** Populates drug list in the Inspect Records panel when area card is clicked. Shows drug names with overlap tier. Ordered by `score` (a column that may not exist in new table — needs investigation).  
**User surface:** Ontology Audit tab — Inspect Records panel (hidden developer tab)  
**Risk level:** LOW — hidden tab, display only  
**Note:** Uses `score` field — this does not exist in `drug_competitive_scores`. Would need to fall back to overlap tier ordering.  
**Can migrate now:** Yes, with `score` field handling

---

### C11 — company_enrichment.py: Write Consumer

**File:** `scripts/company_enrichment.py`  
**Lines:** 2290–2327  
**Operation:** UPSERT to `drug_area_scores` after every enrichment run  
**Fields written:** `drug_id`, `canonical_drug_id`, `area_id`, `overlap`, `cls`, `overlap_rationale`, `vs_ailux_positioning`, `confidence_level`, `source_url`, `last_enriched_at`, `enriched_model`, plus area-specific score fields  
**How used:** The sole enrichment write path. Every time Claude enriches a drug for an area, the competitive assessment is written here.  
**Risk level:** WRITE — must be handled with dual-write window before any consumer migration; otherwise new enrichments won't flow to drug_competitive_scores  
**Can migrate now:** No — parallel write must be implemented before consumer reads are migrated

---

## 2. Classification Table

| ID | Function | Classification | Risk | Can migrate now? |
|---|---|---|---|---|
| C1 | Drug modal primary fetch | `safe_display_consumer` | MEDIUM | ✅ Yes |
| C2 | Drug modal name-search fallback | `safe_display_consumer` | MEDIUM | ✅ Yes (with C1) |
| C3 | PI tab scoreRows fetch | `behavioral_consumer` | HIGH | ❌ No — dual-read first |
| C4 | Phase 4B IBD dual-read | `legacy_provenance_consumer` | NONE | ❌ Never |
| C5 | Phase 4B TL1A dual-read | `legacy_provenance_consumer` | NONE | ❌ Never |
| C6 | Phase 4B TED dual-read | `legacy_provenance_consumer` | NONE | ❌ Never |
| C7 | Phase 4B Atopy dual-read | `legacy_provenance_consumer` | NONE | ❌ Never |
| C8 | Phase 4B FcRn dual-read | `legacy_provenance_consumer` | NONE | ❌ Never |
| C9 | Ontology audit live count | `safe_display_consumer` | LOW | ✅ Yes |
| C10 | Ontology audit inspector | `safe_display_consumer` | LOW | ✅ Yes |
| C11 | company_enrichment.py write | `write_consumer` | HIGH | ❌ No — parallel-write first |

**Summary:**
- `safe_display_consumer`: 4 (C1, C2, C9, C10)
- `behavioral_consumer`: 1 (C3) — the single highest-risk consumer
- `legacy_provenance_consumer`: 5 (C4–C8) — permanently locked on old table
- `write_consumer`: 1 (C11) — enables all future data flow

**Consumers that should never migrate:** C4–C8. Their function is to compare legacy vs normalized. Moving them to `drug_competitive_scores` would make them meaningless — they'd be comparing the successor to itself.

---

## 3. Recommended First Consumer Migration

**Selected: C1 + C2 — Drug Modal Overlap Display**

### Why first

- **Display only.** The modal renders overlap tier, rationale, cls, confidence, and source links. None of these filter the drug list, affect tab sorting, or change which drugs appear.
- **Easiest visual validation.** Open any drug modal. Before migration: overlap badge pulls from drug_area_scores. After: same badge, same text — now from drug_competitive_scores. One drug at a time.
- **Contained scope.** Two fetch calls (C1 + C2) that share identical logic — migrate both in the same diff.
- **Lowest rollback cost.** Two lines: swap query path back to drug_area_scores.
- **Does not block or affect C3.** PI tab uses its own separate scoreRows fetch. The modal can migrate independently.

### Why not C9/C10 first

C9 and C10 are technically lower risk (hidden tab), but they have near-zero user value. The modal migration proves the schema works in a user-facing surface and builds confidence for C3.

### Why not C3 first

C3 drives the tier badge on all PI cards and affects drug ordering. It's the core behavioral consumer. It should be last among production surfaces — after C1 has been proven.

---

## 4. Dual-Read Validation Plan for C1/C2 (Drug Modal)

### Current query (C1/C2)
```js
_sb.from('drug_area_scores')
   .select('area_id,overlap,overlap_rationale,strategic_role,cls,confidence_level,source_url')
   .eq('drug_id', drugId)
```

### Replacement query
```js
_sb.from('drug_competitive_scores')
   .select('context_type,context_id,overlap,overlap_rationale,cls,confidence_level,source_url,vs_ailux')
   .eq('drug_id', drugId)
```

### Key structural change

`drug_area_scores` uses `area_id` as the join key. `drug_competitive_scores` uses `context_id`. The `scoreMap` must be re-keyed:

```js
// Old
const scoreMap = {};
(scoreRes.data || []).forEach(s => { scoreMap[s.area_id] = s; });

// New
const scoreMap = {};
(scoreRes.data || []).forEach(s => { scoreMap[s.context_id] = s; });
```

`area_id` and `context_id` values are aligned:
- `area_id='tl1a'` = `context_id='tl1a'` ✓
- `area_id='ibd'` → `context_id='uc'` and/or `context_id='cd'` (split) — modal will show UC and CD separately after migration
- `area_id='ted'` = `context_id='ted'` ✓ (igf1r deduped into ted)
- `area_id='autoimmune'` = `context_id='autoimmune'` ✓

IBD display note: after migration, the modal will show two rows for IBD drugs (UC context + CD context). This is more accurate than the legacy single-row IBD display. Acceptable intentional difference.

### Confidence level display

The modal renders `confidence_level` as a text badge. Legacy values were `confirmed/supported/inferred`. New values are `A/B/C/inferred`. The display label must update:

```js
// Add to modal render: map A/B/C to display labels
const CONF_LABEL = { A: 'confirmed', B: 'supported', C: 'partial', inferred: 'inferred' };
const confDisplay = CONF_LABEL[area.confidence_level] || area.confidence_level || '—';
```

This maintains existing visual language while reading from new table.

### Expected row parity

For any given drug:
- Rows in `drug_area_scores WHERE drug_id=X` → N rows
- Rows in `drug_competitive_scores WHERE drug_id=X` → N or N+1 rows
- +1 difference possible only for IBD drugs (split into UC + CD contexts)
- All other drugs: exact 1:1 parity by context_id = area_id alignment

### Known intentional differences

| Field | Legacy value | New value | Note |
|---|---|---|---|
| key | `area_id` | `context_id` | Same values, different column name |
| `confidence_level` | `confirmed/supported/inferred` | `A/B/C/inferred` | Semantically identical, re-coded |
| `strategic_role` | present | absent | `drug_competitive_scores` has no `strategic_role` column |
| `vs_ailux` | `vs_ailux_positioning` column | `vs_ailux` column | Column renamed in new schema |
| IBD drug | 1 row (area_id=ibd) | 1–2 rows (context_id=uc, cd) | More accurate split |

**`strategic_role` field:** This field is read by C1/C2 but does not exist in `drug_competitive_scores`. The modal merges it at line 11690: `strategic_role: scoreMap0[a.area_id]?.strategic_role || null`. In the new table this will always be null. Check whether modal renders anything from strategic_role before migrating — if the field is used in display, it must be sourced from `drugs.strategic_role` as a fallback.

### Rollback path

Single-line revert — swap `'drug_competitive_scores'` back to `'drug_area_scores'` in the two fetch calls. No data changes required.

### Validation checklist

Pre-migration (baseline):
- [ ] Open 5 drug modals across different areas (TL1A, TED, FcRn, IL-4Rα, Autoimmune)
- [ ] Record: overlap tier, rationale text, confidence badge, source link present/absent

Post-migration (verify):
- [ ] Open same 5 drug modals
- [ ] Overlap tier matches baseline
- [ ] Rationale text identical (overlap_rationale field identical in both tables)
- [ ] Source link present where it was before
- [ ] Confidence badge updated: `confirmed`→displayed as `confirmed` (via CONF_LABEL map), `supported`→`supported`
- [ ] IBD drug: verify UC + CD rows appear (expected new behavior)
- [ ] No console errors
- [ ] `strategic_role` absence has no visible impact

---

## 5. Parallel-Write Plan for C11 (company_enrichment.py)

### Current write path (line 2290–2327)

`company_enrichment.py` writes to `drug_area_scores` exclusively. The write includes:
- `drug_id`, `area_id`, `overlap`, `cls`, `overlap_rationale`, `vs_ailux_positioning`, `confidence_level`, `source_url`, `last_enriched_at`, `enriched_model`
- E6 confidence invariant enforced before write
- E4 guard: drug_areas row must exist before drug_area_scores write

### Parallel-write design

After drug modal (C1/C2) is migrated and proven, add a second write block to `company_enrichment.py` immediately after the existing `drug_area_scores` write. Both writes execute on every enrichment run until all consumers are migrated.

```python
# ── P6-A: Parallel write to drug_competitive_scores ──────────────────────────
# Mirrors P1-D drug_area_scores write. Execute in parallel until all consumers
# have migrated to drug_competitive_scores. Remove P1-D write only after final
# consumer cutover and 30-day monitoring.
_dcs_payload = {
    k: update_fields[k] for k in _AREA_SCORE_FIELDS if k in update_fields
}
if _dcs_payload:
    # Map area_id → (context_type, context_id)
    _dcs_context = _AREA_CONTEXT_MAP.get(area_id)
    if _dcs_context:
        # ibd and atopy handled with per-drug expansion (same logic as migrate_drug_area_scores.py)
        for ctx_type, ctx_id in _dcs_context:
            _dcs_rec = {
                "drug_id":      drug_id,
                "context_type": ctx_type,
                "context_id":   ctx_id,
                "overlap":      _dcs_payload.get("overlap"),
                "overlap_rationale": _dcs_payload.get("overlap_rationale"),
                "cls":          _dcs_payload.get("cls"),
                "confidence_level": _dcs_payload.get("confidence_level"),
                "source_url":   _dcs_payload.get("source_url"),
                "vs_ailux":     _dcs_payload.get("vs_ailux"),
                "enriched_by":  "claude",
                "enriched_at":  NOW_ISO,
            }
            sb_upsert("drug_competitive_scores", _dcs_rec,
                      on_conflict="drug_id,context_type,context_id")
            log(f"    drug_competitive_scores [{ctx_type}/{ctx_id}]: overlap={_dcs_rec.get('overlap','—')}", indent=2)
```

### AREA_CONTEXT_MAP for enrichment script

Reuse the same mapping from `migrate_drug_area_scores.py`:

```python
_AREA_CONTEXT_MAP = {
    'tl1a':        [('target',         'tl1a')],
    'il4ra':       [('target',         'il4ra')],
    'tslp':        [('target',         'tslp')],
    'fcrn':        [('target',         'fcrn')],
    'igf1r':       [('indication',     'ted')],  # maps to ted
    'ted':         [('indication',     'ted')],
    'autoimmune':  [('strategic_view', 'autoimmune')],
    'respiratory': [('strategic_view', 'respiratory')],
    'tcell':       [('platform_view',  'tcell')],
    # ibd and atopy: require per-drug drug_indications/drug_targets lookup
    # defer to Wave 4 backfill; parallel write initially uses indication/ibd fallback
}
```

IBD and atopy parallel writes are more complex (require drug_indications/drug_targets lookup per enrichment run). For the initial parallel-write implementation, write `indication/ibd` for IBD drugs and `target/il4ra` for atopy drugs as fallback — same as the 3 migration fallback rows. Clean up in a later wave.

### When to implement parallel-write

**Not before C1 is proven.** Parallel-write adds complexity to the enrichment pipeline. Implement after:
1. C1/C2 drug modal migration is deployed and stable for ≥7 days
2. C3 (PI tab) dual-read plan is validated
3. Schema alignment between drug_area_scores write fields and drug_competitive_scores columns is confirmed

### Parallel-write exit criteria

Remove the `drug_area_scores` write (P1-D block) only when:
1. All production consumers have been migrated to `drug_competitive_scores`
2. C3 (PI tab) migration is deployed and stable
3. 30-day monitoring window has closed on all consumers

---

## 6. Risks and Blockers

### R1 — `strategic_role` field missing in drug_competitive_scores (MEDIUM)
`drug_area_scores.strategic_role` is read by C1/C2 but does not exist in `drug_competitive_scores`. If the modal renders this field, it will appear null after migration. **Action before migration:** grep modal template for `strategic_role` usage and confirm it's either unused in display or falls back gracefully to `drugs.strategic_role`.

### R2 — `score` field missing in drug_competitive_scores (LOW)
C10 orders by `drug_area_scores.score` — a column not in the new schema. C10 is a hidden developer tab; this is low-priority. **Action:** Use `overlap` tier ordering as substitute, or add a computed relevance score to drug_competitive_scores.

### R3 — C3 PI tab migration is structurally complex (HIGH)
The `areaScoreMap` in `_makeAreaPI()` is built by iterating `scoreRows` from a single `.in('area_id', this.areaIds)` query. For `drug_competitive_scores`, the equivalent query would be `.in('context_id', contexts)` — but `contexts` requires knowing the context_type + context_id pairs for each areaId. Multi-area tabs (atopy = il4ra+tslp) need special handling. **Action:** Build a local `AREA_TO_CONTEXTS` lookup map in the browser, similar to `AREA_CONTEXT_MAP` in the migration script, before attempting C3 migration.

### R4 — Confidence level display impact (LOW)
Legacy values (`confirmed/supported/inferred`) are displayed in the modal badge. New values are `A/B/C/inferred`. The UI must map these to human-readable display labels. **Action:** Add `CONF_LABEL` lookup in the modal render function before going live.

### R5 — IBD dual-read functions depend on drug_area_scores.area_id='ibd' count (NONE)
C4–C8 must permanently remain on `drug_area_scores`. These are not at risk — they are explicitly classified as `legacy_provenance_consumer` and should not be touched.

### R6 — Enrichment pipeline writes only to drug_area_scores (HIGH — BLOCKER for long-term)
New enrichments after Session 62 write only to `drug_area_scores`. The `drug_competitive_scores` table will drift from the production competitive intelligence as enrichments run. **Timeline impact:** This is not a blocker for C1 migration (modal reads from the migrated snapshot, which is already accurate). It becomes a blocker for C3 migration if enrichments have significantly changed scores. **Action:** Implement parallel-write (C11) within 2–3 sessions.

---

*Prepared Session 63 — 2026-05-26. No code changes made.*
