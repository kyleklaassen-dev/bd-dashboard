# BD Platform — Backend Alignment & Legacy Retirement Audit
**Session 63 — 2026-05-26**
**Commissioned as full nine-section audit prior to frontend acceleration decision**

---

## Audit Summary

**Integration Status: Advanced Partial**

The backend has crossed the ontology build threshold. All biological dashboard surfaces are ontology-backed. The competitive intelligence layer is populated and validated. Governance metadata exists. What remains is formalization: making governance executable, completing the competitive score consumer migration, and giving strategic/platform concepts a permanent backend home. Frontend work can resume with bounded scope constraints — but three backend blockers must be resolved in parallel.

---

## Section 1 — Source-of-Truth Map

### Authoritative Table per Concept

| Concept | Source-of-Truth Table | Status | Notes |
|---|---|---|---|
| Target reference | `targets` | `source_of_truth` | 176 drug_targets rows, correct FK |
| Indication reference | `indications` | `source_of_truth` | With indication_aliases for canonicalization |
| Drug-target relationships | `drug_targets` | `source_of_truth` | 176 rows — drives TL1A/IL-4Rα/TSLP/FcRn tabs |
| Drug-indication relationships | `drug_indications` | `source_of_truth` | 246 rows — drives IBD/TED tabs |
| Trial-indication relationships | `trial_indications` | `source_of_truth` | 301 rows |
| Competitive scores | `drug_area_scores` | `compatibility_shadow` | 212 rows — production writes here, no consumer reads new table yet |
| Competitive scores (successor) | `drug_competitive_scores` | `successor_layer` | 234 rows — populated, validated, no consumer migration yet |
| Area lifecycle/governance | `area_metadata` | `source_of_truth` | 11 rows — fully seeded |
| Strategic views | *(no table)* | `pending_replacement` | drug_competitive_scores has strategic_view rows but no company_strategic_views |
| Platform views | *(no table)* | `pending_replacement` | drug_competitive_scores has platform_view rows but no company_platform_views |
| Enrichment outputs | `drug_area_scores` | `compatibility_shadow` | company_enrichment.py writes here exclusively |
| Ontology structure | `ontology_edges` | `source_of_truth` | 25 rows, locked |
| Company→area membership | `company_areas` | `source_of_truth` | 136 rows — active, no retirement planned |

### Table-by-Table Classification

| Table | Rows | Classification | Disposition |
|---|---|---|---|
| `drug_targets` | 176 | `source_of_truth` | Permanent |
| `drug_indications` | 246 | `source_of_truth` | Permanent |
| `trial_indications` | 301 | `source_of_truth` | Permanent |
| `drug_competitive_scores` | 234 | `successor_layer` | Becomes source_of_truth when all consumers migrated |
| `area_metadata` | 11 | `source_of_truth` | Permanent governance anchor |
| `drug_areas` | 208 | `compatibility_shadow` | Active for strategic/platform; retire biological reads when C3 migrated |
| `drug_area_scores` | 212 | `compatibility_shadow` + `provenance_archive` | C4–C8 permanent legacy reads; C11 writes here; provenance must never be deleted |
| `company_areas` | 136 | `source_of_truth` | Active company membership; not retiring |
| `disease_areas` | N/A | `deprecated_reference` | Referenced only in Audit tab documentation diagram — no active Supabase queries. Old ontology concept. |
| `ontology_edges` | 25 | `source_of_truth` | Locked. Do not modify without advisor approval |

**Critical finding:** There is currently no authoritative table for strategic views (autoimmune, respiratory) or platform views (tcell). `drug_competitive_scores` stores scores in `strategic_view` and `platform_view` context types, and `drug_areas` stores membership, but no normalized company→strategic_view or company→platform_view relationship table exists.

---

## Section 2 — Legacy Dependency Audit

### A. `drug_areas` Dependencies

