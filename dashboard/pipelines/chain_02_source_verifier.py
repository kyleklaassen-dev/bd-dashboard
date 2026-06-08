"""
Static description of the Source Verifier pipeline
(.github/workflows/chain-02-source-verifier.yml).

Documents what the single entrypoint script does — collecting every stored
source_url across the catalog, running five validation checks per URL, writing
results to source_validation_log, flagging bad citations in enriched_field_log,
and opening governance_violations for deals and partnerships with null or
fabricated sources.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "source_verifier",
    "workflow_name": "Source Verifier",
    "workflow_file": ".github/workflows/chain-02-source-verifier.yml",
    "schedule": (
        "Event-driven (after Meridian Research succeeds, --new-only mode) "
        "+ Mon/Thu 08:00 UTC fallback full sweep"
    ),
    "entrypoint": "scripts/validation/source_verifier.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Tier-3 trust layer: every `source_url` stored across the catalog "
        "(drugs, companies, deals, partnerships, catalysts, catalyst_calendar, "
        "drug_sources, entity_relationships, enriched_field_log, "
        "drug_validation_results) is collected and put through a five-step "
        "validation gauntlet — format check, fabrication-pattern detection, "
        "domain trust check, generic-URL flagging, and a live HTTP HEAD. "
        "Results land in `source_validation_log`; bad citations in "
        "`enriched_field_log` get their `field_label` stamped `source_invalid`; "
        "deals and partnerships with null or invalid sources generate "
        "`governance_violations`. "
        "Born from the veligrotug incident where a fabricated catalyst URL survived "
        "undetected for weeks — this is the immune layer that catches that class of "
        "error before the Writer builds an Issue on top of it."
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
        label="source_verifier.py\n(entrypoint — run())",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    subgraph cluster_in {
        label="10 source tables (source_url fields)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        supabase_in [
            label="Supabase\ndrugs · companies · deals ·\ncompany_partnerships · catalysts ·\ncatalyst_calendar · drug_sources ·\nentity_relationships ·\nenriched_field_log · drug_validation_results",
            shape=cylinder,
            fillcolor="#ffe4b8",
            color="#c9890a",
            fontcolor="#111827",
            fontsize=10,
            margin="0.22,0.14"
        ]
    }

    subgraph cluster_collect {
        label="Step 2 — collect_urls(): gather all source_url values"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        collect [label="collect_urls()\n10 × sb_get (+ 3 conditional checks)"]
        newonly [label="--new-only filter\n(skip URLs checked in last 6d)"]
    }

    subgraph cluster_validate {
        label="Step 3 — run_validation(): per-URL five-step gauntlet"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        fmt  [label="is_valid_format()\nbasic URL format"]
        fab  [label="is_fabricated()\nknown-bad patterns"]
        dom  [label="is_trusted_domain()\ndomain allowlist"]
        gen  [label="is_generic()\npipeline/homepage URLs"]
        live [label="check_url_live()\nHTTP HEAD (+ GET fallback)"]
    }

    http_ext [
        label="External HTTP\n(one HEAD per URL)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    subgraph cluster_post {
        label="Steps 4-5 — post-validation actions"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        flag_efl  [label="flag_invalid_in_enriched_field_log()\nstamp field_label='source_invalid'"]
        gov_null  [label="create_governance_violations_for_null_sources()\ndeals + partnerships without source_url"]
    }

    svlog [
        label="Supabase\nsource_validation_log\n(upsert per URL, per batch)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    efl_out [
        label="Supabase\nenriched_field_log\n(field_label='source_invalid')",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    gov_out [
        label="Supabase\ngovernance_violations\n(deals + partnerships\nwith null source_url)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    trigger_out [
        label="Triggers on success:\nchain-03 Content Verifier",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> supabase_in [label="  reads", style="bold", color="#c9890a", fontcolor="#c9890a"]
    supabase_in -> collect
    collect -> newonly [label="  if --new-only"]
    newonly -> fmt
    collect -> fmt [label="  (full sweep)"]
    fmt -> fab -> dom -> gen -> live
    live -> http_ext [label="  HEAD request", style="bold", color="#c9890a", fontcolor="#c9890a"]
    live -> svlog [label="  upsert per batch", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    live -> flag_efl [label="  invalid records"]
    live -> gov_null
    flag_efl -> efl_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    gov_null -> gov_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        sb_in [label="Supabase\n10 tables with source_url fields", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        http_in [label="External HTTP\n(HEAD per URL, 0.5s throttle)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Source\nVerifier",
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

        svlog_out [label="Supabase\nsource_validation_log\n(one row per URL checked)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        efl_out [label="Supabase\nenriched_field_log\n(field_label='source_invalid')", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        gov_out [label="Supabase\ngovernance_violations\n(null-source deals + partnerships)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        trigger_out [label="Triggers\nchain-03 Content Verifier", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    http_in -> pipeline
    pipeline -> svlog_out
    pipeline -> efl_out
    pipeline -> gov_out
    pipeline -> trigger_out
}
""",
    "io": {
        "reads": [
            {
                "name": (
                    "drugs · companies · deals · company_partnerships · catalysts · "
                    "catalyst_calendar · drug_sources · entity_relationships · "
                    "enriched_field_log · drug_validation_results"
                ),
                "kind": "Supabase tables",
                "via": "collect_urls() — up to 10 sb_get calls, filtered to rows with source_url not null",
                "desc": (
                    "Every table in the catalog that can carry a `source_url` (or "
                    "`source_citation` in `enriched_field_log`) is scanned. Each row with "
                    "a non-null URL becomes a `{table_name, entity_id, field_name, "
                    "source_url}` record in the worklist. Three tables "
                    "(`entity_relationships`, `enriched_field_log`, "
                    "`drug_validation_results`) are gated behind `table_exists()` checks "
                    "so the script degrades gracefully if a table is missing."
                ),
                "scope": (
                    "Up to 500 rows per table (PostgREST default limit). The "
                    "`--new-only` flag (used by the nightly event-driven run) further "
                    "filters by cross-referencing `source_validation_log` for URLs "
                    "already checked in the last 6 days — so the chain-02 nightly pass "
                    "only touches what's genuinely new from the Research run."
                ),
            },
            {
                "name": "External HTTP endpoints",
                "kind": "External HTTP",
                "via": "check_url_live() — urllib.request HEAD (+ GET fallback for 405/501)",
                "desc": (
                    "For each URL that passes the format, fabrication, and generic checks, "
                    "`check_url_live()` issues an HTTP HEAD with a 10-second timeout and "
                    "Meridian's User-Agent. If the server returns 405 or 501 (doesn't "
                    "support HEAD), it falls back to a streaming GET. A status code "
                    "below 400 is considered live."
                ),
                "scope": (
                    "One request per URL, batched in groups of 20 with a 0.5-second "
                    "sleep between batches to avoid hammering individual domains. "
                    "The `--limit` flag caps the total number of URLs validated per run."
                ),
            },
        ],
        "cleaning": (
            "**Five validation stages run in order; the first failure short-circuits "
            "the rest.** `is_valid_format()` rejects blank values and non-HTTP strings "
            "immediately — no network call. `is_fabricated()` tests against 13 regex "
            "patterns (search pages, example.com, CT.gov search, etc.) — caught here, "
            "no HTTP call. `is_trusted_domain()` checks the domain allowlist (IR "
            "subdomains, .gov/.edu, known pharma/biotech) and records the result but "
            "does NOT short-circuit (an untrusted domain is still checked live). "
            "`is_generic()` catches bare homepage / pipeline-page URLs that are "
            "technically live but too vague to support a claim — marks valid but "
            "`error_message='generic_url_low_confidence'`, no HTTP call. Only URLs "
            "that pass all four static checks get an actual HTTP HEAD. "
            "The `source_validation_log` upsert key is "
            "`(table_name, entity_id, field_name, source_url)`, so re-running on an "
            "already-logged URL overwrites the existing row rather than creating a "
            "duplicate."
        ),
        "writes": [
            {
                "name": "source_validation_log",
                "kind": "Supabase table",
                "via": "run_validation() → sb_upsert() per batch of 20",
                "desc": (
                    "One row per URL checked: `table_name`, `entity_id`, `field_name`, "
                    "`source_url`, `is_valid`, `http_status_code`, `error_message`, "
                    "`domain_trusted`, `validated_at`, `validation_run_id`. Written "
                    "in batches of 20 as validation proceeds — partial results are "
                    "preserved even if the run fails mid-batch."
                ),
                "scope": (
                    "Bounded by the number of non-null source_url values in the catalog "
                    "(full sweep) or the number of URLs new since the last run "
                    "(--new-only). Upsert key deduplicates on the full (table, entity, "
                    "field, url) composite."
                ),
            },
            {
                "name": "enriched_field_log",
                "kind": "Supabase table",
                "via": "flag_invalid_in_enriched_field_log() → sb_patch()",
                "desc": (
                    "For `enriched_field_log` rows whose `source_citation` URL was "
                    "found invalid, `field_label` is patched to `'source_invalid'`. "
                    "This lets the enrichment pipeline's review queue surface bad "
                    "citations without a separate query."
                ),
                "scope": (
                    "Only runs when there are invalid records and `--dry-run` is not set. "
                    "One PATCH per invalid enriched_field_log row."
                ),
            },
            {
                "name": "governance_violations",
                "kind": "Supabase table",
                "via": "create_governance_violations_for_null_sources() → sb_post()",
                "desc": (
                    "Opens one violation per deal or company_partnership row with a "
                    "null `source_url` (governance rule 5: every deal and partnership "
                    "requires a source). `rule_name` is either "
                    "`deal_missing_source_url` or `partnership_missing_source_url`."
                ),
                "scope": (
                    "Up to 100 deals + 100 partnerships scanned per run. Does not "
                    "deduplicate — re-running on the same null-source record creates "
                    "another violation row. Use `--dry-run` to audit without opening "
                    "duplicate violations."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Supabase helpers",
            "note": "Thin wrappers around raw requests. DRY_RUN is a module-level flag that gates all writes.",
            "groups": [
                [
                    {
                        "function": "sb_get(table, params) / sb_post / sb_patch / sb_upsert",
                        "lines": 44,
                        "desc": (
                            "Four raw-requests wrappers. Each write method checks the "
                            "module-level `DRY_RUN` flag first and logs the suppressed "
                            "call instead of executing it. `sb_upsert` uses the "
                            "`resolution=merge-duplicates` Prefer header so re-inserting "
                            "an existing row updates it rather than erroring."
                        ),
                    }
                ],
                [
                    {
                        "function": "table_exists(table_name)",
                        "lines": 12,
                        "desc": (
                            "Issues a `GET /rest/v1/<table>?limit=0` and returns True "
                            "on any 2xx or 3xx response. Used to gate the three optional "
                            "table reads (`entity_relationships`, `enriched_field_log`, "
                            "`drug_validation_results`) so the script runs cleanly on "
                            "environments where those tables haven't been migrated yet."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Schema migrations",
            "note": "Applied once at the start of each run (Step 1) to ensure the source_validation_log table exists.",
            "groups": [
                [
                    {
                        "function": "apply_migrations()",
                        "lines": 92,
                        "desc": (
                            "Checks whether `source_validation_log` exists and creates "
                            "it with the full schema if missing. Also adds any new "
                            "columns introduced in later runs (e.g. `domain_trusted`, "
                            "`validation_run_id`). Uses the `SUPABASE_PAT` Management "
                            "API token if available; falls back to `sb_post` DDL "
                            "otherwise. Skipped entirely when `--dry-run` is set."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "URL collection",
            "note": "Step 2: gathers every source_url value from the catalog into a flat worklist.",
            "groups": [
                [
                    {
                        "function": "collect_urls()",
                        "lines": 103,
                        "desc": (
                            "Iterates a `TABLE_SPECS` list of `(table_name, id_field, "
                            "url_field)` tuples for 7 core tables, appending "
                            "`{table_name, entity_id, field_name, source_url}` records "
                            "for every non-null URL. Then conditionally queries "
                            "`entity_relationships`, `enriched_field_log` (the "
                            "`source_citation` field specifically), and "
                            "`drug_validation_results` — guarded by `table_exists()` so "
                            "absent tables are silently skipped. Returns the full flat "
                            "list; the `run()` function applies any `--new-only` or "
                            "`--table`/`--limit` filters after this call."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Validation checks",
            "note": "Four static checks run before any HTTP request is made. Each can short-circuit the per-URL pipeline.",
            "groups": [
                [
                    {
                        "function": "is_valid_format(url)",
                        "lines": 12,
                        "desc": (
                            "Rejects blank, non-string, and non-HTTP values. Parses the "
                            "URL with `urlparse` and requires both `scheme` and a "
                            "non-trivial `netloc`. Failure here means no further checks "
                            "are run for this URL."
                        ),
                    }
                ],
                [
                    {
                        "function": "is_fabricated(url)",
                        "lines": 7,
                        "desc": (
                            "Tests against 13 regex patterns known to indicate fabricated "
                            "URLs: search-result pages (`/search?q=`, "
                            "`google.com/search`), CT.gov search pages, "
                            "`example.com`, `placeholder.`, etc. A match here marks the "
                            "URL `fabricated_url_pattern` with no HTTP call."
                        ),
                    }
                ],
                [
                    {
                        "function": "is_trusted_domain(url)",
                        "lines": 28,
                        "desc": (
                            "Checks the domain against a hardcoded allowlist, IR/investor "
                            "subdomain patterns (`ir.*`, `investors.*`, `news.*`), "
                            "`.gov`/`.edu` TLDs, and a named pharma/biotech domain list. "
                            "Records the boolean `domain_trusted` in the log row but does "
                            "not short-circuit — an untrusted domain is still checked live."
                        ),
                    }
                ],
                [
                    {
                        "function": "is_generic(url)",
                        "lines": 7,
                        "desc": (
                            "Matches bare homepage URLs and common pipeline/product/research "
                            "path patterns (`/pipeline/?$`, `/programs/?$`, bare domain "
                            "root). Marks valid with "
                            "`error_message='generic_url_low_confidence'` and returns — "
                            "the URL is real but too vague to support a specific claim."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Live HTTP check",
            "note": "The network call — only runs for URLs that pass all four static checks.",
            "groups": [
                [
                    {
                        "function": "check_url_live(url, timeout=10)",
                        "lines": 26,
                        "desc": (
                            "Issues `HEAD` with Meridian's User-Agent and a 10-second "
                            "timeout, following redirects. If the server returns 405 or "
                            "501 (HEAD not supported), retries with a streaming `GET`. "
                            "Returns `(is_live, status_code, error_message)`. "
                            "Timeout, SSL errors, and connection errors are caught "
                            "individually and returned as descriptive error strings so "
                            "the log row is informative rather than raising."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Validation runner",
            "note": "Iterates the worklist in batches, accumulates results, and writes source_validation_log.",
            "groups": [
                [
                    {
                        "function": "validate_url_record(record)",
                        "lines": 44,
                        "desc": (
                            "Runs the five-stage pipeline (format → fabricated → domain → "
                            "generic → live) on a single URL record. Returns the record "
                            "enriched with `is_valid`, `http_status_code`, `error_message`, "
                            "`domain_trusted`, `validated_at`, and `validation_run_id`."
                        ),
                    }
                ],
                [
                    {
                        "function": "run_validation(url_records, batch_size=20)",
                        "lines": 78,
                        "desc": (
                            "Iterates `url_records` in batches of `batch_size`. For each "
                            "record calls `validate_url_record()`, categorizes the result "
                            "into valid/invalid/generic/fabricated/format_error/timeout "
                            "buckets, builds the `source_validation_log` row, and upserts "
                            "the batch at the end of each batch (0.5s sleep between "
                            "batches). Returns a stats dict consumed by `run()`."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Post-validation actions",
            "note": "Steps 4 and 5: downstream effects for invalid and null-source records.",
            "groups": [
                [
                    {
                        "function": "flag_invalid_in_enriched_field_log(invalid_records)",
                        "lines": 16,
                        "desc": (
                            "Filters `invalid_records` to those from `enriched_field_log` "
                            "and PATCHes each matching row's `field_label` to "
                            "`'source_invalid'`. This surfaces bad citations in the "
                            "enrichment review queue without a separate governance query."
                        ),
                    }
                ],
                [
                    {
                        "function": "create_governance_violations_for_null_sources()",
                        "lines": 69,
                        "desc": (
                            "Queries `deals` and `company_partnerships` for rows with "
                            "`source_url IS NULL` (up to 100 each) and POSTs a "
                            "`governance_violations` row for each with "
                            "`rule_name='deal_missing_source_url'` or "
                            "`'partnership_missing_source_url'`. Enforces governance "
                            "rule 5: every deal and partnership requires a source URL."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main entry point",
            "note": "run() owns argument parsing, the new-only filter, table/limit overrides, and the five-step orchestration.",
            "groups": [
                [
                    {
                        "function": "run(dry_run, target_table, limit, new_only, fresh_days=6)",
                        "lines": 87,
                        "desc": (
                            "Sets the module-level `DRY_RUN` flag, then runs the five "
                            "steps in order: (1) apply DDL migrations, (2) collect URLs, "
                            "(3) apply new-only / table / limit filters, "
                            "(4) run validation + write `source_validation_log`, "
                            "(5) flag invalid `enriched_field_log` entries, "
                            "(6) create `governance_violations` for null-source records. "
                            "Prints a summary of counts at the end. The CLI "
                            "`if __name__ == '__main__'` block parses `--dry-run`, "
                            "`--table`, `--limit`, and `--new-only` and calls `run()`."
                        ),
                    }
                ],
            ],
        },
    ],
}
