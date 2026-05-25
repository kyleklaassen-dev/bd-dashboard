# Unified Area Dashboard Architecture

**Document type:** Technical design note  
**Status:** Design only. Do not implement until advisor approval.  
**Purpose:** Describe the path from the current dual-engine dashboard (tl1aPI + _makeAreaPI) to a single config-driven engine that handles all view types.

---

## 1. Why TL1A Should Not Stay Separate

The current architecture has two dashboard rendering engines:

**`tl1aPI`** (~1700 lines, TL1A tab only)
- Loaded via `loadAreaPI('tl1a')` → `_makeAreaPI('tl1a', ['tl1a'])`
- But internally the TL1A tab renders through a separate `tl1aPI` object that pre-dates `_makeAreaPI`
- Manages its own data fetches, rendering loops, modal triggers, pill states, BD activity, catalysts
- Has `_runPhase4BTL1ADualRead()` wired for comparison — but this is patched in, not native

**`_makeAreaPI`** (all other drug tabs)
- Universal factory used by: tslp, il4ra-tslp, il4ra-ox40l, igf1r-tshr, fcrn, ace, ibd
- Config-driven via `TAB_AREA_MAP`
- Shared patterns: PI table, score injection, dual-read hooks, landscape coverage

**The problem:** Two engines diverge over time. Features added to `_makeAreaPI` don't reach TL1A. TL1A-specific logic can't be reused by other tabs. When Phase 5 migration begins, TL1A requires a completely separate migration path. Any future view type — atopy, autoimmune, respiratory as standalone tabs — would need to choose which engine to bolt onto.

**The principle:**
> TL1A is not a therapeutic area. TL1A is a target-driven dashboard view.  
> IBD is not a target. IBD is an indication-group dashboard view.  
> TED is an indication dashboard view.  
> The difference between these views should live in configuration, not separate code paths.

**One engine. Many view configurations.** This is the correct end state.

---

## 2. Proposed `DASHBOARD_VIEW_CONFIG`

```javascript
const DASHBOARD_VIEW_CONFIG = {

  // ── Indication Group Views ──────────────────────────────────────────────────
  ibd: {
    viewType:             'indication_group_view',
    displayName:          'IBD',
    legacyAreaIds:        ['ibd'],
    indicationIds:        ['uc', 'cd'],
    normalizedSource:     'drug_indications',
    normalizedFilter:     { field: 'indication_id', op: 'in', value: ['uc', 'cd'] },
    phase4bStatus:        'compare_pass_oos_adjusted',
    phase5Ready:          true,
    featureFlag:          'useNormalizedIBD',
  },

  // ── Indication Views ────────────────────────────────────────────────────────
  ted: {
    viewType:             'indication_view',
    displayName:          'TED',
    legacyAreaIds:        ['igf1r'],              // legacy stores TED under igf1r target
    indicationIds:        ['ted'],
    normalizedSource:     'drug_indications',
    normalizedFilter:     { field: 'indication_id', op: 'eq', value: 'ted' },
    phase4bStatus:        'data_layer_verified',  // Phase 4A correction proved ted match
    phase5Ready:          true,                   // after Phase 4C dual-read confirms
    featureFlag:          'useNormalizedTED',
    tabId:                'igf1r-tshr',
  },

  // ── Target Views ────────────────────────────────────────────────────────────
  tl1a: {
    viewType:             'target_view',
    displayName:          'TL1A',
    legacyAreaIds:        ['tl1a'],
    targetIds:            ['tl1a'],
    relatedIndicationIds: ['uc', 'cd'],           // IBD indication group is TL1A's disease context
    normalizedSource:     'drug_targets',
    normalizedFilter:     { field: 'target_id', op: 'eq', value: 'tl1a' },
    phase4bStatus:        'compare_pass_oos_adjusted',
    phase5Ready:          false,                  // requires arch review + shadow-render first
    featureFlag:          'useUnifiedTL1A',
    engineNote:           'currently rendered by tl1aPI, not _makeAreaPI',
  },

  tslp: {
    viewType:             'target_view',
    displayName:          'TSLP',
    legacyAreaIds:        ['tslp'],
    targetIds:            ['tslp'],
    normalizedSource:     'drug_targets',
    normalizedFilter:     { field: 'target_id', op: 'eq', value: 'tslp' },
    phase4bStatus:        'not_started',
    phase5Ready:          false,
    featureFlag:          'useNormalizedTSLP',
  },

  fcrn: {
    viewType:             'target_view',
    displayName:          'FcRn',
    legacyAreaIds:        ['fcrn'],
    targetIds:            ['fcrn'],
    normalizedSource:     'drug_targets',
    normalizedFilter:     { field: 'target_id', op: 'eq', value: 'fcrn' },
    phase4bStatus:        'not_started',
    phase5Ready:          false,                  // blocked — Wave 2D coverage first
    featureFlag:          'useNormalizedFcRn',
    blockedBy:            'wave_2d_fcrn_backfill',
  },

  // ── Future: Modality View ───────────────────────────────────────────────────
  // ace: {
  //   viewType:    'platform_view',
  //   displayName: 'ACE / T-Cell Reset',
  //   ...
  // }
};
```

