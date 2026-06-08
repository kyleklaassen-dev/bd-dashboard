"""
Static description of the Materialize Structural Edges pipeline
(.github/workflows/daily-structural-edges.yml).

Documents what materialize_structural_edges.py does: inserting the three
structural edge predicates (TREATS, ADDRESSES, DEVELOPED_BY) that make the
entity graph traversable from patient through indication, target, drug, and
company. Idempotent — safe to schedule or re-run.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "structural_edges",
    "workflow_name": "Materialize Structural Edges",
    "workflow_file": ".github/workflows/daily-structural-edges.yml",
    "schedule": "Daily 11:30 UTC (7:30 AM ET) — runs 30 min after verify-edges, after the nightly scoring window",
    "entrypoint": "scripts/graph/materialize_structural_edges.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Idempotent graph maintenance job that materializes the structural backbone "
        "of the entity graph into `entity_edges`. The normalized tables (`drug_indications`, "
        "`drug_targets`, `drugs.company_id`) remain the source of truth; this script "
        "derives three edge predicates from them and inserts only the missing ones: "
        "**TREATS** (drug → indication, from `drug_indications`), "
        "**ADDRESSES** (target → indication, derived: if a drug targets T and treats I, "
        "then T addresses I), and "
        "**DEVELOPED_BY** (drug → company, from `drugs.company_id`). "
        "These three predicates make the patient → indication → target → drug → company "
        "traversal chain possible in the graph layer. Runs via the Supabase Management "
        "API (requires `SUPABASE_PAT`) rather than PostgREST — SQL INSERT…WHERE NOT EXISTS "
        "queries are more efficient than a read-compute-write loop in Python."
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
        label="materialize_structural_edges.py\n(entrypoint - main)",
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

    subgraph cluster_source {
        label="Source tables (read via SQL)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        drug_indications [label="drug_indications\n(drug_id -> indication_id)"]
        drug_targets [label="drug_targets\n(drug_id -> target_id)"]
        drugs_co [label="drugs.company_id\n(drug_id -> company)"]
    }

    subgraph cluster_edges {
        label="Edges materialized (INSERT WHERE NOT EXISTS)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        treats [label="TREATS\ndrug -> indication\nconfidence: confirmed"]
        addresses [label="ADDRESSES\ntarget -> indication\n(derived from TREATS + drug_targets)\nconfidence: inferred"]
        developed_by [label="DEVELOPED_BY\ndrug -> company\nconfidence: confirmed"]
    }

    entity_edges_out [
        label="Supabase\nentity_edges\n(new TREATS + ADDRESSES\n+ DEVELOPED_BY rows inserted)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    stdout [
        label="stdout\nnew edge counts per predicate\n+ overall predicate summary",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> supabase_mgmt [label="  run(query) - POST SQL", style="bold", color="#c9890a", fontcolor="#c9890a"]
    supabase_mgmt -> drug_indications [label="  TREATS SQL reads"]
    supabase_mgmt -> drug_targets [label="  ADDRESSES SQL reads"]
    supabase_mgmt -> drugs_co [label="  DEVELOPED_BY SQL reads"]
    drug_indications -> treats
    drug_targets -> addresses
    drug_indications -> addresses [label="  joined"]
    drugs_co -> developed_by
    treats -> entity_edges_out [label="  INSERT RETURNING", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    addresses -> entity_edges_out [label="  INSERT RETURNING", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    developed_by -> entity_edges_out [label="  INSERT RETURNING", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    entity_edges_out -> stdout [label="  counts per predicate"]
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

        sb_in [label="Supabase (via Management API SQL)\ndrug_indications . drug_targets\ndrugs (company_id)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Materialize\nStructural Edges",
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

        edges_out [label="Supabase\nentity_edges\n(TREATS + ADDRESSES + DEVELOPED_BY\nnew rows only)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nedge counts + predicate summary", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    pipeline -> edges_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "drug_indications · drug_targets · drugs (via SQL)",
                "kind": "Supabase tables — read via Management API SQL",
                "via": "main() → run(query) → POST /v1/projects/{project}/database/query",
                "desc": (
                    "The three INSERT queries each join source tables to derive edges. "
                    "**TREATS**: joins `drug_indications` with `drugs` (filtering "
                    "`dashboard_visible=true` and `record_type='drug'`) — one TREATS edge "
                    "per (drug, indication) pair. "
                    "**ADDRESSES**: joins `drug_targets` with `drug_indications` and `drugs` — "
                    "one ADDRESSES edge per (target, indication) pair derivable from any "
                    "drug that targets T and has an indication I. "
                    "**DEVELOPED_BY**: reads `drugs.company_id` directly — one DEVELOPED_BY "
                    "edge per drug with a non-null company_id. "
                    "All three queries filter `dashboard_visible=true` and "
                    "`record_type='drug'` to avoid creating edges for internal/test records."
                ),
                "scope": (
                    "Each query is a single SQL round-trip via the Supabase Management API. "
                    "No pagination — the SQL engine handles all joins server-side. "
                    "Requires `SUPABASE_PAT` (management API token); the workflow passes "
                    "this as a secret."
                ),
            },
        ],
        "cleaning": (
            "**The script is idempotent by design — INSERT WHERE NOT EXISTS on every "
            "predicate.** Each SQL query includes a `NOT EXISTS` subquery that checks "
            "whether the `(subject_id, predicate, object_id)` triple already exists in "
            "`entity_edges` before inserting. Re-running the script on an already-current "
            "graph is a no-op — zero new rows are inserted and no existing rows are "
            "modified. The `RETURNING id` clause is used purely to count new insertions "
            "for the log — the returned IDs are not used for further processing. "
            "`--dry-run` flag skips all three SQL queries and prints a single "
            "informational message, making it safe to test connectivity without touching "
            "the graph."
        ),
        "writes": [
            {
                "name": "entity_edges",
                "kind": "Supabase table",
                "via": "main() → run(EDGES['TREATS'|'ADDRESSES'|'DEVELOPED_BY'])",
                "desc": (
                    "Inserts missing structural edges only — never updates or deletes. "
                    "Each inserted row carries: `subject_type`, `subject_id`, `predicate`, "
                    "`object_type`, `object_id`, `generation_method` ('deterministic'), "
                    "`confidence_level` ('confirmed' for TREATS/DEVELOPED_BY, 'inferred' "
                    "for ADDRESSES), `status` ('active'), `rationale` (describes derivation "
                    "logic), and `created_at`/`updated_at` timestamps. "
                    "After all three predicates, logs the active-edge counts per predicate "
                    "with a final summary SELECT."
                ),
                "scope": (
                    "On a fully-materialized graph, all three queries return 0 new rows — "
                    "the script becomes a pure read + count. On a new catalog import or "
                    "after a bulk drug_indications/drug_targets seed, can insert hundreds "
                    "of new edges in one run."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Management API helper",
            "note": "One function wraps the raw Supabase Management API call used for all SQL queries.",
            "groups": [
                [
                    {
                        "function": "run(query)",
                        "lines": 8,
                        "desc": (
                            "Posts a raw SQL query to "
                            "`https://api.supabase.com/v1/projects/{project}/database/query` "
                            "using the `SUPABASE_PAT` for Bearer authorization. "
                            "Sends `Content-Type: application/json` with a JSON body "
                            "`{query: sql}`. Returns the parsed JSON response (a list of "
                            "row dicts for SELECT/RETURNING queries). Uses `urllib.request` "
                            "directly (no third-party HTTP library) to minimise dependencies."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main — edge materialization loop",
            "note": "Iterates the three predicate SQL queries in sequence and logs counts.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 8,
                        "desc": (
                            "Checks `--dry-run` flag (via `sys.argv`) first — if set, prints "
                            "an informational message and returns 0 immediately. Otherwise "
                            "iterates the `EDGES` dict (keys: TREATS, ADDRESSES, DEVELOPED_BY) "
                            "in definition order, calling `run(query)` for each and printing "
                            "`{predicate}: +{count} new edges`. After the loop, calls `run()` "
                            "once more with a count-by-predicate SELECT to print the overall "
                            "active-edge summary for the graph."
                        ),
                    }
                ],
            ],
        },
    ],
}
