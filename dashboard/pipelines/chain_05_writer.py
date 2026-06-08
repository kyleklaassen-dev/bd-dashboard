"""
Static description of the Meridian Writer pipeline
(.github/workflows/chain-05-meridian-write.yml).

write_meridian.py is a LangGraph StateGraph pipeline. The full node-by-node
breakdown lives in the State Graphs view (dashboard/state_graphs/write_meridian.py).
This page gives the workflow-level context: schedule, trigger position in the
nightly chain, and a brief summary of what the script does.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "meridian_writer",
    "workflow_name": "Meridian Writer",
    "workflow_file": ".github/workflows/chain-05-meridian-write.yml",
    "schedule": (
        "Event-driven (after Compute Landscape Scores succeeds) "
        "+ daily 10:30 UTC fallback (skips if today's Issue already exists)"
    ),
    "entrypoint": "scripts/intelligence/write_meridian.py",
    "unit_key": "file",
    "unit_section_title": "Entrypoint",
    "summary": (
        "Daily Issue-writing run: the last step in the nightly chain "
        "(Research -> Source Verify -> Content Verify -> Score -> Writer). "
        "Pulls together every data source the Issue depends on (intel, deals, "
        "catalysts, BD priorities, drug/company context, competitive graph, "
        "prior issues, reader feedback), runs two LLM passes "
        "(Pass 1: editorial plan; Pass 2: full HTML draft), "
        "saves to Supabase, deploys to GitHub Pages, and triggers "
        "chain-06 (Morning Summary) on success. "
        "A placeholder branch handles quiet nights (no new intel) without "
        "running the expensive LLM passes. "
        "**`write_meridian.py` is a LangGraph `StateGraph` pipeline** — the "
        "node-by-node detail (state fields, routing logic, publish/wrapup steps) "
        "is documented in the **State Graphs -> Write Meridian** view."
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
        label="write_meridian.py\n(LangGraph StateGraph entrypoint)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    supabase_in [
        label="Supabase\nintel · deals · catalysts · catalyst_calendar ·\nbd_priority_scores · drugs · companies ·\nailux_positions · meridian_issues ·\ncompany_signals · trials · competitive_graph ·\nreader_feedback",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=10,
        margin="0.22,0.14"
    ]

    claude_api [
        label="Claude API\n(Pass 1: editorial plan\nPass 2: HTML draft)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    subgraph cluster_sg {
        label="LangGraph StateGraph\n(see State Graphs -> Write Meridian for full detail)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        load    [label="load_context\nfetch all data sources + augment SYSTEM_PROMPT"]
        blocks  [label="build_blocks\nassemble shared prompt blocks"]
        plan    [label="generate_plan\nPass 1: LLM editorial plan"]
        draft   [label="generate_draft\nPass 2: LLM HTML draft"]
        pub     [label="publish\nsave to Supabase + deploy to GitHub Pages"]
        wrapup  [label="wrapup\nbest-effort post-publish steps"]

        placeholder [label="placeholder\n(quiet night — no new intel)"]
    }

    github_pages [
        label="GitHub Pages\n(kyleklaassen-dev/bd-dashboard)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    supabase_out [
        label="Supabase\nmeridian_issues · meridian_plan ·\ncompany_signals · system_status\n(written/updated)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    trigger_out [
        label="Triggers on success:\nchain-06 Morning Summary",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> supabase_in [label="  load_context reads", style="bold", color="#c9890a", fontcolor="#c9890a"]
    supabase_in -> load
    entry -> load
    load -> blocks
    blocks -> plan [label="  normal path (intel exists)"]
    blocks -> placeholder [label="  quiet-night branch"]
    plan -> claude_api [label="  Pass 1", style="bold", color="#c9890a", fontcolor="#c9890a"]
    plan -> draft
    draft -> claude_api [label="  Pass 2", style="bold", color="#c9890a", fontcolor="#c9890a"]
    draft -> pub
    placeholder -> pub [label="  converge on publish"]
    pub -> supabase_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    pub -> github_pages [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    pub -> wrapup
    wrapup -> supabase_out
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

        sb_in [label="Supabase\nintel · deals · catalysts · drugs · companies ·\nbd_priority_scores · competitive_graph ·\nmeridian_issues · reader_feedback · trials", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        claude_in [label="Claude API\n(sonnet — two LLM passes)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Meridian\nWriter",
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

        sb_out [label="Supabase\nmeridian_issues · meridian_plan\ncompany_signals · system_status", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        gh_out [label="GitHub Pages\nkyleklaassen-dev/bd-dashboard\n(HTML issue deployed)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        trigger_out [label="Triggers\nchain-06 Morning Summary", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    claude_in -> pipeline
    pipeline -> sb_out
    pipeline -> gh_out
    pipeline -> trigger_out
}
""",
    "io": {
        "reads": [
            {
                "name": (
                    "intel · deals · catalysts · catalyst_calendar · bd_priority_scores · "
                    "drugs · companies · ailux_positions · meridian_issues · "
                    "company_signals · trials · competitive_graph · reader_feedback"
                ),
                "kind": "Supabase tables",
                "via": "load_context node — fetches all data sources before any LLM pass",
                "desc": (
                    "The `load_context` node fetches every data source the Issue "
                    "depends on in a single pre-LLM phase. Intel, deals, and catalysts "
                    "are windowed to recent records; the last 7 prior issues are fetched "
                    "for continuity/non-repetition; reader feedback is folded into the "
                    "system prompt augmentation. `intel` in particular gates the "
                    "quiet-night placeholder branch."
                ),
                "scope": (
                    "All reads happen once in `load_context` before any LLM call. "
                    "The compiled state is then threaded through all downstream nodes "
                    "without additional DB reads."
                ),
            },
            {
                "name": "Claude API (two passes)",
                "kind": "Anthropic API",
                "via": "generate_plan and generate_draft nodes — ai_client via SYSTEM_PROMPT",
                "desc": (
                    "Pass 1 (`generate_plan`): sends all prompt blocks to produce a "
                    "structured editorial plan (surfacing the highest-priority signals, "
                    "selecting companies, ordering sections). "
                    "Pass 2 (`generate_draft`): takes the plan as input and writes the "
                    "full Issue HTML. The plan is persisted to `meridian_plan` "
                    "immediately after Pass 1 so editorial judgment survives even if "
                    "Pass 2 fails."
                ),
                "scope": (
                    "Two API calls per run on the normal path. The quiet-night "
                    "placeholder branch skips both. `MERIDIAN_FORCE=1` forces "
                    "regeneration even if today's Issue already exists."
                ),
            },
        ],
        "cleaning": (
            "**A quiet-night gate prevents two expensive LLM passes over nothing.** "
            "If `load_context` finds no recent `intel` records, the graph routes to "
            "`placeholder`, which writes a minimal Issue HTML directly without calling "
            "the API. Both paths converge on `publish` — so an Issue is always saved "
            "and deployed before any wrapup step can fail. The fallback schedule "
            "(10:30 UTC daily) runs `write_meridian.py` with a skip guard: if "
            "today's Issue already exists in `meridian_issues`, the script exits early "
            "without a second write. `MERIDIAN_FORCE=1` overrides this guard for "
            "manual regeneration."
        ),
        "writes": [
            {
                "name": "meridian_issues",
                "kind": "Supabase table",
                "via": "publish node — upsert via _db, keyed on date",
                "desc": (
                    "The complete Issue HTML plus metadata (date, word count, "
                    "section list, content fingerprint) is upserted to "
                    "`meridian_issues`. The `content_fingerprint` from Pass 1 "
                    "is stored here so drift between the plan and final draft can "
                    "be detected."
                ),
                "scope": "One upsert per run, keyed on today's date.",
            },
            {
                "name": "meridian_plan",
                "kind": "Supabase table",
                "via": "generate_plan node — persisted immediately after Pass 1",
                "desc": (
                    "The editorial plan object, its formatted prompt-block form, "
                    "and the list of company ids it surfaced are written to "
                    "`meridian_plan` right after Pass 1 completes — before Pass 2 "
                    "begins. This ensures editorial judgment is durable even if the "
                    "draft generation fails."
                ),
                "scope": "One write per run (normal path only; placeholder skips Pass 1).",
            },
            {
                "name": "GitHub Pages",
                "kind": "GitHub Pages deployment",
                "via": "publish node — GitHub API commit + push via GH_DEPLOY_TOKEN",
                "desc": (
                    "The Issue HTML is committed to the `kyleklaassen-dev/bd-dashboard` "
                    "repo and pushed, triggering an automatic GitHub Pages deploy. "
                    "The deploy token (`GH_DEPLOY_TOKEN`) is required for "
                    "`workflow_run`-triggered runs, which receive a read-only default "
                    "token."
                ),
                "scope": "One commit + push per run.",
            },
            {
                "name": "company_signals · system_status",
                "kind": "Supabase tables",
                "via": "wrapup node — best-effort, non-blocking",
                "desc": (
                    "The `wrapup` node performs a handful of post-publish steps: "
                    "updating `company_signals` for companies surfaced in the plan, "
                    "and stamping `system_status` with the write timestamp. These "
                    "run after `publish` commits to GitHub Pages and are allowed to "
                    "fail without affecting the published Issue."
                ),
                "scope": (
                    "One PATCH per surfaced company + one system_status stamp. "
                    "Errors are logged to `state.errors` but don't abort the run."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Entrypoint",
            "note": (
                "write_meridian.py is a LangGraph StateGraph pipeline. The execution-flow "
                "diagram, state schema, node descriptions, and routing rationale are "
                "documented in full in the State Graphs -> Write Meridian view."
            ),
            "groups": [
                [
                    {
                        "file": "scripts/intelligence/write_meridian.py",
                        "lines": 2257,
                        "desc": (
                            "Entrypoint script. Builds and executes a LangGraph "
                            "StateGraph with nodes: load_context -> build_blocks -> "
                            "generate_plan (or placeholder) -> generate_draft -> "
                            "publish -> wrapup. Two LLM passes (editorial plan + HTML "
                            "draft) are separated by a plan-persistence step so the "
                            "first pass survives second-pass failures. "
                            "See State Graphs -> Write Meridian for the full "
                            "node-by-node breakdown."
                        ),
                    }
                ],
            ],
        },
    ],
}
