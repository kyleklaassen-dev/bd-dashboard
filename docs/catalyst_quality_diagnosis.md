# Catalyst Quality Diagnosis Report
**Generated:** 2026-05-22  
**Scope:** All areas (`catalysts` table)  
**Status:** Diagnosis only — no data changes applied

---

## 1. Summary Statistics

| Metric | Value |
|--------|-------|
| Total catalyst rows | 710 |
| Distinct catalysts (company + label) | ~580 estimated |
| Duplicate rows | ~130 (18% duplicate rate) |
| TL1A rows | 394 |
| TL1A distinct groups | ~308 |
| TL1A duplicate rows | ~86 (21% rate) |

### Per-Area Breakdown

| Area | Total Rows | Est. Duplicates | Est. Distinct |
|------|-----------|-----------------|---------------|
| tl1a | 394 | ~86 | ~308 |
| tslp | 113 | ~20 | ~93 |
| tcell | 73 | ~13 | ~60 |
| il4ra | 65 | ~11 | ~54 |
| fcrn | 37 | ~6 | ~31 |
| igf1r | 28 | ~5 | ~23 |
| **Total** | **710** | **~141** | **~569** |

---

## 2. Root Cause Analysis

### Primary Root Cause: No INSERT guard against duplicates

The enrichment pipeline (`company_enrichment.py`) inserts catalysts via a simple array of new objects. It does **not** query existing catalysts before inserting. Each enrichment run adds whatever catalysts the LLM generates — even if nearly identical catalysts already exist from a prior run.

No unique constraint exists on the `catalysts` table. Supabase will silently accept any insert.

### Secondary Root Cause: Repeated daily enrichment runs, May 18–22

Creation-date analysis of TL1A catalysts reveals the insertion pattern:

| Date | Rows Created | Interpretation |
|------|-------------|----------------|
| 2026-05-18 | 23 | Baseline (first enrichment pass) |
| 2026-05-19 | 102 | First full enrichment run |
| 2026-05-20 | 95 | Second full enrichment run |
| 2026-05-21 | 96 | Third full enrichment run |
| 2026-05-22 | 78 | Fourth partial run (in-progress) |

Each run re-inserts essentially the same catalysts under slightly varied labels (LLM paraphrasing), generating a 4× multiplication of core catalyst content. The daily pattern is clear: every enrichment run = +95–102 rows, with ~70% being near-duplicates of prior runs.

### Tertiary Root Cause: LLM label variation prevents exact deduplication

Even when two catalysts describe the same event, the LLM may render them differently:
- `"Duvakitug Phase 3 PACIFIC-CD readout expected 2025"` (run 1)
- `"Phase 3 PACIFIC-CD data readout for duvakitug anticipated 2025"` (run 2)
- `"Teva PACIFIC-CD Phase 3 catalyst expected H2 2025"` (run 3)

These are the same catalyst. Exact string matching would only catch verbatim duplicates; fuzzy matching is needed for full cleanup.

---

## 3. Most-Duplicated Catalyst Groups (TL1A)

These groups appear 4× — one insertion per enrichment run day:

| Company | Label (truncated) | Count |
|---------|------------------|-------|
| caldera | CLD-423 Phase 1 interim safety and PK data expected | 4 |
| teva | Duvakitug anticipated NDA/BLA or MAA regulatory filing in UC and CD | 4 |
| earendil | HXN-1003 Phase 1 initiation by Sanofi (TL1A×IL-23p19 bispecific) | 4 |
| merck | MK-7240 Phase 2 readout in CD expected | 4 |
| abbvie | ABBV-157 Phase 2/3 initiation in CD | 4 |
| roche | RG7625 Phase 1 dose-escalation completion | 4 |
| jnj | JNJ-64304500 Phase 2 UC data readout | 4 |

By exact `(company_id, label)` match: **60 duplicate groups, 146 affected rows** in TL1A.  
By fuzzy `(company_id, label[:60])` match: **~86 duplicate groups** (catches LLM paraphrase variation).

---

## 4. Recommended Uniqueness Key

### Option A — Exact: `(company_id, label)`
- Catches verbatim duplicates only
- Safe: zero false-positive deletions
- Estimated TL1A cleanup: 394 → ~308 rows (removes 86 exact dupes)
- **Recommended for the database constraint**

### Option B — Fuzzy: `(company_id, label[:60], area_id)`
- Catches LLM paraphrase variants
- Slightly more aggressive — may catch distinct catalysts with similar beginnings
- Estimated TL1A cleanup: 394 → ~280–290 rows
- **Recommended for the one-time cleanup pass only**

