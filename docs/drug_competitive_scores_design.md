# drug_competitive_scores — Design Specification
**Written:** Session 58 — 2026-05-26  
**Status:** Architecture design — implementation target Phase 6 / WS3  
**Replaces:** `drug_area_scores` (212 rows, legacy area_id dependency)

---

## Why This Table Exists

`drug_area_scores` is the output layer for every Claude enrichment run. It stores:
- `overlap` — Direct / Adjacent / Same-Space classification
- `overlap_rationale` — Claude's competitive reasoning text
- `cls` — classification tag
- `confidence_level` — A / B / C / inferred
- `source_url` — evidence provenance
- `vs_ailux` — comparison note relative to Ailux position

This is the intelligence that makes Meridian a BD tool rather than a drug database. The problem is structural: `drug_area_scores` uses `area_id` as its context key — a legacy concept that will not survive Phase 6.

**The design goal:** Preserve every byte of competitive intelligence. Replace the `area_id` anchor with explicit, normalized context keys (`context_type` + `context_id`) that survive the drug_areas retirement.

---

## Schema

```sql
CREATE TABLE drug_competitive_scores (
  id                SERIAL PRIMARY KEY,
  drug_id           TEXT NOT NULL REFERENCES drugs(id),
  
  -- Context: what competitive lens is this score about?
  context_type      TEXT NOT NULL,
    -- 'target'          — e.g., "how competitive is this drug in the TL1A space?"
    -- 'indication'      — e.g., "how competitive is this drug in UC?"
    -- 'strategic_view'  — e.g., "position within the autoimmune landscape"
    -- 'platform_view'   — e.g., "T-cell platform capability assessment"
  context_id        TEXT NOT NULL,
    -- For 'target':         drug_targets.target_id      (e.g., 'tl1a', 'il4ra', 'fcrn')
    -- For 'indication':     drug_indications.indication_id (e.g., 'uc', 'ted', 'ra')
    -- For 'strategic_view': company_strategic_views.view_id (e.g., 'autoimmune', 'respiratory')
    -- For 'platform_view':  company_platform_views.platform_id (e.g., 'tcell')
  
  -- Competitive assessment (migrated from drug_area_scores)
  overlap           TEXT,           -- 'Direct' | 'Adjacent' | 'Same-Space'
  overlap_rationale TEXT,           -- Claude's competitive reasoning text
  cls               TEXT,           -- classification tag (free-form)
  confidence_level  TEXT,           -- 'A' | 'B' | 'C' | 'inferred'
  source_url        TEXT,           -- primary evidence provenance URL
  vs_ailux          TEXT,           -- comparison note relative to Ailux position
  
  -- Provenance chain
  enrichment_run_id TEXT,           -- links to future enrichment_runs table
  enriched_by       TEXT DEFAULT 'claude',
  enriched_at       TIMESTAMPTZ,
  
  -- Audit fields
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW(),
  
  -- Uniqueness: one score per drug per context
  UNIQUE(drug_id, context_type, context_id)
);

CREATE INDEX idx_dcs_drug_id ON drug_competitive_scores(drug_id);
CREATE INDEX idx_dcs_context ON drug_competitive_scores(context_type, context_id);
CREATE INDEX idx_dcs_overlap ON drug_competitive_scores(overlap);
```

---

## Migration: drug_area_scores → drug_competitive_scores

### Mapping Logic

Each `drug_area_scores` row has `drug_id` + `area_id`. The migration must determine `context_type` and `context_id` for each `area_id`:

| area_id | context_type | context_id | Notes |
|---------|-------------|------------|-------|
| `tl1a` | `target` | `tl1a` | Direct target match |
| `il4ra` | `target` | `il4ra` | Direct target match |
| `tslp` | `target` | `tslp` | Direct target match |
| `fcrn` | `target` | `fcrn` | Direct target match |
| `ibd` | `indication` | `uc` | IBD = UC∪CD; use UC as primary context |
| `ibd` | `indication` | `cd` | IBD = UC∪CD; second row for CD context |
| `igf1r` | `indication` | `ted` | IGF-1R tab = TED clinical program |
| `ted` | `indication` | `ted` | Duplicate of igf1r in many cases — deduplicate |
| `autoimmune` | `strategic_view` | `autoimmune` | Curated strategic view |
| `respiratory` | `strategic_view` | `respiratory` | Curated strategic view |
| `tcell` | `platform_view` | `tcell` | Platform modality view |

### Special Cases

**IBD → dual-indication expansion:**  
`drug_area_scores` has 1 row per IBD drug. Post-migration, UC-dominant drugs (like mirikizumab) should have a primary UC context. CD-dominant drugs (like risankizumab) should have a primary CD context. IBD overlap drugs (like upadacitinib) get two rows. This requires per-drug classification during migration rather than a blind 1:1 copy.

