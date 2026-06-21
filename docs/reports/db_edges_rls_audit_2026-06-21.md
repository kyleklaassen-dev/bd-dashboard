# entity_edges + RLS Audit — 2026-06-21 (Domain C3)

Read-only. No data changed.

## entity_edges integrity — 28,147 edges, 2 orphans (minor)
Full paginated scan; every `drug`/`company` subject & object id checked against `drugs`/`companies`.

- **Type spread:** subjects — author 11,971 · drug 5,767 · trial 3,383 · institution 2,650 · kol 1,887 · company 1,533 · target 487 · abstract 442 · patient 27. objects — publication 12,879 · indication 4,445 · drug 2,800 · author 4,979 · company 931 · target 885 · filing 632 · …
- **Orphans found: 2** — both `company`-subject `ACTIVE_IN` edges whose `subject_id` doesn't exist in `companies`:
  - `xencor-412`, `xencor-942` — these are **Xencor drug ids** (XmAb412 / XmAb942) mis-typed as `subject_type='company'`. Either the edges should be dropped or re-typed `drug` with the real company subject `xencor`.
- **Verdict:** 2 / 28,147 = 0.007% — clean. Fix is a delete/re-type on `entity_edges` (EdgeWriter / §7 approval); **not actioned** (Kyle's call, non-urgent).

## RLS / anon hygiene — clean
Every table the frontend reads returns **HTTP 200** under the anon (publishable) key: `drugs, companies, catalysts, deals, intel, intel_facts, competitive_signals, conference_abstracts, conference_abstract_signals, entity_narratives, entity_edges, meridian_issues, asset_programs, strategic_insights, drug_clinical_signals, indication_patient_intelligence, payer_tpp_criteria, narrative_provenance, narrative_claim_triangulation, company_signals, research_reads`.

- Core write-protected tables (`drugs`/`companies`/`catalysts`) remain anon-**readable** by design (read-only); writes are blocked by the single-writer triggers (verified 2026-06-21), not by RLS.
- No sensitive table is over-exposed. Consistent with `APPLIED_2026-06-16_rls_enable_24_exposed_tables.sql`.
- (Note: `drug_clinical_signals` and `narrative_claim_triangulation` are keyed by `drug_id`/`narrative_id`, not `id` — probe with `select=*`.)

## Action items (Kyle, non-urgent)
1. Re-type or drop the 2 `xencor-412`/`xencor-942` company edges.
2. (No RLS action needed.)
