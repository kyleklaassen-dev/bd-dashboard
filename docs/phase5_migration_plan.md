# Phase 5 — Controlled Migration Plan

**Status:** Planning only. Do not implement any candidate until advisor approval is confirmed.  
**Governing rule:** One component at a time. Feature-flagged. Individually validated. Logged. Reversible.

---

## Migration Rules (Standing)

Every Phase 5 migration must satisfy all six conditions:

| Condition | Requirement |
|---|---|
| Feature-flagged | `FEATURE_FLAGS.<name>` boolean gates the read branch |
| Reversible | Legacy read path stays in code, commented, for 30 days post-migration |
| Individually validated | Validated in isolation before touching the next component |
| Logged | `entity_consistency_checks` + `update_log.md` entry before and after |
| Compared | Post-migration count must match pre-migration count ± classified OOS |
| Rolled back if mismatch | Any unexplained row count difference triggers immediate rollback to legacy read |

**No global switch. No broad dashboard rewiring. No ontology_edges propagation yet.**

---

## Candidate 1 — IBD Area Tab

### Current state

The IBD area PI is embedded within the TL1A tab. It is loaded by `_makeAreaPI()` when called with an `areaIds` array that includes `'ibd'`. The IBD section renders competitive pipeline data for drugs in the IBD indication space. The call site is within the TL1A tab rendering path — confirm exact invocation at implementation start.

**Phase 4B status:** `compare_pass_oos_adjusted` ✅  
`legacy=N, norm=N, overlap=N, raw≈94%, adj=100%` — confirmed in-browser Session 53n.

---

### Legacy source

```javascript
// Inside _makeAreaPI, when areaIds.includes('ibd'):
_sb.from('drug_area_scores')
   .select('drug_id, area_id, overlap, ...')
   .in('area_id', this.areaIds)  // area_id = 'ibd'
```

Primary read: `drug_area_scores` WHERE `area_id = 'ibd'`  
Join: `drugs` table for name, stage, mechanism, brand_name

---

### Normalized source

```sql
SELECT di.drug_id, di.indication_id, di.confidence_score, di.evidence_type,
       d.name, d.stage, d.mechanism, d.brand_name, d.company_id
FROM drug_indications di
JOIN drugs d ON d.id = di.drug_id
WHERE di.indication_id IN ('uc', 'cd')
ORDER BY di.confidence_score DESC
```

---

### Feature flag

```javascript
// Add to FEATURE_FLAGS object (top of index.html, near other flags)
FEATURE_FLAGS.useNormalizedIBD = false;
// flip to true to activate Phase 5 migration for IBD tab
```

---

### Exact functions touched

| Function | Change |
|---|---|
| `_makeAreaPI()` | Add branch at PI table data-fetch step: when `FEATURE_FLAGS.useNormalizedIBD && this.areaIds.includes('ibd')`, substitute `drug_indications WHERE indication_id IN ('uc','cd')` for `drug_area_scores WHERE area_id='ibd'` |
| `_runPhase4BDualRead()` | No change — continues to run in parallel regardless of flag. Provides post-migration comparison baseline. |
| `_injPIScores()` | Verify score injection still works from `drug_area_scores` or route to `drug_indications.confidence_score` |

No HTML changes. No tab restructuring. No data writes.

---

### Expected output after migration

- Drug list for IBD PI section reads from `drug_indications WHERE indication_id IN ('uc','cd')`
- Row count: normalized count (≥ legacy count, because normalized may surface drugs that were OOS in legacy)
- OOS differences: all explainable via Phase 4B classifications. Specifically:
  - `lm-302` — NOT expected in IBD normalized set (CLDN18.2 ADC, no IBD indication row)
  - `sim0500` — NOT expected in IBD normalized set (RRMM trispecific, no IBD indication row)
  - Any epi-001 rows — held in `backfill_preview`, will NOT appear unless committed
- Drug sort order: by `confidence_score DESC` in normalized path (vs `area_fit DESC` in legacy)

---

### Rollback path

