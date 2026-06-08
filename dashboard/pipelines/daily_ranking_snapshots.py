"""
Static description of the Daily Ranking Snapshots pipeline
(.github/workflows/daily-ranking-snapshots.yml).

Documents what write_ranking_snapshots.py does: reading Next Gen competitive
scores, computing composite rankings, and persisting daily snapshots to the
next_gen_rankings table for the dashboard's ranking visualizations.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "ranking_snapshots",
    "workflow_name": "Daily Ranking Snapshots",
    "workflow_file": ".github/workflows/daily-ranking-snapshots.yml",
    "schedule": "Daily 11:00 UTC (7 AM ET) — after the Meridian issue publishes at 6:30 AM ET",
    "entrypoint": "scripts/scoring/write_ranking_snapshots.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Daily snapshot of next-gen program rankings for the three strategy areas: "
        "tl1a, ibd, and fcrn. Reads `drug_competitive_scores` for all Next Gen "
        "programs in each area, computes a composite score (70% enrichment score + "
        "30% stage signal; Ailux programs use a separate stage-based development "
        "score), sorts descending, and upserts one row per drug per area into "
        "`next_gen_rankings` with rank_position, total_score, stage, and "
        "competitive_relev. The dashboard reads this table directly — it never "
        "writes ranking data itself. The same script also runs as a post-pipeline "
        "step inside the nightly Intelligence Pipeline; this standalone workflow "
        "ensures snapshots are recorded even on days when the enrichment pipeline "
        "is skipped or fails."
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
        label="write_ranking_snapshots.py\n(entrypoint - main)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    scores_in [
        label="Supabase\ndrug_competitive_scores\n(cls='Next Gen', read per area)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    drugs_in [
        label="Supabase\ndrugs\n(id, stage, company_id, name\nread for each drug_id batch)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_loop {
        label="For each area (tl1a / ibd / fcrn)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        composite [label="composite(s)\n70% enrichment score\n+ 30% stage weight\n(Ailux: dev-score table only)"]
        sort [label="sort descending\nassign rank 1..N"]
        build_rows [label="build snapshot_rows\n(entity_id, name, area, rank,\nscore, stage, relev, is_ailux, date)"]
    }

    rankings_out [
        label="Supabase\nnext_gen_rankings\n(upsert - all areas)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    stdout [
        label="stdout\nranked list per area\n(name, score, stage per drug)",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> scores_in [label="  reads Next Gen scores", style="bold", color="#c9890a", fontcolor="#c9890a"]
    entry -> drugs_in [label="  reads stage + company", style="bold", color="#c9890a", fontcolor="#c9890a"]
    scores_in -> composite
    drugs_in -> composite
    composite -> sort
    sort -> build_rows
    build_rows -> rankings_out [label="  sb_upsert", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    build_rows -> stdout [label="  prints each rank"]
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

        sb_scores [label="Supabase\ndrug_competitive_scores\n(cls='Next Gen' per area)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        sb_drugs [label="Supabase\ndrugs\n(stage, company_id, name\nper drug batch)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Daily Ranking\nSnapshots",
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

        rankings_out [label="Supabase\nnext_gen_rankings\n(rank_position, total_score, stage,\ncompetitive_relev, is_ailux, date)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nranked list per area", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_scores -> pipeline
    sb_drugs -> pipeline
    pipeline -> rankings_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "drug_competitive_scores",
                "kind": "Supabase table",
                "via": "compute_rankings(area_id) → sb_get('drug_competitive_scores', {context_id: area, cls: 'Next Gen'})",
                "desc": (
                    "For each of the three strategy areas, fetches all rows from "
                    "`drug_competitive_scores` where `cls='Next Gen'` and "
                    "`context_id=<area_id>`. Each row carries `drug_id`, "
                    "`total_competition_score` (the enrichment-derived score computed "
                    "by `company_enrichment.py`), and `competitive_relevance` text. "
                    "These scores are the primary ranking signal."
                ),
                "scope": (
                    "One query per area (tl1a, ibd, fcrn) with a 1 000-row limit — "
                    "well within the Next Gen program count (~15–40 per area). "
                    "If no Next Gen scores exist for an area, that area is skipped "
                    "and logged to stdout."
                ),
            },
            {
                "name": "drugs",
                "kind": "Supabase table",
                "via": "compute_rankings(area_id) → sb_get('drugs', {id: 'in.(drug_ids)', select: 'id,stage,company_id,name'})",
                "desc": (
                    "After loading the competitive scores, fetches the matching `drugs` "
                    "rows in a single batch query to obtain `stage`, `company_id`, and "
                    "`name` for each scored drug. `stage` feeds the stage-weight component "
                    "of the composite score; `company_id` determines whether the drug "
                    "belongs to Ailux (which uses the `AILUX_DEV_SC` table instead of "
                    "the standard formula); `name` is stored in the snapshot row for "
                    "display in the dashboard."
                ),
                "scope": (
                    "One batch query per area, fetching exactly the drug_ids present in "
                    "the competitive scores result."
                ),
            },
        ],
        "cleaning": (
            "**Composite score formula guards against missing data.** The `composite()` "
            "inner function uses `s.get('total_competition_score') or 0` — so a None or "
            "zero enrichment score falls back to 0 rather than crashing. Stage lookup "
            "uses `stage_map.get(drug_id, 'Preclinical')` — drugs missing from the "
            "`drugs` batch result (an edge case) default to Preclinical stage weight. "
            "Ailux programs bypass the 70/30 formula entirely and use `AILUX_DEV_SC` "
            "keyed on stage — this keeps Ailux's own programs ranked by development "
            "maturity rather than by a competitive score computed against themselves. "
            "The upsert to `next_gen_rankings` is idempotent on "
            "`(entity_id, area_id, snapshot_date)` — re-running on the same day "
            "overwrites the same rows."
        ),
        "writes": [
            {
                "name": "next_gen_rankings",
                "kind": "Supabase table",
                "via": "compute_rankings() → sb_upsert('next_gen_rankings', snapshot_rows)",
                "desc": (
                    "One upserted row per drug per area, containing: "
                    "`entity_id` (the company_id for the drug), `entity_name` (drug name), "
                    "`area_id`, `rank_position` (1-based integer), `total_score` (composite, "
                    "rounded to 2 dp), `stage`, `competitive_relev` (text from competitive "
                    "scores), `is_ailux` (boolean), and `snapshot_date` (today's ISO date). "
                    "The browser reads this table exclusively for its ranking views — "
                    "the table is never written by the dashboard itself."
                ),
                "scope": (
                    "Typically 30–120 rows per full run (10–40 Next Gen programs per area "
                    "across 3 areas). All are upserts on the natural key, so re-running "
                    "does not accumulate rows."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Credential setup and helpers",
            "note": "Module-level setup initialises the database connection and defines two thin wrappers.",
            "groups": [
                [
                    {
                        "function": "sb_get(table, params=None)",
                        "lines": 4,
                        "desc": (
                            "Thin shim over `_db.sb_get()` that injects a default `limit=1000` "
                            "into the params dict before forwarding. Ensures all reads in this "
                            "script observe the same cap without repeating the limit parameter "
                            "at each call site."
                        ),
                    }
                ],
                [
                    {
                        "function": "sb_upsert(table, rows)",
                        "lines": 5,
                        "desc": (
                            "Wraps `_db.sb_upsert()` and normalises the return value: "
                            "the underlying function returns the upserted rows (or [] on "
                            "failure), but callers here only need a success/failure signal, "
                            "so this wrapper returns 200 if the upsert produced rows (or if "
                            "the input was empty), and None on failure."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Ranking computation",
            "note": "Core per-area function — reads scores, computes composite, builds snapshot rows.",
            "groups": [
                [
                    {
                        "function": "compute_rankings(area_id, dry_run=False)",
                        "lines": 61,
                        "desc": (
                            "Fetches Next Gen `drug_competitive_scores` for the area, then "
                            "fetches the matching `drugs` rows for stage and company metadata. "
                            "Defines a `composite(s)` inner function: Ailux drugs return "
                            "`AILUX_DEV_SC[stage]` (a development maturity score); all others "
                            "return `(enrichment_score * 0.7) + (STAGE_W[stage] * 0.3)`. "
                            "Sorts candidates descending by composite score, assigns rank "
                            "1..N, builds a `snapshot_rows` list, and upserts to "
                            "`next_gen_rankings` (or logs the count with DRY RUN prefix). "
                            "Returns the number of rows written."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main entry point",
            "note": "Parses args and drives compute_rankings() across the configured areas.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 11,
                        "desc": (
                            "Parses `--area` (optional, default=None → all three areas) and "
                            "`--dry-run`. Selects the area list: either `[args.area]` for "
                            "a specific area or `NEXT_GEN_AREAS = [tl1a, ibd, fcrn]` for "
                            "a full run. Iterates `compute_rankings()` per area, accumulates "
                            "the total row count, and prints a final summary line."
                        ),
                    }
                ],
            ],
        },
    ],
}
