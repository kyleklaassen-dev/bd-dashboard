# Phase 6 Master Plan — Meridian Architecture Evolution
**Written:** Session 58 — 2026-05-26  
**Status:** Advisor-directed architecture plan — for review before execution  
**Context:** Generated after completing the Session 58 ontology governance mega-sprint (Tracks B–F), which produced the blueprint for this transition.

---

## Framing

The Phase 5 identity program is complete. The ontology migration queue is 80–90% done architecturally. The remaining work is not "move another area from A to B."

The next inflection point is:

> Converting Meridian from **ontology tables + legacy intelligence tables** into **ontology layer + strategic views layer + competitive intelligence layer**.

The governance sprint proved that `drug_areas` is replaceable. `drug_area_scores` is not — not yet. That asymmetry defines the entire Phase 6 agenda.

---

## Current State (as of 2026-05-26)

```
┌─────────────────────────────────────────────────┐
│  ONTOLOGY LAYER (normalized, partially complete) │
│  drug_targets       173 rows, 37 targets         │
│  drug_indications   197 rows, 17 indications     │
│  trial_indications  301 rows (more complete)     │
└────────────────────┬────────────────────────────┘
                     │ serves
┌────────────────────▼────────────────────────────┐
│  LEGACY MEMBERSHIP LAYER (being retired)         │
│  drug_areas         208 rows, 11 area_ids        │
│  drug_area_scores   212 rows (intelligence ↓)   │
│  company_areas      136 rows                     │
└─────────────────────────────────────────────────┘
```

**Three problems with this state:**

1. `drug_areas` is a redundant membership table — ontology tables now serve membership
2. `drug_area_scores` is architecturally orphaned — it stores the most valuable BD intelligence (overlap classification, competitive rationale) but is tied to a legacy concept (`area_id`)  
3. Strategic concepts (autoimmune, respiratory, tcell) have no home once `drug_areas` is gone

---

## Target State (end of Phase 6)

```
┌─────────────────────────────────────────────────────┐
│  ONTOLOGY LAYER (normalized, comprehensive)          │
│  drug_targets       ~180+ rows, complete coverage    │
│  drug_indications   ~244+ rows (Wave 3 added)        │
│  trial_indications  ~340+ rows                       │
└──────────────┬──────────────────┬───────────────────┘
               │                  │
┌──────────────▼────────┐  ┌──────▼──────────────────┐
│  STRATEGIC VIEWS LAYER│  │  INTELLIGENCE LAYER      │
│  company_strategic_   │  │  drug_competitive_scores │
│  views                │  │  (replaces               │
│  company_platform_    │  │   drug_area_scores)      │
│  views                │  │                          │
└───────────────────────┘  └──────────────────────────┘
```

**What this enables:**

- Any question about drug biology → answered from ontology layer
- Any question about competitive position → answered from intelligence layer  
- Any question about strategic landscape → answered from strategic views layer
- `drug_areas`, `drug_area_scores`, `company_areas` retired and archived

---

## Workstream 1 — Finish Runtime Migration Queue

**Goal:** Complete C5/C6/C7 activations. Close out the feature-flag migration program.

**Remaining work:**

| Candidate | Status | Blocking issue |
|-----------|--------|---------------|
| C5 TSLP | Code deployed (flag=false, commit 089819dd) | GitHub Pages/Actions degraded — CDN not serving new code |
| C6 IL-4Rα | Bundled with C5 (useUnifiedAtopy) | Same blocker |
| C7 FcRn | Audit complete, code not yet written | Need to add `useUnifiedFCRN` flag + _makeAreaPI source swap |

**C5/C6 activation procedure** (when Pages recovers):
```bash
# Step 1: Check status
curl -s "https://www.githubstatus.com/api/v2/components.json" | python3 -c "import json,sys; [print(f\"{c['name']}: {c['status']}\") for c in json.load(sys.stdin)['components'] if any(k in c['name'].lower() for k in ['actions','pages'])]"
# Step 2: If operational — deploy → G6 → G7 → advisor go → activate flag=true
```

