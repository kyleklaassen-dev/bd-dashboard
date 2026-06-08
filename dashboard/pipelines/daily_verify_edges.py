"""
Static description of the Verify Competitor Edges pipeline
(.github/workflows/daily-verify-edges.yml).

Documents what verify_competitor_edges.py does: applying four SQL rules to
stamp entity_relationships rows as verified where the evidence is deterministic
(shared disease area, shared molecular target, real source URL, or
parent_company_id FK), moving the graph from 0% verified to ~88%+ on the
competitor layer. Idempotent — safe to schedule.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "verify_edges",
    "workflow_name": "Verify Competitor Edges",
    "workflow_file": ".github/workflows/daily-verify-edges.yml",
    "schedule": "Daily 11:00 UTC (7 AM ET) — after nightly scoring, before structural-edges at 7:30 AM ET",
    "entrypoint": "scripts/validation/verify_competitor_edges.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Rule-based edge verification that stamps `entity_relationships` rows as "
        "`verification_needed=false` where the evidence is a deterministic database "
        "fact — not an unverifiable guess. Four SQL rules are applied in sequence: "
        "(1) **Shared disease area** — `direct_competitor` edges whose two drug-drug "
        "endpoints share a confirmed `drug_areas` membership are verified (they "
        "demonstrably compete in that area); "
        "(2) **Shared molecular target** — edges of any competitive/analogous type "
        "whose drugs both appear in `drug_targets` with the same target are verified; "
        "(3) **Source URL** — edges carrying a real `http…` URL are source-verified; "
        "(4) **Parent company** — `parent_subsidiary` edges derivable from "
        "`companies.parent_company_id` are database-confirmed at `confidence='high'`. "
        "This took the `direct_competitor` layer from 0% verified to ~88% verified. "
        "Idempotent — rows already `verification_needed=false` are not touched. "
        "Runs via Supabase Management API SQL for efficiency."
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
        label="verify_competitor_edges.py\n(entrypoint - main)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    supabase_mgmt [
        label="Supabase Management API\n/v1/projects/{id}/database/query\n(SUPABASE_PAT required)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_rules {
        label="4 verification rules (UPDATE WHERE verification_needed=true)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        r1 [label="Rule 1: Shared disease area\ndirect_competitor edges where\nboth drugs share drug_areas\nconfidence='medium'"]
        r2 [label="Rule 2: Shared molecular target\ndirect_competitor + analogue +\ncombination + geographic edges\nwhere both drugs share drug_targets"]
        r3 [label="Rule 3: Source URL present\nAny edge with source_url LIKE 'http%'"]
        r4 [label="Rule 4: Parent company FK\nparent_subsidiary edges derivable\nfrom companies.parent_company_id\nconfidence='high'"]
    }

    er_out [
        label="Supabase\nentity_relationships\n(verification_needed=false\nconfidence + evidence stamped)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    stdout [
        label="stdout\nrule-verified counts per rule\ncompetitor verified %\noverall graph verified %",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> supabase_mgmt [label="  run(query) per rule", style="bold", color="#c9890a", fontcolor="#c9890a"]
    supabase_mgmt -> r1
    supabase_mgmt -> r2
    supabase_mgmt -> r3
    supabase_mgmt -> r4
    r1 -> er_out [label="  UPDATE RETURNING", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    r2 -> er_out [label="  UPDATE RETURNING", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    r3 -> er_out [label="  UPDATE RETURNING", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    r4 -> er_out [label="  UPDATE RETURNING", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    er_out -> stdout [label="  counts + %"]
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

        sb_in [label="Supabase (via Management API SQL)\nentity_relationships (verification_needed=true rows)\ndrug_areas . drug_targets . companies", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Verify\nCompetitor Edges",
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

        er_out [label="Supabase\nentity_relationships\n(verification_needed=false,\nconfidence, inference_method,\nevidence, notes updated)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nper-rule counts\ncompetitor + overall verified %", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    pipeline -> er_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "entity_relationships · drug_areas · drug_targets · companies (via SQL)",
                "kind": "Supabase tables — read via Management API SQL",
                "via": "main() → run(SQL|SQL_TARGET|SQL_SOURCED|SQL_PARENT) → POST Management API",
                "desc": (
                    "Four SQL UPDATE…FROM queries each join `entity_relationships` against "
                    "supporting tables to find verifiable rows: "
                    "**Rule 1 (SQL)**: joins `drug_areas` twice (self-join on `area_id`) to "
                    "find `direct_competitor` drug-drug edges where both endpoints share a "
                    "confirmed area. "
                    "**Rule 2 (SQL_TARGET)**: joins `drug_targets` twice (self-join on "
                    "`target_id`) to find edges of four relationship types where both drugs "
                    "share a confirmed molecular target. "
                    "**Rule 3 (SQL_SOURCED)**: reads `entity_relationships.source_url` "
                    "directly — no join needed, just a `LIKE 'http%'` filter. "
                    "**Rule 4 (SQL_PARENT)**: joins `companies` to check whether "
                    "`companies.parent_company_id` confirms the `parent_subsidiary` edge. "
                    "Each query only touches rows where `verification_needed=true` — "
                    "already-verified rows are never re-processed."
                ),
                "scope": (
                    "Four SQL round-trips via the Management API. No pagination. "
                    "On a fully-verified graph, all four UPDATE queries affect 0 rows — "
                    "the script becomes a read-only count run. After a bulk enrichment "
                    "that creates new unverified edges, can verify hundreds of rows in "
                    "seconds."
                ),
            },
        ],
        "cleaning": (
            "**All four rules are idempotent** — each UPDATE filters `verification_needed=true`, "
            "so rows already stamped verified are invisible to all subsequent runs. "
            "Evidence strings are array-appended rather than overwritten: "
            "`evidence = ARRAY['rule-verified: both compete in ' || areas]` — a fresh "
            "array is set on first verification; the row is never touched again. "
            "`notes` is appended with a bracketed tag "
            "(e.g. `[rule-verified: shared disease area]`) using "
            "`COALESCE(NULLIF(er.notes,''), '')` to avoid overwriting existing notes. "
            "**`--dry-run`** fires a COUNT query instead of the four UPDATEs — "
            "reports how many `direct_competitor` edges *would* be verified by Rule 1, "
            "without touching any rows."
        ),
        "writes": [
            {
                "name": "entity_relationships",
                "kind": "Supabase table",
                "via": "main() → run(SQL), run(SQL_TARGET), run(SQL_SOURCED), run(SQL_PARENT)",
                "desc": (
                    "Updates `verification_needed`, `confidence`, `inference_method`, "
                    "`evidence`, and `notes` on matching rows. "
                    "Rule 1 and 2 set `confidence='medium'` and `inference_method='rule_inferred'`. "
                    "Rule 3 sets `confidence='medium'` only (inference_method unchanged). "
                    "Rule 4 sets `confidence='high'` and `inference_method='database_join'`. "
                    "After all four rules, two COUNT queries log the competitor-layer "
                    "verified percentage and the overall graph verified percentage — "
                    "both read-only, no further writes."
                ),
                "scope": (
                    "Bounded by the number of `verification_needed=true` rows that match "
                    "each rule's join condition. On a stable graph with no new enrichment, "
                    "all four UPDATEs return 0 rows. After nightly enrichment adds new "
                    "competitor edges, this script verifies them the next morning."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Management API helper",
            "note": "One function wraps all Supabase Management API calls in the script.",
            "groups": [
                [
                    {
                        "function": "run(query)",
                        "lines": 9,
                        "desc": (
                            "Posts a raw SQL string to the Supabase Management API at "
                            "`https://api.supabase.com/v1/projects/{project}/database/query` "
                            "using `SUPABASE_PAT` for Bearer auth. Returns the parsed JSON "
                            "response — a list of row dicts for RETURNING queries, or a "
                            "count summary for SELECT COUNT queries. Uses `urllib.request` "
                            "directly (no third-party HTTP library)."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main — four verification rules",
            "note": "Applies rules in sequence, then logs coverage percentages.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 19,
                        "desc": (
                            "Checks `--dry-run` flag first: if set, runs a COUNT of "
                            "`direct_competitor` edges eligible for Rule 1 and returns 0 "
                            "without touching any rows. Otherwise executes the four UPDATE "
                            "queries in sequence (SQL → SQL_TARGET → SQL_SOURCED → SQL_PARENT), "
                            "collects the count of verified rows per rule into a dict "
                            "`{shared_area, shared_target, source_url, parent_company}`, "
                            "and prints the rule-verified counts. Then runs two SELECT "
                            "queries to print: (a) the `direct_competitor` verified "
                            "percentage (rows where `not verification_needed` / total), and "
                            "(b) the overall `entity_relationships` verified percentage. "
                            "Returns exit code 0."
                        ),
                    }
                ],
            ],
        },
    ],
}
