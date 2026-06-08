"""
Static description of the Competitor Pipeline Monitor pipeline
(.github/workflows/daily-pipeline-monitor.yml).

Nightly hash-based change detection for ~30 competitor pipeline pages.
On any change it fires a signals row + a discovery_queue row for human review.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "pipeline_monitor",
    "workflow_name": "Competitor Pipeline Monitor",
    "workflow_file": ".github/workflows/daily-pipeline-monitor.yml",
    "schedule": "Daily 05:00 UTC (1:00 AM ET) — quiet window before the 6 AM enrichment runs",
    "entrypoint": "scripts/intelligence/pipeline_monitor.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Nightly watchdog for competitor pipeline pages. For each of ~30 "
        "hardcoded company pipeline URLs (spanning TL1A/IBD, FcRn, TSLP, "
        "IL-4Ra, and T-cell engineering competitors), it fetches the page, "
        "strips HTML to visible text, and computes a SHA-256 hash. Previous "
        "hashes are stored as `pipeline_page_hash` signals in Supabase. On "
        "first visit a baseline is set; on any subsequent content change it "
        "fires a `pipeline_page_change` signal and queues a re-audit in "
        "`discovery_queue`. Pages that are JavaScript-rendered shells "
        "(< 100 chars after stripping) are skipped with a warning — the "
        "hash would be meaningless."
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
        label="pipeline_monitor.py · run()\n(entrypoint — loads hashes, iterates companies)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    stored_hashes [
        label="Supabase\nsignals (pipeline_page_hash)\n(read — most recent hash per company)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    pipeline_pages [
        label="~30 company pipeline pages\n(HTTP GET, raw HTML fetch)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_per_company {
        label="Per company: fetch → hash → compare"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        fetch [label="_fetch_page()\nGET + _extract_text()\n(strip HTML, normalise whitespace)"]
        hash_node [label="_hash_content()\nSHA-256 of visible text"]
        compare [label="compare vs stored\n→ NEW / UNCHANGED / CHANGED"]
    }

    subgraph cluster_on_change {
        label="On CHANGED: fire signal + queue re-audit"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        fire_signal [label="_fire_change_signal()\nsignal_type=pipeline_page_change"]
        queue_reaudit [label="_queue_reaudit()\ndiscovery_queue row"]
    }

    signals_hash [
        label="Supabase\nsignals (pipeline_page_hash)\n(upsert new hash — always)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    signals_change [
        label="Supabase\nsignals (pipeline_page_change)\n(insert — changed only)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    discovery_out [
        label="Supabase\ndiscovery_queue\n(insert — changed only)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    entry -> stored_hashes [label="  _load_stored_hashes()", style="bold", color="#c9890a", fontcolor="#c9890a"]
    pipeline_pages -> fetch [label="  GET per company", style="bold", color="#c9890a", fontcolor="#c9890a"]
    fetch -> hash_node
    hash_node -> compare
    stored_hashes -> compare [label="  prev hash"]
    compare -> fire_signal [label="  CHANGED"]
    compare -> queue_reaudit [label="  CHANGED"]
    compare -> signals_hash [label="  always (NEW or CHANGED)", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    fire_signal -> signals_change [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    queue_reaudit -> discovery_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        hashes_in [label="Supabase\nsignals (pipeline_page_hash)\nprevious hash per company", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        pages_in [label="~30 company pipeline pages\n(HTTP GET, raw HTML)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Competitor\nPipeline Monitor",
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

        hash_out [label="Supabase\nsignals (pipeline_page_hash)\nupdated hash (NEW + CHANGED)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        change_out [label="Supabase\nsignals (pipeline_page_change)\n(CHANGED companies only)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        dq_out [label="Supabase\ndiscovery_queue\n(CHANGED companies only)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    hashes_in -> pipeline
    pages_in -> pipeline
    pipeline -> hash_out
    pipeline -> change_out
    pipeline -> dq_out
}
""",
    "io": {
        "reads": [
            {
                "name": "signals (pipeline_page_hash rows)",
                "kind": "Supabase table",
                "via": "_load_stored_hashes() → sb_get('signals', {signal_type: 'eq.pipeline_page_hash', order: 'created_at.desc', limit: '500'})",
                "desc": (
                    "Fetches the most-recent `pipeline_page_hash` signal row per "
                    "company from the `signals` table. The hash is stored in "
                    "`content_hash`, `source_url` carries the pipeline page URL, "
                    "and `company_id` is the lookup key. Using signals for hash "
                    "storage avoids a schema migration on the companies table while "
                    "keeping the audit trail intact."
                ),
                "scope": (
                    "One query, ordered `created_at DESC`, limit 500. The function "
                    "keeps only the first (most recent) row per `company_id` — "
                    "earlier hash rows are left in place as an implicit history."
                ),
            },
            {
                "name": "~30 company pipeline pages",
                "kind": "External HTTP pages",
                "via": "_fetch_page() → urllib.request.urlopen()",
                "desc": (
                    "For each company in `PIPELINE_URLS`, fetches the pipeline "
                    "page with a 15-second timeout and a Meridian user-agent. "
                    "The raw HTML is stripped to visible text by "
                    "`_extract_text()` (which strips script/style/head/noscript "
                    "tags and normalises whitespace). Returns `None` on error."
                ),
                "scope": (
                    "One GET per company, ~30 total. Pages returning < 100 "
                    "visible chars after stripping are treated as JS-rendered "
                    "shells and skipped (hash would be unstable). Connection "
                    "errors are caught and logged as 'error' results — they "
                    "don't abort the run."
                ),
            },
        ],
        "cleaning": (
            "**Two thresholds gate writes.** First, pages with < 100 characters "
            "of visible text are skipped entirely — they indicate a JavaScript-"
            "rendered shell where the hash would be meaningless (changes would "
            "fire on every CDN cache miss, not on content changes). Second, "
            "`_extract_text()` normalises all whitespace runs to single spaces "
            "before hashing so minor layout changes (extra newlines, spacing "
            "tweaks) do not register as content changes. Baseline runs (first "
            "time a company is seen) store the hash but do not fire a change "
            "signal — there is nothing to compare against."
        ),
        "writes": [
            {
                "name": "signals (pipeline_page_hash)",
                "kind": "Supabase table",
                "via": "_store_hash() → sb_post('signals', {...})",
                "desc": (
                    "Inserts a new `pipeline_page_hash` row whenever a page is "
                    "successfully fetched — both on first visit (baseline) and "
                    "on any subsequent visit whether or not the content changed. "
                    "This creates an implicit hash history for each company. "
                    "`relevance_score=0` and `enrichment_triggered=False` since "
                    "hash rows are not signals in the BD sense."
                ),
                "scope": (
                    "One insert per successfully-fetched company per run — "
                    "up to ~30 rows. UNCHANGED companies still get a new hash row "
                    "to confirm the page was checked today."
                ),
            },
            {
                "name": "signals (pipeline_page_change)",
                "kind": "Supabase table",
                "via": "_fire_change_signal() → sb_post('signals', {signal_type: 'pipeline_page_change', ...})",
                "desc": (
                    "Inserts a `pipeline_page_change` signal row when a page's "
                    "hash differs from the stored baseline. `relevance_score=6` "
                    "(medium-high — warrants review but not auto-enrichment). "
                    "Headline: 'Pipeline page changed: {company_id} — review "
                    "for new/updated programs'."
                ),
                "scope": (
                    "At most one per changed company per run. Typically zero to a "
                    "handful per day — most pages are stable day-over-day."
                ),
            },
            {
                "name": "discovery_queue",
                "kind": "Supabase table",
                "via": "_queue_reaudit() → sb_post('discovery_queue', {...})",
                "desc": (
                    "Inserts a discovery_queue row prompting a pipeline re-audit "
                    "for the changed company. Sets `source='pipeline_monitor'`, "
                    "`status='pending'`, `suggested_dest='update_company'`, and "
                    "a `why_discovered` string with the re-audit command to run. "
                    "Area_id is set to a placeholder ('tcell') since the re-audit "
                    "will re-score all areas."
                ),
                "scope": (
                    "One row per changed company per run. The analyst reviews "
                    "this queue item to decide whether to run the re-audit command "
                    "or dismiss the change as cosmetic."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "HTML text extraction & hashing",
            "note": "Two pure functions used to convert raw HTML to a stable fingerprint.",
            "groups": [
                [
                    {
                        "function": "_TextExtractor (HTMLParser subclass)",
                        "lines": 29,
                        "desc": (
                            "Custom `HTMLParser` subclass that collects visible "
                            "text chunks while skipping `script`, `style`, `head`, "
                            "`noscript`, `meta`, and `link` tags (and their "
                            "content). Tracks skip depth to handle nested skip "
                            "tags. `get_text()` joins chunks with spaces."
                        ),
                    }
                ],
                [
                    {
                        "function": "_extract_text(html)",
                        "lines": 10,
                        "desc": (
                            "Feeds `html` through `_TextExtractor` and normalises "
                            "all whitespace runs to single spaces. Falls back to "
                            "returning `html` unchanged on parse error. This "
                            "normalisation is what prevents minor layout changes "
                            "from registering as content changes."
                        ),
                    },
                    {
                        "function": "_hash_content(text)",
                        "lines": 2,
                        "desc": (
                            "SHA-256 of the UTF-8-encoded text. Used as the "
                            "ground-truth fingerprint stored in `content_hash`. "
                            "Any change to visible text on the page — a new drug "
                            "added, a stage advanced, a program removed — "
                            "changes this hash."
                        ),
                    },
                ],
            ],
        },
        {
            "label": "Hash storage helpers",
            "note": "Read and write helpers for the pipeline_page_hash signals that serve as persistent state.",
            "groups": [
                [
                    {
                        "function": "_load_stored_hashes()",
                        "lines": 22,
                        "desc": (
                            "Queries signals for all `pipeline_page_hash` rows "
                            "(limit 500, ordered desc). Returns a dict keyed by "
                            "`company_id`, keeping only the most-recent row per "
                            "company (first seen wins when iterating desc order). "
                            "This is the 'previous state' the current fetch is "
                            "compared against."
                        ),
                    }
                ],
                [
                    {
                        "function": "_store_hash(company_id, pipeline_url, new_hash, dry_run)",
                        "lines": 15,
                        "desc": (
                            "Inserts a new `pipeline_page_hash` signal row with "
                            "the current hash. Called for both NEW and CHANGED "
                            "companies — UNCHANGED companies also get a fresh row "
                            "confirming the page was checked. No-ops in dry-run "
                            "mode."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Change event writers",
            "note": "Two functions called only when a hash mismatch is detected.",
            "groups": [
                [
                    {
                        "function": "_fire_change_signal(company_id, pipeline_url, dry_run)",
                        "lines": 21,
                        "desc": (
                            "Inserts a `pipeline_page_change` signal with "
                            "`relevance_score=6`. Logs success or write failure. "
                            "In dry-run mode prints the action without writing."
                        ),
                    }
                ],
                [
                    {
                        "function": "_queue_reaudit(company_id, pipeline_url, run_id, dry_run)",
                        "lines": 33,
                        "desc": (
                            "Inserts a `discovery_queue` row with "
                            "`source='pipeline_monitor'`, `status='pending'`, and "
                            "a `why_discovered` string that includes the re-audit "
                            "command the analyst should run. `run_id` (a "
                            "timestamp slug like `pipeline_monitor_20260608_0500`) "
                            "is stored in `discovery_run_id` for traceability."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Page fetch",
            "note": "_fetch_page() is the HTTP client — returns normalised visible text or None.",
            "groups": [
                [
                    {
                        "function": "_fetch_page(url, timeout=15)",
                        "lines": 28,
                        "desc": (
                            "GETs the URL with a Meridian user-agent header. "
                            "Decodes the response as UTF-8 (errors='replace') and "
                            "calls `_extract_text()`. Returns `None` on any "
                            "exception — connection errors, timeouts, and HTTP "
                            "errors are all caught and silently returned as None. "
                            "The caller (`run()`) logs the error and increments "
                            "the error counter."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main monitor loop",
            "note": "run() iterates the PIPELINE_URLS dict and dispatches to the appropriate handler for each.",
            "groups": [
                [
                    {
                        "function": "run(dry_run=False, company_filter=None)",
                        "lines": 75,
                        "desc": (
                            "Builds a `run_id` timestamp slug. Calls "
                            "`_load_stored_hashes()`. Optionally filters "
                            "`PIPELINE_URLS` to a single company via "
                            "`--company`. For each company: calls `_fetch_page()`, "
                            "skips if None or < 100 chars (JS shell), computes "
                            "`_hash_content()`, compares to stored hash, then "
                            "dispatches: NEW → store baseline, UNCHANGED → log "
                            "only, CHANGED → fire signal + queue re-audit + "
                            "store new hash. Prints a summary: unchanged / changed "
                            "/ new / errors."
                        ),
                    }
                ],
            ],
        },
    ],
}
