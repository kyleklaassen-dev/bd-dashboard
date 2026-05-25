# Evidence Reconciliation Layer — Meridian BD Platform
**Design note · Session 53c · 2026-05-25**  
**Status:** Designed — not yet built. Seed data captured in Phase 4 harness Part 4b.

---

## Core Principle

> **No single table is ground truth.**
> Truth is evidence-weighted and relationship-validated across all tables.

The relationship tables built in Phases 2–3 (drug_targets, drug_indications, trial_indications) are first-pass normalized relationship layers. They were built with preview, confidence scoring, review status, and validation gates — making them auditable and correctable. But they are not final truth. Some relationships may be incomplete or wrong because:

- Legacy data contained curation errors (e.g., lm-302 in IBD area)
- Structured fields inherited errors from legacy (drugs.target, drugs.indication_short)
- Backfill scripts could only see evidence available at the time
- No single enrichment pass saw all evidence simultaneously

**Before Phase 5 (dashboard migration):** Phase 4A — Evidence Reconciliation — cross-checks all relationship tables against each other and against source evidence. Disagreements are classified. Corrections are proposed. Human approval gates ambiguous cases.

---

## The Self-Healing Loop

```
1. Detect mismatch
       │
2. Classify mismatch
       │
3. Propose correction + assign confidence
       │
4. Human approve / reject  ◄─── auto-approved for mechanical fixes only
       │
5. Apply correction
       │
6. Re-run consistency checks
       └──────────────────────────────────────────────┐
                                                      ▼
                                               (repeat until converged)
```

---

## Evidence Sources (cross-check matrix)

| Table | What it asserts |
|---|---|
| `drug_areas` | Drug belongs to a legacy therapeutic area (production baseline) |
| `drug_indications` | Drug targets a specific indication (normalized candidate truth) |
| `drug_targets` | Drug acts on a specific molecular target |
| `drug_area_scores` | Competitive positioning within a legacy area |
| `drugs.target` | Free-text target field from original intake |
| `drugs.indication_short` | Free-text indication from original intake |
| `trial_indications` | Trial is registered for a specific indication |
| `trials.indication` | Free-text indication from trial record |
| `sources` | Source evidence for drug activity |
| `catalysts` | Upcoming readouts tied to a legacy area |
| `signals` | Intel signals tied to a legacy area |

**Reconciliation logic:** For a given drug, if 5 of these tables agree on an indication and 1 disagrees, the single disagree is likely noise. If 3 agree and 3 disagree, it's a genuine ambiguity requiring human review.

---

## Classification Types

| Classification | Meaning | Auto-fixable? |
|---|---|---|
| `legacy_noise_removed` | Legacy record contradicted by ≥3 other evidence sources | Propose, human approves |
| `normalized_gap` | Valid relationship absent from normalized tables; supported by multiple sources | Auto-propose backfill |
| `ontology_scope_difference` | Tables disagree because they use different semantic buckets | Requires human review |
| `needs_manual_review` | Insufficient cross-table evidence to classify | Human required |
| `new_normalized_value` | Normalized correctly adds a relationship legacy missed | Document, no fix needed |
| `source_conflict` | One source contradicts all others for a specific claim | Auto-propose, human approves |
| `cross_table_inconsistency` | Record disagrees with ≥2 independent evidence tables | Auto-propose with confidence, human approves |

---

## Auto-Fix Rules (no human required)

Apply automatically only:
- Casing normalization (e.g., `UC` → `uc`)
- Known alias mappings (e.g., `severe_asthma` → `asthma`)
- Mechanical FK corrections where the target entity exists and there is no ambiguity
- Governance-locked transformations (enumerated in `docs/indication_ontology_governance.md`)

---

## Auto-Propose Rules (propose + await human approval)

Propose automatically when:
- A legacy area assignment is contradicted by drug target, modality, indication_short, and trial_indications simultaneously
- A drug is absent from drug_indications but trial_indications strongly supports the indication (confidence ≥ 0.7, ≥2 trials)
- A drug is absent from drug_targets but drugs.target field and legacy target table agree

---

## Human Review Required

Human approval required for:
- New disease scope decisions (what counts as "IBD")
- New target definitions
- Ambiguous biology (mechanism spans multiple diseases)
- Commercial / strategic interpretation
- Conflicting strong sources (e.g., two high-quality publications disagree)

---

## `entity_consistency_checks` Table Schema

