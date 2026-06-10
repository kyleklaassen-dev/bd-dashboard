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

## CORRECTED write-path inventory (verified 2026-06-09)
Precise scan (POST/PATCH to `/rest/v1/drugs` or `sb_upsert('drugs')`) — far fewer real writers than the loose grep suggested:
- ✅ **`approve_discovery.py`** — the BIRTH POINT (promotes `discovery_queue` → `drugs`). Used its own `drug_slugify` + exact-id existence check → the source of slug-mismatch dups (sl-325 vs sl325). **MIGRATED to DrugWriter 2026-06-09** (canonical identity resolves before create).
- `molecule_enrichment.py` — PATCHes `canonical_drug_id` (field update). Migrate next.
- `seed_tl1a_companies.py` — seeder `sb_upsert('drugs')`. Migrate.
- `write_meridian.py` (line ~390) — writes drug fields during issue gen. Migrate.
- **NOT drug-writers (reads only):** `drug_intake.py` (writes `discovery_queue`, reads drugs for resolution), `company_enrichment.py` (writes trials/catalysts/company_*/drug_areas — never the `drugs` table).

**Migration order:** ✅ approve_discovery (done) → molecule_enrichment → seed_tl1a_companies → write_meridian. Each keeps its entrypoint, swaps the write for `DrugWriter.upsert(...)`, validated before the next. Then apply enforcement (`PROPOSED_drugwriter_enforcement.sql`).
