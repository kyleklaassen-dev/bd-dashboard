"""
Static description of the Meridian Narrative Generation pipeline
(.github/workflows/weekly-narrative-generation.yml).

Documents what generate_area_narratives.py does — orchestrating a full batch
regen of the narrative layer for an area: evidence collection, per-drug overviews
+ Meridian Analysis, area landscape narrative, trust scores, and queue sync.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "narrative_generation",
    "workflow_name": "Meridian Narrative Generation",
    "workflow_file": ".github/workflows/weekly-narrative-generation.yml",
    "schedule": "Sundays 10:00 UTC (6 AM ET) — weekly full regen, before Monday's audit",
    "entrypoint": "scripts/narrative/generate_area_narratives.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Weekly batch driver that regenerates the complete narrative layer for a "
        "disease area (default: `tl1a`). Because every step derives from current "
        "database rows, a weekly full regen is also the staleness fix — every "
        "narrative stays current with whatever enrichment landed during the week. "
        "The pipeline runs in six sequential stages: (1) evidence backfill to close "
        "citation gaps, (2) trial-identity and publication crosswalk enrichment, "
        "(3) per-drug `overview` + `intelligence` sections via `narrative_gen.py`, "
        "(4) area-wide target landscape narrative via `landscape_narrative.py`, "
        "(5) strategic brief (decision layer) via `strategic_brief.py`, and "
        "(6) trust score computation, collection-queue sync, and cross-publication "
        "value verification. Each sub-script is invoked via `subprocess.run()` with "
        "the current Python interpreter, making the driver resilient to sub-script "
        "failures — one failed drug does not abort the batch."
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
        label="generate_area_narratives.py\n(entrypoint — main())",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    drug_targets_in [
        label="Supabase\ndrug_targets\n(read here — drug_id list for area)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_pre {
        label="Pre-processing (unless --no-crosswalk)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        evidence [label="scripts.evidence.backfill_sources\n(citation gap → cited sources)"]
        crosswalk [label="scripts/enrich_trial_identity.py\n(trial-identity + publication crosswalk)"]
    }

    subgraph cluster_perdrug {
        label="Per-drug loop — overview + intelligence sections"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        narrative_gen [label="scripts/narrative_gen.py\n--drug-id <did> --section <sec>\n--composer llm\n(one subprocess per drug per section)"]
    }

    subgraph cluster_finalize {
        label="Finalization (always runs unless --limit chunk incomplete)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        landscape [label="scripts/landscape_narrative.py\n--target <area>"]
        strategic [label="scripts/strategic_brief.py\n--area <area>"]
        trust [label="scripts/compute_trust_score.py\n--area <area> --apply"]
        queue_sync [label="scripts/sync_collection_queue.py\n--area <area>"]
        pub_verify [label="scripts/verify_publication_values.py\n--area <area>"]
    }

    entity_narratives [
        label="Supabase\nentity_narratives\n(written by narrative_gen.py\nlandscape_narrative.py\nstrategic_brief.py)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    trust_scores [
        label="Supabase\ntrust scores + collection queue\n(written by compute_trust_score.py\nsync_collection_queue.py)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    stdout [
        label="stdout\nper-step results\nok/failed counts",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> drug_targets_in [label="  get(drug_targets?target_id=eq.<area>)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    drug_targets_in -> evidence
    evidence -> crosswalk
    crosswalk -> narrative_gen [label="  one subprocess\n  per drug per section"]
    narrative_gen -> entity_narratives [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    narrative_gen -> landscape [label="  after all drugs done"]
    landscape -> strategic
    strategic -> trust
    trust -> queue_sync
    queue_sync -> pub_verify
    landscape -> entity_narratives [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    strategic -> entity_narratives [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    trust -> trust_scores [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    queue_sync -> trust_scores [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    pub_verify -> stdout [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    narrative_gen -> stdout [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        sb_in [label="Supabase\ndrug_targets · drugs · drug_indications\ndrug_clinical_benchmarks · entity_narratives\n(read by driver + sub-scripts)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        claude_in [label="Claude API\n(ai.client — Sonnet/Opus)\nnarrative generation per drug + area", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Narrative\nGeneration",
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

        narratives_out [label="Supabase\nentity_narratives\n(per-drug overview + intelligence\n+ landscape + strategic brief)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        trust_out [label="Supabase\ntrust scores + collection queue", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nstep results + ok/fail counts", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    claude_in -> pipeline
    pipeline -> narratives_out
    pipeline -> trust_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "drug_targets",
                "kind": "Supabase table",
                "via": "narrative_gen.get('drug_targets?target_id=eq.<area>&select=drug_id')",
                "desc": (
                    "Fetches all `drug_id` values linked to the target area. This is the "
                    "complete worklist for the per-drug loop. Deduplicated into a sorted "
                    "set before the loop begins."
                ),
                "scope": (
                    "One query at startup. The `--limit` flag slices the resulting list "
                    "to support chunked runs (resume with `--skip-existing --limit N`, "
                    "then `--finalize-only` at the end)."
                ),
            },
            {
                "name": "entity_narratives (--skip-existing check)",
                "kind": "Supabase table",
                "via": "narrative_gen.get('entity_narratives?entity_type=eq.drug&...')",
                "desc": (
                    "When `--skip-existing` is set, fetches all existing `(entity_id, "
                    "section)` pairs for the area's drugs. Drugs that already have all "
                    "requested sections are filtered out of `todo`, enabling resumable "
                    "chunked runs."
                ),
                "scope": "One query, only when `--skip-existing` is passed.",
            },
            {
                "name": "Sub-script reads (narrative_gen.py, landscape_narrative.py, etc.)",
                "kind": "Supabase tables (multiple, via sub-scripts)",
                "via": "subprocess.run([sys.executable, 'scripts/narrative_gen.py', ...])",
                "desc": (
                    "Each sub-script invoked by the driver reads from Supabase "
                    "independently. `narrative_gen.py` reads drug fields, "
                    "drug_indications, drug_clinical_benchmarks, and existing "
                    "evidence sources. `landscape_narrative.py` reads entity_narratives "
                    "for the area's drugs. `compute_trust_score.py` reads multiple "
                    "evidence tables. The driver does not pass data to sub-scripts — "
                    "each fetches what it needs."
                ),
                "scope": "One subprocess per drug per section for per-drug scripts; one subprocess each for the finalization steps.",
            },
        ],
        "cleaning": (
            "**The driver is a subprocess orchestrator, not a data transformer.** "
            "It does not read or write Supabase directly (except the startup `drug_targets` "
            "query and the optional `entity_narratives` skip-check). All data logic lives "
            "in the sub-scripts. The `run()` helper captures `stdout` and `stderr`, prints "
            "the last line of output for each subprocess, and returns True/False based on "
            "exit code — a failure increments the `fail` counter but does not abort the "
            "loop. This means a single bad drug row or API timeout cannot block the rest "
            "of the batch."
        ),
        "writes": [
            {
                "name": "entity_narratives",
                "kind": "Supabase table (via sub-scripts)",
                "via": "narrative_gen.py / landscape_narrative.py / strategic_brief.py (each invoked as a subprocess)",
                "desc": (
                    "Per-drug `overview` and `intelligence` sections are written by "
                    "`narrative_gen.py`. The target landscape narrative is written by "
                    "`landscape_narrative.py`. The strategic brief (decision layer) is "
                    "written by `strategic_brief.py`. All three write to `entity_narratives` "
                    "with the appropriate `entity_type`, `entity_id`, and `section` values."
                ),
                "scope": (
                    "One row per (drug, section) per run for the per-drug loop. "
                    "One row for the landscape narrative. One row for the strategic brief."
                ),
            },
            {
                "name": "Trust scores and collection queue",
                "kind": "Supabase tables (via sub-scripts)",
                "via": "compute_trust_score.py --apply / sync_collection_queue.py",
                "desc": (
                    "`compute_trust_score.py --apply` writes per-drug trust scores to "
                    "their respective table. `sync_collection_queue.py` updates the "
                    "evidence collection queue for the area. "
                    "`verify_publication_values.py` checks cross-publication consistency "
                    "but only logs findings to stdout (no DB write)."
                ),
                "scope": "Area-scoped writes, once per finalization pass.",
            },
        ],
    },
    "phases": [
        {
            "label": "Subprocess runner helper",
            "note": "run() is the single shared helper used for every sub-script invocation.",
            "groups": [
                [
                    {
                        "function": "run(cmd)",
                        "lines": 8,
                        "desc": (
                            "Invokes `[sys.executable] + cmd` with `cwd` set to the "
                            "parent of the `narrative/` directory (i.e. the `scripts/` "
                            "root). Captures both stdout and stderr. Prints `$ <cmd>` "
                            "and `→ <last_line>` for each call. Returns `True` if exit "
                            "code is 0, `False` otherwise."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main orchestration",
            "note": "main() owns argument parsing, the worklist build, and all six pipeline stages.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 58,
                        "desc": (
                            "Parses `--area`, `--limit`, `--sections`, `--skip-existing`, "
                            "`--no-crosswalk`, `--finalize-only`. "
                            "Builds the drug_id worklist from `drug_targets`. "
                            "Unless `--finalize-only`: (1) runs evidence backfill via "
                            "`scripts.evidence.backfill_sources`; (2) runs trial-identity "
                            "crosswalk via `scripts/enrich_trial_identity.py`; "
                            "(3) iterates every drug in `todo` and for each section runs "
                            "`scripts/narrative_gen.py --composer llm`, counting ok/fail. "
                            "If `--limit` is set and the chunk isn't done, prints a resume "
                            "hint and returns early. "
                            "Finalization (always if not a partial chunk): runs "
                            "`landscape_narrative.py`, `strategic_brief.py`, "
                            "`compute_trust_score.py --apply`, `sync_collection_queue.py`, "
                            "and `verify_publication_values.py` — each via `run()`."
                        ),
                    }
                ],
            ],
        },
    ],
}
