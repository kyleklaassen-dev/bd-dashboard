# Repository Cleanliness & Legibility Audit — 2026-06-15

**Scope:** Read-only reconnaissance of (a) the local working copy at `/BD Platform/` and (b) the deployed public GitHub repo `kyleklaassen-dev/bd-dashboard`. Goal: can an outside software engineer open the GitHub repo and immediately make sense of it?

**Method:** Local filesystem inventory via shell; GitHub repo inventory via the REST git-trees API (`/git/trees/main?recursive=1`, full tree, 485 entries, not truncated). The supplied `.github_token` is **expired (401 on every endpoint)** — the repo is public, so inventory was done unauthenticated. No files were modified, moved, or deleted.

**Headline:** No committed secrets — this is good. But both the local root and the GitHub repo root are badly cluttered with versioned deliverables and scratch output, and the GitHub repo has **no usable README and no `.gitignore`**, so an outside engineer lands on a wall of `AIB_*_v8..v16.docx`, `aib_tl1a_v8..v16.html`, and a 4.3 MB `index.html` with no orientation. A clean, well-documented intended structure already exists in `docs/architecture/repo_maps.md` — the repo simply doesn't match it.

---

## A. Current-state findings

### A.1 GitHub repo `bd-dashboard` (what an outside engineer actually sees)

- **Public repo**, default branch `main`, description "The Meridian", 485 tree entries (465 files, 20 dirs), ~16.7 MB.
- **README.md is 2 lines / 75 bytes** ("bd-dashboard / BD Intelligence Dashboard - Bispecific Antibody DealMonitor"). No what/why, no run instructions, no architecture, no directory map.
- **No `.gitignore` in the repo at all.** (A good one exists locally — see A.3 — but git is broken on the mount, so deploys go through the GitHub Contents API and bypass it entirely. That is the root cause of the cruft below.)
- **Repo root has 68 loose files**, including the worst offenders:
  - **15 `.docx` drafts** at root: `AIB_TL1A_IL23p19_UC_v6/v8/v9/v10/v11/v12/v13/v14/v15/v16.docx` plus `_Refined` and four other-target AIBs. These are regenerable Word binaries that the local `.gitignore` explicitly excludes.
  - **~16 `aib_*.html` prototype views** at root: `aib_tl1a_v8..v16.html`, `aib_tl1a_full/refined`, `aib_fcrn_v1`, `aib_igf1r_v1`, `aib_il4ra_v1`, `aib_tslp_v1`, `aib_view.html` — superseded HTML prototypes.
  - **4 architecture docs at root** (`ARCHITECTURE.md`, `ARCHITECTURE_v2.md`, `ARCHITECTURE_v3.md`, `ARCHITECTURE_STATUS.md`) — three versions of the same document; unclear which is current.
  - **8 loose `schema_migration_v*.sql`** at root, duplicating the purpose of the `migrations/` directory (which has 60 files in-repo).
  - `build_v20.py` (60 KB) at root — a build-script artifact that belongs in an archive.
  - `update_log.md` is **495 KB** at root — a giant append-only changelog dominating the file listing.
  - Operational text dumps committed: `meridian_overnight_summary.txt` (17 KB).
- **Directory file counts (repo):** scripts 172, docs 74, root 68, migrations 60, `.github` 52, data 28, src 7, tests 3, config 1.
- **`.github/workflows` has 52 workflow files** — many overlapping/legacy names (`weekend_sprint.yml` + `school-week-sprint.yml`, `morning-summary.yml` + `evening-update.yml` + `meridian-write.yml`, etc.). Per project memory, ~15 are intentionally disabled for cost; an outsider can't tell which are live.
- **Largest committed files:** `index.html` 4.3 MB, `update_log.md` 495 KB, `scripts/company_enrichment.py` 248 KB, `data/fine_tune_signal_*.jsonl` 168 KB, `scripts/write_meridian.py` 133 KB, `scripts/weekend_sprint.py` 121 KB.
- **src/ is nearly empty (7 files)** vs scripts/ (172) — the "production Single Writer" layer described in docs is barely represented; the real code mass is in `scripts/`.

### A.2 Local working copy (the source the repo is deployed from)

Even messier than the repo, because the local tree is the staging ground:

