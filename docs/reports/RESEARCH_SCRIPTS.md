# The three research scripts — canonical roles (they are NOT redundant)

A recurring gap-registry note flagged "three overlapping research scripts." On inspection
they have **distinct, complementary roles** — three different stages, not three copies of
one job. This doc is the canonical division of labor so the boundary stays clear.

| Script | Role | Granularity | Writes | Scheduled in |
|--------|------|-------------|--------|--------------|
| **research.py** | **News/intel ingestion engine.** Pulls biopharma RSS, fetches full text, extracts structured intel with Claude Sonnet (grounded in Ailux context). | Broad daily sweep across the whole landscape | `intel`, `deals`, `catalysts`, `catalyst_calendar`, `companies`, `intelligence_discoveries`, `asset_differentiation_profiles`, … | meridian-research.yml (2 AM ET Mon–Sat), validation-research.yml |
| **research_intelligence.py** | **Coverage-scoring + gap-surfacing engine (meta-layer).** Scores how complete each entity's record is and writes the research queue of what to chase next. | Per-entity completeness assessment | `research_queue` (+ completeness_score/tier on entities) | company-enrichment.yml, completeness-scoring.yml |
| **drug_intelligence_researcher.py** | **Deep per-drug research engine.** Runs all 100 Meridian intelligence questions across 8 domains on a single drug. | One drug, exhaustive | `drug_intelligence_qa` (100 Q&A), `drug_clinical_benchmarks`, `drug_development_timelines` | school-week-sprint.yml |

**The flow:** `research.py` ingests the landscape broadly → `research_intelligence.py` measures
coverage and queues the gaps → `drug_intelligence_researcher.py` does the deep dive on a queued
drug. Ingest → assess → deep-dive. No consolidation needed; keep the three separate.

(If a future change blurs these — e.g. research.py starts writing research_queue, or the deep-dive
starts doing broad ingestion — that's the signal the boundary has drifted and should be restored.)
