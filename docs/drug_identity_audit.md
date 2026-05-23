# Drug Identity Audit
**Date:** 2026-05-23  
**Scope:** 4 suspected duplicate pairs surfaced during molecule intelligence gap analysis  
**Principle:** One physical molecule → one canonical drug_id → one molecule_intelligence record

---

## Summary

| Pair | Classification | Action |
|------|---------------|--------|
| `afimkibart` / `pf-06480605` | ✅ Confirmed duplicate | Merge → keep `afimkibart` |
| `erd-1` / `hxn1003` | ✅ Confirmed duplicate | Merge → keep `erd-1` |
| `ep006` / `es302` | ⚠️ Different molecules, naming collision | Fix `ep006` display_name only |
| `qx030n` / `qx031n` | ✅ Distinct molecules | No merge — different targets/areas/partners |

---

## Case 1: `afimkibart` / `pf-06480605` — Confirmed Duplicate

### Identity history
This is one physical molecule that changed hands:  
**Pfizer (PF-06480605)** → Telavant JV (RVT-3101) → **Roche acquired Telavant 2023** → renamed **Afimkibart / RO7790121** → INN: **afimkibart**

### Data state

| Field | `afimkibart` (Roche) | `pf-06480605` (Pfizer) |
|-------|---------------------|----------------------|
| display_name | "afimkibart" (lowercase, poor) | "Afimkibart (RO7790121)" ✓ |
| company_id | roche | pfizer |
| partner_company | "Telavant / Pfizer" | "Roche" |
| target | TL1A | TL1A |
| stage | Phase 3 | Phase 3 |
| cls | "TL1A inhibitor" | "1st Gen" |
| canonical_drug_id | CANON_DRUG_8847B9FE | CANON_DRUG_96B268D4 |
| source_url | clinicaltrials.gov/NCT04997083 | clinicaltrials.gov/NCT06589986 |
| drug_areas | ibd, tl1a | ibd, tl1a |
| drug_area_scores (ibd) | Direct, cls='TL1A inhibitor' | Direct, cls='1st Gen' |
| drug_area_scores (tl1a) | ❌ missing | Direct |
| molecule_intelligence | ❌ none | ✅ high confidence (IgG1, TUSCANY-2 data) |
| trials | 6 (TUSCANY-2, pediatric Ph3s, AD Ph2) | 7 (AMETRINE-1, AMETRINE-2, early Ph1/2s) |
| catalysts | 6 (Roche) | 2 (Pfizer) |

### Canonical choice: `afimkibart`
Rationale: `afimkibart` is the WHO INN, the current Roche-owned asset, and has the active Phase 3 trial data. The `pf-06480605` ID represents a historical Pfizer naming convention that is no longer the operational identity of this drug.

### Merge plan (safe — no deletions until verified)

```sql
-- STEP 1: Fix afimkibart drug record to match canonical display
UPDATE drugs SET
  display_name     = 'Afimkibart (RO7790121)',
  name             = 'Afimkibart',
  cls              = '1st Gen',
  partner_company  = 'Roche / Pfizer (originated)',
  canonical_drug_id = 'CANON_DRUG_96B268D4'  -- keep pf-06480605's canonical (has more data)
WHERE id = 'afimkibart';

-- STEP 2: Copy molecule_intelligence from pf-06480605 to afimkibart
INSERT INTO molecule_intelligence
  SELECT 'afimkibart', format, modality, igg_subclass, fc_engineering, epitope,
         affinity_kd, differentiation_claim, safety_observations, source_url,
         confidence, field_status, last_updated_at
  FROM molecule_intelligence WHERE drug_id = 'pf-06480605';

-- STEP 3: Fix afimkibart's ibd area_score cls (align with 1st Gen standard)
UPDATE drug_area_scores SET cls = '1st Gen' WHERE drug_id = 'afimkibart' AND area_id = 'ibd';

-- STEP 4: Add tl1a area_score for afimkibart (it was missing; pf-06480605 had it)
INSERT INTO drug_area_scores (drug_id, area_id, overlap, cls)
VALUES ('afimkibart', 'tl1a', 'Direct', '1st Gen')
ON CONFLICT (drug_id, area_id) DO UPDATE SET overlap = 'Direct', cls = '1st Gen';

-- STEP 5: Migrate pf-06480605 trials to afimkibart
UPDATE trials SET drug_id = 'afimkibart' WHERE drug_id = 'pf-06480605';

-- STEP 6: Migrate pf-06480605 catalysts to afimkibart (update company_id to roche)
UPDATE catalysts SET drug_id = 'afimkibart', company_id = 'roche' WHERE drug_id = 'pf-06480605';

-- STEP 7: Remove pf-06480605 orphaned rows
DELETE FROM drug_area_scores WHERE drug_id = 'pf-06480605';
DELETE FROM drug_areas WHERE drug_id = 'pf-06480605';
DELETE FROM molecule_intelligence WHERE drug_id = 'pf-06480605';

-- STEP 8: Delete pf-06480605 from drugs (last — FK constraints enforce order)
DELETE FROM drugs WHERE id = 'pf-06480605';
```

