# NEXT SESSION — BD Platform

**Written:** 2026-05-24 (Session 31)  
**Last work:** Phase 2 target coverage + ACTIVE_IN edges  
**Validation:** 995 pass / 0 fail / 5 skip ✅

---

## Session 31 Summary

### Phase 2 target coverage (84.2% → 89.5%)
- 4 new targets: `a4b7_il23p19`, `il1ab`, `cd40`, `ige`
- 9 drug_targets rows for SPY120, SPY130, Lutikizumab, Iscalimab, Omalizumab
- 85/95 area-linked drugs now have ≥1 primary target

### ACTIVE_IN edges (migration v29)
- 137 `entity_edges ACTIVE_IN` rows seeded from all `company_areas` rows
- Graph now answers "who is active in [area]?" as a single predicate lookup
- Validation test id=1077

### entity_edges predicate inventory
| Predicate | Count |
|-----------|-------|
| COMPETES_WITH | 600 |
| TARGETS | 146 |
| ACTIVE_IN | 137 |
| **Total** | **883** |

---

## Meridian L3 Status

With ACTIVE_IN edges complete, all three relationship gaps from the maturity assessment are now addressed:
- COMPETES_WITH ✅ (600 edges)
- drug → TARGETS → target ✅ (146 edges)
- company → ACTIVE_IN → area ✅ (137 edges)

**Meridian is now at L3.** The graph can answer landscape-level questions from stored relationships, not runtime joins.

---

## Next Steps (in priority order)

### P1 — Graph consistency: write ACTIVE_IN on new company_areas writes
`company_intake.py` currently writes to `company_areas` but not `entity_edges`. When a new company is onboarded or a new area added, both tables must stay in sync. Add `write_active_in_edge()` to `company_intake.py` (pattern: same as `write_acquisition_edges()`).

### P2 — Target coverage: resolve remaining 10 unmapped drugs
Remaining unmapped area-linked drugs (89.5% → ~95%+ potential):
| Drug | Issue |
|------|-------|
| cnd319, cnd460, kt501 | Trispecifics — add trispecific target nodes |
| guselkumab-golimumab | Combo study — map each component separately |
| abbv-668 | Verify target; likely IL-13 or related |
| gb004 | Verify (Gossamer Bio — likely TL1A or S1P related) |
| ianalumab | BAFF-R — add target node |
| kyv-101 | CAR-T (CD19) — add cd19 as primary target |
| linsitinib | IGF-1R — already exists, just map the drug |
| lm-302 | Verify target |

linsitinib and kyv-101 look like easy wins (targets already exist).

### P3 — Graph queries as Meridian capabilities
Now that COMPETES_WITH + TARGETS + ACTIVE_IN are all in `entity_edges`, the graph supports:
1. "Who is active in IBD?" → ACTIVE_IN WHERE object_id='ibd'
2. "Which drugs compete with [drug X]?" → COMPETES_WITH WHERE subject_id=X
3. "What does [drug X] target?" → TARGETS WHERE subject_id=X
4. "Which companies have TL1A programs?" → ACTIVE_IN WHERE object_id='tl1a'
5. "Which drugs target IL-23p19?" → TARGETS WHERE object_id='il23p19'
6. "What are Sanofi's active areas?" → ACTIVE_IN WHERE subject_id='sanofi'

Consider wiring one or more of these into the Meridian research prompt as graph-grounded context.

### P4 — Maturity docs update
Update `docs/meridian_maturity_assessment.md` to reflect L3 milestone. The three transitions that completed it, and what L4 would require.

---

## Active Uncertain Cases

### drug_targets — easy wins still unmapped
| Drug | Target | Action |
|------|--------|--------|
| linsitinib | IGF-1R (`igf1r` exists) | Just add drug_targets row |
| kyv-101 | CD19 (`cd19` exists) | Just add drug_targets row |
| ianalumab | BAFF-R (new target needed) | Add `baffr` target + row |

### COMPETES_WITH — uncertain bispecifics not yet seeded
| Drug | Target text | Issue |
|------|-------------|-------|
| SPY230 | IL-23 + TL1A | Confirm bispecific → maps to tl1a_il23p19 |
| APG279 | IL-13 + OX40L | Confirm bispecific → new il13_ox40l target |
| SPY130 | α4β7 + IL-23 | ✅ Now mapped to a4b7_il23p19 |
| SPY120 | α4β7 + TL1A | ✅ Now mapped to tl1a_a4b7 |

---

## DB State (end of Session 31)
| Table | Rows |
|-------|------|
| entity_edges (COMPETES_WITH) | 600 |
| entity_edges (TARGETS) | 146 |
| entity_edges (ACTIVE_IN) | 137 |
| drug_targets | 182 |
| targets | 47 |
| validation_tests | 992 |
| validation suite pass rate | 100% (995/995 non-skip) |
