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
        label="backfill_sources.py\n(entrypoint — owns args, ordering, summary)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    drug_tables [
        label="Supabase\ndrug_targets · drugs · trials\n(read here — area → drug worklist)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    ctgov_api [
        label="ClinicalTrials.gov API\n(read here)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
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

    drug_sources_existing [
        label="Supabase\ndrug_sources\n(read here — existing URLs, dedup)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    patient_unsourced [
        label="Supabase\nindication_patient_intelligence\n(read here — rows missing sources)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
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
        source_repo [label="repositories/\ndrug_source_repository.py"]
    }

    drug_sources_write [
        label="Supabase\ndrug_sources\n(persisted here — insert new rows)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

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
        patient_repo_read [label="repositories/\npatient_intel_repository.py"]
        europe_pmc_2 [label="sources/europe_pmc.py"]
        disease_matcher [label="matching/\ndisease_publication_matcher.py"]
        patient_repo_write [label="repositories/\npatient_intel_repository.py"]
    }

    patient_write [
        label="Supabase\nindication_patient_intelligence\n(persisted here — patch source_urls)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    entry -> drug_evidence [label="  Phase 1\n(per area)"]
    drug_evidence -> drug_repo
    drug_tables -> drug_repo [label="  reads", style="bold", color="#c9890a", fontcolor="#c9890a"]
    drug_repo -> ctgov
    drug_repo -> europe_pmc_1
    ctgov_api -> ctgov [label="  verifies", style="bold", color="#c9890a", fontcolor="#c9890a"]
    epmc_api -> europe_pmc_1 [label="  queries\n  (per drug)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    ctgov -> matcher
    europe_pmc_1 -> matcher
    matcher -> source_repo
    drug_sources_existing -> source_repo [label="  reads\n  (dedup)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    source_repo -> drug_sources_write [label="  writes", style="bold", color="#2f9e63", fontcolor="#2f9e63"]

    source_repo -> patient_evidence [label="  Phase 2\n(after every area finishes)"]
    patient_evidence -> config
    config -> patient_repo_read
    patient_unsourced -> patient_repo_read [label="  reads", style="bold", color="#c9890a", fontcolor="#c9890a"]
    patient_repo_read -> europe_pmc_2
    epmc_api -> europe_pmc_2 [label="  queries\n  (per indication)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    europe_pmc_2 -> disease_matcher
    disease_matcher -> patient_repo_write
    patient_repo_write -> patient_write [label="  writes", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        drug_targets [label="Supabase\ndrug_targets", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        drugs_in [label="Supabase\ndrugs", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        trials_in [label="Supabase\ntrials", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        drug_sources_read [label="Supabase\ndrug_sources\n(existing URLs — dedup read)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        patient_read [label="Supabase\nindication_patient_intelligence\n(rows missing sources)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        ctgov_in [label="ClinicalTrials.gov API", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        epmc_in [label="Europe PMC API", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Meridian\nEvidence Collectors",
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

        drug_sources_write [label="Supabase\ndrug_sources\n(insert new rows)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        patient_write [label="Supabase\nindication_patient_intelligence\n(patch source_urls)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    drug_targets -> pipeline
    drugs_in -> pipeline
    trials_in -> pipeline
    drug_sources_read -> pipeline
    patient_read -> pipeline
    ctgov_in -> pipeline
    epmc_in -> pipeline

    pipeline -> drug_sources_write
    pipeline -> patient_write
}
""",
    "io": {
        "reads": [
            {
                "name": "drug_targets",
                "kind": "Supabase table",
                "via": "repositories/drug_repository.py",
                "desc": "Maps a tracked area (e.g. \"tl1a\") to the list of drug_ids that belong to it — this is what turns --areas into a concrete worklist of drugs.",
                "scope": (
                    "One query per area: `get_drug_ids_for_area()` runs `drug_targets WHERE "
                    "target_id = eq.<area>`, returning a deduped, sorted set of drug_ids. By "
                    "default the entrypoint loops the 7 areas in `DEFAULT_AREAS` (tl1a, "
                    "il23p19, tslp, il4ra, fcrn, igf1r, a4b7), so this fires up to 7 times per "
                    "run; `--limit N` truncates each area's drug list to the first N ids."
                ),
            },
            {
                "name": "drugs",
                "kind": "Supabase table",
                "via": "repositories/drug_repository.py",
                "desc": "Pulls id, name, and display_name for each drug in the worklist.",
                "scope": (
                    "One row-lookup per drug (`get_drug(drug_id)` → `drugs WHERE id = eq.<id>`, "
                    "select id/name/display_name). Called once at the top of "
                    "`collect_for_drug()` for every drug_id surfaced by the area query above — "
                    "so the count scales 1:1 with the worklist, not with anything global."
                ),
            },
            {
                "name": "trials",
                "kind": "Supabase table",
                "via": "repositories/drug_repository.py",
                "desc": "Pulls id, phase, and indication for each drug's registered trials — these NCT-bearing rows seed the CT.gov lookups in Phase 1.",
                "scope": (
                    "One query per drug (`get_trials_for_drug()` → `trials WHERE drug_id = "
                    "eq.<id>`), returning every trial row for that drug — no limit applied. "
                    "Each returned trial is then individually format-checked and verified "
                    "against CT.gov in `_build_ctgov_rows()`."
                ),
            },
            {
                "name": "drug_sources",
                "kind": "Supabase table (read side)",
                "via": "repositories/drug_source_repository.py",
                "desc": "Reads each drug's already-stored source_urls before fetching anything new — this idempotency check is what stops the backfill from inserting the same source twice on a rerun.",
                "scope": (
                    "One query per drug (`get_existing_source_urls()` → `drug_sources WHERE "
                    "drug_id = eq.<id>`, select source_url only), collapsed into a Python "
                    "`set`. Every CT.gov URL and every publication DOI URL is checked against "
                    "this set — and added to it in-memory as it's confirmed — before being "
                    "queued for insert, so a single run never proposes the same URL twice."
                ),
            },
            {
                "name": "indication_patient_intelligence",
                "kind": "Supabase table (read side)",
                "via": "repositories/patient_intel_repository.py",
                "desc": "Pulls every indication row's id, indication_name, and source_urls so Phase 2 can isolate the rows that still lack a real source (skipping ones already sourced or not in DISEASE_MAP).",
                "scope": (
                    "One unfiltered, unlimited query for the whole table "
                    "(`get_all_rows()` → select id, indication_name, source_urls). Filtering "
                    "happens entirely in Python afterward: `_has_real_url()` skips rows that "
                    "already carry an `http...` URL, and rows whose `indication_name` isn't "
                    "one of the 8 keys in `DISEASE_MAP` are skipped as \"aggregate\" "
                    "indications that can't be sourced with a single disease paper."
                ),
            },
            {
                "name": "ClinicalTrials.gov",
                "kind": "External API",
                "via": "sources/ctgov.py",
                "desc": "Validates each NCT ID's format and confirms it actually exists on CT.gov (one round-trip per trial) before the trial is trusted as evidence.",
                "scope": (
                    "Per-trial, not batched: for every trial returned above, `is_valid_nct()` "
                    "regex-checks the `NCT\\d{8}` shape (free, no network call), then — only "
                    "if the URL isn't already in `existing` — `verify_nct()` makes one live "
                    "GET to `/api/v2/studies/<nct>` and confirms the returned `nctId` matches. "
                    "So the number of CT.gov round-trips equals the number of new, "
                    "well-formed, not-yet-stored trial registrations — not the total trial count."
                ),
            },
            {
                "name": "Europe PMC",
                "kind": "External API",
                "via": "sources/europe_pmc.py",
                "desc": "Queried by drug name in Phase 1 (publication evidence) and by disease phrase from DISEASE_MAP in Phase 2 (epidemiology evidence).",
                "scope": (
                    "Two distinct usage patterns. **Phase 1** (`search_by_drug`, page_size=6): "
                    "for each drug, up to 2 search terms (`display_name` and/or `name`, "
                    "deduped) are tried in turn, stopping early once `max_pubs` (default 3) "
                    "publication rows have been accepted — so it's a capped, early-exit loop, "
                    "not an exhaustive sweep. **Phase 2** (`search_by_disease`, page_size=12): "
                    "one query per qualifying indication row, phrased as \"`<disease phrase>` "
                    "AND (epidemiology OR prevalence OR incidence OR burden)\" — the API-side "
                    "filter that narrows results to epidemiology-flavored papers before they "
                    "even reach the matcher."
                ),
            },
        ],
        "cleaning": (
            "**Confirm-before-write, not fetch-then-filter-loosely.** Phase 1 treats every "
            "candidate source as guilty until proven innocent: CT.gov links must pass regex "
            "validation *and* a live existence check (`verify_nct`), and publications must "
            "pass `drug_publication_matcher.is_relevant()` — a normalized substring check that "
            "the drug's name actually appears in the title+abstract (not just references) — "
            "before being queued. Anything already present in the drug's `existing` URL set is "
            "skipped outright. Phase 2 layers on `disease_publication_matcher.filter_and_rank()`: "
            "a publication only survives if it has a real DOI *and* the disease's relevance "
            "token (e.g. \"crohn\", \"myasthenia\") appears in its normalized title+abstract; "
            "survivors are then scored so titles containing epidemiology/prevalence/incidence/"
            "burden terms (`EPMC_PREF_TERMS`) rank first, deduped by URL, and hard-capped to the "
            "**top 2** (`max_results=2`) before being patched onto the row. Net effect: both "
            "phases would rather under-report than attach a shaky or duplicate source."
        ),
        "writes": [
            {
                "name": "drug_sources",
                "kind": "Supabase table",
                "via": "repositories/drug_source_repository.py",
                "desc": "Plain INSERT — no upsert/merge, so it relies entirely on the existing-URL read above to avoid duplicates. Each row carries drug_id, drug_name, claim_type (trial_registration / publication), claim_value, source_url, source_type (ct_gov / publication), source_domain, confidence, added_by, and session_label.",
                "scope": (
                    "Two inserts per drug, each capped: `_build_ctgov_rows()` contributes at "
                    "most one row per *new, verified* trial (no hard cap beyond the trial "
                    "count itself), and `_build_pub_rows()` is hard-capped at `max_pubs` "
                    "(default 3, set via `--max-pubs`) publication rows. So a single drug adds "
                    "at most `len(new trials) + 3` rows in a normal run, ×N drugs ×7 areas."
                ),
            },
            {
                "name": "indication_patient_intelligence",
                "kind": "Supabase table",
                "via": "repositories/patient_intel_repository.py",
                "desc": "PATCHes the source_urls array on matched rows in place (sb_patch) — no new rows are created, existing indication rows simply gain sources.",
                "scope": (
                    "At most one patch per qualifying indication row (8 possible — the size "
                    "of `DISEASE_MAP` — minus whatever already has a real source), each "
                    "carrying at most 2 URLs (the `filter_and_rank` cap above). Rows with no "
                    "matching publications are left untouched and simply logged as `no_hits`."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Entrypoint",
            "note": "Called directly by the GitHub Actions workflow — owns argument parsing (--areas, --dry-run, --limit, --max-pubs), phase ordering, and the run summary.",
            "groups": [
                [
                    {
                        "file": "scripts/evidence/backfill_sources.py",
                        "lines": 128,
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
                        "lines": 181,
                        "desc": "Orchestrates evidence collection for one drug or one area: pulls CT.gov trial registrations and Europe PMC publications, filters them for relevance, and hands the surviving rows to the source repository.",
                    }
                ],
                [
                    {
                        "file": "scripts/evidence/repositories/drug_repository.py",
                        "lines": 23,
                        "desc": "Read-only Supabase access — looks up which drug IDs belong to an area (via drug_targets) and fetches each drug's trial records.",
                    }
                ],
                [
                    {
                        "file": "scripts/evidence/sources/ctgov.py",
                        "lines": 44,
                        "desc": "Validates NCT ID format and builds the canonical ClinicalTrials.gov study URL — runs alongside europe_pmc.py for each drug.",
                        "parallel_with": "scripts/evidence/sources/europe_pmc.py",
                    },
                    {
                        "file": "scripts/evidence/sources/europe_pmc.py",
                        "lines": 41,
                        "desc": "Searches Europe PMC for publications by drug name (or by disease phrase in Phase 2) and returns raw result dicts for the caller to filter — runs alongside ctgov.py for each drug.",
                        "parallel_with": "scripts/evidence/sources/ctgov.py",
                    },
                ],
                [
                    {
                        "file": "scripts/evidence/matching/drug_publication_matcher.py",
                        "lines": 28,
                        "desc": "Relevance guard that checks the drug's name actually appears in a publication's title or abstract, preventing false positives where the name only shows up in references.",
                    }
                ],
                [
                    {
                        "file": "scripts/evidence/repositories/drug_source_repository.py",
                        "lines": 25,
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
                        "lines": 104,
                        "desc": "Walks indication_patient_intelligence rows with no real source URL, searches Europe PMC for matching epidemiology papers (skipping rows already sourced or not in DISEASE_MAP), and patches source_urls on the matches.",
                    }
                ],
                [
                    {
                        "file": "scripts/evidence/config.py",
                        "lines": 22,
                        "desc": "Static configuration: DEFAULT_AREAS (the core immunology set Phase 1 sweeps) and DISEASE_MAP (indication name → Europe PMC search phrase + relevance token).",
                    }
                ],
                [
                    {
                        "file": "scripts/evidence/repositories/patient_intel_repository.py",
                        "lines": 24,
                        "desc": "Reads indication_patient_intelligence rows lacking a source, then later patches the matched source_urls back onto each row — used at both the start and end of Phase 2.",
                    }
                ],
                [
                    {
                        "file": "scripts/evidence/sources/europe_pmc.py",
                        "lines": 41,
                        "desc": "Same Europe PMC client as Phase 1, here queried with each indication's disease phrase from DISEASE_MAP.",
                    }
                ],
                [
                    {
                        "file": "scripts/evidence/matching/disease_publication_matcher.py",
                        "lines": 55,
                        "desc": "Filters and ranks epidemiology publications — requires a real DOI and a relevance-token match, then scores survivors so epidemiology/burden/prevalence titles rank above generic ones.",
                    }
                ],
            ],
        },
    ],
}