```sql
CREATE TABLE entity_consistency_checks (
  id                  SERIAL PRIMARY KEY,
  entity_type         TEXT NOT NULL,            -- 'drug', 'indication', 'target', 'trial', etc.
  entity_id           TEXT NOT NULL,            -- foreign key to the entity
  check_type          TEXT NOT NULL,            -- 'cross_table_inconsistency', 'source_conflict', etc.
  severity            TEXT NOT NULL,            -- 'high', 'medium', 'low'
  status              TEXT DEFAULT 'open',      -- 'open', 'proposed', 'approved', 'rejected', 'resolved'
  conflicting_tables  TEXT[],                   -- e.g. ['drug_areas', 'drug_indications', 'drug_targets']
  conflict_summary    TEXT,                     -- human-readable description of the conflict
  evidence_for        JSONB,                    -- evidence supporting the normalized relationship
  evidence_against    JSONB,                    -- evidence contradicting it
  proposed_fix        TEXT,                     -- proposed correction action
  confidence_score    NUMERIC(4,3),             -- 0.0–1.0
  review_status       TEXT DEFAULT 'pending',   -- 'pending', 'approved', 'rejected'
  reviewed_by         TEXT,
  created_at          TIMESTAMPTZ DEFAULT now(),
  resolved_at         TIMESTAMPTZ
);
```

**Notes:**
- `evidence_for` and `evidence_against` are JSONB arrays of `{table, field, value, source_id}` objects
- `conflicting_tables` enables diagnostic queries like "which two tables disagree most often?"
- `confidence_score` drives the auto-approve threshold (e.g., ≥ 0.95 + auto-fixable type = auto-approve)

---

## Seed Examples (from Phase 4 harness Part 4b)

### lm-302
- **Entity:** drug / lm-302
- **Check type:** cross_table_inconsistency
- **Severity:** high
- **Conflicting tables:** drug_areas (tl1a, ibd) vs drug_targets (CLDN18.2) + drugs.target (Claudin 18.2) + drugs.indication_short (gastric cancer/GEJ)
- **Evidence for IBD:** drug_areas assignment only (legacy curation)
- **Evidence against IBD:** 3 independent sources (target, indication_short, modality=ADC) all point to gastric oncology
- **Proposed fix:** Classify as legacy_noise_removed. Exclude from IBD/TL1A normalized denominator.
- **Confidence:** 0.97

### sim0500
- **Entity:** drug / sim0500
- **Check type:** cross_table_inconsistency
- **Severity:** high
- **Conflicting tables:** drug_areas (tl1a, ibd) vs drugs.indication_short (RRMM) + modality (trispecific)
- **Evidence for IBD:** drug_areas assignment only
- **Evidence against IBD:** RRMM (relapsed/refractory multiple myeloma) is hematology oncology
- **Proposed fix:** Classify as legacy_noise_removed. Exclude from IBD/TL1A normalized denominator.
- **Confidence:** 0.97

### spy072
- **Entity:** drug / spy072
- **Check type:** ontology_scope_difference
- **Severity:** medium
- **Conflicting tables:** drug_areas (tl1a) vs drug_indications (none for IBD) + drugs.indication_short (PsA, axSpA)
- **Evidence:** TL1A mechanism is correct; indication is rheumatology (psoriatic arthritis, axial spondyloarthritis) not IBD
- **Proposed fix:** Classify as legacy_noise_removed for IBD denominator. Could be valid for a future rheumatology area.
- **Confidence:** 0.92

### epi-001
- **Entity:** drug / epi-001
- **Check type:** needs_manual_review
- **Severity:** medium
- **Conflicting tables:** drug_areas (tl1a, ibd) vs drug_indications (held: review_required)
- **Evidence for IBD:** TL1A mechanism is IBD-relevant; anti-TL1A class is IBD-validated
- **Evidence against:** Preclinical only; no indication_short; no trial evidence; no published IBD data
- **Proposed fix:** Hold in backfill_preview until source evidence confirms UC or CD indication.
- **Confidence:** 0.55 (insufficient to auto-decide)

### batoclimab
- **Entity:** drug / batoclimab
- **Check type:** cross_table_inconsistency
- **Severity:** high
- **Conflicting tables:** drug_areas (fcrn, igf1r, autoimmune, ted — 4 separate) vs drug_indications (gmg, cidp, waiha via fcrn mechanism) vs drug_targets (FcRn/FCGRT)
- **Conflict summary:** Legacy placed batoclimab in 4 different areas. Normalized correctly targets FcRn mechanism → gMG/CIDP/WAIHA. The legacy assignments to igf1r, autoimmune, ted are a curation artifact of the legacy catch-all bucket structure.
- **Proposed fix:** Accept drug_indications (gmg, cidp, waiha) as canonical. Flag legacy multi-area assignment for cleanup in Wave 2D.
- **Confidence:** 0.88

### upadacitinib (Rinvoq) — atopy gap
- **Entity:** drug / upadacitinib
- **Check type:** normalized_gap
- **Severity:** medium
- **Conflicting tables:** drug_areas (atopy) but absent from drug_indications for ad
- **Evidence for AD:** FDA-approved for atopic dermatitis (JAK1 inhibitor); published in NDA + trials
- **Evidence against:** None
- **Proposed fix:** Backfill drug_indications: upadacitinib → ad, confidence A.
- **Confidence:** 0.97