**C7 implementation steps** (can be done while Pages degraded):
1. Add `useUnifiedFCRN: false` to FEATURE_FLAGS in index.html
2. Add `_FCRN_NORM = !!(FEATURE_FLAGS.useUnifiedFCRN && this.areaIds.includes('fcrn'))` to `_makeAreaPI().init()`
3. Add `_FCRN_NORM` branch to ternary precedence chain
4. Build `_runPhase4BFCRNDualRead()` method — pattern from `_runPhase4BTL1ADualRead()`
5. 8-gate browser validation → advisor approval → set `useUnifiedFCRN=true` → deploy

**Known issue — riliprubart:** `drugs.target = 'C1q complement'` is stale. Must update to 'FcRn' at C7 activation.

**Session estimate:** 1–2 sessions (1 for C5/C6 when Pages recovers, 1 for C7)

**Exit criteria:** All 7 feature flags = `true`. drug_areas no longer serves any tab membership query.

---

## Workstream 2 — Wave 3 Ontology Coverage Expansion

**Goal:** Elevate `drug_indications` from "primary indications only" to "comprehensive clinical program coverage."

**The gap:** 47 drug-indication pairs exist in `trial_indications` but not in `drug_indications` — covering 34 drugs. These represent real clinical programs that are invisible to the ontology-based dashboard queries.

**Priority tier 1 (5+ pairs per drug):**
- `iscalimab` (CD40, Phase 2): gmg, hs, ra, sjogrens, sle — 5 missing

**Priority tier 2 (2–4 pairs per drug):**
- `lutikizumab` (IL-1α/β, Phase 3): ad, hs, uc
- `imvt-1402` (FcRn, Phase 3): ra, ted
- `astegolimab` (IL-33, Phase 3): ad, asthma
- `infliximab` (TNFα, Approved): cd, ra
- `ianalumab` (BAFF-R, Phase 3): ra, sjogrens
- `afimkibart` (TL1A, Phase 3): ad, cd
- `zumilokibart` (IL-13, Phase 2): asthma, crswnp
- `itepekimab` (IL-33, Phase 3): asthma, crswnp

**Priority tier 3 (1 pair per drug):**
25 additional drugs with single indication gaps — see ECC-7 full list in `docs/ontology_consistency_sweep.md`.

**Indication themes requiring systematic backfill:**
| Indication | Gaps | Key drugs needing backfill |
|------------|------|---------------------------|
| `crswnp` | 8 drugs | tezepelumab, itepekimab, zumilokibart, verekitug, omalizumab, tralokinumab, rademikibart, win378 |
| `hs` | 6 drugs | iscalimab, bimekizumab, sonelokimab, lutikizumab, secukinumab, abbv-668 |
| `ra` | 8 drugs | iscalimab, infliximab, ianalumab, cnd261, ixekizumab, golimumab, upadacitinib, imvt-1402 |
| `asthma` | 6 drugs | astegolimab, itepekimab, zumilokibart, rocatinlimab, win378, tralokinumab |
| `ad` | 4 drugs | lutikizumab, astegolimab, afimkibart, apg777 |

**Also needed — two drugs.target field corrections (ECC-1 P0):**
- `apg333`: set `drugs.target = 'TSLP'`
- `rocatinlimab`: set `drugs.target = 'OX40L'` (currently 'OX40')

**Wave 3 deliverables:**
1. `scripts/wave3_drug_indications_backfill.py` — systematic backfill using trial_indications as source of truth
2. 47 new `drug_indications` rows committed
3. 2 `drugs.target` field corrections applied
4. Re-run ontology consistency sweep — verify 0 ECC-7 gaps remain

**After Wave 3:** drug_indications has ~244 rows (+47) covering substantially all drugs with active clinical programs.

**Session estimate:** 1–2 sessions

---

## Workstream 3 — Competitive Intelligence Layer Normalization

**Goal:** Design and build `drug_competitive_scores` as the explicit, normalized replacement for `drug_area_scores`. This is the largest remaining architectural project.

**Why it matters:** `drug_area_scores` currently stores the output of every enrichment run — Claude's competitive assessments. It contains overlap classification, rationale text, confidence levels, source URLs. This is the intelligence that makes Meridian a BD tool rather than a drug database. Without a normalized replacement, drug_area_scores cannot be retired.

