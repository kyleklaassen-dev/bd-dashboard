# Drug Lifecycle Map

**Status:** authored 2026-06-09 (Phase 0.5). The truth-test for `DrugWriter`. Trace of every live path that creates or modifies a `drugs` row.

> **Headline finding:** there is **no shared write layer**. 30 scripts define their own `sb_upsert()/sb_insert()` helper; ~11 of them touch `drugs`. Each reimplements identity, dedup, and governance (inconsistently, or not at all). This is the root cause of the duplicates, attribution drift, and orphan rows we keep fixing.

## End-to-end flow (today, as-is)

```
EXTERNAL SOURCE            ENTRY SCRIPT (writes drugs)         WHAT IT WRITES
─────────────────────────────────────────────────────────────────────────────
CT.gov / SEC / news   →   research.py                    →   trials, intel (indirect drug refs)
Manual / Cowork       →   drug_intake.py            (POST) →   new drug rows (identity ad-hoc)
Manual / Cowork       →   company_intake.py    (POST/ups) →   drugs for a company's pipeline
Company IR / model    →   company_enrichment.py    (ups)  →   drug fields (22 sb_upsert calls)
Model                 →   molecule_enrichment.py (POST/PATCH) → modality/PK/PD fields
Model                 →   inference_rules.py      (POST) →   inferred fields
Ontology              →   normalize_targets_modality.py (PATCH) → target/modality normalization
Sources               →   verify_sources.py  (POST/PATCH) →   source_url, validation fields
Catalog               →   catalog_backfill.py     (POST) →   catalog/category fields
Daily brief           →   write_meridian.py  (POST/PATCH) →   drug fields during issue gen
                                                              (+ ~6 more scripts referencing drugs)
        │
        ▼
   [ no identity gate ]  ← duplicates enter here (sl-325 vs sl325, bsi-045b vs bosakitug)
        │
        ▼
   drugs table  ──→  drug_targets / drug_indications / drug_sources / entity_edges / intel_fact_entities
        │
        ▼
   FRONTEND: index.html reads drugs (+ joins) for the catalog, area tabs, drug cards
```

## Where each governance rule should be enforced (but isn't, consistently)

| Rule (CLAUDE.md) | Should fire on write | Today |
|---|---|---|
| §1 `company_id` = originator; latest-owner display | every drug insert/update | ad-hoc per script |
| §1a `originator_company_id` only when known & differs | insert/update | rarely set |
| §3 co-dev → `partner_company`, not `company_id` | insert/update | inconsistent |
| §4 `brand_name` ⇒ approved stage | insert/update | not enforced (governance_violations catches after) |
| §5 source required for every fact | every write | partially (drug_sources) |
| identity: no duplicate molecule rows | every insert | **not enforced → dup rows** |
| target = molecular only | insert/update | inconsistent |

## Target flow (after `DrugWriter`)

```
any collector / enricher / inference / intake
        │  (produces a candidate record + a source)
        ▼
   DrugWriter.upsert(record, source)         ← THE ONLY WRITE PATH
        ├─ resolve identity (entity_matcher) → canonical id, no new dup
        ├─ apply governance (§1,1a,3,4,5; target molecular-only)
        ├─ dedup-on-write (match name/aliases/dev_code/inn)
        ├─ write
        └─ validation query (confirm invariants) + audit log
        │
        ▼
   drugs table   (every row provably governed + sourced)
```

## Active vs one-off (finalize before migration)
- **Active (in a workflow / orchestrator):** `company_enrichment.py` (backfill-bd-angle), `research.py` (graph-rebuild), `write_meridian.py` (meridian-write, on-demand).
- **On-demand (Cowork, API spend paused):** `drug_intake.py`, `company_intake.py`, `molecule_enrichment.py`, `inference_rules.py`, `normalize_targets_modality.py`, `verify_sources.py`, `catalog_backfill.py`.
- **One-off / migration:** `one_time_migration.py`, `apply_drug_sources_migration.py`.

**Migration order for DrugWriter:** intake scripts first (where dups are born) → enrichment → normalization → meridian. Each cutover keeps the script's entrypoint, swaps its `sb_upsert('drugs',...)` for `DrugWriter.upsert(...)`, and is validated before the next.
