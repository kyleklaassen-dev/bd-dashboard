"""
Detail content for the Drug Intel Researcher StateGraph
(scripts/pipeline/drug_intel/ — runs scripts/enrichment/drug_intelligence_researcher.py).

Like research_news.py, the topology diagram on this page is generated live
from the compiled graph (see _topology.py) — only the prose (summary,
state-field meanings, node descriptions, routing rationale) is hand-written here.
"""

STATE_GRAPH = {
    "key": "drug_intel",
    "name": "Drug Intel Researcher",
    "module": "pipeline.drug_intel.graph",
    "builder": "build_drug_intel_graph",
    "entrypoint": "scripts/enrichment/drug_intelligence_researcher.py",
    "summary": (
        "Deep-research run for a single drug: works through a fixed bank of "
        "100 questions split across 8 domains (molecule, clinical, patient, "
        "payer, competitive, regulatory, IP, strategic), asking Claude each "
        "one with the drug record and indication as context, then makes two "
        "more passes over the resulting Q&A to pull out structured clinical "
        "benchmarks and development-timeline milestones. Everything is "
        "upserted to Supabase as it's produced rather than batched at the end, "
        "so a long run that fails partway through still leaves useful data behind. "
        "One conditional branch means a bad drug lookup ends the run immediately "
        "instead of burning ~100 Claude calls on a drug that was never loaded."
    ),
    "state": {
        "module": "pipeline.drug_intel.state",
        "class": "DrugIntelPipelineState",
        "fields": [
            {"name": "drug_id",        "type": "str",  "desc": "Supabase id of the drug being researched — the run's primary input."},
            {"name": "indication",     "type": "str",  "desc": "Disease/indication context threaded into every Claude prompt so answers stay on-target."},
            {"name": "dry_run",        "type": "bool", "desc": "When true, Q&A/benchmarks/timeline are still generated but never written to Supabase."},
            {"name": "verbose",        "type": "bool", "desc": "Prints each question and Claude's raw answer as the run progresses, for spot-checking."},
            {"name": "domains_filter", "type": "Optional[list]", "desc": "Restricts the run to a subset of the 8 domains — used for re-running just one section without redoing the whole 100 questions."},
            {"name": "drug",           "type": "dict", "desc": "The loaded drug record (plus company name) — populated by load_drug, read by every node downstream."},
            {"name": "all_qa",         "type": "list", "desc": "Every question/answer pair produced across all domains — the shared input to both extraction nodes."},
            {"name": "benchmarks",     "type": "list", "desc": "Structured clinical-benchmark records pulled out of the Q&A — output of extract_benchmarks."},
            {"name": "timeline",       "type": "list", "desc": "Structured development-milestone records pulled out of the Q&A — output of extract_timeline."},
            {"name": "qa_stored / benchmarks_stored / timeline_stored", "type": "int", "desc": "Row counts actually written to Supabase by each stage — the run's tangible output."},
            {"name": "errors",          "type": "list", "desc": "Per-node failure messages, namespaced as `[node_name] message`."},
            {"name": "nodes_completed", "type": "list", "desc": "Names of nodes that finished successfully, in execution order — the audit trail printed at the end of the run."},
        ],
    },
    "nodes": [
        {
            "name": "load_drug",
            "file": "pipeline/drug_intel/nodes/load_drug.py",
            "lines": 16,
            "desc": "Fetches the drug record and its company name from Supabase by `drug_id`, populating `state.drug`. Everything downstream depends on this succeeding.",
        },
        {
            "name": "research_domains",
            "file": "pipeline/drug_intel/nodes/research_domains.py",
            "lines": 50,
            "desc": (
                "The core of the run — walks the 8 domains (or just `domains_filter`, "
                "if set), and for each one calls Claude once per question via "
                "`call_claude_for_domain`, immediately upserting the resulting Q&A "
                "with `store_qa` so progress survives a crash. Accumulates everything "
                "into `state.all_qa` and a running `qa_stored` count."
            ),
        },
        {
            "name": "extract_benchmarks",
            "file": "pipeline/drug_intel/nodes/extract_benchmarks.py",
            "lines": 21,
            "desc": "Makes a second pass over `state.all_qa` asking Claude to pull out structured clinical-benchmark records (efficacy/safety figures worth comparing against competitors), then stores them and records the count in `state.benchmarks_stored`.",
        },
        {
            "name": "extract_timeline",
            "file": "pipeline/drug_intel/nodes/extract_timeline.py",
            "lines": 19,
            "desc": "Final pass over `state.all_qa` asking Claude to pull out development-timeline milestones (trial starts, readouts, filings), then stores them and records the count in `state.timeline_stored`.",
        },
    ],
    "routing": [
        {
            "after": "load_drug",
            "function": "_route_after_load",
            "branches": [
                {"condition": "`state.ok` is false (drug lookup failed)", "to": "END",
                 "desc": "The drug_id didn't resolve to a Supabase record — the run ends here rather than asking Claude ~100 questions about a drug it never loaded."},
                {"condition": "otherwise", "to": "research_domains",
                 "desc": "Drug loaded successfully — continue into the question bank."},
            ],
        },
    ],
}
