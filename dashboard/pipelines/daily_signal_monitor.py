"""
Static description of the Signal Monitor pipeline
(.github/workflows/daily-signal-monitor.yml).

Lightweight quad-hourly scanner: no LLM, no enrichment. Detects biotech
events from 4 RSS feeds and ClinicalTrials.gov updates, scores relevance
heuristically, and (for score >= 8) triggers targeted Tier 2 enrichment.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "signal_monitor",
    "workflow_name": "Signal Monitor",
    "workflow_file": ".github/workflows/daily-signal-monitor.yml",
    "schedule": "4x/day at 02:30, 06:30, 12:30, 18:30 UTC — catches news cycles across time zones",
    "entrypoint": "scripts/intelligence/signal_monitor.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Tier 1 signal scanner — fast, cheap, no LLM. Four times per day it "
        "fetches RSS from FDA, FierceBiotech, BioPharma Dive, and STAT News, "
        "then polls ClinicalTrials.gov for status updates on every tracked "
        "trial. Each headline is scored 0–10 by heuristic keyword matching "
        "against the Meridian watchlist (company aliases, drug names, disease "
        "area keywords, deal/phase language). Relevant signals (score > 0) are "
        "deduplicated on a content hash and written to `signals`. "
        "High-relevance signals (score ≥ 8) automatically enqueue targeted "
        "Tier 2 enrichment rows in `enrichment_queue` — this is the mechanism "
        "that makes a competitor press release trigger a full pipeline update "
        "within hours, not days."
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
        label="signal_monitor.py · run()\n(entrypoint — loads watchlist, fetches, scores, writes)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    supabase_in [
        label="Supabase\ncompanies · company_areas · company_aliases\ndrug_aliases · drugs · trials\n(read here — watchlist + tracked trials)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    rss_sources [
        label="RSS feeds\nFDA · FierceBiotech\nBioPharma Dive · STAT News",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    ctgov_api [
        label="ClinicalTrials.gov\nv2 API (batches of 20 NCTs)\nlastUpdatePostDate filter",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_load {
        label="Phase 1 — load watchlist + tracked trials"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        watchlist [label="load_watchlist()\nco_names / co_areas / alias_map\ndrug_alias_set"]
        trials [label="load_tracked_trials()\nNCT → {drug_id, company_id}"]
    }

    subgraph cluster_collect {
        label="Phase 2 — collect candidates"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        fetch_rss [label="fetch_rss() × 4 sources\nparse XML, filter by --since"]
        fetch_ct [label="fetch_ct_updates()\nbatch query NCT IDs"]
    }

    subgraph cluster_score {
        label="Phase 3 — score, dedup, write"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        score [label="score_signal()\ncompany + drug + disease\n+ signal-type bonus → 0-10"]
        dedup [label="write_signal()\ncontent_hash dedup\n→ skip or insert"]
        tier2 [label="enqueue_enrichment()\nscore >= 8 + matched company\n→ enrichment_queue rows"]
    }

    signals_out [
        label="Supabase\nsignals\n(insert, dedup on content_hash)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    enrich_out [
        label="Supabase\nenrichment_queue\n(insert, skip if pending exists)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    entry -> supabase_in [label="  reads watchlist + trials", style="bold", color="#c9890a", fontcolor="#c9890a"]
    supabase_in -> watchlist
    supabase_in -> trials
    rss_sources -> fetch_rss [label="  XML fetch", style="bold", color="#c9890a", fontcolor="#c9890a"]
    ctgov_api -> fetch_ct [label="  batch NCT query", style="bold", color="#c9890a", fontcolor="#c9890a"]
    watchlist -> score
    trials -> fetch_ct
    fetch_rss -> score
    fetch_ct -> score
    score -> dedup
    dedup -> signals_out [label="  new signals only", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    dedup -> tier2 [label="  score >= 8"]
    tier2 -> enrich_out [label="  skip if pending", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        sb_in [label="Supabase\ncompanies · company_areas · company_aliases\ndrug_aliases · drugs · trials", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        rss_in [label="RSS feeds\nFDA · FierceBiotech · BioPharma Dive · STAT News", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        ct_in [label="ClinicalTrials.gov\nv2 API (tracked NCTs)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Signal\nMonitor",
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

        signals_out [label="Supabase\nsignals\n(new rows, dedup on content_hash)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        enrich_out [label="Supabase\nenrichment_queue\n(score >= 8 only)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    rss_in -> pipeline
    ct_in -> pipeline
    pipeline -> signals_out
    pipeline -> enrich_out
}
""",
    "io": {
        "reads": [
            {
                "name": "companies · company_areas · company_aliases · drug_aliases · drugs",
                "kind": "Supabase tables",
                "via": "load_watchlist() → sb_get()",
                "desc": (
                    "`load_watchlist()` builds the in-memory scoring structures. "
                    "It fetches all non-acquired companies (limit 200), their "
                    "`company_areas` memberships (limit 1000), and all "
                    "`company_aliases` (limit 1000) to build a lowercased "
                    "`alias_map` that maps any alias string to its company_id. "
                    "It also fetches `drug_aliases` (limit 2000) and "
                    "`drugs.display_name` + `drugs.name` (limit 2000) to build "
                    "a `drug_alias_set` for drug-name headline matching."
                ),
                "scope": (
                    "Five table reads, all at module load time (once per run). "
                    "Alias matching uses word-boundary regexes for short strings "
                    "(< 8 chars) and substring matching for longer ones. "
                    "Aliases shorter than 4 characters are silently skipped to "
                    "avoid false positives."
                ),
            },
            {
                "name": "trials · drugs",
                "kind": "Supabase tables",
                "via": "load_tracked_trials() → sb_get()",
                "desc": (
                    "Loads all `trials` rows that have an NCT-format ID "
                    "(limit 2000), then joins to `drugs` (limit 2000) to "
                    "resolve each trial's `company_id` via `drug_id`. "
                    "Returns a `nct_id → {drug_id, company_id}` dict used by "
                    "`fetch_ct_updates()` to annotate CT.gov updates with a "
                    "pre-identified company."
                ),
                "scope": (
                    "Two full-table reads; result is an in-memory lookup dict. "
                    "Capped at 200 NCT IDs per CT.gov batch query to stay within "
                    "URL length limits."
                ),
            },
            {
                "name": "RSS feeds — FDA, FierceBiotech, BioPharma Dive, STAT News",
                "kind": "External RSS/XML feeds",
                "via": "fetch_rss() → urllib.request.urlopen()",
                "desc": (
                    "Each `fetch_rss()` call fetches the feed XML, parses "
                    "`<item>` elements, strips HTML from titles "
                    "(`_extract_title_from_html()`), parses `pubDate` "
                    "(`_parse_date()`), and filters items older than `--since` "
                    "(default: 2 days ago). Returns a list of "
                    "`{headline, source_url, event_date, signal_type, "
                    "source_name}` dicts."
                ),
                "scope": (
                    "One HTTP GET per feed; no pagination (RSS feeds are always "
                    "the full recent feed). A fetch failure returns an empty list "
                    "and logs the error — one broken feed does not abort the run."
                ),
            },
            {
                "name": "ClinicalTrials.gov v2 API",
                "kind": "External API",
                "via": "fetch_ct_updates() → urllib.request.urlopen()",
                "desc": (
                    "Batches tracked NCT IDs into groups of 20 and queries "
                    "`/api/v2/studies` with an AREA[LastUpdatePostDate] range "
                    "filter. Returns synthetic signal dicts for any tracked "
                    "trial whose CT.gov record was updated since `--since`. "
                    "Fields captured: `briefTitle`, `overallStatus`, "
                    "`primaryCompletionDate`, `lastUpdatePostDate`."
                ),
                "scope": (
                    "ceil(N/20) requests where N = number of tracked trials "
                    "(capped at 200 total). `time.sleep(0.3)` between batches "
                    "to avoid rate-limiting. A batch error is logged and skipped "
                    "rather than aborting the run."
                ),
            },
        ],
        "cleaning": (
            "**Content-hash deduplication prevents the same story from flooding "
            "the signals table across runs.** `_content_hash()` builds an MD5 "
            "of `company_id + headline[:100] + event_date` — so the same "
            "headline on the same day for the same company is always one row, "
            "regardless of which run first saw it. `write_signal()` checks "
            "for an existing row with that hash before inserting. "
            "Score-zero items are dropped entirely — they matched no keyword "
            "in any category. CLI filters (`--company`, `--area`) are applied "
            "after scoring but before writing, so they narrow the output set "
            "without affecting the score logic. `--dry-run` scores and logs "
            "everything but writes nothing, returning a `'dry-run-id'` sentinel "
            "instead of a real signal_id so `enqueue_enrichment()` is also "
            "skipped."
        ),
        "writes": [
            {
                "name": "signals",
                "kind": "Supabase table",
                "via": "write_signal() → sb_insert('signals', rec)",
                "desc": (
                    "One inserted row per new, relevant, non-duplicate signal. "
                    "Columns: `company_id`, `signal_type` (fda / press_release / "
                    "trial_update), `headline` (≤ 400 chars), `raw_headline`, "
                    "`source_url`, `content_hash`, `event_date`, "
                    "`relevance_score` (0–10), `source_name`, and "
                    "`enrichment_triggered=False` (updated to True by "
                    "`enqueue_enrichment()` when applicable). "
                    "Signals with `score == 0` are never written."
                ),
                "scope": (
                    "Bounded by the number of non-duplicate relevant headlines "
                    "across all four RSS feeds plus CT.gov updates, filtered to "
                    "the `--since` window (default 2 days). A typical run inserts "
                    "a handful to low double-digits of new signals."
                ),
            },
            {
                "name": "enrichment_queue",
                "kind": "Supabase table",
                "via": "enqueue_enrichment() → sb_insert('enrichment_queue', rec)",
                "desc": (
                    "One row per area for each company matched by a high-relevance "
                    "signal (score ≥ 8). Each row carries `company_id`, `area_id`, "
                    "`trigger='signal'`, `signal_id`, `priority` (= the score), "
                    "and `status='pending'`. These rows are the Tier 1 → Tier 2 "
                    "handoff: they drive targeted enrichment of the matched "
                    "company's pipeline profile in the areas it competes."
                ),
                "scope": (
                    "At most one row per (company_id, area_id) pair per run — "
                    "`enqueue_enrichment()` checks for an existing `pending` row "
                    "and skips if one already exists. A company active in three "
                    "areas would get three rows; a company in one area gets one."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Watchlist & trial loading",
            "note": "Two loaders that build the in-memory scoring inputs. Both run once at the start of run().",
            "groups": [
                [
                    {
                        "function": "load_watchlist()",
                        "lines": 48,
                        "desc": (
                            "Loads five Supabase tables in sequence to build four "
                            "scoring structures: `co_names` (company_id → name), "
                            "`co_areas` (company_id → set of area_ids), "
                            "`alias_map` (any alias / name / id → company_id), "
                            "and `drug_alias_set` (all drug display names + alias "
                            "strings, lowercased). Logs the counts so the run log "
                            "shows how large each structure is."
                        ),
                    }
                ],
                [
                    {
                        "function": "load_tracked_trials()",
                        "lines": 18,
                        "desc": (
                            "Loads `trials` (NCT IDs) and `drugs` (drug_id → "
                            "company_id) and returns a dict keyed by NCT ID. "
                            "Only includes rows whose `id` starts with 'NCT'. "
                            "Resolves `company_id` via `drug_id` so that "
                            "`fetch_ct_updates()` can annotate each CT.gov "
                            "update with a pre-identified company."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "RSS fetching & date parsing",
            "note": "Two helpers that fetch and parse RSS feeds.",
            "groups": [
                [
                    {
                        "function": "fetch_rss(source, since_date=None)",
                        "lines": 51,
                        "desc": (
                            "Fetches an RSS feed via `urllib.request`, parses XML, "
                            "strips HTML from `<title>` elements "
                            "(`_extract_title_from_html()`), falls back to "
                            "`<description>` if title is empty, and applies the "
                            "`since_date` filter via `_parse_date()`. Returns a "
                            "list of dicts; returns `[]` on any fetch or parse "
                            "error (non-fatal)."
                        ),
                    }
                ],
                [
                    {
                        "function": "_extract_title_from_html(raw_title)",
                        "lines": 5,
                        "desc": (
                            "Strips HTML tags with a regex and unescapes common "
                            "HTML entities. Handles FierceBiotech's anchor-embedded "
                            "titles."
                        ),
                    },
                    {
                        "function": "_parse_date(raw)",
                        "lines": 25,
                        "desc": (
                            "Attempts to parse an RSS pubDate string through five "
                            "strptime format patterns, then falls back to a regex "
                            "extraction of day/month/year. Returns a "
                            "`datetime.date` or `None`."
                        ),
                    },
                ],
            ],
        },
        {
            "label": "ClinicalTrials.gov update scan",
            "note": "fetch_ct_updates() polls tracked NCT IDs for recent status changes.",
            "groups": [
                [
                    {
                        "function": "fetch_ct_updates(tracked_trials, since_date)",
                        "lines": 71,
                        "desc": (
                            "Batches tracked NCT IDs into groups of 20, queries "
                            "the CT.gov v2 API with an AREA[LastUpdatePostDate] "
                            "range filter, and synthesises signal dicts for "
                            "matched studies. Annotates each result with the "
                            "pre-resolved `company_id` from the tracked_trials "
                            "dict. Sleeps 0.3s between batches. Returns an empty "
                            "list if `tracked_trials` is empty."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Relevance scoring",
            "note": "score_signal() is the entire heuristic — no LLM.",
            "groups": [
                [
                    {
                        "function": "score_signal(headline, source_url, signal_type, watchlist)",
                        "lines": 60,
                        "desc": (
                            "Scores 0–10 by accumulating points across four "
                            "independent categories: company alias match (+3, "
                            "word-boundary for short aliases), drug alias match "
                            "(+3, same pattern), disease area keyword match (+2), "
                            "and signal-type bonus (+1-2 depending on type and "
                            "whether deal/phase keywords appear in the headline). "
                            "Returns `(min(score, 10), matched_company_id | None)`. "
                            "The `TIER2_THRESHOLD = 8` constant gates enrichment "
                            "dispatch."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Signal write & enrichment dispatch",
            "note": "write_signal() and enqueue_enrichment() are the two write paths.",
            "groups": [
                [
                    {
                        "function": "_content_hash(co_id, headline, event_date)",
                        "lines": 3,
                        "desc": (
                            "MD5 of `co_id + headline[:100] + event_date`. "
                            "Used as the deduplication key in `write_signal()`."
                        ),
                    }
                ],
                [
                    {
                        "function": "write_signal(item, company_id, relevance_score, dry_run)",
                        "lines": 29,
                        "desc": (
                            "Computes the content hash, checks for an existing "
                            "signals row with that hash (`sb_get` with limit=1), "
                            "and returns `None` if a duplicate is found. Otherwise "
                            "inserts a new signals row and returns the inserted "
                            "`id`. In dry-run mode returns `'dry-run-id'` without "
                            "writing."
                        ),
                    }
                ],
                [
                    {
                        "function": "enqueue_enrichment(company_id, area_ids, signal_id, priority, dry_run)",
                        "lines": 29,
                        "desc": (
                            "For each area_id in the company's tracked areas, "
                            "checks whether a `pending` enrichment_queue row "
                            "already exists for that (company_id, area_id) pair. "
                            "If not, inserts a new row with `trigger='signal'`, "
                            "`signal_id`, and `priority` = the relevance score. "
                            "Returns the count of newly enqueued rows."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main scan loop",
            "note": "run() owns the full scan lifecycle and prints the summary.",
            "groups": [
                [
                    {
                        "function": "run(args)",
                        "lines": 90,
                        "desc": (
                            "Resolves CLI args (`--dry-run`, `--company`, "
                            "`--area`, `--since`, `--verbose`). Loads watchlist "
                            "and tracked trials. Fetches all four RSS feeds then "
                            "CT.gov updates, concatenates into `all_items`. "
                            "For each item: pops the `_co_id_hint` pre-resolved "
                            "by CT.gov, calls `score_signal()`, applies CLI "
                            "filters, calls `write_signal()`, and if score ≥ 8 "
                            "and a company matched, calls `enqueue_enrichment()`. "
                            "Prints a final stats block: scanned / relevant / "
                            "new signals / dedup skipped / Tier 2 queued."
                        ),
                    }
                ],
            ],
        },
    ],
}