```javascript
// To rollback: set flag to false
FEATURE_FLAGS.useNormalizedIBD = false;
// Legacy branch is preserved as a commented fallback in _makeAreaPI()
// No Supabase changes needed — data reads only
```

Rollback is instantaneous. No data mutation involved in the migration.

---

### Validation queries

Run after migration (flag = true):

```javascript
// 1. Confirm Phase 4B compare still passes post-migration
window.showPhase4Compare()
// Expected: 🟢 _makeAreaPI — ibd_indication_group_view → compare_pass_oos_adjusted

// 2. Drug count check
const { data } = await _sb.from('drug_indications').select('drug_id').in('indication_id', ['uc','cd']);
console.log('Normalized IBD drug count:', new Set(data.map(r => r.drug_id)).size);
// Compare to pre-migration legacy count from Phase 4B

// 3. Spot-check expected drug presence
const testDrugs = ['cizutamig', 'duvakitug', 'pvt072', 'izokibep', 'tulisokibart'];
// All should appear in IBD PI section after migration
```

```sql
-- Supabase: pre-migration baseline
SELECT count(DISTINCT drug_id) FROM drug_area_scores WHERE area_id = 'ibd';
-- Record this number before flipping flag

-- Supabase: normalized count
SELECT count(DISTINCT drug_id) FROM drug_indications WHERE indication_id IN ('uc','cd');
-- Delta should match classified OOS count (currently 0 high-severity open items)
```

---

### Acceptance criteria

| Criterion | Requirement |
|---|---|
| Phase 4B status | `compare_pass_oos_adjusted` confirmed post-migration in live browser |
| Row count delta | ≤ classified OOS count (currently 17 IBD-area OOS items across TL1A/IBD boundary) |
| No unexplained absences | Every drug expected in IBD section is present |
| No unexplained additions | Every drug added by normalization has a `drug_indications` row with `confidence_score ≥ 70` |
| Visual parity | PI table renders without errors; sort, filter, and stage pills work correctly |
| Rollback verified | Set `FEATURE_FLAGS.useNormalizedIBD = false` in browser console; confirm legacy render resumes |

---

### Known exclusions (OOS — not failures)

These drugs appear in the legacy IBD set but are **not expected** in the normalized IBD set. Each is classified in `entity_consistency_checks` or `_runPhase4BDualRead.TL1A_DIFF_CLASSIFICATIONS`:

- `lm-302` — CLDN18.2 ADC. No IBD indication. `legacy_noise_removed`.
- `sim0500` — RRMM trispecific. No IBD indication. `legacy_noise_removed`.
- Epi-001 IBD rows — held `pending_review` in `backfill_preview`. Will remain absent until committed.

These drugs appear in the normalized set but **not** in legacy. These are **improvements**, not failures:
- Any drug committed in Wave 2C that has `drug_indications` UC/CD rows but was not in `drug_area_scores` for IBD.

---

### User-visible risk

**Low.** The IBD section is embedded in the TL1A tab — it is not a standalone tab. Users see a PI table of IBD competitor drugs. The change: drug list comes from `drug_indications` instead of `drug_area_scores`. Sort order may shift (confidence_score vs area_fit). No UI structure changes. No modals or navigation affected.

**Pre-announce to user before flipping flag:** "IBD drug list will now reflect indication-normalized data. Sort order may differ slightly. All expected drugs should appear."

---

---

## Candidate 2 — TED Area Tab (igf1r-tshr)

### Current state

The TED view renders inside the `igf1r-tshr` tab via `_makeAreaPI('igf1r-tshr', ['igf1r'])`. The tab shows drugs that target the IGF-1R/TSHR axis, primarily for thyroid eye disease. The Phase 4A correction committed `batoclimab → ted` and `batoclimab → gmg` to `drug_indications`.

**Phase 4B status:** No TED-specific dual-read deployed yet. Phase 4A correction proved data-layer correctness.  
**Phase 4C required:** Run igf1r comparison before flipping flag (see Phase 4C plan, Rank 2).