| Line | Function/Context | Read/Write | Area scope | Status | Replacement |
|---|---|---|---|---|---|
| 3595–3597 | Area drug list loader (autoimmune/respiratory/tcell tabs?) | READ | all areas | **ACTIVE** — strategic/platform tabs still use this | company_strategic_views (not yet built) |
| 3678–3679 | Secondary area drug fetch | READ | areaId param | **ACTIVE** | Same |
| 9836 | TL1A KDEG area membership | READ | TL1A area | **BYPASSED** — feature flag true | drug_targets(tl1a) |
| 11512 | Drug search area tag lookup | READ | all areas | **ACTIVE** — surfaces area chips on search results | drug_competitive_scores (future) |
| 11676 | C1 drug modal primary (with drug_areas join) | READ | drug_id | **PLANNED MIGRATION** — C1/C2 plan complete | drug_competitive_scores |
| 11717 | C2 drug modal name-fallback | READ | drug_id | **PLANNED MIGRATION** | drug_competitive_scores |
| 12542 | C3 PI tab legacy fallback path | READ | areaIds | **BYPASSED** — feature flags true; code present but branch unreachable | drug_indications/drug_targets |
| 12720–12721 | IBD company membership fetch | READ | ibd area | **BYPASSED** — useNormalizedIBD=true takes IBD branch | drug_indications(uc,cd) |
| 12964–12965 | TL1A KDEG area node source | READ | TL1A | **BYPASSED** — useUnifiedTL1A=true | drug_targets |
| 2313 (enrichment) | Guard E4 upsert | WRITE | area_id | **ACTIVE** — writes drug_areas row before every drug_area_scores write | Remove with C11 parallel-write |

**Net active drug_areas reads:** Lines 3595, 3678 (strategic/platform tabs), 11512 (search area tags). All biological area paths are bypassed by feature flags.

### B. `drug_area_scores` Dependencies

| Consumer | Lines | Classification | Status | Disposition |
|---|---|---|---|---|
| C1 — Drug modal primary | 11677 | `safe_display_consumer` | **PLANNED MIGRATION** — plan written | Migrate to drug_competitive_scores (Session 64) |
| C2 — Drug modal fallback | 11718 | `safe_display_consumer` | **PLANNED MIGRATION** | Same commit as C1 |
| C3 — PI tab scoreRows | 12548 | `behavioral_consumer` | **NOT YET MIGRATED** — HIGH RISK | Migrate after C1 proven ≥7 days |
| C4 — Phase 4B IBD dual-read | 14612 | `legacy_provenance_consumer` | **PERMANENT** — intentional | Never migrate |
| C5 — Phase 4B TL1A dual-read | 14743 | `legacy_provenance_consumer` | **PERMANENT** | Never migrate |
| C6 — Phase 4B TED dual-read | 14837 | `legacy_provenance_consumer` | **PERMANENT** | Never migrate |
| C7 — Phase 4B Atopy dual-read | 14943 | `legacy_provenance_consumer` | **PERMANENT** | Never migrate |
| C8 — Phase 4B FcRn dual-read | 15036 | `legacy_provenance_consumer` | **PERMANENT** | Never migrate |
| C9 — Ontology Audit count | 21143 | `safe_display_consumer` | Hidden dev tab — LOW priority | Migrate when C1 proven |
| C10 — Ontology Audit inspector | 21658 | `safe_display_consumer` | Hidden dev tab; uses `score` field absent from new schema | Migrate when C1 proven; substitute overlap ordering |
| C11 — company_enrichment.py write | 2290–2327 | `write_consumer` | **ACTIVE** — all enrichment writes go here exclusively | Add parallel write after C1 stable ≥7 days |

### C. `company_areas` Dependencies

| Line | Context | Status |
|---|---|---|
| 2159 | Global data load (startup) | **ACTIVE** — used for company tab display |
| 9737 | Company modal area membership | **ACTIVE** |
| 2222 (enrichment) | Guard E3 upsert (pre-company_profiles) | **ACTIVE** |
| 661, 918 (enrichment) | Existing area membership check | **ACTIVE** |

`company_areas` is a healthy active table. No retirement planned.

### D. `disease_areas` Dependencies

Zero active Supabase queries. All 94 matches in index.html are documentation strings inside the Ontology Audit tab diagram (static HTML text, not query calls). `disease_areas` can be considered fully retired from runtime use.

---

## Section 3 — Competitive Score Layer Audit

### Migration Fidelity

