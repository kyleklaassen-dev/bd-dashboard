# Meridian — Execution Plan (return-to-work)

**Prepared 2026-06-05 while you fly. Nothing structural was deployed unattended** — this is the plan to execute together on your return. Read on the plane; we start at the top when you're back.

Two tracks: **(A) event-driven verification** (the lag fix you asked for) and **(B) burning down the full Atlas gap backlog**. Track A is really Wave 0 of Track B — the re-chained nightly pipeline is the keystone that fixes ordering *and* delivers event-driven verification *and* enables daily scoring, all at once.

---

## PART A — Event-driven verification

### Today
- Enrichment (`company_enrichment`) runs midnight ET; Research runs 2 AM ET; the Writer chains off Research.
- Verifiers run on a **weekly clock** (Source: Mon/Thu, Content: Tue/Fri) — so a fact created Wednesday isn't content-verified until Friday, and Issues publish daily in between.
- Mitigation already live: the **pre-publish gate** drops fabricated-URL facts *every* day, and withholds any claim already marked `content_confirms_claim=false`.

### Target nightly chain (the change)
```
Research (ingest)
  → Source Verifier   (incremental: only rows unchecked since last run)
  → Content Verifier  (incremental: content_confirms_claim IS NULL)
  → [daily] Scoring   (competitive + landscape, see Wave 0)
  → Meridian Writer   (gate now sees fully-verified facts)
  → Morning Summary
```
Every link is a GitHub Actions `workflow_run` trigger, so each step waits for the prior to succeed. The Issue can then only cite facts that were verified **that same night**, shrinking the lag window from ~3 days to ~0.

### Exact changes (staged, ready to apply on return)
1. **Incremental flags** (small, safe, additive):
   - Content Verifier already incremental (`content_confirms_claim IS NULL`). ✓
   - Source Verifier: add `--new-only` (filter URLs by `url_last_checked` null/older-than-N-days). ~15 lines.
2. **Re-chain via `workflow_run`** (the structural decision — needs your sign-off on the order):
   - `source-verifier.yml`: add `workflow_run: ["Meridian Research"]`, keep the weekly cron as a fallback.
   - `content-verifier.yml`: add `workflow_run: ["Source Verifier"]`.
   - `meridian-write.yml`: re-point its chain from `["Meridian Research"]` → `["Content Verifier"]` (keep the 6:30 cron fallback; the one-Issue-per-day guard makes the fallback safe).
3. **Verify-at-publish backstop** (optional, tightest): have the Writer content-check the *specific* handful of facts it is about to cite, on the spot. Closes the window entirely; adds ~30s + a few LLM calls per Issue.

