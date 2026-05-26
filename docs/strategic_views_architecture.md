# Strategic View Architecture Design
**Generated:** Session 58 — 2026-05-26  
**Status:** Design proposal — advisor review required before implementation  
**Purpose:** Replace curated-strategic and curated-platform `drug_areas` concepts (`autoimmune`, `respiratory`, `tcell`) with a purpose-built architecture that separates biological ontology from strategic classification.

---

## Problem Statement

Three `drug_areas` area_ids cannot be migrated to `drug_targets` or `drug_indications` because they are not biological relationships — they are **human strategic judgments** about how to group drugs for BD analysis:

| area_id | Why it can't migrate |
|---------|---------------------|
| `autoimmune` | Spans 8+ targets (FcRn, CD19, CD20, CD38, CD3, BAFF-R, TSHR, IgE...). The grouping concept is "broad autoimmune landscape" not any single mechanism. |
| `respiratory` | Spans TSLP, IL-33, IL-13, IL-5Rα, JAK. The grouping concept is "airway disease competitive landscape" not any single mechanism. |
| `tcell` | Spans CD19, CD20, BCMA, CD3. The grouping concept is "T-cell therapy modality" — a platform approach, not a target class. |

**Governance Rule #4:** Curated strategic concepts are not ontology relationships.

These concepts are valuable for BD preparation — they define *competitive landscapes Kyle cares about strategically*, not what a drug biologically does. They require a separate architecture.

---

## Proposed Architecture

### Two New Tables

#### `company_strategic_views`
Stores company-level participation in a curated strategic grouping. Designed for BD landscape views that span multiple mechanisms.

```sql
CREATE TABLE company_strategic_views (
  id                  SERIAL PRIMARY KEY,
  company_id          TEXT NOT NULL REFERENCES companies(id),
  view_id             TEXT NOT NULL,              -- 'autoimmune', 'respiratory', 'cardiovascular'
  view_label          TEXT NOT NULL,              -- 'Broad Autoimmune', 'Respiratory'
  participation_type  TEXT NOT NULL,              -- 'lead', 'pipeline', 'emerging'
  rationale           TEXT,                       -- Why this company belongs in this view
  drug_ids            TEXT[],                     -- Which of their drugs qualify (curated list)
  last_reviewed_at    TIMESTAMPTZ,
  reviewed_by         TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(company_id, view_id)
);
```

**Example rows:**
| company_id | view_id | participation_type | drug_ids |
|------------|---------|-------------------|----------|
| abbvie | autoimmune | lead | ['ianalumab', 'iscalimab', 'cand319', 'cand460'] |
| janssen | autoimmune | lead | ['nipocalimab', 'guselkumab-golimumab'] |
| astrazeneca | respiratory | lead | ['tezepelumab', 'tozorakimab'] |
| sanofi | respiratory | lead | ['dupilumab', 'itepekimab'] |

---

#### `company_platform_views`
Stores company-level participation in a modality or platform technology category.

```sql
CREATE TABLE company_platform_views (
  id                  SERIAL PRIMARY KEY,
  company_id          TEXT NOT NULL REFERENCES companies(id),
  platform_id         TEXT NOT NULL,             -- 'tcell', 'adc', 'cart', 'bispecific'
  platform_label      TEXT NOT NULL,             -- 'T-Cell Therapy', 'CAR-T', 'ADC'
  platform_type       TEXT NOT NULL,             -- 'modality', 'mechanism_class', 'delivery'
  capability_stage    TEXT,                      -- 'clinical', 'discovery', 'partnership'
  lead_programs       TEXT[],                    -- Key drug_ids in this platform
  bd_angle            TEXT,                      -- Why this matters for Ailux BD
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(company_id, platform_id)
);
```

**Example rows (tcell platform):**
| company_id | platform_id | platform_type | lead_programs |
|------------|-------------|--------------|--------------|
| cabaletta | tcell | modality | ['caba-201'] |
| kyverna | tcell | modality | ['kyv-101'] |
| atara | tcell | modality | ['atg-201'] |
| wugen | tcell | modality | ['descartes08'] |
| candel | tcell | modality | ['cizutamig'] |

---

## Why Not Just Add a `view_type` Column to `drug_areas`?

Three reasons:

1. **Semantic clarity.** `drug_areas` currently conflates four things: biological targets, disease indications, strategic groupings, and platform views. Adding a `view_type` column to distinguish them preserves the confusion; new tables make the distinction architectural.

2. **Query path.** The dashboard tab system (TAB_AREA_MAP) queries `drug_areas.area_id`. Strategic views don't map to tabs in the same way — they're used for BD landscape browsing and company profiling. They deserve a different query pattern.

