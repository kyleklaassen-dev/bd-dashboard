"""
Detail content for the Write Meridian StateGraph
(scripts/pipeline/write_meridian/ — runs scripts/intelligence/write_meridian.py).

Like research_news.py, the topology diagram on this page is generated live
from the compiled graph (see _topology.py) — only the prose (summary,
state-field meanings, node descriptions, routing rationale) is hand-written here.
"""

STATE_GRAPH = {
    "key": "write_meridian",
    "name": "Write Meridian",
    "module": "pipeline.write_meridian.graph",
    "builder": "build_write_meridian_graph",
    "entrypoint": "scripts/intelligence/write_meridian.py",
    "summary": (
        "Daily Issue-writing run: pulls together every data source the "
        "Issue depends on (intel, deals, catalysts, BD priorities, drug/"
        "company context, the competitive graph, prior issues, reader "
        "feedback), assembles them into shared prompt blocks, then runs two "
        "LLM passes — an editorial plan, then a full HTML draft built from "
        "that plan — before saving to Supabase, deploying to GitHub Pages, "
        "and running a handful of best-effort wrap-up steps. One conditional "
        "branch means a quiet 48 hours produces a minimal placeholder Issue "
        "instead of running two expensive LLM passes over nothing; both that "
        "path and the normal one converge on publish, so an Issue is always "
        "saved and deployed before any wrap-up step gets a chance to fail."
    ),
    "state": {
        "module": "pipeline.write_meridian.state",
        "class": "MeridianState",
        "fields": [
            {"name": "today", "type": "str", "desc": "Date string for the Issue being generated — threaded through to save/deploy/wrapup."},
            {"name": "intel / deals / catalysts / catalyst_calendar_events", "type": "list", "desc": "Recent intelligence, deal, and catalyst records fetched in load_context — `intel` in particular gates the placeholder branch."},
            {"name": "bd_priority_data", "type": "dict", "desc": "Very-high BD-priority scores and strategic views, used to weight what the editorial plan surfaces first."},
            {"name": "drugs / companies", "type": "dict", "desc": "Drug and company context lookups, threaded through both LLM passes and into publish for id resolution."},
            {"name": "ailux_positions / recent_issues / company_signals / trials", "type": "list", "desc": "Ailux's own pipeline positions, the last 7 prior Issues (for continuity/non-repetition), recent company signals, and recent trial updates — all folded into the prompt blocks."},
            {"name": "graph_active_in / graph_targets / graph_competes", "type": "dict / dict / list", "desc": "Competitive-graph context (who's active where, target overlap, who competes with whom) — gives the plan and draft a structural view beyond individual records."},
            {"name": "blocks", "type": "dict", "desc": "Every formatted prompt block shared by both LLM passes — assembled once in build_blocks so generate_plan and generate_draft don't each re-derive them."},
            {"name": "plan / plan_block / plan_company_ids / content_fingerprint", "type": "Any / str / list / Any", "desc": "Pass-1 outputs: the editorial plan object, its formatted prompt-block form, the company ids it surfaced, and a fingerprint of (intel ids + company ids) — persisted immediately so editorial judgment survives even if Pass 2 fails."},
            {"name": "html", "type": "str", "desc": "The final Issue HTML — produced by generate_draft on the normal path, or written directly by placeholder on a quiet night. The one thing publish actually ships."},
            {"name": "errors",          "type": "list", "desc": "Per-node failure messages, namespaced as `[node_name] message`."},
            {"name": "nodes_completed", "type": "list", "desc": "Names of nodes that finished successfully, in execution order — the audit trail printed at the end of the run."},
        ],
    },
    "nodes": [
        {
            "name": "load_context",
            "file": "pipeline/write_meridian/nodes/load_context.py",
            "lines": 59,
            "desc": (
                "Fetches every data source the Issue depends on — intel, deals, "
                "catalysts, BD priorities, drug/company context, Ailux positions, "
                "prior issues, company signals, trials, and the competitive graph "
                "— and augments the writer's module-level SYSTEM_PROMPT with "
                "verification cautions and a reader-feedback block, mirroring the "
                "original script's mutation so both LLM-pass functions (which read "
                "SYSTEM_PROMPT as a global) pick up the augmented version."
            ),
        },
        {
            "name": "build_blocks",
            "file": "pipeline/write_meridian/nodes/build_blocks.py",
            "lines": 37,
            "desc": "Phase A — assembles every formatted prompt block shared by both LLM passes from the fetched context, via `build_content_blocks`. Populates `state.blocks`, the single source both `generate_plan` and `generate_draft` read from.",
        },
        {
            "name": "placeholder",
            "file": "pipeline/write_meridian/nodes/placeholder.py",
            "lines": 42,
            "desc": "Taken when no intel was collected in the lookback window — writes a minimal \"check back tomorrow\" Issue directly into `state.html` and clears the plan fields, skipping both LLM passes entirely.",
        },
        {
            "name": "generate_plan",
            "file": "pipeline/write_meridian/nodes/generate_plan.py",
            "lines": 51,
            "desc": (
                "Pass 1 — calls `generate_editorial_plan` (routed through "
                "`ai_client.run_json`) to decide what the Issue should cover and "
                "how, then immediately persists the plan's intel/company ids and a "
                "content fingerprint into state. This persistence-before-Pass-2 "
                "ordering means editorial judgment is never lost even if the draft "
                "pass fails downstream."
            ),
        },
        {
            "name": "generate_draft",
            "file": "pipeline/write_meridian/nodes/generate_draft.py",
            "lines": 32,
            "desc": (
                "Pass 2 — calls `generate_draft` (routed through `ai_client.run_text`, "
                "since the response is raw HTML rather than JSON) to turn the "
                "editorial plan into the full Issue, including all post-draft "
                "processing: code-fence stripping, first-mention linking, the "
                "fact-check audit, and feedback-widget injection. Populates `state.html`."
            ),
        },
        {
            "name": "publish",
            "file": "pipeline/write_meridian/nodes/publish.py",
            "lines": 39,
            "desc": (
                "Saves the Issue to Supabase, then deploys it to GitHub Pages — in "
                "that order, matching the original script. This node is the "
                "convergence point for both the normal and placeholder paths, and "
                "deliberately runs deploy unconditionally after save: a prior outage "
                "(2026-06-03+) was caused by a post-save step crashing before deploy, "
                "leaving meridian_today.html unpublished."
            ),
        },
        {
            "name": "wrapup",
            "file": "pipeline/write_meridian/nodes/wrapup.py",
            "lines": 58,
            "desc": (
                "Best-effort post-publish steps, each individually wrapped so none "
                "can fail the run: editorial-priority bump, catalyst-outcome sync, "
                "a system_status timestamp stamp, and the fact-check report. By the "
                "time this node runs, the Issue is already live — nothing here is "
                "allowed to take that back."
            ),
        },
    ],
    "routing": [
        {
            "after": "build_blocks",
            "function": "_route_after_blocks",
            "branches": [
                {"condition": "`state.intel` is empty", "to": "placeholder",
                 "desc": "No intel was collected in the lookback window — write a minimal placeholder Issue rather than running two expensive LLM passes over nothing."},
                {"condition": "otherwise", "to": "generate_plan",
                 "desc": "Intel exists — continue into the normal two-pass editorial pipeline."},
            ],
        },
    ],
}
