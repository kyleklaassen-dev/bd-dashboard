# Meridian Foresight — North Star & the Prediction Ladder

**Written 2026-06-08.** This defines what the prediction system is ultimately *for*, and why
the calls we make today — clinical readouts, approvals, deal-value thresholds — are the
training set for the call that actually sells the platform.

---

## The ultimate goal (one sentence)

> **Call the specific business-development event before the market does:**
> *which acquirer buys or partners which molecule (target × indication), at what value, by when* —
> with a calibrated probability and an auditable rationale.

Not "a TL1A deal will happen in 2027." The apex call is **"Company X acquires Molecule Y
(Target Z × Indication W) for ~$N by quarter Q, and here is the evidence chain."** A BD team
that trusts that call knows where to look and what to move on before competitors do. That is
the product.

Everything else on the ladder exists to make that apex call *trustworthy*.

---

## The prediction ladder (why today's calls train tomorrow's apex call)

The system climbs four rungs. Each rung produces a labeled, scored outcome that calibrates the
rung above it. We deliberately keep calls at every rung — the lower rungs are not filler, they
are the training signal.

**L1 — Outcome (will the science work?)**
*Example: "tulisokibart ATLAS-UC meets its primary endpoint, Q4'26–Q1'27."*
Calibrates our read of the biology. A deal is only as valuable as the asset behind it, so the
ability to call a readout is the precondition for calling its consequence. Every resolved
readout teaches us how a given level of Phase 2 evidence maps to a Phase 3 result.

**L2 — Consequence (does the science become value?)**
*Examples: an approval; "AbbVie holds #1 IBD revenue share through FY27"; "an oral takes ≥40%
of new starts"; a deal clears a value threshold.*
Calibrates the link **evidence → commercial value → corporate action**. This is where market
data (TD Cowen share curves, pricing) becomes falsifiable. These calls teach the model what a
readout is *worth*.

**L3 — Deal thesis (who does what, for how much, when)** ← **the apex**
*Examples: "Abivax/obefazimod is acquired by a large-cap for ≥$5B by YE'27"; "AbbVie in-licenses
a second China-origin TL1A asset within ~12 months of the ABBV-701 readout."*
The specific, named, priced, dated BD call. Low base rate, high value. It can only be trusted
once L1/L2 calibration shows our stated 35% actually resolves ~35% of the time.

**L4 — Portfolio foresight (where the next wave forms)** *(future)*
*Example: "the next IBD target after TL1A/IL-23 to draw a ≥$1B deal is an oral / a TL1A-combo."*
Pointing at the target × indication that becomes the *next* TL1A before the field crowds in.
This is the long-horizon ambition; it is fed by the whitespace layer + resolved L1–L3 history.

---

## Why the lower rungs are not optional

1. **Calibration is earned, not declared.** A 35%-confidence acquisition call is only useful if
   our 35%s come true ~35% of the time. We can only prove that with a *volume* of resolved
   calls — and readouts/approvals resolve far faster than acquisitions, so they are the bulk of
   the early track record (Brier score, hit rate, the accuracy line on the tab).
2. **Same evidence graph.** A specific-acquisition call reads from the same substrate as a
   readout call: who owns the asset, its stage and data, who has the cash, who has the portfolio
   gap, what sequencing constraints apply (e.g., AbbVie can't move on a competing TL1A bispecific
   until after the ABBV-701 readout). Populating that graph for L1/L2 *is* the work that makes L3
   possible.
3. **Timing is a learnable error.** Date *ranges* (not single dates) let us grade whether we
   over- or under-estimated timelines, separately from whether we got the event right. That
   timing-error signal is what eventually lets us put a credible *quarter* on an acquisition.

---

## What "more specific" looks like going forward

Per Kyle (2026-06-08), the slate should keep pushing toward specificity along these axes, and
each new call should name as many as it can:

| Axis | Generic (early) | Specific (target state) |
|---|---|---|
| **Target** | "a TL1A asset" | TL1A × IL-23p19 bispecific |
| **Indication** | "IBD" | UC vs CD, line of therapy |
| **Target × Indication** | — | TL1A×IL-23p19 in TNF-experienced CD |
| **Asset** | "a China-origin asset" | named molecule / program |
| **Acquirer** | "a large-cap" | named company (Merck, AbbVie, …) |
| **Amount** | "≥$1.5B" | a band with a floor ($N–$M) |
| **Timing** | "by 2027" | a quarter range (Q4'26–Q1'27) |

The current slate spans all four rungs on purpose. As L1/L2 calls resolve and calibration
firms up, the center of gravity should shift toward L3/L4 — the named, priced, dated calls that
are the reason the platform exists.

---

## Predicting the same event *earlier*, with reasons (the learning loop)

Calling a deal is one axis; calling it **sooner** is the other. A correct acquisition call made
the week before the press release is nearly worthless; the same call made 18 months out is the
product. So every prediction is decomposed and time-stamped, and resolved calls feed a library
of reasons that let the next call move earlier.

**1. Decomposition — confidence is a sum, not a vibe** (`prediction_factors`, `base_rate`).
Every confidence number is built as a **base rate + signed adjustment factors**, each with a
type, a delta, and a rationale, that sum exactly to the stated confidence. Example (tulisokibart
ATLAS = 70%): 45 base + 20 (strong Ph2 delta) + 8 (Ph2→Ph3 precedent) − 3 (Ph3 stringency). When
the call resolves we see *which factor was right or wrong*, not just whether the headline hit.

**2. Early-signal factors — the reasons that buy lead time** (`is_early_signal = true`).
Some factors are the reasons we can see the event coming before the market: "positive Phase 3 +
NDA filing = standard takeout trigger," "AbbVie's repeat China-origin licensing pattern,"
"sequencing window opens after the ABBV-701 readout." These are flagged so they accumulate a
track record.

**3. Lead time — how early we actually were** (`lead_time_days`, set at resolution).
When a call resolves, the scorer computes `outcome_date − made_on`. Averaged across resolved
calls that shared an early-signal reason, this becomes **how far ahead that reason lets us see**.

**4. The signal library — reasons with a track record** (`v_signal_library`).
Each early-signal reason rolls up to: times used, times correct, hit rate, and average lead days.
Over time this answers "what patterns have actually preceded a deal, and by how long?" — turning
one-off rationales into a reusable, evidence-weighted playbook. The next acquisition call starts
from the reasons that have historically paid off, made earlier and with better-calibrated
confidence. *That* is the compounding asset.

**5. Change-log — every revision, with a reason** (`prediction_revisions`).
Predictions are living. Every edit — a confidence raise/cut, a reframe, a resolution, a window
change — is recorded with a mandatory reason. This is both an audit trail and training data:
later we can ask whether our revisions improved calibration (did lowering Immunovant after the
batoclimab failure prove right?). **Standing practice: keep adding new predictions, and never
change one silently — log what changed and why.**

## How this shows up in the product

- The **Predictions tab** tags each call by rung (Outcome · Consequence · Deal thesis) and shows
  a date **range**, the stated conviction, and — for deal theses — the named counterparty and
  value band.
- The **poll/scoreboard** (hit rate, Brier, accuracy line) is the calibration record that earns
  the right to make L3 calls.
- The **AIB** supplies the evidence chain each call cites; the **catalysts** ledger supplies the
  calendar (L0) that the miss-detection sweep grades against.