| Metric | drug_area_scores | drug_competitive_scores | Delta |
|---|---|---|---|
| Total rows | 212 | 234 | +22 (IBD expansion) |
| Distinct drugs | 106 | 106 | 0 |
| Unmapped rows | — | 0 | ✅ |
| Duplicate UNIQUE keys | — | 0 | ✅ |
| NULL context_type/context_id | — | 0 | ✅ |

### Context Distribution

| context_type / context_id | Rows | Source area_id |
|---|---|---|
| target/tl1a | 50 | tl1a |
| indication/uc | 46 | ibd (expansion) |
| indication/cd | 40 | ibd (expansion) |
| strategic_view/autoimmune | 25 | autoimmune |
| target/tslp | 14 | tslp |
| strategic_view/respiratory | 14 | respiratory |
| indication/ted | 13 | ted + igf1r (deduped) |
| platform_view/tcell | 12 | tcell |
| target/il4ra | 10 | il4ra + atopy (deduped) |
| target/fcrn | 7 | fcrn |
| indication/ibd | 3 | ibd (fallback: epi-001, sim0500, spy072) |

### Fallback Rows — Revised Assessment

**IMPORTANT CORRECTION TO PRIOR PLAN.** The NEXT_SESSION note stated sim0500 and spy072 should be backfilled to UC/CD in drug_indications. Live query disproves this:

```
sim0500: drug_indications.indication_id = 'multiple_myeloma'
spy072:  drug_indications.indication_id = 'ra'
```

Neither drug is an IBD indication drug. Both appear in drug_area_scores(area_id=ibd) for competitive landscape purposes — they are drugs that a BD team following IBD would track — but their primary indications are unrelated. The `indication/ibd` fallback in drug_competitive_scores is **correct** for all three fallback drugs. No backfill is needed or appropriate for sim0500 or spy072.

The three fallback rows are properly classified:
- `epi-001`: indication/ibd — ECC open, evidence gap. Held correctly.
- `sim0500`: indication/ibd — MM indication drug tracked in IBD landscape. Correct fallback.
- `spy072`: indication/ibd — RA indication drug tracked in IBD landscape. Correct fallback.

**Action: Remove the sim0500/spy072 backfill task from NEXT_SESSION. The ibd fallback for these drugs is intentional, not a gap.**

### Consumer Migration Order (confirmed)

1. C1 + C2 (drug modal) — Session 64, plan complete
2. C9 + C10 (Ontology Audit hidden tab) — low priority, anytime after C1
3. C11 parallel-write (enrichment) — after C1 stable ≥7 days
4. C3 (PI tab scoreRows) — after C11 parallel-write is proven; final behavioral consumer

---

## Section 4 — Enrichment System Audit

### Current Write Path

```
company_enrichment.py
  └── per drug per area enrichment run
      ├── drugs (PATCH) — overlap, overlap_rationale, vs_ailux, ailux_angle, etc.
      ├── drug_area_scores (UPSERT) — all area-specific competitive fields
      │     enforces: E4 guard (drug_areas upsert first), E6 guard (confidence constraints)
      ├── drug_areas (UPSERT) — membership guard (E4)
      ├── company_areas (UPSERT) — company membership guard (E3)
      └── company_profiles (UPSERT/PATCH)
```

### Gap: No Write to `drug_competitive_scores`

`drug_competitive_scores` receives **zero** enrichment writes. It is a frozen snapshot from Session 62. Every enrichment run since then adds rows to `drug_area_scores` but not to `drug_competitive_scores`. The two tables are diverging.

**Risk timeline:**
- Today: C1/C2 migration reads from a snapshot that is ~0 days old (just migrated). Acceptable.
- After 7 days: any drug enriched in that window has updated drug_area_scores rows but stale drug_competitive_scores rows. C1/C2 post-migration will show older data.
- After 30 days: divergence becomes meaningful for the most actively-enriched drugs.

**Required action (C11):** Add parallel write to `drug_competitive_scores` in company_enrichment.py. Full design is in `docs/drug_competitive_scores_consumer_inventory.md` (Section 5). Implementation: after C1 stable ≥7 days.

### No Nightly Enrichment Report