**The design problem:** `drug_area_scores` uses `area_id` as the context key — but `area_id` is a legacy concept. The new architecture has three context types:
- Target-based (e.g., "how competitive is drug X in the TL1A space?")
- Indication-based (e.g., "how competitive is drug X in UC?")
- Strategic view-based (e.g., "is drug X part of the autoimmune landscape?")

**Proposed schema:** See `docs/drug_competitive_scores_design.md` for full specification.

**Migration procedure:**
1. Create `drug_competitive_scores` table
2. Build migration script: `drug_area_scores` rows → `drug_competitive_scores` rows (map area_id → context_type + context_id)
3. Update all 8 consumers (dashboard + scripts) to read from new table
4. Run parallel reads (old + new) to validate parity
5. Deprecate `drug_area_scores` writes in enrichment pipeline
6. Freeze `drug_area_scores` as read-only historical record
7. After monitoring window: drop `drug_area_scores`

**Consumers that must be migrated:**
| Consumer | Type | Migration complexity |
|----------|------|---------------------|
| Drug modal overlap display | Dashboard (C3 active) | Medium — update query selector |
| PI tab drug card badges | Dashboard | Medium — per-tab context lookup |
| Audit tab scoring | Dashboard | Low — display only |
| company_enrichment.py | Backend script | HIGH — writes enrichment output |
| compute_landscape_coverage.py | Backend script | Medium — rewrite calculations |
| research_intelligence.py | Backend script | Medium — rewrite area discovery |
| seed_preclinical_competitors.py | Backend script | HIGH — writes new drug scores |
| audit_sources.py | Backend script | Low — read-only audit |

**Session estimate:** 5–8 sessions. This is the largest remaining engineering milestone.

**Key insight from advisor:** This is where Meridian becomes a true intelligence platform — when competitive assessments have explicit provenance chains (drug → target → indication → strategic view → score → rationale → source).

---

## Workstream 4 — Strategic Views Architecture

**Goal:** Give autoimmune, respiratory, and tcell concepts a proper home as first-class BD intelligence products — not legacy database rows.

**The reframing:** These aren't ontology entities. They are strategic lenses:
- **Autoimmune Landscape** — cross-mechanism view of companies competing in broad autoimmune
- **Respiratory Landscape** — airway disease competitors across TSLP/IL-13/IL-33/IL-5 mechanisms
- **T-cell Ecosystem** — platform capability map (CAR-T, T-cell engagers, CD3 bispecifics)

**Schema:** See `docs/strategic_views_architecture.md` for full specification.

**Build order:**
1. Create `company_strategic_views` and `company_platform_views` tables (SQL migration)
2. Seed from existing `drug_areas` + `company_areas` data  
3. Migrate `ace` tab (tcell) — 8-gate validation required (only active tab without redirect)
4. Retire `drug_areas` and `company_areas` rows for autoimmune/respiratory/tcell
5. Build Strategic Landscape Panel in dashboard (first-class UI surface)

**The BD product opportunity:** Strategic views become navigable landscape products:
- "Show me all companies in the FcRn Leaders view" 
- "Which companies have both a T-cell therapy platform AND an autoimmune program?"
- "Who entered the respiratory landscape in the last 18 months?" (via catalyst tagging)

This is qualitatively different from the PI tabs — it's BD strategic intelligence at the portfolio level, not the drug level.

**Session estimate:** 3–4 sessions (schema + seed + tab migration + landscape panel)

---

## Drug Areas Retirement Roadmap

| Phase | What Gets Retired | Gate |
|-------|------------------|------|
| **5.3** (now) | drug_areas rows for tl1a/ibd/igf1r (already redirected) | Monitor windows close: IBD/TED ~2026-06-08, TL1A ~2026-06-24 |
| **5.3** | drug_areas rows for atopy/il4ra/tslp | After C5/C6 activation |
| **5.3** | drug_areas rows for fcrn | After C7 activation |
| **5.4** | drug_areas rows for autoimmune/respiratory | After company_strategic_views seeded + validated |
| **5.4** | drug_areas rows for tcell | After company_platform_views + ace tab migration validated |
| **5.6** | drug_areas rows for ted | After reconciliation audit (iscalimab gap resolved) |
| **5.4** | company_areas rows (all areas) | Parallel with drug_areas Phase 5.4 |
| **5.3–5.4** | drug_areas table itself | After all rows deleted — can DROP TABLE |
| **6.x** | drug_area_scores rows | After drug_competitive_scores migration complete + monitoring window |
| **6.x** | drug_area_scores table itself | After all consumers migrated — can DROP TABLE |

