"""
Detail content for the Company Intake StateGraph
(scripts/pipeline/company_intake/ — runs scripts/company_intake.py).

Like research_news.py, the topology diagram on this page is generated live
from the compiled graph (see _topology.py) — only the prose (summary,
state-field meanings, node descriptions, routing rationale) is hand-written here.
"""

STATE_GRAPH = {
    "key": "company_intake",
    "name": "Company Intake",
    "module": "pipeline.company_intake.graph",
    "builder": "build_intake_graph",
    "entrypoint": "scripts/company_intake.py",
    "diagram_width": 520,
    "summary": (
        "Two workflows in one graph, selected by `state.mode`: **intake** "
        "researches a brand-new company and queues the areas it's relevant "
        "to for review, while **reaudit** refreshes a known company's live "
        "pipeline and diffs it against what Meridian already has on file, "
        "queuing only the gaps. Both share three steps — identity "
        "resolution, a model-tier guard, and one open-ended Claude research "
        "call — before diverging into mode-specific scoring/diffing and "
        "queue-writing. Five conditional branches gate the run at almost "
        "every step: a company that's already known (without --force), an "
        "unresolvable name, a Haiku-tier model on a live run, a failed "
        "research call, or — on the relevant path — nothing worth queuing, "
        "all end the run early rather than writing speculative or "
        "low-quality rows to discovery_queue."
    ),
    "state": {
        "module": "pipeline.company_intake.state",
        "class": "IntakeState",
        "fields": [
            {"name": "company_name", "type": "str", "desc": "The name supplied on the command line — the run's primary input, used for both resolution and (if new) the research prompt."},
            {"name": "mode", "type": "str", "desc": "`\"intake\"` (research + queue a new company) or `\"reaudit\"` (diff a known company's pipeline) — the value every conditional edge in this graph branches on."},
            {"name": "dry_run / verbose / force / run_id", "type": "bool / bool / bool / str", "desc": "Run options threaded from the CLI: `dry_run` skips live writes, `verbose` prints extra detail, `force` overrides the existing-company/alias-conflict guards, `run_id` tags every queue row written this run."},
            {"name": "supabase_url / supabase_key", "type": "str", "desc": "Credentials injected by the caller (company_intake.py) rather than loaded inside the graph — keeps the graph itself credential-agnostic and easy to test."},
            {"name": "resolution / company_id", "type": "dict / Optional[str]", "desc": "Output of `resolve_identity` — the resolver's full detail dict, and the resolved company id (None for a brand-new candidate in intake mode)."},
            {"name": "research", "type": "Optional[dict]", "desc": "Parsed JSON from the open-ended Claude research call — company info, pipeline, deals, and per-area relevance assessments. The shared input to everything downstream of research_company."},
            {"name": "relevant_areas / written_areas", "type": "list", "desc": "intake-mode only: areas that cleared the evidence/confidence thresholds (`score_areas`), and the subset that were actually written to discovery_queue after the dedup check (`write_queue`)."},
            {"name": "db_tokens / db_drugs / new_drugs / seen_drugs / gaps_written", "type": "list / list / list / list / int", "desc": "reaudit-mode only: the DB's existing drug-name token set and rows (`load_db_drugs`), the diff result split into gap vs. matched drugs (`diff_pipeline`), and the count of gap rows written (`write_gaps`)."},
            {"name": "aborted / abort_reason", "type": "bool / str", "desc": "Early-exit flags set via `state.abort(reason)` — replaces the bare `return`s in the original functions with an explicit, inspectable stop condition every routing function checks."},
            {"name": "errors",          "type": "list", "desc": "Per-node failure messages, namespaced as `[node_name] message`."},
            {"name": "nodes_completed", "type": "list", "desc": "Names of nodes that finished successfully, in execution order — the audit trail printed at the end of the run."},
        ],
    },
    "nodes": [
        {
            "name": "resolve_identity",
            "file": "pipeline/company_intake/nodes/resolve_identity.py",
            "lines": 101,
            "desc": (
                "Step 1 for both modes — runs `CompanyIdentityResolver` and applies "
                "mode-specific gating: in intake mode, an already-known company or an "
                "unresolved fuzzy-alias conflict requires `--force` to proceed; in "
                "reaudit mode, the company must already resolve to an existing record "
                "or the run aborts outright (you can't re-audit a company that isn't "
                "in Meridian yet). Populates `state.resolution` and `state.company_id`."
            ),
        },
        {
            "name": "load_db_drugs",
            "file": "pipeline/company_intake/nodes/load_db_drugs.py",
            "lines": 69,
            "desc": (
                "reaudit-mode only — loads every drug Meridian already attributes to "
                "this company (both directly owned and via current_owner_company_id, "
                "covering acquisitions), then flattens their ids/names/aliases into a "
                "normalized token set in `state.db_tokens` for `diff_pipeline` to fuzzy-"
                "match against."
            ),
        },
        {
            "name": "model_guard",
            "file": "pipeline/company_intake/nodes/model_guard.py",
            "lines": 46,
            "desc": (
                "Shared safety check — blocks any live (non-dry-run) write when "
                "`INTAKE_MODEL` is configured to a Haiku-tier model. Haiku is known to "
                "hallucinate company pipelines, and a fabricated drug name reaching "
                "`discovery_queue` is worse than no data at all; `--dry-run` is exempt "
                "since it only does fast structural validation."
            ),
        },
        {
            "name": "research_company",
            "file": "pipeline/company_intake/nodes/research_company.py",
            "lines": 193,
            "desc": (
                "The shared core of both modes — one open-ended Claude call (routed "
                "through `ai_client.run_json`, PromptConfig `company_intake_research`) "
                "asking for a comprehensive company profile: pipeline, deals, and a "
                "relevance assessment against all six active Meridian areas (TL1A, "
                "TSLP, IL-4Rα, FcRn, IGF-1R, T-cell engineering). The same prompt and "
                "result feed `score_areas`+`write_queue` in intake mode and "
                "`diff_pipeline`+`write_gaps` in reaudit mode. Populates `state.research`; "
                "aborts the run if the call fails or returns unparseable JSON."
            ),
        },
        {
            "name": "score_areas",
            "file": "pipeline/company_intake/nodes/score_areas.py",
            "lines": 111,
            "desc": (
                "intake-mode only — filters the research's per-area relevance "
                "assessments down to ones that clear minimum evidence and confidence "
                "thresholds (≥0.5 confidence generally, ≥0.6 for Watchlist, plus at "
                "least one molecule or a high-confidence Direct company-level match), "
                "sorts them by relevance tier, and populates `state.relevant_areas`. "
                "Exists specifically to keep speculative, low-evidence rows out of "
                "discovery_queue."
            ),
        },
        {
            "name": "write_queue",
            "file": "pipeline/company_intake/nodes/write_queue.py",
            "lines": 239,
            "desc": (
                "intake-mode only, and the largest node in the graph — writes one "
                "discovery_queue row per relevant area, after a 30-day dedup check "
                "against existing non-rejected rows for the same company. Maps each "
                "area's relevance tier to overlap/layer/score/relationship fields, "
                "picks the most keyword-relevant drug from the pipeline as the row's "
                "headline entity, and POSTs with raw `requests` (not `_db.sb_post`) so "
                "it can branch on HTTP status — 200/201 success, 409 conflict, or a "
                "fallback retry without the `source` column for environments where "
                "migration v22 hasn't landed. Populates `state.written_areas`."
            ),
        },
        {
            "name": "diff_pipeline",
            "file": "pipeline/company_intake/nodes/diff_pipeline.py",
            "lines": 73,
            "desc": (
                "reaudit-mode only — fuzzy-matches each drug from the fresh research "
                "pull against `state.db_tokens` (cleaned-name substring match, then "
                "word-level token match), splitting the live pipeline into "
                "`state.seen_drugs` (already in Meridian) and `state.new_drugs` (gaps). "
                "Prints a per-drug ✓/✦ diff and a summary line."
            ),
        },
        {
            "name": "write_gaps",
            "file": "pipeline/company_intake/nodes/write_gaps.py",
            "lines": 112,
            "desc": (
                "reaudit-mode only — for each gap drug, scores which active areas its "
                "target/mechanism/indication keywords match (falling back to the "
                "company's own relevant areas if nothing matches), and pushes one "
                "discovery_queue row per matched area tagged `source='re_audit'` and "
                "`discovered_by='company_intake_reaudit'`. Mirrors `write_queue`'s raw-"
                "`requests` status-branching approach. Populates `state.gaps_written`."
            ),
        },
    ],
    "routing": [
        {
            "after": "resolve_identity",
            "function": "_route_after_resolve",
            "branches": [
                {"condition": "`state.aborted`", "to": "END",
                 "desc": "Resolution blocked the run — an existing company without `--force`, an unresolved alias conflict without `--force` (intake), or a company that doesn't exist yet (reaudit)."},
                {"condition": "`state.mode == \"reaudit\"`", "to": "load_db_drugs",
                 "desc": "Identity resolved cleanly for a re-audit — load the company's existing DB drugs before researching."},
                {"condition": "otherwise (`mode == \"intake\"`)", "to": "model_guard",
                 "desc": "Identity resolved cleanly for an intake — no DB drugs to load yet, go straight to the model-tier check."},
            ],
        },
        {
            "after": "load_db_drugs",
            "function": "_route_after_load_db_drugs",
            "branches": [
                {"condition": "`state.aborted`", "to": "END",
                 "desc": "Reserved for a future hard-failure case — load_db_drugs itself never aborts today (a fetch error just yields empty lists), but the routing function checks the flag for consistency with every other step."},
                {"condition": "otherwise", "to": "model_guard",
                 "desc": "DB drugs loaded (or empty) — continue to the shared model-tier guard."},
            ],
        },
        {
            "after": "model_guard",
            "function": "_route_after_model_guard",
            "branches": [
                {"condition": "`state.aborted`", "to": "END",
                 "desc": "A Haiku-tier model is configured for a live (non-dry-run) write — the run stops before spending a research call whose output can't be trusted for writes."},
                {"condition": "otherwise", "to": "research_company",
                 "desc": "Model tier is acceptable (or this is a dry run) — proceed to the shared research call."},
            ],
        },
        {
            "after": "research_company",
            "function": "_route_after_research",
            "branches": [
                {"condition": "`state.aborted`", "to": "END",
                 "desc": "The Claude research call failed or returned unparseable JSON — nothing downstream has anything to work with."},
                {"condition": "`state.mode == \"reaudit\"`", "to": "diff_pipeline",
                 "desc": "Research succeeded for a re-audit — diff the fresh pipeline against the DB token set."},
                {"condition": "otherwise (`mode == \"intake\"`)", "to": "score_areas",
                 "desc": "Research succeeded for an intake — score which active areas this new company is actually relevant to."},
            ],
        },
        {
            "after": "diff_pipeline",
            "function": "_route_after_diff",
            "branches": [
                {"condition": "`state.new_drugs` is non-empty", "to": "write_gaps",
                 "desc": "At least one drug on the live pipeline has no matching DB row — queue those gaps for review."},
                {"condition": "otherwise", "to": "END",
                 "desc": "Every drug on the live pipeline already matches something in the DB — nothing to write, the run ends cleanly."},
            ],
        },
        {
            "after": "score_areas",
            "function": "_route_after_score",
            "branches": [
                {"condition": "`state.relevant_areas` is non-empty", "to": "write_queue",
                 "desc": "At least one area cleared the evidence/confidence thresholds — write discovery_queue rows for them."},
                {"condition": "otherwise", "to": "END",
                 "desc": "Nothing about this company met the bar for any active Meridian area — the run ends without writing speculative rows."},
            ],
        },
    ],
}
