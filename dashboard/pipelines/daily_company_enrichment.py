"""
Static description of the Intelligence Pipeline
(.github/workflows/daily-company-enrichment.yml).

Documents what the four entrypoint scripts do — CT.gov trial sync, company
and drug enrichment, completeness / trigger auditing, identity health checking,
and ranking snapshot recording — and how they chain together per area.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "intelligence_pipeline",
    "workflow_name": "Intelligence Pipeline",
    "workflow_file": ".github/workflows/daily-company-enrichment.yml",
    "schedule": (
        "Nightly, 6 areas in parallel — staggered 10 min to avoid Anthropic API bursts: "
        "tl1a 04:00 UTC · tslp 04:10 · il4ra 04:20 · fcrn 04:30 · igf1r 04:40 · tcell 04:50. "
        "Each area run completes in ~30–90 min. Manual dispatch: any single area or 'all'."
    ),
    "entrypoint": (
        "scripts/sync/ct_gov_sync.py → "
        "scripts/enrichment/company_enrichment.py → "
        "scripts/enrichment/research_intelligence.py → "
        "scripts/identity/identity_health_check.py → "
        "scripts/scoring/write_ranking_snapshots.py"
    ),
    "unit_key": "function",
    "unit_section_title": "Script-by-script, in execution order",
    "summary": (
        "The main nightly pipeline. For every tracked disease area it runs a four-step sequence: "
        "**Step 3** (`ct_gov_sync.py`) keeps the `trials` table current by fetching "
        "ClinicalTrials.gov v2 records for all drugs in the area — direct NCT lookups for known "
        "IDs, search-and-score discovery for unknowns, and a drug stage update pass. "
        "**Steps 1, 4, 5, 6** (`company_enrichment.py`, 3 261 lines) drive the core 7-step "
        "intelligence pipeline: discovery, CT.gov context pull, profile enrichment, catalyst "
        "generation, deal intelligence, competitive scoring, and a final audit. "
        "**Step 7** (`research_intelligence.py`) sweeps the area for completeness scores "
        "(0–100 across 6 weighted stages), detects research triggers, and upserts the "
        "research queue so the dashboard always shows what to research next. "
        "A **post-pipeline** pass checks identity-layer health (orphaned canonicals, fuzzy "
        "review queue, company_profiles ↔ company_areas sync) and records a daily ranking "
        "snapshot for next-gen programs to `next_gen_rankings`."
    ),
    "dot": r"""
