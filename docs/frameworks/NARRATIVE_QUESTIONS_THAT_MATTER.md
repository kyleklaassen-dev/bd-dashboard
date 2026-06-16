# Meridian Narrative — The Questions That Matter

**Purpose.** Depth is not the volume of facts in a narrative — it is the *sophistication of
the questions the narrative answers.* A list of trials is shallow; "this asset suppresses
>90% of its target yet 70% of patients still don't remit, so the class ceiling is escape
biology, not potency" is deep. This document defines the questions a Meridian narrative must
answer, in priority order, with the data that answers each and the trust standard it must meet.

**Prepared 2026-06-05.** Companion to `NARRATIVE_KNOWLEDGE_LAYER.md` (the how) and
`DATA_INTEGRITY_SOP.md` (the trust). Every answer is either a **sourced fact** or a
**labeled inference** — never an unmarked assertion.

---

## The principle: a narrative climbs four rungs

1. **Description** — what is it? (facts)
2. **Comparison** — how does it stack up? (facts in context)
3. **Interpretation** — what does it mean? (labeled inference over facts)
4. **Action** — what should *we* do, and when? (the BD decision)

The v1 narrative reached rung 1–2. "Deeper" means climbing to 3–4 *without ever ungrounding
from rung 1.* The questions below are organized so each answer feeds the next rung.

---

## The question hierarchy

Ordered by the patient→molecule→evidence→market→deal→timing→synthesis arc. For each: the
**sophisticated question**, the **data** that answers it, and whether it is **fact or inference**.

### 1. The patient — who needs this, and how badly?
- How large and how underserved is the population, and where does the drug sit in the
  treatment cascade? `indication_patient_intelligence` (counts, biologic-failure rate,
  `treatment_cascade`). **Fact.**
- **Who fails current therapy, and why?** `non_responder_profiles` (escape pathways,
  TE≠efficacy). The most under-asked question in competitive intel. **Fact + inference.**
- What do patients actually prioritize — route, frequency, oral? `patient_reported_priorities`.
  **Fact.**

### 2. The molecule — what is it, really, and why might it win or lose?
- Format, modality, valency, Fc engineering, epitope, half-life. `molecule_intelligence`,
  `drug_pk_parameters`. **Fact.**
- **Is there a responder-selection / biomarker strategy?** `drug_biomarkers` (currently a
  *gap* — see §collection). For tulisokibart this is the whole Prometheus thesis. **Fact.**
- What is the molecular differentiation vs the field (durability of dosing, selectivity)?
  Derived from molecule + PK vs competitors. **Inference.**

### 3. The evidence — does it work, how well, and can we believe the early data?
- Efficacy with comparator, dose, timepoint, indication. `drug_clinical_benchmarks`, `trials`.
  **Fact.**
- **Target engagement vs efficacy** — does hitting the target translate? (tulisokibart:
  >90% sTL1A suppression, ~70% non-remission → the dissociation that defines the ceiling).
  `non_responder_profiles`, PD. **Fact + inference. The single most sophisticated efficacy question.**
- Durability / maintenance, not just induction. `trials` (long-term), benchmarks. **Fact.**
- Safety/tolerability and its differentiation. (collection gap for most assets). **Fact.**

### 4. The competition — who else, and how do they truly differ?
- Direct competitors, stage, sponsor. `drugs` (shared target) + `drug_targets`. **Fact.**
- **How do they differentiate** — format (mAb vs bispecific), dosing (IV vs SC), biomarker
  vs all-comers, efficacy delta? `drug_study_design_comparisons`, `efficacy_benchmarks`.
  Turns "31 competitors" into a matrix. **Fact + inference.**
- **Where is the white space** — unaddressed segment, mechanism, geography? Derived from the
  landscape + non-responder biology. **Inference.**

### 5. The deal — who owns it, what's it worth, is it available?
- Owner, how acquired, precedent valuation. `deals`, `asset_transfer_history` (tulisokibart:
  Merck bought Prometheus for **$10.8B**, Phase II at signing). **Fact.**
- What does the comparable-deal landscape imply for the next TL1A transaction? `deals` across
  the area. **Inference.** (Directly informs Ailux pricing.)
- Availability / partnership status. **Fact.**

### 6. The clock — what happens next, when, and what does it gate?
- **Next catalyst, date, and what it unlocks** (approval, deal, go/no-go). `catalysts`
  (tulisokibart: Aug 2026 Phase 3 UC primary completion). The early-warning North Star. **Fact.**
- Readout *sequence* and the decision windows it creates. `catalysts` ordered. **Inference.**
- **Ailux deal-sequencing constraint** — can we act now, or does a rule block it (AbbVie/Oct
  2026)? `deal_sequencing_constraints` + governance. **Fact + the action trigger.**

### 7. The synthesis — so what, for Ailux? *(the labeled "Meridian Analysis" tier)*
- Is this a competitor, partner, acquisition target, or threat — and why? `risk_summary`,
  `bd_angle` + the above. **Inference (labeled).**
- **The one thing that could change the story** — the key dependency/risk. **Inference.**
- Where does this asset create or destroy value for Ailux's molecule? **Inference.**

### 0. The meta-layer — how much should we believe this? *(cross-cutting)*
- **Triangulation**: how many *independent* sources back each claim, of what type, how recent?
  A claim with CT.gov + the NEJM paper + the deal PR is stronger than one CT.gov row. Render
  the count and let the reader drill into the evidence.
- **Contested / unverified**: what does the graph *not* know, or disagree on? Show gaps
  honestly (the validator already flags fabricated/missing sources). Trust = showing the seams.

---

## What this implies for the build

**Tier expansion (surface what's already collected — fact rungs 1–3,5,6):**
deals/ownership · catalyst timeline · molecule characterization · non-responder/TE-vs-efficacy ·
patient journey. Mostly plumbing over verified rows.

**The Meridian Analysis tier (rung 3–4):** a clearly-labeled inference section answering §7,
every clause resting on a cited fact atom. The database-to-strategist leap.

**Source triangulation + drill-down (meta-layer):** group provenance by *claim*, count
independent sources, surface type/recency, make each claim expandable to its evidence. This is
"depth of trust" and it is what separates Meridian from an AI summary.

**Collection (close the gaps):** `drug_biomarkers` (0 — central to tulisokibart's thesis),
`payer_tpp_criteria`, head-to-head competitor efficacy, safety. Via the disambiguated
evidence-collection pipeline, with the SOP's entity-disambiguation and URL validation.

**Build order:** facts before interpretation before action. Wire the collected-fact tiers and
triangulation first; the Analysis tier sits on top of them; collection runs in parallel as the
engine. Every tier ships with its own validation — each one will surface new data-quality
issues (we have already found fabricated DOIs, misattributed trials, duplicate catalysts).

> The test of depth: can a BD lead read one narrative and know *what the asset is, whether it
> works, who it beats, what it's worth, when to act, and what we'd do* — each claim traceable
> to its source, each judgment marked as judgment.
