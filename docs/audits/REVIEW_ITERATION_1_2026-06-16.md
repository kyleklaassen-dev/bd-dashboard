# Meridian Platform — Autonomous Review Pass (Iteration 1)

> **Run:** overnight 2026-06-16 · **Mode:** READ-ONLY on the database (writes blocked).
> **Scope:** connectivity (every dashboard tab → Supabase binding), the new 📡 Intelligence
> (`intel2`) tab, the 26 `/assets/ii-NN.jpg` images, and accuracy/integrity sanity checks on
> core data (drugs, companies, deals, entity_edges, strategic_insights, target_genetics, …).
> **Live source:** `index.html` fetched from `main` via the GitHub Contents API (2,488,075 bytes /
> 34,847 lines — the slimmed build with base64 images moved to `/assets/`).
> **Read key:** publishable/anon key (the live browser read path), against
> `https://tghntyofptvfhmtchwcv.supabase.co/rest/v1`.

---

## 0. Headline

- **Connectivity: GREEN. No dark panels.** All 112 distinct `.from()` table/view bindings and
  all 14 `intel2` tab tables return data for the **anon** key (the live read path).
  Only two zero-row tables exist (`patent_families`, `resolver_errors`) and **neither is a dark
  panel** — see §2.
- **Assets: GREEN.** All **26/26** `assets/ii-NN.jpg` return HTTP 200 on
  `raw.githubusercontent`. Image extraction is confirmed; **0 base64 data-URIs** remain in
  `index.html`.
- **Accuracy: several real, fixable integrity issues found** — 2 swapped/wrong `modality`
  fields, 2 duplicate-molecule rows, 1 orphaned drug-graph node + 3 mistyped graph edges,
  58/194 drugs with no source row, and ~stale `stage` columns on approved drugs (visually
  masked by `_resolveStage`, but the stored value is wrong).

---

## 1. Connectivity — tab → table bindings (all live)

Enumerated every `.from('…')` in `index.html` (112 distinct tables/views) plus the `intel2`
module's 14 template-literal fetches, and ran an anon `count=exact` against each.

**Result: every binding returns rows for the anon key except two zero-row tables, both benign.**

### 1a. The 📡 Intelligence tab (`intel2`) — the new live read path

All 11 nav sections (`insights, genetics, trials, conf, eu, mfg, trust, kols, grants,
ownership, market`) are present and each maps to a renderer. Every backing table returns
data for **anon** (not just service):

| Section | Table | anon rows |
|---|---|---|
| Strategic insights | `strategic_insights` | 532 |
| Genetics (assoc) | `target_disease_assoc` | 1,537 |
| Genetics (gnomAD LoF) | `target_genetics` | 117 (39 targets × syn/mis/lof) |
| Trial quality | `trial_design_quality` | 1,398 |
| Conference signals | `conference_abstract_signals` | 451 |
| EU approvals | `eu_approvals` | 47 |
| Manufacturing | `manufacturing_sites` | 51 |
| Narrative trust (prov.) | `narrative_provenance` | 4,137 |
| Narrative trust (tri.) | `narrative_claim_triangulation` | 195 |
| KOL | `kols` | 316 |
| KOL bibliometrics | `kol_metrics` | 5 (card is conditional — OK) |
| Grants | `grants` | 642 |
| Ownership | `company_ownership` | 14 |
| Market / unmet need | `indication_patient_intelligence` | 28 |

**No intel2 section is dark.** The module is correctly error-isolated (each renderer falls back
to a "No … data found" muted line rather than throwing).

### 1b. Two zero-row tables — both benign, NOT dark panels

- **`patent_families` (0 rows)** — queried at line 16794 inside the drug-detail "IP & patents"
  panel, *alongside* `drug_patents` (174 rows). The panel renders from `drug_patents`; the
  empty `patent_families` just omits a family-grouping sub-line. Cosmetic.
- **`resolver_errors` (0 rows)** — queried only as a `count` for a governance health badge
  (lines 4325/4427, `.is('resolved_at', null)`). Zero is the *healthy* state (no unresolved
  resolver errors). Correct, not dark.

### 1c. Thin but live (worth noting, not bugs)

`kol_metrics` (5), `company_ownership` (14), `ailux_bd_context` (14), `meridian_issues` (14),
`china_intel` (3), `asset_differentiation_profiles` (3), `drug_combinations` (3),
`competitive_landscapes` (5), `target_pairs` (5). All render; they're acquisition-thin, not
broken (tracked under §C).

---

## 2. Asset check — `/assets/ii-NN.jpg`