digraph {
    rankdir=TB
    bgcolor="transparent"
    fontcolor="#e8ecf2"

    node [
        shape=box,
        style="rounded,filled",
        fillcolor="#dbe9fb",
        color="#5b8def",
        fontcolor="#111827",
        fontname="Helvetica",
        fontsize=12,
        margin="0.18,0.12"
    ]

    edge [
        color="#5b6b7d",
        fontcolor="#e8ecf2",
        fontname="Helvetica",
        fontsize=10,
        arrowsize=0.8
    ]

    schedule [
        label="Nightly cron\n6 areas x 10-min stagger\n(04:00-04:50 UTC)",
        fillcolor="#f3e8fb",
        color="#8b5cf6",
        fontcolor="#111827"
    ]

    step3 [
        label="Step 3\nct_gov_sync.py\n(CT.gov trial sync - area)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    step1456 [
        label="Steps 1,4,5,6\ncompany_enrichment.py\n(7-step intelligence pipeline - area)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    step7 [
        label="Step 7\nresearch_intelligence.py\n(completeness scoring + triggers - area)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    post [
        label="Post-pipeline\nidentity_health_check.py\nwrite_ranking_snapshots.py",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    ctgov [
        label="ClinicalTrials.gov\nv2 API",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    anthropic [
        label="Anthropic API\n(company_enrichment steps)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    supabase [
        label="Supabase\n(reads + writes throughout)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    out_trials [
        label="Supabase\ntrials . drugs.stage\ndrugs.trial_data_status",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    out_enrichment [
        label="Supabase\ncompany_profiles . drugs\ncatalysts . deals . drug_competitive_scores",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    out_audit [
        label="Supabase\nresearch_queue . drugs\n(completeness_score/tier)\nnext_gen_rankings",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    schedule -> step3
    step3 -> ctgov [label="  CT.gov v2 API", style="bold", color="#c9890a", fontcolor="#c9890a"]
    step3 -> supabase [label="  reads drugs/drug_areas\nwrites trials", style="bold", color="#c9890a", fontcolor="#c9890a"]
    step3 -> out_trials [label="  upserts", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    step3 -> step1456 [label="  trials ready"]
    step1456 -> anthropic [label="  enrichment + synthesis", style="bold", color="#c9890a", fontcolor="#c9890a"]
    step1456 -> supabase [label="  reads + writes\nall entity tables", style="bold", color="#c9890a", fontcolor="#c9890a"]
    step1456 -> out_enrichment [label="  upserts", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    step1456 -> step7 [label="  enrichment done"]
    step7 -> supabase [label="  reads entity\ncontext", style="bold", color="#c9890a", fontcolor="#c9890a"]
    step7 -> out_audit [label="  upserts queue\n+ scores", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    step7 -> post
    post -> supabase [label="  reads identity layer\n+ competitive scores", style="bold", color="#c9890a", fontcolor="#c9890a"]
    post -> out_audit [label="  ranking snapshots", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
}
""",
    "io_dot": r"""
digraph {
    rankdir=LR
    bgcolor="transparent"
    fontcolor="#e8ecf2"

    node [
        shape=box,
        style="rounded,filled",
        fontname="Helvetica",
        fontsize=11,
        margin="0.16,0.1"
    ]

    edge [
        color="#5b6b7d",
        fontcolor="#e8ecf2",
        fontname="Helvetica",
        fontsize=10,
        arrowsize=0.8
    ]

    subgraph cluster_in {
        label="Inputs - what comes in, and from where"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        sb_in [label="Supabase\ndrugs . drug_areas . trials . catalysts\ncompany_profiles . deals . drug_competitive_scores\ncanonical_drugs . drug_aliases . company_areas", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        ctgov_in [label="ClinicalTrials.gov\nv2 JSON API\n(per NCT + name search)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        anthropic_in [label="Anthropic API\n(Claude - company enrichment,\ncatalyst synthesis, deal intel)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Intelligence\nPipeline",
        shape=ellipse,
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827",
        fontsize=12
    ]

    subgraph cluster_out {
        label="Outputs - what goes out, and to where"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        sb_out [label="Supabase\ntrials . drugs (stage/trial_data_status/completeness_score)\ncompany_profiles . catalysts . deals\ndrug_competitive_scores . research_queue\nnext_gen_rankings", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nper-area run summary\nidentity health report", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    ctgov_in -> pipeline
    anthropic_in -> pipeline
    pipeline -> sb_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "drugs · drug_areas",
                "kind": "Supabase tables",
                "via": "ct_gov_sync.py run_sync() → sb_get('drug_areas') + sb_get('drugs')",
                "desc": (
                    "Step 3 opens with a drug-area join to build the worklist for the given "
                    "area: `drug_areas` is filtered to the area (plus its `indication_group` "
                    "sibling — e.g., tl1a also pulls ibd-tagged drugs), and the resulting "
                    "`drug_id` list is used to fetch full drug rows from `drugs`. Approved and "
                    "pre-IND drugs are fast-pathed out; only drugs with or without known NCTs "
                    "enter the main sync loop."
                ),
                "scope": (
                    "One area query on `drug_areas` + one batch `drugs` query by `id in (...)`. "
                    "Typical area worklist: 20–60 drugs, fetched in a single round-trip each."
                ),
            },
            {
                "name": "ClinicalTrials.gov v2 API",
                "kind": "External API",
                "via": "ct_gov_sync.py step3a_direct_nct_sync() + step3b_search_discovery()",
                "desc": (
                    "For each drug in the worklist, `step3a` GETs known NCT IDs directly from "
                    "`/api/v2/studies/<nct>` (full protocol section requested), while "
                    "`step3b` fires a name + indication search at `/api/v2/studies?query.term=...` "
                    "and scores each result (name similarity + sponsor match + indication match). "
                    "Only results scoring >=60 are considered; >=85 are auto-accepted."
                ),
                "scope": (
                    "One GET per known NCT (step 3a) plus one search per drug without known NCTs "
                    "(step 3b). Rate-limited with a 1-second sleep between drugs. Typical area "
                    "run touches 50–200 CT.gov API calls."
                ),
            },
            {
                "name": "All entity tables (company_profiles, deals, catalysts, drug_competitive_scores, …)",
                "kind": "Supabase tables",
                "via": "company_enrichment.py — 7-step pipeline reading context for each entity",
                "desc": (
                    "`company_enrichment.py` is a 3 261-line script implementing a 7-step "
                    "intelligence pipeline. It reads broadly across the catalog to build rich "
                    "context for each company/drug entity before synthesizing enriched profiles "
                    "with Claude: step 1 discovers new entities, step 4 generates catalysts from "
                    "primary completion dates and trial milestones, steps 5–6 enrich company "
                    "profiles and deal intelligence, and step 6 also computes competitive scores. "
                    "Every step reads the current state from Supabase to ensure incremental, "
                    "idempotent updates."
                ),
                "scope": (
                    "Per-entity reads for drugs, trials, company_profiles, deals, catalysts, "
                    "drug_competitive_scores, company_areas, and related junction tables. "
                    "Volume is proportional to the number of entities in the area (typically "
                    "30–80 companies) and the depth of enrichment required per entity."
                ),
            },
        ],
        "cleaning": (
            "**ct_gov_sync.py deduplicates trials before writing and gates stage updates on "
            "all-trials consensus.** Trial upserts use `nct_id` as the conflict key — "
            "re-syncing the same NCT overwrites the existing row rather than creating a "
            "duplicate. Stage advancement is conservative: `step3c_update_drug_stage()` "
            "only promotes the drug's stage if *all* active trials support the new phase "
            "(a single Phase 1 trial cannot trigger a 'Phase 3' promotion). Newly discovered "
            "trials via search get `discovery_status='auto'` (>=85 score) or "
            "`discovery_status='unverified'` (60–84) — the dashboard filters on this column "
            "to surface unverified trials for analyst review. "
            "**company_enrichment.py is idempotent by design**: every write is an upsert "
            "on a stable natural key, so re-running an area does not accumulate duplicates."
        ),
        "writes": [
            {
                "name": "trials · drugs",
                "kind": "Supabase tables",
                "via": "ct_gov_sync.py → update_trial_registries() + step3c_update_drug_stage()",
                "desc": (
                    "Step 3 upserts one `trials` row per synced NCT ID (full structured fields: "
                    "status, phase, enrollment, arms, endpoints, primary_completion_date, sponsor) "
                    "and patches `drugs.stage` / `drugs.trial_data_status` where the evidence "
                    "warrants it."
                ),
                "scope": (
                    "Bounded by the number of active trial records per area; typically "
                    "50–300 trial rows upserted per nightly area run."
                ),
            },
            {
                "name": "company_profiles · drugs · catalysts · deals · drug_competitive_scores",
                "kind": "Supabase tables",
                "via": "company_enrichment.py → 7-step upserts (steps 1, 4, 5, 6)",
                "desc": (
                    "Steps 1, 4, 5, and 6 of `company_enrichment.py` collectively update or "
                    "create company profiles, write catalyst rows from trial milestone dates, "
                    "upsert deal records discovered via Claude synthesis, and record "
                    "competitive scores for all Next Gen drug programs in the area."
                ),
                "scope": (
                    "Volume depends on the number of stale or newly discovered entities. "
                    "A full area cold-start may write 50–200 rows; subsequent nightly runs "
                    "are largely no-ops for already-enriched entities."
                ),
            },
            {
                "name": "research_queue · drugs (completeness_score, completeness_tier)",
                "kind": "Supabase tables",
                "via": "research_intelligence.py run_intelligence_audit() → upsert_research_queue()",
                "desc": (
                    "Step 7 scores every entity 0–100 across 6 weighted research stages, "
                    "detects research triggers (stale profiles, catalyst dates passed, "
                    "trial phase ahead of drug stage), determines the next best action, "
                    "and upserts a `research_queue` row with priority score and action text. "
                    "It also stamps `completeness_score` and `completeness_tier` on `drugs`."
                ),
                "scope": (
                    "One `research_queue` upsert per entity per area run. "
                    "Completeness stamps touch every drug row in the area."
                ),
            },
            {
                "name": "next_gen_rankings",
                "kind": "Supabase table",
                "via": "write_ranking_snapshots.py compute_rankings() → sb_upsert('next_gen_rankings', ...)",
                "desc": (
                    "After the main pipeline, `write_ranking_snapshots.py` reads "
                    "`drug_competitive_scores` for Next Gen programs (cls='Next Gen') across "
                    "tl1a, ibd, and fcrn areas, computes a composite score (70% enrichment "
                    "score + 30% stage signal; Ailux programs use a separate development "
                    "score table), sorts and ranks, then upserts one snapshot row per drug "
                    "per area including `rank_position`, `total_score`, `stage`, and "
                    "`competitive_relev` fields. The dashboard reads this table directly — "
                    "it never writes ranking data itself."
                ),
                "scope": (
                    "Typically 10–40 rows per area (Next Gen programs only). "
                    "Runs once at the end of every pipeline invocation regardless of area."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Step 3 — CT.gov trial sync (ct_gov_sync.py)",
            "note": (
                "Runs first, before company_enrichment.py, so trial records and primary "
                "completion dates exist when the enrichment step generates catalysts from PCD milestones."
            ),
            "groups": [
                [
                    {
                        "function": "run_sync(area_id, drug_filter, dry_run, search_only)",
                        "lines": 91,
                        "desc": (
                            "Main entry point. Resolves the area to its `indication_group` "
                            "(so tl1a also pulls ibd-tagged drugs), fetches the drug worklist, "
                            "instantiates a `DrugIdentityResolver` (pre-loads alias cache for the "
                            "run), then iterates each drug through `sync_drug()` with a 1-second "
                            "inter-drug sleep. After the loop, prints a sync summary and runs "
                            "`run_field_validation()` to catch brand-name / study-acronym "
                            "contamination introduced during the sync."
                        ),
                    }
                ],
                [
                    {
                        "function": "sync_drug(drug, dry_run, resolver, search_only)",
                        "lines": 118,
                        "desc": (
                            "Per-drug coordinator. Fast-paths approved drugs (marks 'populated' "
                            "without CT.gov calls) and pre-IND drugs (marks 'pending'). For active "
                            "drugs: calls `step3a_direct_nct_sync()` for known NCT IDs, then "
                            "`step3b_search_discovery()` for unknowns, then "
                            "`step3c_update_drug_stage()` to advance the drug's stage if all "
                            "active trials support promotion. Updates `trial_data_status` to "
                            "'populated' or 'missing' based on results."
                        ),
                    }
                ],
                [
                    {
                        "function": "step3a_direct_nct_sync(drug, nct_ids, dry_run, resolver)",
                        "lines": 87,
                        "desc": (
                            "Fetches each known NCT ID from `ct_fetch_by_nct()`, parses the full "
                            "structured record via `parse_ct_study()`, and upserts to the `trials` "
                            "table. If a `DrugIdentityResolver` is provided, uses it to verify the "
                            "drug-trial association before writing. Returns a list of synced NCT IDs."
                        ),
                    },
                    {
                        "function": "step3b_search_discovery(drug, dry_run, resolver)",
                        "lines": 80,
                        "desc": (
                            "Fires a name + indication search on CT.gov, scores each result with "
                            "`score_search_match()` (name similarity, sponsor, indication signal), "
                            "and upserts results with `discovery_status='auto'` (>=85) or "
                            "`discovery_status='unverified'` (60–84). Scores below 60 are logged "
                            "but not written — avoids polluting the catalog with false positives."
                        ),
                    },
                    {
                        "function": "step3c_update_drug_stage(drug_id, synced_nct_ids, dry_run)",
                        "lines": 58,
                        "desc": (
                            "Reads all synced trials for the drug and determines the consensus "
                            "phase. Only advances the drug's stage if *all* active trials are at "
                            "that phase — a conservative gate that prevents a Phase 1 edge case "
                            "from incorrectly overwriting a Phase 3 stage. Patches `drugs.stage` "
                            "and logs the change."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Steps 1, 4, 5, 6 — Intelligence pipeline (company_enrichment.py)",
            "note": (
                "company_enrichment.py is a 3 261-line script. It implements the core "
                "7-step intelligence pipeline that turns raw CT.gov data and Supabase catalog "
                "entries into enriched company profiles, catalysts, deal records, and "
                "competitive scores. The numbered steps correspond to the platform's "
                "research maturity model (Steps 1, 4, 5, and 6 run in this workflow; "
                "Steps 2 and 3 are handled by ct_gov_sync.py and molecule_enrichment.py)."
            ),
            "groups": [
                [
                    {
                        "function": "Step 1 — Entity discovery",
                        "lines": None,
                        "desc": (
                            "Discovers new companies and drugs active in the area that are not "
                            "yet in the catalog. Queries CT.gov and Supabase to find programs "
                            "referencing the target (e.g., TL1A, TSLP) and creates skeleton "
                            "`drugs` and `companies` rows for new entrants. Idempotent — "
                            "entities already in the catalog are skipped."
                        ),
                    }
                ],
                [
                    {
                        "function": "Step 4 — Catalyst generation",
                        "lines": None,
                        "desc": (
                            "Generates `catalysts` rows from structured trial data. For each drug "
                            "with a primary completion date (PCD) that lacks a corresponding "
                            "catalyst, synthesizes a catalyst record with expected readout date, "
                            "event type, and strategic importance text. This is why ct_gov_sync.py "
                            "must run first — catalysts are derived from the trial records just "
                            "populated in Step 3."
                        ),
                    }
                ],
                [
                    {
                        "function": "Step 5 — Company profile enrichment",
                        "lines": None,
                        "desc": (
                            "Calls Claude to synthesize or update `company_profiles` for each "
                            "company active in the area. Enrichment covers pipeline summary, "
                            "strategic positioning vs. Ailux, mechanism of action notes, "
                            "BD interest signals, and the `ailux_angle` field. Profiles are "
                            "only re-synthesized if stale (not enriched in >30 days) or if "
                            "a research trigger fires — the trigger system from Step 7 feeds "
                            "back into Step 5 on subsequent runs."
                        ),
                    }
                ],
                [
                    {
                        "function": "Step 6 — Deal intelligence + competitive scoring",
                        "lines": None,
                        "desc": (
                            "Discovers and upserts `deals` rows (licensing, co-development, "
                            "M&A) by synthesizing press releases and SEC 8-K filings via Claude. "
                            "After deals are current, computes `drug_competitive_scores` — a "
                            "numeric score per drug per area context (Next Gen / Best-in-Class / "
                            "Combination) that drives the dashboard's ranking tables and "
                            "the post-pipeline `write_ranking_snapshots.py` step."
                        ),
                    }
                ],
                [
                    {
                        "function": "Step 7 audit (internal to company_enrichment.py)",
                        "lines": None,
                        "desc": (
                            "An internal audit at the end of the enrichment run that cross-checks "
                            "governance rules: brand_name_implies_approved, source_url required "
                            "for deals, co-developer attribution consistency. Violations are "
                            "logged to `governance_violations` for human review. This step is "
                            "distinct from the separate Step 7 script (research_intelligence.py) "
                            "that runs afterwards in the workflow."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Step 7 — Research intelligence audit (research_intelligence.py)",
            "note": (
                "Runs last in the main sequence, after enrichment is complete. "
                "Sweeps every entity in the area to answer: what do we know, what is missing, "
                "what changed, and what should happen next."
            ),
            "groups": [
                [
                    {
                        "function": "run_intelligence_audit(area_id, entity_filter, dry_run)",
                        "lines": 108,
                        "desc": (
                            "Main entry point. Discovers all `drug_ids` for the area via "
                            "`drug_areas`, groups them by `entity_id`, then for each entity "
                            "calls the LangGraph `run_entity_pipeline()` orchestrator which "
                            "sequences: `load_entity_context()` → `score_entity_completeness()` → "
                            "`check_research_triggers()` → `get_next_best_action()` → "
                            "`calculate_priority_score()` → `upsert_research_queue()`. "
                            "Prints a ranked priority table on completion."
                        ),
                    }
                ],
                [
                    {
                        "function": "load_entity_context(entity_id, area_id)",
                        "lines": 123,
                        "desc": (
                            "Fetches all Supabase data for one entity: drugs (by entity_id + "
                            "canonical_drug_id), trials (by drug_id AND canonical_drug_id to "
                            "catch both direct and aliased records), company profile, deals, "
                            "catalysts, and competitive scores. Groups sibling drug rows by "
                            "canonical_drug_id and merges them into a single best-values "
                            "representative via `_merge_drug_rows()` — so canonical program "
                            "scoring reflects all rows for that program."
                        ),
                    }
                ],
                [
                    {
                        "function": "score_entity_completeness(ctx)",
                        "lines": 249,
                        "desc": (
                            "Scores the entity 0–100 across 6 weighted stages: "
                            "Stage 1 Entity Discovery (10), Stage 2 Drug Mapping (15), "
                            "Stage 3 Trial Intelligence (20), Stage 4 Catalyst Engine (15), "
                            "Stage 5 Strategic Positioning (25), Stage 6 Deal Intelligence (15). "
                            "Returns a score dict with `completeness_score`, `completeness_tier` "
                            "(thin <40 / partial 40–69 / strong >=70), and lists of "
                            "`missing_fields` and `missing_stages` for the action generator."
                        ),
                    }
                ],
                [
                    {
                        "function": "check_research_triggers(ctx)",
                        "lines": 136,
                        "desc": (
                            "Detects seven trigger types: trial phase ahead of drug stage, "
                            "PCD without a catalyst, completed trial without results, "
                            "catalyst date passed unresolved, profile stale >30 days, "
                            "new deal since last enrichment, and strategic entity missing "
                            "`vs_ailux`. Returns a list of trigger strings consumed by "
                            "`get_next_best_action()` and `calculate_priority_score()`."
                        ),
                    }
                ],
                [
                    {
                        "function": "upsert_research_queue(entity_id, area_id, score_result, …)",
                        "lines": 84,
                        "desc": (
                            "Writes or updates the `research_queue` row for this entity + area "
                            "with completeness score, tier, priority score, next action text, "
                            "and trigger list. Also patches `completeness_score` and "
                            "`completeness_tier` directly onto the `drugs` rows for "
                            "the entity, so the dashboard can show per-drug completeness "
                            "without joining the research_queue table."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Post-pipeline — Identity health check + ranking snapshots",
            "note": (
                "Two scripts run after the main area pipeline completes. "
                "identity_health_check.py uses `continue-on-error: true` — a failure here "
                "does not block the workflow. write_ranking_snapshots.py also uses "
                "`continue-on-error: true` and is skipped on dry-run invocations."
            ),
            "groups": [
                [
                    {
                        "function": "identity_health_check.py  health_check()",
                        "lines": 159,
                        "desc": (
                            "Runs 8 checks on the canonical identity layer: drug identity "
                            "coverage (% with a canonical_drug_id), identity confidence "
                            "distribution (high >=85 / medium / low), resolution method "
                            "breakdown, canonical_drugs table health (active vs. merged), "
                            "alias coverage, fuzzy review queue length, orphaned drug records "
                            "(broken FK refs to canonical_drugs), and company_profiles to "
                            "company_areas sync. With `--fail-on-orphans` and "
                            "`--fail-on-fuzzy-pending` flags set, returns exit code 1 if "
                            "those conditions are found — triggering a CI warning (not a "
                            "pipeline block, since `continue-on-error: true` is set). "
                            "Also calls `reconcile_profiles_areas()` which can optionally "
                            "insert missing `company_areas` rows to repair orphaned profiles."
                        ),
                    }
                ],
                [
                    {
                        "function": "write_ranking_snapshots.py  compute_rankings(area_id)",
                        "lines": 61,
                        "desc": (
                            "Reads `drug_competitive_scores` for Next Gen programs in each of "
                            "the three ranking areas (tl1a, ibd, fcrn), computes a composite "
                            "score (70% enrichment total_competition_score + 30% stage weight; "
                            "Ailux programs use a separate development-score table), sorts "
                            "descending, and upserts one `next_gen_rankings` row per drug "
                            "with rank_position, total_score, stage, competitive_relev, and "
                            "is_ailux flag. The dashboard reads this table directly for "
                            "its ranking visualizations."
                        ),
                    }
                ],
            ],
        },
    ],
}
