"""
Static description of the Fine-Tuning Flywheel Phase 2 pipeline
(.github/workflows/weekly-flywheel-phase2.yml).

Documents, in execution order, what the entrypoint script does — drift
detection, auto-restore, and fine-tuning export — and what it reads from
and writes back to Supabase plus the output/ artifact directory.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "flywheel_phase2",
    "workflow_name": "Fine-Tuning Flywheel Phase 2",
    "workflow_file": ".github/workflows/weekly-flywheel-phase2.yml",
    "schedule": "Tuesdays 12:00 UTC (8 AM ET — the morning after Monday's validation run)",
    "entrypoint": "scripts/ml/flywheel_phase2.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Weekly drift monitor that compares every Kyle-confirmed `kyle_reviews` "
        "value against the live database, auto-restores any that have silently "
        "regressed back to Kyle's confirmed text, and exports the same confirmed "
        "values as prompt→response pairs for future LLM fine-tuning. It's the "
        "guardrail that keeps enrichment runs from quietly overwriting "
        "human-verified ground truth — and the data-collection step that turns "
        "that ground truth into training signal."
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
        label="flywheel_phase2.py\n(entrypoint — owns args, loop, summary)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    kyle_reviews [
        label="Supabase\nkyle_reviews\n(read here — fine_tune_use=true)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_loop {
        label="Per confirmed review (skips [WARNING]/[NEEDS_REVIEW]/empty values)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        get_current [label="get_current_value()\nfetch live field value"]
        compare [label="compare confirmed vs. live\n→ match / partial / drifted / empty"]
        restore [label="restore_value()\n(only if field ∈ RESTORABLE_FIELDS\nand not --detect-only)"]
        build_pair [label="build_training_pair()\n(drug entities only)"]
    }

    entity_tables [
        label="Supabase\ndrugs · company_partnerships · deals\n(read for current value + context)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    restored_tables [
        label="Supabase\ndrugs · company_partnerships · deals\n(patched here — restored fields only)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    drift_report [
        label="output/\ndrift_report_<date>.json",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    training_pairs [
        label="output/\ntraining_pairs_<date>.jsonl",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    artifact [
        label="GitHub Actions\nupload-artifact\n(30-day retention)",
        fillcolor="#fde9c8",
        color="#d99a3b",
        fontcolor="#111827"
    ]

    entry -> kyle_reviews [label="  reads\n  (fine_tune_use=true)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    kyle_reviews -> get_current
    get_current -> entity_tables [label="  reads current value", style="bold", color="#c9890a", fontcolor="#c9890a"]
    entity_tables -> get_current
    get_current -> compare
    compare -> restore [label="  drifted / empty\n  + restorable field"]
    restore -> restored_tables [label="  sb_patch", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    compare -> build_pair [label="  always\n  (drug reviews only)"]
    entity_tables -> build_pair [label="  reads context\n  (name/stage/target/company)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    build_pair -> training_pairs [label="  appends", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    compare -> drift_report [label="  appends to report", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    drift_report -> artifact
    training_pairs -> artifact
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

        kyle_reviews_in [label="Supabase\nkyle_reviews\n(fine_tune_use=true)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        entity_in [label="Supabase\ndrugs · company_partnerships ·\ndeals", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Flywheel\nPhase 2",
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

        entity_out [label="Supabase\ndrugs · company_partnerships ·\ndeals\n(restored fields only)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        files_out [label="output/\ndrift_report_*.json ·\ntraining_pairs_*.jsonl", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        artifact_out [label="GitHub Actions artifact\n(30-day retention)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    kyle_reviews_in -> pipeline
    entity_in -> pipeline
    pipeline -> entity_out
    pipeline -> files_out
    files_out -> artifact_out
}
""",
    "io": {
        "reads": [
            {
                "name": "kyle_reviews",
                "kind": "Supabase table",
                "via": "sb_get('kyle_reviews', {'fine_tune_use': 'eq.true', 'select': '*'})",
                "desc": (
                    "The full set of Kyle-confirmed field reviews flagged "
                    "`fine_tune_use=true` — each row pairs an `entity_type` "
                    "(drug / partnership / deal), an `entity_id`, a `field_name`, "
                    "and the `field_value` Kyle confirmed as correct. This is the "
                    "ground-truth worklist the entire run is built around."
                ),
                "scope": (
                    "One query, one shot: capped at `limit=500` via the shared "
                    "`sb_get(table, params, limit=500)` wrapper, with an optional "
                    "`--entity-type` filter narrowing to a single entity type. "
                    "Everything else in the run iterates this single in-memory list — "
                    "there's no pagination because confirmed-review volume is small "
                    "and grows slowly (one row per Kyle approval)."
                ),
            },
            {
                "name": "drugs · company_partnerships · deals",
                "kind": "Supabase tables",
                "via": "get_current_value() and the context lookup in main()",
                "desc": (
                    "For every reviewed field, `get_current_value()` re-fetches just "
                    "that one column for that one row (`select: field`) to compare "
                    "against the confirmed text. Separately, for drug reviews, "
                    "`main()` re-fetches `id,name,stage,target,company_id` to give "
                    "`build_training_pair()` enough context to write a realistic "
                    "enrichment prompt."
                ),
                "scope": (
                    "Two narrow, single-row reads per reviewed field — "
                    "`{id_col: 'eq.<raw_id>', select: <field>, limit: 1}` for the "
                    "current-value check, and a second `select: 'id,name,stage,"
                    "target,company_id'` lookup for drug context. `entity_id` values "
                    "carry an optional `<prefix>:<uuid>` form; `raw_id = "
                    "entity_id.split(':')[-1]` strips the prefix before either query. "
                    "Nothing here is batched — it's strictly proportional to the "
                    "number of confirmed reviews, which is what keeps the whole run "
                    "inside its 20-minute timeout."
                ),
            },
        ],
        "cleaning": (
            "**Three filters gate every row before it counts as drift, and a fourth "
            "gates whether it gets auto-restored.** First, reviews with a blank "
            "`field_value`, or one starting with `[WARNING]` or `[NEEDS_REVIEW]`, are "
            "routed straight to `no_value` and skipped — they were never usable ground "
            "truth. Second, the live value is string-compared three ways: an exact "
            "match after `.strip()` is `matched`; if either string's first 60 "
            "characters appears inside the other it's called `partial` (treated as "
            "healthy — not drifted, not restored, not reported); anything else is "
            "`drifted`, and a blank live value is called out separately as `empty`. "
            "Third, only `drifted`/`empty` rows get written into the report's "
            "`drifted` bucket at all — `matched` and `partial` rows are counted but "
            "never logged individually. Fourth, auto-restore only fires for rows that "
            "are both drifted/empty *and* whose `field_name` appears in the static "
            "`RESTORABLE_FIELDS` allowlist for that entity type (e.g. `ailux_angle`, "
            "`drug_summary`, `mechanism` for drugs; `source_url`, "
            "`partnership_verified` for partnerships) — and even then, "
            "`--detect-only` suppresses the write entirely so you can audit drift "
            "without risking a bad restore."
        ),
        "writes": [
            {
                "name": "drugs · company_partnerships · deals",
                "kind": "Supabase tables",
                "via": "restore_value() → _db.sb_patch(table, {field: value, updated_at: NOW}, {id_col: 'eq.<raw_id>'})",
                "desc": (
                    "Patches exactly one column (plus `updated_at`) on exactly one "
                    "row back to Kyle's confirmed text — never a broader rewrite. "
                    "This is the auto-restore half of the flywheel: it's what makes "
                    "the weekly run self-healing rather than just diagnostic."
                ),
                "scope": (
                    "Bounded tightly on three sides: only fields in "
                    "`RESTORABLE_FIELDS`, only rows already flagged `drifted`/`empty`, "
                    "and only when `--detect-only` is *not* set. In practice this "
                    "means at most one PATCH per drifted-and-restorable review per "
                    "week — typically a handful of rows, not a sweep."
                ),
            },
            {
                "name": "output/drift_report_<date>.json",
                "kind": "Local artifact file",
                "via": "json.dump(drift_report, ...)",
                "desc": (
                    "A single JSON summary for the run: `date`, `total` reviews "
                    "processed, and four buckets — `drifted` (with confirmed/current "
                    "previews truncated to 100 chars), `restored`, `matched`, and "
                    "`no_value`. This is the audit trail Kyle (or anyone) can open "
                    "after the fact to see exactly what regressed and what got fixed."
                ),
                "scope": (
                    "One file per run, named by date (`drift_report_YYYY-MM-DD.json`), "
                    "written once at the end via a single `json.dump`. Re-running on "
                    "the same day overwrites the same file — there's no append or "
                    "versioning beyond the date stamp."
                ),
            },
            {
                "name": "output/training_pairs_<date>.jsonl",
                "kind": "Local artifact file",
                "via": "build_training_pair() + line-delimited json.dumps(pair)",
                "desc": (
                    "One JSON object per line — `{type, entity_type, entity_id, "
                    "field, prompt, response, source: 'kyle_confirmed', session, "
                    "date}` — pairing a synthesized enrichment prompt with Kyle's "
                    "confirmed answer as the target response. This is the raw "
                    "material for a future fine-tuning pass: real fields, real "
                    "human-verified values, framed as the exact kind of prompt the "
                    "enrichment pipeline would have asked."
                ),
                "scope": (
                    "Drug reviews only (`if entity_type != 'drug': return None` inside "
                    "`build_training_pair()`) — partnerships and deals are tracked for "
                    "drift but not yet exported for fine-tuning. Built incrementally, "
                    "one pair per qualifying review (bounded by the same ≤500-row "
                    "`kyle_reviews` read), then flushed to the `.jsonl` in one pass at "
                    "the end."
                ),
            },
            {
                "name": "GitHub Actions artifact",
                "kind": "CI artifact upload",
                "via": "actions/upload-artifact@v4 (workflow step, not the script)",
                "desc": (
                    "Both output files are uploaded as a single named artifact "
                    "(`flywheel-outputs-<run_id>`) with 30-day retention — making the "
                    "drift report and training pairs downloadable from the Actions run "
                    "page without needing repo write access or a Supabase query."
                ),
                "scope": (
                    "Glob-matched (`output/drift_report_*.json`, "
                    "`output/training_pairs_*.jsonl`), so it picks up whatever the "
                    "script wrote that run — normally exactly one of each."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Helpers",
            "note": "Four supporting functions defined at module level, each called from main().",
            "groups": [
                [
                    {
                        "function": "sb_get(table, params, limit=500)",
                        "lines": 4,
                        "desc": (
                            "Thin shim over `_db.sb_get()` that merges an explicit "
                            "`limit` into the params dict before forwarding — the only "
                            "place in the file that touches `_db` directly."
                        ),
                    }
                ],
                [
                    {
                        "function": "get_current_value(entity_type, entity_id, field)",
                        "lines": 19,
                        "desc": (
                            "Fetches exactly one column for one row from whichever table "
                            "matches `entity_type` (drugs / company_partnerships / deals), "
                            "using a `select: <field>, limit: 1` query. Strips a "
                            "`<prefix>:` from `entity_id` before querying. Returns the "
                            "value as a string, or `None` if the entity type is "
                            "unrecognised or the row doesn't exist."
                        ),
                    }
                ],
                [
                    {
                        "function": "restore_value(entity_type, entity_id, field, value)",
                        "lines": 9,
                        "desc": (
                            "Patches the confirmed value back to the database via "
                            "`_db.sb_patch()`, also setting `updated_at` to the current "
                            "UTC timestamp. Resolves entity type to table/id-column the "
                            "same way as `get_current_value()`. Returns `True` on success."
                        ),
                    }
                ],
                [
                    {
                        "function": "build_training_pair(review, entity_context)",
                        "lines": 34,
                        "desc": (
                            "Constructs a fine-tuning prompt→response pair from a "
                            "`kyle_reviews` row and the drug context dict fetched by "
                            "`main()`. The prompt is a realistic enrichment request "
                            "(\"Research the pharmaceutical drug X... Provide the field Y\") "
                            "and the response is Kyle's confirmed value. Returns `None` for "
                            "non-drug reviews (partnerships / deals not yet exported) or "
                            "for rows missing a field name or confirmed value."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main loop",
            "note": (
                "Single entry point called by `__main__`. Owns argument parsing, "
                "the full per-review loop, and both file writes."
            ),
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 109,
                        "desc": (
                            "Parses `--detect-only` / `--export-only` / `--entity-type`, "
                            "then bulk-fetches all `fine_tune_use=true` `kyle_reviews` "
                            "rows (up to 500). Iterates every review: skips flagged/blank "
                            "values; in `--export-only` mode builds a training pair and "
                            "continues; otherwise calls `get_current_value()`, classifies "
                            "the result as matched / partial / drifted / empty, appends to "
                            "the drift report, calls `restore_value()` for drifted-and-"
                            "restorable fields (unless `--detect-only`), and calls "
                            "`build_training_pair()` for drug reviews. Writes "
                            "`drift_report_<date>.json` and `training_pairs_<date>.jsonl` "
                            "to `output/`, then prints a run summary (processed / matched "
                            "/ drifted / empty / restored / pairs counts plus the first 8 "
                            "drifted fields)."
                        ),
                    }
                ],
            ],
        },
    ],
}
