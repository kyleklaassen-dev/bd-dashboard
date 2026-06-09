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