`write_meridian.py` runs at 6:30 AM ET and produces `meridian_today.html`. `research.py` runs at 2 AM ET for news intelligence. Neither generates an enrichment outcome report. See Section 8.

---

## Section 5 — Ontology Quality Audit

### Cross-Table Consistency

| Check | Finding |
|---|---|
| drugs.target vs drug_targets | Partially aligned — drugs.target is a legacy free-text field; drug_targets is the authoritative normalized table. Known divergence: legacy field is display-only |
| drugs.indication_short vs drug_indications | Partially aligned — same pattern as above |
| trial_indications vs drug_indications | Wave 3 backfill complete: 301 trial-indication rows cross-referenced to 246 drug-indication rows |
| drug_targets vs drug_competitive_scores targets | Aligned: tl1a(50), il4ra(10), tslp(14), fcrn(7) rows in competitive scores match drug_targets membership |
| drug_indications vs drug_competitive_scores indications | Aligned: uc(46), cd(40), ted(13) rows match drug_indications membership. 3 ibd fallbacks confirmed intentional |

### Open ECC Items (2 of 10 open)

| Entity | Issue | Status |
|---|---|---|
| `epi-001` | `ibd_indication_evidence_gap` | Open — held deliberately; no backfill without source evidence |
| `cizutamig` | `ted_indication_scope_review` | Open — new item since last audit |

`cizutamig` + TED is a new ECC item not seen in recent sessions. Should be reviewed in the next session before C1/C2 implementation: determine whether cizutamig belongs in drug_indications(ted) or drug_competitive_scores(indication/ted).

### `drug_validation_results`

The table returns HTTP 400 on anon key access (RLS policy blocking). Service key is also returning 400, suggesting the table may have a column type issue or the query filter syntax needs adjustment. Unable to pull failure list in this session. **Action:** Investigate drug_validation_results RLS at session start.

---

## Section 6 — Area Governance Audit

### Full Classification (from area_metadata live state)

| area_id | lifecycle_state | category | retirement_status | Runtime source | Can archive now? | Notes |
|---|---|---|---|---|---|---|
| `ibd` | redirected | ontology_biological | legacy_retained | drug_indications(uc,cd) | No — C4 permanent, C11 write dependency | Dashboard reads: bypassed |
| `igf1r` | redirected | ontology_biological | legacy_retained | drug_indications(ted) | No — C4–C8 provenance | Deduped into ted in drug_competitive_scores |
| `ted` | redirected | ontology_biological | legacy_retained | drug_indications(ted) | No — same | TED tab reads drug_indications |
| `tl1a` | redirected | ontology_biological | legacy_retained | drug_targets(tl1a) | No — C5 permanent | TL1A tab reads drug_targets |
| `il4ra` | redirected | ontology_biological | legacy_retained | drug_targets(il4ra) | No — C7 permanent | IL-4Rα tab reads drug_targets |
| `tslp` | redirected | ontology_biological | legacy_retained | drug_targets(tslp,tslpr) | No — C7 permanent | TSLP tab reads drug_targets |
| `atopy` | redirected | ontology_biological | legacy_retained | drug_targets(il4ra,tslp,tslpr) | No — C7 permanent | Collapsed into il4ra/tslp in drug_competitive_scores |
| `fcrn` | redirected | ontology_biological | flag_activated | drug_targets(fcrn) | No — C8 permanent | FcRn tab reads drug_targets |
| `autoimmune` | preserved_curated | curated_strategic | not_started | drug_areas(autoimmune) | No — no replacement table | Needs company_strategic_views |
| `respiratory` | preserved_curated | curated_strategic | not_started | drug_areas(respiratory) | No — no replacement table | Needs company_strategic_views |
| `tcell` | preserved_platform | curated_platform | not_started | drug_areas(tcell) | No — no replacement table | Needs company_platform_views |

**Key governance observation:** area_metadata correctly documents that autoimmune, respiratory, and tcell are `not_started` for retirement. These cannot be retired until the replacement tables exist.

---

## Section 7 — Strategic and Platform View Audit

### Current State

