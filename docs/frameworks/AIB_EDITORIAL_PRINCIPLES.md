# Meridian AIB & Issue — Editorial Principles + Redline History

**Purpose.** This is the standing style guide for every Area Intelligence Brief (AIB) and Meridian Issue. It is built from Kyle's redline rounds and is meant to *teach future briefs how to be written* so the standard replicates without re-litigation. When writing or revising any brief, conform to the principles below; when a new redline round adds a principle, append it here and to the changelog.

**How to use.** The generator (`scripts`/`gen_aib_*.js`) is the source of truth for the document; this file is the source of truth for *how* it should read. Before shipping a brief, check it against the Voice, Evidence, Structure, and Interactivity sections.

---

## 1. Voice & tone

- **Direct, scientific, clear.** State findings plainly. The reader is an expert; write for someone who wants information, not persuasion.
- **No story-telling, no emotion, no drama.** Cut lines whose job is to build a narrative arc rather than convey a fact. *Examples flagged: "The mechanism is validated; the lane is crowded." / "the question that defines value from here" / "That single unanswered question is where value concentrates."*
- **No superlatives or sweeping single-cause claims.** Avoid "the prize," "the central question," "the first thing a buyer checks," "the single most important." There is rarely one thing — name the several that matter, precisely.
- **No blanket action or opinion statements.** Don't write "Do not contest" / "you must." Provide insight that lets the reader draw the action.
- **No platform self-reference.** Never cite "Meridian's North Star / Meridian's data show / Meridian's benchmark." Earn credibility through the information and its sources, not by naming the platform.
- **No audience-specific framing.** No "for the board / CEO / CSO." A brief is general intelligence for any qualified reader.
- **Explain the *reasoning*, not the *basics*.** Always show *why* a claim follows from the evidence. Do **not** spend words defining things an expert already knows (e.g., what a companion diagnostic is). Balance: teach the inference, assume the fundamentals.
- **Neutral language on outcomes.** Describe a failed endpoint as a "miss" and explain what happened; don't editorialize ("widely described as a failure"). Let the facts carry the weight.
- **No epistemic tag clutter.** Do not litter the prose with [F]/[I]/[J]/[P] tags; where a claim is a hypothesis or inference, say so in plain words.
- **Cut methodology meta-explanations.** The audience does not need "how to read the forecasts" or "why ranges" spelled out. Show the data and the logic; skip the instructions for reading it.
- **No descriptive subtitle / tagline lines.** Drop the cover "what this brief covers" sentence and similar framing headers. Open on the insight; the reader is a scientist and does not need the brief narrated to them.
- **Even subtle superlatives are still superlatives.** "the first endpoint a partner examines," "the key technical risk," "the central question" all overclaim singularity. Prefer "a primary focus," "a key risk," "a primary consideration" — flag it as *a* leading factor, not *the* one.

## 2. Evidence & sourcing

- **Every figure is footnoted, and every footnote links to the primary web page** (ClinicalTrials.gov, NEJM, Lancet GH, ECCO/DDW, company IR, deal filings).
- **Hyperlink words inline, too.** Key terms (trial names, drugs, deals) should themselves be clickable links to the source page — not only a trailing footnote number.
- **Bold the lead of each footnote** (e.g., **Deal comps:** …) so a reader scanning the notes finds the right one fast.
- **Put sources in the table** as a superscript next to the relevant term; do not waste a whole "Source" column.
- **Label the model behind every number** inline (NHP / first-in-human / healthy-volunteer / Phase 2 patients) — but don't add a separate explanatory caption about it.
- **Never fabricate KOL quotes.** Use sourced field commentary or paraphrased, cited investigator conclusions. Direct quotes require a real, attributable source.
- **Cross-validate against ground truth.** Web-verify and reconcile against the database before asserting; correct the database when it is wrong (and document the correction).
- **Dates must be precise and explained.** If a range looks odd (e.g., "2024-26"), state why (data presented across multiple congresses).
- **Attribute a fact to who asserted it, not to the venue.** Credit the company/author that made the claim (e.g., "Spyre management has characterized…"), not the conference or the bank whose note relayed it. Do not manufacture provenance like "at a Wedbush-hosted EULAR event" — a large event hosting a session does not make the claim the host's.

## 3. Structure & content