All **26/26** images return **HTTP 200** on
`https://raw.githubusercontent.com/kyleklaassen-dev/bd-dashboard/main/assets/ii-NN.jpg`
(`ii-01` … `ii-26`). `index.html` references exactly those 26 files and contains **0**
remaining `data:image/jpeg;base64` URIs — the extraction is complete and the Industry-Insights
tab will render against the on-disk assets.

---

## 3. Accuracy / integrity findings (read-only)

### 3a. `modality` field errors — 2 drugs (the cendakimab-class pattern)

Scanned `drug_format` vs `modality` for contradictions. Two OX40L bispecifics carry wrong
`modality` strings:

| id | drug_format | mechanism (correct) | modality (WRONG) |
|---|---|---|---|
| **apg777** | `bispecific` | "bispecific VHH nanobody … SC" | `Monoclonal antibody` ← should be bispecific/VHH |
| **apg279** | `bispecific_vhh` | "Anti-IL-4Rα×OX40L bispecific antibody" | `co-formulated anti-IL-13 + anti-OX40L mAb combination (fixed-dose SC)` ← describes a co-formulated combo, not a bispecific VHH |

Both target IL-4Rα×OX40L and are bispecifics; the `modality` text looks copied from the wrong
asset (apg777 reads like a plain mAb; apg279 reads like a co-formulation). These surface in the
Drugs-to-Know catalog (`modality` is a displayed column).

### 3b. Duplicate molecules — 2 pairs share one `canonical_drug_id`

| canonical_drug_id | rows | reading |
|---|---|---|
| `CANON_DRUG_F70602D4` | **`ati-045`** (TSLP, company_id **NULL**) + `bosakitug` (TSLP, biosion) | ATI-045 is bosakitug's code → `ati-045` is the stale duplicate (no company). |
| `CANON_DRUG_CA5E6284` | **`xmab5871`** (CD19/FcγRIIb, company_id **NULL**, Ph2/3) + `obexelimab` (CD19×FcγRIIb, zenas, Ph3) | XmAb5871 is obexelimab's code → `xmab5871` is the stale duplicate (no company). |

Both duplicates are the company-less, code-named rows. They should be folded into the named
canonical (alias the code into `drug_aliases` and delete/redirect the bare-code row).

### 3c. Orphaned graph node + mistyped edges in `entity_edges`

