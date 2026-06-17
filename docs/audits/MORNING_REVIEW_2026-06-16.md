# Meridian — Morning Review & Audit (overnight 2026-06-16)

**For:** Kyle · **By:** claude_agent (autonomous) · **Purpose:** review the large batch, verify health, set next steps.
Everything below was self-verified against primary sources and the live DB. Where I was uncertain I held rather than guessed, and I flag the two mistakes I made and corrected.

---

## 0. TL;DR — the platform is healthy and the batch checks out

- **DB integrity: GREEN.** 0 orphan drug-edges, 0 duplicate canonicals, 0 brand⇒approved violations, 0 orphan catalysts, 0 validation failures, **no duplicate drug names**.
- **Enforcement: LIVE.** 4 invariant rules hard-block (mode=exception, 4 triggers); Layer B holds (anon has NO write on core tables except the 2 partnership-pill columns); RLS on all 4 core tables. **0 real pipeline writes have ever been blocked.**
- **Engine: GREEN.** Last ~3h: 8 success, 0 failures. Morning Summary digest fixed. June‑16 Issue serving on Opus.
- **Submitted intel: now auto-reviews every 4h** (was on-demand only). The 9-item backlog was processed; **10 items are in `needs_review` waiting on you.**
- **Governance: 41 → 3** unresolved, every reduction verified. Drugs 192 → 189.

**Net:** the stabilization sprint and the data-quality pass are done. Nothing is broken. The 3 decisions for you are in §3.

---

## 1. What changed this session (with evidence + reversibility)

### 1a. Enforcement (migrations v157–v162, all on `main`, all recorded in `schema_change_log`)
| Migration | What it does | Reversible? |
|---|---|---|
| v157 | WARN-mode triggers + `governance_enforcement_log` + per-rule allow-list scaffolding | yes (drop triggers) |
| v158 | Graph cleanup: purged phantom edges (mk-1718, mdr-018), 6 company-as-drug edges, redundant cld-423 edges; aliased CLD-423→cldr-001 | edges were broken; re-seedable |
| v159 | Escalate the 2 edge referential rules to RAISE EXCEPTION | yes (delete from `governance_enforced_rules`) |
| v160 | Broaden + enforce `catalysts.must_link` (drug OR company OR area) | yes |
| v161 | **Layer B**: REVOKE anon/authenticated write on core tables; keep anon column-grant for partnership pill | yes (GRANT back) |
| v162 | Enforce `drugs.company_id_required` on INSERT, with `discovery_status='auto'` exception | yes |

### 1b. Stage corrections (verified vs company/primary sources) — all via the governed DrugWriter, with sources
- **jnj-4804**: Phase 3 → **Phase 2** (J&J: only Ph2b DUET data; Ph3 DUET ENCORE merely planned).
- **es302** (ElpiScience TL1A×IL-23p19): Phase 2 → **Preclinical** (company pipeline page says "currently in the preclinical stage").
- **lq082** (Novamab TL1A×IL-23×α4β7 trispecific): Phase 2 → **Preclinical** (Synapse/Novamab).
- **shr0817** → corrected to its real identity **SHR-1819** (Hengrui anti-IL-4Rα), Phase 2 → **Preclinical**, mechanism text fixed.
- **7 marketed drugs** earlier flipped to `approved` (Fasenra, Rinvoq, Ebglyss, Imaavy, Rystiggo, Adbry, Nucala) — all verified marketed.
- **apg777/apg279** earlier corrected from a wrong IL-4Rα×OX40L label to IL-13 / IL-13×OX40L (Apogee).
- **Confirmed CORRECT** (so the flag was a source-gap, not inflation; left as-is): **spy230, ear-2001/HXN-1001, bel512/CM512** are genuinely Phase 2.