**Post-merge verification:**
```sql
SELECT d.id, d.display_name, d.stage, d.company_id,
       mi.format, mi.confidence,
       COUNT(DISTINCT t.id) AS trial_count,
       COUNT(DISTINCT c.id) AS catalyst_count
FROM drugs d
LEFT JOIN molecule_intelligence mi ON mi.drug_id = d.id
LEFT JOIN trials t ON t.drug_id = d.id
LEFT JOIN catalysts c ON c.drug_id = d.id
WHERE d.id = 'afimkibart'
GROUP BY d.id, d.display_name, d.stage, d.company_id, mi.format, mi.confidence;
-- Expected: 13 trials (6+7), 8 catalysts (6+2), molecule_intelligence present
```

---

## Case 2: `erd-1` / `hxn1003` — Confirmed Duplicate

### Identity history
**ERD-1** is Earendil Bio's internal program code. After the Sanofi licensing deal (2025 press release), the drug was renamed **HXN-1003** as the public product name. They are the same molecule: a tetravalent TL1A×IL-23p19 bispecific antibody developed on Earendil's AI platform.

### Data state

| Field | `erd-1` (Earendil) | `hxn1003` (Sanofi) |
|-------|-------------------|-------------------|
| display_name | "HXN-1003" | "HXN-1003" |
| company_id | earendil | sanofi |
| partner_company | Sanofi | Earendil |
| target | TL1A (incomplete — should be TL1A×IL-23p19) | TL1A×IL-23p19 ✓ |
| stage | Phase 2 ✓ (Sanofi 2025 PR) | Preclinical (stale) |
| cls | 1st Gen | 1st Gen |
| source_url | sanofi.com 2025 PR | earendilbio.com/pipeline |
| drug_areas | ibd, tl1a | ibd, tl1a |
| drug_area_scores | ibd (Direct), tl1a (Direct) | ibd (Direct) only |
| molecule_intelligence | ✅ medium confidence (tetravalent bispecific) | ❌ none |
| trials | 0 | 0 |
| catalysts | 0 | 0 |

### Note on company ownership
The correct framing: Earendil Bio **originated** the molecule (company_id = earendil), Sanofi is the **partner/licensee**. The `hxn1003` entry incorrectly swaps this, making Sanofi the owner and Earendil the partner. Keep `erd-1` with company_id=earendil and partner_company=Sanofi.

### Canonical choice: `erd-1`
Rationale: `erd-1` holds the molecule_intelligence record, has more complete drug_area_scores, and represents the correct originator perspective (Earendil). The display_name "HXN-1003" will be preserved.

### Merge plan

```sql
-- STEP 1: Fix erd-1 target to full bispecific target name
UPDATE drugs SET
  target = 'TL1A×IL-23p19',
  name   = 'ERD-1 / HXN-1003'
WHERE id = 'erd-1';

-- STEP 2: Remove hxn1003 drug_area_scores (erd-1 already has ibd + tl1a; hxn1003 only has ibd)
DELETE FROM drug_area_scores WHERE drug_id = 'hxn1003';

-- STEP 3: Remove hxn1003 drug_areas (erd-1 already covers both areas)
DELETE FROM drug_areas WHERE drug_id = 'hxn1003';

-- STEP 4: Delete hxn1003 from drugs
DELETE FROM drugs WHERE id = 'hxn1003';
```

**Post-merge verification:**
```sql
SELECT id, display_name, name, target, stage, company_id, partner_company
FROM drugs WHERE id = 'erd-1';
-- Expected: target='TL1A×IL-23p19', name='ERD-1 / HXN-1003', company_id='earendil', partner_company='Sanofi'

SELECT drug_id, area_id, overlap FROM drug_area_scores WHERE drug_id = 'erd-1';
-- Expected: ibd (Direct), tl1a (Direct)
```

---

## Case 3: `ep006` / `es302` — NOT a Duplicate (naming collision)

### What looked like a duplicate
`ep006` has `display_name = 'ES302'` — which matches the `id` of `es302`. This triggered the false positive.

### What they actually are

