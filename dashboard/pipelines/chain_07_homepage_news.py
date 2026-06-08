"""
Static description of the Meridian Homepage News pipeline
(.github/workflows/chain-07-fetch-homepage-news.yml).

Documents what the single entrypoint script does — fetching RSS articles from
trusted biotech sources, scoring and entity-matching each article, validating
URLs, generating Claude summaries for high-priority articles, and writing
the results to the news_articles table for display on the Meridian homepage.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "homepage_news",
    "workflow_name": "Meridian Homepage News",
    "workflow_file": ".github/workflows/chain-07-fetch-homepage-news.yml",
    "schedule": (
        "Event-driven (after Meridian Research succeeds, runs in parallel "
        "with Source Verifier chain) + daily 07:30 UTC fallback"
    ),
    "entrypoint": "scripts/intelligence/fetch_homepage_news.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Nightly homepage news intelligence sweep: fetches articles from three "
        "trusted biotech RSS sources (FierceBiotech, BioPharma Dive, STAT News), "
        "deduplicates by URL and content hash, scores each article 0-100 using a "
        "deterministic formula (source quality + entity match + keyword signals), "
        "validates article URLs with a HEAD check, and generates Claude Haiku "
        "summaries for high-scoring articles (score >= 40). "
        "Results are upserted to `news_articles` for the Meridian homepage. "
        "Runs in parallel with the Source Verifier chain — both are triggered "
        "by Meridian Research completing."
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
        label="fetch_homepage_news.py\n(entrypoint — run())",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    subgraph cluster_reads {
        label="Reads at startup"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        watchlist_in [
            label="Supabase\ncompany_aliases · companies ·\ndrugs\n(entity watchlist)",
            shape=cylinder,
            fillcolor="#ffe4b8",
            color="#c9890a",
            fontcolor="#111827",
            fontsize=10,
            margin="0.22,0.14"
        ]
    }

    step1  [label="Step 1\nRefresh is_this_week / is_today flags\n(expire stale rows)"]

    step3  [label="Step 3\nfetch_rss() x3\n(FierceBiotech + BioPharma Dive + STAT)"]

    rss_in [
        label="RSS Feeds\n(FierceBiotech · BioPharma Dive · STAT News)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    step4  [label="Step 4\nDedup by URL hash + content hash"]

    step5  [label="Step 5\nscore_article()\nentity match + keyword signals\n0-100 score"]

    step6  [label="Step 6\nvalidate_url()\nHTTP HEAD per article URL"]

    http_ext [
        label="External HTTP\n(HEAD per article URL)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    step7  [label="Step 7\ngenerate_summary()\nClaude Haiku for score >= 40\n(optional, --no-claude skips)"]

    claude_api [
        label="Claude API\nclaude-haiku-4-5\n(headline + context -> summary)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    step8  [label="Step 8\nCompute is_today / is_this_week flags"]

    step9  [label="Step 9\nUpsert to news_articles\n(skip invalid-URL articles)"]

    news_articles [
        label="Supabase\nnews_articles\n(upsert on url_hash)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    news_flags [
        label="Supabase\nnews_articles\n(is_this_week / is_today refreshed)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    entry -> watchlist_in [label="  load watchlist", style="bold", color="#c9890a", fontcolor="#c9890a"]
    entry -> step1
    step1 -> news_flags [label="  PATCH expired flags", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    watchlist_in -> step5 [label="  alias/drug maps"]
    entry -> step3
    rss_in -> step3 [label="  GET feed", style="bold", color="#c9890a", fontcolor="#c9890a"]
    step3 -> step4 -> step5 -> step6 -> step7 -> step8 -> step9
    step6 -> http_ext [label="  HEAD", style="bold", color="#c9890a", fontcolor="#c9890a"]
    step7 -> claude_api [label="  summarise", style="bold", color="#c9890a", fontcolor="#c9890a"]
    step9 -> news_articles [label="  upsert", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        rss_in [label="RSS feeds\n(FierceBiotech · BioPharma Dive · STAT News)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        sb_in [label="Supabase\ncompany_aliases · companies · drugs\n(entity watchlist)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        http_in [label="External HTTP\n(HEAD per article URL, 0.1s throttle)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        claude_in [label="Claude API\nHaiku — article summaries\n(score >= 40 only)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Homepage\nNews",
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

        news_out [label="Supabase\nnews_articles\n(upsert on url_hash)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        flags_out [label="Supabase\nnews_articles\n(is_this_week / is_today refreshed)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    rss_in -> pipeline
    sb_in -> pipeline
    http_in -> pipeline
    claude_in -> pipeline
    pipeline -> news_out
    pipeline -> flags_out
}
""",
    "io": {
        "reads": [
            {
                "name": "company_aliases · companies · drugs",
                "kind": "Supabase tables",
                "via": "load_watchlist() — three sb_get calls at startup",
                "desc": (
                    "Builds the entity watchlist used by `score_article()`. "
                    "`company_aliases` provides alias-to-company_id mappings "
                    "(up to 500); `companies` adds canonical company names filtered "
                    "to non-acquired companies (up to 200); `drugs` adds name, "
                    "display_name, and brand_name for all drugs (up to 500, "
                    "minimum 5-char names to avoid false-positive matches). "
                    "The resulting alias_map and drug_alias_set are used for entity "
                    "matching during scoring."
                ),
                "scope": (
                    "Three queries at startup, results held in memory for the "
                    "entire run."
                ),
            },
            {
                "name": "RSS feeds (FierceBiotech · BioPharma Dive · STAT News)",
                "kind": "External RSS / HTTP",
                "via": "fetch_rss(source, since_date) — urllib.request GET per feed",
                "desc": (
                    "Three RSS feeds are fetched sequentially with 0.5s between each. "
                    "Each feed is XML-parsed (ElementTree), extracting headline, "
                    "article URL, raw summary, source name, and publish date. "
                    "If `--since` is set, articles before that date are discarded "
                    "at parse time. If `--limit` is set, the total list is truncated "
                    "after all feeds are fetched."
                ),
                "scope": "Three HTTP GETs; proportional to feed size (typically 20-50 items per feed).",
            },
            {
                "name": "External article URLs",
                "kind": "External HTTP",
                "via": "validate_url() — urllib.request HEAD per article",
                "desc": (
                    "Step 6 HEAD-checks each unique article URL to classify it as "
                    "`valid` (200/3xx), `limited` (401/403), or `invalid`. "
                    "Invalid URLs are skipped in the final write step. "
                    "0.1s throttle between requests."
                ),
                "scope": (
                    "One HEAD request per unique article after dedup; "
                    "proportional to `len(unique_articles)`."
                ),
            },
            {
                "name": "Claude API (claude-haiku-4-5-20251001)",
                "kind": "Anthropic API",
                "via": "generate_summary() → ai_client.run_json(_SUMMARY_CFG, prompt)",
                "desc": (
                    "Step 7 generates `meridian_summary` and `why_it_matters` for "
                    "articles with `relevance_score >= 40` and a valid/limited URL. "
                    "The prompt includes the headline, raw summary, matched company "
                    "names, and matched area names. Haiku is used for speed and cost "
                    "(max_tokens=300). `--no-claude` or absence of `ANTHROPIC_API_KEY` "
                    "skips this step entirely."
                ),
                "scope": (
                    "One API call per qualifying article (score >= 40, valid URL, "
                    "no existing summary). Proportional to high-priority article count; "
                    "0.3s between calls."
                ),
            },
        ],
        "cleaning": (
            "**Dedup runs on two independent hashes before scoring.** "
            "`_url_hash(url)` SHA-256s the normalized URL — exact-URL duplicates "
            "(same story from two fetches) are dropped. `_content_hash(headline)` "
            "SHA-256s the lowercased, punctuation-stripped headline — near-identical "
            "headlines from different sources are also dropped (the first source wins). "
            "The time-window flags (`is_today`, `is_this_week`) are refreshed at "
            "the START of each run (Step 1) by PATCHing existing `news_articles` rows "
            "whose `published_at` is now outside the today/7-day window to false — "
            "this prevents the homepage from permanently showing old articles as "
            "'today'. "
            "Invalid-URL articles (status `invalid`) are skipped in the write step — "
            "`limited` (401/403) articles ARE written because the content is likely "
            "real and the URL is behind a paywall. "
            "The upsert key is `url_hash`, so re-running on the same article updates "
            "the existing row rather than creating a duplicate."
        ),
        "writes": [
            {
                "name": "news_articles (time-window refresh)",
                "kind": "Supabase table",
                "via": "sb_update_where() — sb_patch() with date filters",
                "desc": (
                    "Step 1 (before any RSS fetch): two targeted PATCHes expire "
                    "stale flags on existing rows. "
                    "First: articles with `published_at < (NOW - 7d)` AND "
                    "`is_this_week=true` are set to `is_this_week=false`. "
                    "Second: articles with `published_at < today` AND `is_today=true` "
                    "are set to `is_today=false`. "
                    "Skipped entirely when `--dry-run` is set."
                ),
                "scope": (
                    "Two PATCHes per run, each touching only rows that are "
                    "currently flagged true but have aged out of the window — "
                    "typically a small set on any given day."
                ),
            },
            {
                "name": "news_articles (upsert)",
                "kind": "Supabase table",
                "via": "sb_upsert('news_articles', record, on_conflict='url_hash')",
                "desc": (
                    "Step 9: upserts one row per valid/limited article. Each row "
                    "includes source metadata (name, source_url, article_url, "
                    "headline, published_at), scoring fields (relevance_score, "
                    "priority_level, matched_company_ids, matched_drug_ids, "
                    "matched_area_ids), Claude summary fields (meridian_summary, "
                    "why_it_matters), URL validation fields "
                    "(source_validation_status, http_status, last_validated_at), "
                    "the two content hashes, and the is_today/is_this_week flags. "
                    "`review_status='auto'` marks all machine-generated rows."
                ),
                "scope": (
                    "One upsert per non-invalid article surviving dedup, "
                    "keyed on `url_hash`. Re-running updates existing rows "
                    "with fresh scores, summaries, and flags."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Entity watchlist loader",
            "note": "Builds the company and drug alias maps used by score_article() throughout the run.",
            "groups": [
                [
                    {
                        "function": "load_watchlist()",
                        "lines": 34,
                        "desc": (
                            "Fetches `company_aliases` (500 rows), non-acquired "
                            "`companies` (200 rows), and all `drugs` (500 rows). "
                            "Builds three data structures: `alias_map` "
                            "(alias_name.lower() -> company_id for all aliases and "
                            "canonical company names), `drug_alias_set` "
                            "(all drug names/display_names/brand_names >= 5 chars, "
                            "lowercased), and `drug_id_map` (drug alias -> drug_id). "
                            "Returns a dict containing all three plus `company_ids` "
                            "(id -> name for non-acquired companies)."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Scoring",
            "note": "Deterministic 0-100 relevance score — no LLM involved.",
            "groups": [
                [
                    {
                        "function": "score_article(headline, raw_summary, quality_base, watchlist)",
                        "lines": 85,
                        "desc": (
                            "Combines headline and raw_summary into lowercase `text`, "
                            "then applies seven additive/subtractive signals: "
                            "(1) source quality base (15 for FierceBiotech/BPD/STAT, "
                            "8 for others); "
                            "(2) company match +min(20, hits*8) — short aliases "
                            "(< 8 chars) require word-boundary match; "
                            "(3) drug match +min(20, hits*8) — same boundary logic "
                            "for < 10-char names; "
                            "(4) target/area match +min(15, hits*8) against 6 "
                            "keyword banks (TL1A, TSLP, IL4RA, FcRn, IGF1R, T-cell); "
                            "(5) deal/M&A keywords +20; "
                            "(6) clinical/FDA keywords +20; "
                            "(7) I&I / oncology biology keywords +10; "
                            "weak signal penalty -10 (only if no strong entity match). "
                            "Capped at 0-100. Returns (score, company_ids, drug_ids, "
                            "area_ids, priority_level)."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "URL validator",
            "note": "Light HTTP HEAD check for each article URL.",
            "groups": [
                [
                    {
                        "function": "validate_url(url)",
                        "lines": 29,
                        "desc": (
                            "Issues a HEAD request with a 10-second timeout. "
                            "Returns `('valid', code)` for 200/3xx, "
                            "`('limited', code)` for 401/403 (paywall — article "
                            "is real), `('invalid', code)` for anything else or "
                            "connection errors. `invalid` articles are excluded "
                            "from the write step."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "RSS parser",
            "note": "Fetches and parses one RSS feed.",
            "groups": [
                [
                    {
                        "function": "_clean_html(raw) / _parse_date(raw)",
                        "lines": 40,
                        "desc": (
                            "`_clean_html()` strips all HTML tags and decodes common "
                            "entities. `_parse_date()` tries six date formats "
                            "(including FierceBiotech's non-standard "
                            "'May 21, 2026 3:21pm') and returns ISO 8601 or None."
                        ),
                    }
                ],
                [
                    {
                        "function": "fetch_rss(source, since_date=None)",
                        "lines": 73,
                        "desc": (
                            "GETs the RSS feed URL with the source's User-Agent, "
                            "parses the XML with ElementTree, and extracts each "
                            "`<item>` into a dict: headline, article_url (from `<link>`), "
                            "raw_summary (from `<description>`, HTML-stripped), "
                            "published_at (parsed to ISO 8601), source_name, "
                            "source_url (feed URL), and quality_base. "
                            "Filters to `published_at >= since_date` if set. "
                            "Returns the list of article dicts."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Dedup helpers",
            "note": "Two hash functions used by Step 4 to deduplicate the article list.",
            "groups": [
                [
                    {
                        "function": "_url_hash(url) / _content_hash(headline)",
                        "lines": 8,
                        "desc": (
                            "`_url_hash()` SHA-256s the raw URL string. "
                            "`_content_hash()` lowercases the headline, strips "
                            "non-word characters, collapses whitespace, and "
                            "SHA-256s the result — so 'AbbVie: deal closed' and "
                            "'AbbVie - deal closed' hash to the same value and "
                            "the duplicate is dropped."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Claude summary generator",
            "note": "Optional LLM step — skipped with --no-claude or absent API key.",
            "groups": [
                [
                    {
                        "function": "generate_summary(headline, raw_summary, matched_companies, matched_areas)",
                        "lines": 41,
                        "desc": (
                            "Builds a prompt with the headline, raw summary, "
                            "matched company names (looked up from the watchlist), "
                            "and matched area names. Calls `ai_client.run_json()` with "
                            "the `homepage_news_summary` PromptConfig "
                            "(claude-haiku-4-5, max_tokens=300). Parses "
                            "`{meridian_summary, why_it_matters}` from the response. "
                            "Falls back to empty strings on JSON parse error."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main pipeline",
            "note": "run() owns all nine steps in sequence.",
            "groups": [
                [
                    {
                        "function": "run(args)",
                        "lines": 230,
                        "desc": (
                            "Drives the nine-step pipeline: "
                            "(1) refresh time-window flags on existing rows; "
                            "(2) load entity watchlist; "
                            "(3) fetch RSS feeds; "
                            "(4) dedup by URL hash + content hash; "
                            "(5) score + entity-match all articles; "
                            "(6) validate article URLs; "
                            "(7) generate Claude summaries for score >= 40; "
                            "(8) compute is_today / is_this_week flags; "
                            "(9) upsert to `news_articles` (skip invalid URLs). "
                            "Prints progress at each step and a final summary "
                            "with top-3 articles by relevance score."
                        ),
                    }
                ],
            ],
        },
    ],
}
