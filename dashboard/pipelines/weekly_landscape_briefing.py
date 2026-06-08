"""
Static description of the Meridian Landscape Briefings pipeline
(.github/workflows/weekly-landscape-briefing.yml).

Documents what generate_landscape_briefing.py does — fetching company_profiles
per area, running a 4-section Claude Opus synthesis (archetypes, risk themes,
opportunity map, priority matrix), and writing the result to landscape_briefings.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "landscape_briefing",
    "workflow_name": "Landscape Briefings",
    "workflow_file": ".github/workflows/weekly-landscape-briefing.yml",
    "schedule": "Sundays 09:30 UTC (5:30 AM ET) — runs in parallel window with BD Recommender",
    "entrypoint": "scripts/narrative/generate_landscape_briefing.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Weekly regeneration of cited landscape intelligence briefings for each of the "
        "seven core disease areas (tl1a / ibd / tslp / il4ra / igf1r / fcrn / tcell). "
        "For each area the pipeline fetches all `company_profiles` rows with populated "
        "content fields, assembles a compact per-company text block, and runs four "
        "sequential Claude Opus calls — BD archetypes, risk concentration themes, "
        "white-space opportunities, and a ranked priority matrix of the top 10 "
        "engagement targets. The four JSON outputs are assembled into a full markdown "
        "briefing document, persisted to the `landscape_briefings` table, and written "
        "to `docs/<area>_landscape_briefing.md`. New rows are flagged `needs_review=true` "
        "so the analyst sees them in the governance queue before they enter the dashboard. "
        "The workflow loops over all seven areas sequentially, tolerating per-area failures "
        "with `|| echo '(area failed, continuing)'`."
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
        label="generate_landscape_briefing.py\n(entrypoint — main())",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    profiles_in [
        label="Supabase\ncompany_profiles\n(read here — per area_id)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_synthesis {
        label="4-section Claude Opus synthesis (sequential, 1s sleep between calls)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        s1 [label="1. synthesize_archetypes()\n7 BD archetype clusters\n(JSON array)"]
        s2 [label="2. synthesize_risk_themes()\nTop 5 landscape risk themes\n(JSON array)"]
        s3 [label="3. synthesize_opportunity_map()\n3 white-space opportunities\n(JSON array)"]
        s4 [label="4. synthesize_priority_matrix()\nTop 10 engagement priorities\n(JSON array)"]
    }

    claude_api [
        label="Claude Opus\n(ai.client.run_text)\n4 calls per area\nJSON responses",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    build_md [
        label="build_full_markdown()\nassemble 4 sections + header"
    ]

    lb_table [
        label="Supabase\nlandscape_briefings\n(insert here — needs_review=true)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    docs_file [
        label="docs/<area>_landscape_briefing.md\n(written to disk)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    entry -> profiles_in [label="  fetch_profiles(area_id)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    profiles_in -> s1
    s1 -> claude_api [label="  call 1", style="bold", color="#c9890a", fontcolor="#c9890a"]
    claude_api -> s1
    s1 -> s2
    s2 -> claude_api [label="  call 2", style="bold", color="#c9890a", fontcolor="#c9890a"]
    claude_api -> s2
    s2 -> s3
    s3 -> claude_api [label="  call 3", style="bold", color="#c9890a", fontcolor="#c9890a"]
    claude_api -> s3
    s3 -> s4
    s4 -> claude_api [label="  call 4", style="bold", color="#c9890a", fontcolor="#c9890a"]
    claude_api -> s4
    s4 -> build_md
    build_md -> lb_table [label="  persist_briefing()\nsb_post()", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    build_md -> docs_file [label="  write_text()", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        profiles_in [label="Supabase\ncompany_profiles\n(per area_id)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        opus_in [label="Claude Opus\n(Anthropic API)\n4 calls per area", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Landscape\nBriefings",
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

        lb_out [label="Supabase\nlandscape_briefings\n(needs_review=true)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        docs_out [label="docs/<area>_landscape_briefing.md\n(markdown file)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    profiles_in -> pipeline
    opus_in -> pipeline
    pipeline -> lb_out
    pipeline -> docs_out
}
""",
    "io": {
        "reads": [
            {
                "name": "company_profiles",
                "kind": "Supabase table",
                "via": "fetch_profiles(area_id) → sb_get('company_profiles', {'area_id': 'eq.<area>'})",
                "desc": (
                    "All profiles for the target area, ordered by `company_id`. "
                    "Fetches: `company_id`, `area_id`, `platform_summary`, `bd_summary`, "
                    "`key_risk`, `why_it_matters`, `strategic_behavior`, `vs_ailux`, "
                    "`risk_summary`, `bd_angle`. After the fetch, profiles with no "
                    "populated content fields (all four key fields null/empty) are filtered "
                    "out — only the `populated` subset enters the synthesis."
                ),
                "scope": (
                    "One query per area invocation. Profile text is assembled by "
                    "`summarize_profile()` (each field truncated to 350 chars) then "
                    "concatenated. If the total exceeds 40,000 characters the string is "
                    "hard-truncated to stay within Opus context limits."
                ),
            },
            {
                "name": "landscape_briefings (existence check)",
                "kind": "Supabase table",
                "via": "sb_get('landscape_briefings', {'area_id': 'eq.<area>', 'limit': '1'})",
                "desc": (
                    "When `--force` is NOT set, a pre-flight read checks whether a "
                    "briefing already exists for the area. If one is found, the run "
                    "exits early with a 'use --force to regenerate' message. The "
                    "workflow always passes `--force`, so this check is a no-op in CI "
                    "but protects against accidental local overwrites."
                ),
                "scope": "One `limit=1` probe per area if `--force` is absent.",
            },
            {
                "name": "Claude Opus (Anthropic API)",
                "kind": "External API",
                "via": "call_opus(system, user) → ai_client.run_text(PromptConfig(model='claude-opus-4-6'))",
                "desc": (
                    "Four sequential calls per area, each requesting structured JSON: "
                    "(1) archetype classification of every company into one of seven BD "
                    "archetypes; (2) five landscape-level risk themes across companies; "
                    "(3) three white-space opportunity descriptions; (4) top-10 ranked "
                    "engagement priority matrix with timing triggers. All calls use the "
                    "`SYSTEM_ANALYST` prompt for structured JSON output or `SYSTEM_WRITER` "
                    "for prose. A 1-second sleep separates calls to avoid rate-limit "
                    "spikes. JSON responses are stripped of markdown fences before parsing."
                ),
                "scope": (
                    "28 API calls total in a full seven-area run (4 per area). "
                    "max_tokens varies by section (1000–2000). The 40-minute CI timeout "
                    "provides headroom even if individual calls approach 45 seconds."
                ),
            },
        ],
        "cleaning": (
            "**Content filtering and length guards happen before any API call.** "
            "After fetching profiles, rows with all four key fields empty are dropped — "
            "they'd contribute no signal to the synthesis and would pad the token count. "
            "The assembled profile text is hard-truncated to 40,000 characters with a "
            "'[... additional profiles truncated ...]' marker so Opus sees a bounded "
            "input regardless of area size. JSON parsing errors in any section are "
            "caught by `parse_json()` — on failure, the section returns an empty list "
            "and a markdown fallback message ('*Synthesis failed — retry.*'), so a "
            "single bad API response doesn't abort the whole briefing. The briefing row "
            "is always inserted with `needs_review=True` so no output goes live without "
            "human sign-off."
        ),
        "writes": [
            {
                "name": "landscape_briefings",
                "kind": "Supabase table",
                "via": "persist_briefing() → sb_post('landscape_briefings', payload)",
                "desc": (
                    "One row per area per run. Payload includes: `area_id`, "
                    "`briefing_type='competitive_landscape'`, `title`, `summary` "
                    "(auto-generated stat line), `source_profile_count`, "
                    "`source_company_ids` (JSON array), `archetypes_json`, "
                    "`risk_themes_json`, `opportunity_map_json`, `priority_matrix_json` "
                    "(all four section outputs as JSON strings), `full_markdown`, "
                    "`model_used='claude-opus-4-6'`, `confidence_level='medium'`, "
                    "and `needs_review=True`. Returns the new UUID."
                ),
                "scope": (
                    "One INSERT per area. The `--force` flag does not delete the existing "
                    "row first — it creates a new row alongside the old one. The dashboard "
                    "should query by `order=created_at.desc, limit=1` to get the latest."
                ),
            },
            {
                "name": "docs/<area>_landscape_briefing.md",
                "kind": "Local file",
                "via": "pathlib.Path.write_text(full_markdown)",
                "desc": (
                    "Full markdown briefing written to the `docs/` directory alongside "
                    "the script. Contains the four synthesis sections under a dated "
                    "header block. Overwrites any previous file for the same area."
                ),
                "scope": (
                    "One file per area per run. In CI the file is only visible in the "
                    "runner's workspace unless a subsequent step commits or uploads it."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Profile fetch and summarization",
            "note": "Reads company profiles and converts each to a compact text block for the synthesis prompt.",
            "groups": [
                [
                    {
                        "function": "fetch_profiles(area_id)",
                        "lines": 8,
                        "desc": (
                            "Issues a single `sb_get()` call filtered to `area_id` and "
                            "returning 10 profile fields, ordered by company_id. No "
                            "pagination limit is set explicitly — the shared `sb_get()` "
                            "default applies."
                        ),
                    },
                    {
                        "function": "summarize_profile(p)",
                        "lines": 11,
                        "desc": (
                            "Converts one profile dict to a text block starting with "
                            "`=== COMPANY_ID ===`, then one labelled line per non-empty "
                            "field, each truncated to 350 characters. Used to pack "
                            "multiple company profiles into a single prompt."
                        ),
                    },
                ],
            ],
        },
        {
            "label": "Claude Opus synthesis — four sections",
            "note": "call_opus() and parse_json() are the shared helpers; each synthesize_*() function issues one Opus call.",
            "groups": [
                [
                    {
                        "function": "call_opus(system, user, max_tokens)",
                        "lines": 9,
                        "desc": (
                            "Creates a `PromptConfig` for `claude-opus-4-6` and calls "
                            "`ai_client.run_text()`. Strips markdown fences from the "
                            "response before returning the raw string."
                        ),
                    },
                    {
                        "function": "parse_json(raw, label)",
                        "lines": 7,
                        "desc": (
                            "Tries `json.loads(raw)`; on `JSONDecodeError` prints the "
                            "first 200 chars of the raw response as a debug hint and "
                            "returns `None`. Callers check for `None` and substitute "
                            "a fallback markdown section."
                        ),
                    },
                ],
                [
                    {
                        "function": "synthesize_archetypes(profiles_text, area_id)",
                        "lines": 32,
                        "desc": (
                            "Asks Opus to classify every company into one of seven BD "
                            "archetypes (LIKELY_ACQUIRER, LARGE_PHARMA_COMPETITOR, "
                            "BISPECIFIC_COMPETITOR, LICENSING_ORIGINATOR, GEOGRAPHIC_PLAY, "
                            "PLATFORM_TOOL, MONITOR_ONLY). Returns `(archetypes_json, arch_md)` "
                            "— the raw JSON list and the formatted markdown section."
                        ),
                    },
                    {
                        "function": "synthesize_risk_themes(profiles_text, area_id)",
                        "lines": 29,
                        "desc": (
                            "Asks Opus for the top 5 landscape-level risk themes — "
                            "cross-company structural threats to Ailux's BD strategy. "
                            "Returns `(risk_themes_json, risk_md)` with company lists "
                            "and Ailux response recommendations per theme."
                        ),
                    },
                    {
                        "function": "synthesize_opportunity_map(profiles_text, area_id)",
                        "lines": 29,
                        "desc": (
                            "Asks Opus to identify three white-space opportunities — "
                            "structural gaps not being pursued by any competitor that are "
                            "actionable within 12–18 months. Returns "
                            "`(opp_json, opp_md)` with rationale and deal structure per "
                            "opportunity."
                        ),
                    },
                    {
                        "function": "synthesize_priority_matrix(profiles_text, area_id)",
                        "lines": 33,
                        "desc": (
                            "Asks Opus for a ranked top-10 BD engagement list with "
                            "engagement type (PARTNER / ACQUIRE / MONITOR / LICENSE / "
                            "CO-DEVELOP), headline, rationale, and concrete timing trigger. "
                            "Returns `(matrix_json, matrix_md)`."
                        ),
                    },
                ],
            ],
        },
        {
            "label": "Assembly and persistence",
            "note": "Assembles the four markdown sections into a full document and persists to DB + disk.",
            "groups": [
                [
                    {
                        "function": "build_full_markdown(area_id, profile_count, arch_md, risk_md, opp_md, matrix_md)",
                        "lines": 18,
                        "desc": (
                            "Wraps the four section markdown strings in a header block "
                            "(area, date, model, source profile count) with horizontal "
                            "rule separators. Returns the full briefing as a single string."
                        ),
                    },
                    {
                        "function": "persist_briefing(area_id, profiles, archetypes_json, risk_themes_json, opportunity_map_json, priority_matrix_json, full_markdown)",
                        "lines": 27,
                        "desc": (
                            "Assembles the DB payload and calls `sb_post('landscape_briefings', ...)`. "
                            "Sets `needs_review=True` and `confidence_level='medium'` on every "
                            "insert. Returns the new row UUID."
                        ),
                    },
                ],
            ],
        },
        {
            "label": "Main orchestration",
            "note": "Parses args, checks for existing briefing, runs the full synthesis pipeline, writes outputs.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 67,
                        "desc": (
                            "Parses `--area`, `--dry-run`, `--force`. If not `--force` and "
                            "not `--dry-run`, probes for an existing briefing and exits early "
                            "if found. Fetches profiles, filters to populated set, truncates "
                            "to 40k chars. Runs the four synthesis functions sequentially "
                            "with 1-second sleeps between calls. In `--dry-run` mode: prints "
                            "the first 2000 chars of the markdown and the first 500 chars of "
                            "archetypes_json, then exits without writing. Otherwise: writes "
                            "the markdown file to `docs/`, calls `persist_briefing()`, and "
                            "prints the new briefing ID with a `needs_review=true` reminder."
                        ),
                    }
                ],
            ],
        },
    ],
}
