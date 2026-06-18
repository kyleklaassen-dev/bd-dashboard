# §A.2 — UI / Logic Separation (analysis + plan, 2026-06-18)

> **Goal (ROADMAP §A.2):** the dashboard should *display trusted data*, not *decide truth*. Identity,
> stage, scoring, and dedup rules belong server-side (written once, governed, audited); the browser
> should read the result. This doc inventories what the client actually decides today — now that the
> JS is modular (`assets/js/`, §4 done) — and right-sizes the work.

## TL;DR — §A.2 is mostly already satisfied
The ROADMAP framing ("`_resolveStage`/`_score`/`_dedup`/`canonical` ×61 + `partnership_verified` writes")
overstated the gap. Measured against the extracted modules, most of those are **already reading
server-authoritative data or are pure display formatting.** The only genuine client-side *truth
inference* left is a single heuristic in `_resolveStage`. Detail below.

## Inventory (call-sites counted across `assets/js/` + `index.html`)

| Symbol | Sites | What it actually is | §A.2 status |
|---|---|---|---|
| `_score(n,max)` | 368 | **Display formatter** — returns a color-coded `<span>n/max</span>`. Does NOT compute a score; renders a pre-computed one. | ✅ Leave client-side (rendering, not truth) |
| `canonical*` | 61 | Reads `drugs.canonical_drug_id` + the `canonical_drugs` table (server owns canonical identity). Client displays / counts. | ✅ Already server-authoritative |
| `partnership_verified` | 15 | A stored boolean on partnership rows; client renders a ✓/? pill (`_vPill`). | ✅ Already server-authoritative (stored field) |
| `_dedupeDeals(deals)` | 2 | **Render-time** keyword-overlap dedup of the deals feed (`core.js:701`). Client decides which deals are dups. | 🟡 Minor — low-stakes display feed |
| `_resolveStage(d)` | 6 | Derives display stage from `stage` / `brand_name` / `indication_short` (`dkn.js:248`). | 🟡 The one real item — see below |

## `_resolveStage` — the only genuine truth-derivation, decomposed
```js
function _resolveStage(d) {
  const s = (d.stage || '').toLowerCase();
  if (s.includes('approv')) return 'Approved';                       // (A) display normalization
  if (d.brand_name) return 'Approved';                               // (B) REDUNDANT — writer-enforced
  if (d.indication_short && /\(20\d{2}\)/.test(d.indication_short))   // (C) client-only INFERENCE
      return 'Approved';
  return d.stage || 'Preclinical';                                   // (D) trust the DB
}
```
- **(A)** `approved_us`/`approved_eu`/… → "Approved" — legitimate **display normalization** of a server value. Keep client-side (or expose a server `stage_display`).
- **(B)** `brand_name ⇒ Approved` — **redundant**: `DrugWriter._validate` (drug_writer.py:73–77) already rejects any write where `brand_name` is set but `stage` ∉ `APPROVED_STAGES`, and nulls `brand_name="—"`. So a writer-written row already has `stage` approved whenever `brand_name` is set. The client rule can only ever mask a non-writer (raw) write — which governance forbids anyway. **Safe to drop once we confirm no raw-write rows violate it.**
- **(C)** year-in-`indication_short` ⇒ Approved — a heuristic the **server does not capture**. This is the real client-side truth inference. It can DISAGREE with the writer-enforced `drugs.stage` (e.g. a Phase-3 drug whose `indication_short` mentions a 2019 approval of a *different* indication would be shown "Approved"). **This is a governance decision for Kyle**, not a mechanical move.
- **(D)** fallback to `d.stage` — correct (trusts the DB).

## Recommended sequence (lowest-risk first) — each needs the writer-test + a data check
1. **Audit, don't change (read-only, do first).** Query all dashboard-visible drugs and compute, for each,
   client-`_resolveStage(d)` vs the raw `d.stage`. Three buckets: (i) agree, (ii) differ only via rule (A)
   normalization, (iii) differ via (B) or (C). If bucket (iii) is empty, `_resolveStage` is provably
   redundant and can be reduced to a pure (A) normalizer with zero display change.
