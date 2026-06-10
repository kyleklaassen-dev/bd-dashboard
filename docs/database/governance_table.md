# Data Governance Table

**Status:** v1, 2026-06-09. Per core table: who owns it, the sole writer, the validation that must pass on write, and the source hierarchy. This is the spec the Writer layer enforces (Constitution §4, §6).

## Core entities (Single Writer Pattern target)

| Table | Owner domain | Sole writer (target) | Validation on write | Source hierarchy |
|---|---|---|---|---|
| `drugs` | Drug | `DrugWriter` | identity (no dup molecule); `company_id`=originator; `brand_name`⇒approved; target molecular-only; source present | CT.gov > company IR > publication > news > inference |
| `companies` | Company | `CompanyWriter` | identity (no dup); default `status='subsidiary'`; `parent_company_id` set for sub/acq | registry (GLEIF/SEC) > company site > news |
| `entity_edges` | Graph | `EdgeWriter` | predicate ∈ allowed set; `generation_method` ∈ deterministic\|manual; **UNIQUE(subject_id,predicate,object_id)** ✅ | deterministic seeders > manual curation |
| `catalysts` | Catalyst | `CatalystWriter` | linked to drug or company; date sane; dedup on (drug,event,date) | CT.gov > company IR > news |

## Supporting tables (write through the owning domain's writer or its module)

| Table group | Writer/module | Key invariant |
|---|---|---|
| `drug_targets` / `drug_indications` | ontology module (via DrugWriter on drug change) | canonical target/indication id; UNIQUE(drug,target/indication) |
| `drug_sources` / `intel_facts` | source/intel module | append-only; real URL; `content_confirms_claim` set |
| `intel_fact_entities` | `build_fact_graph` (shared `entity_matcher`) | UNIQUE(fact_id,entity_id,role) ✅ |
| `company_partnerships` / `deals` | CompanyWriter / deal module | `company_id`=lead, `partner_company`=originator; verified flag |
| `market_landscape` / `rx_market_tracker` | ingest + `link_entities` | entity_id resolved via matcher |

## Risky columns (handle only via the writer)
- `drugs.company_id` — originator, never a licensee (Constitution §5).
- `drugs.stage` — managed by `_resolveStage`; never hand-set to approved without milestone.
- `drugs.brand_name` — implies approved; "—" is invalid (clear to null).
- `companies.status` — default subsidiary; `acquired` needs the dissolution test + approval.
- Non-standard FK columns that escape tooling: `asset_transfer_history.from_entity_id/to_entity_id`, `entity_edges.subject_id/object_id`, `ownership_edges.subject_id`.

## Validation queries (run after every write)
- **Dup identity:** `select name,count(*) from drugs group by lower(name) having count(*)>1` → must be empty.
- **brand⇒approved:** `select id from drugs where brand_name is not null and stage not ilike 'approved%'` → empty.
- **orphan check:** every drug appears in `entity_edges` (subject or object).
- **source presence:** every new fact has a `drug_sources`/`intel_facts` row with a URL.
