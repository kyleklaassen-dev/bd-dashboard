# docs/architecture/ — index

Start here. This folder explains how the codebase is built and how it's being
organized. Read in this order depending on what you need.

## Understand the system
- **`docs/ARCHITECTURE.md`** — what the platform does: the 7-stage research
  model (entity discovery → drug mapping → trials → catalysts → positioning → deals →
  discovery loop), the data model, and the script→stage mapping. **Read this first.**
- **`drug_lifecycle.md`** — how a single drug record flows through the pipeline.
- **`../database/governance_table.md`** — per-table owner / sole-writer / validation rules.

## Understand the code's structure & relationships
- **`DEPENDENCY_MAP.md`** — the reliable reference for *what relates to what*: the
  pipeline DAG (which workflow runs which scripts, in order), the shared utility modules,
  and the import coupling. Built from a clean snapshot of `main`. Use before moving any file.
- **`REPO_LAYOUT.md`** — the **target** standard layout (`src/meridian/<domain>/` package,
  thin CLI scripts, one `migrations/`, `web/`), naming conventions, the large-file split
  list, and the **safe incremental migration sequence**. The master plan for the reorg.
- **`repo_maps.md`** — quick "mental maps" (structure / workflow / frontend / where-to-look).
- **`../../scripts/README.md`** — navigation map of the `scripts/` directory by domain.

## The two big refactors (in progress)
- **Scripts → package + smaller files:** `REPO_LAYOUT.md` §5–§6 is the plan;
  `modularization_plan.md` and `PHASE3_4_EXECUTION_DESIGN.md` hold the detailed per-script
  split designs (e.g. the validated `ct_gov_sync.py` fetch/map/write split). The
  single-writer code layer this depends on is built: see `src/database/` (4 writers).
- **`index.html` (34k lines) decomposition:** `INDEX_HTML_MAP.md` maps its anatomy;
  `INDEX_HTML_DECOMPOSITION_PLAN.md` is the staged, risk-ranked split plan.

## Schema/data cleanup
- **`../audits/SCHEMA_CLEANUP_BACKLOG.md`** — dead/empty DB objects (Tier A dropped; Tier B/C backlog).

## Status of the reorg (2026-06-16)
Done safely so far: archived 17 one-off scripts → `scripts/archive/`; consolidated the two
migration dirs into `migrations/`; built the reliable dependency map; hardened + verified the
4 governed writers. **Not yet done** (needs a supervised session — it edits live pipeline code):
moving the active scripts into `src/meridian/` packages, and the `index.html` split.