---

### Legacy source

```javascript
// _makeAreaPI('igf1r-tshr', ['igf1r'])
_sb.from('drug_area_scores')
   .select('drug_id, area_id, overlap, ...')
   .eq('area_id', 'igf1r')
```

Primary read: `drug_area_scores` WHERE `area_id = 'igf1r'`

---

### Normalized source

```sql
SELECT di.drug_id, di.indication_id, di.confidence_score, di.evidence_type,
       d.name, d.stage, d.mechanism, d.brand_name, d.company_id
FROM drug_indications di
JOIN drugs d ON d.id = di.drug_id
WHERE di.indication_id = 'ted'
ORDER BY di.confidence_score DESC
```

---

### Feature flag

```javascript
FEATURE_FLAGS.useNormalizedTED = false;
// flip to true to activate Phase 5 migration for igf1r-tshr tab
```

---

### Exact functions touched

| Function | Change |
|---|---|
| `_makeAreaPI()` | Add branch: when `FEATURE_FLAGS.useNormalizedTED && this.areaIds.includes('igf1r')`, substitute `drug_indications WHERE indication_id='ted'` for `drug_area_scores WHERE area_id='igf1r'` |
| `_runPhase4BTEDDualRead()` | Wire as Phase 4C pre-validation step. Mirrors IBD Path A pattern. Not yet deployed. |

---

### Expected output after migration

- Drug list for igf1r-tshr PI reads from `drug_indications WHERE indication_id='ted'`
- `batoclimab` must appear — ted (95, Ph3) row was committed in Phase 4A correction
- `teprotumumab` (Tepezza, approved TED) must appear — confirm `drug_indications` row exists
- Drugs in `drug_area_scores` igf1r but lacking TED indication are OOS (target-only, no TED indication)

---

### Rollback path

```javascript
FEATURE_FLAGS.useNormalizedTED = false;
// Instant rollback — no data mutation
```

---

### Validation queries

```javascript
// Pre-migration Phase 4C dual-read (must pass before flipping flag)
// Add _runPhase4BTEDDualRead() inside _makeAreaPI — fires on igf1r-tshr tab load
// Expected: compare_pass_oos_adjusted

// Post-migration spot-check
const { data } = await _sb.from('drug_indications').select('drug_id').eq('indication_id', 'ted');
console.log('TED drug count:', data.length);
// batoclimab must be present
```

```sql
-- Pre-migration baseline
SELECT count(*) FROM drug_area_scores WHERE area_id = 'igf1r';

-- Normalized count
SELECT count(DISTINCT drug_id) FROM drug_indications WHERE indication_id = 'ted';

-- Verify batoclimab
SELECT drug_id, confidence_score, evidence_type FROM drug_indications
WHERE drug_id = 'batoclimab' AND indication_id = 'ted';
-- expect: confidence_score=95, evidence_type='ph3'
```

---

### Acceptance criteria

| Criterion | Requirement |
|---|---|
| Phase 4C dual-read | `compare_pass_oos_adjusted` from `_runPhase4BTEDDualRead()` before flag flip |
| batoclimab present | ted row (95, Ph3) renders in PI table |
| teprotumumab present | Approved TED drug renders correctly |
| No unexplained absences | All drugs with ted indication appear |
| Visual parity | PI table renders; stage pills, sort, filters work |
| Rollback verified | Flag flip restores legacy render |

---

### Known exclusions (OOS — not failures)

Drugs expected in legacy `drug_area_scores igf1r` but **not** in normalized TED set:
- IGF-1R-targeted drugs without a TED indication (targeting IGF-1R for oncology, acromegaly, etc.) — these are `ontology_scope_difference` OOS items
- Any IGF-1R/TSHR drug not yet backfilled in `drug_indications` — these are Wave 2D coverage gaps, not migration blockers

---

### User-visible risk