`drug_competitive_scores` already stores scores for strategic/platform contexts:
- `strategic_view/autoimmune`: 25 rows
- `strategic_view/respiratory`: 14 rows
- `platform_view/tcell`: 12 rows

`drug_areas` still stores drug membership:
- autoimmune: 25 rows
- respiratory: 14 rows
- tcell: 11 rows

`company_areas` stores company→area membership (used in company modal, line 9737).

### Missing: No Company-Level Strategic/Platform Tables

The design doc (`docs/drug_competitive_scores_design.md`) references `company_strategic_views.view_id` and `company_platform_views.platform_id` as FK targets for `context_id` in `drug_competitive_scores`. Neither table exists in Supabase.

**Impact today:** The `context_id` column for strategic_view/platform_view rows currently references view_id values (`autoimmune`, `respiratory`, `tcell`) without a foreign key enforced. The data is correct but lacks the governance table behind it.

### Dashboard Reads for Strategic/Platform Views

Lines 3595–3597 in index.html fetch drugs from `drug_areas` for these views. `company_areas` (line 9737) drives the company modal area membership display. Both are currently served by legacy tables with no normalized replacement.

### Proposed Schema (WS4 — not yet started)

```sql
-- company_strategic_views
CREATE TABLE company_strategic_views (
  id            SERIAL PRIMARY KEY,
  company_id    TEXT NOT NULL REFERENCES companies(id),
  view_id       TEXT NOT NULL,   -- 'autoimmune', 'respiratory'
  view_label    TEXT,
  sourced_by    TEXT,
  UNIQUE(company_id, view_id)
);

-- company_platform_views
CREATE TABLE company_platform_views (
  id            SERIAL PRIMARY KEY,
  company_id    TEXT NOT NULL REFERENCES companies(id),
  platform_id   TEXT NOT NULL,   -- 'tcell'
  platform_label TEXT,
  sourced_by    TEXT,
  UNIQUE(company_id, platform_id)
);
```

**Drug membership for strategic/platform:** Derived from `drug_competitive_scores` (strategic_view or platform_view context type). No separate drug membership table needed — it's implicit from the competitive score.

**Company membership for strategic/platform:** Currently in `company_areas` keyed on area_id. The migration path is to populate `company_strategic_views`/`company_platform_views` from the same source, then retire the `company_areas` rows for these three area_ids. This is WS4.

---

## Section 8 — Nightly Reporting Audit

### Current Reporting State

`write_meridian.py` runs at 6:30 AM ET: generates `meridian_today.html` (news/signal digest). This is a product output, not an enrichment health report.

`research.py` runs at 2 AM ET: fetches news, surfaces intel, triggers signal processing. No structured output log of what was enriched, what was skipped, or what validation checks ran.

No nightly enrichment report exists.

### Recommended Design

A lightweight enrichment report should be generated by `company_enrichment.py` as a structured JSON output after each run:

```json
{
  "run_id": "enrich-20260526-tl1a",
  "area_id": "tl1a",
  "ts": "2026-05-26T14:00:00Z",
  "drugs_enriched": 3,
  "drugs_skipped": 47,
  "drugs_failed": 0,
  "records_created": {"drug_area_scores": 1, "drug_areas": 0, "company_areas": 0},
  "records_updated": {"drugs": 3, "drug_area_scores": 2},
  "confidence_distribution": {"A": 1, "B": 2, "inferred": 0},
  "validation_flags": [],
  "ecc_candidates": [],
  "skipped_reasons": {"already_validated": 44, "no_llm_output": 3}
}
```

This JSON can be appended to an `enrichment_runs` table (already referenced as `enrichment_run_id` in `drug_competitive_scores`). **Implementation:** Add structured run logging to `company_enrichment.py` as a post-run step. Low effort, high visibility. Recommended for WS4.

---

## Section 9 — Backend Completion Gate

### Current Status per Gate

