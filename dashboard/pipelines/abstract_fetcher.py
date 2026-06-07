"""
Static description of the Meridian Abstract Fetcher pipeline
(.github/workflows/weekend-abstract-fetcher.yml).

Documents, in execution order, which files the entrypoint script touches,
what each file does, and which steps run in parallel vs. sequentially.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "abstract_fetcher",
    "workflow_name": "Meridian Abstract Fetcher",
    "workflow_file": ".github/workflows/weekend-abstract-fetcher.yml",
    "schedule": "Saturdays 14:00 UTC (10:00 AM ET)",
    "entrypoint": "scripts/abstracts/fetch_abstracts.py",
    "summary": (
        "Weekly sweep that pulls fresh abstracts for Phase 2+ drugs from "
        "Europe PMC and PubMed, then scans bioRxiv/medRxiv for preprints "
        "matching tracked keywords. Everything lands in company_documents."
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
        label="fetch_abstracts.py\n(entrypoint — owns args, ordering, summary)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    subgraph cluster_p1 {
        label="Phase 1 — Drug abstract sweep (all Phase 2+ drugs)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        drug_abstracts [label="drug_abstracts.py\n(business logic)"]
        drug_repo [label="repositories/\ndrug_repository.py"]

        subgraph cluster_p1_parallel {
            label="queried per drug, in parallel"
            style="dotted"
            color="#9aa7b5"
            pencolor="#9aa7b5"
            fontname="Helvetica"
            fontsize=10
            fontcolor="#e8ecf2"

            europe_pmc_1 [label="sources/europe_pmc.py"]
            pubmed [label="sources/pubmed.py"]
        }

        doc_repo_1 [label="repositories/\ndocument_repository.py\n(write)"]
    }

    subgraph cluster_p2 {
        label="Phase 2 — Preprint monitor"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        preprint_monitor [label="preprint_monitor.py\n(business logic)"]
        config [label="config.py\n(PREPRINT_KEYWORDS)"]
        preprint_src [label="sources/preprint.py"]
        doc_repo_2 [label="repositories/\ndocument_repository.py\n(write)"]
    }

    entry -> drug_abstracts [label="  Phase 1"]
    drug_abstracts -> drug_repo
    drug_repo -> europe_pmc_1
    drug_repo -> pubmed
    europe_pmc_1 -> doc_repo_1
    pubmed -> doc_repo_1

    doc_repo_1 -> preprint_monitor [label="  Phase 2\n(after Phase 1 completes)"]
    preprint_monitor -> config
    config -> preprint_src
    preprint_src -> doc_repo_2
}
""",
    "phases": [
        {
            "label": "Entrypoint",
            "note": "Called directly by the GitHub Actions workflow — owns argument parsing, phase ordering, and the run summary.",
            "groups": [
                [
                    {
                        "file": "scripts/abstracts/fetch_abstracts.py",
                        "desc": "Parses CLI flags (--drug, --preprints, --dry-run, --verbose), then runs Phase 1 (drug sweep) followed by Phase 2 (preprint monitor) and prints the final summary.",
                    }
                ],
            ],
        },
        {
            "label": "Phase 1 — Drug abstract sweep",
            "note": "Runs first. Fetches every Phase 2+ drug, then queries both publication sources for each drug in parallel before writing.",
            "groups": [
                [
                    {
                        "file": "scripts/abstracts/drug_abstracts.py",
                        "desc": "Business-logic layer: fetches abstracts for one drug or all Phase 2+ drugs from Europe PMC and PubMed, deduplicates across sources, and builds company_documents rows.",
                    }
                ],
                [
                    {
                        "file": "scripts/abstracts/repositories/drug_repository.py",
                        "desc": "Reads the drug list to sweep from Supabase — either all Phase 2+ drugs (filtered by config.TARGET_STAGES) or a single drug matched by name.",
                    }
                ],
                [
                    {
                        "file": "scripts/abstracts/sources/europe_pmc.py",
                        "desc": "Searches Europe PMC and returns rich publication dicts (pmid, doi, title, authors, journal, abstract), sorted by date — runs alongside pubmed.py for each drug.",
                        "parallel_with": "scripts/abstracts/sources/pubmed.py",
                    },
                    {
                        "file": "scripts/abstracts/sources/pubmed.py",
                        "desc": "Searches PubMed via NCBI E-utilities (esearch → efetch) and normalizes results to the same dict shape as Europe PMC so the two sources can be merged — runs alongside europe_pmc.py for each drug.",
                        "parallel_with": "scripts/abstracts/sources/europe_pmc.py",
                    },
                ],
                [
                    {
                        "file": "scripts/abstracts/repositories/document_repository.py",
                        "desc": "Upserts the merged rows into company_documents, deduplicating on source_url. Shared by both phases.",
                    }
                ],
            ],
        },
        {
            "label": "Phase 2 — Preprint monitor",
            "note": "Runs after Phase 1 finishes. Sweeps bioRxiv/medRxiv for preprints matching a static keyword list.",
            "groups": [
                [
                    {
                        "file": "scripts/abstracts/preprint_monitor.py",
                        "desc": "Business-logic layer: searches bioRxiv/medRxiv for recent preprints matching tracked keywords, deduplicates across keyword groups, and builds company_documents rows.",
                    }
                ],
                [
                    {
                        "file": "scripts/abstracts/config.py",
                        "desc": "Static configuration: TARGET_STAGES (which drug stages Phase 1 sweeps) and PREPRINT_KEYWORDS (the keyword list Phase 2 searches for).",
                    }
                ],
                [
                    {
                        "file": "scripts/abstracts/sources/preprint.py",
                        "desc": "Wraps the Europe PMC client with a SRC:PPR filter so results are restricted to bioRxiv/medRxiv preprints, returning the same rich dict shape with source overridden to \"preprint\".",
                    }
                ],
                [
                    {
                        "file": "scripts/abstracts/repositories/document_repository.py",
                        "desc": "Upserts the preprint rows into company_documents, deduplicating on source_url — the same writer used by Phase 1.",
                    }
                ],
            ],
        },
    ],
}