**TED vs IGF-1R deduplication:**  
Some drugs appear in both `area_id='ted'` and `area_id='igf1r'` in drug_area_scores. These are semantically identical (TED is the indication; IGF-1R was the legacy target proxy for TED). The migration script should prefer the more recent or higher-confidence row and produce a single `context_type='indication', context_id='ted'` row.

**atopy → multi-context expansion:**  
`area_id='atopy'` is a cross-target concept covering IL-4Rα + TSLP. Post-migration, an atopy-classified drug should have separate rows: `context_type='target', context_id='il4ra'` and `context_type='target', context_id='tslp'` (where both apply). Use the drug's actual drug_targets rows to determine which contexts apply.

### Migration Script: `scripts/migrate_drug_area_scores.py`

```python
"""
Migrate drug_area_scores → drug_competitive_scores
Strategy: deterministic mapping where possible, audit log for ambiguous cases
"""

AREA_ID_CONTEXT_MAP = {
    'tl1a':        [('target', 'tl1a')],
    'il4ra':       [('target', 'il4ra')],
    'tslp':        [('target', 'tslp')],
    'fcrn':        [('target', 'fcrn')],
    'igf1r':       [('indication', 'ted')],
    'ted':         [('indication', 'ted')],   # deduplicate with igf1r on insert
    'autoimmune':  [('strategic_view', 'autoimmune')],
    'respiratory': [('strategic_view', 'respiratory')],
    'tcell':       [('platform_view', 'tcell')],
    # IBD handled separately — per-drug UC/CD expansion
}

# IBD expansion: classify drugs by dominant indication before mapping
# 1. Query drug_indications for drug_id ∈ IBD score drugs, filter indication_id IN ('uc','cd')
# 2. If drug has uc but not cd → context_id='uc'
# 3. If drug has cd but not uc → context_id='cd'
# 4. If drug has both → insert two rows (uc + cd)
# 5. If drug has neither → context_id='ibd' (legacy fallback, flag for audit)

# Conflict resolution: UNIQUE(drug_id, context_type, context_id)
# On conflict: prefer row with higher confidence_level order: A > B > C > inferred
# If same confidence: prefer row with non-null source_url
# Losers logged to migration_audit.json for manual review
```

---

## Consumer Migration Map

8 consumers currently read `drug_area_scores`. Migration complexity varies:

| Consumer | Location | Current Query | New Query Pattern | Complexity |
|----------|----------|--------------|-------------------|------------|
| Drug modal overlap display | index.html ~L11675 | `drug_area_scores.eq('drug_id', drugId)` | `drug_competitive_scores.eq('drug_id', drugId)` | **Low** — same shape, different table |
| Modal related drug scores | index.html ~L11716 | `drug_area_scores.eq('drug_id', rid)` | Same as above | **Low** |
| PI tab drug card badges | index.html ~L10771 | `drug_area_scores.eq('drug_id',...).eq('area_id', areaId)` | Add `.eq('context_type', type).eq('context_id', id)` | **Medium** — must derive context from tab |
| Audit tab scoring | index.html ~L18796 | `drug_area_scores.select(...)` | `drug_competitive_scores.select(...)` | **Low** — display only |
| `company_enrichment.py` | scripts/ | Writes `drug_area_scores` rows | Write `drug_competitive_scores` rows | **HIGH** — primary write path |
| `compute_landscape_coverage.py` | scripts/ | Reads coverage from `drug_area_scores` | Aggregate `drug_competitive_scores` by context | **Medium** — rewrite calculations |
| `research_intelligence.py` | scripts/ | Reads `drug_areas` + `drug_area_scores` | Read `drug_competitive_scores` by context | **Medium** |
| `seed_preclinical_competitors.py` | scripts/ | Writes `drug_areas` + `drug_area_scores` | Write normalized tables + `drug_competitive_scores` | **HIGH** |

### Tab → Context Mapping (for PI tab migration)

When the PI tab queries scores for its drug cards, it currently passes `area_id`. Post-migration it must pass `(context_type, context_id)`:

| Tab | area_id | → context_type | → context_id |
|-----|---------|----------------|-------------|
| tl1a | tl1a | target | tl1a |
| tslp | tslp | target | tslp |
| il4ra-tslp | il4ra, tslp | target | il4ra OR tslp (drug-specific) |
| il4ra-ox40l | il4ra | target | il4ra |
| igf1r-tshr | igf1r | indication | ted |
| fcrn | fcrn | target | fcrn |
| ace (tcell) | tcell | platform_view | tcell |

**il4ra-tslp complexity:** This tab shows drugs that may be in il4ra OR tslp territory. The score query must use the drug's primary target to determine which context_id to use. This is the most complex consumer migration.

