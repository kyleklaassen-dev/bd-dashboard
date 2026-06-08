"""
Detail content for the Company Enrichment StateGraph
(scripts/pipeline/ — runs scripts/company_enrichment.py via run_company_pipeline()).

Like research_news.py, the topology diagram on this page is generated live
from the compiled graph (see _topology.py) — only the prose (summary,
state-field meanings, node descriptions, routing rationale) is hand-written here.
"""

STATE_GRAPH = {
    "key": "company_enrichment",
    "name": "Company Enrichment",
    "module": "pipeline.graph",
    "builder": "build_enrichment_graph",
    "entrypoint": "scripts/company_enrichment.py",
    "summary": (
        "The flagship per-company × per-area enrichment run, and the largest "
        "graph in Meridian: loads every Supabase record for the pairing "
        "(pre-syncing missing trials from CT.gov along the way), auto-"
        "generates catalysts from upcoming trial readouts, optionally runs "
        "four live web searches through Claude for fresh clinical/financing/"
        "BD/catalyst intelligence, then sends the full picture to Claude for "
        "structured synthesis — validating, writing, rescoring completeness, "
        "and mining recent intel for new deals to log. Two conditional "
        "branches matter here: `skip_web_search` bypasses an entire node "
        "when the flag is set, and a failed synthesis call aborts the run "
        "before anything gets validated or written, so a bad LLM response "
        "never corrupts 15 tables' worth of company data."
    ),
    "state": {
        "module": "pipeline.state",
        "class": "PipelineState",
        "fields": [
            {"name": "area_id / company_id", "type": "str", "desc": "The company × area pairing being enriched — the run's two required inputs, and the join key for nearly every Supabase query in load_context."},
            {"name": "dry_run / skip_web_search / skip_trial_refresh / fast_model", "type": "bool", "desc": "Run options threaded from the CLI: `dry_run` skips live writes, `skip_web_search` bypasses the gather_web_intel node entirely, `skip_trial_refresh` reuses cached trial rows instead of re-fetching from CT.gov, `fast_model` swaps in a cheaper synthesis PromptConfig."},
            {"name": "enrichment_run_id", "type": "Optional[str]", "desc": "id of the enrichment_runs row this execution is tracked under — used by validate_enrichment to patch trajectory metadata (raw response, field-level stats) for fine-tuning."},
            {"name": "company_map / resolver", "type": "dict / Any", "desc": "External dependencies injected by the caller: the full area company-name→id map, and a `DrugIdentityResolver` instance used by generate_deals to stamp canonical drug ids on newly-logged deals."},
            {"name": "ctx", "type": "CompanyContext", "desc": "Every Supabase record for this company×area — company, profile, drugs, trials, catalysts, deals, recent_intel, ailux_pos — populated once by load_context and read by every node downstream via `ctx.as_dict()`."},
            {"name": "catalysts_generated", "type": "int", "desc": "Count of new catalyst rows auto-created from trial primary-completion dates — output of generate_catalysts."},
            {"name": "web_intel", "type": "str", "desc": "Structured text block from four live Claude web searches (clinical, financing, BD, catalyst timing) — injected into the synthesis prompt. Empty string if skipped or if all searches failed (non-fatal either way)."},
            {"name": "synth_result / synth_data / synth_raw_text", "type": "Any / dict / str", "desc": "Outputs of the Phase B Claude synthesis call: the full RunResult (tokens, cost, stop_reason, ok), the parsed JSON dict, and the raw text (kept for trajectory storage even on parse failure)."},
            {"name": "validated_data / validation_stats", "type": "dict / Any", "desc": "Synthesis output after Pydantic field validation — invalid drug_updates dropped, corrected values logged — plus the ValidationStats object recording what was attempted/changed/confirmed/failed for trajectory tracking."},
            {"name": "completeness_score / completeness_tier / completeness_missing", "type": "Optional[int] / Optional[str] / list", "desc": "Post-write completeness rubric output (0-100, strong/partial/thin, and the specific missing fields) — computed by merging newly-written data with pre-run context so no extra DB read is needed, then patched onto company_profiles."},
            {"name": "deals_created", "type": "int", "desc": "Count of new deal/news records logged from recent intel — output of generate_deals."},
            {"name": "errors",          "type": "list", "desc": "Per-node failure messages, namespaced as `[node_name] message`."},
            {"name": "nodes_completed", "type": "list", "desc": "Names of nodes that finished successfully, in execution order — the audit trail printed at the end of the run."},
        ],
    },
    "nodes": [
        {
            "name": "load_context",
            "file": "pipeline/nodes/load_context.py",
            "lines": 365,
            "desc": (
                "By far the largest node — fetches company, profile, drugs (filtered "
                "to this area's indication_group), trials, catalysts, deals, recent "
                "intel, and Ailux's competitive position from Supabase. Self-contained: "
                "it includes its own CT.gov pre-sync logic, so any drug with zero trial "
                "rows gets searched and upserted on the spot, and (unless "
                "`skip_trial_refresh`) every existing trial gets re-fetched directly by "
                "NCT id for the latest status, phase, and completion date. Populates `state.ctx`."
            ),
        },
        {
            "name": "generate_catalysts",
            "file": "pipeline/nodes/generate_catalysts.py",
            "lines": 166,
            "desc": (
                "Scans every trial in `state.ctx` for a future primary-completion date "
                "(parsing assorted date formats — ISO, \"Mon YYYY\", \"Q3 2026\", bare "
                "years — into a sortable form), and auto-creates an upcoming-catalyst "
                "record for each one that doesn't already exist. Idempotent by drug × "
                "date. Populates `state.catalysts_generated`."
            ),
        },
        {
            "name": "gather_web_intel",
            "file": "pipeline/nodes/gather_web_intel.py",
            "lines": 157,
            "desc": (
                "Phase A of Step 5 — runs Claude with live web search across four "
                "topics (clinical data old and new, financing/company status, BD "
                "activity, catalyst timeline), using an area-specific competitive-"
                "context label to focus the queries. Falls back to an empty string on "
                "any failure — synthesis continues with Supabase context alone. "
                "Populates `state.web_intel`. Skipped entirely when `skip_web_search` is set."
            ),
        },
        {
            "name": "synthesize_enrichment",
            "file": "pipeline/nodes/synthesize_enrichment.py",
            "lines": 71,
            "desc": (
                "Phase B of Step 5 — builds the full enrichment prompt from "
                "`state.ctx` plus `state.web_intel`, and calls `ai_client.run_json()` "
                "(swapping to a faster/cheaper PromptConfig when `fast_model` is set, "
                "with up to 3 retries). Stores the full RunResult, parsed data, and raw "
                "text on state, and records an error — without raising — if the call "
                "or JSON parse failed, which the routing function below checks."
            ),
        },
        {
            "name": "validate_enrichment",
            "file": "pipeline/nodes/validate_enrichment.py",
            "lines": 73,
            "desc": (
                "Runs Claude's `drug_updates` through Pydantic field validation — "
                "dropping invalid rows and logging corrected values — then writes the "
                "clean list back into `state.validated_data` so `write_enrichment` only "
                "ever sees sound records. Also patches `enrichment_runs` twice (raw "
                "response, then field-level tracking stats) for fine-tuning trajectory "
                "data, with each patch individually try/excepted as non-fatal."
            ),
        },
        {
            "name": "write_enrichment",
            "file": "pipeline/nodes/write_enrichment.py",
            "lines": 45,
            "desc": (
                "Delegates to `write_step5()` in the company_enrichment monolith — a "
                "~930-line function spanning 15 tables (company_profiles, drugs, "
                "catalysts, deals, company_areas, drug_areas, drug_indications, "
                "drug_targets, and more) — kept there intentionally until a dedicated "
                "refactor can safely extract it. This node is a thin, lazily-imported wrapper."
            ),
        },
        {
            "name": "score_completeness",
            "file": "pipeline/nodes/score_completeness.py",
            "lines": 224,
            "desc": (
                "Computes a stage-aware 0-100 completeness rubric (platform/BD "
                "intelligence, drug summaries, mechanism details, key_data for late-"
                "stage drugs, catalyst source URLs, key_risk/why_it_matters, overlap "
                "rationale for Direct competitors) by merging the newly-written data "
                "with pre-run context — no extra DB read needed — then patches "
                "`company_profiles` with the score, tier, and missing-field list. "
                "Populates `state.completeness_score/tier/missing`."
            ),
        },
        {
            "name": "generate_deals",
            "file": "pipeline/nodes/generate_deals.py",
            "lines": 177,
            "desc": (
                "Step 6 — scans `state.ctx.recent_intel` for headlines matching a wide "
                "keyword net (formal BD terms, financing, regulatory milestones, press-"
                "release markers), dedupes against existing deals by a normalized "
                "headline signature, infers a deal type, and uses `state.resolver` to "
                "stamp a canonical drug id on each new deal where the headline names "
                "one of the company's programs. Populates `state.deals_created` — the "
                "graph's terminal node."
            ),
        },
    ],
    "routing": [
        {
            "after": "generate_catalysts",
            "function": "_route_web_intel",
            "branches": [
                {"condition": "`state.skip_web_search` is true", "to": "synthesize_enrichment",
                 "desc": "The caller opted out of live web search (e.g. for a faster/cheaper run) — go straight to synthesis with Supabase context alone."},
                {"condition": "otherwise", "to": "gather_web_intel",
                 "desc": "Run the four web-search topics first, so synthesis has fresh clinical/financing/BD/catalyst intelligence to work with."},
            ],
        },
        {
            "after": "synthesize_enrichment",
            "function": "_route_after_synthesis",
            "branches": [
                {"condition": "`state.ok` is false (Claude call or JSON parse failed)", "to": "END",
                 "desc": "Synthesis didn't produce usable structured data — the run aborts rather than validating and writing across 15 tables from a bad or empty response."},
                {"condition": "otherwise", "to": "validate_enrichment",
                 "desc": "Synthesis succeeded — continue into validation, write, scoring, and deal discovery."},
            ],
        },
    ],
}
