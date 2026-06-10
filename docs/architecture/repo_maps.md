# Meridian Repo Maps

**Status:** v1, 2026-06-09. The "mental maps" for understanding the repo at a glance. Companion to `drug_lifecycle.md` (data flow for drugs) and `database/governance_table.md` (the database stability map).

---

## 1. Structure map (file → folder → status)

```
BD Platform/
├── index.html              ACTIVE   the dashboard (~34k lines; Phase 4 split target)
├── CLAUDE.md               ACTIVE   operating instructions (slim; detail in /docs)
├── src/                    NEW      production layer (Single Writer Pattern)
│   └── database/           ACTIVE   client.py + drug_writer/company_writer/edge_writer
│   └── (identity, ingestion, ontology, enrichment, scoring, frontend, utils = staged dirs)
├── scripts/                ACTIVE   ~185 pipeline scripts (enrichment, research, intake, graph)
│   ├── maintenance/        ACTIVE   entity_matcher tools: dedupe_entities, graph_audit, link_extras
│   └── one_off/            ARCHIVE  retired audit/debug one-offs
├── tests/database/         NEW      DrugWriter + writer regression suites (read-only)
├── migrations/             ACTIVE   155 numbered SQL; PROPOSED_*.sql = staged for review
├── docs/                   ACTIVE   architecture/ database/ audits/ decisions.md constitution.md
│   └── archive/            ARCHIVE  full prior CLAUDE.md + deprecated plans
└── archive/                ARCHIVE  dashboard_builds/ (build_v*.py), html_backups/
```
Status legend: ACTIVE (live), NEW (this sprint), ARCHIVE (historical, kept for reference), staged (created, not yet populated).

## 2. Workflow map (data flow + the 50 GitHub workflows, grouped)

```
EXTERNAL SOURCES                 INGESTION              IDENTITY/ONTOLOGY      ENRICHMENT           GRAPH                 PRODUCTS
CT.gov, SEC, PubMed,   ──▶  meridian-research,    ──▶  entity_matcher,   ──▶  company-enrichment,──▶ meridian-graph-  ──▶ meridian-write,
openFDA, EMA, news,         meridian-free-ingest,      ontology mapping       backfill-bd-angle,     rebuild,             patient-briefs,
PDFs (Wedbush/Cowen)        chunk_extract,             (drug_targets/         completeness-          structural-edges,    landscape-briefing,
                            abstract-fetcher,          indications)           scoring                deal-edges,          morning/evening,
                            patent-sweep,                                                            verify-edges         bd-recommender
                            ictrp/cde-china,
                            fetch-homepage-news,
                            review_submitted_intel
        │                                                                                                                      │
        ▼                                                                                                                      ▼
  VALIDATION/GOVERNANCE: run-validation-tests, content-verifier, source-verifier, trial-audit, audit-retention, pipeline-health/monitor
        │
        ▼
  DATABASE (Supabase) ──────────────────────────────────────────────────────────────────────────▶ FRONTEND (index.html, GitHub Pages)
```
Workflow groups: **ingestion** (research, free-ingest, chunk_extract, abstract-fetcher, patent-sweep, china harvest, homepage-news, submitted-intel) · **enrichment** (company-enrichment, backfill-*, completeness/landscape scoring, score-foresight) · **graph** (graph-rebuild, structural-edges, deal-edges, verify-edges, derived-rebuild) · **products** (meridian-write, briefs, recommender, ranking-snapshots, summaries) · **validation/ops** (run-validation-tests, content/source-verifier, trial-audit, pipeline-health/monitor, audit-retention, stock-prices) · **migration** (apply-migration, apply-drug-sources-migration). **Note:** API-spend workflows are paused; most run on-demand.

## 3. Frontend dependency map (what index.html reads)

| Table | reads | Notes |
|---|---|---|
| `drugs` | 27 | core catalog / drug cards |
| `deals` | 23 | BD / deals views |
| `companies` | 23 | company cards |
| `catalysts` | 20 | calendar / timeline |
| `drug_targets` | 17 | area tabs (ontology — ADR-002) |
| `intel` / `intel_facts` | 16 | research-intelligence panels |
| `drug_area_scores` | 14 | scoring (note: `drug_areas` legacy still read 8×) |
| `drug_indications` | 12 | indication tabs |
| `trials` | 10 | trial readouts |
| `news_articles` | 9 | homepage news |
| `company_profiles` | 8 | ⚠️ read but EMPTY (dark feature — populate) |

**Risk:** the UI reads several empty tables (`company_profiles`, `company_areas`) — dark features. And it still reads legacy `drug_areas` (ADR-002 fallback to remove in Phase 3).

## 4. Claude working map (where to look)

- **Read first (every session):** `docs/STABILIZATION_PLAN.md`, `CLAUDE.md`, `NEXT_SESSION.md`.
- **Source of truth (don't contradict):** `docs/constitution.md`, `docs/database/governance_table.md`, `docs/decisions.md` (ADR), `docs/architecture/drug_lifecycle.md`.
- **Use for entity work:** `scripts/entity_matcher.py` (resolver), `src/database/*_writer.py` (writes), `scripts/maintenance/` (dedupe/audit/link).
- **Avoid unless asked:** `archive/**`, `scripts/one_off/**`, `index.html` internals (huge; Phase 4), the 17 `build_v*.py` history.
- **Never:** add a new ad-hoc `sb_upsert('drugs'/'companies'/'entity_edges', …)` path — use the Writers.

## 5. Database stability map
See `docs/database/governance_table.md` — core tables, sole writers, validation-per-write, risky columns, source hierarchy. Key facts: `entity_edges` is now idempotent (UNIQUE constraint, ADR-009); core-table writes are migrating to the Writer layer (ADR-010).