**Key design decisions:**

1. `viewType` is the primary dispatch key inside `_makeAreaPI`. The engine branches on view type to determine its normalized query strategy.
2. `legacyAreaIds` preserves the backward-compatibility mapping — the legacy `drug_area_scores` query still uses these IDs during dual-read.
3. `featureFlag` connects the config entry to the runtime feature flag. The flag name is the source of truth for implementation.
4. `phase5Ready` is a gate, not a permission. It reflects whether Phase 4C validation has cleared. It changes to `true` after dual-read confirmation — not before.

---

## 3. Supported View Types

### `indication_view`
- **Source:** `drug_indications WHERE indication_id = X`
- **Canonical example:** TED tab (indication_id='ted')
- **Semantics:** Show all drugs targeting this specific disease, regardless of target
- **When to use:** When the dashboard tab is named for a disease (TED, atopy, lupus)

### `indication_group_view`
- **Source:** `drug_indications WHERE indication_id IN (X, Y, ...)`
- **Canonical example:** IBD tab (indication_ids=['uc','cd'])
- **Semantics:** Show all drugs targeting any indication in the group
- **When to use:** When the dashboard tab covers a disease area that spans multiple ICD-level indications

### `target_view`
- **Source:** `drug_targets WHERE target_id = X`
- **Canonical example:** TL1A tab (target_id='tl1a')
- **Semantics:** Show all drugs that target this biological mechanism, regardless of indication
- **When to use:** When the tab is named for a biological mechanism (TL1A, TSLP, FcRn, IL-4Rα)
- **Note:** Target views need `relatedIndicationIds` for context — drugs that compete in the indication space but not via this target

### `platform_view` *(future)*
- **Source:** `drug_targets WHERE target_id IN (X, Y, ...)` OR custom query
- **Canonical example:** ACE tab (CD19, BCMA, CD3 — T-cell reset platform)
- **When to use:** When the dashboard tab covers a therapeutic platform or modality rather than a single target or indication

### `modality_view` *(future)*
- **Source:** `drug_modalities` or `drugs.modality`
- **Canonical example:** "All bispecifics", "All oral small molecules"
- **Not yet implemented.** Placeholder for the intelligence layer.

---

## 4. How `_makeAreaPI` Should Become Config-Aware

Currently `_makeAreaPI(tabId, areaIds)` does one thing: fetch from `drug_area_scores WHERE area_id IN (areaIds)`. It doesn't know what type of view it's building.

The config-aware version adds a view-type dispatch at the data fetch step:

```javascript
// Current (simplified)
async function _makeAreaPI(tabId, areaIds) {
  const { data: scoreRows } = await _sb
    .from('drug_area_scores')
    .select('drug_id, area_id, ...')
    .in('area_id', areaIds);
  // render...
}

// Config-aware version (simplified)
async function _makeAreaPI(tabId, areaIds, config = null) {
  const viewConfig = config || DASHBOARD_VIEW_CONFIG[tabId] || null;
  const NORM_ENABLED = viewConfig && FEATURE_FLAGS[viewConfig.featureFlag];

  let primaryRows;

  if (NORM_ENABLED) {
    // Normalized read based on view type
    if (viewConfig.viewType === 'indication_view' || viewConfig.viewType === 'indication_group_view') {
      const { data } = await _sb
        .from('drug_indications')
        .select('drug_id, indication_id, confidence_score, evidence_type')
        .in('indication_id', viewConfig.indicationIds);
      primaryRows = _mapDrugIndicationsToScoreFormat(data);  // normalize field names
    } else if (viewConfig.viewType === 'target_view') {
      const { data } = await _sb
        .from('drug_targets')
        .select('drug_id, target_id, confidence_score, relationship_type')
        .eq('target_id', viewConfig.targetIds[0]);
      primaryRows = _mapDrugTargetsToScoreFormat(data);      // normalize field names
    }
  } else {
    // Legacy read (unchanged)
    const { data } = await _sb
      .from('drug_area_scores')
      .select('drug_id, area_id, ...')
      .in('area_id', areaIds);
    primaryRows = data;
  }

  // Everything below this line is unchanged: render PI table, inject scores, etc.
  // ...
}
```

