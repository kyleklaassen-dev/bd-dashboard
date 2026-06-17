# PRIORITY

**Single source of future work: `ROADMAP.md`. Session reading guide: `START_HERE.md`.**

## Active task
Finish the package migration — the **narrative cluster** (ROADMAP §1). enrichment-core web + write_meridian
are DONE; next = `narrative_gen` consumers (generate_area_narratives, generate_patient_briefs, landscape_narrative,
patient_narrative, strategic_brief, collect_evidence, seed_*_edges, reconcile_drug_integrity, verify_publication_values).
Run the full-repo importer sweep first; dispatch-verify each (narrative-generation / patient-briefs / evidence-collectors).

## Always
Start: read START_HERE.md → ROADMAP Now/Next → NEXT_SESSION. End: update ROADMAP + NEXT_SESSION, run
`scripts/maintenance/repo_hygiene_check.py`, confirm engine green.
