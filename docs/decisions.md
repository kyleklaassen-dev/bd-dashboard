# Architecture Decision Register (ADR)

**Status:** v1, 2026-06-09. Institutional memory so decisions aren't re-debated. Consolidated from CLAUDE.md and the ~30 memory files. Append new ADRs; never rewrite history (supersede instead).

Format: `ADR-NNN — Title (date) — Decision · Why · Status`.

---

**ADR-001 — Company identity is canonical & originator-anchored (2026-05).** `drugs.company_id` = originator (inventor) always; licensees live in `company_partnerships`/`deals`. *Why:* ownership ≠ identity; prevents attribution churn. *Status:* active (Constitution §5). Refined by ADR-009.

**ADR-002 — `drug_targets` replaced `drug_areas` for biological data (2026-05).** Area tabs read the ontology (`drug_targets`/`drug_indications`) via `_makeAreaPI`, not legacy `drug_areas`. *Why:* normalized ontology over flat legacy table. *Status:* active; legacy fallback reads remain in `index.html` (to be removed in Phase 3).

**ADR-003 — Source documentation is mandatory (2026-05).** Every fact in Supabase must have a source row in `drug_sources`/`intel_facts` with a real URL. *Why:* trusted intelligence; no unverifiable claims. *Status:* active (Constitution §2).

**ADR-004 — Default company `status='subsidiary'` (2026-05).** Only `acquired` when provably dissolved (dissolution test). *Why:* avoid wrongly hiding active companies. *Status:* active.

**ADR-005 — `brand_name` implies approved stage (2026-05).** Any drug with a brand_name must be in an approved stage; "—" is invalid. *Why:* consistency. *Status:* active; `governance_violations` tracks breaches (to become a hard check in DrugWriter).

**ADR-006 — Latest/notable owner is displayed primary, originator secondary (2026-06-07).** `company_id` = displayed owner; `originator_company_id` (nullable) records the originator when known and different. *Why:* market associates assets with current owner (e.g. Skyrizi→AbbVie, orig. Boehringer) without losing provenance. *Status:* active (Constitution §5; refines ADR-001).

**ADR-007 — Knowledge graph = two layers (2026-06-08).** `entity_edges` (structural: TARGETS, COMPETES_WITH, DEVELOPED_BY, …) + `intel_fact_entities` (fact→entity). Cards read the graph, not raw subject_id. *Why:* traversable relationships. *Status:* active.

**ADR-008 — Shared `entity_matcher` is the one entity resolver (2026-06-09).** All entity linking (facts, market tables, edges) uses `scripts/entity_matcher.py` with an ambiguity guard. *Why:* one resolver, consistent linking, no mis-attribution. *Status:* active.

**ADR-009 — `entity_edges` is idempotent at the DB layer (2026-06-09).** Added `UNIQUE(subject_id,predicate,object_id)`. *Why:* edge writes were duplicating; constraint makes them safe. *Status:* active.

**ADR-010 — Single Writer Pattern (2026-06-09, ADOPTED, in progress).** Each core entity (drug, company, edge, catalyst) gets exactly one Writer that enforces identity + governance + validation; collectors/enrichers propose only. Direct writes to core tables to be physically blocked. *Why:* 30 scripts with their own `sb_upsert` = no owner of truth → duplicates/drift. *Status:* DrugWriter being built (Phase 2). Enforcement (permission boundary) staged for review.

**ADR-011 — Stabilization before features (2026-06-09).** No new features until stabilization Phases 1–3 are green. *Why:* optimize for clarity, reversibility, testability, DB stability. *Status:* active (`STABILIZATION_PLAN.md`).

---
*Older operational details (deploy recipes, schema specifics, pipeline notes) remain in `/docs` and memory; this register captures only durable architectural decisions.*
