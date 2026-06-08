"""
Static description of the Compute Landscape Dependency Scores pipeline
(.github/workflows/chain-04-compute-landscape-scores.yml).

Documents what the single entrypoint script does — computing five sub-component
scores for each competitive_landscapes row, combining them into a
landscape_dependency_score, patching the result back to Supabase, applying a
research_queue priority boost for weak areas, and stamping system_status.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "compute_landscape_scores",
    "workflow_name": "Compute Landscape Dependency Scores",
    "workflow_file": ".github/workflows/chain-04-compute-landscape-scores.yml",
    "schedule": (
        "Event-driven (after Content Verifier succeeds, --all mode) "
        "+ Mon 11:30 UTC fallback"
    ),
    "entrypoint": "scripts/scoring/compute_landscape_scores.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Computes the `landscape_dependency_score` (LDS) for every "
        "`competitive_landscapes` row, using a five-component formula: "
        "drug coverage (35%), relationship coverage (25%), catalyst coverage (20%), "
        "source validation (15%), minus a staleness penalty (5%). "
        "Each component is derived from live `drug_competitive_scores`, `drugs`, "
        "`deals`, and `catalysts` data, ensuring scores reflect the catalog's "
        "current state after the nightly Research → Source Verify → Content Verify "
        "chain. After scoring, areas with low LDS get a priority boost in "
        "`research_queue` (N4 feedback loop), and `system_status` is stamped so "
        "the dashboard can show a fresh-scores badge."
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
        label="compute_landscape_scores.py\n(entrypoint — main())",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    landscapes_in [
        label="Supabase\ncompetitive_landscapes\n(LDS is null, or --all / --area)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_per_area {
        label="Per landscape row — compute_for_area()"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        dcs [label="drug_competitive_scores\n(get drug_ids for area)"]
        drugs_in [label="drugs\n(source_url, last_synced_date)"]
        deals_in [label="deals\n(drug_id set with at least 1 deal)"]
        cats_in  [label="catalysts\n(drug_id set with at least 1 catalyst)"]

        subgraph cluster_formula {
            label="LDS formula"
            style="dotted"
            color="#9aa7b5"
            pencolor="#9aa7b5"
            fontname="Helvetica"
            fontsize=10
            fontcolor="#e8ecf2"

            cov1 [label="drug_coverage x 35"]
            cov2 [label="relationship_coverage x 25"]
            cov3 [label="catalyst_coverage x 20"]
            cov4 [label="source_validation x 15"]
            stale [label="staleness_penalty x -5"]
        }

        staleness_fn [label="staleness_score(drugs)\n(avg days since last_synced)"]
    }

    landscapes_out [
        label="Supabase\ncompetitive_landscapes\n(LDS + 5 sub-scores patched)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    rq_out [
        label="Supabase\nresearch_queue\n(N4 priority boost for low-LDS areas)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    status_out [
        label="Supabase\nsystem_status\n(last_scoring_at stamped)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    trigger_out [
        label="Triggers on success:\nchain-05 Meridian Writer",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> landscapes_in [label="  reads areas to score", style="bold", color="#c9890a", fontcolor="#c9890a"]
    landscapes_in -> dcs
    dcs -> drugs_in [label="  fetch drug details"]
    dcs -> deals_in [label="  fetch deal coverage"]
    dcs -> cats_in  [label="  fetch catalyst coverage"]
    drugs_in -> staleness_fn
    drugs_in -> cov1
    drugs_in -> cov4
    deals_in -> cov2
    cats_in -> cov3
    staleness_fn -> stale
    cov1 -> landscapes_out [label="  patch LDS + sub-scores", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    cov2 -> landscapes_out
    cov3 -> landscapes_out
    cov4 -> landscapes_out
    stale -> landscapes_out
    landscapes_out -> rq_out [label="  N4 feedback boost", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    landscapes_out -> status_out [label="  stamp scoring time", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    entry -> trigger_out [label="  workflow_run event", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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
        label="Inputs — what comes in, and from where"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        sb_in [label="Supabase\ncompetitive_landscapes (areas to score)\ndrug_competitive_scores · drugs\ndeals · catalysts", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Compute\nLandscape\nScores",
        shape=ellipse,
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827",
        fontsize=12
    ]

    subgraph cluster_out {
        label="Outputs — what goes out, and to where"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        landscapes_out [label="Supabase\ncompetitive_landscapes\n(LDS + sub-scores patched)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        rq_out [label="Supabase\nresearch_queue\n(N4 priority boost)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        status_out [label="Supabase\nsystem_status\n(last_scoring_at)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        trigger_out [label="Triggers\nchain-05 Meridian Writer", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    pipeline -> landscapes_out
    pipeline -> rq_out
    pipeline -> status_out
    pipeline -> trigger_out
}
""",
    "io": {
        "reads": [
            {
                "name": "competitive_landscapes",
                "kind": "Supabase table",
                "via": "main() → sb_get('competitive_landscapes', params)",
                "desc": (
                    "Fetches all rows (up to 20) where `landscape_dependency_score IS "
                    "NULL` by default. `--all` drops the null filter to recompute "
                    "all areas; `--area <id>` restricts to a single row. Each row "
                    "provides `area_id`, `target_pair`, and the optional "
                    "`expected_drug_count`, `expected_relationship_count`, "
                    "`expected_catalyst_count` overrides used in the formula."
                ),
                "scope": (
                    "Single query at startup; the nightly chained run passes `--all` "
                    "so all areas are recomputed on freshly-verified data."
                ),
            },
            {
                "name": "drug_competitive_scores",
                "kind": "Supabase table",
                "via": "compute_for_area() → sb_get() with context_type/context_id filters",
                "desc": (
                    "For each area, one or more queries (depending on the `ctx_map` "
                    "entry for that area) fetch all `drug_id` values in that area's "
                    "competitive-score context. This is the denominator for all "
                    "coverage calculations."
                ),
                "scope": (
                    "One query per context tuple per area (up to 2 for multi-context "
                    "areas like `ibd`). Capped at 200 rows per query."
                ),
            },
            {
                "name": "drugs",
                "kind": "Supabase table",
                "via": "compute_for_area() → sb_get('drugs', {'id': 'in.(...)', ...})",
                "desc": (
                    "For the drug_ids in an area, fetches `id`, `source_url`, and "
                    "`last_synced_date`. `source_url` drives the "
                    "`source_validation_score`; `last_synced_date` drives the "
                    "`staleness_penalty`."
                ),
                "scope": "One query per area, capped at 200 rows.",
            },
            {
                "name": "deals · catalysts",
                "kind": "Supabase tables",
                "via": "compute_for_area() — chunked in.(drug_id_list) queries, 50 ids per chunk",
                "desc": (
                    "For deals: collects drug_ids that have at least one deal row "
                    "— the numerator for `relationship_coverage_score`. "
                    "For catalysts: collects drug_ids that have at least one catalyst "
                    "row — the numerator for `catalyst_coverage_score`. Both are "
                    "chunked in groups of 50 ids to stay within Supabase's URL length "
                    "limit for the `in.(...)` filter."
                ),
                "scope": (
                    "ceil(len(drug_ids) / 50) queries each for deals and catalysts, "
                    "capped at 200 rows per chunk."
                ),
            },
        ],
        "cleaning": (
            "**All five sub-components are capped at 1.0 (maximum) before being "
            "multiplied by their weights.** `drug_coverage` uses `expected_drug_count` "
            "from the landscape row as the denominator if set and greater than actual "
            "— preventing an over-count from inflating the score. "
            "`relationship_coverage` and `catalyst_coverage` similarly use "
            "`expected_relationship_count` / `expected_catalyst_count` from the row, "
            "falling back to heuristics (60% and 70% of total drugs respectively) if "
            "not set. The `staleness_penalty` is a smooth ramp: 0.0 for avg sync "
            "within 60 days, 0.5 for 60-120 days, up to 1.0 beyond 120 days — so "
            "a completely un-synced area loses at most 5 LDS points. "
            "Areas with no DCS rows return an empty result dict and are skipped in "
            "the output summary."
        ),
        "writes": [
            {
                "name": "competitive_landscapes",
                "kind": "Supabase table",
                "via": "compute_for_area() → sb_patch('competitive_landscapes', {'area_id': 'eq.<id>'}, result)",
                "desc": (
                    "Patches `landscape_dependency_score`, all five sub-component "
                    "scores (`drug_coverage_score`, `relationship_coverage_score`, "
                    "`catalyst_coverage_score`, `source_validation_score`, "
                    "`staleness_penalty`), the three `expected_*_count` fields, "
                    "`drug_count`, and `coverage_computed_at`. One PATCH per area."
                ),
                "scope": "One write per area row processed (bounded by the initial landscape query).",
            },
            {
                "name": "research_queue",
                "kind": "Supabase table",
                "via": "_apply_lds_priority_feedback() → _db.sb_patch() per row",
                "desc": (
                    "N4 feedback loop: for areas with LDS below 75, pending "
                    "`research_queue` items for that area get a priority boost "
                    "(+8 for LDS 60-75, +15 for LDS < 60), capped at 100. "
                    "This steers the next enrichment run toward filling coverage gaps "
                    "in weak areas."
                ),
                "scope": (
                    "Up to 50 queue items per low-LDS area, one PATCH each. "
                    "Skipped entirely if no areas scored below 75 or if the queue "
                    "is empty."
                ),
            },
            {
                "name": "system_status",
                "kind": "Supabase table",
                "via": "main() → sb_patch('system_status', {'id': 'eq.1'}, {...})",
                "desc": (
                    "Stamps `last_scoring_at`, `updated_at`, "
                    "`last_pipeline_label='landscape_scoring'`, and a human-readable "
                    "`note` with the count of areas recomputed. Lets the dashboard "
                    "surface a fresh-scores badge."
                ),
                "scope": "One PATCH per run, always on `id=1`.",
            },
        ],
    },
    "phases": [
        {
            "label": "Helpers",
            "note": "Two thin wrappers and one standalone computation used throughout compute_for_area().",
            "groups": [
                [
                    {
                        "function": "sb_get(table, params) / sb_patch(table, params, payload)",
                        "lines": 8,
                        "desc": (
                            "One-line shims over `_db.sb_get()` and `_db.sb_patch()` "
                            "that normalise the argument order used by the older call "
                            "sites in this file. `sb_patch` swaps the `params` / "
                            "`payload` positional order relative to `_db.sb_patch`."
                        ),
                    }
                ],
                [
                    {
                        "function": "staleness_score(drugs)",
                        "lines": 19,
                        "desc": (
                            "Parses `last_synced_date` from each drug row, computes "
                            "the average age in days, and maps it to a penalty: "
                            "0.0 (avg <= 60 days), linear 0-0.5 (60-120 days), "
                            "linear 0.5-1.0 (> 120 days), capped at 1.0. "
                            "Drugs with no `last_synced_date` are omitted from the "
                            "average; if all are null returns 1.0 (maximum penalty)."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Per-area computation",
            "note": "Core scoring logic — reads all relevant data for one area and computes its LDS.",
            "groups": [
                [
                    {
                        "function": "compute_for_area(landscape, dry_run=False)",
                        "lines": 133,
                        "desc": (
                            "Entry point for one area. Resolves the area's "
                            "`drug_competitive_scores` context using a hardcoded "
                            "`ctx_map` (e.g. `ibd` maps to UC + CD indication "
                            "contexts). Fetches drug details, then chunked deal and "
                            "catalyst coverage. Computes all five sub-components, "
                            "combines them into the LDS formula, prints each "
                            "intermediate value, and (unless `dry_run`) PATCHes "
                            "`competitive_landscapes`. Returns the result dict "
                            "(or `{}` if no DCS rows found for the area)."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "N4 LDS feedback",
            "note": "Priority boost for weak areas — steers the enrichment queue toward coverage gaps.",
            "groups": [
                [
                    {
                        "function": "_apply_lds_priority_feedback(results)",
                        "lines": 35,
                        "desc": (
                            "Takes the `{area_id: lds}` results dict from `main()`. "
                            "For each area with LDS < 75, fetches up to 50 pending "
                            "`research_queue` items for that area and increments their "
                            "`priority_score` by BOOST_MEDIUM (+8) or BOOST_HIGH (+15), "
                            "capped at 100. Logs the total count of boosted items. "
                            "Errors per area are caught individually so a queue table "
                            "absence doesn't abort the scoring run."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main loop",
            "note": "Parses args, fetches landscapes, drives per-area scoring, applies N4 feedback, and stamps system_status.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 48,
                        "desc": (
                            "Parses `--dry-run`, `--area`, and `--all`. Queries "
                            "`competitive_landscapes` (null LDS by default, or `--all` "
                            "for all, or `--area` for one). Iterates each landscape "
                            "row calling `compute_for_area()`, collects results into "
                            "a `{area_id: lds}` dict, prints the summary table. Then "
                            "calls `_apply_lds_priority_feedback()` and patches "
                            "`system_status` (both only when not dry-run and results "
                            "are non-empty)."
                        ),
                    }
                ],
            ],
        },
    ],
}
