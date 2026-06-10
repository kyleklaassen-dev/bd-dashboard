# Meridian Constitution

**Status:** v1, 2026-06-09. The short, enforceable statement of what Meridian treats as truth and what may change it. Distilled from existing governance (CLAUDE.md §1–6, memory decisions) — not invented. Keep this short; mechanics live in `governance_table.md` and `decisions.md`.

## 1. What Meridian is
A competitive-intelligence and BD-strategy platform whose value derives upward from the patient: **Patient → Indication → Target → Company**. The molecule and the patient are the most important things. Meridian is a *trusted* intelligence system: every claim is traceable to a source.

## 2. What counts as truth
A fact is "true" in Meridian only if it is **(a) stored in Supabase and (b) backed by a source row in `drug_sources`/`intel_facts` with a real URL.** A fact that lives only in chat, memory, or a doc is not truth. Never fabricate URLs — omit rather than guess.

## 3. Source hierarchy (when sources disagree)
`ClinicalTrials.gov / regulatory filings` > `company IR / press release` > `peer-reviewed publication` > `reputable news` > `model inference`. A lower-tier source never overwrites a higher-tier confirmed fact; it is recorded with lower `confidence` and surfaced as contradiction, not silently merged.

## 4. What may modify truth
- **Core entities (`drugs`, `companies`, `entity_edges`, `catalysts`) may be written through their single designated Writer only.** Collectors, enrichers, inference, and intake **propose**; the Writer **decides** (identity, governance, validation). No script writes a core table directly.
- Identity is canonical: a real-world molecule/company has exactly one row. New rows are created only when identity resolution finds no existing match.

## 5. What is immutable / protected
- `company_id` on a drug = **originator** (never rewritten to a licensee). Ownership/licensing lives in partnerships/deals.
- Prior names are never lost (alias capture on every write).
- Source rows are append-only; corrections add a new row, they don't erase history.

## 6. What requires validation (always)
Every write path runs a **validation query after writing** and refuses/flags on invariant breach: no duplicate identity, `brand_name ⇒ approved stage`, target = molecular-only, source present, attribution rules (§1/§3). No DB write path ships without this.

## 7. What requires human approval (Kyle)
- Deleting/merging entities or dropping tables (irreversible).
- Flipping a drug to `approved` without a recognized approval milestone.
- Changing company `status` to `acquired` (default is `subsidiary`).
- Any change to this Constitution.

## 8. How we change the system
Audit → consolidate → enforce. Small, reversible, tested changes. Deprecate, don't ambiguously delete. Record every architectural decision in `decisions.md` (ADR) so it isn't re-debated. **No new features until the stabilization phases (see `STABILIZATION_PLAN.md`) are green.**