### gb004 — mechanism field data error
- **Entity:** drug / gb004
- **Check type:** source_conflict
- **Severity:** medium
- **Conflict:** `drugs.mechanism = 'Anti-TL1A'` — this is incorrect. GB004 is a PHD inhibitor (HIF-1α stabilizer, oral small molecule), not an anti-TL1A antibody. The drug targets the PHD1/HIF-1α pathway to reduce inflammation. `drugs.target = 'PHD1/HIF-1α'` and `drugs.modality = 'oral HIF-1α stabilizer (PHD inhibitor, small molecule)'` are both correct — only the mechanism field is wrong.
- **Evidence for correction:** drugs.target, drugs.modality, and drug indication (UC, terminated) all confirm PHD inhibitor biology. Anti-TL1A antibodies are biologics, not oral small molecules.
- **Proposed fix:** Update `drugs.mechanism` for gb004 from `'Anti-TL1A'` to `'PHD inhibitor (HIF-1α stabilizer)'`. Requires advisor approval before applying.
- **Confidence:** 0.95 (high — cross-field evidence is internally consistent; mechanism field is the outlier)
- **Status:** Backlogged — do NOT fix during Phase 4B dual-read work. Requires separate evidence review and field update approval.

### ep006 / es302 — duplicate drug_id
- **Entity:** drug / ep006, es302
- **Check type:** cross_table_inconsistency
- **Severity:** medium
- **Conflict:** ep006 appears in legacy drug_areas and comparison results. es302 may be the canonical ID for the same molecule (IL-23 inhibitor, UC/CD).
- **Proposed fix:** Determine canonical ID. If es302 = canonical: tombstone ep006 → es302. Merge drug_areas + drug_indications rows.
- **Confidence:** 0.70 (requires confirmation)

---

## Relationship to Phase 4 Harness

The Phase 4 harness (`scripts/phase4_compare_legacy_vs_normalized.py`) currently:
- Detects differences between legacy and normalized tables (Parts 1–2)
- Classifies each extra-legacy and extra-norm record (Part 4)
- Reports reconciliation candidates (Part 4b)

**View-type governance (2026-05-25):**
Legacy areas are not a uniform ontological category. The harness now distinguishes view types via `LEGACY_VIEW_TYPES`:
- **Target views** (`tl1a`, `fcrn`, `igf1r`, `tslp`, `il4ra`) — normalized via `drug_targets.target_id`
- **Indication group views** (`ibd`, `atopy`, `respiratory`, `autoimmune`) — normalized via `drug_indications.indication_id`
- **Indication views** (`ted`) — normalized via `drug_indications.indication_id`
- **Platform views** (`tcell`) — no clean normalized path yet

TL1A is a biological **target**. IBD is an **indication group** (UC + CD). These require separate Phase 4B dual-read validation paths. Do not conflate their comparison logic or migration planning.

**Phase 4 sequence (updated 2026-05-25):**
1. ✅ Phase 4 harness — difference detection and classification
2. ✅ Phase 4A — Evidence Reconciliation — candidate review + corrections applied (2026-05-25)
3. ✅ Semantic correction — `LEGACY_VIEW_TYPES` added; TL1A target-view and IBD indication-group-view separated in harness
4. 🔲 Phase 4B — Dual-read validation:
   - IBD indication-group path: legacy `drug_area_scores.area_id = 'ibd'` vs `drug_indications WHERE indication_id IN ('uc','cd')`
   - TL1A target-view path: legacy `drug_area_scores.area_id = 'tl1a'` vs `drug_targets WHERE target_id = 'tl1a'`
5. 🔲 Phase 5 — Switch dashboard logic (only after 4A and 4B pass)

**Build order for entity_consistency_checks:**
1. Create table via migration SQL
2. Build `scripts/run_evidence_reconciliation.py` — queries all relationship tables for a drug, detects inconsistencies, writes rows to entity_consistency_checks
3. Seed with the 7 known candidates above
4. Surface in dashboard (Ontology Audit tab or new Reconciliation tab)
5. Add review UI: approve / reject / resolve buttons

---

## What This Does NOT Change

- drug_targets (173 rows) — valid; keep all rows
- drug_indications (192 rows) — valid; keep all rows
- trial_indications (319 rows) — valid; keep all rows
- ontology_edges (25 rows) — locked until Phase 4B dual-read clears

All existing relationship rows remain intact. The reconciliation layer adds a *correction proposal queue*, not a rollback. Rows are flagged for review, not deleted.

---

## Non-Negotiable Rules (unchanged)

1. No skipping validation gates.
2. No bypassing governance.
3. No dashboard rewiring before Phase 4B dual-read validates zero regressions.
4. No unlocking ontology_edges until advisor explicitly approves post Phase 4A+4B.
