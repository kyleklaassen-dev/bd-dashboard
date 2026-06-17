# START HERE — Meridian reading guide

A 60-second router for any work session. **Read this first, then route to the few files your task needs.**
Goal: seamless, production-level operations — know what to read, when, and how, every time, without hunting.

## Every session — read these 4, in order (≤5 min)
1. **`CLAUDE.md`** — operating instructions + the hard governance rules (what's truth, single-writer, sources, deploy). Non-negotiable.
2. **`START_HERE.md`** (this file) — the router.
3. **`ROADMAP.md`** — the single source of future work. Look at **Now / Next**.
4. **`NEXT_SESSION.md`** — the last session's handoff (what just happened, gotchas). `PRIORITY.md` = the current active task.

## Then route by what you're about to do
| If you're going to… | Read first |
|---|---|
| Move/rename/migrate scripts | `docs/architecture/REPO_LAYOUT.md` (target layout + §6 method) · `docs/architecture/DEPENDENCY_MAP.md` (what relates to what). Run the full-repo importer sweep before moving anything. |
| Write to a core table (`drugs`, `companies`, `entity_edges`, `catalysts`) | `docs/database/governance_table.md` + the writer in `src/database/` (`drug_writer.py` etc.). **Never** ad-hoc upsert a core table. |
| Add a fact / enrich | `CLAUDE.md` source rule (every fact needs a `drug_sources`/`intel_facts` row with a real URL) + `docs/governance/*`. Verify primary source before writing. |
| Touch identity / entity linking | `src/meridian/identity/entity_matcher.py` is the one resolver (imported by the writers — change with care; run `tests/database/`). |
| Generate a Meridian Issue / narrative | `docs/.../meridian_writing_standards` + the products in `src/meridian/products/`. |
| Deploy | **Use normal git** (`git add`/`commit`/`push`) — real local clone, working `origin` + osxkeychain creds. The old "git broken → GitHub API" rule was Cowork-sandbox-only; `scripts/deploy_files.py` is just a fallback now. Pages CDN ~10-min TTL; verify via raw.githubusercontent. |
| Understand the system end-to-end | `ARCHITECTURE.md` (7-stage model) · `docs/architecture/drug_lifecycle.md` · `docs/architecture/repo_maps.md`. |
| Pick up the big refactors | `ROADMAP.md` §1–§6 + `docs/architecture/REPO_LAYOUT.md` / `INDEX_HTML_DECOMPOSITION_PLAN.md`. |

## Golden rules (the ones that bite)
- **Single-writer:** core tables only through their writer. **Sources:** every fact needs a real-URL source row. **Never fabricate URLs.**
- **`company_id` = originator** (never a licensee); ownership lives in partnerships/deals.
- **New code goes in `src/meridian/<domain>/`,** not flat `scripts/`. One responsibility per module, ≤ ~300–400 lines.
- **A move isn't done until the workflow that exercises it runs green.** Read workflow YAML from `main`, not a stale snapshot.
- **Spend status:** currently ON (freeze lifted 2026-06-16) — LLM workflows may be dispatched to verify. Re-check if cost posture changes.

## When you finish — leave it clean (so the next session is seamless)
1. Update **`ROADMAP.md`** (check off done; add anything discovered).
2. Update **`NEXT_SESSION.md`** (handoff: what changed, what's next, any gotcha) and **`PRIORITY.md`** (next active task).
3. Run the **drift guardrail** (`python3 scripts/maintenance/repo_hygiene_check.py`) and fix anything it flags.
4. Confirm the engine is green (no failed workflow runs from your changes).