### 1c. Identity cleanup (Kyle-approved batch)
- **Purged 2 phantoms** (deleted, no real-world asset, 0 orphans left): `hlx36`, `ionis-tslp-25rx`.
- **Merged 1 duplicate** (FK-aware): `hr7044` → `shr-1905` (Hengrui anti-TSLP). Also dedup'd earlier: ati-045→bosakitug, xmab5871→obexelimab.
- **Dropped 8 records REVERSIBLY** (`dashboard_visible=false`, NOT deleted — they're still in the DB):
  - Off-domain oncology (real but out of IBD/I&I scope): `eta1001, gb1275, ky1044, srf-231, xb3217`.
  - Unverifiable/misidentified: `rgx-181` (actually REGENXBIO's Batten-disease gene therapy, mislabeled anti-FcRn), `nvx-360` (no such drug found), `calt-100` (no such TSLP antibody; Calluna's real asset is CAL101), `dam-51` (no public presence).

### 1d. Trial-link cleanup — ⚠️ includes a mistake I caught and reversed
- Cleared **13 `trial_misattributed` flags**. 11 were genuine (the drug linked to a registry/observational/diet study where it isn't an arm).
- **I initially over-removed 2** before re-checking ct.gov: **filgotinib/NCT02714634** (a real treatment-arm in a Phase 4 RA RCT) and **inebilizumab/NCT06885957** (a named cohort in an NMOSD study). **Both restored** and documented. Memory updated so the ct.gov intervention check happens up front next time. (Worth your spot-check: §2.)

### 1e. Misc / infra
- 17/26 unlinked catalysts linked to a drug/company; the rest are area-anchored.
- 58→11→ (now small) `drug_sources` gaps closed by promotion + collectors.
- **Morning Summary workflow fixed** (it was failing on a gitignored file; now uploads an artifact; also fixed a `governance_violations.created_at` query bug).
- **Startup reliability**: CLAUDE.md, README, and the memory index corrected (stale `BD Platform` path → `bd-dashboard`; dead `.github_token` → `.github_token_workflow`).
- **shr-1905** company backfilled to Hengrui (this audit).

---

## 2. What to spot-check (5 minutes)
1. **The 2 restored trial links** — confirm you agree filgotinib/NCT02714634 and inebilizumab/NCT06885957 are real (they are named in the ct.gov intervention/arm data). If you disagree, they're easy to remove again.
2. **The 8 reversibly-dropped records** — they're hidden, not deleted. Confirm none should stay visible. Reverse any with `UPDATE drugs SET dashboard_visible=true WHERE id='…'`.
3. **The 4 stage corrections** (jnj-4804, es302, lq082, shr0817/SHR-1819) — all downgrades from inflated stages, each with a source in `drug_sources` (session_label `gov_phase_inflation_2026-06-16`).
4. **10 `submitted_intel` items in `needs_review`** — these are real submissions the auto-review flagged for your judgment.

---

## 3. Decisions that need you
1. **Hard-delete vs keep the 8 dropped records?** They're hidden now. If you want them gone permanently, say so and I'll purge them (with full reference cleanup). Otherwise they stay hidden and recoverable.
2. **The 2 likely-phantoms I did NOT delete** (`nvx-360`, `calt-100`) — I dropped them reversibly rather than purge, because I'm ~90% (not 100%) sure they're fake. Want them hard-purged like hlx36/ionis-tslp?
3. **China-asset stage flags** (`generate-uc`/GB-3250, `lbl-053`) — these are Phase 3 claims with zero China CDE/NMPA footprint. They need a CDE/NMPA check I couldn't complete. Want me to dig, or hold?

---

## 4. Next-steps roadmap (prioritized)

**P1 — quick, high-confidence data fixes (ready to execute next session):**
- Backfill mechanism for 5 well-known approved drugs (all textbook, just need sourced URLs): `certolizumab-pegol` (PEGylated anti-TNF-α Fab), `etanercept` (TNFR2-Fc fusion), `etrasimod` (S1P1/4/5 modulator), `tildrakizumab` (anti-IL-23p19 mAb), `tofacitinib` (JAK1/3 inhibitor).
- Canonicalize 3 Shattuck assets missing `canonical_drug_id`: `sl325, sl425, sl846` (needs the real entity_matcher — run in CI or a non-mount env).
- Backfill `source_url` on 7 deals; `drug_sources` on 5 visible drugs (`certolizumab-pegol, cnd4985, etanercept, etrasimod, lbl-051-s3`).

**P1 — data acquisition (biggest remaining gap):**
- Company firmographics: **58 companies** missing `hq_country`, **34** missing `company_type`, **58** missing `strategic_value_score`. GLEIF/enrichment pass.

**P2 — the 3 governance holds** (§3.3 + `ab001`/`sm-101` by-design ambiguous-identity — likely just mark acknowledged).

**P2 — Phase 3 modularization** (`docs/architecture/modularization_plan.md`): split the 6 largest scripts, one at a time, now that enforcement is in place. This is the first real post-freeze architecture step and deserves a focused session with per-script CI verification.

**P3 — Phase 4**: decompose `index.html` (~35k lines). Highest effort, last.

---

## 5. Method note
All DB writes went through the governed DrugWriter or carefully-tested, rolled-back-first SQL via the Management API (PAT). Merges used the FK-aware `dedupe_entities.py`. Every migration is on `main` and in `schema_change_log`. The one process miss this session (unlinking 2 real trials before the ct.gov check) was caught on review and reversed — the rest verified clean.