- **Build the general value case first; the specific asset (ALX001) later.** Establish what makes *an* asset valuable in the space before evaluating the home asset.
- **Cover:** title is **"TL1A × IL-23p19 in UC/CD"** (name the two indications directly; superseded the earlier "in IBD" / "Ulcerative Colitis & IBD"); show the date only; no audience/prep line; no epistemic key; no descriptive subtitle.
- **Drop redundant table captions.** If the table already encodes it (owner-first ordering, bold = bispecific), don't restate it in a caption line — the reader can see it.
- **Tables list Owner first, originator second** (originator still shown — it matters, in part — but the market associates the asset with the owner).
- **Discuss both UC and Crohn's throughout.** They carry different biology and challenges (fistulizing/fibrostenotic CD vs. UC mucosal disease); a UC-only read is incomplete.
- **Cover lines of therapy (1L / 2L / 3L+).** Where an asset is likely to sit in the treatment sequence drives its addressable population and value.
- **Include a dedicated payer section.** Payers decide value: why would a payer reimburse one agent over another (efficacy bar, dosing, line placement, step therapy, comparative effectiveness). This is critical and recurring.
- **Cover the alternative-mechanism / competitive landscape, not just the target.** What other targets and modalities (incl. small molecules) treat the same indication; who is developing them; where they are in the clinic; whether the field thinks they are better or worse. Distinguish competition in the **target space** from competition in the **indication space** — both matter. This is a generalized component to carry into every area.
- **Give asset-level detail:** antibody/molecule format, dosing regimen, and route — not just efficacy and half-life.
- **Predictions carry ranges** (and, for value, an explicit floor and band) so they are gradeable over time — but do not add a paragraph explaining why; just use them.
- **Predictions carry a DATE range, too** — not a single "resolves by" date. Like value/percent bands, a timing window (e.g., "Q4 2026 – Q1 2027") gives a baseline to grade against, so a resolved prediction can show whether we over- or under-estimated the timeline, not just the outcome.

## 4. Interactivity (dashboard rendering)

- **Drug names are buttons.** Every named drug (tulisokibart, afimkibart, vedolizumab, ustekinumab, …) should be clickable to open its canonical drug card for easy reference.
- **Words are hyperlinks.** Clicking a linked term opens the referenced source page directly.

## 5. Coverage standard — the CI Mastery Checklist (added 2026-06-08)

