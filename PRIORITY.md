# Meridian — Current Priority Stack

**Last updated:** 2026-06-16 (overnight autonomous legibility + stabilization pass).
**Rule:** Claude reads this at the start of every session before any other action, and updates it at the end of every session. Kyle reviews and corrects direction here, not mid-session.

---

## ▶ DOING NOW

**Stabilization sprint is the active program** (see `docs/STABILIZATION_PLAN.md`). The engine is back on, the repo is clean, and governance/validation backlogs are triaged. The one open gate is **single-writer enforcement at the database layer**, which is **blocked on credentials** (the Supabase service key + a working GitHub PAT were lost — read-only anon access only tonight).

**Freeze still in effect:** no new product features until single-writer enforcement and Phases 1–3 are green.

---

## Stabilization stage board (TRUE state as of 2026-06-16)

| Stage | What it is | Status |
|-------|-----------|--------|
| **Engine** | The 15 core GitHub Actions workflows re-enabled and live (research → enrich → graph → write → validate). | ✅ DONE — re-enabled. |
| **Stage 0** | Production git wiring: a single protected `main` branch, clean clone, deploys reconciled. | ✅ DONE. |
| **Stage 1** | Governance + validation triage: `governance_violations` 86 → **41** unresolved; `drug_validation_results` non-pass 43 → **35** (34 warning + 1 needs_review, **0 fail**); clear false-positive fixes applied. | ✅ DONE (triage). Residual real data fixes need DB writes → see Stage 4 block. |
| **Stage 2** | 📡 Intelligence tab: surfaces **11 previously-dark backend datasets** (strategic insights, genetic validation, trial-design quality, conference signals, EU approvals, manufacturing, narrative trust, …). | ✅ DONE — staged + deployed in `index.html`. |
| **Stage 3** | Repo legibility: README/.gitignore added, root cruft removed, `update_log.md` trimmed (495KB → ~79KB) with history archived, `docs/` root organized (66 → 10 files). | 🔄 IN PROGRESS — most done this overnight pass. |
| **Stage 4** | **Enforcement** — apply the single-writer permission boundary (`migrations/PROPOSED_drugwriter_enforcement.sql`) so direct writes to core tables are physically blocked. | ⛔ BLOCKED on DB credentials (lost service key / PAT). This is the gate that makes "single writer" real. |
| **Stage 5** | Connectivity backfills + residual data fixes (table backfills the connectivity audit surfaced). | 🔄 IN PROGRESS — read-only analysis done; the writes are blocked on credentials. |

> **Live data counts (anon read, 2026-06-15/16):** drugs **194**, companies **191**, deals **218**, governance unresolved **41**, validation non-pass **35** (0 fail).

---

## QUEUE (in order)

| # | Item | Priority | Status | Notes |
|---|------|----------|--------|-------|
| 1 | **Restore DB credentials** — rotate + re-share the Supabase service key and a working GitHub PAT (or remount `bd-dashboard`). | P0 | ⛔ BLOCKER | Unblocks Stages 1-residual, 4, and 5. Nothing that writes Supabase can proceed without this. |
| 2 | **Stage 4 — apply enforcement DDL** | P0 | Blocked | `migrations/PROPOSED_drugwriter_enforcement.sql` (trigger backstop + permission boundary). Needs the service key + a watch window. Success = direct writes to `drugs`/`companies`/`catalysts` physically blocked. |
| 3 | **Stage 1 residual data fixes** — real (non-false-positive) governance + validation rows. | P1 | Blocked | 41 governance + 35 validation rows remain; the residue is real wrong-asset trial links / stage-confidence / source gaps. Triaged in `docs/audits/GOVERNANCE_TRIAGE_2026-06-15.md` + `VALIDATION_TRIAGE_2026-06-15.md`. Fixes require DB writes. |
| 4 | **Stage 5 — connectivity table backfills** | P1 | Blocked | Dark/empty tables + missing links from `docs/audits/CONNECTIVITY_GAP_AUDIT_2026-06-15.md`. Read analysis done; backfills need writes. |
| 5 | **Rotate the exposed service-role key** | P1 | Open | Standing security item; folds into queue #1. |
| 6 | **Phase 3 — modularization** (split the 6 largest scripts) | P2 | Plan authored | `docs/architecture/modularization_plan.md`. Safe, one-at-a-time, after writer enforcement. |
| 7 | **Phase 4 — decompose `index.html`** | P3 | Not started | Highest effort, last. |

---

## North Star (read before every architectural decision)

> "Which molecule should Ailux bring to the clinic, in which indication, with which differentiated clinical hypothesis — and where does the competitive landscape create or close that window?"

Intelligence hierarchy: **Patient → Indication → Target → Company.** Value flows upward from patients, not downward from deal activity.

Stabilization north star: **exactly ONE approved, enforced path that can modify each core entity (drug, company, edge, catalyst).** "Single writer" is a convention until the database enforces it — success is measured by enforcement, not by "scripts were rewritten."

---

## Update Rules

- Claude updates `## ▶ DOING NOW` and the stage board / queue at the end of every session.
- Completed items get a date + note.
- Kyle corrects sequencing here — not mid-session in chat.
- Convert relative dates to absolute when editing.
