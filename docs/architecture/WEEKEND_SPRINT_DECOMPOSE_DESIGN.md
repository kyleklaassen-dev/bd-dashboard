# §2 — `weekend_sprint.py` Decompose (turnkey design, 2026-06-18)

> **The last ≥1000-line file** (`scripts/weekend_sprint.py`, 3,001 lines) and the only remaining item in the
> ≥1000 health bucket. It is an **active Saturday cron** (`weekend_sprint.yml`), so this is a *supervised*
> refactor with a dispatch-verify — NOT the byte-identical relocation used for the §3 library splits. This doc
> makes the execution turnkey: the structure, the `DRY_RUN` blocker solution, and the verify procedure.

## Structure (already clean phases)
- **Base:** creds (`_read_file_credential`), `sb_get/post/patch/upsert`, `log`, `table_exists`,
  `ensure_weekend_sprint_log_table`, `log_phase`.
- **Block A — audit (8):** `phase_a1_schema_health` … `phase_a8_stale_data_detection` (+ `_phase_a6_legacy_backlog`).
- **Block B — enrichment (8):** `phase_b1_drug_enrichment` … `phase_b8_partnership_verification` (+ `_llm_enrich`).
- **Orchestrator:** `main` (arg parse, phase dispatch, the run loop).

**Good news — low duplication.** It already *calls into* the extracted agents via lazy `_import_agent(...)`
(`mod.run(dry_run=…)`, `mod.enrich_drug(…)`), so the decompose is mostly relocating the phase bodies + base
helpers, not de-duplicating logic. The earlier "duplicates company_enrichment/coverage/etc." concern is largely
already addressed by those call-ins.

## The `DRY_RUN` blocker — and its fix
`DRY_RUN` is a module-level bool (`weekend_sprint.py:116`) **rebound at runtime** in `main` from `--dry-run`, and
read directly in ~20 phase bodies (`if DRY_RUN:` / `if not DRY_RUN:`). If phases move to submodules that do
`from weekend_sprint import DRY_RUN`, each submodule captures the **import-time** value (`False`) — the runtime
rebinding never propagates. (Contrast `_RUN_TOKENS`, a dict mutated in place → shared by reference → safe.)

**Fix (same "shared mutable" principle):** replace the bare bool with an accessor in the new `weekend/common.py`:
```python
# weekend/common.py
_RUN = {"dry_run": False}                 # mutable holder → shared by reference across submodules
def set_dry_run(v): _RUN["dry_run"] = bool(v)
def is_dry_run():   return _RUN["dry_run"]
```
Then mechanically: every `if DRY_RUN:` → `if is_dry_run():`, every `dry_run=DRY_RUN` → `dry_run=is_dry_run()`,
and in `main`: `set_dry_run(args.dry_run)` once, before dispatch. Now all submodules read the live value.
(Alternative: thread `dry_run` as a param into each phase — cleaner signatures but touches every call site; the
accessor is lower-churn for a 16-phase orchestrator.)

## Target layout (`src/meridian/ops/weekend/`)
- `common.py` — creds, `sb_*`, `log`, `log_phase`, `table_exists`, `ensure_*`, the `is_dry_run/set_dry_run` accessor.
- `audit.py` — `phase_a1..a8` (+ `_phase_a6_legacy_backlog`).
- `enrich.py` — `phase_b1..b8` (+ `_llm_enrich`), keeping the `_import_agent` call-ins.
- `weekend_sprint.py` (orchestrator, stays an entrypoint) — `main`, arg parse, phase registry/dispatch, run loop.
Workflow `weekend_sprint.yml` entrypoint path unchanged (orchestrator keeps its name/location) → no YAML edit.

## Verify procedure (supervised — this is the gate)
1. After the refactor, run **locally** `python scripts/weekend_sprint.py --dry-run` (or the dispatch with a
   dry-run input). Confirm: every phase logs `[DRY RUN]` and **no DB writes occur** (watch `field_change_audit`
   /`governance_violations` row counts before/after — must be unchanged).
2. Grep-assert zero remaining bare `DRY_RUN` references after the accessor swap.
3. Run the writer/edge suites (the agents it calls write through Writers).
4. Only then let the next scheduled Saturday run execute live — **with Kyle watching the first run** (it writes
   to the production DB; a `DRY_RUN`-accessor bug = unintended writes, which is exactly why this is supervised).

## Why not autonomous
A `DRY_RUN` mistake here flips the cron from "report" to "write to production." That blast radius (unintended
writes to core tables on an unattended Saturday run) is the reason §2 is supervised. The design above makes the
execution mechanical and the verify concrete, so the supervised pass is short.

## Status
Design only. No code changed. Sequenced + de-risked; execution awaits a watched dispatch. ROADMAP §2 updated.
