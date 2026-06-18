# §E — Entity-Resolution Convergence (analysis, 2026-06-18)

> **Goal (ROADMAP §E / health metric #3):** one canonical entity resolver (`identity/entity_matcher.py`,
> the ambiguity-guarded `Registry`) instead of many ad-hoc name→id matchers. This doc inventories the
> "resolver" surface, removes false positives, and right-sizes the convergence (it's supervised — changing
> identity matching affects dedup / data integrity in live pipelines).

## The surface — 19 files matched the resolver grep; classified:

### A. Already canonical / already on `entity_matcher` (no work)
| file | symbol | note |
|---|---|---|
| `identity/entity_matcher.py` | `Registry.resolve` | **the target** |
| `database/drug_writer.py` | `resolve_identity` | uses `entity_matcher.Registry` already |
| `database/company_writer.py` | `resolve_identity` | uses `entity_matcher.Registry` already |

### B. FALSE POSITIVES — not entity identity at all (leave; they should NOT converge)
| file | symbol | what it actually resolves |
|---|---|---|
| `scoring/score_foresight.py` | `resolve_catalyst`, `resolve_tier2` | catalyst **lifecycle** ("mark resolved"), not identity |
| `validation/conflict_detector.py` | `canonical_target` | canonicalizes a molecular **target string** |
| `graph/seed_api_edges.py` | `resolve_target` | maps a **target symbol** to a valid set |
| `products/narrative/triangulate.py` | `resolve_ncts` | extracts **NCT trial ids** from text (takes a `resolver` param — already delegates) |
| `graph/unify_graph.py` | `resolve` | graph-node unification (structural, not name→id) |

### C. Genuine name→id resolvers — the actual convergence candidates (~11)
`enrichment/company/resolve.py::resolve_company_id` · `ingestion/research.py::resolve_company_id` ·
`identity/company_identity_resolver.py::resolve` · `identity/identity_resolution.py::resolve/resolve_batch` ·
`identity/intake/research.py::resolve_identity` · `identity/review_submitted_intel.py::match_entity` ·
`ingestion/chunk_extract.py::find_drug/find_company` · `ingestion/drugintake/research.py::resolve_drug_identity` ·
`scoring/compute_patient_whitespace.py::resolve` · `validation/validation_research.py::resolve_drug` ·
`graph/build_institution_intel.py::resolve_company`.

## Concrete findings
1. **§E is ~11 real resolvers, not 17–19.** Removing the false positives (B) and the already-canonical writers
   (A) right-sizes the metric-#3 target.
2. **Confirmed near-duplicate:** `resolve_company_id(name, company_map)` exists in BOTH
   `enrichment/company/resolve.py` (superset: exact → parenthetical-strip → substring → base-substring) and
   `ingestion/research.py` (subset: exact → substring only). Unifying them would *change* the nightly research
   pipeline's matching (adds the parenthetical-strip), so it is a **behavior change to live code**, not a free dedup.
3. **Why convergence is supervised:** these resolvers feed dedup / edge-seeding / intake. Swapping any to
   `entity_matcher.Registry` changes which names match which ids → can create or prevent merges. Each swap needs
   a before/after match-set diff on real data + the writer/edge regression suites + (for pipeline files) a
   dispatch-verify. `entity_matcher` is also network-backed (builds a Registry from Supabase), so the lightweight
   `(name, company_map)` callers can't trivially swap without a fetch.

## Recommended sequence (supervised)
1. **Lowest-risk first:** unify the two `resolve_company_id` copies — make `ingestion/research.py` import the
   `enrichment/company/resolve.py` version (or a shared `identity` helper). Verify with a match-set diff over the
   live `company_map` + a `meridian-research` dispatch (it adds parenthetical-strip → confirm no worse matching).
2. Fold the simple `(name, map)` matchers (`compute_patient_whitespace.resolve`, `chunk_extract.find_*`,
   `review_submitted_intel.match_entity`) onto one shared lightweight helper, then onto `entity_matcher` where a
   Registry is available.
3. Leave the writers (already canonical) and the false-positives (B) alone.

## Equivalence audit (2026-06-18, read-only) — confirms even the "lowest-risk" item is supervised
Tested both `resolve_company_id` impls over 576 inputs (192 company_map keys + parenthetical variants):
- identical: **570** · superset only-adds-a-match (safe): **0** · **different id: 6**.
- The 6 diverge on companies whose *name itself* contains parens — e.g. `"Bausch Health (BHC) (TL1A mono)"`:
  subset substring-matches `bauschhealth`; superset strips the trailing `(TL1A mono)` → exact-matches
  `bauschhealthbhc`. Same for `ImmuPharma/Avion`, `United Therapeutics management`.
- **Verdict:** unifying is NOT behavior-neutral (the superset re-resolves these differently — arguably *more*
  correct, but different), so it stays a **supervised** change requiring a `meridian-research` dispatch-verify,
  not a blind dedup. The audit converts "probably supervised" → "empirically supervised, with the exact 6 cases."

## Status
Analysis + equivalence audit done (read-only). No code changed — execution remains supervised across §E
(identity matching → dedup/data-integrity blast radius), now with concrete divergence evidence. ROADMAP §3/§E updated.
