"""
Static description of the Meridian BD Recommender pipeline
(.github/workflows/weekly-bd-recommender.yml).

Documents what bd_recommender.py does — scoring all tracked companies across
five BD-relevant dimensions, generating Claude Haiku deal framings in parallel,
and writing a ranked call list to the bd_recommendations table.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "bd_recommender",
    "workflow_name": "BD Recommender",
    "workflow_file": ".github/workflows/weekly-bd-recommender.yml",
    "schedule": "Sundays 09:00 UTC (5 AM ET) — runs after audit retention, before deal edges",
    "entrypoint": "scripts/scoring/bd_recommender.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Weekly BD intelligence run that scores every tracked company with a "
        "`strategic_value_score` across five dimensions — Strategic Value (30 pts), "
        "Pipeline Urgency (25 pts), Deal Appetite (20 pts), Partnership Fit (15 pts), "
        "and Coverage Gap (10 pts) — then calls Claude Haiku in parallel to generate "
        "a 3-sentence deal conversation opener for each top-N company. Results are "
        "written to the `bd_recommendations` table with a `call_urgency` tier "
        "(`this_week` / `this_month` / `this_quarter` / `watch`). "
        "Governance constraints are applied at ranking time: AbbVie is hard-capped to "
        "`watch` urgency for any TL1A bispecific until after ABBV-701 Phase 1 readout "
        "(Oct 2026). The run is fully idempotent — today's existing rows are deleted "
        "before re-inserting so re-runs don't accumulate duplicates."
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
        label="bd_recommender.py\n(entrypoint — args, pull, score, frame, write)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    supabase_in [
        label="Supabase\ncompanies · company_strategic_views\ndeals · catalyst_calendar · drugs\n(read here — scoring inputs)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_score {
        label="Phase 2 — score_company() per company"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        sv [label="Strategic Value\nsvs/100 * 30 pts"]
        pu [label="Pipeline Urgency\ncatalyst events next 12 mo\n+8 readout / +8 PDUFA\n+5 general / P0 boost"]
        da [label="Deal Appetite\ndeals last 18 mo\n+10 if upfront >$500M\n+5 per other deal"]
        pf [label="Partnership Fit\nview_type map\nlicensing=15 / partnership=12\nacq=10 / competitive=3"]
        cg [label="Coverage Gap\n10 x (1 - coverage_heuristic)\n+AbbVie governance cap"]
    }

    claude_api [
        label="Claude Haiku\n(ai.client.run_text)\n3-sentence deal opener\nper top-N company",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_write {
        label="Phase 5 — write results"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        delete_today [label="DELETE bd_recommendations\nWHERE recommendation_date=TODAY"]
        insert_rows [label="INSERT top-N rows\nwith rank + scores + deal_framing\n+ call_urgency"]
    }

    bd_recs [
        label="Supabase\nbd_recommendations\n(write here — ranked call list)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    stdout [
        label="stdout\nfull report — scores + framings\nper-urgency summary",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> supabase_in [label="  pull_all_data()", style="bold", color="#c9890a", fontcolor="#c9890a"]
    supabase_in -> sv
    supabase_in -> pu
    supabase_in -> da
    supabase_in -> pf
    supabase_in -> cg
    sv -> claude_api [label="  top-N companies\n  ThreadPoolExecutor(4)"]
    pu -> claude_api
    da -> claude_api
    pf -> claude_api
    cg -> claude_api
    claude_api -> delete_today
    delete_today -> insert_rows
    insert_rows -> bd_recs [label="  sb_upsert", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    insert_rows -> stdout [label="  print report", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        sb_in [label="Supabase\ncompanies · company_strategic_views\ndeals · catalyst_calendar · drugs", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        claude_in [label="Claude Haiku\n(Anthropic API)\ndeal framing per company", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="BD\nRecommender",
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

        bd_out [label="Supabase\nbd_recommendations\n(ranked call list with deal framings)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nscores + framings + urgency summary", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    claude_in -> pipeline
    pipeline -> bd_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "companies",
                "kind": "Supabase table",
                "via": "pull_all_data() → sb_get('companies', {...})",
                "desc": (
                    "All companies with a non-null `strategic_value_score`, up to 200 rows. "
                    "Fetches `id`, `name`, `strategic_value_score`, `coverage_status`, "
                    "`strategic_value_rationale`, `ailux_angle`, `overlap`, and `status`. "
                    "This is the primary worklist — only companies with a scored SVS enter "
                    "the scoring loop."
                ),
                "scope": (
                    "Single query with `strategic_value_score=not.is.null` and `limit=200`. "
                    "Unscored companies (new, not yet enriched) are silently skipped — "
                    "they don't appear in any recommendation output."
                ),
            },
            {
                "name": "company_strategic_views",
                "kind": "Supabase table",
                "via": "pull_all_data() → sb_get('company_strategic_views', {...})",
                "desc": (
                    "Partnership-fit context for every company. Fetches `company_id`, "
                    "`view_type`, `strategic_score`, `summary`, and `ailux_relevance`. "
                    "When a company has multiple view rows, the one with the highest "
                    "`view_type` priority is kept "
                    "(licensing_candidate > partnership > acquisition_target > competitive). "
                    "Used by `score_company()` for the Partnership Fit dimension (0–15 pts) "
                    "and by `generate_deal_framing()` as the context block in the prompt."
                ),
                "scope": (
                    "Single query with `limit=400`. De-duplicated in Python by keeping "
                    "the best view_type per company_id."
                ),
            },
            {
                "name": "deals",
                "kind": "Supabase table",
                "via": "pull_all_data() → sb_get('deals', {'deal_date': 'gt.<18mo_ago>'})",
                "desc": (
                    "All deals from the last 18 months, used for the Deal Appetite dimension "
                    "(0–20 pts). Each deal adds +10 pts if `upfront_usd_m > 500`, else +5 pts, "
                    "capped at 20. Deals are matched to a company by `company_id`, `from_company`, "
                    "or `to_company` — the name-based fallbacks catch deals where the "
                    "`company_id` FK wasn't set."
                ),
                "scope": (
                    "Single query filtered to `deal_date > 18 months ago`, limit 300."
                ),
            },
            {
                "name": "catalyst_calendar",
                "kind": "Supabase table",
                "via": "pull_all_data() → sb_get('catalyst_calendar', {'and': '...'})",
                "desc": (
                    "Upcoming catalyst events in the next 12 months, used for the Pipeline "
                    "Urgency dimension (0–25 pts). Trial readouts, PDUFA dates, and FIH starts "
                    "each carry different point values (+8 / +8 / +4). P0-significance events "
                    "get a +2 boost. The earliest qualifying event is also captured as "
                    "`key_catalyst` for display in the deal framing."
                ),
                "scope": (
                    "Single query with an `and=(expected_date.gt.TODAY, expected_date.lt.12mo)` "
                    "compound filter, limit 200, ordered `expected_date.asc`."
                ),
            },
            {
                "name": "drugs",
                "kind": "Supabase table",
                "via": "pull_all_data() → sb_get('drugs', {'overlap': 'eq.Direct'})",
                "desc": (
                    "All drugs tagged `overlap=Direct`, used to provide deal framing context "
                    "(the 'their tracked assets' block in the Claude prompt). Also joined by "
                    "`company_id` to find drugs owned by a company that may have catalyst "
                    "entries not linked directly to the company."
                ),
                "scope": "Single query with `overlap=eq.Direct` and `limit=150`.",
            },
            {
                "name": "Claude Haiku (Anthropic API)",
                "kind": "External API",
                "via": "generate_deal_framing() → ai_client.run_text(_FRAMING_CFG, prompt)",
                "desc": (
                    "One API call per top-N company to generate a 3-sentence deal "
                    "conversation opener. The prompt includes the Ailux context block, "
                    "company-specific summary, tracked drug list, partnership type, and "
                    "key catalyst. AbbVie responses have the governance timing note "
                    "appended as a postscript."
                ),
                "scope": (
                    "Up to `--top` (default 20) calls, executed in parallel via "
                    "`ThreadPoolExecutor(max_workers=4)` with a 30-second timeout each. "
                    "If `ANTHROPIC_API_KEY` is not set, framing is skipped and a "
                    "placeholder is used."
                ),
            },
        ],
        "cleaning": (
            "**Scoring is bounded on both ends; governance applies before ranking.** "
            "Each dimension is individually capped (Strategic Value at 30, Pipeline Urgency "
            "at 25, etc.) so no single dimension can dominate the total. AbbVie's "
            "`call_urgency` is hard-overridden to `watch` regardless of numeric score "
            "when `company_id == 'abbvie'` — the governance constraint is applied in "
            "`score_company()` before the ranked list is built, not as a post-filter. "
            "The idempotency guarantee comes from an explicit `DELETE` of today's "
            "existing rows before the `INSERT`, so re-running on the same day replaces "
            "rather than accumulates. Company-level failures in the scoring loop are "
            "caught and logged as warnings rather than aborting the run, so one bad "
            "company row doesn't lose the whole recommendation set."
        ),
        "writes": [
            {
                "name": "bd_recommendations",
                "kind": "Supabase table",
                "via": "sb_post('bd_recommendations', rows) → _db.sb_upsert()",
                "desc": (
                    "One row per company in the top-N list, with: `company_id`, "
                    "`recommendation_date` (today), five component score columns, "
                    "`rank`, `deal_framing` (Claude text), `call_urgency`, and "
                    "`key_catalyst`. Today's existing rows are deleted first so the "
                    "table always reflects the most recent run. The table is created "
                    "via `ensure_table()` if it doesn't exist yet (requires "
                    "`SUPABASE_PAT`)."
                ),
                "scope": (
                    "Exactly `--top` rows written per run (default 20). "
                    "The `--dry-run` flag suppresses both the DELETE and the INSERT "
                    "while still printing the full scored and framed output."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Credentials and module-level setup",
            "note": "Credential loading and AI client initialization at import time.",
            "groups": [
                [
                    {
                        "function": "_cred(env_var, filename)",
                        "lines": 9,
                        "desc": (
                            "Reads a credential from an environment variable first, "
                            "then falls back to a dot-file in `_REPO_ROOT` or `_SCRIPTS_DIR`. "
                            "Used to load `SUPABASE_PAT` for the Management API calls "
                            "in `ensure_table()`."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "DB helpers",
            "note": "Thin wrappers over the shared _db module — sb_get, sb_post, sb_delete.",
            "groups": [
                [
                    {
                        "function": "sb_get(path, params)",
                        "lines": 2,
                        "desc": "Delegates to `_db.sb_get()`. Used by `pull_all_data()` for all five source-table reads.",
                    },
                    {
                        "function": "sb_post(table, rows, dry_run)",
                        "lines": 5,
                        "desc": (
                            "Delegates to `_db.sb_upsert()` or prints a dry-run message. "
                            "Used by `main()` to write the final recommendations batch."
                        ),
                    },
                    {
                        "function": "sb_delete(table, params, dry_run)",
                        "lines": 6,
                        "desc": (
                            "Delegates to `_db.sb_delete()` or prints a dry-run message. "
                            "Used by `main()` to clear today's existing rows before re-inserting."
                        ),
                    },
                ],
            ],
        },
        {
            "label": "Data pull",
            "note": "Fetches all five source tables in one sequential pass before scoring begins.",
            "groups": [
                [
                    {
                        "function": "pull_all_data()",
                        "lines": 57,
                        "desc": (
                            "Issues five `sb_get()` calls to fetch companies, strategic views, "
                            "deals (last 18 months), catalyst events (next 12 months), and "
                            "direct-overlap drugs. De-duplicates `company_strategic_views` in "
                            "Python by keeping the highest-priority view_type per company. "
                            "Returns a dict keyed by table name for use throughout the run. "
                            "Prints row counts for each source table."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Scoring",
            "note": "score_company() computes all five dimensions for a single company and returns the scored dict.",
            "groups": [
                [
                    {
                        "function": "score_company(company, data)",
                        "lines": 82,
                        "desc": (
                            "Computes Strategic Value (svs / 100 * 30, capped 30), Pipeline "
                            "Urgency (sums catalyst event points for next-12-month events, "
                            "capped 25), Deal Appetite (sums deal points for last-18-month "
                            "deals, capped 20), Partnership Fit (view_type lookup, 3–15 pts), "
                            "and Coverage Gap (10 * coverage_heuristic, 0–10 pts). Derives "
                            "`call_urgency` from total (this_week ≥60, this_month ≥45, "
                            "this_quarter ≥30, watch <30). Applies AbbVie governance override. "
                            "Returns the full scored dict including `company_drugs` list and "
                            "`key_catalyst` string."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Deal framing (Claude Haiku)",
            "note": "Calls the AI client to generate a 3-sentence deal conversation opener for each top-N company.",
            "groups": [
                [
                    {
                        "function": "generate_deal_framing(scored)",
                        "lines": 37,
                        "desc": (
                            "Builds a structured prompt with the Ailux context block, company "
                            "summary (from strategic view, ailux_relevance, or ailux_angle "
                            "in that priority), tracked drug list, view_type, and key catalyst. "
                            "Calls `ai_client.run_text()` with claude-haiku-4-5 and "
                            "max_tokens=400, 30-second timeout. Appends the AbbVie governance "
                            "timing note as a postscript if `abbvie_blocked=True`. Returns a "
                            "string; falls back to a bracketed error message if the API call "
                            "raises or returns empty."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Table creation (ensure_table)",
            "note": "Creates bd_recommendations if it doesn't exist, using a probe GET then Management API DDL.",
            "groups": [
                [
                    {
                        "function": "ensure_table(dry_run)",
                        "lines": 38,
                        "desc": (
                            "Probes the table with a `limit=1` GET. If the table exists, "
                            "returns immediately. If it doesn't exist and `SUPABASE_PAT` is "
                            "available, creates the table and three indexes via four sequential "
                            "Management API POST calls. If the PAT is absent, prints the DDL "
                            "for manual execution and returns False."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main loop",
            "note": "Orchestrates all phases: pull → score → rank → frame (parallel) → ensure table → delete/insert → print report.",
            "groups": [
                [
                    {
                        "function": "main(dry_run, top_n, print_top)",
                        "lines": 96,
                        "desc": (
                            "1. Calls `pull_all_data()`. "
                            "2. Calls `score_company()` for every company in the companies list "
                            "(catches per-company exceptions as warnings). "
                            "3. Sorts by `total_score` descending, slices top_n, assigns ranks. "
                            "4. Runs `generate_deal_framing()` in a `ThreadPoolExecutor(4)`, "
                            "collecting framing text back onto each scored dict. "
                            "5. Calls `ensure_table()`, then DELETEs today's existing rows, "
                            "then INSERTs the new batch via `sb_post()`. "
                            "6. Prints the ranked report (scores, framings, urgency tier) for "
                            "the top `print_top` companies, then a final urgency-bucket summary. "
                            "Returns the top list for testing."
                        ),
                    }
                ],
            ],
        },
    ],
}
