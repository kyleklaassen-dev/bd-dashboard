"""
Static description of the Meridian Research pipeline
(.github/workflows/chain-01-meridian-research.yml).

research.py is a LangGraph StateGraph pipeline. The full node-by-node
breakdown lives in the State Graphs view (dashboard/state_graphs/research_news.py).
This page gives the workflow-level context: schedule, trigger, entrypoint, and
a brief summary of what the script does.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "meridian_research",
    "workflow_name": "Meridian Research",
    "workflow_file": ".github/workflows/chain-01-meridian-research.yml",
    "schedule": "Daily 06:00 UTC (2 AM ET) — first link in the nightly intelligence chain",
    "entrypoint": "scripts/intelligence/research.py",
    "unit_key": "file",
    "unit_section_title": "Entrypoint",
    "summary": (
        "Nightly intelligence sweep that runs RSS feeds → relevance filter → "
        "deduplication → full-text fetch → Claude LLM extraction → Supabase write, "
        "then appends a CT.gov new-registration poller and an EDGAR 8-K sweep for "
        "14 tracked companies. "
        "**`research.py` is a LangGraph `StateGraph` pipeline** — the node-by-node "
        "detail (state fields, routing logic, early-exit branches) is documented in "
        "the **State Graphs → Research News** view. "
        "On completion this workflow triggers chain-02 (Source Verifier) and "
        "chain-07 (Homepage News) in parallel."
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
        label="research.py\n(LangGraph StateGraph entrypoint)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    rss [
        label="RSS Feeds\n(FierceBiotech · BioPharma Dive · STAT News)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    ctgov [
        label="ClinicalTrials.gov API\n(new-registration poller)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    edgar [
        label="SEC EDGAR\n(8-K sweep, 14 companies)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    supabase_in [
        label="Supabase\n(company/drug context,\nexisting intel dedup window)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_sg {
        label="LangGraph StateGraph — phases 1-5\n(see State Graphs -> Research News for full detail)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        fetch  [label="fetch_feeds\nPhase 1 — pull RSS articles"]
        filter [label="filter_relevant\nPhase 2 — focus-area match"]
        dedup  [label="dedup\nPhase 3 — drop already-seen URLs"]
        full   [label="fetch_full_text\nPhase 4 — retrieve article body"]
        claude [label="extract_intel\nPhase 5 — Claude extraction"]
        write  [label="write_intel\nPhase 5b — write to Supabase"]
    }

    subgraph cluster_p6 {
        label="Phase 6 — appended post-graph (no LLM cost)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        ctpoll  [label="CT.gov poller\n(~2 min)"]
        edgsweep [label="EDGAR 8-K sweep\n(~8 min)"]
    }

    supabase_out [
        label="Supabase\nintel · deals · catalysts\n(upserted)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    triggers [
        label="Triggers on success:\nchain-02 Source Verifier\nchain-07 Homepage News",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> supabase_in [label="  reads context + dedup window", style="bold", color="#c9890a", fontcolor="#c9890a"]
    rss -> fetch [label="  pull", style="bold", color="#c9890a", fontcolor="#c9890a"]
    entry -> fetch
    fetch -> filter -> dedup -> full -> claude -> write
    write -> supabase_out [label="  upsert", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    entry -> ctpoll
    entry -> edgsweep
    ctgov -> ctpoll [label="  GET", style="bold", color="#c9890a", fontcolor="#c9890a"]
    edgar -> edgsweep [label="  GET", style="bold", color="#c9890a", fontcolor="#c9890a"]
    ctpoll -> supabase_out
    edgsweep -> supabase_out
    write -> triggers [label="  workflow_run event", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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
        ctgov_in [label="ClinicalTrials.gov API\n(new registrations)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        edgar_in [label="SEC EDGAR\n(8-K filings, 14 companies)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        sb_in [label="Supabase\ncompany/drug context\nexisting intel (dedup)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Meridian\nResearch",
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

        sb_out [label="Supabase\nintel · deals · catalysts\n(upserted)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        trigger_out [label="Triggers\nchain-02 Source Verifier\nchain-07 Homepage News", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    rss_in -> pipeline
    ctgov_in -> pipeline
    edgar_in -> pipeline
    sb_in -> pipeline
    pipeline -> sb_out
    pipeline -> trigger_out
}
""",
    "io": {
        "reads": [
            {
                "name": "RSS feeds (FierceBiotech · BioPharma Dive · STAT News · etc.)",
                "kind": "External RSS",
                "via": "fetch_feeds node — feedparser over configured source list",
                "desc": (
                    "Phase 1 pulls the last `hours_back` (default 48) hours of articles "
                    "from the configured RSS source list. Each article becomes a candidate "
                    "for the relevance filter in Phase 2."
                ),
                "scope": (
                    "One HTTP fetch per RSS source, proportional to feed update frequency. "
                    "Articles outside the `hours_back` window are discarded before any "
                    "downstream processing."
                ),
            },
            {
                "name": "Supabase — company/drug context + recent intel",
                "kind": "Supabase tables",
                "via": "StateGraph setup — loaded once before graph execution",
                "desc": (
                    "Company and drug name/alias maps are loaded at startup and threaded "
                    "into the graph state as `company_map` and `resolver`. Recent `intel` "
                    "source URLs (last 7 days) are fetched for the dedup node's "
                    "`existing_urls` set."
                ),
                "scope": (
                    "Two broad reads at startup; no per-article Supabase reads inside "
                    "the graph loop."
                ),
            },
            {
                "name": "ClinicalTrials.gov API (Phase 6)",
                "kind": "External API",
                "via": "CT.gov poller appended after the main StateGraph completes",
                "desc": (
                    "Phase 6 polls CT.gov for newly-registered trials relevant to tracked "
                    "focus areas. Runs in ~2 minutes with no Anthropic API calls."
                ),
                "scope": "One or more GET requests per polling interval; no LLM cost.",
            },
            {
                "name": "SEC EDGAR (Phase 6)",
                "kind": "External API",
                "via": "EDGAR 8-K sweep appended after the main StateGraph completes",
                "desc": (
                    "Phase 6 sweeps EDGAR for 8-K filings from 14 tracked companies. "
                    "Runs in ~8 minutes with no Anthropic API calls."
                ),
                "scope": "One GET per company per sweep run.",
            },
        ],
        "cleaning": (
            "**Two early-exit branches and a dedup check keep the run lean.** "
            "The `filter_relevant` node applies focus-area keyword matching and drops "
            "everything that doesn't hit a tracked signal — a quiet night exits the "
            "graph here. The `dedup` node intersects remaining article URLs against the "
            "last-7-days `existing_urls` set and exits early if nothing is new. "
            "The surviving articles are the only ones that get full-text fetch and "
            "Claude extraction, so API cost is proportional to genuinely new signal."
        ),
        "writes": [
            {
                "name": "intel · deals · catalysts",
                "kind": "Supabase tables",
                "via": "write_intel node — upsert via _db",
                "desc": (
                    "Structured records extracted by Claude are upserted to `intel`, "
                    "`deals`, and `catalysts`. Row counts are stored in the state as "
                    "`inserted_intel`, `inserted_deals`, `inserted_catalysts`."
                ),
                "scope": (
                    "Bounded by the number of articles that survive the relevance filter "
                    "and dedup check. On a typical night: 0-30 new intel rows."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Entrypoint",
            "note": (
                "research.py is a LangGraph StateGraph pipeline. The execution-flow "
                "diagram, state schema, node descriptions, and routing rationale are "
                "documented in full in the State Graphs -> Research News view. "
                "Phase 6 (CT.gov poller + EDGAR 8-K sweep) runs after the graph "
                "completes, adding external-signal collection at zero LLM cost."
            ),
            "groups": [
                [
                    {
                        "file": "scripts/intelligence/research.py",
                        "lines": 1382,
                        "desc": (
                            "Entrypoint script. Builds and executes a 6-node LangGraph "
                            "StateGraph (fetch_feeds -> filter_relevant -> dedup -> "
                            "fetch_full_text -> extract_intel -> write_intel) covering "
                            "Phases 1-5, then appends Phase 6 (CT.gov new-registration "
                            "poller + EDGAR 8-K sweep for 14 companies). "
                            "See State Graphs -> Research News for the full "
                            "node-by-node breakdown."
                        ),
                    }
                ],
            ],
        },
    ],
}
