# PRIORITY

**Single source of future work: `ROADMAP.md`. Session reading guide: `START_HERE.md`.**

## Active task
**One clear data-write path** (ROADMAP §A.1) — the gating item. Gating question: can ONE approved path
create/modify a drug record ingestion→database→dashboard? Today NO (drug_intake/company_intake/write_meridian/
verify_sources raw-REST write `drugs`, bypassing DrugWriter). **Freeze new dashboard features until clean.**
**Start:** route `drug_intake.py` (primary intake) through `DrugWriter`, then the other 3; run tests/database/ after each.

Migration status: package migration's enrichment-core web + narrative cluster DONE (2026-06-17, flat scripts 47→32);
remaining migration = LLM stragglers + writers→`src/meridian/database/` (the latter dovetails with §A.1).

## Always
Start: read START_HERE.md → ROADMAP Now/Next → NEXT_SESSION. End: update ROADMAP + NEXT_SESSION, run
`scripts/maintenance/repo_hygiene_check.py`, confirm engine green.