- **`cld-423`** is the `subject_id` of **8 manual `COMPETES_WITH` edges** (incl. `→ alx001`) but
  **does not exist in `drugs`**. All 8 *object* drugs exist — only the subject is orphaned. The
  asset was likely renamed/removed without cleaning its edges. These edges currently inject a
  phantom competitor into the graph (and into alx001's competitive set).
- **3 mistyped edges** carry `subject_type='drug'` but the `subject_id` is a **company**:
  `abbvie → adalimumab`, `amgen → etanercept`, `aurinia → voclosporin` (all `deterministic`,
  `COMPETES_WITH`). In this taxonomy drugs compete with drugs; a company as a `drug`-typed
  subject is wrong. Likely a seeder that emitted the company id instead of the asset id.

(Sampled the abstract/author edge bulk too — those are clean: `PRESENTED`, `AUTHORED`,
`CO_AUTHORED_WITH` dominate and type-check.)

### 3d. Stale `stage` on approved drugs (masked at render, wrong in DB)

8 drugs have a populated `approval_date` and/or `brand_name` but `stage` = `Phase 2/3`:
`benralizumab`(Fasenra), `rozanolixizumab`(Rystiggo), `upadacitinib`(Rinvoq),
`nipocalimab`(Imaavy), `mepolizumab`(Nucala, stage=Phase 2), `lebrikizumab`(Ebglyss),
`tralokinumab`(Adbry), `amlitelimab` (approval_date set, Ph3).
Per the data-validation rule (brand_name→approved, approval_date→approved) the stored `stage`
is wrong. **The dashboard masks this** — `_resolveStage()` (line 9744) maps brand_name → "Approved"
at render time, so users see "Approved". But any consumer reading `drugs.stage` directly
(exports, analytics, the catalog `.order('stage')`) gets the stale value. Worth a DB cleanup.

### 3e. Null-heavy critical columns (quantified)

- **drugs:** 14/194 have **NULL `company_id`** (no company affiliation shown), incl.
  `ati-045`, `xmab5871` (the duplicates above), plus `ati-052 sm-101 dam-51 gb1275 calt-100
  ab001 nvx-360 shr-1905 lbp-ec01 eta1001 xb3217 srf-231 rgx-181`.
  9/194 have **NULL `canonical_drug_id`** — 2 are legitimate "Combo Study" rows
  (`risankizumab-vs-vedolizumab`, `risankizumab-lutikizumab-or-trosunilimab`; category set,
  not real molecules), the rest are recent un-canonicalized assets.
- **companies (191):** null `hq_country` **58**, null `company_type` **34**, null `ticker` **84**
  (private cos — expected), null `strategic_value_score` **58**, `status` 0 (clean).
- **deals (218):** **0** orphaned drug_id/company_id (referentially clean). **7** deals have
  **no `source_url`** (governance: every fact needs a source). 150/218 have no economics
  (upfront+total both null) — mostly non-financial deal types; acquisition gap, not corruption.
- **news_articles:** only **2** rows with NULL `published_at` (they sort to the top under
  `order=published_at.desc` if nulls-first — cosmetic ordering glitch, content present).

### 3f. Source-documentation coverage gap

**58/194 drugs (30%) have NO row in `drug_sources`.** Per the standing "every fact in Supabase
needs its source in Supabase" rule this is the single largest governance gap. Examples:
`alx002, etrasimod, etanercept, certolizumab-pegol, ibi302, hbm2001, hlx36, gb004`, plus many
recent code-named assets. (Note `alx001` IS sourced; `alx002` is not.)

---

## 4. Prioritized findings

### (A) GitHub-fixable now — dashboard / doc, no DB write — 3 items

1. **Doc drift:** `docs/architecture/INDEX_HTML_MAP.md` still describes the **4.4 MB / 26 base64
   JPEG** build ("lines ~6270–6553", "44.2% of the file"). The live file is **2.49 MB** with
   images at `/assets/ii-NN.jpg` and **0** base64 URIs. Update §6 + the snapshot header so the
   map matches `main`. *(Pure doc fix.)*
2. **`patent_families` empty sub-line (line ~16794):** add a guard so the "IP & patents" panel
   skips the family block when `patent_families` returns 0 rows, rather than rendering an empty
   stub. Low-risk, cosmetic fallback. *(Optional — panel already renders from `drug_patents`.)*
3. **`news_articles` null-date ordering:** the homepage news `order=published_at.desc` lets the
   2 null-dated rows float to the top. Add `nullsLast` so dated articles lead. *(One-line client fix.)*

> Connectivity needs **no** binding fixes — every panel has data. The GitHub-fixable count is
> primarily a doc-sync + two cosmetic guards.

### (B) DB-write fixes — blocked tonight; queued for morning — precise list

1. `apg777`: set `modality` → bispecific/VHH (it is "bispecific VHH nanobody", not "Monoclonal
   antibody").
2. `apg279`: set `modality` → bispecific (IL-4Rα×OX40L bispecific VHH); current value describes a
   co-formulated IL-13+OX40L combo (wrong asset).
3. Dedup `ati-045` into `bosakitug` (alias `ATI-045` → `drug_aliases`, redirect refs, retire the
   NULL-company `ati-045` row; both share `CANON_DRUG_F70602D4`).
4. Dedup `xmab5871` into `obexelimab` (alias `XmAb5871`, retire NULL-company row; share
   `CANON_DRUG_CA5E6284`).
5. `entity_edges`: delete/repair the **8 `cld-423` COMPETES_WITH** edges (orphan subject not in
   `drugs`) — removes a phantom competitor from alx001's set.
6. `entity_edges`: fix the **3 mistyped edges** where `subject_type='drug'` but subject is a
   company (`abbvie`, `amgen`, `aurinia`) — re-type to `company` with the correct predicate or
   delete.
7. Normalize stale `stage` on the 8 approved drugs in §3d (or rely on `_resolveStage` and accept
   the column is render-only — but then any non-UI consumer must call it too).
8. Backfill `company_id` on the 12 real (non-dup) NULL-company drugs.

### (C) Data-acquisition gaps

- **Source documentation:** 58/194 drugs (30%) lack any `drug_sources` row; 7 deals lack
  `source_url`. Highest-leverage governance backfill.
- **Company firmographics:** 58 null `hq_country`, 34 null `company_type`, 58 null
  `strategic_value_score`.
- **Thin intel tables (live but sparse):** `company_ownership` (14 — only 14 of 191 companies
  have an LEI parent chain), `kol_metrics` (5), `china_intel` (3),
  `asset_differentiation_profiles` (3), `drug_combinations` (3). Expand via GLEIF / Semantic
  Scholar / existing harvesters.
- **Deal economics:** 150/218 deals carry no upfront/total value (many are non-financial, but
  the financial subset is worth enriching for BD comps).

---

## 5. Method notes / caveats

- All counts via anon `Prefer: count=exact` against the live REST endpoint — this is exactly the
  browser's read path, so "returns rows for anon" == "panel will populate".
- The `intel2` tables use template-literal `fetch()` (not `_sb.from()`), so a naive `.from()`
  grep misses them — they were enumerated directly from the module (lines 31141–31395) and
  counted separately.
- No writes were attempted. Items in (B) are specified precisely enough to execute in the
  morning once the write path is open.
