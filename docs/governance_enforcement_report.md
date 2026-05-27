# Governance Enforcement Report
**Generated**: 2026-05-27  
**Session**: Governance Hardening Sprint

---

## Summary

Four previously static governance docs have been converted into enforceable system components:
memory files (loaded every session), enrichment prompt rules (active in every Claude API call),
a database violations table (migration ready), and a CLAUDE.md for session-start auto-load.

---

## Task 1: Governance Docs Read

Three docs existed:
- `docs/governance_subsidiary_vs_acquired.md` — 5-step test, canonical examples, DB fields
- `docs/governance_licensing_attribution.md` — originator rule, full pipeline SQL, AbbVie/FutureGen
- `docs/governance_deal_sequencing.md` — 3 sequencing rules, AbbVie/XPF005 canonical constraint
- `docs/governance_codev_attribution.md` — **did not exist** (created as new memory file from first principles)

---

## Task 2: Memory Files Created

Five files written to memory directory:

| File | Rule | Key Trigger |
|------|------|-------------|
| `project_governance_subsidiary_acquired.md` | Subsidiary vs acquired 5-step test | Before any company status change |
| `project_governance_licensing_attribution.md` | Originator attribution + full pipeline SQL | Before any BD gap analysis |
| `project_governance_deal_sequencing.md` | Timing constraints, AbbVie Oct 2026 block | Before rating company "call now" |
| `project_governance_codev_attribution.md` | co_developer_ids[], partnership_verified logic | Before any co-dev data entry |
| `project_governance_data_validation.md` | brand_name→approved, source_url required | Before any drug or deal write |

---

## Task 3: MEMORY.md Updated

Five entries added to the index at the bottom of MEMORY.md. Each entry is under 150 chars and includes the trigger condition. The index now has 52 entries total.

---

## Task 4: Database Constraints

### governance_violations Table

**Status**: Migration SQL written and ready. Automated pg-meta execution not available on this Supabase instance. Manual apply required.

**Apply via**:
```bash
python3 scripts/apply_governance_violations.py
# If pg-meta unavailable, script prints SQL for manual paste into:
# https://supabase.com/dashboard/project/tghntyofptvfhmtchwcv/sql/new
```

**Files**:
- `migrations/schema_migration_governance_v1.sql` — DDL + seed data
- `scripts/apply_governance_violations.py` — migration runner with verification

### Violations Found (2026-05-27 audit)

**brand_name_implies_approved** — 5 violations:

| Drug ID | Drug Name | brand_name value | Stage | Fix |
|---------|-----------|-----------------|-------|-----|
| astegolimab | astegolimab | "—" (dash placeholder) | Phase 3 | Clear brand_name to NULL |
| caba-201 | CABA-201 | "—" (dash placeholder) | Phase 2 | Clear brand_name to NULL |
| catalog-53 | Newsoara TSLP Ab | "HY-6725" (catalog reagent number) | Phase 1 | Clear brand_name to NULL |
| itepekimab | itepekimab | "—" (dash placeholder) | Phase 3 | Note: approved as Kyntheum in EU. Update stage to approved_eu or clear brand_name |
| risankizumab-lutikizumab-or-trosunilimab | Combination trial | "TARGET-CD (M24-885)" (trial identifier) | Phase 2 | Clear brand_name to NULL |

Root cause: brand_name field was used as a free-text label/placeholder in some enrichment runs.
The dash "—" appears to be an empty-state placeholder that slipped through as an actual value.

**codev_requires_source_url** — 2 violations (deals table):

| Deal ID | From | To | Type | Fix |
|---------|------|----|------|-----|
| 198 | agenus | spyre | licensing | Add press release URL |
| 201 | lanova | zymeworks | licensing | Add press release URL |

Note: `company_partnerships` table does not have a `source_url` column (schema gap). Violations checked against the `deals` table which does. The governance_violations migration seeds these as pending fixes.

---

## Task 5: Enrichment Scripts Updated

Three scripts patched with governance rules. All changes deployed to GitHub (kyleklaassen-dev/bd-dashboard):

### `scripts/company_enrichment.py`
Added `GOVERNANCE RULES` block to `ENRICHMENT_SYSTEM` prompt (6 rules, ~35 lines). Rules cover:
1. Attribution (originator always)
2. Company status defaults
3. Co-dev attribution pattern
4. Brand name implies approved
5. Source URL required
6. Deal sequencing (AbbVie/Oct 2026 constraint named explicitly)

### `scripts/molecule_enrichment.py`
Added `## Governance Rules` section to `build_prompt()`. Rules cover:
- Attribution (company_id = originator)
- Brand name only for approved drugs
- Source URL verifiability
- Co-dev target field hygiene

### `scripts/research.py`
Added `GOVERNANCE RULES FOR DEAL EXTRACTION` to `EXTRACT_PROMPT`. Rules clarify:
- deal_from = licensee/acquirer, deal_to = licensor/originator
- AbbVie/FutureGen as canonical example of correct direction
- source_url always required for deal records

---

## Task 6: CLAUDE.md Created

`CLAUDE.md` written at workspace root. Contains:
- Platform orientation and credentials locations
- Session start checklist (validation queue + governance violations check)
- All 6 governance rules with canonical examples and SQL
- Architecture quick reference (ontology migration, stage resolution, deploy pattern)
- Key files index
- Governance violations table reference

**Deployed to GitHub**: `CLAUDE.md` at repo root (auto-loaded by Claude Code).

---

## Pending Actions (not automated)

1. **Apply governance_violations migration**: Run `python3 scripts/apply_governance_violations.py` or paste `migrations/schema_migration_governance_v1.sql` into Supabase SQL editor
2. **Fix brand_name violations**: Clear the 5 brand_name placeholders (dash values) from the drugs table
3. **Add source_urls to deals 198 and 201**: Agenus→Spyre and Lanova→Zymeworks
4. **Add source_url column to company_partnerships**: Current schema lacks this field; violations tracked via deals table as proxy
