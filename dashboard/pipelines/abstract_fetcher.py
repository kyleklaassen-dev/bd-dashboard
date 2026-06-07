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

    drugs_table [
        label="Supabase\ndrugs\n(read here — Phase 2+ worklist)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    epmc_api [
        label="Europe PMC API\n(read here)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    pubmed_api [
        label="PubMed / NCBI\nE-utilities\n(read here)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
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

        doc_repo_1 [label="repositories/\ndocument_repository.py"]
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
        doc_repo_2 [label="repositories/\ndocument_repository.py"]
    }

    company_documents [
        label="Supabase\ncompany_documents\n(persisted here — upsert on source_url)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    entry -> drug_abstracts [label="  Phase 1"]
    drug_abstracts -> drug_repo
    drugs_table -> drug_repo [label="  reads", style="bold", color="#c9890a", fontcolor="#c9890a"]
    drug_repo -> europe_pmc_1
    drug_repo -> pubmed
    epmc_api -> europe_pmc_1 [label="  queries\n  (per drug)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    pubmed_api -> pubmed [label="  queries\n  (per drug)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    europe_pmc_1 -> doc_repo_1
    pubmed -> doc_repo_1
    doc_repo_1 -> company_documents [label="  writes", style="bold", color="#2f9e63", fontcolor="#2f9e63"]

    doc_repo_1 -> preprint_monitor [label="  Phase 2\n(after Phase 1 completes)"]
    preprint_monitor -> config
    config -> preprint_src
    epmc_api -> preprint_src [label="  queries\n  (SRC:PPR filter)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    preprint_src -> doc_repo_2
    doc_repo_2 -> company_documents [label="  writes", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        drugs_table [label="Supabase\ndrugs", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        epmc_in [label="Europe PMC API", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        pubmed_in [label="PubMed\n(NCBI E-utilities)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        preprint_in [label="bioRxiv / medRxiv\n(via Europe PMC SRC:PPR)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Meridian\nAbstract Fetcher",
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

        company_documents [label="Supabase\ncompany_documents\n(upsert on source_url)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    drugs_table -> pipeline
    epmc_in -> pipeline
    pubmed_in -> pipeline
    preprint_in -> pipeline
    pipeline -> company_documents
}
""",
    "io": {
        "reads": [
            {
                "name": "drugs",
                "kind": "Supabase table",
                "via": "repositories/drug_repository.py",
                "desc": "Pulls id, name, dev_code, target, stage, and company_id for every Phase 2+ drug (or a single name match) — this is the worklist of drugs to sweep, and it supplies the company_id/target/phase that get embedded in each document written downstream.",
                "scope": (
                    "One batched query, capped at 80 rows: `get_phase2_plus_drugs()` filters "
                    "`stage IN (...)` against the static `TARGET_STAGES` set (phase_2 through "
                    "approved/filed) and applies `limit=80`. In `--drug <name>` mode it instead "
                    "calls `find_by_name()`, an `ilike '*name*'` partial match capped at 5 rows. "
                    "Either way this runs once per pipeline execution — not per drug."
                ),
            },
            {
                "name": "Europe PMC",
                "kind": "External API",
                "via": "sources/europe_pmc.py",
                "desc": "Searched by drug name; returns rich publication records — title, authors, journal, abstract, pmid/doi, publication date.",
                "scope": (
                    "Per-drug, not global: `_fetch_and_dedup()` builds up to 2 queries per drug "
                    "— the bare drug name, and \"`<name> <target>`\" if the drug has a target — "
                    "and asks Europe PMC for up to 6 results per query (`max_results=6`), sorted "
                    "newest-first. So worst case ≈ 2 queries × 6 results × 80 drugs per run, "
                    "though most drugs return far fewer (or zero) hits."
                ),
            },
            {
                "name": "PubMed (NCBI E-utilities)",
                "kind": "External API",
                "via": "sources/pubmed.py",
                "desc": "esearch then efetch by drug name; results are normalized to the same shape as Europe PMC so the two sources merge cleanly.",
                "scope": (
                    "Same per-drug query pair as Europe PMC, but capped lower — `max_results=4` "
                    "per query. `esearch` returns up to 4 PMIDs, then a single `efetch` batch-call "
                    "retrieves their full XML records (title/abstract/journal/date parsed out via "
                    "regex). Results merge into the same pool Europe PMC populates."
                ),
            },
            {
                "name": "bioRxiv / medRxiv",
                "kind": "External API (via Europe PMC, SRC:PPR filter)",
                "via": "sources/preprint.py",
                "desc": "Searched using the static PREPRINT_KEYWORDS list from config.py to catch early-stage research before it's formally published.",
                "scope": (
                    "Phase 2 only — runs once per pipeline execution, independent of the drug "
                    "list. Loops the 13 hard-coded phrases in `PREPRINT_KEYWORDS` (e.g. "
                    "\"TL1A DR3 IBD\", \"tulisokibart\"), wraps each in `(<phrase>) SRC:PPR` to "
                    "restrict Europe PMC to preprints, and pulls up to 3 results per keyword "
                    "(`max_results=3`) — so at most 13 × 3 = 39 raw hits before dedup."
                ),
            },
        ],
        "cleaning": (
            "**Two layers of dedup, then a hard cap.** Within `_fetch_and_dedup()`, every "
            "Europe PMC + PubMed result is keyed by `pmid` (falling back to `source_url`) and "
            "added to a `seen` set — so the same paper surfacing from both sources, or from "
            "both the bare-name and name+target queries, only counts once. The merged, deduped "
            "list is then hard-capped to the **top 12** results per drug (`results[:12]`) before "
            "row-building. A result is dropped entirely if it has neither a `pmid` nor a `doi` "
            "(no stable URL to dedupe or link to), and `build_doc_row()` truncates every text "
            "field to safe lengths (title 400 chars, authors 500, abstract 3000, etc.) and "
            "normalizes `pub_date` to `YYYY-MM-DD` — clearing it outright if it's an unparseable "
            "month-name format. The preprint sweep follows the same dedup-by-`source_url` "
            "pattern across all 13 keyword groups."
        ),
        "writes": [
            {
                "name": "company_documents",
                "kind": "Supabase table",
                "via": "repositories/document_repository.py",
                "desc": "Upserted on source_url (sb_upsert, on_conflict=\"source_url\") — each row carries company_id, drug_id, document_type (abstract / clinical_data / other), title, authors, journal, publication_date, source_url, pubmed_id, doi, abstract_text, drug_names, target, and phase. Upserting on source_url makes weekly reruns idempotent: existing rows refresh in place instead of duplicating.",
                "scope": (
                    "Written in two batches per run — once after each drug's abstracts are "
                    "collected (≤12 rows/drug, ×≤80 drugs), and once for the whole preprint "
                    "sweep (≤39 rows). `upsert_documents()` is a thin pass-through to "
                    "`sb_upsert(..., on_conflict=\"source_url\")`, so the actual ceiling on new "
                    "rows per run is governed entirely by the read-side caps above, not by "
                    "anything on the write side."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Entrypoint",
            "note": "Called directly by the GitHub Actions workflow — owns argument parsing, phase ordering, and the run summary.",
            "groups": [
                [
                    {
                        "file": "scripts/abstracts/fetch_abstracts.py",
                        "lines": 105,
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
                        "lines": 155,
                        "desc": "Business-logic layer: fetches abstracts for one drug or all Phase 2+ drugs from Europe PMC and PubMed, deduplicates across sources, and builds company_documents rows.",
                    }
                ],
                [
                    {
                        "file": "scripts/abstracts/repositories/drug_repository.py",
                        "lines": 33,
                        "desc": "Reads the drug list to sweep from Supabase — either all Phase 2+ drugs (filtered by config.TARGET_STAGES) or a single drug matched by name.",
                    }
                ],
                [
                    {
                        "file": "scripts/abstracts/sources/europe_pmc.py",
                        "lines": 70,
                        "desc": "Searches Europe PMC and returns rich publication dicts (pmid, doi, title, authors, journal, abstract), sorted by date — runs alongside pubmed.py for each drug.",
                        "parallel_with": "scripts/abstracts/sources/pubmed.py",
                    },
                    {
                        "file": "scripts/abstracts/sources/pubmed.py",
                        "lines": 91,
                        "desc": "Searches PubMed via NCBI E-utilities (esearch → efetch) and normalizes results to the same dict shape as Europe PMC so the two sources can be merged — runs alongside europe_pmc.py for each drug.",
                        "parallel_with": "scripts/abstracts/sources/europe_pmc.py",
                    },
                ],
                [
                    {
                        "file": "scripts/abstracts/repositories/document_repository.py",
                        "lines": 20,
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
                        "lines": 99,
                        "desc": "Business-logic layer: searches bioRxiv/medRxiv for recent preprints matching tracked keywords, deduplicates across keyword groups, and builds company_documents rows.",
                    }
                ],
                [
                    {
                        "file": "scripts/abstracts/config.py",
                        "lines": 31,
                        "desc": "Static configuration: TARGET_STAGES (which drug stages Phase 1 sweeps) and PREPRINT_KEYWORDS (the keyword list Phase 2 searches for).",
                    }
                ],
                [
                    {
                        "file": "scripts/abstracts/sources/preprint.py",
                        "lines": 19,
                        "desc": "Wraps the Europe PMC client with a SRC:PPR filter so results are restricted to bioRxiv/medRxiv preprints, returning the same rich dict shape with source overridden to \"preprint\".",
                    }
                ],
                [
                    {
                        "file": "scripts/abstracts/repositories/document_repository.py",
                        "lines": 20,
                        "desc": "Upserts the preprint rows into company_documents, deduplicating on source_url — the same writer used by Phase 1.",
                    }
                ],
            ],
        },
    ],
}