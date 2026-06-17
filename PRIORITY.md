# Meridian — Current Priority Stack

**Last updated:** 2026-06-16 (Stage 4 enforcement turned ON + Stage 1 residual data fixes applied).
**Rule:** Claude reads this at the start of every session before any other action, and updates it at the end of every session. Kyle reviews and corrects direction here, not mid-session.

---

## ▶ DOING NOW

**Stabilization sprint — single-writer enforcement is now REAL (channel + invariant).** Layer B is live: anon/authenticated can no longer INSERT/UPDATE/DELETE core tables (only the Writers' service_role can), with one column-scoped exception (the partnership-pill toggle). Layer A triggers hard-block 3 invariants (`edges.subject_drug_orphan`, `edges.object_drug_orphan`, `catalysts.must_link`); the rest log in WARN. **The stabilization freeze can lift.**

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
| **Stage 4** | **Enforcement — DONE.** Layer A: v157 observe-only triggers → v159/v160 hard-block `edges.subject_drug_orphan`, `edges.object_drug_orphan`, `catalysts.must_link` (per-rule allow-list `governance_enforced_rules`; observability in `governance_enforcement_log`). Layer B: v161 revoked anon/authenticated writes on all 4 core tables (service_role only), keeping a column-scoped anon grant for the partnership-pill. Verified end-to-end: phantom edge / orphan catalyst / anon field-write all rejected; writers + seeders green. | ✅ DONE (channel + invariant enforced). |
| **Stage 5** | Connectivity backfills + residual data. | 🔄 IN PROGRESS — 58 drugs still lack `drug_sources`; 26 catalysts unlinked. |

> **Live data counts (2026-06-16 PM):** drugs **192**, companies 191, deals 218, governance unresolved 41, validation non-pass 35, orphan drug-edges **0**.

---

## QUEUE (in order)

| # | Item | Priority | Status | Notes |
|---|------|----------|--------|-------|
| 1 | **Service-role key rotation** | P0 | ⛔ Kyle's | Standing security item (key was once exposed in client). Claude can map consumers + verify after; rotation itself is Kyle's. |
| 2 | **Add Denali/Odyssey/Abivax/NewLimit as companies** → link the 9 area-only catalysts to them | P2 | Open | 17/26 catalysts linked to a drug/company; 9 remain area-anchored because their company isn't in the DB yet. |
| 3 | **(DONE) Layer B permission boundary** | — | ✅ 2026-06-16 | v161: anon/authenticated write revoked on core tables; service_role only; partnership-pill kept via column grant. |
| 4 | **(DONE) `drugs.company_id_required` enforced** | — | ✅ 2026-06-16 | v162: required on INSERT except `discovery_status='auto'` (the harvester transient). 12 company-less drugs are all auto → compliant. |
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
