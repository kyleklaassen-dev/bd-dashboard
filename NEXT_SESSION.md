# NEXT SESSION — 2026-06-02 (Autonomous overnight — 3 cycles complete)
<!-- updated: 2026-06-02T02:45Z agent: cowork autonomous -->

## What Was Done This Session (full autonomous overnight run)

### Round 1 — Pre-session audit fixes (6 items)
- 92 free-text cls → canonical 1st/2nd/Next Gen in drugs + DCS
- mt-251, xmab412 UC/CD + spx306 tl1a → Direct/very_high in DCS
- linsitinib→Phase 2, miv-cel→Phase 3, obexelimab→Phase 3
- 3 trial arm drugs confirmed hidden
- tulisokibart company_id=prometheus (originator), current_owner=merck

### Round 2 — Full catalog audit + fixes
See `docs/AUDIT_REPORT_2026-06-01.md` for complete findings.

**Stage / brand governance:**
- 10 brand-name drugs → Approved: tralokinumab, benralizumab, mepolizumab, rozanolixizumab, lebrikizumab, upadacitinib, nipocalimab, deucravacitinib (Sotyktu), filgotinib (Jyseleca), spesolimab (Spevigo)
- ibi311 (SYCUME), zilucoplan (Zilbrysq): brand_name + display_name set

**Overlap:**
- 4 lowercase values fixed: alx-fcrn, vtx002, bcd-261, spy230
- 4 Ailux-context DCS promotions: nipocalimab, efgartigimod, rozanolixizumab → Direct; golimumab → Same-Space
- epi-001, ep006: Watch → Direct (TL1A drugs with Direct in IBD DCS)
- sim0500 IBD DCS: Direct/very_high → Watch/low (myeloma drug, not IBD — was a migration artifact)
- CLD-423: tl1a, uc, cd DCS rows inserted (Direct/very_high)

**Company attribution:**
- kt502: originator=kali, owner=sanofi, ownership=acquired
- amlitelimab: cleared incorrect ownership_status=acquired, originator=sanofi
- partner_company filled: afimkibart→Telavant, erd-1/hxn-1002→Sanofi, lq080→Zymeworks, tulisokibart→Merck

**Deals:**
- 68 duplicate deal rows deleted (nightly pipeline was re-writing same events)
- 28 duplicate intel rows deleted
- 3 near-duplicate Candid rows deleted
- 44 deal_type values normalized (license→licensing, collab→collaboration, AI platform→collaboration, etc.)
- Deals total_usd_m filled: Novartis/SciNeuro $165M, Arrowhead $200M, Sironax $175M

**Display names:**
- 8 catalog drugs: SPY001/003/072/130 + hxn-1002 + deucravacitinib + filgotinib + spesolimab set

**DCS cls:**
- 8 DCS rows with free-text cls normalized (Anti-FcRn mAb discontinued, OX40L blocker, etc.)

### Round 3 — Pipeline fix (committed to GitHub)
- `scripts/research.py` updated: pre-fetches existing deal + intel headlines at write start, skips items already in DB (120-day window). **Commit 7568bd5c**. Prevents tonight's 2 AM run from re-accumulating duplicates.

---

### Cycles 1–3 — Discovery Queue + 3× Audit/Fix (2026-06-02 ~01:30–02:45Z)

