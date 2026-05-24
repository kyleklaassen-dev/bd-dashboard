# NEXT SESSION — BD Platform

**Written:** 2026-05-24 (Session 33)  
**Last work:** Catalyst Coverage Sprint — scoring fix + backfill + compute  
**Validation:** 993 pass / 0 fail / 7 skip ✅

---

## Session 33 Summary — Catalyst Coverage Sprint

### What was built
- `compute_coverage.py` v1.1 — fixed ACTIVE_STAGES denominator (excludes Approved), fixed upsert on_conflict
- `scripts/backfill_catalysts.py` — idempotent catalyst backfill (stage corrections + historical catalysts + future catalysts)

### Changes made
- mirikizumab stage → `Approved` (Omvoh FDA approved for UC + CD; was artificially in denominator)
- batoclimab stage → `Discontinued` (company not filing BLA; TED Phase 3 failed April 2026)
- 2 resolved historical catalysts added (batoclimab TED failure, batoclimab MG positive)
- 4 future unresolved catalysts added (imvt-1402 CLE/Graves'/MG, lutikizumab/ibd combo)

### Platform state (end of Session 33)
| Dimension | Score | Change | Flag |
|-----------|-------|--------|------|
| Molecule intelligence | 99.5 | — | ✅ |
| Deal linkage | 97.1 | — | ✅ |
| Target mapping | 97.1 | +5.4 | ✅ |
| Confidence coverage | 82.7 | — | ✅ |
| Enrichment recency | 70.4 | — | ok |
| Profile completeness | 68.3 | — | ok |
| Source coverage | 59.5 | — | ⚠ |
| Ownership coverage | 57.7 | — | ⚠ |
| Catalyst coverage | **53.6** | **+10.5** | ⚠ |

**Platform average: 72.8 / 100** (was 71.3)

### Remaining catalyst gap (53.6 → 70 target)
The 10.5-point gain came from:
- Scoring fix (Approved drugs removed from denominator)
- Stage corrections (mirikizumab + batoclimab removed from denominator)
- 4 new future catalysts (imvt-1402 x2 areas, lutikizumab/ibd)

Remaining gap: ~35 more Phase 2 programs need catalysts. Most are at smaller companies  
(connectbiopharma, qyuns, upstreambio, lanova) or large-company Phase 2 programs  
where readout dates are less well-defined.

---

## Next Steps (in priority order)

### P0 — Wire compute_coverage.py into nightly schedule
The script should run nightly so coverage scores reflect fresh enrichment data.  
Pattern: add scheduled GitHub Action or Cowork scheduled task calling `compute_coverage.py`.  
Note: upsert on_conflict is now fixed — nightly runs will properly update existing rows.

### P1 — Source coverage sprint (59.5 → 70 target)
Drug_area_scores rows systematically lack source_url. This is the highest-leverage remaining gap  
because source_url is weighted 2× in the overall score.

**Approach:**
- Check `company_enrichment.py` source_url write behavior — is it being populated from enrichment output?
- Build `backfill_sources.py` — for drug_area_scores rows with `confidence='confirmed'` and no source, find CT.gov NCT ID or company IR URL
- E6 rule: confidence='confirmed' + no source_url = automatic ⚠ in coverage

### P2 — Ownership coverage sprint (57.7 → 70 target)
Licensed-in drugs (drugs.partner_company set) should have ownership_edges.

**Approach:**
- Query: `drugs WHERE partner_company IS NOT NULL` + LEFT JOIN ownership_edges → find gaps
- Build `backfill_ownership_edges.py` — convert partner_company text into ORIGINATED_BY/LICENSED_IN edges
- Link to deals table via deal_id where possible

### P3 — Wire ACTIVE_IN into company_intake.py
When `company_intake.py` writes a new `company_areas` row, it must also write the corresponding  
`entity_edges ACTIVE_IN` row for graph consistency.  
Pattern: add `write_active_in_edge()` alongside `write_acquisition_edges()`.

### P4 — Continue catalyst coverage (53.6 → 60+)
Add catalysts for Phase 2 programs where readout windows are estimable:
- connectbiopharma/atopy — what drug? needs research
- qyuns/respiratory — what drug? needs research
- upstreambio/respiratory — what drug? needs research
- Large-company Phase 2 programs: riliprubart/sanofi, rocatinlimab/pfizer, linvoseltamab/regeneron

### P5 — Easy remaining drug target mappings
- `linsitinib` → `igf1r` (target exists, just add drug_targets row)
- `kyv-101` → `cd19` (target exists, just add drug_targets row)
- `ianalumab` → add `baffr` target, then drug_targets row

### P6 — Coverage dashboard (future)
Once scores are stable and nightly compute is running, build a coverage view into the Meridian dashboard.  
The recommended_actions_json already has the data — just needs a surface.

---

## DB State (end of Session 33)
| Table | Rows |
|-------|------|
| entity_edges (COMPETES_WITH) | 600 |
| entity_edges (TARGETS) | 146 |
| entity_edges (ACTIVE_IN) | 137 |
| drug_targets | 182 |
| targets | 47 |
| coverage_scores | 137 |
| catalysts (total) | ~698 |
| catalysts (unresolved) | 692 |
| validation suite | 993 pass / 0 fail / 7 skip |

---

## Collection Priority Order (Kyle's ranking — future sessions)
1. FDA regulatory feed
2. SEC/EDGAR monitoring
3. Pipeline page change detection
4. Conference abstract collection (DDW, ACR, EULAR, AAAAI, ATS)
5. PubMed ingestion
6. Patents (long-horizon)

---

## Session 28b cont. — TL1A Landscape Briefing + landscape_briefings Infrastructure

**Tasks #224–227 complete.**

### What was built
- `docs/tl1a_landscape_briefing.md` — cleaned, QA'd 5,700-word TL1A landscape briefing
- `landscape_briefings` table — new Supabase table for structured landscape intelligence
- `scripts/generate_landscape_briefing.py` — reusable 4-section Opus synthesis pipeline
- TL1A briefing inserted: `id=00536c9a-358b-400a-b634-be2e00f30a37`, needs_review=true

### Verification flags in the briefing (needs Meridian research)
| Claim | Location | Status |
|-------|----------|--------|
| Xencor Ultomiris royalty dispute $100–120M | Section 4 #7 | Needs verification |
| Takeda Entyvio biosimilar exposure beginning 2027 | Section 3 | Needs verification |
| AbbVie $1.71B upfront for ABBV-701 via Celsius | Section 4 #6 | Needs verification |
| Morphic acquisition ~$3.2B by Lilly | Section 3 | Needs verification |

### Next actions on landscape intelligence
- **Run backfill for other areas:** `python3 scripts/backfill_risk_bd_angle.py --area tslp` (then fcrn, il4ra)
- **Generate next area briefing:** `python3 scripts/generate_landscape_briefing.py --area tslp`
- **Surface briefing in frontend:** landscape_briefings row could feed an "Industry Landscape" tab section
- **Resolve verification flags:** spot-check the 4 flagged claims against public sources or Meridian deals table