2. **If (C) fires on real rows:** decide with Kyle — either (a) backfill the correct `stage` for those rows
   through `DrugWriter` (server becomes right, heuristic removed), or (b) keep the heuristic but move it into
   a server `stage_resolved` column computed at write time so the dashboard reads one trusted field.
3. **`_dedupeDeals`:** optional — move to a write-time/`deals` dedup if the feed shows dup noise; low priority.

## What NOT to do
- Don't move `_score` server-side — it's a formatter; 368 sites of churn for no truth gain.
- Don't touch `canonical*` / `partnership_verified` — already server-owned; the client only displays them.
- Don't change `drugs.stage` data or add columns without a validation query + Kyle's approval
  (CLAUDE.md: no DB write path without validation; data-model changes are approval-gated).

## Step 1 audit — RESULTS (2026-06-18, read-only over all 181 drugs)
| bucket | count | meaning |
|---|---|---|
| client `_resolveStage` == `db.stage` | 169 | no client divergence |
| differ via (A) approved-normalization | 5 | `approved_us`→"Approved" — display-only, expected |
| differ via (B) `brand_name`⇒Approved | **7** | ⚠️ DB `stage` not approved despite a brand_name |
| differ via (C) indication-year heuristic | **0** | the heuristic is **dead** — never fires |

**Finding 1 — (C) is dead code.** 0/181 rows resolve via the indication-year heuristic. It can be removed
with zero display impact — **but only after Finding 2 is fixed** (see ordering below).

**Finding 2 — (B) masks 7 stale `drugs.stage` values (data-integrity).** Seven *marketed* drugs have a
`brand_name` but a non-approved `stage`, so the dashboard only shows them "Approved" via the client band-aid:

| drug | db.stage | brand | actually approved? |
|---|---|---|---|
| rozanolixizumab | Phase 3 | Rystiggo | ✅ FDA 2023 (gMG) |
| benralizumab | Phase 3 | Fasenra | ✅ FDA 2017 (asthma) |
| mepolizumab | Phase 2 | Nucala | ✅ FDA 2015 |
| upadacitinib | Phase 3 | Rinvoq | ✅ FDA 2019 |
| tralokinumab | Phase 3 | Adbry | ✅ FDA 2021 (AD) |
| nipocalimab | Phase 3 | Imaavy | ✅ FDA 2025 (gMG) |
| lebrikizumab | Phase 3 | Ebglyss | ✅ FDA 2024 (AD) |

These violate CLAUDE.md's hard rule (`brand_name ⇒ approved stage`) and would be rejected by `DrugWriter`
today — so they predate the writer or were written raw / had the brand added without re-validation. The
dashboard's correctness here depends entirely on the client masking them.

## Correct sequence (revised by the audit)
1. ⚠️ **Fix the data FIRST (governance-gated — needs Kyle).** Correct `drugs.stage` → the right approved
   stage for the 7 rows **via `DrugWriter`** (the governed path; it validates `brand_name⇒approved` and
   writes the audit row). Each needs a source URL per the approval rule. This is a core-`drugs` write to
   BD-facing competitor stages → **do not do autonomously.** Recommended, with the evidence above.
2. **Then simplify `_resolveStage`** to (A)+(D) only — drop the now-redundant (B) and dead (C). After step 1
   the DB `stage` is authoritative, so the client just normalizes the display string. Verify via the preview
   loop (the 7 drugs still show "Approved" because the DB now says so, not the band-aid).
3. **`_dedupeDeals`:** optional, low priority.

> **Do NOT reorder.** Removing the client (B) band-aid before fixing the data would display 7 marketed drugs
> as "Phase 3" — a visible regression in BD-facing intelligence.

## Status
Analysis + read-only audit done. No code/data changed. The one concrete next action is the 7-row `stage`
correction — governance-gated (core `drugs` table, competitor intelligence), so it awaits Kyle's go-ahead.
ROADMAP §A.2 updated to this right-sized scope.
