# Data Integrity Hardening Plan
_Meridian BD Platform — v1.0 — May 2026_

---

## Operating Principle

> Before more signals enter Meridian, every signal needs a clean destination and one authoritative write path.

Signal volume amplifies whatever data quality exists at the time it arrives. Fixing identity, ownership, and write paths now costs 1–2 days. Fixing them after Tier 1 is live costs weeks.

---

## Implementation Sequence

Items are grouped into three phases: zero-migration fixes (do now), additive schema (do before Tier 1), and restructuring (do during Molecule Database migration).

---

### Phase 0 — Zero Schema Changes (Do Now)

These require no DB migrations, no enrichment script changes, and no dashboard updates. Pure workflow and validation fixes.

---

#### P0-A: Retire evening-update.yml, daily meridian-research.yml ✅ DONE

**Problem:** Both ran `research.py` at 02:30 UTC and 06:00 UTC Mon–Sat. source_url dedup prevented duplicate rows but both incurred Anthropic API costs for ~3.5 hours of overnight articles. `research.py` uses Claude for extraction (LLM-heavy = Tier 2 behavior), not a cheap heuristic scan.

**Fix:**
- `meridian-research.yml` changed to daily `0 6 * * *` ✅
- `evening-update.yml` retired (schedule trigger removed, kept as reference) ✅
- 02:30 UTC slot reserved for future `signal_monitor.py` (Tier 1, no LLM)

**Effort:** 15 min | **Risk:** None | **Done:** 2026-05-21

---

#### P0-B: Validate + reconcile company_areas ↔ company_profiles

**Problem:** `company_profiles` rows can exist for areas not in `company_areas`. AbbVie has a `company_profiles` row for `il4ra` but no `company_areas.il4ra` entry. Orphaned profiles accumulate silently because there's no FK enforcement between the two tables (they're linked only by convention via `(company_id, area_id)`).

**Fix:** Add `reconcile_profiles_areas()` to `identity_health_check.py`:
```python
def reconcile_profiles_areas():
    """Ensure every company_profiles row has a matching company_areas entry."""
    profiles = sb_get('company_profiles', {'select': 'company_id,area_id'})
    areas = {(r['company_id'], r['area_id']) for r in sb_get('company_areas', {'select': 'company_id,area_id'})}
    orphaned = [p for p in profiles if (p['company_id'], p['area_id']) not in areas]
    for p in orphaned:
        log(f"  REPAIR: inserting company_areas ({p['company_id']}, {p['area_id']})")
        sb_upsert('company_areas', {'company_id': p['company_id'], 'area_id': p['area_id']})
    log(f"reconcile_profiles_areas: {len(orphaned)} orphaned profiles repaired")
```
Run in health check and as a repair step in `company_enrichment.py` after enrichment completes.

**Effort:** 1 hr | **Risk:** Low — additive repair only | **Do before Tier 1:** Yes — signal-triggered enrichment will write new profiles; they must land in sync

---

#### P0-C: One-time backfill — stamp company_id on research.py-written deals

**Problem:** `research.py` writes deals with `from_company`/`to_company` as text strings and no `company_id` FK. These deals are invisible in the Company Database profile panel (which queries `deals WHERE company_id = ?`).

**Fix:** One-time migration script using company name → company_id matching:
```python
# In one_time_migration.py or a new backfill_deals.py
deals_without_id = sb_get('deals', {
    'select': 'id,from_company,to_company',
    'company_id': 'is.null'
})
for deal in deals_without_id:
    cid = resolve_company_id(deal['from_company'], company_map)
    if cid:
        sb_patch('deals', {'id': f"eq.{deal['id']}"}, {'company_id': cid})
```
This doesn't need CompanyIdentityResolver — existing `resolve_company_id()` in `research.py` is sufficient for backfill.

**Effort:** 1 hr | **Risk:** Low — existing rows only, no schema change | **Do before Tier 1:** Preferable — cleans up existing data before new deals arrive

---

### Phase 1 — Additive Schema (Before Tier 1)

New tables and columns only. No existing columns removed. All changes backward-compatible. Enrichment and dashboard continue working unchanged while new infrastructure is built alongside.

---

#### P1-A: CompanyIdentityResolver + company_aliases table

**Problem:** Company names arrive as free text in `research.py` (from article extraction), discovery_queue (from enrichment), and future Tier 1 signals. Resolution is currently done via `resolve_company_id()` — substring matching, not logged, not canonical.

