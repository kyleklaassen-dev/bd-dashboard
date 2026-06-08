"""
Static description of the Morning Summary pipeline
(.github/workflows/chain-06-morning-summary.yml).

Documents what the single entrypoint script does — querying four Supabase
tables to capture overnight activity (enrichment runs, field changes,
governance violations, validation alerts), formatting a plain-text summary,
writing it to meridian_overnight_summary.txt in the repo, and uploading it
as a GitHub Actions artifact.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "morning_summary",
    "workflow_name": "Morning Summary",
    "workflow_file": ".github/workflows/chain-06-morning-summary.yml",
    "schedule": (
        "Event-driven (after Meridian Writer succeeds) "
        "+ daily 11:00 UTC fallback (7 AM ET)"
    ),
    "entrypoint": "scripts/intelligence/morning_summary.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Generates a plain-text overnight digest immediately after the Writer "
        "publishes the daily Issue. Queries the last 12 hours of activity across "
        "four Supabase tables — enrichment runs, field-level changes, "
        "governance violations, and validation alerts — and formats them into a "
        "human-readable summary written to `meridian_overnight_summary.txt` "
        "in the repo root. The file is committed and pushed (using the write-capable "
        "deploy token) and uploaded as a 7-day GitHub Actions artifact so the "
        "summary is accessible from the Actions run page without a Supabase query."
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
        label="morning_summary.py\n(entrypoint — __main__)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    subgraph cluster_fetch {
        label="Four parallel Supabase reads (12-hour window)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        er   [label="fetch_enrichment_runs()\nenrichment_runs\n(started_at >=12h ago)"]
        fc   [label="fetch_field_changes()\nfield_change_audit\n(changed_at >=12h ago, limit 500)"]
        gv   [label="fetch_governance_violations()\ngovernance_violations\n(resolved=false, limit 50)"]
        va   [label="fetch_validation_alerts()\ndrug_validation_results\n(fail/warning, limit 100)"]
    }

    format_fn [label="format_summary()\nfour-section plain-text digest"]

    out_txt [
        label="meridian_overnight_summary.txt\n(repo root)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    artifact [
        label="GitHub Actions artifact\nmeridian-overnight-summary\n(7-day retention)",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> er [label="  reads", style="bold", color="#c9890a", fontcolor="#c9890a"]
    entry -> fc [label="  reads", style="bold", color="#c9890a", fontcolor="#c9890a"]
    entry -> gv [label="  reads", style="bold", color="#c9890a", fontcolor="#c9890a"]
    entry -> va [label="  reads", style="bold", color="#c9890a", fontcolor="#c9890a"]
    er -> format_fn
    fc -> format_fn
    gv -> format_fn
    va -> format_fn
    format_fn -> out_txt [label="  write", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    out_txt -> artifact [label="  upload-artifact@v4", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        sb_in [label="Supabase\nenrichment_runs · field_change_audit ·\ngovernance_violations · drug_validation_results", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Morning\nSummary",
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

        txt_out [label="meridian_overnight_summary.txt\n(repo root, committed + pushed)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        artifact_out [label="GitHub Actions artifact\nmeridian-overnight-summary\n(7-day retention)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    pipeline -> txt_out
    txt_out -> artifact_out
}
""",
    "io": {
        "reads": [
            {
                "name": "enrichment_runs",
                "kind": "Supabase table",
                "via": "fetch_enrichment_runs() → sb_get()",
                "desc": (
                    "Fetches all enrichment runs with `started_at >= NOW - 12h`, "
                    "ordered ascending. Each row includes `id`, `started_at`, "
                    "`completed_at`, `status`, `area_id`, `company_ids`, `drug_ids`, "
                    "`model_used`, and a `summary` dict containing `fields_updated`. "
                    "The summary section groups runs by status (completed / failed / "
                    "partial / still running) and lists the companies, drugs, and "
                    "field counts for each."
                ),
                "scope": "No row limit — all runs in the 12-hour window are returned.",
            },
            {
                "name": "field_change_audit",
                "kind": "Supabase table",
                "via": "fetch_field_changes() → sb_get()",
                "desc": (
                    "Fetches field-level changes from `changed_at >= NOW - 12h`, "
                    "ordered ascending, capped at 500. Groups by `(table_name, "
                    "entity_id)` and shows up to 10 field changes per entity, "
                    "including old value, new value, and the actor/source. "
                    "The 'WHAT CHANGED' section is capped at 40 entities in the "
                    "formatted output."
                ),
                "scope": "Capped at 500 rows.",
            },
            {
                "name": "governance_violations",
                "kind": "Supabase table",
                "via": "fetch_governance_violations() → sb_get()",
                "desc": (
                    "Fetches all unresolved violations (`resolved=false`), ordered "
                    "by `created_at DESC`, capped at 50. Shows table name, row id, "
                    "rule name, description (truncated to 120 chars), and detection "
                    "date in the 'GOVERNANCE FLAGS' section."
                ),
                "scope": "Capped at 50 rows (all unresolved, not time-windowed).",
            },
            {
                "name": "drug_validation_results",
                "kind": "Supabase table",
                "via": "fetch_validation_alerts() → sb_get()",
                "desc": (
                    "Fetches rows with `check_status IN (fail, warning)`, ordered "
                    "by `updated_at DESC`, capped at 100. Shows drug_id, status, "
                    "check_type, and notes in the 'VALIDATION ALERTS' section."
                ),
                "scope": "Capped at 100 rows.",
            },
        ],
        "cleaning": (
            "**All four reads are independent and run sequentially — a failure in "
            "one (e.g. a missing table) would raise and abort the script, but each "
            "fetch is a single call with no retry logic.** The `format_summary()` "
            "function applies display caps: 40 entities in the change section, "
            "30 validation alerts, 20 governance violations. These prevent the output "
            "file from growing unbounded on high-activity nights. All values are "
            "truncated to safe lengths (e.g. entity names to 80 chars, descriptions "
            "to 120 chars) before being written to the text file."
        ),
        "writes": [
            {
                "name": "meridian_overnight_summary.txt",
                "kind": "File (repo root)",
                "via": "open(out_path, 'w') + f.write(summary)",
                "desc": (
                    "A single plain-text file written to the repo root each run. "
                    "Overwrites the previous run's file — no versioning beyond the "
                    "GitHub commit history. The path is resolved relative to the "
                    "script's location so it always lands at the repo root regardless "
                    "of the working directory."
                ),
                "scope": "One file write per run.",
            },
            {
                "name": "GitHub Actions artifact (meridian-overnight-summary)",
                "kind": "CI artifact upload",
                "via": "actions/upload-artifact@v4 (workflow step, not the script)",
                "desc": (
                    "The text file is uploaded as a named artifact with 7-day "
                    "retention, making it downloadable from the Actions run page "
                    "without repo read access or a Supabase query."
                ),
                "scope": "One artifact upload per run (single file path).",
            },
        ],
    },
    "phases": [
        {
            "label": "Time window helper",
            "note": "Two tiny helpers that compute the lookback cutoff timestamp used by all four fetch functions.",
            "groups": [
                [
                    {
                        "function": "utc_now() / since_str(hours=WINDOW_HOURS)",
                        "lines": 7,
                        "desc": (
                            "`utc_now()` returns `datetime.datetime.utcnow()`. "
                            "`since_str(hours)` subtracts `hours` (default 12 — the "
                            "overnight window) from `utc_now()` and formats the result "
                            "as `YYYY-MM-DDTHH:MM:SSZ` — the cutoff value used in all "
                            "four `gte.{cutoff}` PostgREST filters."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Data fetchers",
            "note": "Four independent functions, each issuing one Supabase query for its section.",
            "groups": [
                [
                    {
                        "function": "fetch_enrichment_runs()",
                        "lines": 11,
                        "desc": (
                            "GETs `enrichment_runs` filtering `started_at >= cutoff`, "
                            "requesting id, started_at, completed_at, status, area_id, "
                            "company_ids, drug_ids, model_used, and the `summary` JSON "
                            "column. No row limit. Returns the raw list."
                        ),
                    }
                ],
                [
                    {
                        "function": "fetch_field_changes()",
                        "lines": 12,
                        "desc": (
                            "GETs `field_change_audit` filtering `changed_at >= cutoff`, "
                            "ordered ascending, limit 500. Requests table_name, entity_id, "
                            "entity_type, field_name, old_value, new_value, changed_at, "
                            "changed_by, change_source."
                        ),
                    }
                ],
                [
                    {
                        "function": "fetch_governance_violations()",
                        "lines": 11,
                        "desc": (
                            "GETs `governance_violations` filtering `resolved=false`, "
                            "ordered by `created_at DESC`, limit 50. Not time-windowed — "
                            "all open violations are surfaced regardless of age, so "
                            "chronic issues don't silently disappear from the digest."
                        ),
                    }
                ],
                [
                    {
                        "function": "fetch_validation_alerts()",
                        "lines": 12,
                        "desc": (
                            "GETs `drug_validation_results` filtering "
                            "`check_status IN (fail, warning)`, ordered by `updated_at "
                            "DESC`, limit 100. Not time-windowed — shows the current "
                            "open alert set."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Entity label resolver",
            "note": "Small helper used by format_summary() to build readable entity identifiers.",
            "groups": [
                [
                    {
                        "function": "_entity_label(row)",
                        "lines": 8,
                        "desc": (
                            "Extracts `entity_type` (or `table_name`) and `entity_id` "
                            "from a row dict and returns `'entity_type/entity_id'`. "
                            "Falls back to `'?'` for missing fields. Used in the "
                            "field-changes section to group changes under a readable "
                            "entity header."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Formatter",
            "note": "Assembles all four data sets into the plain-text digest.",
            "groups": [
                [
                    {
                        "function": "format_summary(runs, changes, violations, alerts, date_str)",
                        "lines": 107,
                        "desc": (
                            "Builds a list of lines in four sections: "
                            "(1) ENRICHMENT RUNS — groups by status, lists companies, "
                            "drugs, and fields_updated per run; "
                            "(2) WHAT CHANGED — groups field changes by entity, "
                            "shows old/new/by for each field, capped at 40 entities; "
                            "(3) VALIDATION ALERTS — lists fail/warning rows, "
                            "capped at 30; "
                            "(4) GOVERNANCE FLAGS — lists unresolved violations, "
                            "capped at 20. "
                            "Returns `'\\n'.join(lines)`."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main block",
            "note": "Drives the full run: fetch, format, write file, and print to stdout.",
            "groups": [
                [
                    {
                        "function": "__main__ block",
                        "lines": 34,
                        "desc": (
                            "Calls the four fetch functions, passes the results to "
                            "`format_summary()`, writes the output to "
                            "`<repo_root>/meridian_overnight_summary.txt`, and also "
                            "prints the summary to stdout (so it appears in the Actions "
                            "log). The workflow step then uploads the file as an artifact."
                        ),
                    }
                ],
            ],
        },
    ],
}
