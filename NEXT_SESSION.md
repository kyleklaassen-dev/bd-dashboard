# 🔧 WRITERS HARDENED (Phase 3 prereq DONE, 2026-06-16)

Single-writer **code layer is now complete + verified**. All 4 writers exist in `src/database/` (DrugWriter was already live). Found+fixed real bugs in 2:
- **EdgeWriter**: allowed only 13 predicates / 6 node types — would have REJECTED TESTED_IN (326), PRESENTED (442), CO_AUTHORED_WITH (4,979), MANUFACTURES, INVESTIGATES (1,808), and all abstract/author/kol/trial/patent edges. Expanded to the full **35 predicates / 18 node types** in the live graph. Verified: TESTED_IN/PRESENTED now accepted, bad predicate + missing node still rejected.
- **CatalystWriter**: still required drug/company only — out of sync with the broadened v160 `must_link`. Aligned to drug/company/**area/target/indication**. Verified area-anchored now passes.
- CompanyWriter verified OK (defaults subsidiary; rejects acquired-without-parent). All py_compile + dry-run smoke tests green.

**NEXT increment (the actual de-bulking):** wire the writers into the seeders/enrichers — route the ad-hoc `sb_upsert('entity_edges'/'catalysts'/'companies', …)` calls through Edge/Catalyst/CompanyWriter (start with the edge seeders — lowest risk, highest call-count). Each wiring de-bulks the script AND completes single-writer at the code layer (DB layer already enforces via v157–v162). Then the ct_gov_sync split per `docs/architecture/PHASE3_4_EXECUTION_DESIGN.md`.

NOTE: the Supabase **Management API** had a transient 504 outage around 12:25–12:30 UTC (Cloudflare); the project **REST endpoint stayed up** the whole time, so this work used REST. If DDL/migrations error with 504, just retry.

---

# ✅ EXECUTED OVERNIGHT (after the morning-review audit, 2026-06-16)

Kyle approved all 3 decisions + P1–P3. Done since the audit:
- **Governance 3 → 0.** Hard-deleted the 9 dropped records (off-domain oncology + phantoms incl. nvx-360/calt-100; full ref cleanup, 0 orphans, drugs 189→180). China stage flags resolved: GB-3250/generate-uc Phase 3→Preclinical (no trial evidence); LBL-053 already Preclinical (flag stale). ab001/sm-101 acknowledged (by-design ambiguous-identity).
- **P1:** 5 well-known mechanisms backfilled (certolizumab-pegol/etanercept/etrasimod/tildrakizumab/tofacitinib); SHR-1905→Hengrui; dispatched company-enrichment (firmographics — 58 country/strategic-value gaps, running in CI), evidence-collectors + refresh-company-verified (both green).
- **P2/P3:** delivered a code-validated execution design — `docs/architecture/PHASE3_4_EXECUTION_DESIGN.md` — for the ct_gov_sync split and the index.html first extractions. NOT executed live: the mount can't integration-test a 1,400-line refactor of a core pipeline mid-run; the design makes a focused session fast + safe.
- **Deferred (note):** canonicalize sl325/sl425/sl846 (needs entity_matcher in CI); 7 deal source_url backfills.

**Morning decisions left:** none blocking. Optional: review the 10 submitted_intel `needs_review` items; pick a focused session to execute the Phase 3 ct_gov_sync split (design ready).

---

# ☀️ MORNING REVIEW READY (2026-06-16 overnight)

Read **`docs/audits/MORNING_REVIEW_2026-06-16.md`** first. TL;DR: DB healthy (0 orphans/dups/validation-fails), enforcement live (4 rules + Layer B), engine green, governance 41→3, submitted-intel now 4-hourly (10 items in needs_review for you). Batch self-verified; 2 over-removed trial links were caught and restored. 3 decisions await you (see audit §3): hard-delete vs keep the 8 reversibly-dropped records; purge nvx-360/calt-100?; China-CDE check for generate-uc/lbl-053. Next-steps roadmap in audit §4 (quick data fixes → company firmographics → Phase 3 modularization).

---

# NEXT_SESSION — addendum (2026-06-16 PM, Stage 4 DONE)

Continued from the entry below. **Single-writer enforcement is now REAL (channel + invariant); the freeze can lift.**

## Added this block
- **Catalysts:** linked 17/26 unlinked catalysts to a specific drug/company; the other 9 are area-anchored (their company isn't in the DB yet — Denali/Odyssey/Abivax/NewLimit). Found+fixed one true duplicate (3124/3125 ATI-052, shared default sort_date). `migrations/v160` broadens `catalysts.must_link` to "drug OR company OR area" and **enforces** it.
- **Layer B (`migrations/v161`):** REVOKE INSERT/UPDATE/DELETE/TRUNCATE on drugs/companies/catalysts/entity_edges from anon+authenticated. Discovery: anon previously had FULL write on all core tables (could rewrite any field) + an `anon_update_drugs_partnership` RLS policy used by the dashboard partnership-pill (index.html ~L21171). Kept that feature via a column-scoped `GRANT UPDATE (partnership_verified, partner_company) ON drugs TO anon`. Verified: anon writing `mechanism` → 401; anon INSERT company → 401; pill toggle → 204; service_role/writers unaffected.
- **apg TARGETS edges re-synced:** apg777→`il13` only; apg279→`il13`+`ox40l` (were il4ra/ox40l from the pre-correction target).
- **drug_sources backfill:** missing-source drugs 20→11 (promoted 9 drugs' existing `source_url` into `drug_sources`); dispatched evidence-collectors for the rest. The 11 remaining are the known obscure code-named assets (resolve as they disclose).
- **Startup reliability:** fixed CLAUDE.md + README on `main` (stale `BD Platform` path → bd-dashboard; dead `.github_token` → `.github_token_workflow`) and corrected the memory-index paths.

## Now-open (not freeze-blocking) — see PRIORITY.md
1. Drug-discovery `company_id` policy → then enforce `drugs.company_id_required` (12 company-less code drugs).
2. Add Denali/Odyssey/Abivax/NewLimit companies → link the 9 area-only catalysts.
3. Optional: route the partnership-pill write through an RPC and drop the anon column grant.

---

# NEXT_SESSION — handoff (2026-06-16, Stage 4 enforcement ON)

**Session goal:** turn on Stage 4 single-writer enforcement and clear the Stage 1 residual data fixes. Both done (enforcement is partial-by-design). Operated on LIVE `main` + Supabase via the GitHub/Management APIs (git still deadlocks on the mount; key in `.github_token_workflow`).

## What got done
1. **Stage 4 WARN → EXCEPTION.**
   - `migrations/v157_writer_enforcement_warn.sql` — observe-only BEFORE INSERT/UPDATE triggers on drugs/companies/catalysts/entity_edges, logging every invariant breach to **`governance_enforcement_log`** (REST-queryable). Mode switch in `governance_enforcement_config`.
   - Watched a live write cycle (completeness-scoring, stock-prices, free-ingest, structural-edges) → only soft `brand_implies_approved` warnings, **zero hard violations**.
   - `migrations/v159_writer_enforcement_escalate.sql` — **per-rule** enforcement allow-list `governance_enforced_rules`. The two edge referential rules (`edges.subject_drug_orphan`, `edges.object_drug_orphan`) now **RAISE EXCEPTION**. Verified: phantom-edge insert rejected, valid edge accepted, all edge seeders green, 0 real writes blocked.
2. **Stage 1 residual data fixes (all via governed paths / Kyle-approved).**
   - **apg777 / apg279 were MIS-TARGETED** (review doc had it backwards). Primary sources: APG777 = zumilokibart = anti-IL-13 mAb; APG279 = IL-13×OX40L fixed-dose combination. Corrected target/mechanism/drug_format via DrugWriter, with Apogee sources.
   - **CLD-423 is REAL** (Caldera/Qyuns IL-23p19×TL1A bispecific, a direct Ailux competitor) and already existed as `cldr-001`. The 16 `cld-423` edges were wrong-id duplicates → deleted + code aliased onto cldr-001 (`migrations/v158`).
   - **Phantoms purged:** mk-1718, mdr-018 (no real-world asset; like the v80 mk-1695 purge) — ~54 edges deleted.
   - **Company-as-drug edges deleted** (abbvie/amgen/aurinia/jnj/ucb/orukatherapeutics, 6 edges).
   - **Duplicate molecules merged** (FK-aware `dedupe_entities.py`): ati-045→bosakitug, xmab5871→obexelimab. Codes aliased; bare rows retired. drugs 194→192.
   - **7 stale approved stages flipped** to `approved` (Fasenra, Rinvoq, Ebglyss, Imaavy, Rystiggo, Adbry, Nucala) — all verified marketed. brand⇒approved violations → 0.
   - Net: **orphan drug-edges 74 → 0.**

## ⚠️ Validate / watch
- Engine still healthy after enforcement (edge seeders re-ran green). If a NEW pipeline ever emits an edge to a not-yet-created drug, it will now hard-fail with `governance violation [edges.*_drug_orphan]` — that's intended; fix the writer to create the drug first.
- One known accepted side effect of the merges: a few `drug_sources`/`drug_targets`/`trial_registries` rows attached to the duplicate code-rows were dropped on unique-collision (regenerable derived data).

## Next (see PRIORITY.md queue)
1. **Link the 26 unlinked catalysts** (all real) → then add `catalysts.must_link` to `governance_enforced_rules`.
2. **Layer B permission boundary** (REVOKE INSERT/UPDATE on core tables from anon/authenticated + write RPC) — the real physical single-writer; confirm pipelines use service_role first.
3. **Drug-discovery `company_id` policy** → then enforce `drugs.company_id_required` (12 company-less codes remain).
4. **Backfill `drug_sources`** for the 58 drugs (run evidence-collectors, free).
5. **apg777/apg279 `TARGETS` edge re-sync** to il13/ox40l so the corrected target reaches the graph.

## Carried over
- 4 mechanism/target flags needing a primary source: `mk-1695`, `shr0817`, `hlx36`, `abs-101`.
- Service-role key rotation is Kyle's (standing security item).

---

# NEXT_SESSION — handoff (overnight 2026-06-15 → 06-16)

**Autonomous legibility + stabilization pass.** Goal: make the repo ready for morning review and friendly to an outside engineer, and refresh the planning docs to TRUE current state. Operated on the LIVE repo (`kyleklaassen-dev/bd-dashboard`, `main`) via the GitHub Contents + Git Data APIs. `index.html` was deliberately NOT touched (another task owns it).

## What got done tonight
1. **`update_log.md` trimmed** 495 KB → ~79 KB (most recent ~50 entries, 943 lines). Older history moved to `docs/reports/update_log_archive.md` (~410 KB). Both verified live.
2. **`docs/` root organized** 66 → 10 files. Moved 56 dated reports/audits/memos/DDL into `docs/reports/`, `docs/audits/`, `docs/database/`, `docs/frameworks/`, `docs/decisions/` in batch commits (git history preserves the moves). **Kept at docs root** (intentionally): the governance/read-first docs (`constitution.md`, `decisions.md`, `STABILIZATION_PLAN.md`) and the **script-referenced** docs (`foresight_review_queue.md` is a *write target* of `score_foresight.py`; `phase4_comparison_harness.md` is the default `--output` of the phase4 compare script; plus `drug_competitive_scores_ddl.sql`, `catalyst_quality_diagnosis.md`, `dashboard_dependency_inventory.md`, `evidence_reconciliation_layer.md`, `drug_area_scores_retirement_plan.md`).
3. **`README.md` reconciled to reality** — fixed the repository map (removed nonexistent `supabase/` and root `archive/` rows and `migrations/legacy/`; corrected `src/` to "only `database/` populated, rest staged"; corrected `scripts/` subdirs to integrations/maintenance/migrations; `docs/` subdir list now includes `decisions/`; added the 📡 Intelligence tab; deploy section now reflects the single protected `main`).
4. **Planning docs refreshed to TRUE state** — `PRIORITY.md` rewritten around the stabilization stage board (Engine on, Stage 0/1/2 done, Stage 3/5 in progress, Stage 4 blocked); this `NEXT_SESSION.md` section; a session-log entry appended to `docs/STABILIZATION_PLAN.md`. Live counts cited from anon read: drugs 194, companies 191, deals 218, governance unresolved 41, validation non-pass 35 (0 fail).

## ⛔ BLOCKED — needs you (the gating items)
The **Supabase service key and a working GitHub PAT were lost** — tonight had **read-only anon** DB access only. The following can't proceed until you **rotate + re-share the service key and a PAT, or remount `bd-dashboard`**:
- **Stage 4 enforcement DDL** — apply `migrations/PROPOSED_drugwriter_enforcement.sql` (the permission boundary that makes single-writer real). Needs the service key + a watch window.
- **Stage 1 residual data fixes** — the 41 governance + 35 validation rows that are *real* (wrong-asset trial links, stage-confidence, source gaps), not false-positives. Triage detail in `docs/audits/GOVERNANCE_TRIAGE_2026-06-15.md` + `docs/audits/VALIDATION_TRIAGE_2026-06-15.md`.
- **Stage 5 table backfills** — the dark/empty tables + missing links in `docs/audits/CONNECTIVITY_GAP_AUDIT_2026-06-15.md`.
- **Rotate the previously-exposed service-role key** (standing security item) — do this as part of the key refresh.

## ⏳ Carried over (still open from prior sessions)
- **4 mechanism/target flags** needing a primary source: `mk-1695`, `shr0817`, `hlx36`, `abs-101`.
- **11 obscure company-less drug codes** (`ab001`, `calt-100`, `eta1001`, `mg-k10`, `sm-101`, `xb3217`, …) — resolve as they disclose.

---

# NEXT_SESSION — handoff (overnight 2026-06-05 → 06)

Two-part overnight session. **Part 1** finished the narrative depth-of-trust stack; **Part 2** ("do all of these, especially patient") built four big new layers on top. All deployed to `main` via the GitHub Git Data API (local git can't commit on this mount; use `outputs/gh_commit.py "<msg>" <files...>`; for `.github/workflows/*` files set `GH_TOKEN_FILE=.github_token_workflow`).

## PART 2 — the four big pushes (newest)
1. **Patient-intelligence depth (North Star)** — `scripts/patient_narrative.py` + `generate_patient_briefs.py` + `.github/workflows/patient-briefs.yml`. Cited "Meridian Patient Brief" + "Meridian Patient Analysis" (molecule×patient fit) per indication, `entity_type='indication'`. Reuses the full provenance/independence/gap machinery. Generated UC/CD/IBD live. **Key fact:** the patient table is rich but UNSOURCED (`source_urls` NULL), so all patient facts land INTERNAL-tier → independence view shows 0 independent → **138 patient facts now queued for collection**. (commits dd634ef, 338a2ed)
2. **Autonomous evidence collector (the flywheel)** — `scripts/collect_evidence.py`. Works the gap queue by fetching VERIFIABLE independent sources — ct.gov registry records (per NCT) + Europe PMC publications (relevance-checked) — and writing cited `drug_sources` rows (never fabricates a URL; idempotent). **Proven closed loop:** collected 12 sources for tulisokibart / 8 for duvakitug → regen → independent_claims 3→5, peer-reviewed 14; duvakitug multi-domain 8→10. Wired as the first batch step. (commit 70420af)
3. **Go wide — all areas** — dispatched the narrative workflow on CI for **il23p19, tslp, il4ra, fcrn, igf1r** (limit=0) and the patient-briefs workflow for all 28 indications. Running now. (the competitive + patient layers go wide server-side overnight)
4. **Strategic decision layer (apex)** — `scripts/strategic_brief.py`. Ranked, cited BD brief per landscape, `entity_type='target', section='business'`. Each asset carries stage + overlap + DATA-TRUST grade; the brief **discounts low-trust profiles** and honors deal-sequencing. TL1A brief written: XmAb412 "call now" (A/94), SPY120 caveated (C/67), AbbVie timing-gated to ABBV-701 Oct-2026. First time trust actively shapes a recommendation. Wired into the batch driver. (commit 8788aa6)

## PART 1 — depth-of-trust stack (earlier tonight)
- **Stateful collection queue** (v76 + `sync_collection_queue.py`); **cross-publication value agreement** (v77 + `verify_publication_values.py` — NEJM abstract confirms tulisokibart 26%); **dashboard surfacing** (independence badge / disagreement chip / gap count / tier dots / ✓N× in `index.html`); **CI key fix** (scripts read `SUPABASE_SERVICE_KEY` from env — the weekly Narrative job had been failing); **full TL1A field populated** (72 narratives).

## ⚠️ Validate in the morning
- **Check the CI fleet finished green**: 5 area Narrative Generation runs + 1 Patient Briefs run were in_progress at write time. https://github.com/kyleklaassen-dev/bd-dashboard/actions — re-dispatch any that failed (key fix + collector are in `main`).
- **Eyeball a card** (tulisokibart): independence badge, ⚠ disagreement chip (26% vs 49.1%), tier dots, ✓N×.
- **Read the TL1A Strategic Brief**: `entity_narratives WHERE entity_type='target' AND entity_id='tl1a' AND section='business'` — this is the new decision layer; tell me if the ranking/logic matches your read (feedback goes in `narrative_feedback`, honored on regen).
- Migrations this session: **v72–v77** applied.

## Still open (next increments)
- Surface the **patient brief** + **strategic brief** on the dashboard (the card loader currently renders drug overview/intelligence; add indication briefs to area tabs and the `business` section to the landscape view).
- Feed cross-pub `confirmed` values + collected sources back as confidence boosts to the trust score.
- `sync_collection_queue --all` is heavy (per-row resolves); fine on schedules but could be batched.
- Collector v2: patient/epidemiology source discovery for the 138 indication gaps (currently it handles drug gaps).

---
## ⏳ STILL WAITING ON YOU (carried over, unresolved)
- **4 mechanism/target flags** needing a primary source (⚑ queue / `governance_violations`): `mk-1695`, `shr0817`, `hlx36`, `abs-101`.
- **11 obscure company-less drug codes** (`ab001`, `calt-100`, `eta1001`, `mg-k10`, `sm-101`, `xb3217`, …) — resolve as they disclose.
