# Meridian BD Platform — Claude Working Reference

This file is auto-loaded by Claude Code at session start. Read all sections before making any data edits.

---

## Platform Orientation

- **What it is**: Competitive intelligence and BD strategy platform for Ailux Biotherapeutics (TL1A×IL-23p19 bispecific for IBD)
- **Workspace**: `/Users/kyleklaassen/Documents/Claude/Projects/BD Platform/`
- **Dashboard**: kyleklaassen-dev/bd-dashboard (GitHub Pages)
- **Backend**: Supabase project `tghntyofptvfhmtchwcv`
- **Credentials**: `.supabase_service_key`, `.supabase_anon_key`, `.github_token` in workspace root

## Session Start Checklist

1. Check `drug_validation_results` for fail/warning/needs_review before other work
2. Check `governance_violations WHERE resolved = false` for outstanding data integrity issues
3. Read NEXT_SESSION.md if present for context from last session

---

## Governance Rules (MANDATORY)

### 1. Licensing Attribution
`drugs.company_id` = **originator (inventor/developer) ALWAYS**. Never change to a licensee.
Licensee relationships go in `company_partnerships` / `deals` tables only.

Full effective pipeline query requires joining BOTH `drugs.company_id` AND `company_partnerships`:
```sql
SELECT d.name, d.stage,
  CASE WHEN d.company_id = '{cid}' THEN 'direct' ELSE 'licensed_in' END as attribution
FROM drugs d
LEFT JOIN company_partnerships cp ON cp.company_id = d.company_id
  AND cp.partner_company_id = '{cid}'
  AND cp.deal_type IN ('licensing', 'co-development', 'option', 'collaboration')
WHERE d.company_id = '{cid}' OR cp.id IS NOT NULL
```

**Canonical**: ABBV-701.company_id = 'futuregen'. AbbVie appears via partnership row only.

### 2. Company Status (Subsidiary vs Acquired)
Default to `status='subsidiary'` for any company still operating independently.
Only set `status='acquired'` when the company has **provably dissolved** — no active website, no independent pipeline, no named leadership.

Decision test (apply in order):
1. Active website with own pipeline? → subsidiary
2. Named leadership (CEO/CSO)? → subsidiary
3. Active on LinkedIn/CrunchBase? → subsidiary
4. Parent announced dissolution explicitly? → acquired
5. >3 years post-acquisition, no independent public activity? → consider acquired, flag for review

**Canonicals**: Blueprint Medicines = subsidiary. Ailux = subsidiary. Prometheus = acquired. Celgene = acquired.

Always set `parent_company_id` for both subsidiary and acquired.

### 3. Co-Development Attribution
Multi-company drugs use:
- `partner_company` = co-developer name
- `partnership_type = 'co_developed'`
- `partnership_verified = false` (until press release or CT.gov sponsor field confirms)

Do NOT change `company_id`. Do NOT embed partner name in the `target` field.
Target field = molecular targets only (e.g., "TL1A × IL-23p19").

### 4. Brand Name Implies Approved
Any drug with `brand_name` set MUST have `stage` in:
`approved | approved_us | approved_eu | approved_china | approved_us_eu | approved_partial`

A dash "—" is NOT a valid brand_name — clear to null. Never set stage=approved manually without also setting brand_name or a recognized approval milestone. Stage resolution is managed by `_resolveStage` in `_makeAreaPI`.

### 5. Source URL Required
Every deal, partnership, and co-developer relationship requires a `source_url` (CT.gov NCT link, press release, SEC 8-K, or company IR). Do not fabricate URLs. Omit rather than guess. Set `partnership_verified = false` if source cannot be confirmed.

### 6. Deal Sequencing
Before rating any company as "call now" for an Ailux asset, check:
1. Do they have an existing asset in the same mechanism? (direct OR licensed)
2. Is there a readout expected in the next 18 months?
3. Could they achieve the same via combining existing assets?

**Active constraint**: AbbVie cannot be targeted for any TL1A bispecific until after ABBV-701 Phase 1 readout (expected Oct 2026). Downgrade to timing_note if constraint applies.

---

## Architecture Quick Reference

- **Area tabs**: read from `drug_targets` (ontology) via `_makeAreaPI` — never from legacy `drug_areas` for biological data
- **Stage resolution**: `_resolveStage(drug)` in index.html — brand_name + indication_short year → 'Approved'
- **Pipeline query**: always join `drug_targets` + `drug_indications` (not `drug_areas`) for Phase 5+ areas
- **Completeness scoring**: `coverage_scores` table, computed by `scripts/compute_coverage.py`

## Deploy Pattern

```bash
TOKEN=$(cat .github_token)
# Commit + push to main → GitHub Pages auto-deploys
git add -A && git commit -m "description" && git push
```

## Key Files

- `index.html` — main dashboard (single file, ~10k lines)
- `scripts/company_enrichment.py` — company/drug enrichment pipeline (ENRICHMENT_SYSTEM prompt)
- `scripts/research.py` — nightly news intelligence pipeline
- `scripts/molecule_enrichment.py` — molecule characterization pipeline
- `migrations/v1_schema.sql` — live schema snapshot (do not apply to prod); forward migrations start at v2
- `migrations/_archive/` — pre-v1 historical SQL (see `_archive/SITUATION.md`)
- `scripts/apply_governance_violations.py` — applies the above migration + verifies

## Governance Violations Table

`governance_violations` table (apply via `scripts/apply_governance_violations.py` or Supabase SQL editor):
- Tracks soft-constraint violations without hard-blocking enrichment
- Check at session start: `governance_violations?resolved=eq.false`
- Rules tracked: `brand_name_implies_approved`, `codev_requires_source_url`, `approval_date_implies_approved`

## Memory Files (governance)
- `project_governance_subsidiary_acquired.md` — subsidiary vs acquired decision test
- `project_governance_licensing_attribution.md` — originator attribution + full pipeline SQL
- `project_governance_deal_sequencing.md` — timing constraints (AbbVie/Oct 2026 canonical)
- `project_governance_codev_attribution.md` — co-dev partner handling rules
- `project_governance_data_validation.md` — brand_name, approval_date, source_url rules
