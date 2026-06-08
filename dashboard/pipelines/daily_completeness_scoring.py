"""
Static description of the Completeness Scoring pipeline
(.github/workflows/daily-completeness-scoring.yml).

Documents what research_intelligence.py does when run platform-wide with
--area all: sweeping every disease area for field-presence completeness scores
and tier assignments without any LLM calls. Cheap, fast, and comprehensive.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "completeness_scoring",
    "workflow_name": "Completeness Scoring",
    "workflow_file": ".github/workflows/daily-completeness-scoring.yml",
    "schedule": "Daily 09:30 UTC (5:30 AM ET) — runs after the nightly enrichment window closes, before the morning Meridian issue publishes",
    "entrypoint": "scripts/enrichment/research_intelligence.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Platform-wide completeness sweep that scores *every* entity in *every* area "
        "for field-presence completeness every day. The same `research_intelligence.py` "
        "script runs inside the nightly Intelligence Pipeline as Step 7 (one area at a "
        "time), but this workflow runs it standalone with `--area all` so the full "
        "catalog is rescored each morning — not just the area that happened to run last "
        "night. Scoring is pure field-presence (no LLM calls), so it completes in "
        "minutes and never touches the Anthropic API. Outputs: `completeness_score` and "
        "`completeness_tier` (thin / partial / strong) stamped on every `drugs` row, "
        "and an updated `research_queue` row per entity with priority score and "
        "next-best-action text."
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

    entry [
        label="research_intelligence.py\n--area all\n(entrypoint)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    supabase_in [
        label="Supabase\ndrug_areas . drugs . trials . catalysts\ncompany_profiles . deals\ndrug_competitive_scores\n(read here - all areas)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_loop {
        label="For each area (tl1a / tslp / il4ra / fcrn / igf1r / tcell)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        load_ctx [label="load_entity_context()\n(drugs + trials + catalysts\n+ profile + deals)"]
        score [label="score_entity_completeness()\n0-100 across 6 weighted stages\n(field-presence only, no LLM)"]
        triggers [label="check_research_triggers()\n(stale profile, PCD without catalyst,\ntrial phase mismatch, etc.)"]
        action [label="get_next_best_action()\n(priority-ordered decision tree)"]
        priority [label="calculate_priority_score()\n(0-200 urgency integer)"]
        upsert [label="upsert_research_queue()\n(write result + stamp drugs)"]
    }

    research_queue [
        label="Supabase\nresearch_queue\n(upsert per entity per area)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    drugs_out [
        label="Supabase\ndrugs\n(completeness_score + completeness_tier\nstamped on every drug row)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    stdout [
        label="stdout\nranked priority table per area\n(top 3 entities + average score)",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> supabase_in [label="  reads all areas", style="bold", color="#c9890a", fontcolor="#c9890a"]
    supabase_in -> load_ctx
    load_ctx -> score
    score -> triggers
    triggers -> action
    action -> priority
    priority -> upsert
    upsert -> research_queue [label="  upsert", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    upsert -> drugs_out [label="  patch score/tier", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    upsert -> stdout [label="  summary"]
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

        supabase_in [label="Supabase\ndrug_areas . drugs . trials\ncatalysts . company_profiles\ndeals . drug_competitive_scores\n(all 6 areas)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Completeness\nScoring",
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

        rq_out [label="Supabase\nresearch_queue\n(completeness score, tier, priority,\nnext action, triggers per entity)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        drugs_out [label="Supabase\ndrugs\n(completeness_score + completeness_tier\nstamped on every row)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nranked priority table\nper area", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    supabase_in -> pipeline
    pipeline -> rq_out
    pipeline -> drugs_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "drug_areas · drugs · trials · catalysts · company_profiles · deals · drug_competitive_scores",
                "kind": "Supabase tables",
                "via": "run_intelligence_audit() → load_entity_context() per entity",
                "desc": (
                    "For each area, `run_intelligence_audit()` discovers entities via "
                    "`drug_areas`, then calls `load_entity_context()` for each one. That "
                    "function fetches: `drugs` rows by entity_id and canonical_drug_id, "
                    "`trials` rows for those drugs, `catalysts`, the `company_profiles` row "
                    "for the company, `deals`, and `drug_competitive_scores`. Sibling drug "
                    "rows sharing a canonical_drug_id are merged into a single "
                    "best-values representative before scoring — so a program with two "
                    "drug rows (e.g., a bispecific and a monotherapy component) scores "
                    "as a single canonical program."
                ),
                "scope": (
                    "With `--area all`, iterates all 6 areas sequentially. Each area "
                    "reads its own drug_areas slice plus full entity context per entity "
                    "(typically 30–80 companies per area). No pagination concerns — "
                    "per-entity reads are narrow and bounded."
                ),
            },
        ],
        "cleaning": (
            "**Scoring is pure field-presence — no LLM calls, no external API calls.** "
            "`score_entity_completeness()` checks whether each of the 6 stage fields is "
            "non-empty (using `_nonempty()` which rejects None, '', [], {}) and weights "
            "them: Stage 1 Entity Discovery 10%, Stage 2 Drug Mapping 15%, Stage 3 Trial "
            "Intelligence 20%, Stage 4 Catalyst Engine 15%, Stage 5 Strategic Positioning "
            "25%, Stage 6 Deal Intelligence 15%. Drug-level scores are averaged across "
            "canonical programs (not raw rows) to avoid double-counting multi-row programs. "
            "The `_nonempty` check means a field set to an empty list or a blank string "
            "does not get credit — it must have actual content. "
            "Tier thresholds are fixed: thin <40, partial 40–69, strong >=70."
        ),
        "writes": [
            {
                "name": "research_queue",
                "kind": "Supabase table",
                "via": "upsert_research_queue() → _db.sb_upsert('research_queue', [row])",
                "desc": (
                    "One upserted row per entity per area, carrying: "
                    "`completeness_score`, `completeness_tier`, `priority_score`, "
                    "`next_action` (plain-English text from the decision tree), "
                    "`research_triggers` (list of detected trigger types), "
                    "`stage_scores` (per-stage breakdown), `missing_fields`, "
                    "and `last_scored_at` timestamp. Upsert key is "
                    "`(entity_id, area_id)` — re-running the same area is idempotent."
                ),
                "scope": (
                    "One row per entity per area per run. With --area all and 6 areas "
                    "each having ~50 entities, a full sweep writes ~300 research_queue "
                    "rows. All are upserts on a stable key, so re-runs never accumulate "
                    "duplicates."
                ),
            },
            {
                "name": "drugs (completeness_score, completeness_tier)",
                "kind": "Supabase table",
                "via": "upsert_research_queue() → _db.sb_patch('drugs', {completeness_score, completeness_tier}, {entity_id: ...})",
                "desc": (
                    "After writing the research_queue row, `upsert_research_queue()` also "
                    "patches `completeness_score` and `completeness_tier` directly onto "
                    "every `drugs` row for that entity. This allows the dashboard to "
                    "display per-drug completeness in drug lists without joining the "
                    "research_queue table — a denormalized convenience column that is "
                    "always refreshed by this daily sweep."
                ),
                "scope": (
                    "One PATCH per entity (targeting all drug rows for that entity_id). "
                    "Touches every drug row in the catalog over a full --area all run."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Entry point and area loop",
            "note": "The script's __main__ block parses args and calls run_intelligence_audit() once per area.",
            "groups": [
                [
                    {
                        "function": "__main__ argparse → run_intelligence_audit(area_id, …)",
                        "lines": 30,
                        "desc": (
                            "Parses `--area` (single area name or 'all'), `--entity` filter, "
                            "and `--dry-run`. With `--area all`, iterates `ALL_AREAS = "
                            "[tl1a, tslp, il4ra, fcrn, igf1r, tcell]` and calls "
                            "`run_intelligence_audit()` for each. With a single area, calls "
                            "it once. `--dry-run` is propagated all the way through to "
                            "`upsert_research_queue()`, suppressing all writes."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Entity context loading",
            "note": "For each entity in the area, all relevant Supabase data is fetched in one coordinated load.",
            "groups": [
                [
                    {
                        "function": "load_entity_context(entity_id, area_id)",
                        "lines": 123,
                        "desc": (
                            "Fetches the full context bundle for one entity: drugs (by entity_id "
                            "plus canonical_drug_id to catch all sibling rows), trials (by "
                            "drug_id AND canonical_drug_id), company profile, catalysts, "
                            "deals, and competitive scores. Calls `_group_drugs_by_canonical()` "
                            "to cluster drug rows by canonical_drug_id, then "
                            "`_merge_drug_rows()` to produce one best-values representative "
                            "per canonical program — so the scorer always sees one row per "
                            "program regardless of how many rows the program has in `drugs`."
                        ),
                    }
                ],
                [
                    {
                        "function": "_group_drugs_by_canonical(drugs) + _merge_drug_rows(rows)",
                        "lines": 68,
                        "desc": (
                            "`_group_drugs_by_canonical()` partitions the drug list into "
                            "sub-lists keyed by canonical_drug_id (drugs without a canonical "
                            "each get their own singleton group). `_merge_drug_rows()` then "
                            "takes a group and returns one dict where each field is the "
                            "first non-empty value across all rows in the group — so "
                            "completeness scoring reflects the best-available data for "
                            "the canonical program, not just one arbitrarily-chosen row."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Completeness scoring",
            "note": "Pure field-presence scoring across 6 weighted stages — no LLM, no external API.",
            "groups": [
                [
                    {
                        "function": "score_entity_completeness(ctx)",
                        "lines": 249,
                        "desc": (
                            "Checks each field in the context bundle for non-emptiness and "
                            "accumulates a weighted score across 6 stages: "
                            "Stage 1 Entity Discovery (weight 10) — entity_id, drugs list, "
                            "company_id; "
                            "Stage 2 Drug Mapping (15) — mechanism, target, stage, "
                            "differentiation_thesis, canonical_drug_id per program; "
                            "Stage 3 Trial Intelligence (20) — has_trials, arms/endpoints "
                            "populated, confidence_score >=80; "
                            "Stage 4 Catalyst Engine (15) — at least one catalyst with "
                            "expected_date + title; "
                            "Stage 5 Strategic Positioning (25) — profile exists, "
                            "competitive_position, vs_ailux, key_differentiators; "
                            "Stage 6 Deal Intelligence (15) — has_deals, economics_royalties "
                            "+ strategic_signal populated. Returns `completeness_score` (0–100 "
                            "int), `completeness_tier`, per-stage breakdown, and "
                            "`missing_fields` / `populated_fields` lists."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Trigger detection and action generation",
            "note": "After scoring, the entity is checked for time-sensitive conditions that require downstream action.",
            "groups": [
                [
                    {
                        "function": "check_research_triggers(ctx)",
                        "lines": 136,
                        "desc": (
                            "Detects seven trigger types on the entity context: "
                            "(1) trial phase ahead of drug stage; "
                            "(2) trial has a PCD but no catalyst generated; "
                            "(3) completed trial with no results text on the drug; "
                            "(4) catalyst expected_date has passed unresolved; "
                            "(5) company profile not enriched in >30 days; "
                            "(6) new deal created_at newer than last enrichment; "
                            "(7) entity is strategic but vs_ailux is empty. "
                            "Returns a list of triggered type names."
                        ),
                    }
                ],
                [
                    {
                        "function": "get_next_best_action(ctx, score_result)",
                        "lines": 103,
                        "desc": (
                            "Priority-ordered decision tree that converts the score result "
                            "and trigger list into a single plain-English action string "
                            "(e.g. 'Run trial sync — 2 PCDs without catalysts'). "
                            "Checks triggers first (most urgent), then missing stages in "
                            "descending weight order, then general completeness gap. "
                            "The action string is stored in research_queue.next_action "
                            "and surfaces in the dashboard's priority list."
                        ),
                    }
                ],
                [
                    {
                        "function": "calculate_priority_score(ctx, score_result, triggers)",
                        "lines": 64,
                        "desc": (
                            "Computes an urgency integer 0–200 from three components: "
                            "base = (100 - completeness_score) for incompleteness urgency; "
                            "trigger bonus = +15 per active trigger; "
                            "strategic multiplier = x1.5 if the company is flagged as "
                            "strategic for Ailux. Returns the score plus a human reason "
                            "string (e.g. 'incomplete [score=42] + 2 triggers'). "
                            "Higher score = research sooner."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Research queue write",
            "note": "Upserts the scored result and stamps completeness directly onto drugs rows.",
            "groups": [
                [
                    {
                        "function": "upsert_research_queue(entity_id, area_id, score_result, …)",
                        "lines": 84,
                        "desc": (
                            "Upserts a `research_queue` row keyed on `(entity_id, area_id)` "
                            "with the full scoring output: completeness_score, "
                            "completeness_tier, priority_score, next_action, triggers, "
                            "stage_scores breakdown, missing_fields list, and "
                            "last_scored_at ISO timestamp. Then patches "
                            "`completeness_score` and `completeness_tier` directly onto "
                            "all `drugs` rows for the entity. Both writes are skipped "
                            "if `dry_run=True`."
                        ),
                    }
                ],
            ],
        },
    ],
}
