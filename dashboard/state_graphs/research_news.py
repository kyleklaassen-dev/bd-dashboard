"""
Detail content for the Research News StateGraph
(scripts/pipeline/research_news/ — runs as phases 1-5 of intelligence/research.py).

Unlike the static GitHub-workflow descriptions, the topology diagram on this
page is generated live from the compiled graph (see _topology.py) — only the
prose (summary, state-field meanings, node descriptions, routing rationale)
is hand-written here.
"""

STATE_GRAPH = {
    "key": "research_news",
    "name": "Research News",
    "module": "pipeline.research_news.graph",
    "builder": "build_research_news_graph",
    "entrypoint": "scripts/intelligence/research.py  (phases 1-5)",
    "summary": (
        "Nightly news-extraction sweep: pulls articles from RSS feeds, filters "
        "them down to ones relevant to tracked focus areas, drops anything "
        "already seen in the last week, fetches full article text for the "
        "survivors, sends them to Claude in batches to extract structured "
        "intel/deal/catalyst records, and writes everything to Supabase. "
        "Two early-exit branches mean a quiet night ends the run after the "
        "first or second node instead of doing pointless downstream work."
    ),
    "state": {
        "module": "pipeline.research_news.state",
        "class": "ResearchNewsState",
        "fields": [
            {"name": "hours_back",   "type": "int",  "desc": "Lookback window for the RSS sweep — defaults to 48 hours."},
            {"name": "dry_run",      "type": "bool", "desc": "When true, the run still fetches and extracts but skips the final Supabase write."},
            {"name": "company_map",  "type": "dict", "desc": "Company name → id lookup, threaded in from the caller so nodes don't re-fetch it."},
            {"name": "resolver",     "type": "Any",  "desc": "Identity resolver used to match article text back to tracked companies and drugs."},
            {"name": "articles",     "type": "list", "desc": "Raw articles pulled from the RSS feed list — output of fetch_feeds."},
            {"name": "relevant",     "type": "list", "desc": "Articles that matched a focus-area keyword (or came from a direct-source passthrough) — output of filter_relevant."},
            {"name": "existing_urls","type": "set",  "desc": "source_urls already present in `intel` from the last 7 days, used to drop repeats."},
            {"name": "new_articles", "type": "list", "desc": "Relevant articles not already seen — these are the ones that get full-text enrichment and sent to Claude."},
            {"name": "intel",        "type": "list", "desc": "Structured intel/deal/catalyst records extracted by Claude — output of extract_intel, input to write_intel."},
            {"name": "inserted_intel / inserted_deals / inserted_catalysts", "type": "int", "desc": "Row counts written to Supabase by the final node — the run's tangible output."},
            {"name": "errors",          "type": "list", "desc": "Per-node failure messages, namespaced as `[node_name] message`."},
            {"name": "nodes_completed", "type": "list", "desc": "Names of nodes that finished successfully, in execution order — the audit trail printed at the end of the run."},
        ],
    },
    "nodes": [
        {
            "name": "fetch_feeds",
            "file": "pipeline/research_news/nodes/fetch_feeds.py",
            "lines": 28,
            "desc": "Phase 1 — pulls articles from the configured RSS feed list for the last `hours_back` hours. Populates `state.articles`.",
        },
        {
            "name": "filter_relevant",
            "file": "pipeline/research_news/nodes/filter_relevant.py",
            "lines": 28,
            "desc": "Phase 2 — keeps articles that match a tracked focus-area keyword, or come from a direct-source passthrough list. Populates `state.relevant`.",
        },
        {
            "name": "dedup",
            "file": "pipeline/research_news/nodes/dedup.py",
            "lines": 31,
            "desc": "Phase 3 — drops any relevant article whose source_url is already present in `intel` from the last 7 days. Populates `state.new_articles` and `state.existing_urls`.",
        },
        {
            "name": "enrich_full_text",
            "file": "pipeline/research_news/nodes/enrich_full_text.py",
            "lines": 29,
            "desc": "Phase 4 — fetches the full article body for high-priority new articles, tagging each entry in `state.new_articles` with `full_text` in place.",
        },
        {
            "name": "extract_intel",
            "file": "pipeline/research_news/nodes/extract_intel.py",
            "lines": 86,
            "desc": (
                "Phase 5a — batches new articles and sends them to Claude via "
                "`ai_client.run_text()` (prompt lives in `ai/prompts/research_news.py`), "
                "then parses the JSON-array response into structured records, "
                "accumulating them into `state.intel`. The one node in this graph "
                "that talks to an LLM — and the reason this pipeline exists as a "
                "StateGraph rather than a plain script: it was the rewrite that "
                "moved this call off a raw `anthropic.Anthropic()` client and onto "
                "the shared `ai/` infrastructure layer."
            ),
        },
        {
            "name": "write_intel",
            "file": "pipeline/research_news/nodes/write_intel.py",
            "lines": 28,
            "desc": "Phase 5b — writes the extracted intel/deal/catalyst records to Supabase, resolving company/drug references via `state.company_map` and `state.resolver`.",
        },
    ],
    "routing": [
        {
            "after": "filter_relevant",
            "function": "_route_after_filter",
            "branches": [
                {"condition": "`state.relevant` is empty", "to": "END",
                 "desc": "Nothing matched a tracked focus area — the run ends here rather than deduping, enriching, and extracting an empty list."},
                {"condition": "otherwise", "to": "dedup",
                 "desc": "At least one relevant article exists — continue to dedup."},
            ],
        },
        {
            "after": "dedup",
            "function": "_route_after_dedup",
            "branches": [
                {"condition": "`state.new_articles` is empty", "to": "END",
                 "desc": "Every relevant article was already captured in the last week — nothing new to enrich, extract, or write."},
                {"condition": "otherwise", "to": "enrich_full_text",
                 "desc": "New articles exist — continue to full-text enrichment, extraction, and write."},
            ],
        },
    ],
}
