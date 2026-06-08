"""
Static description of the Content Verifier pipeline
(.github/workflows/chain-03-content-verifier.yml).

Documents what the single entrypoint script does — fetching the text of
each cited source page, asking Claude whether the page supports the claim,
and writing the verdict back to drug_sources while opening governance_violations
for claims whose source contradicts or omits them.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "content_verifier",
    "workflow_name": "Content Verifier",
    "workflow_file": ".github/workflows/chain-03-content-verifier.yml",
    "schedule": (
        "Event-driven (after Source Verifier succeeds) "
        "+ Tue/Fri 08:30 UTC fallback"
    ),
    "entrypoint": "scripts/validation/content_verifier.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Tier-4 trust layer: closes the gap between 'the URL exists' (Tier 3) "
        "and 'the URL actually proves the fact'. For each unverified "
        "`drug_sources` claim, the script fetches the cited page, strips HTML "
        "to readable text, and asks Claude whether the page **supports**, "
        "**contradicts**, or **doesn't contain** the claim. "
        "Confirmed claims get `content_confirms_claim=true`; "
        "contradicted or absent claims open a `governance_violation` for human "
        "review; pages that are paywalled, JS-rendered, or unreachable are "
        "marked `url_status='unverifiable'` without penalising the claim. "
        "Uses `claude-haiku-4-5` (cheap + fast — judging task, not generation). "
        "Triggered by the veligrotug hallucination incident."
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
        label="content_verifier.py\n(entrypoint — main())",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    drug_sources_in [
        label="Supabase\ndrug_sources\n(content_confirms_claim IS NULL\nor --recheck)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_loop {
        label="Per drug_sources row (up to --limit, default 40)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        fetch_text [label="fetch_text(url)\nHTTP GET + HTML strip"]
        judge_node [label="judge(claim_type, claim_value, page_text)\nClaude claude-haiku-4-5\nsupports | contradicts | absent | unreadable"]
    }

    ext_http [
        label="External HTTP\n(GET per source URL)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    claude_api [
        label="Claude API\nclaude-haiku-4-5-20251001\n(judge prompt, max_tokens=200)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    subgraph cluster_write {
        label="Per-row write decision"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        supports_path  [label="supports\ncontent_confirms_claim=TRUE\nconfidence='confirmed'"]
        bad_path       [label="contradicts / absent\ncontent_confirms_claim=FALSE\nopen governance_violation"]
        unread_path    [label="unreadable / fabricated\nurl_status='unverifiable'\n(claim unchanged)"]
    }

    drug_sources_out [
        label="Supabase\ndrug_sources\n(content_confirms_claim,\nconfidence, url_status,\nurl_last_checked)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    gov_out [
        label="Supabase\ngovernance_violations\n(rule: source_does_not_support_claim)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    trigger_out [
        label="Triggers on success:\nchain-04 Compute Landscape Scores",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> drug_sources_in [label="  reads unverified claims", style="bold", color="#c9890a", fontcolor="#c9890a"]
    drug_sources_in -> fetch_text
    fetch_text -> ext_http [label="  GET", style="bold", color="#c9890a", fontcolor="#c9890a"]
    fetch_text -> judge_node [label="  text (if readable)"]
    fetch_text -> unread_path [label="  fabricated / error / empty"]
    judge_node -> claude_api [label="  judge prompt", style="bold", color="#c9890a", fontcolor="#c9890a"]
    judge_node -> supports_path [label="  supports"]
    judge_node -> bad_path [label="  contradicts / absent"]
    judge_node -> unread_path [label="  unreadable"]
    supports_path -> drug_sources_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    bad_path -> drug_sources_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    bad_path -> gov_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    unread_path -> drug_sources_out [label="  url_status only", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    entry -> trigger_out [label="  workflow_run event", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        sb_in [label="Supabase\ndrug_sources\n(unverified claims, up to --limit)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        http_in [label="External HTTP\n(GET per source page)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        claude_in [label="Claude API\nclaude-haiku-4-5 judge", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Content\nVerifier",
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

        sb_out [label="Supabase\ndrug_sources\n(content_confirms_claim + url_status)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        gov_out [label="Supabase\ngovernance_violations\n(contradicts + absent verdicts)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        trigger_out [label="Triggers\nchain-04 Landscape Scores", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    http_in -> pipeline
    claude_in -> pipeline
    pipeline -> sb_out
    pipeline -> gov_out
    pipeline -> trigger_out
}
""",
    "io": {
        "reads": [
            {
                "name": "drug_sources",
                "kind": "Supabase table",
                "via": "_db.sb_get('drug_sources', params)",
                "desc": (
                    "Fetches up to `--limit` (default 40) rows from `drug_sources` "
                    "where `source_url IS NOT NULL` and (by default) "
                    "`content_confirms_claim IS NULL` — i.e. claims that haven't been "
                    "verified yet. `--recheck` drops the null filter to re-verify "
                    "already-checked rows. Each row provides `id`, `drug_id`, "
                    "`claim_type`, `claim_value`, and `source_url` for the judge."
                ),
                "scope": (
                    "Single query, capped at `--limit` (default 40, overridable via "
                    "workflow_dispatch). The low cap keeps each run cheap: one GET "
                    "and one Claude call per row."
                ),
            },
            {
                "name": "External source pages",
                "kind": "External HTTP",
                "via": "fetch_text(url) — requests.get with 20s timeout, follow redirects",
                "desc": (
                    "For each row, `fetch_text()` GETs the cited source URL, strips "
                    "`<script>`, `<style>`, and all HTML tags, unescapes entities, "
                    "collapses whitespace, and returns the first 8000 characters of "
                    "readable text. A fabricated URL pattern (search pages, etc.) is "
                    "caught before any network call. Responses shorter than 200 "
                    "characters after stripping are treated as JS-rendered shells."
                ),
                "scope": "One GET per row, no throttle — capped by the --limit guard.",
            },
            {
                "name": "Claude API (claude-haiku-4-5-20251001)",
                "kind": "Anthropic API",
                "via": "judge() → ai_client.run_json(_JUDGE_CFG, prompt)",
                "desc": (
                    "The page text (up to 8000 chars) plus the claim type and value are "
                    "sent to claude-haiku-4-5 with a strict fact-checker system prompt. "
                    "The model returns compact JSON: "
                    "`{\"verdict\": \"supports|contradicts|absent|unreadable\", "
                    "\"evidence\": \"<=160 chars\"}`. "
                    "Haiku is used deliberately — judging task, not generation, and "
                    "the run processes up to 40 claims per invocation."
                ),
                "scope": (
                    "One API call per readable source page (fabricated, errored, or "
                    "empty pages short-circuit before the call). max_tokens=200 keeps "
                    "cost minimal."
                ),
            },
        ],
        "cleaning": (
            "**A deliberately conservative non-punishment policy.** Unreadable pages "
            "(JS shells, paywalls, fetch errors) set `url_status='unverifiable'` and "
            "leave `content_confirms_claim` unchanged — a drug is never penalised just "
            "because its IR page requires a login. Only two verdicts trigger a "
            "`governance_violation`: `contradicts` (the page states something "
            "incompatible with the claim) and `absent` (the page is readable and "
            "on-topic but does NOT contain the claim). The `supports` verdict sets "
            "`content_confirms_claim=true` and `confidence='confirmed'`. "
            "The judge prompt instructs strict matching: indication, target, stage, "
            "and deal terms must actually appear on the page, not merely be implied. "
            "The script exits non-zero only on a true `contradicts` result — so CI "
            "alerts on provably wrong data but not on unreadable pages."
        ),
        "writes": [
            {
                "name": "drug_sources",
                "kind": "Supabase table",
                "via": "_db.sb_patch('drug_sources', patch, {'id': 'eq.<row_id>'})",
                "desc": (
                    "For every row processed (not dry-run), patches `url_last_checked` "
                    "and `url_status`. Additionally patches `content_confirms_claim` "
                    "and `confidence` for `supports` (true / 'confirmed') and "
                    "`contradicts`/`absent` (false / 'unverified') verdicts. "
                    "Unreadable pages get only `url_last_checked` + `url_status` — "
                    "`content_confirms_claim` is intentionally left unchanged."
                ),
                "scope": "One PATCH per row processed (bounded by --limit).",
            },
            {
                "name": "governance_violations",
                "kind": "Supabase table",
                "via": "open_violation(row, verdict, evidence) → _db.sb_post()",
                "desc": (
                    "One violation per `contradicts` or `absent` verdict: "
                    "`rule_name='source_does_not_support_claim'`, "
                    "`description` includes the verdict, drug_id, claim_type, "
                    "the first 80 chars of the claim value, the evidence excerpt, "
                    "and the source URL. `resolved=false` so it lands in the "
                    "review queue immediately."
                ),
                "scope": (
                    "Only fired for the two failure verdicts; supports and unreadable "
                    "never create a violation. No dedup — re-running on the same "
                    "`contradicts` row creates a second violation."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Page fetcher",
            "note": "Downloads and strips a source URL to readable plain text.",
            "groups": [
                [
                    {
                        "function": "fetch_text(url)",
                        "lines": 18,
                        "desc": (
                            "Checks the URL against the `FABRICATED` regex before any "
                            "network call. Then GETs the URL with a 20-second timeout "
                            "and a browser User-Agent, strips `<script>`, `<style>`, "
                            "and `<noscript>` blocks, removes all remaining HTML tags, "
                            "unescapes entities, and collapses whitespace. Returns "
                            "`(text[:8000], 'ok')` for readable pages, "
                            "`(None, 'fabricated')`, `(None, 'empty')` (< 200 chars "
                            "after stripping — JS shell), or `(None, 'http_4xx/5xx')` / "
                            "`(None, 'error:<type>')` for failures."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Claude judge",
            "note": "Asks Claude whether the page content actually supports the claim.",
            "groups": [
                [
                    {
                        "function": "judge(claim_type, claim_value, page_text)",
                        "lines": 6,
                        "desc": (
                            "Constructs a prompt `CLAIM (<type>): <value>\\n\\nPAGE TEXT:\\n"
                            "<text>` and calls `ai_client.run_json()` with the "
                            "`content_verifier_judge` PromptConfig (claude-haiku-4-5, "
                            "max_tokens=200). Parses the JSON response and returns "
                            "`(verdict, evidence)`. If the response JSON is invalid, "
                            "returns `('unreadable', 'judge_error: invalid JSON "
                            "response')` — the same conservative path as a fetch error."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Violation writer",
            "note": "Opens a governance_violation for claims whose source contradicts or omits them.",
            "groups": [
                [
                    {
                        "function": "open_violation(row, verdict, evidence)",
                        "lines": 8,
                        "desc": (
                            "POSTs a `governance_violations` row with `table_name="
                            "'drug_sources'`, `row_id=str(row['id'])`, `rule_name="
                            "'source_does_not_support_claim'`, a description that "
                            "includes the verdict, drug_id, claim_type, truncated "
                            "claim_value, evidence excerpt, and source URL, and "
                            "`resolved=False`. Called only for `contradicts` and "
                            "`absent` verdicts."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main loop",
            "note": "Parses args, fetches the batch, runs the per-row pipeline, and prints the tally.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 49,
                        "desc": (
                            "Parses `--limit` (default 40), `--dry-run`, and `--recheck`. "
                            "Fetches up to `--limit` unverified `drug_sources` rows. "
                            "For each: calls `fetch_text()`, routes fabricated/error "
                            "URLs to the unreadable path, calls `judge()` for readable "
                            "text, increments the tally, and (unless `--dry-run`) "
                            "PATCHes `drug_sources` and optionally opens a violation. "
                            "Prints a per-row status line and a final summary. "
                            "Exits non-zero if any `contradicts` verdict was found "
                            "(so the GitHub Actions job marks red on real data errors)."
                        ),
                    }
                ],
            ],
        },
    ],
}
