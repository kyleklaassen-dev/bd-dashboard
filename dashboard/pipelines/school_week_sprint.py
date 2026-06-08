"""
Static description of the School Week Intelligence Sprint pipeline
(.github/workflows/weekly-school-week-sprint.yml).

Unlike the other three pipelines, this workflow has no Python entrypoint
of its own — it's a single GitHub Actions job that detects which weekday
it is and then runs a different hand-picked sequence of *existing*
enrichment/scoring/validation scripts directly, in a shell block, for
that day. So the "phases" below are organized by sprint day rather than
by file-execution-order or function-execution-order.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "school_week_sprint",
    "workflow_name": "School Week Intelligence Sprint",
    "workflow_file": ".github/workflows/weekly-school-week-sprint.yml",
    "schedule": (
        "Mon-Fri, 9 PM ET (01:00 UTC the next day) — one cron entry per "
        "weeknight. The job detects the current weekday and runs only that "
        "day's task; a `school-week-sprint` concurrency lock prevents overlap "
        "with the next night's run."
    ),
    "entrypoint": (
        "(none — the workflow YAML directly sequences existing scripts "
        "per weekday, inside a single `sprint` job)"
    ),
    "unit_key": "file",
    "unit_section_title": "Script-by-script, by sprint day",
    "summary": (
        "A five-night rotation that spreads a week's worth of enrichment "
        "across Monday-Friday: company profiles, molecule/mechanism detail, "
        "100-question drug intelligence seeding, ground-truth validation, "
        "and a Friday competitive-scoring sweep — each night scoped to two "
        "or three competitive areas so no single run does too much."
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
        margin="0.12,0.07"
    ]

    edge [
        color="#5b6b7d",
        fontcolor="#e8ecf2",
        fontname="Helvetica",
        fontsize=9,
        arrowsize=0.7
    ]

    entry [
        label="weekly-school-week-sprint.yml\n(single job — detects today's weekday\nfrom `date -u +%u`, then runs only\nthat day's shell step; manual\ndispatch can force day=all)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827",
        fontsize=11,
        margin="0.18,0.1"
    ]

    supabase_in [
        label="Supabase\ncompanies · drugs · drug_areas ·\ncompany_profiles · validation_tests · …\n(read here — scoped by --area each night)",
        shape=cylinder, fillcolor="#ffe4b8", color="#c9890a", fontcolor="#111827", fontsize=10, margin="0.18,0.1"
    ]
    claude_in [
        label="Claude API\n(read here — company_enrichment,\nmolecule_enrichment,\ndrug_intelligence_researcher)",
        shape=cylinder, fillcolor="#ffe4b8", color="#c9890a", fontcolor="#111827", fontsize=10, margin="0.18,0.1"
    ]
    ctgov_in [
        label="ClinicalTrials.gov API v2\n(read here — Tuesday's ct_gov_sync only)",
        shape=cylinder, fillcolor="#ffe4b8", color="#c9890a", fontcolor="#111827", fontsize=10, margin="0.18,0.1"
    ]

    subgraph cluster_mon {
        label="Monday — Company profile enrichment batch 1"
        style="dashed"; color="#9aa7b5"; pencolor="#9aa7b5"
        fontname="Helvetica"; fontsize=10; fontcolor="#e8ecf2"

        mon_company [label="company_enrichment.py --skip-discovery\n(×3 — tl1a, fcrn, ibd)"]
        mon_rank [label="write_ranking_snapshots.py"]
        mon_company -> mon_rank
    }

    subgraph cluster_tue {
        label="Tuesday — Mechanism + source_url enrichment"
        style="dashed"; color="#9aa7b5"; pencolor="#9aa7b5"
        fontname="Helvetica"; fontsize=10; fontcolor="#e8ecf2"

        tue_molecule [label="molecule_enrichment.py\n(×3 — tl1a, ibd, fcrn)"]
        tue_ctgov [label="ct_gov_sync.py --area tl1a"]
        tue_molecule -> tue_ctgov
    }

    subgraph cluster_wed {
        label="Wednesday — 100Q intelligence seeding"
        style="dashed"; color="#9aa7b5"; pencolor="#9aa7b5"
        fontname="Helvetica"; fontsize=10; fontcolor="#e8ecf2"

        wed_researcher [label="drug_intelligence_researcher.py\n--area tl1a --limit 10"]
        wed_company [label="company_enrichment.py --skip-discovery\n(×2 — igf1r, atopy)"]
        wed_researcher -> wed_company
    }

    subgraph cluster_thu {
        label="Thursday — Company profiles pass 2 + validation"
        style="dashed"; color="#9aa7b5"; pencolor="#9aa7b5"
        fontname="Helvetica"; fontsize=10; fontcolor="#e8ecf2"

        thu_company [label="company_enrichment.py --skip-discovery\n(×2 — tslp, il4ra)"]
        thu_validate [label="validate_ground_truth.py\n--write-results"]
        thu_company -> thu_validate
    }

    subgraph cluster_fri {
        label="Friday — Competitive scoring sweep + ranking"
        style="dashed"; color="#9aa7b5"; pencolor="#9aa7b5"
        fontname="Helvetica"; fontsize=10; fontcolor="#e8ecf2"

        fri_scores [label="apply_competitive_scores_v56.py\n⚠ not present in scripts/", fillcolor="#f6dada", color="#c2554f"]
        fri_rank [label="write_ranking_snapshots.py"]
        fri_validate [label="validate_ground_truth.py\n--write-results"]
        fri_coverage [label="compute_coverage.py"]
        fri_scores -> fri_rank -> fri_validate -> fri_coverage
    }

    daily [
        label="write_ranking_snapshots.py\n(Daily ranking snapshot — if: always(),\nruns again after whichever day's task ran)",
        fillcolor="#dbe9fb", color="#5b8def", fontcolor="#111827"
    ]

    supabase_in -> entry [label="  reads", style="bold", color="#c9890a", fontcolor="#c9890a"]
    claude_in -> entry [label="  invoked by\n  enrichment scripts", style="bold", color="#c9890a", fontcolor="#c9890a"]
    ctgov_in -> tue_ctgov [label="  syncs trials", style="bold", color="#c9890a", fontcolor="#c9890a"]

    entry -> mon_company [label="  if day == monday"]
    entry -> tue_molecule [label="  if day == tuesday"]
    entry -> wed_researcher [label="  if day == wednesday"]
    entry -> thu_company [label="  if day == thursday"]
    entry -> fri_scores [label="  if day == friday"]

    mon_rank -> daily
    tue_ctgov -> daily
    wed_company -> daily
    thu_validate -> daily
    fri_coverage -> daily

    supabase_out [
        label="Supabase\ncompany_profiles · drugs · molecule_intelligence ·\ntrials · drug_intelligence_qa · coverage_scores · …\n(written here — patched/upserted per script)",
        shape=cylinder, fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827", fontsize=10, margin="0.18,0.1"
    ]
    rankings_out [
        label="Supabase\nnext_gen_rankings\n(daily snapshot — written here,\nbrowser only ever reads it)",
        shape=cylinder, fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827", fontsize=10, margin="0.18,0.1"
    ]

    entry -> supabase_out [label="  writes", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    daily -> rankings_out [label="  writes", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        supabase_tables [label="Supabase\n(companies · drugs · drug_areas ·\ncompany_profiles · validation_tests · …)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        claude_in [label="Claude API\n(enrichment & research scripts)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        ctgov_in [label="ClinicalTrials.gov API v2\n(Tuesday only)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="School Week\nIntelligence Sprint",
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

        supabase_writes [label="Supabase\n(company_profiles · molecule_intelligence ·\ntrials · drug_intelligence_qa ·\ncoverage_scores · …)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        rankings_out [label="Supabase\nnext_gen_rankings\n(daily snapshot)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    supabase_tables -> pipeline
    claude_in -> pipeline
    ctgov_in -> pipeline
    pipeline -> supabase_writes
    pipeline -> rankings_out
}
""",
    "io": {
        "reads": [
            {
                "name": "Supabase — companies, drugs & ontology tables",
                "kind": "Supabase tables",
                "via": "each script's own Supabase REST client",
                "desc": (
                    "companies, drugs, drug_areas, company_profiles, deals, trials, "
                    "canonical_drugs, validation_tests, and the coverage source tables — "
                    "read by every script in the rotation to build that night's worklist."
                ),
                "scope": (
                    "Nothing here is a global pull — every invocation is scoped by "
                    "`--area <name>`, and a given weeknight only ever touches two or "
                    "three of the platform's competitive areas (Monday: tl1a/fcrn/ibd, "
                    "Tuesday: tl1a/ibd/fcrn, Wednesday: tl1a/igf1r/atopy, Thursday: "
                    "tslp/il4ra, Friday: whatever apply_competitive_scores_v56 and "
                    "compute_coverage touch platform-wide). `--skip-discovery` on every "
                    "company_enrichment.py call also turns off Step 1 (Entity Discovery) "
                    "of its 7-step pipeline, so these runs only refresh companies already "
                    "tracked — they never search for new ones."
                ),
            },
            {
                "name": "Claude API",
                "kind": "External LLM API",
                "via": "company_enrichment.py · molecule_enrichment.py · drug_intelligence_researcher.py",
                "desc": (
                    "Three of the rotation's scripts make their own Claude calls: "
                    "company_enrichment.py (profiles, deals, catalysts — Mon/Wed/Thu), "
                    "molecule_enrichment.py (mechanism_detail + confidence level, reasoning "
                    "from training knowledge with no live web search — Tue), and "
                    "drug_intelligence_researcher.py (the 100-question / 8-domain seed — Wed)."
                ),
                "scope": (
                    "Bounded the same way the reads are: by `--area` and, on Wednesday, an "
                    "explicit `--limit 10` that caps the 100Q seeding to 10 drugs per run. "
                    "Each script owns its own prompt design and call volume — the workflow "
                    "just decides which script runs on which night."
                ),
            },
            {
                "name": "ClinicalTrials.gov API v2",
                "kind": "External API",
                "via": "ct_gov_sync.py (Tuesday step only)",
                "desc": (
                    "Pipeline Step 3 — mirrors CT.gov data into the `trials` table for "
                    "every drug in the given area: known NCT IDs are fetched directly, "
                    "everything else is searched by sponsor/intervention."
                ),
                "scope": (
                    "Runs once per week (Tuesday, `--area tl1a` only) — the lightest-touch "
                    "external read in the rotation. Full structured fields (status, phase, "
                    "enrollment, arms, endpoints, dates, sponsor) are parsed per trial."
                ),
            },
        ],
        "cleaning": (
            "**`continue-on-error: true` on every day's step, plus `--area` scoping and "
            "`--skip-discovery`/`--limit` flags, are the whole cleaning story here — there's "
            "no shared dedup/merge layer because each script is independent and already "
            "owns its own.** If one night's scripts throw (the clearest example: Friday's "
            "first line calls `scripts/apply_competitive_scores_v56.py`, which doesn't "
            "exist in the repo — it was likely retired or renamed during a refactor), "
            "`continue-on-error` swallows the failure and the job moves on to the next "
            "line, so write_ranking_snapshots → validate_ground_truth → compute_coverage "
            "still run that night even though the scoring step silently failed first. "
            "`--skip-discovery` keeps company_enrichment.py from spending a run on Step 1 "
            "(Entity Discovery) on weeknights — discovery only matters when you're adding "
            "new companies, not refreshing tracked ones. `--area` is the actual scoping "
            "mechanism: it's passed to every enrichment/sync script and is what keeps a "
            "single weeknight from re-touching the entire platform. The always-on "
            "`write_ranking_snapshots.py` step at the bottom (`if: always()`) re-runs "
            "regardless of whether the day's primary task succeeded, failed, or was "
            "skipped — guaranteeing `next_gen_rankings` gets a fresh daily snapshot either way."
        ),
        "writes": [
            {
                "name": "Supabase — enrichment & scoring tables",
                "kind": "Supabase tables",
                "via": "each script's own sb_patch()/sb_upsert() calls",
                "desc": (
                    "company_profiles, companies, deals, catalysts, drugs, "
                    "molecule_intelligence, trials, drug_intelligence_qa, "
                    "drug_clinical_benchmarks, drug_development_timelines, "
                    "validation_tests results, coverage_scores, and more — patched or "
                    "upserted by whichever script ran that night."
                ),
                "scope": (
                    "Same `--area`/`--limit`/`--skip-discovery` bounds as the reads — each "
                    "script can only write what it pulled and processed for its 2-3 "
                    "assigned areas. compute_coverage.py (Friday) is the one script here "
                    "that legitimately writes platform-wide: it upserts coverage_scores by "
                    "`entity_id`/`area_id` across every company and area, not just the "
                    "night's scoped subset."
                ),
            },
            {
                "name": "next_gen_rankings",
                "kind": "Supabase table",
                "via": "write_ranking_snapshots.py — runs after Monday/Friday's primary task AND every night via the always-on daily step",
                "desc": (
                    "A daily snapshot row per next-gen bispecific program — entity_id, "
                    "area_id, rank_position, total_score, stage, competitive_relevance, "
                    "is_ailux — captured immediately after drug_competitive_scores changes "
                    "so the dashboard's ranking history stays gap-free. The browser only "
                    "ever reads this table; this script is its sole writer."
                ),
                "scope": (
                    "Up to two snapshot passes on Monday and Friday nights (once as part "
                    "of that day's task, once via the always-on daily step) and one on "
                    "Tue/Wed/Thu — never more than a couple of upserts per run."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Monday — Company profile enrichment batch 1",
            "note": "Runs the systematic intelligence pipeline (minus discovery) for three competitive areas, then snapshots rankings.",
            "groups": [
                [
                    {
                        "file": "scripts/enrichment/company_enrichment.py",
                        "lines": 3261,
                        "desc": "Run three times (--area tl1a, fcrn, ibd, all with --skip-discovery): the full 7-step systematic intelligence pipeline minus Step 1 (Entity Discovery) — refreshes company_profiles, deals, catalysts, and related fields via Claude for every company already tracked in that area.",
                    }
                ],
                [
                    {
                        "file": "scripts/scoring/write_ranking_snapshots.py",
                        "lines": 132,
                        "desc": "Captures the daily next_gen_rankings snapshot (entity_id, area_id, rank_position, total_score, stage, competitive_relevance, is_ailux) for every next-gen bispecific program.",
                    }
                ],
            ],
        },
        {
            "label": "Tuesday — Mechanism detail + source_url enrichment",
            "note": "Targets molecule-level fields and re-syncs trial data for the TL1A area.",
            "groups": [
                [
                    {
                        "file": "scripts/enrichment/molecule_enrichment.py",
                        "lines": 352,
                        "desc": "Run three times (--area tl1a, ibd, fcrn): enriches molecule_intelligence (mechanism_detail + a high/medium/low confidence rating) for each area's drugs using Claude — reasons from training knowledge and Supabase context only, no live web search.",
                    }
                ],
                [
                    {
                        "file": "scripts/sync/ct_gov_sync.py",
                        "lines": 1363,
                        "desc": "Pipeline Step 3 (--area tl1a): mirrors ClinicalTrials.gov data into the trials table — fetches known NCT IDs directly from the CT.gov API v2, searches by sponsor/intervention for the rest, and parses full structured fields (status, phase, enrollment, arms, endpoints, dates, sponsor).",
                    }
                ],
            ],
        },
        {
            "label": "Wednesday — 100Q intelligence seeding for top competitors",
            "note": "Seeds the deep, 100-question research layer for the highest-priority TL1A drugs, then enriches two adjacent-area company sets.",
            "groups": [
                [
                    {
                        "file": "scripts/enrichment/drug_intelligence_researcher.py",
                        "lines": 675,
                        "desc": "(--area tl1a --limit 10): researches up to 10 TL1A drugs against all 100 Meridian intelligence questions across 8 domains, writing rows to drug_intelligence_qa, drug_clinical_benchmarks, and drug_development_timelines.",
                    }
                ],
                [
                    {
                        "file": "scripts/enrichment/company_enrichment.py",
                        "lines": 3261,
                        "desc": "Run twice more (--area igf1r, atopy, both with --skip-discovery) — same discovery-skipped profile-enrichment pass as Monday, just for two different competitive areas.",
                    }
                ],
            ],
        },
        {
            "label": "Thursday — Company profiles pass 2 + validation expansion",
            "note": "A second weekly profile-enrichment pass for two more areas, capped off by a full ground-truth validation run.",
            "groups": [
                [
                    {
                        "file": "scripts/enrichment/company_enrichment.py",
                        "lines": 3261,
                        "desc": "Run twice more (--area tslp, il4ra, both with --skip-discovery) — the third weeknight to use this same discovery-skipped enrichment pass, rounding out the week's area coverage.",
                    }
                ],
                [
                    {
                        "file": "scripts/validation/validate_ground_truth.py",
                        "lines": 589,
                        "desc": "(--write-results): runs every row in validation_tests against live Supabase data and persists pass/fail results back to the DB — the regression check that catches drift from the week's enrichment writes so far.",
                    }
                ],
            ],
        },
        {
            "label": "Friday — Competitive scoring sweep + ranking snapshots",
            "note": "The week's heaviest, most platform-wide night — recomputes scores and coverage, then re-validates and re-snapshots everything. continue-on-error masks a broken first step (see below).",
            "groups": [
                [
                    {
                        "file": "scripts/apply_competitive_scores_v56.py",
                        "lines": 0,
                        "desc": "⚠ Referenced by the workflow but not present anywhere in scripts/ — likely retired or renamed during a refactor. Because the step has continue-on-error: true, this silently fails every Friday and the rest of the night's scripts still run.",
                    }
                ],
                [
                    {
                        "file": "scripts/scoring/write_ranking_snapshots.py",
                        "lines": 132,
                        "desc": "Same daily ranking-snapshot capture as Monday — runs again here regardless of whether the scoring step above succeeded.",
                    }
                ],
                [
                    {
                        "file": "scripts/validation/validate_ground_truth.py",
                        "lines": 589,
                        "desc": "(--write-results): the week's second full validation pass — confirms nothing drifted after Thursday's checkpoint and Friday's (attempted) scoring sweep.",
                    }
                ],
                [
                    {
                        "file": "scripts/scoring/compute_coverage.py",
                        "lines": 609,
                        "desc": "Recomputes per-company, per-area coverage_scores across all 9 diagnostic dimensions and upserts them by entity_id/area_id — the one script in this entire workflow that legitimately runs platform-wide rather than scoped to 2-3 areas.",
                    }
                ],
            ],
        },
        {
            "label": "Daily — always-on ranking snapshot",
            "note": "The workflow's final step, gated on if: always() — runs every single night regardless of which day's task ran, succeeded, or failed, so next_gen_rankings never has a gap.",
            "groups": [
                [
                    {
                        "file": "scripts/scoring/write_ranking_snapshots.py",
                        "lines": 132,
                        "desc": "Captures one more next_gen_rankings snapshot at the very end of the run — the workflow's safety net for keeping the dashboard's ranking history continuous.",
                    }
                ],
            ],
        },
    ],
}