**What must be preserved indefinitely:** The competitive assessment data itself (overlap, rationale, confidence). These must be migrated to `drug_competitive_scores`, not deleted.

---

## Session Sequence and Dependency Map

```
IMMEDIATE (can start while GitHub Pages degraded)
├── Wave 3 enrichment (WS2): 47 drug-indication gaps → 1–2 sessions
├── C7 implementation (WS1): code only, flag=false → 1 session
└── drug_competitive_scores design + SQL migration → 1 session

WHEN PAGES RECOVERS
├── C5/C6 activation (WS1): G6 → G7 → advisor → flag=true → 1 session
└── C7 browser validation (WS1): after code deployed → 1 session

AFTER WS1 COMPLETE (C5/C6/C7 all active)
├── drug_areas batch retirement (Phase 5.3): delete ibd/tl1a/igf1r/atopy/il4ra/tslp/fcrn → 1 session
├── Begin company_strategic_views seeding (WS4) → 1 session
└── Begin drug_competitive_scores consumer migration (WS3) → multi-session

AFTER STRATEGIC VIEWS SEEDED
├── ace tab migration 8-gate validation → 1 session
├── drug_areas Phase 5.4 retirement (autoimmune/respiratory/tcell/company_areas) → 1 session
└── Continue WS3 consumer migration → multi-session

AFTER ALL CONSUMERS MIGRATED (WS3 complete)
└── drug_area_scores freeze + eventual DROP → 1 session
```

**Total estimated session count:**
- WS1 (remaining): 2–3 sessions
- WS2 (Wave 3): 1–2 sessions  
- WS3 (drug_competitive_scores): 5–8 sessions
- WS4 (strategic views): 3–4 sessions
- Retirement + cleanup: 2–3 sessions
- **Total: ~14–20 sessions to complete Phase 6**

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| GitHub Pages remains degraded | Medium | Medium — delays C5/C6 only | Work WS2/WS3/C7-code in parallel |
| drug_competitive_scores migration breaks enrichment pipeline | Medium | High — enrichment writes stop | Parallel-write period (both tables) before cutting over |
| ace tab (tcell) 8-gate validation fails | Low | Medium — tcell tab breaks | Rollback: flag=false |
| Wave 3 backfill introduces wrong indications | Low | Medium — false drug-indication pairs | trial_indications as source of truth; confidence_score threshold |
| consumer inventory incomplete (missed a drug_area_scores reader) | Medium | Low — display bugs | Comprehensive grep + browser test |
| Strategic views architecture needs redesign | Low | Medium — adds sessions | Design doc reviewed before SQL migration |

---

## Priority Queue (What to Build Next)

**Session 59 (immediate — no Pages needed):**
1. P0 ECC fixes: `apg333.target='TSLP'`, `rocatinlimab.target='OX40L'`
2. Wave 3 Wave A backfill: iscalimab (5 rows) + lutikizumab (3) + imvt-1402 (2) + astegolimab (2) — top 9 rows
3. C7 code implementation: `useUnifiedFCRN=false`, source swap in `_makeAreaPI()`, `_runPhase4BFCRNDualRead()`

**Session 60:**
1. Wave 3 Wave B: remaining 38 drug-indication pairs
2. C5/C6 activation (if Pages recovers) OR continue WS3 planning

**Session 61:**
1. drug_competitive_scores SQL migration — create table + seed script
2. C7 browser validation + activation (if deployed)

**Sessions 62–68:**
1. drug_competitive_scores consumer migration (per consumer, one session each)
2. company_strategic_views + company_platform_views schema + seeding
3. ace tab migration
4. drug_areas batch retirement (Phase 5.3 + 5.4)