**Why this matters for Tier 1:** `signal_monitor.py` will parse company names from press release headlines. If "AbbVie" vs "ABBV" vs "Abbvie" routes to different results, signals accumulate against the wrong entity.

**Schema addition:**
```sql
CREATE TABLE company_aliases (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    text NOT NULL REFERENCES companies(id),
  alias_name    text NOT NULL,
  alias_type    text NOT NULL,  -- 'primary' | 'ticker' | 'abbreviation' | 'common' | 'subsidiary'
  source        text,
  confidence    int DEFAULT 100,
  is_primary    bool DEFAULT false,
  created_at    timestamptz DEFAULT now(),
  UNIQUE(company_id, alias_name)
);
```

**CompanyIdentityResolver class** (new `scripts/company_identity_resolver.py`):
- Same 4-step cascade as DrugIdentityResolver: exact → normalized → fuzzy (flag, don't merge) → log not-found
- Pre-populate aliases from `companies` table: name, ticker, `companies.id` variants
- Log resolution attempts to `identity_audit_log` (operation = 'company_resolve')
- Replace `resolve_company_id()` in research.py with resolver

**Seed data for launch:**
```
abbvie: AbbVie, ABBV, AbbVie Inc
merck: Merck, Merck & Co, MRK, Merck Sharp & Dohme, MSD
sanofi: Sanofi, SNY, Sanofi-Aventis
astrazeneca: AstraZeneca, AZN, AZ
regeneron: Regeneron, REGN, Regeneron Pharmaceuticals
roche: Roche, RHHBY, Genentech (subsidiary)
jnj: Johnson & Johnson, J&J, JNJ, Janssen
... etc.
```

**Effort:** 3–4 hr | **Risk:** Low — new tables, no destructive changes | **Must complete before Tier 1**

---

#### P1-B: intel.primary_company_id

**Problem:** The `intel` table has no `company_id` column — company linkage goes through the `intel_companies` junction table. Every Company Database query for "show me intel for AbbVie" requires a join. With signal volume increasing, this becomes a performance and query-complexity burden.

**Fix:**
```sql
ALTER TABLE intel ADD COLUMN primary_company_id text REFERENCES companies(id);
CREATE INDEX idx_intel_primary_company ON intel(primary_company_id, intel_date DESC);
```

**Backfill:** For existing intel rows with exactly one company in `intel_companies`, stamp that company as `primary_company_id`.

**Update research.py write path:** After resolving company names with CompanyIdentityResolver, set `primary_company_id` to the lead company (first mentioned in the headline, or the "from" company in deals).

**Effort:** 1–2 hr (after P1-A) | **Risk:** Low — nullable column, junction preserved | **Do before Tier 1:** Yes — Tier 1 signals all have a primary company; CO panel intel queries get simpler

---

#### P1-C: Catalyst deduplication — UNIQUE constraint

**Problem:** `research.py` and `company_enrichment.py` can both write catalysts for the same event (e.g., a Phase 3 readout appears in a press release AND gets generated by enrichment). No UNIQUE constraint prevents duplicates.

**Fix:**
```sql
-- Step 1: Identify and remove duplicates (keep earliest created_at)
DELETE FROM catalysts
WHERE id NOT IN (
  SELECT MIN(id) FROM catalysts
  GROUP BY canonical_drug_id, catalyst_type, sort_date
);

-- Step 2: Add UNIQUE constraint
ALTER TABLE catalysts
ADD CONSTRAINT catalysts_canonical_dedup
UNIQUE (canonical_drug_id, catalyst_type, sort_date);
```

**Update research.py:** Change catalyst INSERT to UPSERT with `ON CONFLICT DO NOTHING`.

**Update company_enrichment.py:** Already uses UPSERT — verify ON CONFLICT target matches new constraint.

**Effort:** 1–2 hr | **Risk:** Medium — must audit for existing duplicates before adding constraint (dedup backfill required first) | **Do before Tier 1:** Yes — Tier 1 signals may trigger enrichment that generates catalysts; duplicates compound quickly

---

#### P1-D: drug_area_scores table (parallel write, no removal yet)

**Problem:** `drugs.overlap`, `drugs.cls`, `drugs.overlap_rationale`, `drugs.vs_competitor` are area-relative fields stored on the drug row with no `area_id`. A drug that competes in two areas gets its overlap classification overwritten on each enrichment run for whichever area runs last.

**Correct model:** Drugs are area-agnostic entities. Area-specific competitive interpretation belongs in a separate layer.

**New table:**
```sql
CREATE TABLE drug_area_scores (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  drug_id               text NOT NULL REFERENCES drugs(id),
  canonical_drug_id     text REFERENCES canonical_drugs(canonical_id),
  area_id               text NOT NULL,
  overlap               text,   -- Direct | Adjacent | Same-Space | Watch
  cls                   text,   -- mechanism class label
  overlap_rationale     text,
  vs_ailux_positioning  text,
  area_fit              text,
  area_fit_rationale    text,
  last_enriched_at      timestamptz DEFAULT now(),
  UNIQUE(drug_id, area_id)
);
```

**Phase 1 approach (parallel write, no removal):**
1. Create the table
2. Backfill from existing `drugs` rows — for each drug, attempt to determine its area context from `company_areas` (if a company has one area, the drug's overlap belongs to that area)
3. Update `company_enrichment.py` to write to `drug_area_scores` IN ADDITION to `drugs.overlap` (not instead of — preserve backward compat)
4. Do NOT remove `drugs.overlap` yet — dashboard still reads it

**Phase 2 (during Molecule Database migration):** Update dashboard to read from `drug_area_scores`, then remove `drugs.overlap`/`cls`/`overlap_rationale`.

**Effort:** 2–3 hr for table + backfill + parallel writes | **Risk:** Low (Phase 1 is purely additive) | **Do before Tier 1:** Yes — Tier 1-triggered enrichment should write area scores to the right table from the start

---

### Phase 2 — Restructuring (During Molecule Database Migration)

These changes touch existing columns and read paths. Deferred until the Molecule Database migration gives a natural moment to update all drug/molecule consumers at once.

---

#### P2-A: molecule_intelligence — intrinsic facts only

**Problem:** `molecule_intelligence` has UNIQUE on `canonical_drug_id` (one row per molecule), but enrichment runs per-area with area context. If tulisokibart gets enriched under TL1A, then re-enriched under a future IBD run, area-specific interpretation in the MI row gets overwritten.

**Design decision:** `molecule_intelligence` should hold only intrinsic, area-agnostic molecular facts:
- `format`, `modality`, `valency`, `fc_engineering`, `ig_subclass`
- `epitope`, `affinity_kd`, `lowest_active_dose`
- `safety_observations`, `differentiation_claim`

Area-specific interpretation (`vs_ailux_in_area`, `competitive_rationale`) should move to `drug_area_scores.vs_ailux_positioning`.

**Fix:**
```sql
-- New table for area-specific molecule intelligence
CREATE TABLE molecule_area_intelligence (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_drug_id   text REFERENCES canonical_drugs(canonical_id),
  area_id             text NOT NULL,
  vs_ailux            text,
  competitive_notes   text,
  area_fit_rationale  text,
  last_enriched_at    timestamptz DEFAULT now(),
  UNIQUE(canonical_drug_id, area_id)
);
```

Update `company_enrichment.py` `write_molecule_intelligence()` to:
1. Write intrinsic fields to `molecule_intelligence` (use UPSERT, only update fields that improve on `unknown` status)
2. Write area-specific interpretation to `molecule_area_intelligence`

**Effort:** 2–3 hr | **Risk:** Medium — changes enrichment write path + MI card dashboard render | **When:** During Molecule Database migration

---

#### P2-B: Remove drugs.overlap/cls in favor of drug_area_scores (Phase 2 of P1-D)

After Molecule Database migration updates all dashboard reads to use `drug_area_scores`, remove the legacy columns from `drugs`:
```sql
ALTER TABLE drugs DROP COLUMN overlap;
ALTER TABLE drugs DROP COLUMN cls;
ALTER TABLE drugs DROP COLUMN overlap_rationale;
ALTER TABLE drugs DROP COLUMN vs_competitor;
```

**Effort:** 30 min (after all readers updated) | **Risk:** Low at this point | **When:** End of Molecule Database migration

---

#### P2-C: DRUGS_ALL static array → Supabase (Molecule Database Phase 1)

Remove the hardcoded `DRUGS_ALL` JS array in `index.html`. Replace Drugs-to-Know tab with a Supabase query against `drugs` + `canonical_drugs` + `molecule_intelligence`. This IS the Molecule Database Phase 1 implementation — the tab transforms from a static catalog into a live queryable molecule entity view.

**Effort:** 2–3 hr | **Risk:** Medium — large JS refactor; must handle loading states | **When:** Molecule Database Phase 1

---

### Phase 3 — Reference Refresh (Post-Tier-1)

Low urgency. These are display-layer fixes that matter but don't affect write-path integrity.

---

#### P3-A: PHARMA_DATA hardcoding → companies table

Add financial columns to `companies` table: `revenue_usd_b`, `r_and_d_usd_b`, `market_cap_usd_b`, `employee_count`. Create `reference_refresh.py` to populate from public sources quarterly. Remove DOM-read workaround in CO panel.

**Effort:** 1–2 hr + schema migration | **When:** After Tier 1 is stable

---

## Summary Table

| Item | Phase | Effort | Risk | Before Tier 1? | Status |
|------|-------|--------|------|----------------|--------|
| P0-A: Retire evening-update.yml | P0 | 15 min | None | Yes | ✅ Done 2026-05-21 |
| P0-B: reconcile_profiles_areas() | P0 | 1 hr | Low | Yes | ✅ Done 2026-05-21 |
| P0-C: Backfill deals.company_id | P0 | 1 hr | Low | Preferred | ✅ Done 2026-05-21 |
| P1-A: CompanyIdentityResolver | P1 | 3–4 hr | Low | **Must** | ✅ Done 2026-05-21 |
| P1-B: intel.primary_company_id | P1 | 1–2 hr | Low | Yes | ✅ Done 2026-05-22 |
| P1-C: Catalyst UNIQUE constraint | P1 | 1–2 hr | Medium | Yes | ✅ Done 2026-05-22 |
| P1-D: drug_area_scores (parallel) | P1 | 2–3 hr | Low | Yes | ✅ Done 2026-05-22 |
| P2-A: molecule_intelligence split | P2 | 2–3 hr | Medium | No | ✅ Already done — write_molecule_intelligence() only writes intrinsic fields; vs_ailux_positioning now in drug_area_scores (P1-D) |
| P2-B: Remove drugs.overlap cols | P2 | 30 min | Low | No | Pending (after P2-A) |
| P2-C: DRUGS_ALL → Supabase | P2 | 2–3 hr | Medium | No | ✅ Done 2026-05-22 |
| P3-A: PHARMA_DATA → companies | P3 | 1–2 hr | Low | No | Pending (PHARMA_DATA var not in index.html; needs rescoping as financial columns on companies table) |

**Total before Tier 1:** ~10–13 hours of implementation work (P0 + P1)
**Total restructuring:** ~7–9 hours (P2), natural fit with Molecule Database migration
**Total post-Tier-1:** ~2–3 hours (P3)

---

## Migration Risks

**Catalyst UNIQUE constraint (P1-C):** The most risky single step. Must run a deduplication audit before adding the constraint, or the `ALTER TABLE` will fail on existing duplicates. Run this first:
```sql
SELECT canonical_drug_id, catalyst_type, sort_date, COUNT(*)
FROM catalysts
GROUP BY canonical_drug_id, catalyst_type, sort_date
HAVING COUNT(*) > 1;
```
If output is non-empty, delete duplicates before adding constraint.

**drug_area_scores backfill (P1-D):** Companies with one area are easy to backfill. Companies with two areas (e.g., AbbVie has tl1a + ibd) are ambiguous — can't know which area each drug's `overlap` was set in without enrichment history. Safe default: use the earliest company_area for multi-area companies; accept that some backfill will be approximate and will be corrected by next enrichment run.

**molecule_intelligence write path (P2-A):** Changing what `write_molecule_intelligence()` writes means the next enrichment run after the update will no longer overwrite area-specific fields — which is the desired behavior but requires validating that `--rescore-molecule` still functions correctly after the split.

---

## What This Enables

After Phase 0 + Phase 1 complete (~2 days of work):
- Every signal from `signal_monitor.py` routes to a canonical company via CompanyIdentityResolver
- Every deal written by any script has a `company_id` FK and surfaces in Company Database
- Every catalyst from any source is deduplicated
- Company intel queries use direct FK instead of junction join
- Area-specific drug scores accumulate correctly per area without overwriting
- company_areas and company_profiles stay in sync automatically

The platform is then ready for Tier 1 signal volume without data drift compounding.
