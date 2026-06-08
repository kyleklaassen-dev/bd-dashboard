"""
Static description of the Apply SQL Migration pipeline
(.github/workflows/manual-apply-migration.yml).

Documents what apply_sql_migration.py does when triggered manually — reading
any SQL file from the repo and executing it against Supabase via the
Management API. Same script used by weekly-audit-retention.yml.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "apply_migration",
    "workflow_name": "Apply SQL Migration",
    "workflow_file": ".github/workflows/manual-apply-migration.yml",
    "schedule": "Manual dispatch only — no cron schedule",
    "entrypoint": "scripts/build/apply_sql_migration.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Manual-only workflow for applying any SQL migration file to the Supabase "
        "database via the Management API. The caller supplies a `migration_file` "
        "path (relative to the repo root, e.g. `migrations/v99_add_column.sql`) and "
        "an optional `dry_run` boolean. The script reads the file from disk, prints "
        "the project reference, file path, and SQL body, then POSTs it to "
        "`/v1/projects/<ref>/database/query`. This is the canonical pattern for all "
        "forward migrations on the Meridian platform — new schema changes are written "
        "as SQL files in `migrations/`, then applied via this workflow rather than "
        "via the Supabase dashboard. The same `apply_sql_migration.py` script is "
        "reused by the weekly Audit Retention workflow with a fixed SQL path."
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

    dispatch [
        label="Manual workflow_dispatch\nmigration_file path + dry_run flag",
        fillcolor="#fde9c8",
        color="#d99a3b",
        fontcolor="#111827"
    ]

    entry [
        label="apply_sql_migration.py\n(entrypoint — main())",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    sql_file [
        label="<migration_file>\n(any .sql in repo — reads from disk)",
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

    db_result [
        label="Supabase\n(any table — migration-dependent)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    stdout [
        label="stdout\nproject ref + SQL text + response rows",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    dispatch -> entry
    entry -> sql_file [label="  open(migration_file).read()", style="bold", color="#c9890a", fontcolor="#c9890a"]
    sql_file -> entry
    entry -> mgmt_api [label="  POST {query: sql}\n  (unless --dry-run)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    mgmt_api -> db_result [label="  executes SQL"]
    mgmt_api -> entry [label="  response rows"]
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

        sql_in [label="<migration_file>\n(any SQL file in repo — dispatch input)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        env_in [label="SUPABASE_PAT + SUPABASE_URL\n(GitHub Actions secrets)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Apply SQL\nMigration",
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

        db_out [label="Supabase\n(any table — migration-dependent)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nproject ref + SQL + response", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
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
                "name": "<migration_file>",
                "kind": "Local file",
                "via": "open(sql_path).read() in main()",
                "desc": (
                    "The SQL file path provided as the first positional argument "
                    "(from `migration_file` workflow dispatch input). Can be any "
                    "`.sql` file in the repo — forward migrations in `migrations/`, "
                    "fix scripts, or DDL for new tables. The script reads the entire "
                    "file into a string and passes it as-is to the Management API."
                ),
                "scope": "One file read per invocation.",
            },
            {
                "name": "SUPABASE_URL · SUPABASE_PAT",
                "kind": "Environment variables",
                "via": "os.environ['SUPABASE_URL'] and os.environ['SUPABASE_PAT']",
                "desc": (
                    "`SUPABASE_URL` provides the project reference slug. "
                    "`SUPABASE_PAT` is the Personal Access Token for the Management API. "
                    "Both injected from GitHub Actions secrets. `SUPABASE_SERVICE_KEY` "
                    "is also available in the environment but not used by this script."
                ),
                "scope": "Read once at startup.",
            },
        ],
        "cleaning": (
            "**The script is intentionally dumb — it passes the SQL through verbatim.** "
            "There is no SQL parsing, validation, or transformation in Python. The "
            "Management API executes it in a single transaction; if the SQL raises a "
            "Postgres error, the HTTP response carries the error and the script prints "
            "it to stderr and exits 1. A `--dry-run` flag prints the SQL and project "
            "reference without making any API call, so you can verify the correct file "
            "is targeted before committing."
        ),
        "writes": [
            {
                "name": "(migration-dependent tables)",
                "kind": "Supabase (any table — determined by the SQL file)",
                "via": "Supabase Management API POST /v1/projects/<ref>/database/query",
                "desc": (
                    "The exact tables and rows affected depend entirely on the SQL file. "
                    "Forward migrations in `migrations/` typically CREATE TABLE, ADD "
                    "COLUMN, or CREATE INDEX. Fix scripts may UPDATE, DELETE, or backfill "
                    "data. The Management API executes the SQL with project-owner "
                    "privileges — there is no row-level restriction."
                ),
                "scope": (
                    "One SQL execution per dispatch. For migrations that are "
                    "`IF NOT EXISTS` or `ON CONFLICT DO NOTHING`, re-running is safe. "
                    "For destructive SQL (DROP, DELETE without WHERE), there is no "
                    "guard — review the file carefully before dispatching."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Entry point",
            "note": "Single function — same main() shared with the weekly-audit-retention workflow.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 51,
                        "desc": (
                            "Parses `sys.argv[1:]` for the SQL file path and `--dry-run`. "
                            "Reads `SUPABASE_URL` to extract the project reference. "
                            "Reads the SQL file. Prints the project ref, file path, and SQL. "
                            "If `--dry-run`, exits 0 without any API call. "
                            "Otherwise reads `SUPABASE_PAT`, builds a POST to "
                            "`https://api.supabase.com/v1/projects/<ref>/database/query` "
                            "with a browser-style User-Agent (required to bypass Cloudflare "
                            "from CI runners), and prints the response. "
                            "Returns exit code 0 on success, 1 on HTTP error."
                        ),
                    }
                ],
            ],
        },
    ],
}
