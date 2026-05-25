# Dashboard Dependency Inventory
**Status:** Inventory only — no fixes applied  
**Created:** 2026-05-25 (Session 49i)  
**Purpose:** Phase 4 / Phase 5 migration control document  
**Fields audited:** `disease_area` · `disease_areas` · `area_id` · `drug_area_scores`  
**Classification standard:** strict (safe = display-only with zero data-selection effect)

---

## Point 1 — Total References by Field

| Field | References |
|---|---|
| `area_id` | 87 |
| `disease_areas` | 55 |
| `disease_area` | 12 |
| `drug_area_scores` | 23 |
| **TOTAL** | **177** |

---

## Point 2 — Count by Classification

| Classification | Count | % |
|---|---|---|
| **Safe** | 68 | 38% |
| **Needs Migration** | 94 | 53% |
| **Blocked** | 15 | 8% |

**Classification standard applied:**
- **Safe** — display-only; does not affect which data appears, how records filter/score/sort, which cards render, which queries run. Color/label constants that only assign a visual style string qualify. Pure schema documentation text qualifies.
- **Needs Migration** — affects application behavior: filters, joins, scoring, sorting, card rendering, dashboard sections, enrichment reads/writes, source selection, aggregation counts. Includes AREA_COLORS/AREA_LABELS if they gate which element renders. All `.eq()`, `.in()`, `.filter()`, `.select()` query calls.
- **Blocked** — correct replacement depends on relationship tables not yet complete. Migrating now would change outputs without a comparison layer.

---

## Point 3 — Top 5 Highest-Risk Dependencies

### 1 · Lines 11557–11620 · `openDrugEntityModal()` · `drug_area_scores` + `area_id` · **BLOCKED**
Controls: Drug modal competitive positioning. Merges `drug_areas` (membership) + `drug_area_scores` (overlap/rationale) via `area_id` key. Dual-source fallback: if `drug_areas` is empty, reads `drug_area_scores` directly. This is the core enrichment merge path — what appears in every drug's "Competitive Positioning" tab.  
**Why high risk:** Silent failure. If FK semantics drift or area_id values become inconsistent, competitive data disappears from every drug modal with no error. Cannot safely replace until drug_indications is fully scored and a comparison layer exists. Score migration must be atomic.

### 2 · Lines 12064–12069 · `loadBDDashboard()` / deal query · `area_id` · **NEEDS MIGRATION**
Controls: Deal tab rendering. Filters `deals` by `area_id`; if no match, falls back to `deals WHERE area_id IS NULL`. This fallback will silently change the result set after migration — any deal orphaned during area_id remapping becomes invisible without explicit handling.  
**Why high risk:** Orphaned records are not flagged. If area_id values change and deals are not atomically remapped, deals disappear from the dashboard with no error, and the null fallback picks up unrelated untagged deals.

### 3 · Lines 3337–3460 · `_loadAreaDrugTabs()` · `area_id` · **NEEDS MIGRATION**
Controls: Entire tab navigation structure. Chains `.in('area_id', areas)` across `intel_areas`, `deals`, `catalysts`, `drug_areas`. Every PI tab's drug list originates here.  
**Why high risk:** Any inconsistency in `area_id` values produces empty tabs with no error signal — zero records, not an exception. Migrating this requires all six area→indication→drug mappings to be coherent simultaneously.

### 4 · Lines 12136–12142 · `_loadCompetitiveFeeds()` · `drug_area_scores` · **BLOCKED**
Controls: Which drugs appear in which tab and in what competitive order. Reads `drug_area_scores.overlap`, `drug_area_scores.cls` to sort and filter the drug list.  
**Why high risk:** Enrichment scripts write to `drug_area_scores`; dashboard reads from it. The read and write sides are coupled. Migrating the read (to drug_indications) without migrating the write (enrichment scripts) creates a two-source inconsistency — some drugs scored in new table, some only in old.

### 5 · Lines 11651–11690 · `openDrugEntityModal()` → tab pills · `area_id` + `TAB_AREA_MAP` · **NEEDS MIGRATION**
Controls: Footer pills in drug modal — which tabs a drug appears in. Uses hard-coded `TAB_AREA_MAP = { 'tl1a': [...], 'tslp': [...], ... }` keyed by `area_id`. If therapeutic_areas introduces new IDs or renames existing ones, this mapping breaks silently — no pills show, user loses area context.  
**Why high risk:** TAB_AREA_MAP is entirely hard-coded, not derived from schema. No automatic sync. Migration requires both data and code change simultaneously.

---

## Point 4 — Now Unblocked by drug_indications (Phase 4 Compare Queue)

**drug_indications was committed 2026-05-25 (129 rows). These references are no longer structurally blocked but must not be migrated until a comparison layer validates zero regressions.**

| Lines | Function/Section | Field | Was Waiting For | Phase 4 Action |
|---|---|---|---|---|
| 11557–11620 | `openDrugEntityModal()` — area merge | `drug_area_scores`, `drug_areas` | drug_indications FK structure | Dual-read test: compare area_merge vs. drug_indications join; assert count parity |
| 12136–12142 | `_loadCompetitiveFeeds()` — score feed | `drug_area_scores.area_id` | drug_indications as replacement read source | Switch read only after enrichment scripts also write to drug_indications + score migration complete |
| 20246–20250 | Schema validation comments | (doc) | drug_indications table definition | Table exists; validation tests now runnable |
| 19815–19817 | FK inconsistency note: `drug_area_scores.disease_area` | `drug_area_scores` | ontology_mappings to translate legacy_id → new_id | Add ontology_mappings first; then backfill + migrate |
| 18102 | Feature backlog: competitor derivation from `drug_area_scores` | `drug_area_scores.overlap` | drug_indications to provide canonical drug→area link | Can now be built using drug_indications + drug_area_scores join |
| 20463–20481 | Area detail page | `drug_area_scores.area_id` | drug_indications for replacement join | Phase 4 comparison read before cutover |

