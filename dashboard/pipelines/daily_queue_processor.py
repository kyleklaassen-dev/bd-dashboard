"""
Static description of the Discovery Queue Processor pipeline
(.github/workflows/daily-queue-processor.yml).

Daily 6 AM ET run that processes up to 65 pending research_queue items via
three route handlers: CT.gov trial search, Claude Sonnet drug field enrichment,
and PubMed PK/PD extraction.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "queue_processor",
    "workflow_name": "Discovery Queue Processor",
    "workflow_file": ".github/workflows/daily-queue-processor.yml",
    "schedule": "Daily 10:00 UTC (6 AM ET) — clears overnight queue growth before analysts start work",
    "entrypoint": "scripts/intake/process_queue_item.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "The workhorse that turns `research_queue` items into real database "
        "entries. Every morning it picks the top 65 pending items by "
        "`priority_score` and routes each through one of three handlers: "
        "Route 1 (CT.gov) searches ClinicalTrials.gov for the drug's trials, "
        "upserts the best NCT ID to `trial_registries`, and can advance a "
        "drug's stage from Preclinical if trial evidence is found. "
        "Route 2 (Drug enrichment) calls Claude Sonnet to fill null fields "
        "(target, mechanism, differentiation_thesis, ailux_angle, drug_summary, "
        "stage, indication_short) — never overwriting existing values. "
        "Route 3 (PubMed PK/PD) extracts half-life, Cmax, or bioavailability "
        "from a PubMed abstract via Claude Haiku. "
        "Each item is marked `processing` before its handler runs and "
        "`resolved` after — creating a clear audit trail."
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
        label="process_queue_item.py\n(--batch --limit 65)\nbatch loop + route dispatch",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    rq_in [
        label="Supabase\nresearch_queue\n(status=pending, order by priority_score desc)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    classify [label="_classify_route()\nctgov / drug_enrich / pkpd"]

    subgraph cluster_r1 {
        label="Route 1 — CT.gov trial search"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        search_ct [label="search_ctgov()\nGET /api/v2/studies"]
        insert_trials [label="insert_trials()\nPATCH/POST trial_registries\nbest NCT, phase rank"]
        stage_advance [label="advance stage\nif Preclinical + Phase found"]
    }

    subgraph cluster_r2 {
        label="Route 2 — Drug field enrichment (Claude Sonnet)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        enrich_fields [label="enrich_drug_fields()\nclaude-sonnet-4-6\ntarget · mechanism · ailux_angle\ndrug_summary · stage · indication_short"]
        patch_drug [label="PATCH drugs\nnull fields only"]
    }

    subgraph cluster_r3 {
        label="Route 3 — PubMed PK/PD"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        fetch_pm [label="fetch_pubmed_abstract()\nGET eutils/efetch.fcgi"]
        extract_pk [label="extract_pk_with_claude()\nclaude-haiku-4-5\nhalf_life / cmax / bioavailability"]
        insert_pk [label="POST drug_pk_parameters\nif confidence >= 0.5"]
    }

    ctgov_api [
        label="ClinicalTrials.gov\nAPI v2",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11
    ]

    pubmed_api [
        label="PubMed eutils API",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11
    ]

    claude_api [
        label="Anthropic API\nSonnet (Route 2)\nHaiku (Route 3)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11
    ]

    trial_reg [
        label="Supabase\ntrial_registries",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    drugs_out [
        label="Supabase\ndrugs\n(stage + null fields)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    pk_out [
        label="Supabase\ndrug_pk_parameters",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    rq_out [
        label="Supabase\nresearch_queue\n(status: processing → resolved)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    entry -> rq_in [label="  top 65 pending by priority", style="bold", color="#c9890a", fontcolor="#c9890a"]
    rq_in -> classify
    classify -> search_ct [label="  ctgov route"]
    classify -> enrich_fields [label="  drug_enrich route"]
    classify -> fetch_pm [label="  pkpd route"]
    ctgov_api -> search_ct [style="bold", color="#c9890a", fontcolor="#c9890a"]
    search_ct -> insert_trials
    insert_trials -> trial_reg [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    insert_trials -> stage_advance
    stage_advance -> drugs_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    claude_api -> enrich_fields [style="bold", color="#c9890a", fontcolor="#c9890a"]
    enrich_fields -> patch_drug
    patch_drug -> drugs_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    pubmed_api -> fetch_pm [style="bold", color="#c9890a", fontcolor="#c9890a"]
    fetch_pm -> extract_pk
    claude_api -> extract_pk [style="bold", color="#c9890a", fontcolor="#c9890a"]
    extract_pk -> insert_pk
    insert_pk -> pk_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    search_ct -> rq_out [label="  mark_resolved()"]
    patch_drug -> rq_out [label="  mark_resolved()"]
    insert_pk -> rq_out [label="  mark_resolved()"]
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

        rq_in [label="Supabase\nresearch_queue\n(pending items)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        drugs_in [label="Supabase\ndrugs\n(current field values)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        ct_in [label="ClinicalTrials.gov\nAPI v2 (Route 1)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        pm_in [label="PubMed eutils\nAPI (Route 3)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        ai_in [label="Anthropic API\nSonnet · Haiku", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Discovery Queue\nProcessor",
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

        rq_out [label="Supabase\nresearch_queue\n(status → resolved)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        drugs_out [label="Supabase\ndrugs\n(null fields filled, stage advanced)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        trial_out [label="Supabase\ntrial_registries\n(NCT ID + trial count)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        pk_out [label="Supabase\ndrug_pk_parameters\n(half_life · cmax · bioavailability)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    rq_in -> pipeline
    drugs_in -> pipeline
    ct_in -> pipeline
    pm_in -> pipeline
    ai_in -> pipeline
    pipeline -> rq_out
    pipeline -> drugs_out
    pipeline -> trial_out
    pipeline -> pk_out
}
""",
    "io": {
        "reads": [
            {
                "name": "research_queue",
                "kind": "Supabase table",
                "via": "batch loop → sb_get('research_queue', {assigned_status: 'eq.pending', order: 'priority_score.desc', limit: str(args.limit)})",
                "desc": (
                    "Fetches the top N pending items by `priority_score` "
                    "descending (default N=65). Each item carries `entity_id`, "
                    "`entity_name`, `company_id`, `context_type`, "
                    "`next_best_action` (action hint), `reason`, and "
                    "`missing_fields`. These fields drive `_classify_route()` "
                    "and the three handlers."
                ),
                "scope": (
                    "One query per batch run. Items are processed sequentially "
                    "with a 2-second sleep between them to rate-limit Claude "
                    "and CT.gov calls."
                ),
            },
            {
                "name": "drugs",
                "kind": "Supabase table",
                "via": "handle_ctgov() / handle_drug_enrichment() → sb_get('drugs', {id: 'eq.<id>'})",
                "desc": (
                    "Route 1 looks up the drug by `entity_id` to find its "
                    "current `stage` (used to decide whether to advance it). "
                    "If entity_id is a company, looks up all the company's "
                    "drugs. Route 2 fetches the full drug row to identify "
                    "which fields are already populated (only null/empty fields "
                    "are written)."
                ),
                "scope": (
                    "One or two narrow queries per item. Route 2 may fetch up "
                    "to 20 drugs per company-level item."
                ),
            },
            {
                "name": "ClinicalTrials.gov API v2",
                "kind": "External API",
                "via": "search_ctgov() → requests.get('/api/v2/studies', {query.term: drug_name, pageSize: 10})",
                "desc": (
                    "Route 1 searches for trials by `drug_name` (optionally "
                    "joined with `company_id`). Returns up to 10 studies with "
                    "`nct_id`, `title`, `phase`, `status`, `start_date`. "
                    "`best_phase()` and `phase_rank()` are used to select the "
                    "highest-phase trial for `trial_registries`."
                ),
                "scope": "One GET per Route 1 item, 25-second timeout.",
            },
            {
                "name": "PubMed eutils API",
                "kind": "External API",
                "via": "fetch_pubmed_abstract() → requests.get('eutils/efetch.fcgi', {db: 'pubmed', id: pmid, rettype: 'abstract'})",
                "desc": (
                    "Route 3 extracts a PMID from the `reason` field regex "
                    "(`PMID: \\d+`) and fetches the abstract text. Returns up "
                    "to 3000 chars of plain text. Empty abstract → skip."
                ),
                "scope": "One GET per Route 3 item, 20-second timeout.",
            },
            {
                "name": "Anthropic API — claude-sonnet-4-6 (Route 2) + claude-haiku-4-5 (Route 3)",
                "kind": "External API",
                "via": "ai_client.run_json(PromptConfig, prompt)",
                "desc": (
                    "Route 2 calls Sonnet with a BD-focused drug enrichment "
                    "prompt requesting 7 fields (max_tokens=1200). "
                    "Route 3 calls Haiku with a PK extraction prompt requesting "
                    "6 parameters (max_tokens=400). Both return JSON; "
                    "unparseable responses are treated as empty dicts."
                ),
                "scope": (
                    "At most one Claude call per item. Haiku is used for "
                    "PK/PD because the task is highly structured and Haiku "
                    "is faster and cheaper for JSON extraction."
                ),
            },
        ],
        "cleaning": (
            "**Three safety rules govern writes.** Route 1: stage advancement "
            "only fires if the drug's current `stage` is `Preclinical` / "
            "`preclinical` / empty — never overwrites an existing non-null stage. "
            "Route 2: only null or empty fields in the `drugs` row are updated; "
            "existing values are never overwritten (`if enriched.get(field) and "
            "not drug.get(field)`). Route 3: PK rows are only inserted if "
            "`confidence >= 0.5` — low-confidence extractions are discarded. "
            "All three handlers return a list of action strings; if the list "
            "is empty, `mark_resolved()` records 'No new data found — item "
            "reviewed' rather than leaving the item unresolved."
        ),
        "writes": [
            {
                "name": "research_queue",
                "kind": "Supabase table",
                "via": "mark_processing() + mark_resolved() → sb_patch('research_queue', {'id': 'eq.<id>'}, ...)",
                "desc": (
                    "`mark_processing()` stamps `assigned_status='processing'` "
                    "and `last_action_at` before the handler runs. "
                    "`mark_resolved()` stamps `assigned_status='resolved'` "
                    "and `next_best_action='DONE: <summary>'` after — creating "
                    "a two-step audit trail. Warnings are logged if a PATCH "
                    "fails but do not abort the run."
                ),
                "scope": "Two PATCHes per item processed.",
            },
            {
                "name": "trial_registries",
                "kind": "Supabase table",
                "via": "insert_trials() → requests.patch / requests.post('trial_registries', ...)",
                "desc": (
                    "Route 1 tries to PATCH the existing "
                    "`(drug_id, registry_name='ClinicalTrials.gov')` row with "
                    "the best NCT ID, `trial_count`, and "
                    "`search_status='found'`. Falls back to POST if no row "
                    "exists. Selects the best trial by phase rank (3 > 2 > 1 "
                    "> any)."
                ),
                "scope": "At most one write per Route 1 item per drug.",
            },
            {
                "name": "drugs",
                "kind": "Supabase table",
                "via": "handle_ctgov() / handle_drug_enrichment() → sb_patch('drugs', {'id': 'eq.<id>'}, update)",
                "desc": (
                    "Route 1 may PATCH `stage` (Preclinical → best_phase). "
                    "Route 2 PATCHes up to 7 fields that were null: `target`, "
                    "`mechanism`, `differentiation_thesis`, `ailux_angle`, "
                    "`drug_summary`, `stage`, `indication_short`, plus "
                    "`last_synced_date`."
                ),
                "scope": (
                    "At most one PATCH per drug per item. Route 2 iterates up "
                    "to 20 drugs if the entity_id is a company."
                ),
            },
            {
                "name": "drug_pk_parameters",
                "kind": "Supabase table",
                "via": "handle_pkpd() → sb_post('drug_pk_parameters', pk_row, prefer='return=minimal')",
                "desc": (
                    "Route 3 inserts one PK row per item: `drug_id`, "
                    "`parameter_type` (half_life / cmax / bioavailability), "
                    "`value_numeric`, `unit`, `dose_route`, `species`, "
                    "`source_type='abstract'`, `source_url` "
                    "(https://pubmed.ncbi.nlm.nih.gov/{pmid}/), and "
                    "`confidence_score`."
                ),
                "scope": "One insert per successful Route 3 item.",
            },
        ],
    },
    "phases": [
        {
            "label": "Helpers & queue utilities",
            "note": "Thin wrappers for queue state management.",
            "groups": [
                [
                    {
                        "function": "log(msg)",
                        "lines": 2,
                        "desc": "Prints with two-space indent and flush=True.",
                    },
                    {
                        "function": "sb_patch(table, params, payload)",
                        "lines": 2,
                        "desc": "Shim that swaps params/payload order vs _db.sb_patch.",
                    },
                    {
                        "function": "sb_post(table, payload, prefer='return=minimal')",
                        "lines": 9,
                        "desc": (
                            "Issues a direct `requests.post()` with "
                            "`Prefer: return=minimal` (avoids the "
                            "representation overhead of `_db.sb_post()`). "
                            "Returns True on 200/201."
                        ),
                    },
                ],
                [
                    {
                        "function": "get_item(item_id)",
                        "lines": 3,
                        "desc": "Fetches one research_queue row by UUID.",
                    },
                    {
                        "function": "mark_processing(item_id)",
                        "lines": 6,
                        "desc": "PATCHes `assigned_status='processing'` + `last_action_at`.",
                    },
                    {
                        "function": "mark_resolved(item_id, summary)",
                        "lines": 12,
                        "desc": (
                            "PATCHes `assigned_status='resolved'`, "
                            "`next_best_action='DONE: <summary[:200]>'`, "
                            "and `last_action_at`. Logs a warning if "
                            "the PATCH fails."
                        ),
                    },
                ],
            ],
        },
        {
            "label": "Route 1 — CT.gov trial search",
            "note": "Three functions that search CT.gov, select the best trial, and update the DB.",
            "groups": [
                [
                    {
                        "function": "search_ctgov(drug_name, company_name=None)",
                        "lines": 33,
                        "desc": (
                            "GETs CT.gov v2 `/studies` with `query.term` = "
                            "drug_name (optionally joined with company_name), "
                            "`pageSize=10`. Extracts `nct_id`, `title`, "
                            "`phase`, `status`, `start_date` from each study. "
                            "Returns a list of dicts; returns `[]` on HTTP "
                            "error or exception."
                        ),
                    }
                ],
                [
                    {
                        "function": "best_phase(phases)",
                        "lines": 8,
                        "desc": (
                            "Returns the highest phase string from a list "
                            "('Phase 3' > 'Phase 2' > 'Phase 1' > ''). "
                            "Used to decide whether stage advancement is "
                            "warranted."
                        ),
                    },
                    {
                        "function": "insert_trials(drug_id, trials)",
                        "lines": 63,
                        "desc": (
                            "Selects the best trial by `phase_rank()` "
                            "(3 > 2 > 1 > any). PATCHes the existing "
                            "`(drug_id, 'ClinicalTrials.gov')` row in "
                            "`trial_registries`; falls back to POST if "
                            "no row exists. Stores `registry_id`, "
                            "`registry_url`, `trial_count`, "
                            "`search_status='found'`."
                        ),
                    },
                ],
                [
                    {
                        "function": "handle_ctgov(item)",
                        "lines": 43,
                        "desc": (
                            "Resolves drug rows from `entity_id` (drug or "
                            "company). Calls `search_ctgov()`, then "
                            "`insert_trials()` for each drug. If phases found "
                            "and current stage is Preclinical, PATCHes `stage`. "
                            "Returns list of action strings."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Route 2 — Drug field enrichment",
            "note": "Two functions that call Claude Sonnet and safely write only null fields.",
            "groups": [
                [
                    {
                        "function": "enrich_drug_fields(drug_id, drug_name, context)",
                        "lines": 24,
                        "desc": (
                            "Formats the BD-focused enrichment prompt with "
                            "drug_name and context (area, stage, company, "
                            "context_type, missing_fields). Calls "
                            "`ai_client.run_json()` with `claude-sonnet-4-6`, "
                            "max_tokens=1200. Returns parsed dict or `{}` "
                            "on failure."
                        ),
                    }
                ],
                [
                    {
                        "function": "handle_drug_enrichment(item)",
                        "lines": 72,
                        "desc": (
                            "Resolves drug rows from entity_id. For each drug, "
                            "calls `enrich_drug_fields()`, then builds an "
                            "`update` dict of only the fields that are in "
                            "`NULLABLE_FIELDS` and currently null in the DB. "
                            "Stage is only written if currently null. Always "
                            "sets `last_synced_date`. PATCHes the drug and "
                            "logs filled fields. Skips if all fields already "
                            "populated."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Route 3 — PubMed PK/PD extraction",
            "note": "Three functions that extract a PMID, fetch the abstract, and write PK parameters.",
            "groups": [
                [
                    {
                        "function": "fetch_pubmed_abstract(pmid)",
                        "lines": 12,
                        "desc": (
                            "GETs PubMed efetch (rettype=abstract, retmode=text). "
                            "Returns up to 3000 chars of plain text or empty "
                            "string on failure."
                        ),
                    },
                    {
                        "function": "extract_pk_with_claude(drug_name, abstract_text)",
                        "lines": 31,
                        "desc": (
                            "Calls `claude-haiku-4-5` with a structured PK "
                            "extraction prompt requesting half_life_h, dose_route, "
                            "cmax_value, cmax_unit, bioavailability_pct, species, "
                            "and confidence (0.0-1.0). max_tokens=400. Returns "
                            "parsed dict or `{}` on failure."
                        ),
                    },
                ],
                [
                    {
                        "function": "handle_pkpd(item)",
                        "lines": 79,
                        "desc": (
                            "Extracts PMID from reason field regex. Fetches "
                            "abstract. Calls `extract_pk_with_claude()`. "
                            "Discards result if `confidence < 0.5`. Resolves "
                            "drug_id from entity_id. Picks the most informative "
                            "parameter (half_life > cmax > bioavailability). "
                            "POSTs to `drug_pk_parameters`."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Router & item processor",
            "note": "_classify_route() reads three item fields to pick a route; process_item() drives the full lifecycle.",
            "groups": [
                [
                    {
                        "function": "_classify_route(item)",
                        "lines": 40,
                        "desc": (
                            "Inspects `context_type`, `next_best_action`, and "
                            "`reason` (all lowercased). Priority order: "
                            "PMID/pubmed/pk signals → `pkpd`; CT.gov/clinical "
                            "trial signals → `ctgov`; mechanism/mapping/enrichment "
                            "signals → `drug_enrich`. Default: `drug_enrich` "
                            "(most common gap type)."
                        ),
                    }
                ],
                [
                    {
                        "function": "process_item(item)",
                        "lines": 32,
                        "desc": (
                            "Calls `mark_processing()`, `_classify_route()`, "
                            "dispatches to the correct handler, catches handler "
                            "exceptions, and calls `mark_resolved()` with the "
                            "action summary. Returns the list of action strings."
                        ),
                    }
                ],
            ],
        },
    ],
}
