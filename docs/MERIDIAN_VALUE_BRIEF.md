# What Meridian Is — A Teaching Brief

A clear, sharable explanation of what this platform is and why it matters. Written to be read aloud to someone seeing it for the first time. Every line states what is true and why it counts.

---

## The one-sentence version

**Meridian is a trusted, source-traceable intelligence graph for biopharma business development** — it maintains a living, validated model of every competitive asset: what it is, who controls it, how it differentiates, and when the window to act on it opens.

---

## The job it does

Business development runs on a flood of inputs — press releases, ClinicalTrials.gov, SEC filings, conference abstracts — and rewards clear decisions. Meridian converts that flood into decisions. Each fact it learns becomes **structured, attributed to a source, validated against ground truth, and linked to every other fact.** So the working question rises from "what happened today" to "what does today change about which molecule to move on, in which indication, and when."

The product thesis, stated plainly: **companies want trusted intelligence, and Meridian delivers it.**

---

## The seven things that define it

1. **A knowledge graph.** Drugs, targets, indications, companies, deals, and trials are linked entities. A single question — "show Company X's full effective pipeline including licensed-in assets" — returns a complete answer because the relationships are modeled.
2. **A source on every fact.** Each claim lives in `drug_sources` with its URL, source type, and a confidence of confirmed, inferred, or unverified. Every assertion traces back to its origin.
3. **Model-versus-ground-truth comparison.** The model's output is measured against Kyle's confirmed reviews, and agreement is tracked over time.
4. **A human review loop that teaches the system.** Confirmations become training signal — the flywheel — so the model grows more fluent in this exact domain with every pass.
5. **An error memory.** Each correction is recorded with its reason (the validation-failure taxonomy), so the platform learns the shape of past mistakes and improves around them.
6. **Relevance scoring.** Competitive scores, landscape-dependency scores, and coverage scores rank what deserves attention for Ailux's specific assets.
7. **A full audit trail.** **66 database triggers** capture every change to 38 core tables into `field_change_audit` — roughly 60,000 recorded changes. Every edit leaves a trace, which is what makes the intelligence defensible.

---

## The insights this workflow uniquely produces

Because the data is connected and validated, the pipeline answers questions a single source leaves open:

- **Effective pipeline.** Originator and owner are modeled as distinct facts, so a competitor's true reach — including in-licensed and co-developed assets — stays visible (AbbVie's TL1A position via ABBV-701/FutureGen is a canonical example).
- **Deal-sequencing windows.** The system knows the right moment: AbbVie becomes a clean target for a TL1A bispecific after the ABBV-701 Phase 1 readout (Oct 2026).
- **Whitespace.** Target-pair combinations that remain open (`target_pair_whitespace`) — the rarest and highest-value BD signal.
- **Molecular differentiation.** Format, half-life, dosing, and IL-23 arm selectivity explain why a p19-selective bispecific leads a p40-blocking one.
- **Timing intelligence.** Catalysts and patent cliffs lay out the calendar of when value is created.
- **Patient-anchored value.** Every competitive read traces down to unmet patient need, so positioning rests on biology.

---

## How the data flows (the 30-second mental model)

**Ingestion → Enrichment → Scoring → Validation → Synthesis → Presentation**, wrapped by two loops: the **flywheel** (your reviews teach the next enrichment) and the **freshness signal** (every pipeline stamps `system_status`, the dashboard shows when new intelligence lands). A **health monitor** records every workflow run into `pipeline_runs`, so the factory reports on its own state.

The platform surfaces 74 tables to the dashboard today and holds a deep reserve of structured intelligence behind them — partnerships, source provenance, whitespace, and BD recommendations — ready to surface in priority order.

---

## How to demo it in 60 seconds

1. Open the **workflow map** → *Run health*: "a live, self-monitoring intelligence factory — 24 pipelines, 167 tables, now watched by a health monitor."
2. *Connections*: "every fact is a connected, sourced node; here is exactly what reaches the user and what comes next."
3. Click a node → click a table: "trace any table to the pipelines that produce it and the scripts that consume it."
4. Open the **Meridian Issue**: "each morning it composes the day's BD-relevant changes into a written brief, with first-mention links back to the graph."

---

## The honest edge

The moat is the **accumulated, corrected, source-linked graph.** Kyle's first philosophy captures it: *"Being wrong is okay; we just want to be correct more often. The more evidence we collect, the easier it is to know."* Every correction sharpens the next answer, and that compounding belongs to Meridian alone — a competitor with the same model still starts from an empty graph. The value lives in the connections, and the connections grow every day.
