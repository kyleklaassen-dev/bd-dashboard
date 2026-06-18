# PRIORITY

**Single source of future work: `ROADMAP.md`. Session reading guide: `START_HERE.md`.**

## Active task — two dedicated-session refactors (designed, not yet executed)
The whole §A correctness spine is DONE: ✅ §A.1 one-write-path (all 4 core tables single-writer),
✅ §A.4 audit (field_change_audit covers all 4 tables, writer attribution), ✅ §A.5 edge-case tests (9/9).
Package migration DONE (src/ = unified `meridian` pkg). Two big refactors remain — do each as its OWN session:

1. **§3 large-file splits** (`docs/architecture/PHASE3_4_EXECUTION_DESIGN.md`). ✅ **`company_enrichment` DONE**
   (4,377→937 orchestrator + 11 modules under `src/meridian/enrichment/company/`; byte-identical, writer-test-gated;
   branch `refactor/section3-company-enrichment-prompts`, not yet pushed). NEXT targets, same method (AST-guided,
   byte-identical, writer-test-gated): `write_meridian` (2,387; `meridian-preview --dry-run` verifiable), `drug_intake`
   (1,627), `research` (1,539), `ct_gov_sync` (1,409). Deferred (supervised): route `company/common.py` `sb_*` → writers.
2. **§A.2 UI/logic separation** in `index.html` (34k lines: `_resolveStage`/`_score`/`_dedup`/`canonical`×61). Move
   identity/scoring/stage logic server-side; dashboard displays trusted data. Pair with §4 decomposition. Page-load-verify
   each extraction (local `python3 -m http.server` + load index.html). HIGHEST risk — do last.

START HERE NEXT SESSION: read this + NEXT_SESSION.md (top entry) + ROADMAP §A/§3/§4. Pick #1 (§3) first.
Verify-gate everything with `tests/database/` (8/0 + 6/0) — they exercise all writers live, read-only.

## Always
Start: read START_HERE.md → ROADMAP Now/Next → NEXT_SESSION. End: update ROADMAP + NEXT_SESSION, run
`scripts/maintenance/repo_hygiene_check.py`, confirm engine green.
