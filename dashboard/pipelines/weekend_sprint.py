"""
Static description of the Meridian Weekend Sprint pipeline
(.github/workflows/weekend-sprint.yml).

Unlike the other two weekend pipelines, this one is a single 3,018-line
orchestrator script (scripts/weekend_sprint.py) — there is no package of
small files to walk through. So instead of a file-by-file breakdown this
module documents it function-by-function: each `phase_*` is its own unit
of work, run in a fixed order within its block by `run_block()`.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "weekend_sprint",
    "workflow_name": "Meridian Weekend Sprint",
    "workflow_file": ".github/workflows/weekend-sprint.yml",
    "schedule": (
        "13 separate cron triggers from Friday 9 PM ET through Sunday 2 PM ET — "
        "Block A and F run once (open/close the weekend), Blocks B/C/D/E re-run "
        "2-3x each. A `concurrency: weekend-sprint` lock keeps runs from overlapping."
    ),
    "entrypoint": "scripts/weekend_sprint.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "The autonomous weekend orchestrator: 53 phase functions across six "
        "lettered blocks (A-F) that validate schema/governance, enrich drugs "
        "and companies, map relationships, recompute scores, run consistency "
        "QA, and finally write NEXT_SESSION.md and push reporting artifacts "
        "back to GitHub — all while Kyle is away from the keyboard."
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
        fontsize=10,
        margin="0.1,0.06"
    ]

    edge [
        color="#5b6b7d",
        fontcolor="#e8ecf2",
        fontname="Helvetica",
        fontsize=9,
        arrowsize=0.7
    ]

    entry [
        label="weekend_sprint.py --block <A-F>\n(entrypoint — one GitHub Actions job per block,\neach on its own cron trigger; run_block() walks\nits phases in order via the shared PHASE_MAP)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827",
        fontsize=11,
        margin="0.18,0.1"
    ]

    supabase_in [
        label="Supabase\ndrugs · companies · coverage_scores ·\nenrichment_runs · governance_violations · …\n(read here — scoped per phase)",
        shape=cylinder, fillcolor="#ffe4b8", color="#c9890a", fontcolor="#111827", fontsize=10, margin="0.18,0.1"
    ]
    claude_in [
        label="Claude API\n(read here — via lazily-imported\nagent modules: drug_enrichment,\nseed_strategic_views, bd_recommender, …)",
        shape=cylinder, fillcolor="#ffe4b8", color="#c9890a", fontcolor="#111827", fontsize=10, margin="0.18,0.1"
    ]
    github_in [
        label="GitHub Contents API\n(read here — F6 fetches current file\nSHAs before committing)",
        shape=cylinder, fillcolor="#ffe4b8", color="#c9890a", fontcolor="#111827", fontsize=10, margin="0.18,0.1"
    ]

    subgraph cluster_a {
        label="Block A — Validation & Schema  ·  first run: Sat 01:00 UTC"
        style="dashed"; color="#9aa7b5"; pencolor="#9aa7b5"
        fontname="Helvetica"; fontsize=10; fontcolor="#e8ecf2"

        a1 [label="A1 · schema_health"]
        a2 [label="A2 · governance_validation"]
        a3 [label="A3 · source_url_validation"]
        a4 [label="A4 · duplicate_detection"]
        a5 [label="A5 · coverage_compute"]
        a6 [label="A6 · coverage_gap_finder"]
        a7 [label="A7 · trajectory_health"]
        a8 [label="A8 · stale_data_detection"]
        a1 -> a2 -> a3 -> a4 -> a5 -> a6 -> a7 -> a8
    }

    subgraph cluster_b {
        label="Block B — Primary Enrichment  ·  re-runs: Sat 03:00 + 19:00 UTC"
        style="dashed"; color="#9aa7b5"; pencolor="#9aa7b5"
        fontname="Helvetica"; fontsize=10; fontcolor="#e8ecf2"

        b1 [label="B1 · drug_enrichment"]
        b2 [label="B2 · company_enrichment"]
        b3 [label="B3 · bd_angle_enrichment"]
        b4 [label="B4 · risk_summary_enrichment"]
        b5 [label="B5 · mechanism_status"]
        b6 [label="B6 · clinical_details"]
        b7 [label="B7 · deal_enrichment"]
        b8 [label="B8 · partnership_verification"]
        b1 -> b2 -> b3 -> b4 -> b5 -> b6 -> b7 -> b8
    }

    subgraph cluster_c {
        label="Block C — Relationship Mapping  ·  re-runs: Sat 07:00 + Sun 07:00 UTC"
        style="dashed"; color="#9aa7b5"; pencolor="#9aa7b5"
        fontname="Helvetica"; fontsize=10; fontcolor="#e8ecf2"

        c1 [label="C1 · missing_partnerships"]
        c2 [label="C2 · licensing_chains"]
        c3 [label="C3 · codev_attribution"]
        c4 [label="C4 · competitor_mapping"]
        c5 [label="C5 · patent_landscape"]
        c6 [label="C6 · relationship_dating"]
        c7 [label="C7 · conference_catalysts"]
        c8 [label="C8 · regulatory_milestones"]
        c1 -> c2 -> c3 -> c4 -> c5 -> c6 -> c7 -> c8
    }

    subgraph cluster_d {
        label="Block D — Scoring & Synthesis  ·  re-runs: Sat 11:00 + 23:00, Sun 11:00 UTC"
        style="dashed"; color="#9aa7b5"; pencolor="#9aa7b5"
        fontname="Helvetica"; fontsize=10; fontcolor="#e8ecf2"

        d1 [label="D1 · strategic_value_scoring"]
        d2 [label="D2 · competitive_landscape"]
        d3 [label="D3 · drug_competitive_scores"]
        d4 [label="D4 · ailux_bd_analysis"]
        d5 [label="D5 · pipeline_advancement"]
        d6 [label="D6 · area_knowledge_and_catalyst"]
        d7 [label="D7 · patient_intelligence"]
        d8 [label="D8 · coverage_recompute"]
        d9 [label="D9 · target_pair_whitespace_refresh"]
        d10 [label="D10 · indication_priority_refresh"]
        d11 [label="D11 · asset_value_predictions_refresh"]
        d1 -> d2 -> d3 -> d4 -> d5 -> d6 -> d7 -> d8 -> d9 -> d10 -> d11
    }

    subgraph cluster_e {
        label="Block E — Consistency & QA  ·  re-runs: Sat 15:00, Sun 03:00 + 15:00 UTC"
        style="dashed"; color="#9aa7b5"; pencolor="#9aa7b5"
        fontname="Helvetica"; fontsize=10; fontcolor="#e8ecf2"

        e1 [label="E1 · stage_ctgov_xref"]
        e2 [label="E2 · enrichment_consistency"]
        e3 [label="E3 · governance_revalidation"]
        e4 [label="E4 · source_verifier"]
        e5 [label="E5 · consistency_checker"]
        e6 [label="E6 · schema_validation_review"]
        e7 [label="E7 · positive_label_quality"]
        e8 [label="E8 · agent_disagreement"]
        e1 -> e2 -> e3 -> e4 -> e5 -> e6 -> e7 -> e8
    }

    subgraph cluster_f {
        label="Block F — Reporting & Cleanup  ·  final run: Sun 18:00 UTC"
        style="dashed"; color="#9aa7b5"; pencolor="#9aa7b5"
        fontname="Helvetica"; fontsize=10; fontcolor="#e8ecf2"

        f1 [label="F1 · final_coverage"]
        f2 [label="F2 · next_session_md"]
        f3 [label="F3 · sprint_summary"]
        f4 [label="F4 · human_queue_builder"]
        f5 [label="F5 · trajectory_summary"]
        f6 [label="F6 · github_commit"]
        f7 [label="F7 · enrichment_cleanup"]
        f8 [label="F8 · alert_generation"]
        f9 [label="F9 · bd_recommendations"]
        f10 [label="F10 · navigator_lookup_refresh"]
        f1 -> f2 -> f3 -> f4 -> f5 -> f6 -> f7 -> f8 -> f9 -> f10
    }

    governance_out [
        label="Supabase\ngovernance_violations · drug_validation_results\n(written here — new rows opened on rule failure)",
        shape=cylinder, fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827", fontsize=10, margin="0.18,0.1"
    ]
    enrichment_out [
        label="Supabase\ndrugs · companies · coverage_scores ·\ncompany_strategic_views · drug_competitive_scores · …\n(written here — patched/upserted, skipped if --dry-run)",
        shape=cylinder, fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827", fontsize=10, margin="0.18,0.1"
    ]
    sprint_log_out [
        label="Supabase\nweekend_sprint_log\n(written here — one row per phase via run_phase())",
        shape=cylinder, fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827", fontsize=10, margin="0.18,0.1"
    ]
    github_out [
        label="GitHub repo\nNEXT_SESSION.md · navigator_lookup.json\n(written here — committed / deployed to Pages)",
        shape=cylinder, fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827", fontsize=10, margin="0.18,0.1"
    ]

    supabase_in -> entry [label="  reads", style="bold", color="#c9890a", fontcolor="#c9890a"]
    claude_in -> entry [label="  invoked by enrichment\n  & scoring phases", style="bold", color="#c9890a", fontcolor="#c9890a"]

    entry -> a1 [label="  Block A run"]
    a8 -> b1 [label="  Block B run\n  (separately triggered)"]
    b8 -> c1 [label="  Block C run"]
    c8 -> d1 [label="  Block D run"]
    d11 -> e1 [label="  Block E run"]
    e8 -> f1 [label="  Block F run\n  (closes the weekend)"]

    a2 -> governance_out [label="  writes", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    e1 -> governance_out [label="  writes", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    f8 -> governance_out [label="  writes", style="bold", color="#2f9e63", fontcolor="#2f9e63"]

    b1 -> enrichment_out [label="  writes", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    d1 -> enrichment_out [label="  writes", style="bold", color="#2f9e63", fontcolor="#2f9e63"]

    entry -> sprint_log_out [label="  logs every\n  phase result", style="bold", color="#2f9e63", fontcolor="#2f9e63"]

    github_in -> f6 [label="  reads SHAs", style="bold", color="#c9890a", fontcolor="#c9890a"]
    f6 -> github_out [label="  commits", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    f10 -> github_out [label="  deploys", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        supabase_tables [label="Supabase\n(~28 core, scoring & QA tables)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        claude_in [label="Claude API\n(via lazily-imported agent modules)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        github_in [label="GitHub Contents API\n(file SHAs before commit)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Meridian\nWeekend Sprint",
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

        supabase_writes [label="Supabase\n(enrichment, scoring & QA writes)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        sprint_log [label="Supabase\nweekend_sprint_log\n(one row per phase)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        github_out [label="GitHub repo\nNEXT_SESSION.md ·\nnavigator_lookup.json", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    supabase_tables -> pipeline
    claude_in -> pipeline
    github_in -> pipeline
    pipeline -> supabase_writes
    pipeline -> sprint_log
    pipeline -> github_out
}
""",
    "io": {
        "reads": [
            {
                "name": "Supabase — core & scoring tables",
                "kind": "Supabase tables",
                "via": "shared sb_get() helper",
                "desc": (
                    "drugs, companies, trials, drug_targets, deals, company_partnerships, "
                    "coverage_scores, enrichment_runs, governance_violations, "
                    "drug_validation_results, enriched_field_log, news_articles, "
                    "catalyst_calendar, fine_tune_dataset, and ~15 more — read across "
                    "nearly all 53 phases to build worklists, cross-check stages, and "
                    "supply scoring inputs."
                ),
                "scope": (
                    "There is no single global pull — each phase issues its own narrowly "
                    "scoped query, and almost every one carries an explicit `limit`. "
                    "Examples: A1 samples up to 20 orphaned `drugs` rows; A2 reviews up to "
                    "100 open `governance_violations` and up to 200 branded drugs; A3/A8 "
                    "page through recent batches rather than full tables. This caps the "
                    "read volume of any single phase regardless of how large the underlying "
                    "tables grow — `table_exists()` and `sb_get()` are the only two access "
                    "points, called once per phase, never in a loop over the whole table."
                ),
            },
            {
                "name": "Claude API",
                "kind": "External LLM API (via lazily-imported agent modules)",
                "via": "_import_agent() — searches scripts/ + subfolders, imports at call time",
                "desc": (
                    "Eleven phases delegate to standalone agent scripts that each make their "
                    "own Claude calls: drug_enrichment.py, company_enrichment.py, "
                    "seed_strategic_views, patch_competitive_scores_null, "
                    "update_area_knowledge_counts, seed_indication_priorities, "
                    "coverage_gap_finder, source_verifier, consistency_checker, "
                    "human_queue_builder, and bd_recommender. Three more (B3 bd_angle, "
                    "B4 risk_summary, B6 clinical_details) make their own short-form calls "
                    "in-process via a local `_llm_enrich()` helper."
                ),
                "scope": (
                    "For the eleven agent-script phases, weekend_sprint.py never touches the "
                    "Anthropic API itself — it reads `ANTHROPIC_API_KEY` once at startup and "
                    "hands control to whichever agent module a phase needs via "
                    "`_import_agent()`, which finds the `<name>.py` file anywhere under "
                    "scripts/, loads it with `importlib`, and calls its `run(dry_run=DRY_RUN)` "
                    "entrypoint. How many Claude calls that makes — and on how many rows — is "
                    "entirely that module's own logic, not the orchestrator's. If the module "
                    "can't be found or fails to import, `_import_agent()` logs a warning and "
                    "returns `None`, and four phases (A6, E4, E5, F4) fall back to an inline "
                    "`_legacy_*` routine that does the same job with direct Supabase queries "
                    "instead of an LLM. B3/B4/B6 are the exception: they call `_llm_enrich()` "
                    "directly for one short text field per row (bd_angle, risk_summary, "
                    "patient_population/primary_endpoint). As of the 2026-06-08 "
                    "`ai/client.py` migration, `_llm_enrich()` no longer instantiates its own "
                    "raw `anthropic.Anthropic` client (pinned to a stale `claude-sonnet-4-5`) "
                    "— it now routes through the shared `ai_client.run_text()` / "
                    "`PromptConfig` infra on `claude-sonnet-4-6`, the same pattern used "
                    "across the rest of scripts/."
                ),
            },
            {
                "name": "GitHub Contents API",
                "kind": "External API",
                "via": "phase_f6_github_commit()",
                "desc": (
                    "Before committing NEXT_SESSION.md and the sprint summary back to the "
                    "repo, F6 fetches the current file SHAs — required by GitHub's contents "
                    "API to update (rather than create) a file."
                ),
                "scope": (
                    "Two GET calls per run (one per file being updated), authenticated with "
                    "`GITHUB_TOKEN`. This is the only phase that talks to GitHub directly; "
                    "F10's deploy goes through `build_navigator_lookup.py` instead."
                ),
            },
        ],
        "cleaning": (
            "**Per-phase isolation, a global dry-run gate, and bounded reads — there's no "
            "single dedup/clean step because there's no single corpus being merged.** "
            "`run_phase()` wraps every `phase_*()` call in its own try/except: an exception "
            "is logged with a full traceback, recorded as `status=\"error\"` in "
            "`weekend_sprint_log`, and `run_block()` moves on to the next phase after a "
            "2-second pause — so one broken agent module can't take down the rest of a "
            "block, let alone the weekend. The global `DRY_RUN` flag (set by `--dry-run`) "
            "is threaded through every phase: writes still get fetched and synthesized, but "
            "`sb_post`/`sb_patch`/`sb_upsert` calls are skipped and logged as "
            "\"[DRY RUN] would write...\" instead of executed, so the whole orchestrator can "
            "be smoke-tested without mutating Supabase. On the read side, the only cleaning "
            "that happens is the caps described above — `limit=20/100/200` on nearly every "
            "query — plus existence checks before writes (e.g. A2 only opens a new "
            "`governance_violations` row if a matching open one doesn't already exist, which "
            "is itself a dedup of sorts at write time)."
        ),
        "writes": [
            {
                "name": "Supabase — enrichment & scoring tables",
                "kind": "Supabase tables",
                "via": "sb_patch() / sb_upsert() inside Block B/C/D phases",
                "desc": (
                    "drugs, companies, coverage_scores, company_strategic_views, "
                    "drug_competitive_scores, competitive_landscapes, drug_stage_history, "
                    "area_knowledge, catalyst_calendar, target_pair_whitespace, "
                    "asset_value_predictions, indication_patient_intelligence, deals, "
                    "company_partnerships, and more — patched or upserted with newly "
                    "enriched/recomputed values."
                ),
                "scope": (
                    "Volume is bounded by the same per-phase read caps — a phase can only "
                    "write what it pulled. Every write path checks `DRY_RUN` first, so a "
                    "`--dry-run` invocation produces the full log output (\"would update X "
                    "rows\") with zero mutations. This is the largest write surface in the "
                    "pipeline by table count, but the smallest by rows-per-table — most "
                    "phases touch a few dozen rows at most per run."
                ),
            },
            {
                "name": "governance_violations / drug_validation_results",
                "kind": "Supabase tables",
                "via": "sb_post() in phase_a2, phase_e1, phase_f8 (and others on rule failure)",
                "desc": (
                    "New violation/validation rows are opened whenever a governance or "
                    "consistency rule fails — e.g. A2 opens a `brand_name_implies_approved` "
                    "row for any branded drug whose stage isn't in the approved set; E1 logs "
                    "stage/CT.gov mismatches; F8 escalates anything still open into an alert."
                ),
                "scope": (
                    "Write-on-failure only — a clean dataset produces zero new rows. Each "
                    "insert is gated by `DRY_RUN` and (in A2) a pre-check that an equivalent "
                    "open violation doesn't already exist, so reruns don't pile up duplicate "
                    "flags for the same underlying issue."
                ),
            },
            {
                "name": "weekend_sprint_log",
                "kind": "Supabase table",
                "via": "log_phase() (called from run_phase() after every phase) + phase_f3",
                "desc": (
                    "One row per phase execution — phase_id, name, block, status, "
                    "records_processed, duration, and any error message — plus an aggregate "
                    "summary row written by F3 at the end of Block F. This table is also the "
                    "audit trail that F2, F5, and F8 read back from to build NEXT_SESSION.md, "
                    "trajectory stats, and alerts."
                ),
                "scope": (
                    "Exactly one insert per phase run (53 inserts for a full weekend pass, "
                    "more when blocks re-run), plus one summary row from F3. "
                    "`ensure_weekend_sprint_log_table()` creates the table on first use if "
                    "it doesn't exist yet — this is the only table the orchestrator can "
                    "create rather than just read/write."
                ),
            },
            {
                "name": "GitHub repo",
                "kind": "External API / static deploy",
                "via": "phase_f6_github_commit() + phase_f10 → build_navigator_lookup.py",
                "desc": (
                    "F6 commits NEXT_SESSION.md (the open-violations + sprint-log digest "
                    "assembled by F2) and the sprint summary directly to `main`. F10 "
                    "regenerates `navigator_lookup.json` and pushes it live to GitHub Pages "
                    "via `build_navigator_lookup.py`."
                ),
                "scope": (
                    "Two commits per full weekend run (F6 and whatever F10's build script "
                    "produces), each gated by `DRY_RUN` and requiring `GITHUB_TOKEN`. This "
                    "is the only point where the pipeline writes outside Supabase."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Entrypoint & orchestration",
            "note": (
                "Called directly by each GitHub Actions job with --block <letter> (or "
                "--phase <id> for manual single-phase runs). Owns argument parsing, the "
                "PHASE_MAP / BLOCK_PHASES lookup tables, per-phase error isolation, and "
                "weekend_sprint_log writes — every phase below runs through this layer."
            ),
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 51,
                        "desc": "Parses --block / --phase / --dry-run / --sprint-id, ensures the weekend_sprint_log table exists, loads config/weekend_phases.yaml, and dispatches to run_phase() or run_block().",
                    }
                ],
                [
                    {
                        "function": "run_block(block, config)",
                        "lines": 29,
                        "desc": "Looks up the ordered phase list for a block in BLOCK_PHASES, runs each through run_phase() with a 2-second pause between, and returns a succeeded/failed summary.",
                    },
                    {
                        "function": "run_phase(phase_id, config)",
                        "lines": 40,
                        "desc": "Runs one phase function from PHASE_MAP inside a try/except, times it, and writes the result (status, records, duration, error) to weekend_sprint_log via log_phase() — the isolation layer that keeps one bad phase from sinking a block.",
                    },
                ],
            ],
        },
        {
            "label": "Block A — Validation & Schema",
            "note": "First block of the weekend (Sat 01:00 UTC). Confirms the schema is healthy and flags governance/source/duplicate/coverage issues before any enrichment runs.",
            "groups": [
                [
                    {"function": "phase_a1_schema_health()", "lines": 48,
                     "desc": "Confirms all ~28 expected tables exist via table_exists(), and samples up to 20 drugs rows for orphaned company_id values."},
                ],
                [
                    {"function": "phase_a2_governance_validation()", "lines": 54,
                     "desc": "Pulls up to 100 open governance_violations and checks up to 200 branded drugs against the brand_name→approved-stage rule, opening a new violation row for each mismatch (skipped under --dry-run)."},
                ],
                [
                    {"function": "phase_a3_source_url_validation()", "lines": 43,
                     "desc": "Scans deals and company_partnerships for rows missing a source_url."},
                ],
                [
                    {"function": "phase_a4_duplicate_detection()", "lines": 47,
                     "desc": "Compares drug and company name lists for likely duplicates (near-matches that may need merging)."},
                ],
                [
                    {"function": "phase_a5_coverage_compute()", "lines": 53,
                     "desc": "Recalculates coverage_scores for drugs and companies using the same logic as compute_coverage.py."},
                ],
                [
                    {"function": "phase_a6_coverage_gap_finder()", "lines": 21,
                     "desc": "Delegates to the Tier-4 QA agent coverage_gap_finder.py, which identifies 9 categories of missing data and queues them with priority scores; falls back to _phase_a6_legacy_backlog() (47 lines — a direct drugs/companies/coverage_scores scan) if that module can't be imported."},
                ],
                [
                    {"function": "phase_a7_trajectory_health()", "lines": 29,
                     "desc": "Reviews recent enrichment_runs for quality/error-rate trends."},
                ],
                [
                    {"function": "phase_a8_stale_data_detection()", "lines": 39,
                     "desc": "Flags fields recorded in enrichment_runs that haven't been refreshed in 90+ days."},
                ],
            ],
        },
        {
            "label": "Block B — Primary Enrichment",
            "note": "Re-run twice per weekend (Sat 03:00 and 19:00 UTC). The heaviest LLM-driven block — fills in missing drug/company fields via the standalone enrichment agents.",
            "groups": [
                [
                    {"function": "phase_b1_drug_enrichment()", "lines": 64,
                     "desc": "Pulls low-coverage drugs (joined against coverage_scores) and runs them through drug_enrichment.py's LLM enrichment pipeline."},
                ],
                [
                    {"function": "phase_b2_company_enrichment()", "lines": 85,
                     "desc": "Same pattern for companies — selects low-coverage rows and reuses company_enrichment.py's enrichment logic."},
                ],
                [
                    {"function": "phase_b3_bd_angle_enrichment()", "lines": 61,
                     "desc": "Backfills missing bd_angle text for Direct/Adjacent drugs via _llm_enrich() (ai_client.run_text, claude-sonnet-4-6) and logs each change to enriched_field_log."},
                ],
                [
                    {"function": "phase_b4_risk_summary_enrichment()", "lines": 51,
                     "desc": "Backfills missing risk_summary text for Phase 2+ drugs via _llm_enrich() (ai_client.run_text, claude-sonnet-4-6)."},
                ],
                [
                    {"function": "phase_b5_mechanism_status()", "lines": 35,
                     "desc": "Fills null mechanism_status values in competitive_landscapes."},
                ],
                [
                    {"function": "phase_b6_clinical_details()", "lines": 60,
                     "desc": "Fills missing patient_population and primary_endpoint fields for Phase 2/3 drugs via _llm_enrich() (ai_client.run_text, claude-sonnet-4-6)."},
                ],
                [
                    {"function": "phase_b7_deal_enrichment()", "lines": 22,
                     "desc": "Enriches recently-added deals that are missing a source_url or deal_value."},
                ],
                [
                    {"function": "phase_b8_partnership_verification()", "lines": 34,
                     "desc": "Reviews unverified company_partnerships rows for confirmation status."},
                ],
            ],
        },
        {
            "label": "Block C — Relationship Mapping",
            "note": "Re-run twice (Sat 07:00, Sun 07:00 UTC). Builds out company-to-company and drug-to-trial relationships from news, deals, and trial registries.",
            "groups": [
                [
                    {"function": "phase_c1_missing_partnerships()", "lines": 29,
                     "desc": "Scans news_articles for company relationships that aren't yet captured in company_partnerships."},
                ],
                [
                    {"function": "phase_c2_licensing_chains()", "lines": 24,
                     "desc": "Builds asset_transfer_history chains for top drugs from existing deals records."},
                ],
                [
                    {"function": "phase_c3_codev_attribution()", "lines": 38,
                     "desc": "Verifies co-developer relationships against the licensing-attribution governance rule and flags violations."},
                ],
                [
                    {"function": "phase_c4_competitor_mapping()", "lines": 46,
                     "desc": "Cross-references trials against drugs to surface competitor assets that aren't yet tracked via CT.gov."},
                ],
                [
                    {"function": "phase_c5_patent_landscape()", "lines": 19,
                     "desc": "Seeds placeholder patent-landscape notes for drugs that lack them."},
                ],
                [
                    {"function": "phase_c6_relationship_dating()", "lines": 27,
                     "desc": "Backfills valid_from dates on company_partnerships rows that don't have one."},
                ],
                [
                    {"function": "phase_c7_conference_catalysts()", "lines": 52,
                     "desc": "Scans news_articles and catalyst_calendar for upcoming conference data presentations worth tracking."},
                ],
                [
                    {"function": "phase_c8_regulatory_milestones()", "lines": 32,
                     "desc": "Scans news_articles for PDUFA dates and approval-decision announcements."},
                ],
            ],
        },
        {
            "label": "Block D — Scoring & Synthesis",
            "note": "Re-run three times (Sat 11:00 + 23:00, Sun 11:00 UTC) — the longest block (11 phases). Recomputes every derived score and ranking once Block B/C writes have landed.",
            "groups": [
                [
                    {"function": "phase_d1_strategic_value_scoring()", "lines": 78,
                     "desc": "Computes strategic_value_score for every company via the seed_strategic_views agent, writing results to company_strategic_views."},
                ],
                [
                    {"function": "phase_d2_competitive_landscape()", "lines": 30,
                     "desc": "Refreshes mechanism counts in competitive_landscapes from the current drugs table."},
                ],
                [
                    {"function": "phase_d3_drug_competitive_scores()", "lines": 122,
                     "desc": "Recomputes drug_competitive_scores for any rows with a null total_competition_score, delegating null-patching to the patch_competitive_scores_null agent — the largest single phase function in the file."},
                ],
                [
                    {"function": "phase_d4_ailux_bd_analysis()", "lines": 37,
                     "desc": "Runs Ailux-specific BD-candidate analysis honoring the deal-sequencing constraints (e.g. the AbbVie / Oct-2026 readout gate)."},
                ],
                [
                    {"function": "phase_d5_pipeline_advancement()", "lines": 55,
                     "desc": "Detects drug stage changes since the last run and logs them to drug_stage_history."},
                ],
                [
                    {"function": "phase_d6_area_knowledge_and_catalyst()", "lines": 77,
                     "desc": "Refreshes area_knowledge counts (via the update_area_knowledge_counts agent) and related catalyst_calendar entries from drug_targets."},
                ],
                [
                    {"function": "phase_d7_patient_intelligence()", "lines": 39,
                     "desc": "Updates indication_patient_intelligence records with newly enriched patient-population data."},
                ],
                [
                    {"function": "phase_d8_coverage_recompute()", "lines": 4,
                     "desc": "Thin trigger that re-runs the coverage calculation now that Block B/C enrichment writes have landed."},
                ],
                [
                    {"function": "phase_d9_target_pair_whitespace_refresh()", "lines": 50,
                     "desc": "Recounts competing bispecifics in target_pair_whitespace directly from the live drugs table."},
                ],
                [
                    {"function": "phase_d10_indication_priority_refresh()", "lines": 41,
                     "desc": "Calls the seed_indication_priorities agent to recompute all 17 indication-area ranking scores."},
                ],
                [
                    {"function": "phase_d11_asset_value_predictions_refresh()", "lines": 57,
                     "desc": "Recomputes composite scores in asset_value_predictions from the indication_priority scores D10 just refreshed — the last step in the scoring chain."},
                ],
            ],
        },
        {
            "label": "Block E — Consistency & QA",
            "note": "Re-run three times (Sat 15:00, Sun 03:00 + 15:00 UTC). Cross-checks everything Blocks B-D just wrote for drift, contradictions, and disagreement between runs.",
            "groups": [
                [
                    {"function": "phase_e1_stage_ctgov_xref()", "lines": 22,
                     "desc": "Cross-checks drug stage values against trial_registries and writes mismatches to drug_validation_results."},
                ],
                [
                    {"function": "phase_e2_enrichment_consistency()", "lines": 35,
                     "desc": "Flags significant field changes recorded in enriched_field_log between consecutive enrichment runs."},
                ],
                [
                    {"function": "phase_e3_governance_revalidation()", "lines": 4,
                     "desc": "Thin re-run of the A2 governance checks now that this weekend's enrichment writes have landed."},
                ],
                [
                    {"function": "phase_e4_source_verifier()", "lines": 31,
                     "desc": "Delegates to the source_verifier agent to audit citation/source quality; falls back to _phase_e4_legacy_audit() (32 lines — a direct deals scan) if that module can't be imported."},
                ],
                [
                    {"function": "phase_e5_consistency_checker()", "lines": 29,
                     "desc": "Delegates to the consistency_checker agent to detect cross-field contradictions; falls back to _phase_e5_legacy_contradiction() (36 lines — a direct companies/drugs scan) if that module can't be imported."},
                ],
                [
                    {"function": "phase_e6_schema_validation_review()", "lines": 33,
                     "desc": "Reviews the schema_valid flags recorded in enrichment_runs for this weekend's writes."},
                ],
                [
                    {"function": "phase_e7_positive_label_quality()", "lines": 20,
                     "desc": "Verifies the quality of positive-label rows in fine_tune_dataset."},
                ],
                [
                    {"function": "phase_e8_agent_disagreement()", "lines": 49,
                     "desc": "Flags fields that different enrichment runs or agents populated with conflicting values, via enriched_field_log."},
                ],
            ],
        },
        {
            "label": "Block F — Reporting & Cleanup",
            "note": "Final block of the weekend (Sun 18:00 UTC). Assembles everything the prior blocks logged into a digest, pushes it to GitHub, and tidies up.",
            "groups": [
                [
                    {"function": "phase_f1_final_coverage()", "lines": 4,
                     "desc": "Thin trigger for the definitive end-of-sprint coverage calculation."},
                ],
                [
                    {"function": "phase_f2_next_session_md()", "lines": 93,
                     "desc": "Assembles open governance_violations and this weekend's weekend_sprint_log entries into NEXT_SESSION.md, written to the workspace root for Kyle's next working session."},
                ],
                [
                    {"function": "phase_f3_sprint_summary()", "lines": 41,
                     "desc": "Writes one aggregate summary row for the whole sprint to weekend_sprint_log."},
                ],
                [
                    {"function": "phase_f4_human_queue_builder()", "lines": 28,
                     "desc": "Delegates to the human_queue_builder agent to assemble the Monday review queue; falls back to _phase_f4_legacy_review_queue() (50 lines — a direct drug_validation_results / governance_violations scan into monday_review_queue) if that module can't be imported."},
                ],
                [
                    {"function": "phase_f5_trajectory_summary()", "lines": 28,
                     "desc": "Refreshes aggregate trajectory statistics from this weekend's enrichment_runs."},
                ],
                [
                    {"function": "phase_f6_github_commit()", "lines": 59,
                     "desc": "Commits NEXT_SESSION.md and the sprint summary straight to main via the GitHub Contents API (requires GITHUB_TOKEN) — fetches each file's current SHA first so the commit updates rather than recreates it."},
                ],
                [
                    {"function": "phase_f7_enrichment_cleanup()", "lines": 21,
                     "desc": "Archives enrichment_runs rows older than 90 days."},
                ],
                [
                    {"function": "phase_f8_alert_generation()", "lines": 85,
                     "desc": "Cross-references drug_validation_results, governance_violations, and drugs to flag critical issues for Kyle to review first thing Monday."},
                ],
                [
                    {"function": "phase_f9_bd_recommendations()", "lines": 26,
                     "desc": "Delegates to the bd_recommender agent to score every company and refresh the weekly top-20 BD call list with Claude-generated deal framing."},
                ],
                [
                    {"function": "phase_f10_navigator_lookup_refresh()", "lines": 268,
                     "desc": "Rebuilds navigator_lookup.json and deploys it live to GitHub Pages via build_navigator_lookup.py — the longest function in the file by a wide margin (268 of the script's 3,018 lines)."},
                ],
            ],
        },
    ],
}
