# Repo Cleanse — EXECUTED 2026-06-15

**Target:** LIVE GitHub repo `kyleklaassen-dev/bd-dashboard`, branch `main` (source of
truth; local mount is stale and was used only for the new `README.md` / `.gitignore`
content and for token auth).

**Method:** Single batch commit via the GitHub **Git Data API** (create blobs →
create tree off the live base tree with paths removed/added → create commit →
fast-forward update `refs/heads/main`). No `git`, no per-file Contents DELETEs.

**Auth:** `.github_token_workflow` (the plain `.github_token` is dead).

---

## Commit

- **SHA:** `7c0c9e53e2b2eda4795ded8631fe04b6946ca8f2`
- **Parent:** `5287efe28ad48347dcdaf5019b14ee114134663b`
- **Message:** `Repo cleanse: remove regenerable deliverables + version sprawl + cruft; add README + .gitignore (legibility pass)`
- Combined STEP B (additive) and STEP C (removals) into this one commit.

---

## Files ADDED / REPLACED (2)

1. **`README.md`** — replaced the prior 2-line stub with the full engineer-facing
   README (what Meridian is, quickstart, architecture-at-a-glance, repository-map
   table, governance/source-of-truth links, security model, status). Content from
   the freshly-written local `README.md`.
2. **`.gitignore`** — **created** (the repo previously had NONE — the highest-leverage
   security/cruft fix). Content from the local `.gitignore`: blocks all secret
   dotfiles + catch-alls (`*.key`, `*.pem`, `*_secret*`, `*service_role*`),
   `.docx`/`.xlsx`, logs, caches, OS/editor cruft, run/process artifacts.

---

## Files REMOVED (43) — all regenerable / version-sprawl / cruft, recoverable via git history

### Regenerable `.docx` deliverables (15)
- `AIB_FcRn_Albumin_autoimmune_v1.docx`
- `AIB_IGF1R_TSHR_thyroid_eye_disease_v1.docx`
- `AIB_IL4Ra_OX40L_atopic_dermatitis_v1.docx`
- `AIB_TSLP_IL33_asthma_COPD_v1.docx`
- `AIB_TL1A_IL23p19_UC_Refined.docx`
- `AIB_TL1A_IL23p19_UC_v6.docx`, `_v8.docx`, `_v9.docx`, `_v10.docx`, `_v11.docx`,
  `_v12.docx`, `_v13.docx`, `_v14.docx`, `_v15.docx`, `_v16.docx`
  (entire family removed — regenerable; the editorial standard lives in
  `docs/frameworks/AIB_EDITORIAL_PRINCIPLES.md`)

### Superseded AIB / prototype HTML (15)
- `aib_fcrn_v1.html`, `aib_igf1r_v1.html`, `aib_il4ra_v1.html`, `aib_tslp_v1.html`
- `aib_tl1a.html`, `aib_tl1a_full.html`, `aib_tl1a_refined.html`
- `aib_tl1a_v8.html`, `_v9.html`, `_v10.html`, `_v11.html`, `_v12.html`,
  `_v13.html`, `_v14.html`, `_v15.html`, `_v16.html`
  *(Note: `aib_view.html` was NOT removed — see "Kept" below.)*

### Duplicate ARCHITECTURE versions (3) — kept canonical `ARCHITECTURE.md`
- `ARCHITECTURE_v2.md`, `ARCHITECTURE_v3.md`, `ARCHITECTURE_STATUS.md`

### Stray root SQL (7) — `migrations/` (60 numbered files, v12+) is the one home
- `schema_migration_v2.sql`, `v3`, `v4`, `v5`, `v7`, `v8`, `v10.sql`

### Other regenerable cruft (3)
- `build_v20.py` (regenerable build artifact)
- `meridian_overnight_summary.txt` (committed operational text dump)

> Count by category: 15 docx + 15 prototype-html (16 candidates minus `aib_view.html`)
> + 3 architecture + 7 sql + 1 build + 1 text-dump = **43**.

---

## Kept — "uncertain / served, left in place" (1 of note)

- **`aib_view.html` — KEPT (served).** The live `index.html` loads it in an
  `<iframe id="aib-frame" src="aib_view.html?area=...">` (lines ~12235 / ~12242),
  so it is an active part of the deployed dashboard. The manifest grouped it with
  the prototypes, but a reference scan of all served HTML showed `index.html`
  actively depends on it. Deleting it would break the dashboard's AIB panel.
  Per the KEEP-when-unsure rule it was left in place.

### Other root files intentionally kept (not cruft)
`index.html`, `Meridian_Live.html`, `meridian_today.html`, `Meridian_Coverage.html`,
`Meridian_DocIntel.html`, `intelligence.html`, `predictions.html`,
`meridian_ask.html`, `meridian_ask_review.html`, `meridian_atlas.html`,
`meridian_brief.html`, `meridian_feedback_ui.html`, `meridian_strategic_lens.html`,
`meridian_workflow_map.html` (served product views); `CLAUDE.md`, `README.md`,
`ARCHITECTURE.md`, `BD_ANALYST_PLAYBOOK.md`, `CODE_REVIEW.md`, `PRIORITY.md`,
`NEXT_SESSION.md`, `SESSION_PROTOCOL.md`, `update_log.md`, `.nojekyll`.
All of `src/ scripts/ tests/ migrations/ .github/ docs/ config/ data/` untouched.

---

## Verification (re-fetched live tree after commit)

- `README.md` present: **yes**
- `.gitignore` present: **yes**
- All 43 removed files: **gone (0 still present)**
- Protected files intact: `index.html`, `Meridian_Live.html`, `meridian_today.html`,
  `CLAUDE.md`, `aib_view.html`, `ARCHITECTURE.md`, `.nojekyll` — all OK
- Protected dirs intact: `src/`=7, `scripts/`=172, `tests/`=3, `migrations/`=60,
  `.github/`=53, `docs/`=74, `config/`=1, `data/`=28 — all present
- **Root file count: 68 → 26.** Total tree entries: 486 → 444.

---

## Follow-ups not done here (out of scope of this cleanse / need owner)

- Deploy tooling should honor the new `.gitignore` ignore-list so future
  Contents-API pushes can't reintroduce `.docx`/`.xlsx`/logs/secrets (root cause).
- Rotate the previously exposed Supabase service-role key (open security item).
- Larger structural moves (relocate product HTML to `web/`, tidy `docs/` root,
  rationalize the 53 workflows, rotate `update_log.md`) remain owner-gated per the
  audit's section C.3.

*Executed 2026-06-15 against the live repo. All removals recoverable via git history.*