Kyle's **CI Mastery Checklist** is the definition of what a *complete* AIB covers. It is built on the
North Star ordering **Patient → Indication → Target → Company**, and every item carries one discipline
question: **"Can I answer it without looking it up, do I know the source, can I say how confident I am,
and what would change the answer?"** Weave the checklist in to *create* coverage — never bolt on a
literal 46-row table (that's forcing it). The four layers and what each demands of the brief:

- **TARGET — the biology you're betting on:** identity (name, gene, protein, aliases, family); normal
  function; pathway (upstream/downstream); role in disease; **validation level** (genetic / clinical /
  hypothesis); druggability & modalities; mechanism options (block/degrade, mono vs combined);
  differentiation levers (affinity, selectivity, half-life, combinability); **on-target safety ceiling**;
  redundancy / escape; biomarker availability; precedent & graveyard; competitive intensity; IP position.
- **INDICATION — the disease you're entering:** definition & subtypes; epidemiology; pathophysiology;
  full treatment ladder; *specific* unmet need; competitive pipeline (approved **and** clinical, by
  mechanism + stage); endpoints & placebo rates; trial-design norms; **regulatory landscape**; **the bar
  to beat (the actual number)**; commercial dynamics; catalysts (ECCO/DDW/JPM); history & lessons;
  **expansion potential** (adjacent indications / label expansion).
- **PATIENT POPULATION — the ground truth:** who they are (demographics, onset, severity); **patient
  journey** (time-to-dx, who treats); disease burden / QoL; **treatment experience** (route, monitoring,
  frequency, side-effects); segmentation; "**better**" from the patient's view; non-responders & escape
  biology; **real-world adherence/persistence**; access & equity; patient voice / PROs; trial-vs-reality
  gap; who pays. *(This layer is Kyle's #1 — keep the brief patient-rich, not just disease-rich.)*
- **THE OVERLAY — CI → BD decision:** for every competing asset, layer **attribution** (owner vs
  originator vs licensee), **stage**, **differentiation**, **catalyst timing**, **deal/availability
  status** (partnered / available / locked), and **the so-what** (where our asset wins/loses, and the posture).

**How it shows up (v13):** target-identity block ("The targets, precisely" — TNFSF15/DR3, IL23A/IL-23R,
genetic + clinical validation, on-target ceiling); patient ground-truth paragraph (journey, persistence,
"better"); a **BD overlay** table (control / availability / so-what per asset); a "Beyond IBD" expansion
line; a "Regulatory read" line; and a closing **"What would change this view"** table that operationalizes
the discipline's 4th question (claim → disconfirming signal). Hypotheses are labelled as hypotheses.

---

## Redline history (changelog)

Every note Kyle has made is recorded verbatim below, with its disposition (✅ applied · ◐ partial / next pass · ★ standing principle · ⚙ feature). Status key tells future writers what is already a rule vs. still open.

### Round 1 — `TL1A.docx` (2026-06-08, on the v6 edition) → produced **v8**

**Comments (verbatim → disposition):**
1. "Statements like this are unnecessary. 'Do not' is an opinion; lets avoid and provide insight rather than blanket action statements." → ★ §1.4 (no blanket action). ✅ removed "Do not contest."
2. "Be specific, who is racing?" → ✅ named tulisokibart/Merck, afimkibart/Roche, duvakitug/Sanofi-Teva, SPY002/Spyre.
3. "No need to talk to the board or anyone specifically — general intelligence doc for anyone who reads it." → ★ §1.6. ✅ removed "Bottom line for the board."
4. "If we focus on Ailux do this later, after we build a foundation as to why an asset is valuable in this space." → ★ §3 (general value case first). ✅
5. "I find this question odd. Focus on what makes an asset valuable and why, rather than ALX001 specifically." → ✅ reframed "why ALX001 deserves to exist" → "What determines value here."
6. "Be more specific." (unmet need) → ★ §1.7. ✅
7. "Talk about sense and rationale. Why a bispecific makes sense. Prove it in what follows." → ✅ added "Why a bispecific" rationale leading into the science.
8. "Avoid using superlatives." → ★ §1.3. ✅
9. "Be more specific, less nuanced." → ✅
10. "Explain, never make a statement without creating clarity." → ★ §1.7. ✅
11. "I think this paragraph is strong." (escape-pathway step) → kept.
12. "Ensure it is accurate and provide more detail where possible." → ✅ web-verified + expanded.
13. "Make these sources superscript on top so they don't take space; hyperlink all sources; clicking opens the source web page." → ★ §2. ✅ (footnotes v8; inline links v9).
14-15. "same with this source / all of these sources." → ✅
16. "Explain the miss and why, and what we can take from this." (afimkibart) → ✅ total-vs-modified-Mayo explanation.
17. "Clarify what model is used for these values — NHP, mouse, FIH, etc." → ★ §2 (label the model). ✅
18. "This point is not factual [OSM] … defensible biology is OSM/OSMR escape pathway … a strategy, not a current fact. I like presenting info like this for BD direction." → ✅ OSM rewritten to honest hypothesis; DB biomarker rows flagged [HYPOTHESIS].
19. "Good statement, be more specific. We want to learn as well." (IL-23 clean profile) → ✅ safety specifics added.
20. "What were the results?" (tulisokibart 50-wk safety) → ✅ actual results (URTI-predominant, no serious infections, no discontinuations).
21. "Hyperlink sources for all of these attached to the text." → ★ §2. ✅ (v9 inline links).
22. "These [predictions] are good but maybe explain what exactly we are predicting and why — for you and your audience." → ✅ forecast decomposition.
23. "This deserves further explanation to understand the logic." (forecast) → ✅ decomposition shown.
24. "Provide upfront values as well." (deal comps) → ✅ upfront added.
25. "Include royalties and other deal factors for clarity." → ✅ deal structure (50/50 cost/profit, royalties).
26. "Avoid superlatives." → ★ §1.3. ✅
27. "Should have a less-than as well so we have a range — better prediction, improvable by knowing why we were too high or low." → ★ §3 (ranges). ✅
28. "Ensure footnotes are clear throughout so when referenced it's easy to understand." → ✅ bold footnote leads (v9).

**Insertions (Kyle's written notes):**
- "Could be nice to have quotes and KOL statements … what others leading the industry are thinking." → ◐ added sourced field commentary (ACG); real direct KOL quotes still OPEN (only if sourced — no fabrication, §2).
- "(no need to mention Meridian's specific value, instead show value through information)" → ★ §1.5. ✅
- "(Worth mentioning the monospecifics that validated IL-23p19 and the potential match; be specific about what's completed vs. what still needs doing.)" → ✅ IL-23p19-in-IBD validation (what's done vs. needed).

**Deletions Kyle made (all honored):** epistemic-key legend; "Source-traced…" line; "Prepared for the Ailux Board, CEO, CSO & R&D" line; "Bottom line for the board"; "Meridian's North Star / Meridian's data show / benchmark"; "Implication for ALX001"; the China "why this is an Ailux advantage" paragraph; "Generated by Meridian … v4" footer; footnote about Meridian's empty tables; stray "0893" on the cover.

**Verified corrections this round:** tulisokibart ARTEMIS-UC = 26% vs 1% (all-comers) / 32% vs 11% (biomarker+) [NEJM 2024] (was wrongly 28/8); afimkibart TUSCANY-2 missed total-Mayo primary but hit modified-Mayo secondary [Lancet GH 2025]; IL-23p19 validated in IBD (mirikizumab Omvoh UC'23+CD'25, risankizumab, guselkumab).

### Round 2 — `TL1A_v2.docx` (2026-06-08, on v8) → produced **v9**

**Comments (verbatim → disposition):**
1. "I want each of these bolded drugs to be buttons that when pressed show the canonical card for that drug — makes ease of reference easier." → ⚙ §4. ✅ drug-name chips open a Supabase-backed canonical card.
2. "Avoid statements like this. Be direct, rather than creating emotion." → ★ §1.2. ✅ ("the mechanism is validated; the lane is crowded" cut).
3. "Same with this statement, be more direct, less story-telling." → ★ §1.2. ✅ ("the question that defines value from here" cut).
4. "There is more than just a single unanswered question. No need to make statements like this. **Keep track of all of my notes and record them so we can teach future issues and AIB how to be written. This is important.**" → ★ §1.3 + this whole document. ✅
5. "Odd words, I want scientific, direct, clear." ("The prize") → ★ §1.1. ✅
6. "There must be more than this one central question, still feels superlative." → ★ §1.3. ✅ ("This is the central, unproven question" reworded).
7. "I want hyperlinks attached directly to words as well, and to click those words and go directly to the web page discussing the topic referenced." → ★ §2. ✅ (v9 inline ExternalHyperlinks).
8. "All named drugs should have buttons that when pressed bring up the canonical card." → ⚙ ✅ drug chips (all named drugs).
9. "Be specific about what will be discussed later. Scientific, no need to simplify your introduction." → ★ §1.7. ✅
10. "Bring the sources into the table and link to words with the numbers next; no need for a whole column for sources." → ◐ inline links + footnotes done; §4 still has a compact "Src" column → move to inline superscripts NEXT PASS.
11. "Both UC and CD should be discussed throughout. They each bring different and unique challenges." → ★ §3. ✅ (§1 UC/CD table; CD fibrostenotic/fistulizing woven through).
12. "Strong word [failure]. Could just say miss, or explain what happened so we're aware." → ★ §1 (neutral language). ✅ softened to "miss."
13. "I feel we should also see dosing regimen and dosing method here." → ★ §3 (asset detail). ✅ route + dosing added.
14. "Should also know details about the antibody format and other pertinent information." → ★ §3. ✅ format column.
15. "I like this statement. It's well placed and insightful." (OSM direction) → kept.
16. "Why is this date over 2 years?" (2024-26) → ✅ footnote clarifies data presented across multiple congresses.

**Insertions (Kyle's written notes):**
- "Dive more into payer insights … why would payers pay for something over another … there should be a section below for this." → ★ §3 + ⚙ ✅ new §8 Payer differentiation.
- "Worthwhile to talk about the 1L, 2L etc. of care; simplify and present it valuably." → ★ §3 + ✅ new §2 Lines of therapy.
- "Present alternatives … other targets being validated, who's working on them, where in clinical dev, why, does industry think better/worse? Small molecules? … not only who we compete with in the target space but in the indication space … a generalized key component as we expand." → ★ §3 + ✅ new §5 Alternative mechanisms & broader competition.
- "Lets show owner first in this table and have originator be secondary, important, in part." → ★ §3. ✅ owner-first tables.

> **Process rule.** When the next redline round lands: (1) extract every comment + insertion verbatim with `pandoc --track-changes=all`; (2) add a new "Round N" itemized ledger here with dispositions; (3) fold any new standing rule into Sections 1-4. Nothing gets lost between rounds.

### Round 3 — `AIB_TL1A_IL23p19_UC_v11.docx` (2026-06-08, on v11) → produced **v12**

*(The v10/v11 changes between Round 2 and here were chat-driven — inline word-hyperlinks replacing citation numbers, canonical-card chips, and Cowen/Wedbush fact integration — not a docx redline, so they have no ledger entry. This is the third docx redline round.)*

**Comments (verbatim → disposition):**
1. "No need for these style of headers. Remove them. Focus on the insight and information. We are speaking to scientists." (on the cover subtitle/tagline) → ★ §1. ✅ Descriptive subtitle line removed entirely.
2. "This seems inaccurate. No reason to be stated. EULAR is a large event, just because some insight came from wedbush does not mean this, no need to say this." (on "at a Wedbush-hosted EULAR 2026 event") → ★ §2 (attribute the asserter, not the venue). ✅ Reworded to "Spyre management has publicly characterized…"; venue/host framing deleted.
3. "seems superalative. there may be other points, albiet, this is may be a primary consideration. Be careful with your words." (on "it is the first endpoint a partner's diligence examines") → ★ §1 (subtle superlatives). ✅ → "it is a primary focus of a partner's diligence."
4. "we should also give date ranges for predictions as well, for the same reason we give ranges for value and percents. Gives us something to work from. why did we over or under estimate the timeline?" → ★ §3 (predictions carry a DATE range). ✅ "Resolves by" single dates → ranges (Q4 2026 – Q1 2027; H2 2027 – H1 2028; etc.); column renamed "Resolves (range)."

**Insertions / deletions (Kyle's inline edits):**
- Title "TL1A × IL-23p19 in **IBD**" → "**UC/CD**" → ★ §3. ✅ Applied to docx + viewer band + viewer `<h1>`.
- "+currently" → "validated in Phase 2 and **currently** in Phase 3" (his note: "without this word it makes it sound like TL1A is validated Phase 2 and Phase 3"). ✅
- "The axes on which **any** TL1A/IL-23 asset **is** judged**, stated as specifics rather than principles**:" → "The axes on which TL1A/IL-23 **assets are** judged:" → ★ §1 (cut meta-framing). ✅
- Deleted §4 caption "Owner first; originator in parentheses. Bold rows are TL1A×IL-23 bispecifics." → ★ §3 (drop redundant captions). ✅ (efficacy-is-Phase-2 caption retained).
- "Payers**, not prescribers,** set realized value" → "Payers set realized value" → ★ §1 (direct). ✅

### Round 4 — CI Mastery Checklist integration (`CI_Mastery_Checklist.docx`, 2026-06-08, on v12) → produced **v13**

*(Not a redline — Kyle supplied his standing CI Mastery Checklist and asked to "integrate this checklist into the AIB … do not force it, weave it in to create value along the way.")*

**What it is → disposition:** the checklist became **Section 5 above (the coverage standard)** ★ and was woven into v13, not bolted on. Gaps it surfaced in v12, each now filled with sourced content:
1. **Target identity & genetic validation** (was missing) → ✅ "The targets, precisely": TL1A=TNFSF15→DR3(TNFRSF25)/DcR3; IL-23p19=IL23A→IL-23R; TNFSF15 + IL23R are validated IBD GWAS loci; on-target safety ceiling (DR3/Treg) stated. *(Front. Immunol. 2019)*
2. **Patient ground-truth** (disease-heavy, patient-light) → ✅ "The patient, not just the disease": journey (CD dx delay ~5-9 mo, ~3.5 physicians), persistence (~45-48% on first biologic at 1 yr), "better" from the patient's view. *(CD diagnostic-delay review; Crohn's & Colitis 360)*
3. **BD overlay** (attribution only) → ✅ "BD overlay — control, availability, and the so-what" table: per-asset control / availability (locked vs acquirable vs partnerable) / so-what. Spyre/Mirador/Xencor flagged as the transactable optionality.
4. **Expansion potential** (missing) → ✅ "Beyond IBD": tulisokibart Ph2b in HS/axSpA/RA; IL-23p19 approved in psoriasis/PsA. *(Merck PR 2026)*
5. **Regulatory landscape** (missing) → ✅ "Regulatory read" line: modified-Mayo/endoscopic endpoints, ~10-13% placebo, class precedent → gating risk is comparative efficacy + dual-blockade safety, not regulatory novelty.
6. **The discipline's 4th question** (scattered) → ✅ closing **"What would change this view"** table (claim → disconfirming signal) + explicit hypothesis-labelling note.

**Standing rule added:** the CI Mastery Checklist is now the coverage standard for *every* AIB (Section 5); future area briefs (TSLP, IL-4Rα, IGF-1R, FcRn) must answer its four layers with sourced, confidence-rated content.