| Gate | Criterion | Status |
|---|---|---|
| G1 | All biological dashboard reads use ontology tables | ✅ All 7 surfaces (IBD, TED, TL1A, IL-4Rα, TSLP, FcRn, Drug Modal) — feature flags all true |
| G2 | drug_competitive_scores is populated and validated | ✅ 234 rows, 0 unmapped, 0 duplicates, all spot-checks pass |
| G3 | drug_area_scores display consumers are migrated or formally retained | ⏳ C1/C2 planned; C3 pending; C4–C8 formally retained as provenance |
| G4 | No scripts write only to legacy tables | ❌ company_enrichment.py writes exclusively to drug_area_scores — no parallel write yet |
| G5 | area_metadata documents every area_id | ✅ 11/11 area_ids classified |
| G6 | Strategic/platform concepts have a defined backend home | ⏳ Scores in drug_competitive_scores, but company_strategic_views / company_platform_views not built |
| G7 | entity_consistency_checks has no open high-severity items | ⚠ 2 open: epi-001 (known, held), cizutamig (new — needs review) |
| G8 | Wave 3 validation passed | ✅ 246 drug-indication rows, Wave 3 complete |
| G9 | Retirement/archival plan is documented | ✅ area_metadata + consumer_inventory + C1/C2 plan |
| G10 | Frontend work can resume safely | ⚠ Conditionally yes — see recommendation |

Gates clear: G1, G2, G5, G8, G9 — 5/10
Gates partial: G3, G6, G7 — 3/10
Gates failed: G4 — 1/10

---

## Final Output

### 1. Current Integration Status: **Advanced Partial**

The biological dashboard is fully ontology-backed (G1 complete). The competitive intelligence layer is built and validated. Area governance is documented. The platform is structurally sound. What's missing is the final mile: wiring consumers to the new table, getting writes to flow to both tables simultaneously, and building the two missing governance tables for strategic/platform views.

### 2. Evidence

- 7 biological surfaces now read from drug_targets / drug_indications (all 6 feature flags = true)
- 234 drug_competitive_scores rows covering 106 drugs across 11 context/id combinations
- 11/11 area_ids classified in area_metadata
- 246 drug_indications rows (Wave 3 complete)
- 301 trial_indications rows
- 2 open ECC items (down from higher counts earlier in the project)

### 3. Remaining Backend Gaps

| Gap | Severity | Estimated effort |
|---|---|---|
| C11 parallel-write: company_enrichment.py doesn't write drug_competitive_scores | HIGH — tables diverging | 1 session |
| C1/C2 consumer migration | MEDIUM — plan complete, needs implementation | 1 session |
| C3 PI tab behavioral consumer migration | HIGH complexity, MEDIUM urgency | 2–3 sessions |
| company_strategic_views / company_platform_views schema | MEDIUM — autoimmune/respiratory/tcell still legacy | 1–2 sessions |
| cizutamig/ted ECC review | LOW-MEDIUM | <1 session |
| drug_validation_results query access (400 error) | LOW | Investigate at session start |
| Enrichment run logging | LOW | 1 session |

### 4. Risk Ranking

| Risk | Probability | Impact |
|---|---|---|
| Enrichment drift: drug_competitive_scores becomes stale as drug_area_scores is enriched | HIGH (happening now) | MEDIUM (C1/C2 shows slightly old data post-migration) |
| C3 regression: PI tab scoring breaks during migration | MEDIUM | HIGH (breaks core competitive view) |
| cizutamig/ted ECC: may indicate a TED indication gap | LOW | LOW (single drug) |
| company_strategic_views missing: autoimmune/respiratory/tcell tabs continue on legacy table | LOW near-term | MEDIUM long-term (blocks WS4 frontend work) |
| drug_validation_results inaccessible | LOW | LOW (monitoring gap, not data gap) |

### 5. Recommended Next Phase

**Phase 6 completion order:**

1. **Session 64 (immediate):** C1/C2 implementation + _confBadge fix + dual-read harness + 10-drug validation. Also: investigate cizutamig/ted ECC. Investigate drug_validation_results 400.
2. **Session 65–66:** C11 parallel-write to drug_competitive_scores in company_enrichment.py. Monitor enrichment drift window.
3. **Session 67:** C3 PI tab migration (behavioral consumer — highest risk; do after C11 is proven).
4. **Session 68–69:** WS4 — company_strategic_views + company_platform_views DDL + migration from company_areas.

