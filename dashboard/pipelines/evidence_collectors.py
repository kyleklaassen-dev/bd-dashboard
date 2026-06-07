"""
Static description of the Meridian Evidence Collectors pipeline
(.github/workflows/weekend-evidence-collectors.yml).

Documents, in execution order, which files the entrypoint script touches,
what each file does, and which steps run in parallel vs. sequentially.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "evidence_collectors",
    "workflow_name": "Meridian Evidence Collectors",
    "workflow_file": ".github/workflows/weekend-evidence-collectors.yml",
    "schedule": "Saturdays 15:00 UTC (11:00 AM ET) — runs ~1h after the Abstract Fetcher",
    "entrypoint": "scripts/evidence/backfill_sources.py",
    "summary": (
        "Evidence source backfill that walks each tracked drug area, attaches "
        "verified CT.gov trial links and Europe PMC publications to drugs, "
        "then sources patient/epidemiology rows for tracked indications."
    ),
    "dot": r"""
digraph {
    rankdir=TB
    bgcolor="transparent"
    fontcolor="#e8ecf2"

    node [
        shape=box,
        style="rounded,filled",
        fillcolor="#ddf2e3",
        color="#52b788",
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
        label="backfill_sources.py\n(entrypoint — owns args, ordering, summary)",
        fillcolor="#bfe6cc",
        color="#2d8659",
        fontcolor="#111827"
    ]

    subgraph cluster_p1 {
        label="Phase 1 — Drug evidence (areas run sequentially, failures isolated)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        drug_evidence [label="drug_evidence.py\n(business logic, per area)"]
        drug_repo [label="repositories/\ndrug_repository.py"]

        subgraph cluster_p1_parallel {
            label="queried per drug"
            style="dotted"
            color="#9aa7b5"
            pencolor="#9aa7b5"
            fontname="Helvetica"
            fontsize=10
            fontcolor="#e8ecf2"

            ctgov [label="sources/ctgov.py"]
            europe_pmc_1 [label="sources/europe_pmc.py"]
        }

        matcher [label="matching/\ndrug_publication_matcher.py"]
        source_repo [label="repositories/\ndrug_source_repository.py\n(read existing + write)"]
    }

    subgraph cluster_p2 {
        label="Phase 2 — Patient / epidemiology evidence (runs after all areas finish)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        patient_evidence [label="patient_evidence.py\n(business logic)"]
        config [label="config.py\n(DEFAULT_AREAS, DISEASE_MAP)"]
        patient_repo_read [label="repositories/\npatient_intel_repository.py\n(read unsourced rows)"]
        europe_pmc_2 [label="sources/europe_pmc.py"]
        disease_matcher [label="matching/\ndisease_publication_matcher.py"]
        patient_repo_write [label="repositories/\npatient_intel_repository.py\n(patch source_urls)"]
    }

    entry -> drug_evidence [label="  Phase 1\n(per area)"]
    drug_evidence -> drug_repo
    drug_repo -> ctgov
    drug_repo -> europe_pmc_1
    ctgov -> matcher
    europe_pmc_1 -> matcher
    matcher -> source_repo

    source_repo -> patient_evidence [label="  Phase 2\n(after every area finishes)"]
    patient_evidence -> config
    config -> patient_repo_read
    patient_repo_read -> europe_pmc_2
    europe_pmc_2 -> disease_matcher
    disease_matcher -> patient_repo_write
}
""",
    "phases": [
        {
            "label": "Entrypoint",
            "note": "Called directly by the GitHub Actions workflow — owns argument parsing (--areas, --dry-run, --limit, --max-pubs), phase ordering, and the run summary.",
            "groups": [
                [
                    {
                        "file": "scripts/evidence/backfill_sources.py",
                        "desc": "Parses CLI flags, loops Phase 1 over each area (isolating failures so one bad area doesn't stop the rest), then runs Phase 2 once, and prints the final OK/PARTIAL FAILURE summary.",
                    }
                ],
            ],
        },
        {
            "label": "Phase 1 — Drug evidence (CT.gov + Europe PMC)",
            "note": "Areas are processed one at a time (sequential, failure-isolated). For each drug, CT.gov and Europe PMC are queried, results are relevance-filtered, and only new sources are written.",
            "groups": [
                [
                    {
                        "file": "scripts/evidence/drug_evidence.py",
                        "desc": "Orchestrates evidence collection for one drug or one area: pulls CT.gov trial registrations and Europe PMC publications, filters them for relevance, and hands the surviving rows to the source repository.",
                    }
                ],
                [
                    {
                        "file": "scripts/evidence/repositories/drug_repository.py",
                        "desc": "Read-only Supabase access — looks up which drug IDs belong to an area (via drug_targets) and fetches each drug's trial records.",
                    }
                ],
                [
                    {
                        "file": "scripts/evidence/sources/ctgov.py",
                        "desc": "Validates NCT ID format and builds the canonical ClinicalTrials.gov study URL — runs alongside europe_pmc.py for each drug.",
                        "parallel_with": "scripts/evidence/sources/europe_pmc.py",
                    },
                    {
                        "file": "scripts/evidence/sources/europe_pmc.py",
                        "desc": "Searches Europe PMC for publications by drug name (or by disease phrase in Phase 2) and returns raw result dicts for the caller to filter — runs alongside ctgov.py for each drug.",
                        "parallel_with": "scripts/evidence/sources/ctgov.py",
                    },
                ],
                [
                    {
                        "file": "scripts/evidence/matching/drug_publication_matcher.py",
                        "desc": "Relevance guard that checks the drug's name actually appears in a publication's title or abstract, preventing false positives where the name only shows up in references.",
                    }
                ],
                [
                    {
                        "file": "scripts/evidence/repositories/drug_source_repository.py",
                        "desc": "Reads each drug's existing source_urls (so re-runs stay idempotent) and inserts newly-confirmed rows into drug_sources.",
                    }
                ],
            ],
        },
        {
            "label": "Phase 2 — Patient / epidemiology evidence",
            "note": "Runs once, after every area in Phase 1 has finished. Sources epidemiology papers for indication rows that are still missing a real source URL.",
            "groups": [
                [
                    {
                        "file": "scripts/evidence/patient_evidence.py",
                        "desc": "Walks indication_patient_intelligence rows with no real source URL, searches Europe PMC for matching epidemiology papers (skipping rows already sourced or not in DISEASE_MAP), and patches source_urls on the matches.",
                    }
                ],
                [
                    {
                        "file": "scripts/evidence/config.py",
                        "desc": "Static configuration: DEFAULT_AREAS (the core immunology set Phase 1 sweeps) and DISEASE_MAP (indication name → Europe PMC search phrase + relevance token).",
                    }
                ],
                [
                    {
                        "file": "scripts/evidence/repositories/patient_intel_repository.py",
                        "desc": "Reads indication_patient_intelligence rows lacking a source, then later patches the matched source_urls back onto each row — used at both the start and end of Phase 2.",
                    }
                ],
                [
                    {
                        "file": "scripts/evidence/sources/europe_pmc.py",
                        "desc": "Same Europe PMC client as Phase 1, here queried with each indication's disease phrase from DISEASE_MAP.",
                    }
                ],
                [
                    {
                        "file": "scripts/evidence/matching/disease_publication_matcher.py",
                        "desc": "Filters and ranks epidemiology publications — requires a real DOI and a relevance-token match, then scores survivors so epidemiology/burden/prevalence titles rank above generic ones.",
                    }
                ],
            ],
        },
    ],
}
