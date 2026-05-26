# Enrichment Observability Plan — Session 64
**Date:** 2026-05-26  
**Workstream:** WS-D — Nightly Enrichment Observability  
**Priority:** P1 (implement after C1/C2 stable)

---

## Problem Statement

After every nightly enrichment run, there is currently no structured record of:
- What was searched
- What was found vs. skipped
- What changed in Supabase
- What changed on the dashboard
- What needs human review

The only audit path today is reading enrichment logs manually. No queryable history.

---

## Proposed Schema: `enrichment_runs` Table

```sql
CREATE TABLE IF NOT EXISTS enrichment_runs (
  id                          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id                      TEXT NOT NULL UNIQUE,  -- e.g. 'enrich-20260526-tl1a'
  run_type                    TEXT NOT NULL CHECK (run_type IN ('area','company','drug','news','manual')),
  source_script               TEXT NOT NULL,          -- 'company_enrichment.py' | 'research.py' | 'write_meridian.py'
  area_id                     TEXT,                   -- area context if applicable
  context_type                TEXT,                   -- 'company' | 'drug' | 'area'
  context_id                  TEXT,                   -- company_id or drug_id or area_id
  started_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at                TIMESTAMPTZ,
  status                      TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','completed','failed','partial')),

  -- Research inputs
  search_queries_used         JSONB,                  -- array of query strings sent to search
  sources_checked             INTEGER DEFAULT 0,
  articles_found              INTEGER DEFAULT 0,
  articles_skipped_duplicate  INTEGER DEFAULT 0,

  -- Entity detection
  entities_detected           JSONB,                  -- {drugs:[], companies:[], targets:[], indications:[]}
  drugs_matched               INTEGER DEFAULT 0,
  companies_matched           INTEGER DEFAULT 0,
  targets_matched             INTEGER DEFAULT 0,
  indications_matched         INTEGER DEFAULT 0,

  -- Supabase write summary
  records_created_json        JSONB,                  -- {table: count, ...}
  records_updated_json        JSONB,                  -- {table: count, ...}
  records_skipped_json        JSONB,                  -- {table: count, ...}
  skipped_reasons_json        JSONB,                  -- {reason: count, ...}

  -- Quality signals
  confidence_distribution_json JSONB,                 -- {A:N, B:N, C:N, inferred:N}
  validation_flags_json       JSONB,                  -- array of flag objects
  ecc_candidates_json         JSONB,                  -- array of entity_consistency_check candidates
  dashboard_sections_affected_json JSONB,             -- {section_id: change_type, ...}

  -- Error log
  error_log                   TEXT,

  -- Timestamps
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_er_run_id      ON enrichment_runs (run_id);
CREATE INDEX IF NOT EXISTS idx_er_area_id     ON enrichment_runs (area_id);
CREATE INDEX IF NOT EXISTS idx_er_status      ON enrichment_runs (status);
CREATE INDEX IF NOT EXISTS idx_er_started_at  ON enrichment_runs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_er_script      ON enrichment_runs (source_script);

-- RLS
ALTER TABLE enrichment_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_enrichment_runs"    ON enrichment_runs FOR SELECT USING (true);
CREATE POLICY "service_write_enrichment_runs" ON enrichment_runs FOR ALL USING (auth.role() = 'service_role');
```

---

## Implementation: company_enrichment.py

### Where to add

Add a `EnrichmentRunLogger` class to `company_enrichment.py`. Initialize at run start, accumulate counts throughout, flush to Supabase at run end.