**Critical constraint:** The render path below the data fetch does **not change** during Phase 5. The mapping functions `_mapDrugIndicationsToScoreFormat` and `_mapDrugTargetsToScoreFormat` translate normalized fields to the same shape that the existing render code expects. This keeps the blast radius minimal.

---

## 5. Shadow-Render Plan for TL1A

Before replacing any visible TL1A output, run the unified `_makeAreaPI` in shadow mode — no visible changes, full comparison capture.

**Step 1:** Add `DASHBOARD_VIEW_CONFIG.tl1a` (see Section 2).

**Step 2:** After TL1A tab loads via `tl1aPI`, also call (silently):
```javascript
const shadowPi = _makeAreaPI('tl1a', ['tl1a'], DASHBOARD_VIEW_CONFIG.tl1a);
await shadowPi.init(); // renders into a detached DOM node
```

**Step 3:** Compare outputs:
```javascript
window.__MERIDIAN_TL1A_SHADOW__ = {
  tl1aPI_drugs:         [...legacyDrugSet],
  unified_drugs:        [...shadowDrugSet],
  overlap:              [...overlapSet],
  legacy_only:          [...legacyOnlySet],
  unified_only:         [...unifiedOnlySet],
  section_errors:       [],    // render errors in shadow
  timestamp:            new Date().toISOString()
};
```