- **Root file counts by extension (non-recursive):** 37 `.docx`, 35 `.html`, 31 `.md`, 13 `.xlsx`, 13 `.sql`, 8 `.log`, 4 `.py`, 3 `.txt`, 3 `.sh`, 2 `.pid`, 2 `.json`, 1 `.tmp`.
- **Versioned deliverables at root:**
  - **37 `.docx`** including the full `AIB_TL1A_IL23p19_UC_v2..v16` family (15 versions), `BD_Platform_Architecture` ×3, and ~16 other one-off Word docs (~2.78 MB of `.docx`+`.xlsx` combined).
  - **13 `Meridian_Master_Review_v11..v25.xlsx`** — 13 versions of the same spreadsheet at root.
- **31 loose `.md`** at root: dated session findings (`Meridian_Session_Findings_2026-06-08/09.md`), one-off audit/plan reports (`GAP_REMEDIATION_PLAN_2026-06-11.md`, `FABLE_LEVERAGE_REVIEW_2026-06-11.md`, `Knowledge_Graph_Connectivity_Audit_2026-06-09.md`, `TRIAL_MISATTRIBUTION_BATCH_2026-06-11.md`, etc.) that belong under `docs/reports/` or `docs/audits/`.
- **Active cruft / process artifacts at root:**
  - `_perm_test.tmp`, `.git/_perm_test.tmp` (perm-probe leftovers)
  - 10 `.log` files (`akeso_run.log`, `enrichment_daemon.log`, `toz_*_output.log`, `tozorakimab_*.log`, …) and 2 `.pid` files (`akeso_run.pid`, `enrichment_daemon.pid`) — daemon/run output that should be gitignored (and is, locally).
  - 2 Office lock/temp files: `~$_Mastery_Checklist.docx`, `~$ridian_Ontology_Reference.docx`.
- **Hidden-file cruft (counts):** 31 `.fuse_hidden*` files, 3 `.~lock.*#` LibreOffice lock files (`Meridian_Master_Review_v22/v23.xlsx`, `TL1A_UC_Efficacy_Sourced_2026-06-10.xlsx`), 4 `.DS_Store` (root, docs/, scripts/, .github/). `.fuse_hidden*` are also under `prototypes/` and `scripts/`.
- **`__pycache__/` at root** (should be gitignored; it is locally).
- **`docs/` is itself cluttered:** 232 files total, **193 loose at the docs root**, only then organized into 9 subdirs (`architecture/`, `archive/`, `audits/`, `database/`, `frameworks/`, `reports/`, `semantic_layer/`, `skills/`, `sops/`). Mixed in are non-doc artifacts (e.g. `ailux_angle_preview_*.json`, `ailux_angle_rollback_*.json`).
- **Subdir scale:** scripts 548 files, migrations 180, archive 39, src 18, tests 20, prototypes 7.
- **Scratch/working dirs present locally** (correctly gitignored): `.scratch_audit/`, `outputs/`, `health_reports/`, `kol_work/`, `edge_work/`, `logs/`, `enrichment/`.

### A.3 The good news — the intended structure is already documented

- `docs/architecture/repo_maps.md` (v1, 2026-06-09) defines a clean target layout (`index.html`, `src/`, `scripts/` + `maintenance/` + `one_off/`, `tests/`, `migrations/`, `docs/`, `archive/`) with ACTIVE/NEW/ARCHIVE status legend, a workflow map, and a frontend dependency map. The repo just doesn't conform to it.
- A **local `.gitignore` exists and is excellent**: it ignores all secret dotfiles, `*.key/*.pem/*_secret*/*service_role*`, `.DS_Store`, `__pycache__/`, `.venv/`, `.fuse_hidden*`, `*.docx`, `*.xlsx`, `~$*`, `.~lock.*#`, `*.log`, `logs/`, scratch dirs, and `data/*/` caches. **It is simply not in effect on the deploy path** (Contents-API deploys ignore it).
- There is already a `docs/DASHBOARD_REORG_PLAN_2026-06-12.md` and `docs/audits/STABILIZATION_AUDIT_2026-06-09.md` — reorg intent exists; this audit complements them with the repo-vs-local delta.

---

## B. CRITICAL section