```python
import uuid, datetime

class EnrichmentRunLogger:
    def __init__(self, area_id, context_type='area', context_id=None):
        self.run_id = f"enrich-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{area_id}"
        self.area_id = area_id
        self.context_type = context_type
        self.context_id = context_id or area_id
        self.started_at = datetime.datetime.utcnow().isoformat()
        self.status = 'running'

        # Counters
        self.sources_checked = 0
        self.articles_found = 0
        self.articles_skipped_duplicate = 0
        self.drugs_matched = 0
        self.companies_matched = 0

        # Detail accumulators
        self.search_queries = []
        self.entities_detected = {'drugs': [], 'companies': [], 'targets': [], 'indications': []}
        self.records_created = {}
        self.records_updated = {}
        self.records_skipped = {}
        self.skipped_reasons = {}
        self.confidence_distribution = {}
        self.validation_flags = []
        self.ecc_candidates = []
        self.dashboard_sections_affected = {}
        self.error_log = None

    def log_search(self, query):
        self.search_queries.append(query)

    def log_article(self, *, is_duplicate=False):
        if is_duplicate:
            self.articles_skipped_duplicate += 1
        else:
            self.articles_found += 1

    def log_entity(self, entity_type, entity_id):
        if entity_type in self.entities_detected:
            self.entities_detected[entity_type].append(entity_id)
        if entity_type == 'drugs':
            self.drugs_matched += 1
        elif entity_type == 'companies':
            self.companies_matched += 1

    def log_write(self, table, operation='created'):
        target = self.records_created if operation == 'created' else self.records_updated
        target[table] = target.get(table, 0) + 1

    def log_skip(self, table, reason='already_validated'):
        self.records_skipped[table] = self.records_skipped.get(table, 0) + 1
        self.skipped_reasons[reason] = self.skipped_reasons.get(reason, 0) + 1

    def log_confidence(self, level):
        self.confidence_distribution[level] = self.confidence_distribution.get(level, 0) + 1

    def log_validation_flag(self, flag):
        self.validation_flags.append(flag)

    def log_ecc_candidate(self, candidate):
        self.ecc_candidates.append(candidate)

    def log_dashboard_change(self, section_id, change_type):
        self.dashboard_sections_affected[section_id] = change_type

    def flush(self, sb_service_key, supabase_url, status='completed', error=None):
        """Write run record to enrichment_runs table."""
        if error:
            self.error_log = str(error)
            self.status = 'failed'
        else:
            self.status = status

        payload = {
            'run_id':                        self.run_id,
            'run_type':                      'area',
            'source_script':                 'company_enrichment.py',
            'area_id':                       self.area_id,
            'context_type':                  self.context_type,
            'context_id':                    self.context_id,
            'started_at':                    self.started_at,
            'completed_at':                  datetime.datetime.utcnow().isoformat(),
            'status':                        self.status,
            'search_queries_used':           self.search_queries,
            'sources_checked':               self.sources_checked,
            'articles_found':                self.articles_found,
            'articles_skipped_duplicate':    self.articles_skipped_duplicate,
            'entities_detected':             self.entities_detected,
            'drugs_matched':                 self.drugs_matched,
            'companies_matched':             self.companies_matched,
            'records_created_json':          self.records_created,
            'records_updated_json':          self.records_updated,
            'records_skipped_json':          self.records_skipped,
            'skipped_reasons_json':          self.skipped_reasons,
            'confidence_distribution_json':  self.confidence_distribution,
            'validation_flags_json':         self.validation_flags,
            'ecc_candidates_json':           self.ecc_candidates,
            'dashboard_sections_affected_json': self.dashboard_sections_affected,
            'error_log':                     self.error_log,
        }

        import requests
        try:
            r = requests.post(
                f"{supabase_url}/rest/v1/enrichment_runs",
                headers={
                    'apikey': sb_service_key,
                    'Authorization': f'Bearer {sb_service_key}',
                    'Content-Type': 'application/json',
                    'Prefer': 'return=minimal',
                },
                json=payload,
                timeout=10,
            )
            r.raise_for_status()
            return self.run_id
        except Exception as e:
            print(f"[EnrichmentRunLogger] Failed to flush run record: {e}")
            return None
```

### Integration points in company_enrichment.py

1. **Run start** — initialize `EnrichmentRunLogger` per area run
2. **Article dedup check** — call `logger.log_article(is_duplicate=True)` when URL already in intel
3. **Entity match** — call `logger.log_entity('drugs', drug_id)` when matched in context
4. **Upsert success** — call `logger.log_write('drug_area_scores', 'updated')` after each write
5. **Skip decision** — call `logger.log_skip('drugs', reason='already_validated')` when field is high-confidence and skipped
6. **Confidence record** — call `logger.log_confidence(confidence_level)` after each LLM classification
7. **Run end** — call `logger.flush(...)` in finally block

### Skip-field logic (addresses "smart skip" requirement)

Fields that should NOT be re-enriched unless trigger condition is met:

| Field | Skip condition | Re-enrich trigger |
|---|---|---|
| `ailux_angle` | confidence_level = 'A' | New article directly contradicts; ownership/stage changes |
| `overlap` | confidence_level IN ('A','B') | Stage change; new clinical data |
| `overlap_rationale` | Same as overlap | Same |
| `mechanism` | confidence_level = 'A' | Never — only manual override |
| `stage` | approval_date set OR stage = 'Approved' | Clinical result reported |
| `source_url` | source_url IS NOT NULL AND confidence_level = 'A' | Source becomes 404 |
| `partnership_type` | partnership_verified = true | Partnership dissolution signal |

Implementation: add `_should_skip_field(drug_row, field_name)` function that returns `(bool, reason)`.

---

## Implementation: research.py

Lighter-weight logging for the news/intel pipeline:

```python
class ResearchRunLogger:
    """Lightweight logger for research.py nightly runs."""
    def __init__(self, run_date):
        self.run_id = f"research-{run_date}"
        self.articles_fetched = 0
        self.articles_skipped = 0
        self.intel_rows_written = 0
        self.deal_rows_written = 0
        self.catalyst_rows_written = 0
        self.company_signals_written = 0
        self.entity_edges_written = 0
        self.errors = []
```

Flush to `enrichment_runs` with `run_type='news'` and `source_script='research.py'` at run end.

---

## Answerable Questions After Implementation

| Question | Source |
|---|---|
| "What changed overnight?" | `enrichment_runs WHERE started_at > NOW()-1d ORDER BY started_at DESC` |
| "What did Claude enrich vs skip?" | `skipped_reasons_json`, `records_updated_json`, `articles_skipped_duplicate` |
| "What changed in Supabase?" | `records_created_json + records_updated_json` |
| "What changed on the dashboard?" | `dashboard_sections_affected_json` |
| "Which drugs were newly classified?" | join `enrichment_runs.entities_detected` with drugs table |
| "Is enrichment quality drifting?" | `confidence_distribution_json` trend over runs |
| "What needs human review?" | `validation_flags_json`, `ecc_candidates_json` |

---

## nightly_health_report.py Additions

Add these five count queries to the existing health report:

```python
# 1. Intel pipeline throughput (last 24h)
intel_24h = sb_service.from_('intel').select('*', count='exact', head=True)\
    .gte('created_at', yesterday_iso).execute()

# 2. field_backfill_preview pending queue
fbp_pending = sb_service.from_('field_backfill_preview').select('*', count='exact', head=True)\
    .eq('preview_status', 'pending').execute()

# 3. news_articles freshness (last 24h)
news_24h = sb_service.from_('news_articles').select('*', count='exact', head=True)\
    .gte('updated_at', yesterday_iso).execute()

# 4. catalysts added last 7d
cats_7d = sb_service.from_('catalysts').select('*', count='exact', head=True)\
    .gte('created_at', week_ago_iso).execute()

# 5. deals added last 7d
deals_7d = sb_service.from_('deals').select('*', count='exact', head=True)\
    .gte('created_at', week_ago_iso).execute()
```

---

## Implementation Order

1. **Apply DDL** to Supabase (SQL Editor)
2. **Add `EnrichmentRunLogger` class** to `company_enrichment.py` (~80 lines)
3. **Wire logging calls** into existing enrichment loop (~15 insertion points)
4. **Add `ResearchRunLogger`** to `research.py` (~30 lines + 5 insertion points)
5. **Update `nightly_health_report.py`** with 5 additional count queries
6. **Verify**: run enrichment for one area, confirm `enrichment_runs` row is written

**Effort estimate:** 1 session (Session 66 per roadmap — after C11 parallel-write is underway)

---

## Duplicate Memory Beyond 7-Day URL Dedup

Current: `intel.source_url` dedup window = 7 days.

Proposed extension for high-quality content:
- For articles that produced confidence_level = 'A' enrichments, store URL in `enrichment_runs.search_queries_used` with a `seen_at` timestamp
- Before re-fetching: query `enrichment_runs WHERE search_queries_used @> '["url"]'::jsonb AND completed_at > NOW()-90d`
- If found with 'A' confidence enrichment in last 90 days, skip unless trigger condition met

This is a future optimization — implement after basic logging is proven.

---

*Session 64 — 2026-05-26. Design only — no Supabase or script changes made this session.*