**Phase 4 acceptance criteria:** (a) both old and new read paths run in parallel on production data; (b) row counts match; (c) no dashboard visual regressions; (d) enrichment write-side simultaneously migrated.

---

## Point 5 — ✓ UNBLOCKED (trial_indications committed 2026-05-25) — Phase 4 Compare Queue

**Status updated 2026-05-25:** trial_indications now has 319 committed rows. These references are no longer structurally blocked. They move to Phase 4 compare queue — do not migrate until dual-read comparison layer validates zero regressions.

## Point 5 — Previously: Blocked Until trial_indications Complete

| Lines | Function/Section | Field | Reason |
|---|---|---|---|
| 3383 | Catalyst fetch in `_loadAreaDrugTabs()` | `catalysts.area_id` | Catalysts should eventually route via trial_indications. Cannot safely replace area_id filter until trial→indication mapping is complete |
| 3418, 3460 | Signals + trials fetch | `signals.area_id`, `trials` join | Trial area logic is currently area_id-driven; replacement requires trial_indications to provide the canonical trial→indication link |
| 2641 | Unified feed catalyst assembly | `catalysts.area_id` | Catalysts linked to areas via `area_id`; should link via trial_indications after migration |
| 14707–14716 | Ontology panel catalyst/signal visualization | `catalysts.area_id` | Reads catalysts/signals by area_id for display; replacement requires trial_indications as join source |
| 19951–19952 | Ontology audit live counts | `drug_area_scores` + indications | Count query compares drug_area_scores population; can only be replaced when drug_indications + trial_indications both fully populated |
| 11559–11560 | Drug modal trials fetch | `trials` by `drug_id` | Currently fetches by drug_id; should eventually correlate via trial_indications to show indication-level trial context inside drug modals |

**Count: ~6 paths now unblocked. Phase 4 acceptance criteria:** (a) both old and new read paths run in parallel on production data; (b) row counts match; (c) no dashboard visual regressions.

---

## Point 6 — Safe as Legacy Fallback Through Phase 5

### Display Constants (zero data-selection effect)
- Lines 2221–2244: `AREA_LABELS`, `AREA_COLORS`, `AREA_BG`, `TAB_PORTFOLIO_LABELS` — pure style maps keyed by area_id string; assign visual appearance only, no logic gating
- Lines 2312–2313, 2456–2457: `areaColor = AREA_COLORS[d.area_id]` — lookup only, assigns a CSS color string
- Lines 3131–3132, 3232–3233: Significance panel area label lookups — display only
- Lines 10160–10181, 10378–10432: CEM modal area label lookups — no filter, no join

### Schema Documentation (zero application impact)
- Lines 17206–17747: HTML educational panels explaining `drug_area_scores`, `disease_areas` relationships
- Lines 17362, 17424, 17441: Schema relationship diagrams with FK notation
- Lines 17611–17616: "Biology path / Entity path / Score path" flow explanations
- Lines 20702–20704, 20719–20720: Table schema description cards
- Lines 19514, 19530, 19550: FK relationship descriptions in ontology audit page

### QC Monitors and Audit Trails (diagnostic only, no business logic)
- Lines 19395, 19492–19544: Ontology QC section — counts `disease_areas` rows, checks misclassification
- Line 20041: `qc('drugs',[['!null','disease_area']])` — legacy field population check
- Line 20093: Row count "Has disease area (legacy)" — observability metric
- Lines 20254–20259: Assertions that legacy tables are not corrupted — keep as safeguard

### Graceful Fallbacks (should remain even after migration)
- Line 12069: `deals WHERE area_id IS NULL` fallback — catches orphaned records; keep through Phase 4
- Lines 11576–11581: Drug modal dual-source fallback (drug_areas empty → drug_area_scores direct) — backward compatibility shim
- Line 20615: "No drugs found in drug_area_scores for this area ID" empty state — keep for user guidance

### Legacy Field Reads with Clear Retirement Path
- Lines 11499–11505: `company_profiles WHERE area_id` — filters catalyst list; retire after `company_profiles.therapeutic_area_id` exists
- Line 14096: Single `.eq('area_id', cfg.area_id)` — isolated, low-risk; mark TODO Phase 5
- Line 20778: `indications.order('disease_area,id')` — display sort only; retire after therapeutic_area_id available

---

## Migration Sequence

```
Phase 1 ✓  Create ontology_mappings, indication_aliases, entity_edges
Phase 2 ✓  drug_targets committed (173 rows)
Phase 2 ✓  drug_indications committed (129 rows) ← 2026-05-25
Phase 2 ✓  trial_indications committed (319 rows) ← 2026-05-25  L4 QUERYABLE ACHIEVED
Phase 3     Update dashboard queries to read from new tables
            Order: safe references first → needs-migration → blocked (after Phase 4)
Phase 4     Dual-read comparison: validate zero regressions before any cutover
Phase 5     Archive blocked references; retire legacy fields
            Rename disease_area → _legacy_disease_area for audit trail
```

**Rule:** Do not migrate any BLOCKED reference before the Phase 4 comparison layer exists.  
**Rule:** Do not migrate any NEEDS MIGRATION reference until trial_indications is committed and score migration is planned.