- **No committed secrets found — PASS.**
  - GitHub Actions workflows reference secrets correctly via `${{ secrets.* }}` (checked `meridian-research.yml`): `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`. None hardcoded.
  - Deployed `index.html` contains **only** `SUPABASE_ANON = "sb_publishable_..."` (Supabase's publishable/anon key, designed to be client-side and safe behind RLS) — no `service_role`, no JWT, no `sk-`/`ghp_` tokens. The prior service-key exposure (per project memory) is confirmed remediated in the deployed file.
  - No secret dotfiles (`.github_token`, `.supabase_*`, `.env`) appear in the repo tree.
- **CRITICAL — no `.gitignore` committed to the repo.** The protection that keeps secrets and cruft out lives only in the local `.gitignore`, which the Contents-API deploy path bypasses. This is the single most important gap: nothing structurally prevents a future deploy from pushing `.env`, `.supabase_service_key`, a `.docx`, or a log into the public repo. **The local `.gitignore` should be committed to the repo, and the deploy tooling should honor an ignore list.** (Note: the supplied `.github_token` is also expired and should be rotated for any future automated deploy/cleanup.)
- **HIGH — secret dotfiles are unencrypted at the local root** (`.github_token`, `.github_token_workflow`, `.supabase_service_key`, `.supabase_pat`, `.anthropic_api_key`, `.env`). They are gitignored locally and not in the repo, so this is hygiene, not a breach — but the exposed/leaked service_role key flagged in project memory still needs rotation in Supabase regardless.

---

## C. Cleanup plan (ordered)

### C.1 Safe to do automatically (pure cruft — no information loss)

These remove regenerable junk and editor/OS artifacts. None are tracked by the repo; most are already in the local `.gitignore`.

1. **Delete local hidden cruft:** 31 `.fuse_hidden*`, 3 `.~lock.*#`, 4 `.DS_Store`, 2 `~$*.docx`, `_perm_test.tmp`, `.git/_perm_test.tmp`, root `__pycache__/`.
2. **Delete process artifacts at local root:** the 10 `.log` files and 2 `.pid` files (`akeso_run.{log,pid}`, `enrichment_daemon.{log,pid}`, `toz_*`, `tozorakimab_*`). They are gitignored and regenerated on each run.
3. **Commit the local `.gitignore` to the repo** (verbatim — it is already correct). This is the highest-leverage automatic fix.
4. **Remove the regenerable deliverable binaries from the repo** (they violate the existing `.gitignore` rule `*.docx`/`*.xlsx`): the 15 root `AIB_*_v*.docx`, all root `aib_tl1a_v*.html`/`aib_*_v1.html` prototypes, and any committed `.docx`. The *source of truth* for these (the editorial standard) is `docs/frameworks/AIB_EDITORIAL_PRINCIPLES.md` + `docs/sops/meridian_issue_style_v1.0.yaml`, per the `.gitignore` comment — the drafts themselves don't belong in version control.
5. **Stop committing operational text dumps** (`meridian_overnight_summary.txt`) — gitignore the pattern.

> Recommendation: do C.1.1–C.1.2 directly; stage C.1.3–C.1.5 (repo deletions) as a single reviewed deploy since they touch the public repo.

### C.2 Archive superseded versions (keep one, retire the rest — owner can skim first)

6. **Collapse `.docx` version families to the latest** and move older versions to `archive/deliverables/`: keep `AIB_TL1A_IL23p19_UC_v16.docx`, archive v2–v15 + `_Refined`. Same for `BD_Platform_Architecture` (keep v2.1).
7. **Collapse `Meridian_Master_Review_v11..v25.xlsx` to the latest** (v25), archive the rest to `archive/master_review/`.
8. **Collapse `ARCHITECTURE*.md`:** designate one current `ARCHITECTURE.md` (likely the content of `_v3`), move `_v2`/`_v3`/`_STATUS` to `docs/archive/`. Cross-link from the README.
9. **Move the 8 root `schema_migration_v*.sql` into `migrations/`** (or `migrations/legacy/` if superseded by the numbered set) so there is one migrations home.
10. **Move `build_v20.py` (and any other `build_v*.py`) to `archive/dashboard_builds/`** — `repo_maps.md` already names this archive location.
11. **Move the 31 dated `.md` reports off the root** into `docs/reports/` (session findings, gap/leverage reviews, batch audits).

### C.3 Needs owner approval (deletions, relocations, structural)

12. **Relocate the ~16 root `*.html` views.** Decide which are live products vs prototypes. Live ones (e.g. `meridian_*.html`, `index.html`, `predictions.html`, `intelligence.html`) stay at root or move to a `web/` dir; prototypes (`aib_*`, `ontology_*_prototype.html`, `intelligence_audit.html`) move to `prototypes/` or `archive/`. Requires owner to confirm what's still deployed.
13. **Tidy `docs/` root (193 loose files).** Sort the loose `.md` into the existing subdirs (`reports/`, `audits/`, `frameworks/`, `architecture/`) and move data artifacts (`ailux_angle_preview_*.json`, `ailux_angle_rollback_*.json`) out of `docs/` into `archive/` or a data dir. Add/refresh `docs/INDEX.md` as the docs map.
14. **Rationalize the 52 workflows.** Owner to mark live vs disabled (a `# STATUS: disabled (cost)` header per file, or move disabled ones to `.github/workflows/disabled/`), and dedupe overlapping schedulers (`weekend_sprint` vs `school-week-sprint`, the morning/evening/write trio).
15. **Address the 4.3 MB `index.html` and 495 KB `update_log.md`.** `index.html` is already the Phase-4 split target; `update_log.md` should be truncated/rotated (archive history, keep recent) so it doesn't dominate the repo.
16. **Decide `src/` vs `scripts/` boundary.** With src/ at 18 files and scripts/ at 548, document (in README/repo_maps) what graduates into `src/` (governed writers, production layer) vs stays in `scripts/` (pipelines/one-offs), so an outsider knows where the "real" code is.
17. **Rotate credentials** (service_role key per memory) and **rotate the expired `.github_token`** — required before any automated deploy of this cleanup.

---

## D. Proposed clean directory structure

This matches `docs/architecture/repo_maps.md` and what an outside engineer expects:

```
bd-dashboard/
├── README.md                 # what/why, quickstart, architecture, dir map (see E)
├── .gitignore                # the existing local one, committed
├── CLAUDE.md                 # AI operating instructions (kept)
├── index.html                # the dashboard (Phase-4 split target)
├── web/                      # other deployed HTML (meridian_ask, atlas, brief, predictions, intelligence)
│   └── prototypes/           # aib_*, ontology_* experiments (or move to archive/)
├── src/                      # production layer (single-writer pattern, client.py, *_writer.py)
│   ├── database/  identity/  ingestion/  ontology/  enrichment/  scoring/  frontend/  utils/
├── scripts/                  # pipelines
│   ├── maintenance/          # dedupe, audit, link tools
│   ├── integrations/         # external-API sync
│   └── one_off/              # retired one-offs (archive-tier)
├── tests/                    # writer + regression suites
├── migrations/               # all numbered SQL (absorb root schema_migration_v*.sql)
├── data/                     # tracked dashboard inputs only (caches in data/*/ are gitignored)
├── docs/                     # architecture/ database/ audits/ reports/ frameworks/ sops/ archive/
│   └── INDEX.md              # the docs map
├── archive/                  # historical, kept for reference
│   ├── dashboard_builds/     # build_v*.py
│   ├── deliverables/         # superseded AIB_*.docx
│   └── master_review/        # superseded Meridian_Master_Review_v*.xlsx
└── .github/workflows/        # live workflows; disabled/ subdir for paused ones
```

**Root should hold ~10 files, not 68:** README, .gitignore, CLAUDE.md, index.html, and the top-level config — everything else lives in a labeled directory.

---

## E. Recommended README outline

Replace the 2-line README with:

```markdown
# Meridian — BD & Competitive-Intelligence Platform

> One-paragraph: what Meridian is (a competitive-intelligence & BD platform for
> Ailux's TL1A×IL-23p19 bispecific program in IBD), who it's for, and what the
> live dashboard does. Link to the deployed GitHub Pages URL.

## Quickstart
- Prerequisites (Python version, .env from .env.example, Supabase project).
- How to run the dashboard locally / where it deploys (GitHub Pages, CDN TTL note).
- How to run the test suite (tests/database/test_drug_writer.py — read-only).

## Architecture (at a glance)
- The data flow: external sources → ingestion → identity/ontology → enrichment →
  graph → products → Supabase → frontend. (Embed/lift the diagram from
  docs/architecture/repo_maps.md.)
- Backend: Supabase (anon key + RLS in the client; service key only in CI secrets).
- Frontend: index.html on GitHub Pages.

## Repository map
- Table of top-level dirs with a one-line purpose each (mirror section D).
- "Where to look" pointers: src/ = production writers, scripts/ = pipelines,
  migrations/ = SQL, docs/ = everything else.

## Governance & source-of-truth docs
- Links: docs/STABILIZATION_PLAN.md, docs/constitution.md,
  docs/database/governance_table.md, docs/architecture/repo_maps.md, docs/decisions.md.

## Security
- Secrets live in CI (GitHub Secrets) and local dotfiles only — never committed.
- Client uses the Supabase publishable/anon key behind RLS.

## Status
- Current sprint (stabilization), what's frozen, what's in progress.
```

---

*Audit performed read-only on 2026-06-15. No files modified, moved, or deleted. GitHub inventory unauthenticated (supplied token expired); repo is public.*