3. **Schema ownership.** `drug_areas` has a PK of `(drug_id, area_id)`. Strategic views are inherently company-centric, not drug-centric. The natural join is `company → view → drugs`, not `drug → area`. `company_strategic_views` with a `drug_ids[]` array column reflects this correctly.

---

## Migration Plan

### Phase 1: Seed company_strategic_views from existing drug_areas

For each of the three preserved areas, generate seed rows from existing `drug_areas` + `company` joins:

```python
# Pseudocode
for area_id in ['autoimmune', 'respiratory']:
    drugs_in_area = query drug_areas where area_id = area_id
    for drug in drugs_in_area:
        company_id = drug.company_id
        upsert company_strategic_views(
            company_id=company_id,
            view_id=area_id,
            view_label=VIEW_LABELS[area_id],
            participation_type='pipeline',  # default; curate manually
            drug_ids=[drug.drug_id]  # merge per company
        )
```

### Phase 2: Seed company_platform_views from tcell drug_areas

Same pattern for tcell → company_platform_views(platform_id='tcell').

### Phase 3: Build dashboard query layer for new views

The `ace` tab (TAB_AREA_MAP: `['tcell']`) currently queries `drug_areas.area_id = 'tcell'`. After migration:
- New query: `company_platform_views.platform_id = 'tcell'` → join to drugs via `lead_programs` array
- TAB_AREA_MAP would be extended or the tab would use a new query path

### Phase 4: 8-gate validation for tcell tab

The `ace` tab is the only preserved area with a live tab. Its migration must go through the same 8-gate browser validation protocol as C1–C7:
- G1-G4: Drug counts match (drug_platform_views vs drug_areas)
- G5: No OOS classification errors
- G6: Zero console errors with old flag
- G7: compare_pass_oos_adjusted with new source
- G8: Rollback confirmed

### Phase 5: Retire drug_areas rows for autoimmune, respiratory, tcell

Once both new tables are seeded, validated, and serving the dashboard correctly, the drug_areas rows for these three area_ids can be batch-deleted.

---

## Dashboard Integration: Strategic Views Panel

Rather than tabs (which imply a specific competitive landscape), strategic views should be surfaced as:

1. **Company profile panel** — when viewing a company, show which strategic views they participate in (autoimmune, respiratory, platform play)
2. **BD landscape filter** — a filter in the main drugs view: "Show me all drugs in the autoimmune strategic view"
3. **Signals feed tag** — catalyst events tagged with their strategic view context (e.g. an IND filing tagged as autoimmune + tcell)

This is architecturally different from the PI tabs (which are point-in-time competitive landscapes) — strategic views are cross-cutting lenses.

---

## Governance Rules for Strategic Views

**Rule 1: Strategic views are human-curated.** They are not automatically derived from targets or indications. A drug belongs in a strategic view because a human decided it matters for BD analysis in that context.

**Rule 2: Strategic views can overlap freely.** A drug can be in autoimmune AND tcell AND respiratory. Unlike drug_areas where area_ids were siloed per tab, strategic views are multi-dimensional lenses.

**Rule 3: Strategic views are company-centric, not drug-centric.** The unit of analysis is "which companies are players in X space" not "which drugs target X". This is the BD-native framing.

**Rule 4: Platform views track capability, not biology.** `company_platform_views.capability_stage` distinguishes companies with clinical programs vs discovery-stage. This enables the BD question: "Who is building a T-cell therapy capability worth partnering with?"

**Rule 5: No feature flag required.** Unlike C1–C7 which replaced existing dashboard queries, strategic views are additive. They don't modify existing tab behavior — they add new query surfaces. No migration gate protocol is needed for the new tables themselves. The `tcell` tab migration still requires the 8-gate protocol.

---

## Implementation Priority

| Step | Blocker | Priority |
|------|---------|---------|
| Create `company_strategic_views` table | None | Medium — no active tab dependency |
| Create `company_platform_views` table | None | Medium — no active tab dependency |
| Seed autoimmune + respiratory from drug_areas | Table creation | Medium |
| Seed tcell from drug_areas | Table creation | Medium |
| Migrate `ace` tab to company_platform_views | Seed complete + 8-gate validation | High — only remaining active non-redirected tab |
| Retire drug_areas(autoimmune, respiratory, tcell) | Tab migration validated | Final step |

**Recommended timing:** After C5/C6/C7 activations are complete. The migration queue (Track A) is the current P0; strategic view architecture is the next architectural inflection after that queue closes.