### Option C — Semantic: `(company_id, sort_date, catalyst_type)`
- Groups by date + type regardless of label wording
- Risk: over-deduplication (a company can have two catalysts of the same type on the same date)
- **Not recommended** as a constraint; too coarse

**Decision: Use Option A for the uniqueness constraint. Use Option B for the one-time deduplication cleanup.**

---

## 5. Safe Deduplication Strategy

### Step 1: One-time cleanup — remove exact duplicates (safe, apply first)

For each `(company_id, area_id, label)` group, keep the row with the **highest `id`** (most recent insert). This preserves the most current LLM output and removes older copies.

```sql
-- Preview: how many rows would be deleted?
SELECT COUNT(*) AS rows_to_delete
FROM catalysts c
WHERE id NOT IN (
  SELECT MAX(id)
  FROM catalysts
  GROUP BY company_id, area_id, label
);

-- Execute (irreversible — run preview first):
DELETE FROM catalysts
WHERE id NOT IN (
  SELECT MAX(id)
  FROM catalysts
  GROUP BY company_id, area_id, label
);
```

**Estimated impact:** ~86 rows removed from TL1A; ~141 total across all areas.  
**Risk level:** Low. Only removes rows where label is byte-for-byte identical.

### Step 2: One-time fuzzy cleanup — remove near-duplicates (moderate, review before applying)

```sql
-- Preview groups that share company + first 60 chars of label
SELECT company_id, area_id, LEFT(label, 60) AS label_prefix, COUNT(*) AS cnt
FROM catalysts
GROUP BY company_id, area_id, LEFT(label, 60)
HAVING COUNT(*) > 1
ORDER BY cnt DESC, company_id;
```

Review the output before executing deletions. Once confirmed:

```sql
DELETE FROM catalysts
WHERE id NOT IN (
  SELECT MAX(id)
  FROM catalysts
  GROUP BY company_id, area_id, LEFT(label, 60)
);
```

**Estimated additional impact:** removes ~55 more rows beyond Step 1.  
**Risk level:** Moderate. Review the preview to ensure no distinct catalysts share a 60-char prefix.

### Step 3: Add a unique constraint to prevent future duplicates

```sql
-- After cleanup, add constraint to block future verbatim duplication
CREATE UNIQUE INDEX catalysts_company_area_label_unique
ON catalysts (company_id, area_id, label);
```

This will cause future inserts of duplicate catalysts to fail at the DB level, which will surface the issue in enrichment logs rather than silently accumulating duplicates.

**Alternative:** Modify `company_enrichment.py` to use upsert (`onConflict=company_id,area_id,label`) instead of plain insert, allowing silent idempotent re-enrichment.

---

## 6. Enrichment Pipeline Fix

After cleanup, the enrichment script should be updated to prevent re-accumulation:

```python
# In company_enrichment.py — catalyst insert
# Change from:
supabase.table("catalysts").insert(catalyst_records).execute()

# To (upsert on unique key):
supabase.table("catalysts").upsert(
    catalyst_records,
    on_conflict="company_id,area_id,label"
).execute()
```

This requires the unique index from Step 3 to exist first.

---

## 7. Estimated Final State After Cleanup

| Area | Before | After Step 1 | After Steps 1+2 |
|------|--------|-------------|-----------------|
| tl1a | 394 | ~308 | ~280 |
| tslp | 113 | ~93 | ~85 |
| tcell | 73 | ~60 | ~55 |
| il4ra | 65 | ~54 | ~49 |
| fcrn | 37 | ~31 | ~28 |
| igf1r | 28 | ~23 | ~21 |
| **Total** | **710** | **~569** | **~518** |

---

## 8. Recommended Execution Order

1. **Run Step 1 preview** — confirm ~86 TL1A rows qualify for exact deletion
2. **Run Step 1 delete** — execute exact dedup (safe)
3. **Run Step 2 preview** — manually review fuzzy groups for false positives
4. **Run Step 2 delete** — execute fuzzy dedup only after review
5. **Add unique index** (Step 3) — prevents future accumulation
6. **Update enrichment pipeline** — switch inserts to upserts
7. **Verify** — re-run count query to confirm expected row counts

**Do not modify the enrichment pipeline before running cleanup** — the pipeline fix produces correct upserts only after the constraint exists.

---

*Report generated by Claude | BD Platform Intelligence Layer | Session 2026-05-22*