---

## Enrichment Pipeline: Updated Schema

`company_enrichment.py` currently writes:
```python
sb.table("drug_area_scores").upsert({
    "drug_id": drug_id,
    "area_id": area_id,
    "overlap": overlap,
    "overlap_rationale": rationale,
    "cls": cls_tag,
    "confidence_level": confidence,
    "source_url": source_url,
    "vs_ailux": vs_note
})
```

Post-migration it will write:
```python
sb.table("drug_competitive_scores").upsert({
    "drug_id": drug_id,
    "context_type": context_type,   # derived from area/target/indication
    "context_id": context_id,
    "overlap": overlap,
    "overlap_rationale": rationale,
    "cls": cls_tag,
    "confidence_level": confidence,
    "source_url": source_url,
    "vs_ailux": vs_note,
    "enriched_at": datetime.utcnow().isoformat()
}, on_conflict="drug_id,context_type,context_id")
```

The enrichment prompt itself does **not** change — it still produces the same overlap/rationale/cls/confidence output. Only the persistence target changes.

---

## Parallel-Write Period

To de-risk the migration, the enrichment pipeline will write to **both** tables for a monitoring window before cutting over:

```
Phase 6.3a: Create drug_competitive_scores table + run migration script
Phase 6.3b: Enable parallel writes in company_enrichment.py (write both tables)
Phase 6.3c: Migrate all 8 consumers to read from drug_competitive_scores
Phase 6.3d: Validate parity: SELECT COUNT(*) divergence + spot-check 20 rows
Phase 6.3e: Disable drug_area_scores writes in enrichment pipeline
Phase 6.3f: 2-week monitoring window (drug_area_scores frozen, read-only)
Phase 6.3g: DROP TABLE drug_area_scores (after monitoring confirms no regressions)
```

---

## Provenance Chain (Phase 6 Target)

The full intelligence chain after migration:

```
Drug
 └── drug_targets (target_id, primary_target)
      └── drug_competitive_scores (context_type='target', context_id=target_id)
           └── overlap, overlap_rationale, confidence_level, source_url
                └── enrichment_runs.id (future: audit trail per enrichment batch)

Drug
 └── drug_indications (indication_id)
      └── drug_competitive_scores (context_type='indication', context_id=indication_id)
           └── same fields
```

Every competitive assessment has an explicit biological provenance chain. The question "why does Meridian classify Drug X as Adjacent in the TL1A space?" becomes answerable in full:
- drug_targets: Drug X binds target Y, and Y is in the TL1A competitive context
- drug_competitive_scores: Claude assessed X as Adjacent because [rationale text] based on [source_url]

---

## What This Enables (Phase 6 Products)

1. **Cross-context competitive queries:** "Show me all drugs that are Direct competitors in both the TL1A AND UC contexts" — currently impossible with area_id
2. **Context-aware enrichment freshness:** Track when each context was last enriched separately — TL1A scores may be 2 weeks stale while FcRn scores are current
3. **Strategic view scoring:** Companies can be scored for their position in a strategic view using the same schema as target-level scoring
4. **Provenance completeness:** Every score links forward to its biological anchor (drug_targets or drug_indications) and backward to its source URL

---

## Open Questions (Before Implementation)

1. **atopy area_id:** Does `area_id='atopy'` in drug_area_scores represent the combo-tab context (il4ra+tslp together), or each target independently? Need to inspect rows before writing the migration expansion logic.
2. **ted vs igf1r deduplication:** How many drugs have BOTH area_id='ted' and area_id='igf1r' scores? If many, the deduplication logic needs a clear tiebreaker rule.
3. **confidence_level for migrated rows:** Migrated rows should be tagged `enriched_by='migration'` + `enrichment_run_id='migration-2026-05'` to distinguish from freshly enriched rows.
4. **enrichment_runs table:** Future requirement. Not needed for initial migration but should be designed before the parallel-write period begins.

---

## Implementation Order

1. Run pre-migration queries: count rows per area_id, identify ted/igf1r duplicates, identify atopy scope
2. Write `scripts/migrate_drug_area_scores.py`
3. Create `drug_competitive_scores` table (SQL migration via Supabase dashboard)
4. Run migration script — verify row count + spot-check 20 rows
5. Enable parallel writes in `company_enrichment.py`
6. Migrate consumers one at a time (Low complexity first: modal → audit tab → PI tab badges → backend scripts)
7. Validate parity
8. Freeze drug_area_scores writes
9. Monitor for 2 weeks
10. DROP TABLE drug_area_scores

**Session estimate:** 5–8 sessions. Steps 1–4 = 1 session. Steps 5–7 = 2–4 sessions (one per major consumer pair). Steps 8–10 = 1 session.
