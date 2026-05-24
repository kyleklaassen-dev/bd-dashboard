# NEXT SESSION — BD Platform

**Written:** 2026-05-24 (Session 35 cont.)  
**Last work:** Ownership Coverage Sprint — backfill + deal_linkage scoring fix  
**Validation:** 993 pass / 0 fail / 7 skip ✅

---

## Session 35 Summary — Ownership Coverage Sprint (cont.)

### What was built
- `scripts/backfill_ownership_edges.py` — 28 new ORIGINATED_BY/LICENSED_IN edges for partner_company drugs
- `compute_coverage.py` — `score_deal_linkage()` fix: ORIGINATED_BY excluded from deal denominator
- 4 ownership_edges linked to existing deal records (qx030n, kt501, fg-m701, duvakitug)

### Coverage result (end of Session 35)
| Dimension | Score | Change | Flag |
|-----------|-------|--------|------|
| Molecule intelligence | 99.5 | — | ✅ |
| Deal linkage | 97.1 | — | ✅ |
| Target mapping | 97.1 | — | ✅ |
| Source coverage | 89.0 | +29.5 | ✅ |
| Confidence coverage | 82.7 | — | ✅ |
| Profile completeness | 73.9 | +5.6 | ok |
| Enrichment recency | 70.4 | — | ok |
| **Ownership coverage** | **100.0** | **+42.3** | ✅ |
| Catalyst coverage | 53.6 | — | ⚠ |

**Platform average: 83.0 / 100** (was 79.1, +3.9)

### Key insight: ownership sprint
- 28 drugs had partner_company set but no ownership_edge → backfilled with ORIGINATED_BY/LICENSED_IN
- Scoring fix was critical: ORIGINATED_BY edges (company invented the drug) excluded from deal_linkage denominator
- Only LICENSED_IN, ACQUIRED, SPUN_OUT_FROM require deal_id linkage
- Remaining gap: 24 transactional edges with no matching deal record (foundational historical partnerships)

---

## Session 35 Source Sprint Summary

### What was built
- `compute_coverage.py` v1.2 — source_coverage denominator = confirmed+supported only
- `scripts/backfill_sources.py` — Phase 1: drug URL patches; Phase 2: drug→DAS cascade
- `company_enrichment.py` — E6-R3 warning: supported + no source_url → log warning

### Key insight: scoring fix vs. backfill
The 29.5-point source jump was primarily the scoring fix (v1.2):
- `inferred`/`null` rows were counting against the denominator
- These represent model inferences, not sourced claims — shouldn't require source_url
- After fix: denominator = confirmed (50) + supported (74) = 124 rows, ~100% covered

---

## Session 34 Summary — L4-A: Graph Intelligence in Meridian

### What was built
- `fetch_graph_context()` — fetches ACTIVE_IN, TARGETS, COMPETES_WITH from entity_edges at Meridian generation time
- `build_graph_block()` — formats three graph layers into prompt-ready intelligence block:
  - ACTIVE PLAYERS BY AREA (area roster from ACTIVE_IN edges)
  - MECHANISM CONVERGENCE (contested targets with ≥2 competing entities, from TARGETS edges)
  - DIRECT COMPETITIVE PAIRS (confirmed COMPETES_WITH, deduplicated, capped at 50)
- Both PLAN_PROMPT and DRAFT_PROMPT now include `{graph_block}` — graph context feeds both passes

### Why this matters (L4-A unlock)
The Meridian no longer needs to reconstruct competitive structure from LLM memory. "Who is active in FcRn?" is answered from stored ACTIVE_IN edges. Mechanism convergence is read from TARGETS edges, not hallucinated. BD Lens callouts can now cite graph-grounded relationships.

**Commit:** `1c25ff6` — `scripts/write_meridian.py`

---

## Next Steps (in priority order)

### ✅ P1 — Backfill risk_summary + bd_angle — DONE (Session 34)
25/25 profiles filled: tslp (10/10), fcrn (6/6), il4ra (9/9). All four main areas now have interpretive intelligence coverage.

### ✅ P1 — Source coverage sprint — DONE (Session 35)
Source coverage: 59.5 → 89.0 (+29.5). Platform average: 72.8 → 79.1 (+6.3).
compute_coverage.py v1.2: denominator = confirmed+supported only. backfill_sources.py written.

### ✅ P2 — Ownership coverage sprint — DONE (Session 35 cont.)
Ownership coverage: 57.7 → 100.0 (+42.3). Platform average: 79.1 → 83.0 (+3.9).
28 ORIGINATED_BY/LICENSED_IN edges inserted. deal_linkage scoring fix: ORIGINATED_BY excluded from denominator.

### P1 — Wire compute_coverage.py into nightly schedule
Add scheduled GitHub Action or Cowork task calling compute_coverage.py nightly.

### P2 — Catalyst coverage (53.6 → 60+)
Add catalysts for Phase 2 programs with estimable readout windows.

### P3 — Coverage dashboard
Surface coverage_scores + recommended_actions_json in Meridian dashboard view.

---

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
