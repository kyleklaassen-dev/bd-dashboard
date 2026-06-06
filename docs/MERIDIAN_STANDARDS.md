# Meridian — Shared Vocabulary & Connection Standards

**Purpose.** One canonical wording for the platform so the dashboard, the workflow map, the pipelines, and any explanation to a third party all use the same terms. When everything is named the same way, the system becomes teachable and the connections become obvious. Adopt these terms in new UI copy, comments, and docs; migrate old wording opportunistically.

Status: v1 — established 2026-06-04. This is a living standard.

---

## 1. The pipeline stages (always in this order)

Every workflow belongs to exactly one stage. Use these names everywhere.

| Stage | One-line definition | Canonical examples |
|---|---|---|
| **Ingestion** | Pull raw signal from the outside world into Supabase | `research.py`, `ct_gov_sync.py`, `fetch_homepage_news.py`, `pipeline_monitor.py` |
| **Enrichment** | Turn raw signal into structured, attributed intelligence | `company_enrichment.py`, `molecule_enrichment.py`, `process_queue_item.py` |
| **Scoring** | Quantify competitive position, coverage, ranking | `apply_competitive_scores_v56.py`, `compute_landscape_scores.py`, `compute_coverage.py` |
| **Validation** | Prove facts against sources, detect drift/conflicts | `validate_ground_truth.py`, `conflict_detector.py`, `company_validator.py` |
| **Synthesis** | Compose human-facing intelligence products | `write_meridian.py`, `morning_summary.py` |
| **Presentation** | Surface intelligence to the user | `index.html` dashboard, Meridian Issue, S3 banner |

Cross-cutting: **Human review** (Kyle's confirmations) and the **Flywheel** (review → training signal → better enrichment).

---

## 2. Table connection states (the connectivity taxonomy)

Every Supabase table is in exactly one state. This is the language for "what is and isn't connected."

| State | Definition | Action |
|---|---|---|
| **Surfaced** | A pipeline writes it **and** the dashboard reads it | Healthy — keep |
| **Dark** | A pipeline actively writes (and usually reads) it, but the user never sees it | Surface — it's live data, a connection not new collection |
| **Inert / Abandoned** | Has rows, but **no script of any kind** writes or reads it — seeded once via SQL, now stale | Wire a producer to revive, or retire. Do **not** surface as-is (stale) |
| **Orphan-write** | Written by a pipeline, read by **nothing** | Wire a consumer or retire |
| **Trigger-fed** | Written by a DB trigger (audit/capture), not a script | Internal by design — not an orphan |
| **Infra** | Logs, link tables, aliases, queues — internal by design | Leave internal |
| **Scaffolded** | **0 rows** but has an `updated_at`/audit trigger — built for a planned feature, unfed | Populate or drop |
| **Dead** | Empty **and** no trigger, producer, or consumer | Drop |

Current census (re-verified 2026-06-04, 167 tables, trigger-aware): **74 Surfaced · 7 Dark (surface-ready) · 9 Inert/Abandoned · 3 Orphan-write · ~31 Infra · 38 other unsurfaced · 7 Scaffolded-empty.** Producer reality: **110 scripts exist, only 30 are scheduled; 66 DB triggers feed the audit trail across 38 tables** (a genuine strength — every change to core tables is captured in `field_change_audit`).

---

## 3. Run-health states (workflow status)

Use these exact words for any workflow/pipeline status (matches the map's Run-health view).

- **Green** — last scheduled run succeeded.
- **Failing** — last run errored (and nothing alerted — see monitoring gap).
- **Never run** — scheduled but zero successful runs on record.
- **Fixed** — was failing, corrected, and re-verified green.

---

## 4. The intelligence hierarchy (the "why")

Value flows **upward** from the patient. Use this ordering in any explanation, and tag intelligence to its layer.

**Patient → Indication → Target → Molecule → Company → Deal.**

A fact is only as valuable as the patient need it ultimately serves. Competitive and BD intelligence sit on top of, and derive from, patient and molecular reality.

---

## 5. Scoring vocabulary (one name per metric)

| Canonical term | What it measures | Source table |
|---|---|---|
| **Competitive score** (`drug_competitive_scores`) | How a drug competes within an area | `drug_competitive_scores` |
| **Landscape-dependency score (LDS)** | How complete/trustworthy an area's landscape is | `competitive_landscapes` |
| **Coverage score** | How fully a drug/area is characterized | `coverage_scores` |
| **Evidence tier** | Confidence level of a stored fact | `drug_sources.confidence` |
| **Strategic value** | How much Kyle should care (BD importance) | (planned) |

Confidence words — use only these three, everywhere: **confirmed · inferred · unverified**.

---

## 6. Naming conventions (reduce drift)

- **Originator vs owner.** `drugs.company_id` = originator, always. Licensee/owner relationships live in `company_partnerships` / `deals`. Never overload `company_id`.
- **Targets** = molecular targets only (`TL1A × IL-23p19`). Never embed modality or company.
- **Disease area** is the canonical phrase (not "therapeutic area" in UI copy); the area id is lowercase (`tl1a`, `ibd`, `igf1r`).
- **One queue name per purpose.** Today there are four (`research_queue`, `discovery_queue`, `enrichment_queue`, `intelligence_debt_queue`) — document each one's distinct role or consolidate.
- **Secrets/env:** standardize on `SUPABASE_SERVICE_KEY` (two workflows still pass `SUPABASE_SERVICE_ROLE_KEY`).
- **Freshness/“fresh data.”** Use "fresh intelligence" for new data arriving; "stale" for data past its review window.

---

## 7. Connection definition (when is something "connected"?)

A relationship is **connected** when: (1) a pipeline writes the data **with a source**, (2) a downstream pipeline or the dashboard reads it, and (3) the user can trace it back to that source. Anything missing one of these three is a connection gap — see the workflow map's Table-Connectivity view and gap list.
