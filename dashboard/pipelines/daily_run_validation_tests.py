"""
Static description of the Ground Truth Validation Tests pipeline
(.github/workflows/daily-run-validation-tests.yml).

Runs all validation_tests rows against live Supabase data daily, writes
pass/fail results back to the table, and exits non-zero if any P1 blockers
fail. No LLM — pure declarative assertions.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "validation_tests",
    "workflow_name": "Run Ground Truth Validation Tests",
    "workflow_file": ".github/workflows/daily-run-validation-tests.yml",
    "schedule": "Daily 11:00 UTC (7 AM ET) — drift now surfaces within 24h rather than weekly",
    "entrypoint": "scripts/validation/validate_ground_truth.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "The quality gate for the Meridian catalog. Every morning it loads every "
        "row from `validation_tests`, runs each against live Supabase data, and "
        "writes pass/fail results back. The test suite covers 13 distinct "
        "test_types — drug overlap, stage, company attribution, catalog "
        "visibility, drug identity completeness, area membership consistency, "
        "intel attribution, source URL integrity, competitor edge existence, and "
        "more. A shared in-memory cache minimises database round-trips: most "
        "test types read from a handful of bulk-fetched table snapshots. "
        "The run exits with code 1 if any P1 tests fail — turning the Actions "
        "job red and making regressions impossible to miss."
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
        label="validate_ground_truth.py · main()\n(entrypoint — load, run, report, write)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    vt_in [
        label="Supabase\nvalidation_tests\n(all rows, or filtered by --area/--priority/--type)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_cache {
        label="Shared cache (lazy-loaded per test_type)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        drugs_cache [label="drugs_all\nstage · overlap · company_id\ndisplay_name · target · catalog_category"]
        company_cache [label="companies_all\nstatus · hq_country · parent_company_id"]
        area_cache [label="company_areas · drug_areas\ndrug_area_scores · company_profiles"]
        edge_cache [label="entity_edges (COMPETES_WITH)\ndrug_area_scores_all · drug_areas_all"]
        intel_cache [label="intel · intel_companies\nsource_verifications"]
    }

    subgraph cluster_run_test {
        label="run_test(): per validation_test row"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        dispatch [label="dispatch on test_type\n(13 types)"]
        evaluate [label="evaluate_operator()\neq/ne/contains/not_null\ngte/lte/not_contains/is_null"]
        verdict [label="pass / fail / skip / error"]
    }

    print_report [label="print_report()\ncolored pass/fail table\ngrouped by test_type"]

    vt_out [
        label="Supabase\nvalidation_tests\n(--write-results: PATCH last_pass_fail,\nlast_actual_value, consecutive_failures)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    stdout [
        label="stdout\ncolored report + P1 blocker list\nexit code 1 if P1 fails",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> vt_in [label="  load tests", style="bold", color="#c9890a", fontcolor="#c9890a"]
    vt_in -> dispatch
    dispatch -> drugs_cache [label="  lazy load\n  on first access", style="bold", color="#c9890a", fontcolor="#c9890a"]
    dispatch -> company_cache [style="bold", color="#c9890a", fontcolor="#c9890a"]
    dispatch -> area_cache [style="bold", color="#c9890a", fontcolor="#c9890a"]
    dispatch -> edge_cache [style="bold", color="#c9890a", fontcolor="#c9890a"]
    dispatch -> intel_cache [style="bold", color="#c9890a", fontcolor="#c9890a"]
    drugs_cache -> evaluate
    company_cache -> evaluate
    area_cache -> evaluate
    edge_cache -> evaluate
    intel_cache -> evaluate
    evaluate -> verdict
    verdict -> print_report
    verdict -> vt_out [label="  --write-results", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    print_report -> stdout
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

        vt_in [label="Supabase\nvalidation_tests\n(assertions to run)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        ref_in [label="Supabase\ndrugs · companies · company_areas · drug_areas\ndrug_area_scores · company_profiles · entity_edges\nintel · intel_companies · source_verifications", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Ground Truth\nValidation Tests",
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

        vt_out [label="Supabase\nvalidation_tests\n(last_pass_fail · last_actual_value\nconsecutive_failures · last_failure_at)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\ncolored report + exit code", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    vt_in -> pipeline
    ref_in -> pipeline
    pipeline -> vt_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "validation_tests",
                "kind": "Supabase table",
                "via": "main() → sb_get('validation_tests', params)",
                "desc": (
                    "Loads all validation test rows, ordered by "
                    "`priority.asc, test_type.asc, test_name.asc`. "
                    "Supports optional CLI filters: `--area` adds "
                    "`area_id=eq.<area>`, `--priority` adds "
                    "`priority=eq.<P>`, `--type` adds "
                    "`test_type=eq.<type>`. Each row carries "
                    "`test_type`, `entity_id`, `field_name`, "
                    "`expected_value`, `expected_operator`, `area_id`, "
                    "`priority`, and `test_name`."
                ),
                "scope": (
                    "One query, limit 1000. The full suite is ~1000 tests; "
                    "a typical area-filtered run is ~50-200."
                ),
            },
            {
                "name": "Reference tables (shared cache)",
                "kind": "Supabase tables",
                "via": "run_test() → sb_get() per cache key (lazy, once per key per run)",
                "desc": (
                    "Each test_type uses a subset of pre-fetched table "
                    "snapshots stored in a shared `cache` dict. Snapshots "
                    "are fetched on first access for each cache key and "
                    "reused for all subsequent tests of the same type. "
                    "Tables loaded: `drugs` (id/name/overlap/stage/"
                    "company_id/display_name/target/catalog_category), "
                    "`companies` (id/name/status/hq_country/"
                    "parent_company_id), `company_areas`, `drug_areas`, "
                    "`drug_area_scores`, `company_profiles`, "
                    "`entity_edges` (COMPETES_WITH active), `intel`, "
                    "`intel_companies`, `source_verifications`."
                ),
                "scope": (
                    "At most one bulk GET per cache key per run — the cache "
                    "prevents O(N) queries for N tests of the same type. "
                    "All table reads use limit=1000 via the `sb_get()` shim."
                ),
            },
        ],
        "cleaning": (
            "**The cache is the primary efficiency mechanism, not a data "
            "transformation.** `run_test()` does all comparisons in Python "
            "against the cached snapshots rather than issuing per-row queries. "
            "The `evaluate_operator()` function normalises both `actual` and "
            "`expected` to lowercase strings before `eq`/`ne`/`contains` "
            "comparisons — avoiding case-sensitivity false failures. "
            "`not_null` specifically rejects empty strings, 'null', and 'none' "
            "as well as Python `None`. Compound entity_ids in the form "
            "`drug_id:area_id` or `company_id:area_id` are split on `:` by "
            "the relevant test types. An unknown `test_type` returns `skip` "
            "rather than `error` so new test types can be added to the DB "
            "before the script handles them."
        ),
        "writes": [
            {
                "name": "validation_tests",
                "kind": "Supabase table",
                "via": "main() → sb_patch('validation_tests', payload, {'id': 'eq.<id>'})",
                "desc": (
                    "When `--write-results` is set, PATCHes four columns on "
                    "each test row: `last_checked_at` (UTC ISO), "
                    "`last_actual_value` (actual value from DB, ≤ 200 chars), "
                    "`last_pass_fail` (pass/fail/skip/error), and "
                    "`consecutive_failures` (incremented on fail, reset to 0 on "
                    "pass). Also sets `last_failure_at` on fail rows. "
                    "This is what makes the dashboard's validation history "
                    "panel possible."
                ),
                "scope": (
                    "One PATCH per test row in the run, only when "
                    "`--write-results` is set (always passed by the workflow). "
                    "A failed PATCH is logged but does not abort the run."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Supabase helper",
            "note": "Thin sb_get wrapper that enforces a limit=1000 floor.",
            "groups": [
                [
                    {
                        "function": "sb_get(table, params=None)",
                        "lines": 5,
                        "desc": (
                            "Merges `limit='1000'` into params (unless the "
                            "caller already set a higher limit) before calling "
                            "`_db.sb_get()`. Ensures bulk table reads don't "
                            "silently truncate at Supabase's default 100-row "
                            "limit."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Operator evaluation",
            "note": "evaluate_operator() is the comparison engine — handles all 8 operator types.",
            "groups": [
                [
                    {
                        "function": "evaluate_operator(actual, expected, operator)",
                        "lines": 25,
                        "desc": (
                            "Applies the declared operator to `actual` vs "
                            "`expected` (both strings). Operators: `eq` / `ne` "
                            "(case-insensitive string compare), `not_null` / "
                            "`is_null` (checks for empty/null/none), `contains` / "
                            "`not_contains` (substring), `gte` / `lte` (numeric "
                            "float cast). Returns False for unrecognised operators "
                            "or type-cast failures."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Test runner (13 test types)",
            "note": "run_test() dispatches to one of 13 test_type branches, all using the shared cache.",
            "groups": [
                [
                    {
                        "function": "run_test(test, cache)",
                        "lines": 362,
                        "desc": (
                            "Dispatches on `test['test_type']` to 13 branches. "
                            "Each branch lazy-loads its required table snapshots "
                            "into `cache` and calls `evaluate_operator()`. "
                            "Returns `(result, actual_value, error_msg)`. "
                            "Types: `overlap_check` (drug overlap vs drug_area_scores), "
                            "`company_visible` (company in area), `field_present` "
                            "(company_profile field), `drug_exists` / "
                            "`not_hallucinated` (drug presence), `stage_check`, "
                            "`company_check` (drug ownership or company field), "
                            "`display_name_check`, `catalog_visibility`, "
                            "`drug_area_interpretation_check` (E2: "
                            "drug_areas ↔ drug_area_scores consistency), "
                            "`drug_area_score_check` (E4: inverse of E2), "
                            "`drug_identity_check` (E5: core fields present), "
                            "`company_area_check` (E3: profile ↔ area), "
                            "`intel_attribution_check` (zero orphan intels), "
                            "`confidence_requires_source` (E6: confirmed scores "
                            "have source_url), `source_url_integrity` (E10: "
                            "no broken confirmed sources), "
                            "`competes_with_edge_exists` (E9: COMPETES_WITH edges)."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Report printing",
            "note": "print_report() formats the terminal output grouped by test_type.",
            "groups": [
                [
                    {
                        "function": "print_report(results, fail_only=False)",
                        "lines": 47,
                        "desc": (
                            "Groups results by `test_type`, sorts each group "
                            "with failures first. Prints a coloured header line "
                            "(passed / failed / skipped / total), a P1 blocker "
                            "alert or all-clear, then a per-type section with "
                            "per-row lines showing icon / priority / name / "
                            "expected / actual. `--fail-only` suppresses passing "
                            "rows. Returns `(failed_count, p1_fails)`."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main",
            "note": "main() loads tests, drives the run loop, prints the report, and optionally writes results.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 77,
                        "desc": (
                            "Parses `--area`, `--priority`, `--type`, "
                            "`--fail-only`, `--write-results`. Loads tests via "
                            "`sb_get('validation_tests', params)`. Runs each "
                            "test with a shared `cache={}` dict. Prints a "
                            "progress indicator (`✅`/`❌`/`⏭`) that overwrites "
                            "in place. Calls `print_report()`. If "
                            "`--write-results`, PATCHes each test row with its "
                            "result. Exits code 1 if any P1 tests failed."
                        ),
                    }
                ],
            ],
        },
    ],
}
