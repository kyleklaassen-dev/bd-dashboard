"""
Static description of the Meridian Audit Retention pipeline
(.github/workflows/weekly-audit-retention.yml).

Documents what apply_sql_migration.py does when called with the prune
migration file — calling fn_prune_field_change_audit(30) via the Supabase
Management API to delete non-governance, non-correction rows older than 30 days.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "audit_retention",
    "workflow_name": "Audit Retention",
    "workflow_file": ".github/workflows/weekly-audit-retention.yml",
    "schedule": "Sundays 08:00 UTC (4 AM ET) — weekly pruning before the BD sprint begins",
    "entrypoint": "scripts/build/apply_sql_migration.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Weekly maintenance job that keeps the `field_change_audit` table from "
        "growing unbounded. The table accumulates roughly 10,000 rows per day as "
        "enrichment and validation runs log every field change; without pruning, "
        "storage and query performance degrade steadily. This workflow calls "
        "`apply_sql_migration.py` with `migrations/prune_field_change_audit.sql`, "
        "which executes a single Postgres function `fn_prune_field_change_audit(30)` "
        "via the Supabase Management API. The function deletes rows older than 30 days "
        "**only** if they are not tagged as governance-relevant or corrections — those "
        "are kept indefinitely. The result is a hard bound on audit table size while "
        "preserving every row that matters for review or compliance."
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
        label="apply_sql_migration.py\n(entrypoint — args, print SQL, execute)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    sql_file [
        label="migrations/prune_field_change_audit.sql\n(reads from disk)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    mgmt_api [
        label="Supabase Management API\n/v1/projects/ref/database/query\n(POST — executes SQL)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_prune {
        label="Postgres — fn_prune_field_change_audit(30)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        prune_fn [label="DELETE FROM field_change_audit\nWHERE created_at older than 30 days\nAND NOT governance AND NOT correction\nRETURNS rows_pruned count"]
    }

    stdout [
        label="stdout\nproject ref + SQL text + rows_pruned count",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> sql_file [label="  open(sql_path).read()", style="bold", color="#c9890a", fontcolor="#c9890a"]
    sql_file -> entry
    entry -> mgmt_api [label="  POST {query: sql}", style="bold", color="#c9890a", fontcolor="#c9890a"]
    mgmt_api -> prune_fn [label="  executes"]
    prune_fn -> mgmt_api [label="  rows_pruned"]
    mgmt_api -> entry [label="  response body"]
    entry -> stdout [label="  prints result", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        sql_in [label="migrations/prune_field_change_audit.sql\n(disk — single SELECT fn call)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        env_in [label="SUPABASE_PAT + SUPABASE_URL\n(GitHub Actions secrets)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Audit\nRetention",
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

        db_out [label="Supabase\nfield_change_audit\n(rows deleted — non-governance, non-correction, >30 days)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nproject ref + SQL + rows_pruned", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sql_in -> pipeline
    env_in -> pipeline
    pipeline -> db_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "migrations/prune_field_change_audit.sql",
                "kind": "Local file",
                "via": "open(sql_path).read() in main()",
                "desc": (
                    "The entire SQL migration file is read from disk into a string. "
                    "The file contains a single statement: "
                    "`SELECT public.fn_prune_field_change_audit(30) AS rows_pruned;` "
                    "which delegates all retention logic to the Postgres function "
                    "already installed in the database. The script itself is generic — "
                    "it applies whatever SQL file is passed as its first argument."
                ),
                "scope": (
                    "One file read per invocation. The file path is taken from "
                    "`sys.argv[1]`, so the same `apply_sql_migration.py` script "
                    "is reused by other workflows (e.g. `manual-apply-migration.yml`) "
                    "with different SQL files."
                ),
            },
            {
                "name": "SUPABASE_URL · SUPABASE_PAT",
                "kind": "Environment variables",
                "via": "os.environ['SUPABASE_URL'] and os.environ['SUPABASE_PAT'] in main()",
                "desc": (
                    "`SUPABASE_URL` is parsed to extract the project reference slug "
                    "(everything between `https://` and `.supabase.co`). "
                    "`SUPABASE_PAT` is the Personal Access Token used to authorize "
                    "the Management API POST. Both are injected by GitHub Actions "
                    "from repository secrets."
                ),
                "scope": (
                    "Read once at startup. If `SUPABASE_URL` is missing the script "
                    "raises `KeyError` immediately. `SUPABASE_PAT` is only read if "
                    "`--dry-run` is not set."
                ),
            },
        ],
        "cleaning": (
            "**The retention filter lives entirely in the Postgres function, not in "
            "Python.** `fn_prune_field_change_audit(30)` contains the predicate that "
            "distinguishes purgeable rows (routine enrichment changes older than 30 days "
            "with no governance or correction tag) from rows that must be retained "
            "indefinitely (governance-flagged changes, analyst corrections). The Python "
            "script is intentionally dumb — it passes the SQL through verbatim, prints "
            "the returned `rows_pruned` count, and exits. A `--dry-run` flag prints the "
            "SQL and exits before the Management API call, so you can verify the file "
            "contents without touching the database."
        ),
        "writes": [
            {
                "name": "field_change_audit",
                "kind": "Supabase table (rows deleted)",
                "via": "Supabase Management API POST /v1/projects/<ref>/database/query",
                "desc": (
                    "Rows matching the retention predicate are deleted inside "
                    "`fn_prune_field_change_audit(30)`. Specifically: rows where "
                    "`created_at < NOW() - INTERVAL '30 days'` AND the row is not "
                    "tagged as governance-relevant or a correction. The function "
                    "returns the count of deleted rows as `rows_pruned`, which the "
                    "script prints to stdout."
                ),
                "scope": (
                    "At steady state (~10k rows/day), a typical weekly run prunes "
                    "roughly 40-70k rows (rows older than 30 days that are not "
                    "governance/correction). The function is idempotent: running "
                    "twice in the same window deletes 0 rows the second time."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Entry point and argument parsing",
            "note": "Single function; the entire script is one main() with no helpers.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 51,
                        "desc": (
                            "Parses `sys.argv[1:]` for the SQL file path and an optional "
                            "`--dry-run` flag. Reads the SQL file from disk. Extracts the "
                            "Supabase project reference from `SUPABASE_URL`. Prints the "
                            "project ref, the migration file path, and the full SQL body. "
                            "If `--dry-run`, prints 'DRY RUN — not executing' and exits 0. "
                            "Otherwise reads `SUPABASE_PAT`, builds a POST request to "
                            "`https://api.supabase.com/v1/projects/<ref>/database/query` "
                            "with the SQL as JSON body, sends it with a browser-style "
                            "User-Agent (required to bypass Cloudflare on the Management "
                            "API from CI runners), and prints the response rows (the "
                            "`rows_pruned` count returned by the Postgres function). "
                            "Returns exit code 0 on success or 1 on HTTP error."
                        ),
                    }
                ],
            ],
        },
    ],
}
