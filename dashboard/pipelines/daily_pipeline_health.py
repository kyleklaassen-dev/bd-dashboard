"""
Static description of the Pipeline Health Monitor pipeline
(.github/workflows/daily-pipeline-health.yml).

Polls the GitHub Actions API for every workflow's latest run, logs outcomes
to pipeline_runs, and stamps system_status.health_summary so the dashboard
can surface a live green/failing count. No LLM — pure API polling and SQL
writes.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "pipeline_health",
    "workflow_name": "Pipeline Health Monitor",
    "workflow_file": ".github/workflows/daily-pipeline-health.yml",
    "schedule": "Every 6 hours (00:15, 06:15, 12:15, 18:15 UTC) — 15-minute offset avoids contention with on-the-hour workflows",
    "entrypoint": "scripts/pipeline_health.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "The monitoring backbone of the Meridian platform. Every six hours it "
        "polls the GitHub Actions API for the latest run of every workflow in "
        "the repository, records each outcome to `pipeline_runs` (keyed by "
        "`run_id` so re-runs are idempotent), and stamps "
        "`system_status.health_summary` with a human-readable "
        "\"N green / M failing / K never-run\" string. One-shot migration and "
        "retired workflows are excluded from the failing count. "
        "Born from the Meridian Writer silent-failure incident: before this, "
        "a workflow could fail every day without anyone noticing."
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
        label="pipeline_health.py\n(entrypoint — args, poll, write, summarize)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    gh_api [
        label="GitHub Actions API\n/repos/{repo}/actions/workflows\n+ /workflows/{id}/runs",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_poll {
        label="latest_runs(): one pass per workflow"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        list_wfs [label="GET /actions/workflows\n(per_page=100)"]
        per_wf [label="GET /workflows/{id}/runs\n(per_page=1)\nfor each workflow"]
    }

    subgraph cluster_classify {
        label="main(): classify rows"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        ignored [label="_ignored()\nfilter migration + retired"]
        classify [label="split into:\nhealthy / failing / never-run"]
    }

    pipeline_runs [
        label="Supabase\npipeline_runs\n(upsert on run_id)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    system_status [
        label="Supabase\nsystem_status (id=1)\nlast_health_at + health_summary",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    stdout [
        label="stdout\nsummary + FAILING/NEVER-RUN lists",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> gh_api [label="  poll workflows", style="bold", color="#c9890a", fontcolor="#c9890a"]
    gh_api -> list_wfs
    list_wfs -> per_wf [label="  one GET per workflow"]
    per_wf -> ignored
    ignored -> classify
    classify -> pipeline_runs [label="  upsert_runs()", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    classify -> system_status [label="  stamp_health()", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    classify -> stdout [label="  always"]
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

        gh_in [label="GitHub Actions API\n/actions/workflows + /runs", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Pipeline\nHealth Monitor",
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

        runs_out [label="Supabase\npipeline_runs\n(upsert on run_id)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        status_out [label="Supabase\nsystem_status\nlast_health_at + health_summary", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nhealth summary + alerts", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    gh_in -> pipeline
    pipeline -> runs_out
    pipeline -> status_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "GitHub Actions API — workflow list + latest runs",
                "kind": "External API",
                "via": "latest_runs() → gh() → requests.get with GH_TOKEN",
                "desc": (
                    "`latest_runs()` first GETs "
                    "`/repos/{repo}/actions/workflows?per_page=100` to enumerate "
                    "every workflow file. For each, it GETs "
                    "`/workflows/{id}/runs?per_page=1` to retrieve only the single "
                    "most-recent run. The run record carries `status`, `conclusion`, "
                    "`run_started_at`, `html_url`, and the triggering `event`. "
                    "Workflows that have never run return an empty `workflow_runs` "
                    "list and are recorded as `status='never_run'`."
                ),
                "scope": (
                    "N+1 requests where N is the number of workflow files in the "
                    "repo (typically ~25). The `per_page=1` cap on the runs query "
                    "keeps response sizes small — only the latest run object is "
                    "needed. `GH_TOKEN` is the auto-provided Actions token "
                    "(`${{ secrets.GITHUB_TOKEN }}`), which has `actions:read` "
                    "scope. The `GITHUB_REPO` env var defaults to "
                    "`kyleklaassen-dev/bd-dashboard`."
                ),
            },
        ],
        "cleaning": (
            "**Two exclusion layers prevent false positives before the health "
            "summary is computed.** First, `_ignored(name)` filters out workflows "
            "by exact name (e.g. 'Apply SQL Migration', 'Evening Research Update "
            "(RETIRED)') and by a heuristic: any workflow whose `path` starts with "
            "`.github/workflows/` and whose name contains 'migration' "
            "(case-insensitive) is excluded — these are intentionally manual, "
            "one-shot workflows that are expected to be in a non-success state. "
            "Second, within `main()`, the failing bucket further excludes rows "
            "whose `conclusion` is `skipped`, `cancelled`, or `None` — a cancelled "
            "run is not a health failure. Only rows with a non-None, non-success "
            "conclusion on an active, non-ignored workflow count as 'failing'. "
            "The `upsert_runs()` write uses `on_conflict=run_id` with "
            "`resolution=merge-duplicates` so re-polling on the same run_id is "
            "always idempotent."
        ),
        "writes": [
            {
                "name": "pipeline_runs",
                "kind": "Supabase table",
                "via": "upsert_runs() → requests.post('pipeline_runs?on_conflict=run_id', ...)",
                "desc": (
                    "One row per workflow run, upserted on `run_id`. Each row "
                    "carries `workflow_name`, `workflow_id`, `run_id`, `status`, "
                    "`conclusion`, `event`, `run_started_at`, `run_html_url`, and "
                    "a computed `is_healthy` boolean. Workflows that have never "
                    "run (`run_id=None`) are excluded from this write — they "
                    "appear in the stdout summary but have no run to persist."
                ),
                "scope": (
                    "Bounded by the number of workflows with at least one run — "
                    "typically ~20-25 rows per poll. The upsert means each "
                    "`run_id` appears at most once in the table; if the same run "
                    "is polled again (e.g. while still in_progress), its row is "
                    "updated in place."
                ),
            },
            {
                "name": "system_status",
                "kind": "Supabase table (single row, id=1)",
                "via": "stamp_health() → requests.patch('system_status', params={'id': 'eq.1'}, ...)",
                "desc": (
                    "PATCHes four columns on the single `system_status` row: "
                    "`last_health_at` (UTC ISO timestamp), "
                    "`health_summary` (the 'N green / M failing / K never-run' "
                    "string, truncated to 500 chars), "
                    "`last_pipeline_label` ('health_monitor'), and `updated_at`. "
                    "This is what the dashboard reads to display its live "
                    "health indicator."
                ),
                "scope": (
                    "Exactly one PATCH per run, always to `id=1`. No insert — "
                    "the row is assumed to exist (created by the schema migration)."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Credential & API helpers",
            "note": "Module-level setup: credential loading and the thin GitHub API wrapper.",
            "groups": [
                [
                    {
                        "function": "_f(name)",
                        "lines": 3,
                        "desc": (
                            "Reads a credential from a workspace-root dot-file "
                            "(e.g. `.github_token`). Returns an empty string if "
                            "the file doesn't exist. Used as the fallback when "
                            "the environment variable is not set (local runs)."
                        ),
                    }
                ],
                [
                    {
                        "function": "gh(url, **params)",
                        "lines": 4,
                        "desc": (
                            "Thin wrapper around `requests.get` that injects "
                            "`Authorization: token {GH_TOKEN}` and "
                            "`Accept: application/vnd.github+json` headers, "
                            "raises on non-2xx, and returns the parsed JSON body. "
                            "Used by both the workflow-list and the per-workflow "
                            "runs calls inside `latest_runs()`."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "GitHub Actions poll",
            "note": "latest_runs() enumerates every workflow and fetches its most-recent run in an N+1 pattern.",
            "groups": [
                [
                    {
                        "function": "latest_runs()",
                        "lines": 21,
                        "desc": (
                            "Lists all workflow files via "
                            "`GET /actions/workflows?per_page=100`, then for "
                            "each workflow calls `GET /workflows/{id}/runs?"
                            "per_page=1`. For workflows with at least one run, "
                            "builds a result dict containing `workflow_name`, "
                            "`workflow_id`, `run_id`, `status`, `conclusion`, "
                            "`event`, `run_started_at`, `run_html_url`, and "
                            "`is_healthy` (True only when `conclusion == "
                            "'success'`). For workflows with zero runs, "
                            "synthesises a `status='never_run'` entry with "
                            "`is_healthy=False`."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Ignore-list filter",
            "note": "_ignored() separates one-shot / retired workflows from the active health signal.",
            "groups": [
                [
                    {
                        "function": "_ignored(name)",
                        "lines": 2,
                        "desc": (
                            "Returns True if the workflow name is in the "
                            "hardcoded `IGNORE` set (exact-match names like "
                            "'Apply SQL Migration') **or** if the name starts "
                            "with `.github/workflows/` and contains 'migration' "
                            "case-insensitively (path-based catch-all for future "
                            "migration YAMLs). Ignored workflows are polled and "
                            "recorded in `pipeline_runs` but are not counted "
                            "in the health summary buckets."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Supabase writes",
            "note": "Two write helpers called from main() after polling is complete.",
            "groups": [
                [
                    {
                        "function": "upsert_runs(rows)",
                        "lines": 10,
                        "desc": (
                            "Filters out rows with `run_id=None` (never-run "
                            "workflows have nothing to upsert), then POSTs the "
                            "remaining list to "
                            "`pipeline_runs?on_conflict=run_id` with "
                            "`resolution=merge-duplicates`. Logs the HTTP "
                            "status if the write fails (non-2xx)."
                        ),
                    }
                ],
                [
                    {
                        "function": "stamp_health(summary)",
                        "lines": 6,
                        "desc": (
                            "PATCHes `system_status` row `id=1` with the "
                            "current UTC timestamp (`last_health_at`), the "
                            "health summary string (truncated to 500 chars), "
                            "`last_pipeline_label='health_monitor'`, and "
                            "`updated_at`. This is the single write that "
                            "powers the dashboard's live health indicator."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main",
            "note": "Orchestrates poll → classify → write and handles the optional --fail-on-red exit code.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 33,
                        "desc": (
                            "Parses `--dry-run` and `--fail-on-red`. Calls "
                            "`latest_runs()`, filters to active workflows via "
                            "`_ignored()`, splits into `healthy`, `failing`, "
                            "and `never` buckets (with `failing` further "
                            "excluding `skipped`/`cancelled`/`None` conclusions). "
                            "Prints the summary and the FAILING/NEVER-RUN lists. "
                            "In non-dry-run mode, calls `upsert_runs()` and "
                            "`stamp_health()`. If `--fail-on-red` is set and "
                            "any active workflow is failing, exits with code 1 "
                            "(turns the health-monitor job itself red as an "
                            "alert) — but does not suppress the successful "
                            "data write."
                        ),
                    }
                ],
            ],
        },
    ],
}
