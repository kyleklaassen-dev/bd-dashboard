# Meridian — Current Priority Stack

**Last updated:** 2026-06-16 (Stage 4 enforcement turned ON + Stage 1 residual data fixes applied).
**Rule:** Claude reads this at the start of every session before any other action, and updates it at the end of every session. Kyle reviews and corrects direction here, not mid-session.

---

## ▶ DOING NOW

**Stabilization sprint — enforcement is now partially REAL.** Credentials are restored. The single-writer boundary is enforced at the DB layer for graph referential integrity (the two `entity_edges` drug-orphan rules now `RAISE EXCEPTION`); the remaining invariants log in WARN mode until their data is cleaned and the Layer-B permission boundary lands.

**Freeze status:** still on, but lifting. What remains to fully lift it: (1) link the 26 unlinked catalysts → enforce `catalysts.must_link`; (2) decide the drug-discovery `company_id` policy → enforce `drugs.company_id_required`; (3) apply Layer B (REVOKE INSERT/UPDATE on core tables from anon/authenticated + an RPC write path) — the real "single physical writer."

---

## Stabilization stage board (TRUE state as of 2026-06-16 PM)

| Stage | What it is | Status |
|-------|-----------|--------|
| **Engine** | 15 core workflows re-enabled, healthy. Today's Issue ("The Meridian — June 16, 2026") generated on Opus, live. | ✅ DONE. |
| **Stage 0** | Production git wiring (one protected `main`, clean clone). | ✅ DONE. |
| **Stage 1** | Governance/validation triage **+ residual data fixes**. Applied: apg777/apg279 mis-targeting corrected (zumilokibart = anti-IL-13 mAb; APG279 = IL-13×OX40L FDC); duplicate molecules merged (ati-045→bosakitug, xmab5871→obexelimab); phantom drug codes purged (mk-1718, mdr-018); 6 company-as-drug edges deleted; cld-423 edges aliased onto the real `cldr-001`; 7 stale approved-drug stages flipped. **Orphan drug-edges 74→0; brand⇒approved violations →0; drugs 194→192.** | ✅ DONE. |
| **Stage 2** | 📡 Intelligence tab — 11 live datasets. | ✅ DONE. |
| **Stage 3** | Repo legibility (README, update_log trim, docs/ organize). | ✅ DONE. |
| **Stage 4** | **Enforcement.** v157 installed observe-only triggers on drugs/companies/catalysts/entity_edges (log to `governance_enforcement_log`). v159 escalated the 2 edge referential rules to `RAISE EXCEPTION` (per-rule allow-list `governance_enforced_rules`). Verified: a phantom-edge insert is rejected; a valid edge succeeds; all edge seeders (structural/deal/verify) green; 0 real writes blocked. | 🔄 PARTIAL — edge rules enforced; catalyst/drug/company rules still WARN; Layer-B permission boundary pending. |
| **Stage 5** | Connectivity backfills + residual data. | 🔄 IN PROGRESS — 58 drugs still lack `drug_sources`; 26 catalysts unlinked. |

> **Live data counts (2026-06-16 PM):** drugs **192**, companies 191, deals 218, governance unresolved 41, validation non-pass 35, orphan drug-edges **0**.

---

## QUEUE (in order)

| # | Item | Priority | Status | Notes |
|---|------|----------|--------|-------|
| 1 | **Service-role key rotation** | P0 | ⛔ Kyle's | Standing security item (key was once exposed in client). Claude can map consumers + verify after; rotation itself is Kyle's. |
| 2 | **Link the 26 unlinked catalysts** → then enforce `catalysts.must_link` | P1 | Open | All 26 are real (Denali DNL758, Viridian veligrotug PDUFA, Spyre SKYLINE combos, zumilokibart Ph3…). Match each to its drug/company, then add the rule to `governance_enforced_rules`. |
| 3 | **Layer B permission boundary** | P1 | Open | REVOKE INSERT/UPDATE on `drugs/companies/catalysts/entity_edges` from anon/authenticated + a SECURITY DEFINER write RPC. Confirm no pipeline writes via anon/authenticated first (they use service_role). This is what fully makes "single writer" physical. |
| 4 | **Drug-discovery `company_id` policy** → enforce `drugs.company_id_required` | P2 | Open | 12 company-less code-named drugs remain. Decide: require company at insert (may break discovery) vs. a quarantine stage. Then harden the rule. |
| 5 | **Backfill `drug_sources` for 58 drugs** | P1 | Open | Run evidence-collectors (free ct.gov/EuropePMC) to close the 30% source-coverage gap; 7 deals also lack source_url. |
| 6 | **apg777/apg279 graph re-sync** | P2 | Open | Their `TARGETS` edges still point to il4ra/ox40l; re-seed to il13/ox40l so the corrected target propagates to the graph + landscapes. |
| 7 | **Continue review→fix iterations** (accuracy + connectivity) | P2 | Ongoing | Build on each pass. |
| 8 | **Phase 3 modularization / Phase 4 index.html** | P3 | Plan authored | After enforcement fully lands. |

---

## North Star (read before every architectural decision)

> "Which molecule should Ailux bring to the clinic, in which indication, with which differentiated clinical hypothesis — and where does the competitive landscape create or close that window?"

Intelligence hierarchy: **Patient → Indication → Target → Company.** Value flows upward from patients, not downward from deal activity.

Stabilization north star: **exactly ONE approved, enforced path that can modify each core entity (drug, company, edge, catalyst).** "Single writer" is a convention until the database enforces it — success is measured by enforcement, not by "scripts were rewritten." (As of 2026-06-16, graph referential integrity is enforced; the rest is queued above.)

---

## Update Rules

- Claude updates `## ▶ DOING NOW` and the stage board / queue at the end of every session.
- Completed items get a date + note.
- Kyle corrects sequencing here — not mid-session in chat.
- Convert relative dates to absolute when editing.