**Low.** The igf1r-tshr tab is one of the smaller area sets. The switch changes the data source from target-based (IGF-1R) to indication-based (TED). User sees TED-specific competitor drugs rather than all IGF-1R-targeted drugs. This is the **correct** semantic — the tab is titled for TED (thyroid eye disease), not IGF-1R biology.

---

---

## Candidate 3 — Drug Entity Modal

### Pre-condition: 10-Drug Verification Sprint

Before migration planning proceeds, run the following 10-drug verification sprint. For each drug: open modal, call `window.showPhase4Compare()`, record classification, note whether migration is safe.

**Sprint status (from Session 53n):** 3 of 10 drugs verified. 7 remaining.

| Drug | Modal status | ECC entry | Safe for migration? | Notes |
|---|---|---|---|---|
| lm-302 | `needs_manual_review` | closed / legacy_noise_removed | ✅ Yes — explainable | CLDN18.2 ADC, tl1a area is legacy noise |
| batoclimab | `cross_table_inconsistency` | corrected (ted+gmg fixed) | ✅ Yes — explainable | igf1r/autoimmune = legacy catch-all artifact |
| epi-001 | `acceptable_mismatch` | open / held | ✅ Yes — explainable | IBD inds held pending source evidence |
| sim0709 | ⏳ Not run | — | Pending | |
| spy072 | ⏳ Not run | closed / tl1a_rheumatology_scope | Pending | |
| upadacitinib | ⏳ Not run | open / atopy_ad_gap / accepted | Pending | |
| teprotumumab | ⏳ Not run | — | Pending | |
| dupilumab | ⏳ Not run | — | Pending | |
| efgartigimod | ⏳ Not run | — | Pending | |
| risankizumab | ⏳ Not run | closed / ibd_indication_not_tl1a_target | Pending | |

**To run remaining 7 drugs:**
1. Open modal for each drug (`openDrugEntityModal('<drug_id>', '<name>', null)`)
2. Call `window.showPhase4Compare()` in browser console
3. Record status field from the last record in the array
4. Note `component='openDrugEntityModal'`, `path='drug_entity_modal'`
5. Graduate any `cross_table_inconsistency` with no ECC entry to `entity_consistency_checks`

**Migration proceeds only after all 10 drugs are classified and zero unclassified `cross_table_inconsistency` entries remain.**

---

### Current state

`openDrugEntityModal()` fetches area membership from `drug_areas` + `drug_area_scores`, then uses that to render the area pills and context in the modal. `_runPhase4CModalDualRead()` runs in parallel at the end of modal load.

**Phase 4B status:** Infrastructure deployed (Session 53j). 3/10 verification sprint drugs classified.

---

### Legacy source

```javascript
// In openDrugEntityModal()
_sb.from('drug_areas').select('area_id').eq('drug_id', drugId),
_sb.from('drug_area_scores').select('area_id,overlap,...').eq('drug_id', drugId),
```

---

### Normalized source

```javascript
// Parallel reads already running in _runPhase4CModalDualRead()
_sb.from('drug_targets').select('target_id,confidence_score,...').eq('drug_id', resolvedDrugId),
_sb.from('drug_indications').select('indication_id,confidence_score,...').eq('drug_id', resolvedDrugId),
_sb.from('trials').select('id,...').eq('drug_id', resolvedDrugId)
  // → trial_indications JOIN
```

---

### Feature flag

```javascript
FEATURE_FLAGS.useNormalizedDrugModal = false;
// flip to true after 10-drug sprint completes with zero unclassified mismatches
```

---

### Exact functions touched

| Function | Change |
|---|---|
| `openDrugEntityModal()` | Add branch: when `FEATURE_FLAGS.useNormalizedDrugModal`, primary area membership read uses `drug_targets` + `drug_indications` instead of `drug_areas` + `drug_area_scores` |
| `_runPhase4CModalDualRead()` | No change — continues to run in parallel. Post-migration, it compares normalized-primary vs legacy-shadow. |

---

### Expected output after migration