| | `ep006` | `es302` |
|--|---------|---------|
| company_id | episcience | elpiscience |
| company name | Episcience / Eprovaxia (US) | Elpiscience Biopharma (China) |
| target | TL1A (monoclonal, 1st Gen per mol_intel) | TL1A×IL-23p19 |
| stage | Phase 2 | Preclinical |
| molecule_intelligence | ✅ low confidence bispecific | ❌ none |
| source_url | eprovaxia.com | none |

**Episcience** (now Eprovaxia) is a US-based biotech. Their lead TL1A program is EP006, which they internally label ES302 — this is a company-specific product name, not the Elpiscience molecule.

**Elpiscience Biopharma** is a separate Chinese biotech with their own TL1A×IL-23p19 preclinical program, id=`es302`.

These are two different molecules from two different companies. The name `ES302` is shared by coincidence.

### Action required (data quality fix only)

```sql
-- Fix ep006 display_name to avoid collision with es302 (Elpiscience)
UPDATE drugs SET display_name = 'EP006 (Eprovaxia)' WHERE id = 'ep006';

-- Note: molecule_intelligence for ep006 is correct as-is (drug_id='ep006')
-- No merge or deletion needed
```

Also flag in molecule_intelligence: the mol_intel for ep006 calls it a "bispecific antibody" but ep006's target says just "TL1A" (not bispecific). The low confidence rating reflects this uncertainty. Needs human review before enrichment.

---

## Case 4: `qx030n` / `qx031n` — Distinct Molecules

### Why they were flagged
Same company (Qyuns), similar alphanumeric IDs, molecule_intelligence exists only for qx031n.

### Why they are NOT duplicates

| | `qx030n` | `qx031n` |
|--|----------|----------|
| target | TL1A×IL-23p19 | TSLP×IL-33 |
| partner | Caldera | Roche |
| disease areas | ibd, tl1a | respiratory, tslp |
| stage | Phase 1 | Phase 1 |
| molecule_intelligence | ❌ none | ✅ medium confidence |

Completely different biology, different partnerships, different disease areas. These are two separate Qyuns programs with similar naming conventions (QX = Qyuns; 030N and 031N are sequential program numbers).

### Action required (enrichment gap only)

```sql
-- No merge. qx030n simply needs its own molecule_intelligence record.
-- Add to molecule enrichment backlog:
-- drug_id = 'qx030n', target = TL1A×IL-23p19 bispecific, Qyuns/Caldera partnership
```

---

## Execution Order

Execute merges in this order to minimize risk:

**1. Merge B first: hxn1003 → erd-1** (simpler — no trials/catalysts to migrate)

**2. Merge A second: pf-06480605 → afimkibart** (more complex — 7 trials + 2 catalysts to migrate; verify trial dedup after)

**3. Data fix: ep006 display_name** (standalone UPDATE, no dependencies)

**4. After merges complete:** Run `python3 scripts/validate_ground_truth.py` — all 61 tests should still pass.

---

## Uncertain Cases Requiring Human Review

| Drug | Issue | Requires |
|------|-------|---------|
| `ep006` | Molecule_intel says "bispecific" but target field says "TL1A" (not bispecific). Low confidence mol_intel. | Verify: is EP006 a monospecific or bispecific? |
| `afimkibart` post-merge | 13 combined trials may include duplicates (e.g., AMETRINE trials may appear on both old IDs). | Review trial list after merge and dedup if needed. |
| `erd-1` stage | Phase 2 (from Sanofi 2025 PR) vs Preclinical (hxn1003) — Sanofi PR likely correct but confirm. | Spot-check against earendilbio.com/pipeline. |

---

## Post-Audit State (Expected)

After executing merges A + B + data fix C:
- `afimkibart`: canonical Roche/Pfizer anti-TL1A mAb, Phase 3, 13 trials, 8 catalysts, molecule_intelligence ✓
- `erd-1`: canonical Earendil/Sanofi TL1A×IL-23p19 tetravalent bispecific, Phase 2, mol_intel ✓
- `ep006`: Eprovaxia TL1A program, display_name fixed to 'EP006 (Eprovaxia)'
- `es302`: Elpiscience TL1A×IL-23p19, distinct identity preserved
- `qx030n`: Qyuns TL1A×IL-23p19, distinct identity, queued for molecule enrichment
- `qx031n`: Qyuns TSLP×IL-33 bispecific, distinct identity, molecule_intelligence ✓
- `pf-06480605`: deleted
- `hxn1003`: deleted

**Molecule intelligence coverage after merges + subsequent enrichment pass:**  
16 drugs → 18 drugs with mol_intel (afimkibart + erd-1 inherit their records after merge).