Frontend work can run in parallel starting Session 64 within the following scope constraint: **Drug Card upgrade is safe.** The drug card reads from tables that are either fully migrated (drug_targets, drug_indications) or being migrated in Session 64 (drug_competitive_scores via C1/C2). The PI tabs and competitive landscape views require C3 migration first.

### 6. Concrete Implementation Plan

```
Session 64:
  backend:  C1/C2 migration + _confBadge fix + dual-read harness
  backend:  cizutamig ECC review
  backend:  drug_validation_results RLS investigation
  frontend: Sprint 1 drug card — ailux_angle + overlap tier display (already migrated)

Session 65:
  backend:  C11 parallel-write to drug_competitive_scores in company_enrichment.py
  frontend: Sprint 1 drug card — catalyst timeline + competitive cluster

Session 66:
  backend:  C11 monitoring + verification (≥7 days since C1)
  frontend: Sprint 1 drug card — ownership chain + confidence indicator

Session 67:
  backend:  C3 PI tab consumer migration (behavioral, HIGH risk)
  frontend: Sprint 2 — homepage intelligence feed

Session 68:
  backend:  WS4 — company_strategic_views + company_platform_views DDL
  backend:  Migrate company_areas(autoimmune/respiratory/tcell) to new tables
  frontend: Sprint 2 continuation
```

### 7. Files That Need Modification

| File | Change needed | Session |
|---|---|---|
| `index.html` | _confBadge fix + C1/C2 fetch swap + _CEM_AMAP uc/cd + dual-read harness | 64 |
| `index.html` | C3 PI tab scoreRows → drug_competitive_scores | 67 |
| `scripts/company_enrichment.py` | Add parallel write block to drug_competitive_scores after P1-D | 65 |

### 8. Supabase Tables That Need Modification

| Table | Change needed | Session |
|---|---|---|
| `drug_competitive_scores` | Ongoing — entries added via C11 parallel-write | 65 |
| `company_strategic_views` | CREATE TABLE — new | 68 |
| `company_platform_views` | CREATE TABLE — new | 68 |
| `drug_indications` | Potentially: cizutamig/ted entry (pending ECC review) | 64 |

### 9. Scripts That Need Modification

| Script | Change needed | Session |
|---|---|---|
| `company_enrichment.py` | Add parallel write to drug_competitive_scores (C11) | 65 |
| `company_enrichment.py` | Future: remove drug_area_scores write (after all consumers migrated) | Session 70+ |

### 10. Tests That Must Pass Before Backend Alignment is Called Complete

```
T1: drug_competitive_scores row count ≥ drug_area_scores row count
T2: No active production consumers reading drug_area_scores for display (C4–C8 exempt as provenance)
T3: company_enrichment.py writes to drug_competitive_scores on every enrichment run
T4: area_metadata.retirement_status = 'migration_complete' for all 8 biological areas
T5: company_strategic_views and company_platform_views tables exist with correct FK structure
T6: entity_consistency_checks has zero open items rated HIGH severity
T7: drug_validation_results accessible with zero fail-status rows (excluding known pre-approved gaps)
T8: All 6 feature flags remain true (no regression)
```

### 11. Frontend Readiness Recommendation

**Frontend work can resume now with scoped constraints.**

**Safe to build in Sprint 1 (Drug Card):**
- `ailux_angle`, `overlap`, `overlap_rationale` — all on `drugs` table, fully enriched
- `catalysts` — 786 rows, direct drug_id FK
- `drug_targets` — source of truth, 176 rows
- `drug_indications` — source of truth, 246 rows
- `companies`, `partnerships` — active, no retirement planned

**Wait for Session 64 before building:**
- Drug modal competitive context display (reads drug_competitive_scores — C1/C2 going live in Session 64)

**Wait for Session 67 before building:**
- PI tab competitive landscape features (reads drug_area_scores via C3 — pending migration)

**Wait for Session 68 before building:**
- Any feature that groups by strategic view (autoimmune/respiratory) or platform view (tcell) at the company level

The drug card upgrade is the correct first sprint. It uses tables that are either already migrated or being migrated this session. **Frontend work should proceed in parallel with C11 (enrichment parallel-write) rather than waiting for it.**

---

*Prepared Session 63 — 2026-05-26. No data modified.*