- Modal area pills derived from `drug_targets` (for target-driven areas) + `drug_indications` (for indication-driven areas)
- Area tab membership logic via `TAB_AREA_MAP` reverse lookup remains unchanged
- `drug_area_scores` fields (overlap, strategic_role, overlap_rationale) may need bridged from legacy source or migrated to normalized fields in a future step

---

### Rollback path

```javascript
FEATURE_FLAGS.useNormalizedDrugModal = false;
// Instant rollback — no data mutation
```

---

### Acceptance criteria

| Criterion | Requirement |
|---|---|
| 10-drug sprint | All 10 drugs classified. Zero unclassified `cross_table_inconsistency` entries. |
| Zero new ECC opens | No new high-severity issues surface during sprint |
| Area pills correct | batoclimab shows fcrn + ted; cizutamig shows tl1a; vedolizumab shows ibd |
| Rollback verified | Flag flip restores legacy render |

---

### Known exclusions

- `drug_area_scores.overlap` and `overlap_rationale` fields have no equivalent in `drug_targets` / `drug_indications`. These BD context fields (Direct / Adjacent / Same-Space classification) are legacy enrichment output. Migration plan: read overlap context from `drug_area_scores` as a secondary join even when primary area membership comes from normalized tables. This is a parallel read, not a blocking dependency.

---

### User-visible risk

**Low–Medium.** The modal is the highest-frequency view — Kyle opens it constantly. Risk: area pills may differ for edge-case drugs with legacy catch-all classifications (e.g., batoclimab's igf1r/autoimmune legacy areas). These are already classified and documented.

---

---

## TL1A — Migration Note (Do Not Migrate Yet)

**Status:** Planning only. No implementation until shadow-render validation passes.

TL1A migration is architecturally more complex than IBD or TED because TL1A uses a **separate dashboard engine** (`tl1aPI` object, ~1700 lines) rather than the shared `_makeAreaPI` factory. See `docs/unified_area_dashboard_architecture.md` for the full design.

### Required before any TL1A Phase 5 migration:

1. **Read-path inventory** — Map every data fetch inside `tl1aPI`. Identify all `drug_area_scores`, `drug_areas`, `drug_combinations`, `company_areas` calls within the TL1A rendering path.

2. **Target-view dual-read** — `_runPhase4BTL1ADualRead()` is already wired inside `_makeAreaPI` — but TL1A's PI table renders through `tl1aPI`, not `_makeAreaPI`. Confirm that the dual-read fires on TL1A tab load and produces a valid record.

3. **Feature flag design** — TL1A's feature flag must be inside `tl1aPI`, not `_makeAreaPI`. The pattern:
   ```javascript
   FEATURE_FLAGS.useUnifiedTL1A = false;
   // false → current tl1aPI
   // true  → unified _makeAreaPI(DASHBOARD_VIEW_CONFIG.tl1a)
   ```

4. **Target-specific validation** — TL1A normalized source is `drug_targets WHERE target_id='tl1a'`. The 17 OOS items are fully classified. Adjusted match = 100%.

5. **Separate acceptance criteria** — TL1A has modal section rendering (catalysts, BD activity, market context, history) that `_makeAreaPI` does not currently support. These sections must render equivalently or be preserved as TL1A-specific sections within the unified engine before the switch.

### TL1A is Candidate 4, not Candidate 3.

TL1A migration happens after: IBD ✅ → TED ✅ → Drug modal ✅ → TL1A ⏳.

---

## Migration Log Template

Add an entry to `update_log.md` for each migration following this format:

```
### [Date] — Phase 5 Migration: [Component]
- Feature flag: FEATURE_FLAGS.[name] → true
- Legacy source: [table/query]
- Normalized source: [table/query]
- Pre-migration count: [N]
- Post-migration count: [N]
- Delta: [N] (all classified: [list])
- Phase 4C dual-read status: [compare_pass_oos_adjusted / compare_pass]
- Rollback verified: yes
- ECC open high-severity: 0
```

---

*Generated: 2026-05-25 — Session 53m*  
*Status: Awaiting advisor approval before Candidate 1 implementation begins.*
