"""
Detail content for the Drug Enrichment StateGraph
(scripts/pipeline/drug/ — runs scripts/enrichment/drug_enrichment.py).

Like research_news.py, the topology diagram on this page is generated live
from the compiled graph (see _topology.py) — only the prose (summary,
state-field meanings, node descriptions, routing rationale) is hand-written here.
"""

STATE_GRAPH = {
    "key": "drug",
    "name": "Drug Enrichment",
    "module": "pipeline.drug.graph",
    "builder": "build_drug_graph",
    "entrypoint": "scripts/enrichment/drug_enrichment.py",
    "summary": (
        "Per-drug field-filling run: loads the drug record plus its company, "
        "targets, indications, and trials from Supabase, computes a coverage "
        "score, and — if that score is below 80% — asks Claude to fill in the "
        "missing fields, validates and sanitizes whatever comes back, writes "
        "only the fields that were actually missing, logs each change with "
        "provenance, and records an enrichment_runs row for observability. "
        "Two conditional branches mean a drug that's already well-enriched, "
        "or an LLM call that fails outright, ends the run early rather than "
        "writing partial or low-confidence data."
    ),
    "state": {
        "module": "pipeline.drug.state",
        "class": "DrugPipelineState",
        "fields": [
            {"name": "drug_id",        "type": "str",  "desc": "Supabase id of the drug being enriched — the run's primary input."},
            {"name": "dry_run",        "type": "bool", "desc": "When true, the run still computes what it would write but skips the Supabase patch."},
            {"name": "ctx",            "type": "dict", "desc": "Drug + company + targets + indications + trials, fetched in one shot — the context every downstream node reads from."},
            {"name": "drug_name",      "type": "str",  "desc": "Display name pulled from `ctx`, used in log lines and provenance records."},
            {"name": "coverage / coverage_before / coverage_after", "type": "int", "desc": "Completeness score (0-100) computed from the drug record — `coverage` doubles as `coverage_before` at load time, and `coverage_after` is recomputed post-write to show the delta."},
            {"name": "missing_fields", "type": "list", "desc": "Field names the drug record is currently missing — the allow-list that `validate` filters Claude's output against."},
            {"name": "prompt",         "type": "str",  "desc": "The enrichment prompt built from `ctx` and sent to Claude — kept on state for debugging/auditing."},
            {"name": "llm_raw",        "type": "dict", "desc": "Parsed JSON returned by Claude — raw, pre-validation. Input to the validate node."},
            {"name": "validated_data", "type": "dict", "desc": "Claude's output after sanitization (overlap enum, catalog_category, source_url, text-length checks)."},
            {"name": "fields_to_write","type": "dict", "desc": "The subset of `validated_data` that's actually missing on the drug record — the only thing the write node patches."},
            {"name": "fields_written", "type": "int",  "desc": "Count of fields actually patched onto the drug — the run's tangible output."},
            {"name": "enrichment_run_id", "type": "Optional[str]", "desc": "id of the enrichment_runs row this execution is tracked under, used by log_run for the final status patch."},
            {"name": "errors",          "type": "list", "desc": "Per-node failure messages, namespaced as `[node_name] message`."},
            {"name": "nodes_completed", "type": "list", "desc": "Names of nodes that finished successfully, in execution order — the audit trail printed at the end of the run."},
        ],
    },
    "nodes": [
        {
            "name": "load_context",
            "file": "pipeline/drug/nodes/load_context.py",
            "lines": 41,
            "desc": "Fetches the drug plus its company/targets/indications/trials in one call, computes the current coverage score and the list of missing fields, and populates `state.ctx`, `state.drug_name`, `state.coverage`, `state.missing_fields`.",
        },
        {
            "name": "synthesize",
            "file": "pipeline/drug/nodes/synthesize.py",
            "lines": 42,
            "desc": "Builds the enrichment prompt from `state.ctx` and sends it to Claude via `ai_client.run_json()` (PromptConfig `drug_enrichment`, claude-sonnet-4-6), logging token counts and cost. Populates `state.prompt` and `state.llm_raw`.",
        },
        {
            "name": "validate",
            "file": "pipeline/drug/nodes/validate.py",
            "lines": 36,
            "desc": "Sanitizes Claude's raw JSON (overlap enum, catalog_category, source_url, text-length checks) via `validate_output`, then narrows the result down to just the fields that are actually missing on the drug — `state.fields_to_write` is deliberately never a superset of `state.missing_fields`.",
        },
        {
            "name": "write",
            "file": "pipeline/drug/nodes/write.py",
            "lines": 75,
            "desc": "Patches the `drugs` table with `fields_to_write`, logs each individual field change to `enriched_field_log` with provenance (old value, new value, source_url), recomputes coverage, and upserts a `coverage_scores` row. Short-circuits cleanly if there's nothing to write or `dry_run` is set.",
        },
        {
            "name": "log_run",
            "file": "pipeline/drug/nodes/log_run.py",
            "lines": 48,
            "desc": "Writes (or patches, if `enrichment_run_id` already exists from model-comparison tooling) an `enrichment_runs` row recording status, duration, model, and records-processed — the observability trail used to compare model versions over time.",
        },
    ],
    "routing": [
        {
            "after": "load_context",
            "function": "_route_after_load",
            "branches": [
                {"condition": "`state.ok` is false (drug not found)", "to": "END",
                 "desc": "The drug_id didn't resolve to a Supabase record — nothing downstream can run without context."},
                {"condition": "`state.coverage` ≥ 80%", "to": "END",
                 "desc": "The drug is already well-enriched — the run exits without spending a Claude call on a record that doesn't need one."},
                {"condition": "otherwise", "to": "synthesize",
                 "desc": "Coverage is below the threshold — continue to ask Claude to fill the gaps."},
            ],
        },
        {
            "after": "synthesize",
            "function": "_route_after_synth",
            "branches": [
                {"condition": "`state.ok` is false (LLM call or JSON parse failed)", "to": "END",
                 "desc": "Claude's response didn't come back as usable JSON — the run ends rather than validating and writing garbage."},
                {"condition": "otherwise", "to": "validate",
                 "desc": "Claude returned parseable JSON — continue to sanitize and filter it."},
            ],
        },
    ],
}
