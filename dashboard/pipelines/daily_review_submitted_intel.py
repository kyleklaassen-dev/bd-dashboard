"""
Static description of the Submitted Intel Auto-Review pipeline
(.github/workflows/daily-review-submitted-intel.yml).

Every 6 hours, screens submitted_intel rows with status='new':
validates the source URL, fetches page content, extracts structured
intelligence via Claude Opus, checks for duplicates, executes deep
entity writes, and updates the row status.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "review_submitted_intel",
    "workflow_name": "Meridian — Submitted Intel Auto-Review",
    "workflow_file": ".github/workflows/daily-review-submitted-intel.yml",
    "schedule": "Every 6 hours (00:00, 06:00, 12:00, 18:00 UTC) — skips entirely if no new rows",
    "entrypoint": "scripts/intake/review_submitted_intel.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Path 5 intake: turns analyst-submitted URLs and text snippets into "
        "structured database entries with zero manual data entry. The workflow "
        "first runs an inline Python check against `submitted_intel?status=eq.new` "
        "and exits early if the table is empty — the main script never runs on "
        "quiet days. When rows are present, it validates each URL, fetches page "
        "content, calls Claude Opus for entity extraction, runs four-vector "
        "duplicate detection, and then a second Claude Sonnet pass (deep extraction) "
        "that directly writes companies, drugs, clinical benchmarks, deals, catalysts, "
        "Q&A insights, and company documents to the database. The row is stamped "
        "`analyzed` or `needs_review` based on confidence, BD relevance, and "
        "duplicate risk."
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
        label="review_submitted_intel.py · main()\n(entrypoint — fetches new rows, loops)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    inline_check [
        label="Inline Python check\n(workflow step)\nsubmitted_intel?status=eq.new\ncount > 0?",
        fillcolor="#fde9c8",
        color="#d99a3b",
        fontcolor="#111827"
    ]

    submitted_intel_in [
        label="Supabase\nsubmitted_intel\n(status=eq.new)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_per_row {
        label="process_row(): per submitted_intel row"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        validate_url [label="validate_url()\nHTTP HEAD → valid/broken/unchecked"]
        fetch_page [label="fetch_page_text()\nGET + light HTML strip\n(≤ 6000 chars)"]
        claude_extract [label="call_claude() [Opus]\nentity extraction + proposed actions\n→ structured JSON"]
        entity_match [label="load_entities() + match_entity()\nfuzzy match to companies/drugs"]
        dup_check [label="check_duplicates()\n4-vector dedup check\n→ risk: low/medium/high"]
        status_route [label="route to status:\nanalyzed / needs_review"]
        deep_exec [label="deep_execute_intelligence() [Sonnet]\ncompanies, drugs, clinical data,\ndeals, catalysts, Q&A, docs"]
    }

    external_url [
        label="Submitted URL\n(HTTP HEAD + GET)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    claude_api [
        label="Anthropic API\nclaude-opus-4-6 (extraction)\nclaude-sonnet-4-6 (deep extraction)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    dedup_tables [
        label="Supabase\nsubmitted_intel · research_queue\ncatalysts · deals\n(read — dedup checks)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    entity_writes [
        label="Supabase\ndrugs · companies · deals\ncatalysts · drug_clinical_benchmarks\ndrug_intelligence_qa · company_documents\nconversation_intelligence_intake",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    submitted_out [
        label="Supabase\nsubmitted_intel\n(PATCH status + extracted fields)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    inline_check -> entry [label="  has_new=true only"]
    entry -> submitted_intel_in [label="  reads new rows", style="bold", color="#c9890a", fontcolor="#c9890a"]
    submitted_intel_in -> validate_url
    external_url -> validate_url [label="  HEAD request", style="bold", color="#c9890a", fontcolor="#c9890a"]
    validate_url -> fetch_page
    external_url -> fetch_page [label="  GET (if valid)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    fetch_page -> claude_extract
    claude_api -> claude_extract [label="  Opus extraction", style="bold", color="#c9890a", fontcolor="#c9890a"]
    claude_extract -> entity_match
    entity_match -> dup_check
    dedup_tables -> dup_check [label="  4 dedup vectors", style="bold", color="#c9890a", fontcolor="#c9890a"]
    dup_check -> status_route
    status_route -> deep_exec
    claude_api -> deep_exec [label="  Sonnet deep pass", style="bold", color="#c9890a", fontcolor="#c9890a"]
    deep_exec -> entity_writes [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    status_route -> submitted_out [label="  PATCH status + fields", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        si_in [label="Supabase\nsubmitted_intel (status=new)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        url_in [label="Submitted URL\n(HEAD validate + GET fetch)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        dedup_in [label="Supabase\nsubmitted_intel · research_queue\ncatalysts · deals (dedup reads)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        entity_ref_in [label="Supabase\ncompanies · drugs (entity matching)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Submitted Intel\nAuto-Review",
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

        si_out [label="Supabase\nsubmitted_intel\n(status + extracted fields)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        entities_out [label="Supabase\ndrugs · companies · deals\ncatalysts · drug_clinical_benchmarks\ndrug_intelligence_qa · company_documents\nconversation_intelligence_intake", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    si_in -> pipeline
    url_in -> pipeline
    dedup_in -> pipeline
    entity_ref_in -> pipeline
    pipeline -> si_out
    pipeline -> entities_out
}
""",
    "io": {
        "reads": [
            {
                "name": "submitted_intel",
                "kind": "Supabase table",
                "via": "main() → sb_get('submitted_intel', {status: 'eq.new', order: 'created_at.asc', limit: args.limit})",
                "desc": (
                    "Fetches rows with `status='new'`, ordered oldest-first, up "
                    "to `--limit` (default 20). Each row carries `source_url`, "
                    "`submitted_text`, and `submitted_by`. A pre-step in the "
                    "workflow uses inline Python to query "
                    "`submitted_intel?status=eq.new&select=id&limit=1` and "
                    "short-circuits the job if the count is zero — the main "
                    "script never starts on quiet days."
                ),
                "scope": (
                    "One query per run, bounded by `--limit`. A 1-second "
                    "`time.sleep()` between rows acts as a rate-limit courtesy "
                    "pause for the Claude API."
                ),
            },
            {
                "name": "Submitted URL (HEAD + GET)",
                "kind": "External HTTP resource",
                "via": "validate_url() → requests.head() | fetch_page_text() → requests.get()",
                "desc": (
                    "`validate_url()` sends a HEAD request (10s timeout, "
                    "follow redirects) to classify the URL as `valid` "
                    "(HTTP < 400), `broken`, or `unchecked` (no URL). "
                    "`fetch_page_text()` then GETs the page (15s timeout) "
                    "if `val_status == 'valid'`, strips script/style tags "
                    "and collapses whitespace, and returns up to 6000 chars."
                ),
                "scope": (
                    "Two requests per row with a valid URL. Pages that aren't "
                    "`text/html` or `text/plain` return an empty string. Fetch "
                    "failures are non-fatal — extraction proceeds with empty "
                    "page content."
                ),
            },
            {
                "name": "companies · drugs (entity matching)",
                "kind": "Supabase tables",
                "via": "load_entities() → sb_list() + match_entity()",
                "desc": (
                    "Loads the full `companies` (id, name) and `drugs` "
                    "(id, display_name) tables via `sb_list()` (Range: 0-9999). "
                    "Cached in module-level globals so the load happens at most "
                    "once per run. `match_entity()` does a case-insensitive "
                    "substring match to link Claude's extracted company/drug "
                    "names to existing IDs in the database."
                ),
                "scope": (
                    "Two full-table reads, once per run (cached). Results are "
                    "added to the extraction dict as `matched_company_ids` / "
                    "`matched_drug_ids` / `unmatched_companies` / "
                    "`unmatched_drugs`."
                ),
            },
            {
                "name": "submitted_intel · research_queue · catalysts · deals (dedup)",
                "kind": "Supabase tables",
                "via": "check_duplicates() → sb_get() × 4 paths",
                "desc": (
                    "Four independent duplicate-detection vectors: (1) exact "
                    "source_url match in submitted_intel (non-rejected rows); "
                    "(2) near-identical extracted_title in submitted_intel "
                    "(>75% keyword overlap); (3) company/drug name in "
                    "research_queue entity_name/reason; (4) similar catalyst "
                    "label or deal headline in `catalysts`/`deals` (>65% "
                    "overlap). Each positive match contributes a reason string "
                    "to the dedup result."
                ),
                "scope": (
                    "Up to 4 Supabase reads per row: one exact-URL check, one "
                    "title scan (all non-rejected submitted_intel rows), one "
                    "research_queue scan (limit 200), and one table scan of "
                    "catalysts or deals depending on intel_type. Results are "
                    "combined into a risk level: low / medium / high."
                ),
            },
        ],
        "cleaning": (
            "**Three layers gate the final status.** First, if Claude extraction "
            "fails entirely the row goes to `needs_review` with a note — "
            "no entity writes happen. Second, the duplicate check's risk level "
            "drives the status: `high` or `medium` risk → `needs_review` "
            "(human decides); `low` → `analyzed`. Third, BD relevance of `none` "
            "also forces `needs_review`. Only `analyzed` rows get stamped with "
            "the full extracted payload; `needs_review` rows get URL validation "
            "and the Claude extraction (if any) but no entity writes. "
            "The deep execution runs for both `analyzed` and `needs_review` "
            "rows as long as extraction succeeded — entity writes are not "
            "blocked by duplicate risk."
        ),
        "writes": [
            {
                "name": "submitted_intel",
                "kind": "Supabase table",
                "via": "process_row() → sb_patch('submitted_intel', row_id, update)",
                "desc": (
                    "PATCHes the processed row with: `status` (analyzed / "
                    "needs_review), `source_validation_status`, "
                    "`source_http_status`, `source_name`, `source_type`, "
                    "`extracted_title`, `extracted_summary`, "
                    "`extracted_key_facts_json`, `extracted_entities_json`, "
                    "`proposed_actions_json` (with any duplicate warnings "
                    "prepended), `confidence_level`, `analyzed_at`, and "
                    "`review_notes` (deep execution summary)."
                ),
                "scope": "One PATCH per processed row.",
            },
            {
                "name": "drugs · companies · deals · catalysts · drug_clinical_benchmarks · drug_intelligence_qa · company_documents · conversation_intelligence_intake",
                "kind": "Supabase tables",
                "via": "deep_execute_intelligence() → _db.sb_upsert() / _db.sb_patch()",
                "desc": (
                    "The Sonnet deep extraction pass (second Claude call) "
                    "sentence-by-sentence reads the submission and writes up to "
                    "eight entity types: new/updated companies, drugs (with "
                    "mechanism/target/stage/summary), clinical benchmarks, deals "
                    "(upfront + total value), catalyst_calendar entries, Q&A "
                    "insights keyed to question IDs, company_documents, and an "
                    "intake log in conversation_intelligence_intake. Drug IDs are "
                    "auto-slugged from the drug name. Existing records are patched "
                    "rather than duplicated (upsert pattern)."
                ),
                "scope": (
                    "Bounded by the number of entities mentioned in the submission. "
                    "A rich conference abstract might write ~5-15 rows across "
                    "tables; a simple URL submission might write 2-3. "
                    "Deep execution is non-fatal — a `try/except` logs but does "
                    "not re-raise, so a write failure does not prevent the "
                    "status PATCH."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Helpers & configuration",
            "note": "Module-level setup: credentials, Claude PromptConfigs, and thin Supabase wrappers.",
            "groups": [
                [
                    {
                        "function": "sb_patch(table, row_id, payload)",
                        "lines": 2,
                        "desc": (
                            "Thin shim over `_db.sb_patch()` that translates "
                            "the `row_id` string to an `{id: 'eq.<row_id>'}` "
                            "params dict."
                        ),
                    },
                    {
                        "function": "sb_list(table, select='*')",
                        "lines": 7,
                        "desc": (
                            "Full-table fetch via requests.get with "
                            "`Range: 0-9999`. Used only by `load_entities()` "
                            "for the companies and drugs reference tables."
                        ),
                    },
                ],
            ],
        },
        {
            "label": "URL validation & page fetch",
            "note": "Two functions that assess the source URL quality and retrieve its content.",
            "groups": [
                [
                    {
                        "function": "validate_url(url)",
                        "lines": 14,
                        "desc": (
                            "Sends a HEAD request (10s timeout, follow redirects). "
                            "Returns `(validation_status, http_status, source_name)` "
                            "where `source_name` is the domain of the final URL "
                            "after redirects. Timeouts and exceptions → "
                            "`('broken', 0, '')`."
                        ),
                    }
                ],
                [
                    {
                        "function": "fetch_page_text(url, max_chars=6000)",
                        "lines": 21,
                        "desc": (
                            "GETs the URL (15s, follow redirects), checks for "
                            "`text/html` or `text/plain` content type, strips "
                            "script/style tags and all HTML tags with regex, "
                            "collapses whitespace, and truncates to `max_chars`. "
                            "Returns empty string on any failure."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Entity lookup",
            "note": "Lazy-loaded entity reference tables used for fuzzy name matching.",
            "groups": [
                [
                    {
                        "function": "load_entities()",
                        "lines": 7,
                        "desc": (
                            "Populates module-level `_COMPANIES` and `_DRUGS` "
                            "from `sb_list()` if not already loaded. Called once "
                            "per run (lazy init pattern)."
                        ),
                    },
                    {
                        "function": "match_entity(name, entities, name_field)",
                        "lines": 12,
                        "desc": (
                            "Case-insensitive substring match: checks if "
                            "`name` appears in any entity's `name_field`, or "
                            "vice versa. Returns the entity's `id` on the first "
                            "match, or `None`."
                        ),
                    },
                ],
            ],
        },
        {
            "label": "Duplicate detection",
            "note": "check_duplicates() runs four independent dedup vectors and returns a risk rating.",
            "groups": [
                [
                    {
                        "function": "_kw(text)",
                        "lines": 8,
                        "desc": (
                            "Extracts meaningful keywords by lowercasing, "
                            "removing punctuation, and filtering out a 50-word "
                            "stopword list and words shorter than 3 chars."
                        ),
                    },
                    {
                        "function": "_overlap(a, b)",
                        "lines": 3,
                        "desc": (
                            "Jaccard-like overlap: `|a ∩ b| / min(|a|, |b|)`. "
                            "Values above 0.75 trigger a near-duplicate "
                            "title warning; above 0.65 triggers a similar "
                            "catalyst/deal warning."
                        ),
                    },
                ],
                [
                    {
                        "function": "check_duplicates(url, submitted_text, extraction)",
                        "lines": 73,
                        "desc": (
                            "Runs all four dedup vectors. Returns "
                            "`{is_duplicate, reasons, risk}` where risk is "
                            "'high' (≥ 2 reasons), 'medium' (1 reason), or "
                            "'low' (0 reasons). Used both to prepend "
                            "`reject_duplicate` actions to `proposed_actions_json` "
                            "and to override the Claude-assigned status."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Claude extraction (Pass 1 — Opus)",
            "note": "call_claude() is the first Claude call: structured entity extraction from URL + text + page content.",
            "groups": [
                [
                    {
                        "function": "call_claude(url, text, page_content)",
                        "lines": 12,
                        "desc": (
                            "Formats `EXTRACTION_PROMPT` with url, submitted_text, "
                            "and up to 3000 chars of page_content. Calls "
                            "`ai_client.run_json()` with the `claude-opus-4-6` "
                            "PromptConfig (max_tokens=1500). Returns the parsed "
                            "JSON dict or `None` on failure. The JSON schema "
                            "covers: extracted_title, extracted_summary, "
                            "source_type, extracted_key_facts, extracted_entities "
                            "(companies/drugs/targets/areas/deal_value/trial_ids), "
                            "intel_type, proposed_actions (action/table/rationale/"
                            "priority), confidence_level, bd_relevance, "
                            "duplicate_risk."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Deep intelligence execution (Pass 2 — Sonnet)",
            "note": "deep_execute_intelligence() drives a second Claude call that directly writes entities to the database.",
            "groups": [
                [
                    {
                        "function": "deep_execute_intelligence(row, extraction, url, text, page_content)",
                        "lines": 205,
                        "desc": (
                            "Formats `DEEP_EXTRACTION_PROMPT` with up to 4000 "
                            "chars of page_content. Calls `ai_client.run_json()` "
                            "with `claude-sonnet-4-6` (max_tokens=3000). The "
                            "JSON response schema covers 6 entity types: "
                            "companies, drugs (with mechanism/target/stage/summary/"
                            "key_data/competitor flags), clinical_data, deals, "
                            "catalysts (with date parsing for YYYY, YYYY-QN, "
                            "YYYY-MM-DD formats), and qa_insights (keyed to "
                            "integer question_id). Also writes a company_documents "
                            "row and a conversation_intelligence_intake row. "
                            "Returns a list of action strings for the "
                            "`review_notes` stamp."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Row processing & main loop",
            "note": "process_row() orchestrates the full pipeline for one row; main() drives the batch.",
            "groups": [
                [
                    {
                        "function": "process_row(row, dry_run=False)",
                        "lines": 127,
                        "desc": (
                            "Executes the 6-step pipeline for one row: "
                            "(1) validate URL, (2) fetch page, (3) Claude "
                            "extraction, (4) entity matching, (5) duplicate "
                            "check + status routing, (6a) deep entity writes, "
                            "(6b) PATCH row status. Deep execution runs for both "
                            "`analyzed` and `needs_review` statuses (not for "
                            "extraction failures). Prints a step-by-step log "
                            "with `│` prefix. Returns the `update` dict for "
                            "inspection."
                        ),
                    }
                ],
                [
                    {
                        "function": "main()",
                        "lines": 37,
                        "desc": (
                            "Parses `--dry-run`, `--id` (single row), and "
                            "`--limit` (default 20). Fetches new rows via "
                            "`sb_get()`. Calls `process_row()` for each with "
                            "a 1-second sleep between rows. Prints done summary."
                        ),
                    }
                ],
            ],
        },
    ],
}