**Step 4:** Capture and classify:
- Drug count parity
- Target rows (drug_targets tl1a set)
- IBD context rows (drug_indications uc/cd — the "related indications" in TL1A's config)
- Trial data parity
- Catalyst data parity (catalysts come from `area_catalysts` table, not drug_area_scores — no change expected)
- BD activity parity (deals table — no change expected)
- Modal section rendering (market context, SOC, history — these are static HTML in tl1aPI, not queries)

**Acceptance for shadow:** All dynamic sections (drug table, scores, catalysts, BD) produce parity output. Static sections (modal panels) are confirmed present. `window.__MERIDIAN_PHASE4_COMPARE__` shows `compare_pass_oos_adjusted` for the shadow run.

---

## 6. Feature Flag Plan

```javascript
// All Phase 5 flags — add to FEATURE_FLAGS object at top of index.html
const FEATURE_FLAGS = {
  // Phase 5 candidates (flip to true after validation)
  useNormalizedIBD:         false,   // Candidate 1
  useNormalizedTED:         false,   // Candidate 2
  useNormalizedDrugModal:   false,   // Candidate 3

  // TL1A unified engine (shadow first, then flip)
  useUnifiedTL1A:           false,   // Candidate 4 — do not flip until shadow passes
  tl1aShadowMode:           false,   // shadow render without visible changes

  // Future candidates
  useNormalizedTSLP:        false,
  useNormalizedIL4Ra:       false,
  useNormalizedFcRn:        false,   // blocked until Wave 2D
};
```

**Runtime override (browser console):**
```javascript
// Enable for a single session without deploying
FEATURE_FLAGS.useNormalizedIBD = true;
// Refresh IBD section (or reload tab)

// Disable immediately if mismatch
FEATURE_FLAGS.useNormalizedIBD = false;
```

**Deployment rule:** Feature flags deploy as `false`. Never deploy a flag as `true` before in-browser validation session is complete.

---

## 7. Acceptance Criteria Before Retiring `tl1aPI`

`tl1aPI` can be removed only after ALL of the following pass:

| Criterion | Gate |
|---|---|
| Shadow render passes | `window.__MERIDIAN_TL1A_SHADOW__` shows compare_pass_oos_adjusted |
| Feature flag tested | `FEATURE_FLAGS.useUnifiedTL1A = true` in browser for 3+ live sessions without issues |
| Fallback tested | `FEATURE_FLAGS.useUnifiedTL1A = false` restores tl1aPI render identically |
| No modal regressions | All TL1A modal panels (Market, SOC, Catalysts, BD, History) render correctly under unified engine |
| No pill regressions | TL1A area pills (left + right) behave identically |
| No navigation regressions | `openTl1aModal()` and `closeTl1aModal()` still work (these are TL1A-specific, may need bridging) |
| entity_consistency_checks | Open high-severity = 0 |
| Multiple live checks | At least 3 complete TL1A tab loads, each producing correct output, before `tl1aPI` code is removed |
| Update log entry | `update_log.md` entry confirming retirement decision |

**30-day rule:** After flag flip to `true`, keep `tl1aPI` code commented (not deleted) for 30 days. Deletion only after 30 days of clean operation.

---

## 8. Risks and Rollback

### Risk 1: `tl1aPI` uses non-shared rendering patterns
**Risk:** TL1A modal panels (Market context, Standard of Care, History) are statically rendered inside `tl1aPI` with unique HTML that `_makeAreaPI` doesn't know about.  
**Mitigation:** Don't migrate these panels. Keep them as TL1A-specific sections in the unified config (`tl1a.staticSections: [...]`). The unified engine renders the dynamic drug table; the static sections remain as today.  
**Rollback:** `FEATURE_FLAGS.useUnifiedTL1A = false`.

### Risk 2: Field name mismatch between `drug_targets`/`drug_indications` and existing PI render code
**Risk:** The PI table render code expects fields like `overlap`, `area_fit`, `cls`, `overlap_rationale` from `drug_area_scores`. Normalized tables use different field names.  
**Mitigation:** The mapping functions (`_mapDrugTargetsToScoreFormat`, `_mapDrugIndicationsToScoreFormat`) translate normalized fields to legacy shape. The render path does not change.  
**Rollback:** Feature flag flip.

### Risk 3: OOS drugs appear or disappear unexpectedly
**Risk:** A drug that was in legacy but not normalized (or vice versa) causes a visible change that wasn't expected.  
**Mitigation:** Phase 4C classification sprint ensures every difference is documented before flag flip. The `entity_consistency_checks` table is the live record.  
**Rollback:** Feature flag flip + log entry.

### Risk 4: `useUnifiedTL1A` flag flip breaks TL1A pill state and modal system
**Risk:** TL1A pill visibility and modal open/close is managed by `tl1aPI`-specific functions (`openTl1aModal`, `closeTl1aModal`). These must still work under the unified engine.  
**Mitigation:** These functions reference DOM IDs, not `tl1aPI` internals. They will continue working. Verify during shadow mode.  
**Rollback:** Feature flag flip.

### Risk 5: Premature `tl1aPI` deletion
**Risk:** The 30-day window is shortened and `tl1aPI` code is deleted before a regression is caught.  
**Mitigation:** Hard rule: 30 days before deletion. No exceptions.  
**Rollback:** Git history. The code is recoverable from the last commit before deletion.

---

## Implementation Order

This document describes the design. Implementation is staged:

1. **Phase 5 Candidate 1:** Add `FEATURE_FLAGS.useNormalizedIBD`. Modify `_makeAreaPI` IBD branch. Do not add config object yet. (IBD migration is simple enough to not need full config machinery.)
2. **Phase 5 Candidate 2:** Add `FEATURE_FLAGS.useNormalizedTED`. Same pattern as IBD.
3. **Phase 5 Candidate 3:** Add `FEATURE_FLAGS.useNormalizedDrugModal`. Promote `_runPhase4CModalDualRead` read to primary.
4. **`DASHBOARD_VIEW_CONFIG` introduction:** After Candidates 1–3 land, introduce the config object. Candidates 1–3 can be retrofitted to use it.
5. **TL1A shadow mode:** `FEATURE_FLAGS.tl1aShadowMode = true`. No visible changes.
6. **`_makeAreaPI` config-aware refactor:** Implement view-type dispatch. Test on IBD and TED (already migrated) before touching TL1A.
7. **TL1A unified flag:** `FEATURE_FLAGS.useUnifiedTL1A` testing.
8. **`tl1aPI` retirement:** After all acceptance criteria pass.

---

*Generated: 2026-05-25 — Session 53m*  
*Status: Design only. Not approved for implementation.*
