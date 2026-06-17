# Meridian BD Platform — Claude Operating Instructions

Short and operational by design. Detailed architecture, governance, and history live in `/docs`. Full prior version: `docs/archive/CLAUDE_full_2026-06-09.md`.

## What this is
Competitive-intelligence & BD platform for Ailux (TL1A×IL-23p19 bispecific, IBD).
Workspace: the **bd-dashboard repo clone** (this folder; the old `BD Platform` folder is retired) · Dashboard repo: `kyleklaassen-dev/bd-dashboard` (GitHub Pages, protected `main`) · Backend: Supabase `tghntyofptvfhmtchwcv`. Creds in `.supabase_service_key`, `.supabase_anon_key`, `.github_token_workflow` (the plain `.github_token` is DEAD), `.supabase_pat`.

## Read-first (source of truth)
1. `docs/STABILIZATION_PLAN.md` — current phase, what's in progress, success criteria. **READ FIRST.**
2. `docs/constitution.md` — what is truth, what may modify it, source hierarchy, what needs approval.
3. `docs/database/governance_table.md` — per-table owner / sole-writer / validation.
4. `docs/architecture/drug_lifecycle.md` — how a drug record flows.
5. `docs/decisions.md` — ADR (why things are the way they are; don't re-debate).
6. `NEXT_SESSION.md` / `PRIORITY.md` — last session's handoff.

## Session start
1. Read `STABILIZATION_PLAN.md` (we are in a stabilization sprint — no new features until Phases 1–3 green).
2. Check `drug_validation_results` for fail/warning and `governance_violations WHERE resolved=false`.
3. Run `tests/database/test_drug_writer.py` (read-only) — must be green.

## Hard rules (governance — full detail in constitution.md + governance_table.md)
- **Core tables (`drugs`, `companies`, `entity_edges`, `catalysts`) are written through their Writer only.** Use `src/database/drug_writer.py` (others in progress). Do NOT add new ad-hoc `sb_upsert('drugs',...)` paths.
- `drugs.company_id` = **originator** (never a licensee). Display owner via `_resolveStage`/originator marker. Ownership → partnerships/deals.
- `brand_name` ⇒ approved stage (a dash "—" is invalid → null).
- Default company `status='subsidiary'`; `acquired` only when provably dissolved.
- **Every fact in Supabase needs a source row** (`drug_sources`/`intel_facts`) with a real URL. Never fabricate URLs.
- Entity linking uses the one resolver: `scripts/entity_matcher.py` (ambiguity-guarded).
- No DB write path without a validation query. Deletes/merges/table-drops/`approved`-flips need Kyle's approval.

## Deploy
**Use normal git.** This is a real local clone on macOS with a working `origin` remote (HTTPS + osxkeychain creds) — `git add` / `git commit` / `git push` work. The old "git is broken (FUSE deadlocks) → deploy via the GitHub API" rule was specific to the **retired Cowork sandbox** (which could create/overwrite but not delete) and **no longer applies** in Claude Code. `scripts/deploy_files.py` (GitHub Git Data API, `.github_token_workflow`) is kept only as a fallback if a push ever fails. GitHub Pages CDN ~10-min TTL; verify via raw.githubusercontent. DB writes: `.supabase_service_key` (REST), `.supabase_pat` (DDL via Management API, curl not urllib).

## Before/after any edit (Claude behavior rule)
Before: state the layer, affected files, affected tables, breakpoints, proposed tests; keep changes small.
After: run/propose tests, update the changelog + `STABILIZATION_PLAN.md`, deprecate (don't ambiguously delete), add no duplicate workflows.

## Key paths
`src/database/` (writers + shared client) · `scripts/` (active pipelines) · `scripts/maintenance/` (dedupe, audit, link tools) · `scripts/one_off/` + `archive/` (historical) · `tests/` · `migrations/` (numbered; `PROPOSED_*` = staged for review) · `index.html` (dashboard, ~34k lines — Phase 4 target).