**Decision for you:** confirm the target order above (especially putting Writer behind the verifiers), and whether to add the verify-at-publish backstop (#3) or rely on the chain (#2).

---

## PART B — Gap backlog, sequenced

35 gaps in the Atlas registry; 8 fixed during this engagement; **27 open**. Sequenced below by dependency → value → risk. Tags: **effort** S/M/L · **risk** Low/Med/High · **decision** = needs your judgment before I act.

### Wave 0 — Foundation (the keystone; do first)
| Gap | Action | Effort | Risk | Notes |
|---|---|---|---|---|
| Enrichment runs before ingest · Daily Issues read weekly scores · half clock-ordered | **Re-chain the nightly DAG** into real dependency order (ingest → enrich → verify → score → write) | L | Med | **decision** — reshapes the nightly schedule. Delivers event-driven verification + daily scoring + kills 3 ordering gaps at once. |
| Scoring runs weekly, read daily | Make competitive + landscape scoring a **daily** step in the chain (or post-enrichment) | M | Low | Falls out of Wave 0 |

### Wave 1 — Trust & content quality (mostly safe, high value)
| Gap | Action | Effort | Risk | |
|---|---|---|---|---|
| Event-driven verification | Apply Part A (#1, #2) | M | Med | decision on order |
| Validation lags up to a week | Run `validate_ground_truth` daily (or after enrichment) | S | Low | |
| Completeness scored on 1/3 of drugs | Run `compute_coverage`/`rescore_completeness` catalog-wide; schedule it | M | Low | |
| 28 drugs lack company_id | Research + attribute (governance: originator) | M | Low | per-drug web research |
| 22 drugs lack source_url | Source them (or mark unverified) | M | Low | |
| Enrichment cost tokens stay 0 | Record `usage.input/output_tokens` into `enrichment_runs`; add a cost tile | S | Low | |
| Content-disconfirmed claims | Wire into Writer gate | — | — | **DONE this engagement** |

### Wave 2 — Surfacing (needs your eye — live dashboard UI)
| Gap | Action | Effort | Risk | |
|---|---|---|---|---|
| 7 DARK tables not surfaced | Surface in priority order; **start `drug_sources` (provenance on the drug card) + `company_partnerships`** | L | Med | decision on UI design |
| Strategic Lens not in dashboard | Fold the TL1A lens into `index.html` | M | Med | |
| Health tile (pipeline_runs) | A dashboard tile reading `pipeline_runs` | S | Low | held for your eyeball |
| next_gen_rankings orphan-write | Wire the movement-arrow consumer or retire | S | Low | |

### Wave 3 — Cleanup & decisions (judgment calls)
| Gap | Action | Effort | Risk | |
|---|---|---|---|---|
| 9 INERT tables (patent cliffs, portfolio conflicts, BD readiness, Ailux strategic context…) | **decision**: revive a producer for each, or retire | L | Med | strategically valuable — recommend revive |
| 80/110 scripts unscheduled | Schedule the live producers (bd_recommender, generate_landscape_briefing…); archive true one-offs | M | Low | |
| 3 overlapping research scripts | Consolidate into one ingest service | M | Med | |
| write_ranking_snapshots ×3 | Single-owner it | S | Low | |
| drugs table ~120 cols | Pick canonical field per concept; deprecate dupes | M | Med | decision |
| field_change_audit ~60k, no retention | Add retention/rollup | S | Low | |
| residual anon-write tables | Move drugs/discovery_queue/submitted_intel writes behind Supabase Auth | M | Med | decision |
| Python version drift | Standardize to 3.12 (safe now that monitoring exists) | S | Low | |

### Wave 4 — Loose ends
| Gap | Action | Effort | Risk | |
|---|---|---|---|---|
| jnj-tcell / amgen-fcrn flagged tests | Add the asset, or retire the test | S | Low | decision |
| Flywheel option 2 (fine-tune) | Format JSONL → Anthropic fine-tune; evaluate signal | L | Med | decision (cost) |
| fetch-news double-trigger · review-vs-action cadence | Minor schedule tidy | S | Low | |
| Weekend Sprint last-red | Confirm self-healed on this weekend's run | S | Low | |

---

## PART C — First session when you're back

1. **5 min:** open the Atlas → Gap registry; confirm Wave priorities and the few **decision** items above (nightly order, INERT revive-vs-retire, surfacing design, schema canon).
2. **Then execute top-down.** Suggested first concrete moves:
   - Wave 0: I draft the re-chained orchestrator for your review → deploy → watch one nightly cycle in the health monitor.
   - Wave 1: flip verifiers to event-driven (Part A), schedule daily validation + completeness scoring, wire token-cost capture.
3. **Verify each wave** via the health monitor + the validation suite (both already running).

### Already prepped / safe state for the flight
- Trust stack fully live: Source Verifier (now covers catalysts + drug_sources, detects search-URL fabrications), Content Verifier (Tier-4, scheduled), pre-publish gate, content-disconfirmed-claim withholding, health monitor.
- One-Issue-per-day guard (entry + save layers).
- veligrotug error fixed; CLD-423 deduped + primary-sourced.
- Nothing structural deployed unattended; the weekly verifier crons keep running so coverage continues while you travel.

> North star for the burn-down: every wave should make a fact *harder to get wrong and easier to trust* — the same principle the veligrotug fix was built on.