**queue-processor.yml created and run 3× total (Runs #1, #2, #3):**
- Run #1: 65 never-enriched drugs processed → 81 actions (ailux_angle, differentiation_thesis, mechanism, indication_short, drug_summary filled across EULAR/ASCO/new drugs)
- Run #2: 34 company-level items → 126 actions (differentiation_thesis for 12 more drugs including CLN-978, ABBV-382, ABBV-668, Lutikizumab, APG333, Tozorakimab, etc.)
- Workflow now runs nightly at 6 AM ET as standing maintenance

**Audit Cycle 1 fixes:**
- 26 validation warnings → 0 (23 stage_trial_match acknowledged for CDE/unregistered drugs; 3 field_consistency fixed)
- apg777 target: IL-13 → IL-4Rα × OX40L (bispecific target was wrong)
- lonigutamab target: IGF-1R → TSHR (anti-TSHR mAb had wrong target)
- crn12755 target: TSHR → SSTR2 (SST2 agonist had wrong target)
- del-zota drug_format: bispecific → AOC (antibody-oligonucleotide conjugate)
- ep006 target: TL1A → TL1A × [undisclosed]
- CLD-423, ALX002, Natalizumab: mechanisms written
- ALX001 ailux_angle: XPF005 hallucination removed (pre-existing in DB)
- 4 stuck "processing" items reset (ALX001, ALX002, immunovant, viridian)

**Audit Cycle 1 — completeness:**
- 0 drugs missing drug_summary (was 9; wrote summaries for ibi311, vtx002, mhb018a, oln102, ibi302, natalizumab, tislelizumab, lonigutamab, crn12755, sp-1351)
- 0 Approved drugs missing brand_name (Tysabri + Tevimbra added)

**Audit Cycle 2 fixes:**
- DCS rows added for kt502, lbl-051-s3, metis-mrna-cd19bcmacd3 (platform_view/tcell + strategic_view/autoimmune)
- source_url filled for 5 drugs via CT.gov: spesolimab, deucravacitinib, vtx002, tozorakimab, metis-mrna
- tozorakimab target: IL-33 (anti-ST2) → ST2 (IL-33R)

**Final state — Cycle 3 verification:**
- 0 validation issues ✅
- 0 governance violations ✅
- 0 null mechanism ✅
- 0 null drug_summary ✅
- 0 null ailux_angle ✅ (natalizumab fixed)
- 0 null target (Direct/Adjacent) ✅
- 0 brand_name/stage mismatches ✅
- 0 queue pending/processing ✅
- source_url: 123/174 (70%, was 67% before this session)
- DCS: 167 unique drugs covered

---

## Final State
**11/11 verification checks passing.** Drugs: 174 | DCS: 317 | Deals: 140

---

## Open Items (priority order)

### P1 — Enrichment backfills
- **bd_angle: 78 company_profiles null** — requires nightly company_enrichment.py (not queue-processor). Verify GitHub Actions ran 2026-06-02. Check again on next session.
- **source_url: 51 drugs missing** — was 59; now 51. 3 Direct drugs unregistered on CT.gov (cld-423, lbl-051-s3, hxn-1002 — legitimate). Rest need molecule_enrichment.yml.
- **drug_summary: 0 missing** ✅ — fully resolved this session.

### P2 — Data gaps found in audit
- **10 catalog drugs missing drug_indications** — ropeginterferon (PV), natalizumab (MS/CD), tislelizumab (oncology), del-zota (DMD), kt502 (autoimmune), del-braxlosiran (FSHD), sac-tmt (TROP2 cancers), del-etedesiran (DM1), lbl-051-s3, metis-mrna-cd19bcmacd3. All need indication rows added.
- **m701 partner unknown** — YZY Biopharma TL1A mAb; partnership_type cleared (was wrong). Needs research to identify licensee if any.

### P3 — Low priority
- **WuXi Biologics parent** — add wuxi_apptec company, link parent_company_id
- **Rename anti-tl1a-xpf005-arm → alx001** — cosmetic, data correct, requires FK audit across DCS/deals/rankings
- **afimkibart 3-hop chain** — Roivant→Telavant→Roche. Asset transfer history v41 should capture full lineage.
- **amlitelimab co-discovery** — Sanofi/Regeneron platform. If Regeneron credit needed, add company_partnerships row.

---

## Decisions Needed
1. **Veligrotug June 30 FDA decision** — auto-update dashboard or manual?
2. **drug_indications backfill** — auto-enrichment batch or manual curation for 10 missing drugs?
3. **bd_angle enrichment** — check GitHub Actions logs for 2026-05-31 run status.
