"""
Static description of the Execute Intel Actions pipeline
(.github/workflows/daily-execute-intel-actions.yml).

Daily 6:30 AM ET run (30 minutes after queue-processor) that promotes
approved discovery_queue items to the drugs table (G1) and executes
proposed_actions from analyzed submitted_intel rows (G2). A second step
in the same workflow queues newly promoted drugs for enrichment (N3).
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "execute_intel_actions",
    "workflow_name": "Execute Intel Actions",
    "workflow_file": ".github/workflows/daily-execute-intel-actions.yml",
    "schedule": "Daily 10:30 UTC (6:30 AM ET) — 30 minutes after queue-processor to pick up newly promoted drugs",
    "entrypoint": "scripts/intake/execute_intel_actions.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "The gap-closing step that turns analyst approvals into live database "
        "entries. It runs two passes in sequence. G1 (discovery promotion): "
        "any `discovery_queue` row with `status='approved'` and no "
        "`created_drug_id` yet is auto-slugged and inserted into `drugs`, "
        "then `created_drug_id` is stamped back on the queue row. "
        "G2 (submitted intel execution): any `submitted_intel` row with "
        "`status='analyzed'` and no `imported_at` timestamp has its "
        "`proposed_actions_json` executed — currently `add_catalyst` "
        "(creates a catalyst_calendar entry) and `add_source` (marks "
        "the item done). A second workflow step (inline Python, the N3 fix) "
        "then finds any newly auto-promoted drugs created in the last 25 "
        "hours with a null mechanism and queues them in `research_queue` "
        "for immediate enrichment."
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
        label="execute_intel_actions.py · main()\n(G1 discovery promotion + G2 submitted intel)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    inline_n3 [
        label="Inline Python (workflow step)\nN3 fix: queue newly promoted\ndrugs for enrichment",
        fillcolor="#dbe9fb",
        color="#5b8def",
        fontcolor="#111827"
    ]

    subgraph cluster_g1 {
        label="G1 — promote_discovery_queue()"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        dq_in [label="discovery_queue\n(status=approved, created_drug_id IS NULL)"]
        check_exists [label="check drugs.id exists\n(skip if already created)"]
        make_id [label="make_id(name)\nauto-slug from drug_name"]
        promote [label="POST drugs\n(stage/overlap/catalog_category/discovery_status)"]
        stamp_dq [label="PATCH discovery_queue\ncreated_drug_id = new slug"]
    }

    subgraph cluster_g2 {
        label="G2 — execute_submitted_intel()"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        si_in [label="submitted_intel\n(status=analyzed, imported_at IS NULL)"]
        parse_actions [label="parse proposed_actions_json\nskip: reject_duplicate / needs_human_review"]
        exec_catalyst [label="add_catalyst:\nfind drug by name\nPOST catalyst_calendar"]
        exec_source [label="add_source:\nmark done (no write)"]
        stamp_si [label="PATCH submitted_intel\nimported_at = NOW"]
    }

    subgraph cluster_n3 {
        label="N3 inline step — enrich newly promoted drugs"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        find_new [label="GET drugs\n(discovery_status=auto, mechanism IS NULL\ncreated_at >= 25h ago, limit 20)"]
        queue_enrich [label="POST research_queue\n(context_type=never_enriched\npriority_score=90)"]
    }

    dq_table_in [
        label="Supabase\ndiscovery_queue\n(approved, unlinked rows)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    si_table_in [
        label="Supabase\nsubmitted_intel\n(analyzed, not yet imported)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    drugs_ref [
        label="Supabase\ndrugs\n(check for existing slug)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    drugs_out [
        label="Supabase\ndrugs\n(new promoted rows — G1)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    dq_out [
        label="Supabase\ndiscovery_queue\n(created_drug_id stamped)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    catalyst_out [
        label="Supabase\ncatalyst_calendar\n(new G2 catalyst rows)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    si_out [
        label="Supabase\nsubmitted_intel\n(imported_at stamped)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    rq_out [
        label="Supabase\nresearch_queue\n(N3: newly promoted drugs)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    entry -> dq_table_in [label="  G1: reads approved", style="bold", color="#c9890a", fontcolor="#c9890a"]
    dq_table_in -> dq_in
    dq_in -> check_exists
    check_exists -> drugs_ref [style="bold", color="#c9890a", fontcolor="#c9890a"]
    drugs_ref -> make_id
    make_id -> promote
    promote -> drugs_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    promote -> stamp_dq
    stamp_dq -> dq_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]

    entry -> si_table_in [label="  G2: reads analyzed", style="bold", color="#c9890a", fontcolor="#c9890a"]
    si_table_in -> si_in
    si_in -> parse_actions
    parse_actions -> exec_catalyst
    parse_actions -> exec_source
    exec_catalyst -> drugs_ref [label="  find drug by name", style="bold", color="#c9890a", fontcolor="#c9890a"]
    exec_catalyst -> catalyst_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    exec_source -> stamp_si
    exec_catalyst -> stamp_si
    stamp_si -> si_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]

    inline_n3 -> find_new
    find_new -> drugs_ref [style="bold", color="#c9890a", fontcolor="#c9890a"]
    find_new -> queue_enrich
    queue_enrich -> rq_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        dq_in [label="Supabase\ndiscovery_queue\n(approved, unlinked)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        si_in [label="Supabase\nsubmitted_intel\n(analyzed, not imported)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        drugs_in [label="Supabase\ndrugs\n(slug collision check + drug name lookup)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Execute Intel\nActions",
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

        drugs_out [label="Supabase\ndrugs\n(G1: new promoted rows)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        dq_out [label="Supabase\ndiscovery_queue\n(created_drug_id stamped)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        catalyst_out [label="Supabase\ncatalyst_calendar\n(G2: add_catalyst actions)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        si_out [label="Supabase\nsubmitted_intel\n(imported_at stamped)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        rq_out [label="Supabase\nresearch_queue\n(N3: unenriched promoted drugs)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    dq_in -> pipeline
    si_in -> pipeline
    drugs_in -> pipeline
    pipeline -> drugs_out
    pipeline -> dq_out
    pipeline -> catalyst_out
    pipeline -> si_out
    pipeline -> rq_out
}
""",
    "io": {
        "reads": [
            {
                "name": "discovery_queue",
                "kind": "Supabase table",
                "via": "promote_discovery_queue() → sb_get('discovery_queue', {status: 'eq.approved', created_drug_id: 'is.null'})",
                "desc": (
                    "Fetches approved items that have not yet been linked to "
                    "a `drugs` row (`created_drug_id IS NULL`). Columns read: "
                    "`id`, `drug_name`, `company_name`, `target`, `stage`, "
                    "`overlap`, `area_id`, `confidence_score`, "
                    "`why_discovered`. Company-only entries (no `drug_name`) "
                    "are skipped with a `COMPANY_ONLY` stamp."
                ),
                "scope": "One query, limit 200.",
            },
            {
                "name": "submitted_intel",
                "kind": "Supabase table",
                "via": "execute_submitted_intel() → sb_get('submitted_intel', {status: 'eq.analyzed', imported_at: 'is.null'})",
                "desc": (
                    "Fetches analyzed rows whose `imported_at` is still null "
                    "(not yet executed). Columns read: `id`, `extracted_title`, "
                    "`extracted_entities_json`, `proposed_actions_json`, "
                    "`source_url`, `extracted_key_facts_json`."
                ),
                "scope": "One query, limit 200.",
            },
            {
                "name": "drugs (slug collision check + drug name lookup)",
                "kind": "Supabase table",
                "via": "promote_discovery_queue() + execute_submitted_intel() → sb_get('drugs', ...)",
                "desc": (
                    "G1 checks `drugs?id=eq.<slug>` to avoid duplicating an "
                    "already-promoted drug (stamps `created_drug_id` and "
                    "skips the insert). G2's `add_catalyst` handler looks up "
                    "the drug by name via `drugs?name=ilike.*<clean>*` to "
                    "find the drug_id for the catalyst row."
                ),
                "scope": "One narrow query per item for G1; one per drug name for G2 add_catalyst.",
            },
            {
                "name": "drugs (N3 — newly promoted unenriched)",
                "kind": "Supabase table",
                "via": "Inline Python step → requests.get('drugs', {discovery_status: 'eq.auto', mechanism: 'is.null', created_at: 'gte.<25h>'})",
                "desc": (
                    "The N3 inline Python step queries for auto-discovered "
                    "drugs (from G1 promotions) created in the last 25 hours "
                    "with a null `mechanism`. These are the drugs that need "
                    "immediate enrichment via the queue_processor."
                ),
                "scope": "One query, limit 20.",
            },
        ],
        "cleaning": (
            "**Two idempotency guards prevent double-writes.** G1: the slug "
            "collision check (`sb_get('drugs', {'id': 'eq.<slug>'})`) means "
            "re-running the workflow after a partial failure never creates "
            "duplicate drug rows — if the drug already exists, `created_drug_id` "
            "is stamped and the insert is skipped. G2: `imported_at IS NULL` "
            "ensures each submitted_intel row is executed at most once — once "
            "stamped, it's invisible to future runs. "
            "The `make_id()` function sanitises the drug name to a URL-safe "
            "slug (lowercase, hyphens, 40-char cap). Unicode characters in "
            "targets (α, β, ×) are transliterated to ASCII before storing. "
            "G2 skips `reject_duplicate`, `needs_human_review`, and "
            "`add_company_note` actions — these are informational and require "
            "human judgment."
        ),
        "writes": [
            {
                "name": "drugs",
                "kind": "Supabase table",
                "via": "promote_discovery_queue() → sb_post('drugs', drug)",
                "desc": (
                    "G1 inserts a minimal drug stub: `id` (slug), `name`, "
                    "`display_name`, `target` (ASCII-ised), `stage` (default "
                    "'Preclinical'), `overlap` (default 'Watch'), "
                    "`catalog_category='Pipeline'`, "
                    "`discovery_status='auto'`, `confidence_score`, "
                    "`data_source='discovery_queue'`, `drug_summary`. "
                    "No enrichment fields — those come from queue_processor."
                ),
                "scope": (
                    "At most one insert per approved-and-unlinked discovery_queue "
                    "row. Typical run: 0–5 promotions per day."
                ),
            },
            {
                "name": "discovery_queue",
                "kind": "Supabase table",
                "via": "promote_discovery_queue() → sb_patch('discovery_queue', {'id': 'eq.<id>'}, {created_drug_id: drug_id})",
                "desc": (
                    "Stamps `created_drug_id` on each promoted queue row, "
                    "whether the drug was newly created or already existed. "
                    "Company-only rows get `created_drug_id='COMPANY_ONLY'`. "
                    "This prevents re-processing on future runs."
                ),
                "scope": "One PATCH per processed queue item.",
            },
            {
                "name": "catalyst_calendar",
                "kind": "Supabase table",
                "via": "execute_submitted_intel() → sb_post('catalyst_calendar', cat)",
                "desc": (
                    "G2's `add_catalyst` action creates a catalyst row "
                    "linked to the resolved `drug_id`. Fields: `drug_id`, "
                    "`area_id='ibd'`, `catalyst_date='2026'`, "
                    "`sort_date='2026-12-31'`, `label` (intel signal title), "
                    "`catalyst_type='readout'`, `significance='medium'`, "
                    "`catalyst_status='pending'`, "
                    "`confidence_level='inferred'`, `confidence_score=0.5`, "
                    "`notes` (action rationale), `resolved=False`. "
                    "Duplicate check: skips if a catalyst with a similar label "
                    "already exists for that drug."
                ),
                "scope": (
                    "At most one per drug per analyzed submitted_intel item "
                    "with an `add_catalyst` action."
                ),
            },
            {
                "name": "submitted_intel",
                "kind": "Supabase table",
                "via": "execute_submitted_intel() → sb_patch('submitted_intel', {'id': 'eq.<id>'}, {imported_at: NOW})",
                "desc": (
                    "Stamps `imported_at` on each fully-processed row — whether "
                    "or not any actions fired. This prevents re-processing on "
                    "future runs."
                ),
                "scope": "One PATCH per item that had any actions or that was already fully handled.",
            },
            {
                "name": "research_queue",
                "kind": "Supabase table",
                "via": "N3 inline Python → requests.post('research_queue', {...})",
                "desc": (
                    "N3 inserts one `research_queue` row per newly promoted "
                    "drug that still has a null `mechanism`: "
                    "`entity_id=drug.id`, `entity_name`, "
                    "`context_type='never_enriched'`, `priority_score=90`, "
                    "`assigned_status='pending'`, `reason` (explains the drug "
                    "needs enrichment). These high-priority rows are picked up "
                    "by the next queue-processor run."
                ),
                "scope": "At most 20 inserts per run (limit in the inline query).",
            },
        ],
    },
    "phases": [
        {
            "label": "Helpers",
            "note": "Four module-level utility functions used throughout the script.",
            "groups": [
                [
                    {
                        "function": "sb_get(table, params, limit=200)",
                        "lines": 2,
                        "desc": (
                            "Merges `limit` into params and forwards to "
                            "`_db.sb_get()`. The `limit` kwarg always wins "
                            "over any 'limit' already in params."
                        ),
                    },
                    {
                        "function": "sb_post(table, payload)",
                        "lines": 2,
                        "desc": "Shim over `_db.sb_post()` returning bool.",
                    },
                    {
                        "function": "sb_patch(table, params, payload)",
                        "lines": 2,
                        "desc": "Shim that swaps params/payload order vs _db.sb_patch.",
                    },
                ],
                [
                    {
                        "function": "make_id(name)",
                        "lines": 10,
                        "desc": (
                            "Lowercases the name, strips non-word characters, "
                            "collapses whitespace to hyphens, deduplicates "
                            "consecutive hyphens, and truncates to 40 chars. "
                            "Also strips parenthetical suffixes "
                            "(`name.split('(')[0].strip()`) before slugging."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "G1 — Discovery queue promotion",
            "note": "promote_discovery_queue() converts approved discovery_queue items to minimal drug stubs.",
            "groups": [
                [
                    {
                        "function": "promote_discovery_queue(dry_run=False)",
                        "lines": 60,
                        "desc": (
                            "Fetches approved, unlinked discovery_queue items. "
                            "For each: skips if no `drug_name`, stamps "
                            "`COMPANY_ONLY` for company-only entries. Slugs the "
                            "drug name via `make_id()`. Checks for an existing "
                            "drugs row with that slug (skip + stamp if exists). "
                            "Otherwise transliterates target to ASCII, builds the "
                            "stub dict, and calls `sb_post('drugs', drug)`. On "
                            "success stamps `created_drug_id`. Prints a "
                            "per-item status and a final count."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "G2 — Submitted intel action execution",
            "note": "execute_submitted_intel() walks proposed_actions_json and fires supported action types.",
            "groups": [
                [
                    {
                        "function": "execute_submitted_intel(dry_run=False)",
                        "lines": 86,
                        "desc": (
                            "Fetches analyzed, not-yet-imported submitted_intel "
                            "rows. For each, iterates `proposed_actions_json` "
                            "(a list of action dicts). Skips "
                            "`reject_duplicate`, `needs_human_review`, "
                            "`add_company_note`. For `add_catalyst`: finds the "
                            "drug by name (ilike), checks for a near-duplicate "
                            "catalyst label, and inserts a catalyst_calendar row. "
                            "For `add_source`: marks done without a write "
                            "(source attachment is handled by human review). "
                            "Stamps `imported_at` on the submitted_intel row if "
                            "any actions were present or handled. Returns executed "
                            "count."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "N3 inline step — enrich newly promoted drugs",
            "note": "The second workflow step (inline Python, not in execute_intel_actions.py) handles the N3 gap.",
            "groups": [
                [
                    {
                        "function": "(inline Python — workflow step)",
                        "lines": 20,
                        "desc": (
                            "Queries `drugs` for rows with "
                            "`discovery_status=auto`, `mechanism IS NULL`, "
                            "and `created_at >= 25 hours ago`. For each, "
                            "inserts a `research_queue` row with "
                            "`context_type='never_enriched'` and "
                            "`priority_score=90`. This ensures that drugs "
                            "promoted by G1 earlier today are picked up by "
                            "the next queue-processor run rather than waiting "
                            "in the queue at default priority."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main",
            "note": "main() parses args and dispatches to G1/G2 based on --discovery / --submitted flags.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 18,
                        "desc": (
                            "Parses `--discovery` (G1 only), `--submitted` "
                            "(G2 only), and `--dry-run`. If neither flag is "
                            "set, runs both. The workflow YAML's `ARGS` "
                            "construction means both run by default; passing "
                            "`discovery=false` passes `--submitted` to run G2 "
                            "only, and vice versa."
                        ),
                    }
                ],
            ],
        },
    ],
}
