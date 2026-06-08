"""
Static description of the Meridian Weekly Trial-ID Audit pipeline
(.github/workflows/weekly-trial-audit.yml).

Documents what the single entrypoint script does — collecting every NCT
reference from the catalog, verifying each against the ClinicalTrials.gov
v2 API, and logging fabricated or misattributed trials to governance_violations
for human review. Never auto-edits drug data.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "trial_audit",
    "workflow_name": "Meridian Weekly Trial-ID Audit",
    "workflow_file": ".github/workflows/weekly-trial-audit.yml",
    "schedule": "Mondays 11:00 UTC (7 AM ET) — runs the morning after the weekend sprint settles",
    "entrypoint": "scripts/identity/trial_id_audit.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Weekly integrity sweep that verifies every ClinicalTrials.gov NCT "
        "referenced anywhere in the catalog against the CT.gov v2 JSON API. "
        "Fabricated NCTs (404 / empty record) and misattributed NCTs (the real "
        "trial belongs to a different asset) are logged to `governance_violations` "
        "as unresolved findings for human review. **Nothing is auto-edited** — "
        "trial reassignment is a judgment call that stays with the analyst. "
        "Born from the NCT07423299 incident (a real trial wrongly scrubbed from "
        "the catalog): this workflow is the immune system that catches that class "
        "of error before it propagates."
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
        label="trial_id_audit.py\n(entrypoint — args, collect, verify, log)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    supabase_in [
        label="Supabase\ncatalysts · drug_clinical_benchmarks\ndrug_bispecific_landscape · platform_trials\ndrugs · drug_aliases · drug_targets\n(read here — NCT refs + identifiers)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    ctgov_api [
        label="ClinicalTrials.gov\nv2 JSON API\n(read here — per NCT)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.2,0.12"
    ]

    subgraph cluster_collect {
        label="Phase 1 — collect_refs(): build (drug, NCT) worklist"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        subgraph cluster_sql {
            label="fast path (SUPABASE_PAT present)"
            style="dotted"
            color="#9aa7b5"
            pencolor="#9aa7b5"
            fontname="Helvetica"
            fontsize=10
            fontcolor="#e8ecf2"

            refs_sql [label="_refs_sql() + _run_sql()\nManagement API CTE\n(single round-trip)"]
        }

        subgraph cluster_rest {
            label="fallback path (no PAT)"
            style="dotted"
            color="#9aa7b5"
            pencolor="#9aa7b5"
            fontname="Helvetica"
            fontsize=10
            fontcolor="#e8ecf2"

            postgrest [label="5 × PostgREST GET\n(one per source table)"]
        }
    }

    subgraph cluster_verify {
        label="Phase 2 — per (drug, NCT): verify + classify"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        ctgov_record [label="ctgov_record(nct)\nfetch title + interventions"]
        drug_ids [label="drug_identifiers(drug_id)\nbuild token set"]
        classify [label="classify(drug_id, nct)\nMATCH / MISMATCH / NONEXISTENT"]
    }

    gov_violations [
        label="Supabase\ngovernance_violations\n(upsert NONEXISTENT + MISMATCH only)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    stdout [
        label="stdout summary\n(counts + first 80 chars of each finding)",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> supabase_in [label="  reads refs + identifiers", style="bold", color="#c9890a", fontcolor="#c9890a"]
    supabase_in -> refs_sql
    supabase_in -> postgrest
    refs_sql -> ctgov_record [label="  Phase 2\n  (per ref)"]
    postgrest -> ctgov_record [label="  Phase 2\n  (per ref)"]
    ctgov_api -> ctgov_record [label="  GET /studies/<nct>", style="bold", color="#c9890a", fontcolor="#c9890a"]
    ctgov_record -> classify
    supabase_in -> drug_ids [label="  reads drugs +\n  drug_aliases", style="bold", color="#c9890a", fontcolor="#c9890a"]
    drug_ids -> classify
    classify -> gov_violations [label="  upsert (--apply only)", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    classify -> stdout [label="  always", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        supabase_in [label="Supabase\ncatalysts · drug_clinical_benchmarks\ndrug_bispecific_landscape · platform_trials\ndrugs · drug_aliases · drug_targets", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        ctgov_in [label="ClinicalTrials.gov\nv2 JSON API\n(per NCT, rate-limited)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Meridian\nTrial-ID Audit",
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

        gov_out [label="Supabase\ngovernance_violations\n(NONEXISTENT + MISMATCH, --apply only)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nrun summary + findings", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    supabase_in -> pipeline
    ctgov_in -> pipeline
    pipeline -> gov_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "catalysts · drug_clinical_benchmarks · drug_bispecific_landscape · platform_trials · drugs",
                "kind": "Supabase tables",
                "via": "collect_refs() → _sb('GET', ...) or _run_sql() Management API CTE",
                "desc": (
                    "Five tables are scanned to build the (drug_id, NCT) worklist — "
                    "every place in the catalog where an NCT identifier can be stored: "
                    "`catalysts.related_trial_id`, `drug_clinical_benchmarks.nct_id`, "
                    "`drug_bispecific_landscape.nct_id`, `platform_trials.nct_id`, and "
                    "`drugs.source_url` (regex-extracted). Each is filtered to rows that "
                    "match `ilike.*NCT*` (PostgREST path) or `~* 'NCT[0-9]{8}'` (SQL "
                    "path), so only rows that actually carry an NCT are touched."
                ),
                "scope": (
                    "Two paths, same result. If `SUPABASE_PAT` is available, "
                    "`_refs_sql()` builds a single UNION CTE and `_run_sql()` posts "
                    "it to the Supabase Management API in one round-trip — the preferred "
                    "path for CI. If the PAT is absent (or the Management API call "
                    "fails), `collect_refs()` falls back to five separate PostgREST GETs "
                    "with `ilike.*NCT*` filters, unions the results in Python, and "
                    "deduplicates with a `set`. An optional `--area` filter then reduces "
                    "the worklist to drugs linked to one `drug_targets.target_id` via a "
                    "sixth GET."
                ),
            },
            {
                "name": "drugs · drug_aliases",
                "kind": "Supabase tables",
                "via": "drug_identifiers(drug_id) → _sb('GET', ...)",
                "desc": (
                    "For each drug in the worklist, `drug_identifiers()` fetches its "
                    "`name`, `display_name`, `brand_name`, `aliases`, and "
                    "`canonical_drug_id` from `drugs`, then fetches any additional "
                    "`alias_name` values from `drug_aliases` (keyed by "
                    "`canonical_drug_id`, not `drug_id`). The result is the token set "
                    "used by `classify()` to decide whether a CT.gov trial title or "
                    "intervention list contains a recognizable reference to this drug."
                ),
                "scope": (
                    "Two queries per unique drug in the worklist: one "
                    "`GET drugs?id=eq.<drug_id>&select=...` and one "
                    "`GET drug_aliases?canonical_id=eq.<cid>&select=alias_name`. "
                    "Results are lowercased and length-filtered (≥3 chars) before "
                    "matching — short tokens would generate false positives across "
                    "unrelated trials."
                ),
            },
            {
                "name": "ClinicalTrials.gov v2 API",
                "kind": "External API",
                "via": "ctgov_record(nct) → urllib.request (raw — CT.gov is not Supabase REST)",
                "desc": (
                    "For each (drug, NCT) pair, `ctgov_record()` calls "
                    "`GET /api/v2/studies/<nct>` requesting only "
                    "`protocolSection.identificationModule` (for `briefTitle`) and "
                    "`protocolSection.armsInterventionsModule` (for intervention names). "
                    "A 404 means the NCT doesn't exist (NONEXISTENT); a 200 with a "
                    "title that contains none of the drug's tokens is MISMATCH; a 200 "
                    "with a matching token is MATCH."
                ),
                "scope": (
                    "One GET per (drug, NCT) pair, rate-limited by `--sleep 0.2` "
                    "(0.2 s between calls in CI — the workflow passes this flag "
                    "explicitly). The field projection keeps the response payload "
                    "small — only two protocol-section modules are requested, not the "
                    "full study record. `urllib.request` is used raw here (not `_db`) "
                    "because CT.gov is an external API, not Supabase REST — same "
                    "precedent as `ct_gov_sync.py`."
                ),
            },
        ],
        "cleaning": (
            "**The worklist is deduplicated before any API calls, and the "
            "governance write is idempotent.** `collect_refs()` builds a Python "
            "`set` of `(drug_id, nct)` tuples — so the same NCT appearing in two "
            "source tables (e.g. both `catalysts` and `drug_clinical_benchmarks`) "
            "is only verified once. NCTs are uppercased at collection time so "
            "`NCT07219368` and `nct07219368` are treated as the same reference. "
            "The `governance_violations` upsert uses "
            "`on_conflict=table_name,row_id,rule_name`, so re-running on an already-"
            "flagged NCT is a no-op — the existing unresolved row stays in place "
            "rather than creating a duplicate. **MATCH results are never written** — "
            "only NONEXISTENT and MISMATCH produce rows. The `--dry-run` flag "
            "suppresses all writes entirely, so you can audit the CT.gov responses "
            "without touching the governance queue."
        ),
        "writes": [
            {
                "name": "governance_violations",
                "kind": "Supabase table",
                "via": "_sb('POST', 'governance_violations?on_conflict=table_name,row_id,rule_name', [...])",
                "desc": (
                    "One upserted row per NONEXISTENT or MISMATCH finding, with "
                    "`resolved=False` so it lands in the review queue. "
                    "`rule_name` is `trial_fabricated_<NCT>` or "
                    "`trial_misattributed_<NCT>`, `description` carries the human-"
                    "readable detail (e.g. \"NCT07423299 not found on "
                    "ClinicalTrials.gov\"), and `resolution_notes` stamps the actor "
                    "(`trial_id_audit.py@v0`) and session date with an explicit "
                    "\"Review/reassign — NOT auto-edited\" note. The drug row itself "
                    "is never touched."
                ),
                "scope": (
                    "Bounded by the number of non-MATCH findings per run — typically "
                    "a handful, since MATCH is the common case for legitimate catalog "
                    "entries. The upsert on the composite key means each unique "
                    "(drugs, drug_id, rule_name) triple can have at most one open "
                    "violation row regardless of how many times the audit reruns."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Credential & Supabase helpers",
            "note": "Two thin wrappers used throughout the script to read credentials and issue Supabase calls.",
            "groups": [
                [
                    {
                        "function": "_secret(env_name, filename)",
                        "lines": 16,
                        "desc": (
                            "Reads a credential from an environment variable first "
                            "(CI path), falling back to a workspace-root dot-file "
                            "(local path). Used for `SUPABASE_PAT` — the optional "
                            "Management API token that enables the faster CTE path "
                            "in `collect_refs()`."
                        ),
                    }
                ],
                [
                    {
                        "function": "_sb(method, ep, data=None, prefer=None)",
                        "lines": 15,
                        "desc": (
                            "Adapter that translates this script's older "
                            "`(method, 'table?query')` call convention to the shared "
                            "`_db.sb_get()` / `_db.sb_upsert()` interface. Parses the "
                            "`?key=value` query string into a params dict, dispatches "
                            "GET to `_db.sb_get` and POST to `_db.sb_upsert`. The "
                            "`prefer` argument is accepted for call-site compatibility "
                            "but unused — `_db` sets its own Prefer headers."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "ClinicalTrials.gov verification",
            "note": "Fetches one CT.gov API record per NCT and returns the fields needed by classify().",
            "groups": [
                [
                    {
                        "function": "ctgov_record(nct)",
                        "lines": 19,
                        "desc": (
                            "GETs `https://clinicaltrials.gov/api/v2/studies/<nct>` "
                            "requesting only the two protocol-section modules needed "
                            "for classification: `identificationModule` (briefTitle) "
                            "and `armsInterventionsModule` (intervention names). "
                            "A 404 returns `(False, None, [])` — the NONEXISTENT "
                            "signal. A successful response returns "
                            "`(True, title, interventions_list)`. Uses raw "
                            "`urllib.request` with a 20-second timeout and a browser "
                            "User-Agent header."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Drug identifier resolution",
            "note": "Builds the token set used to decide whether a CT.gov trial title belongs to a given drug.",
            "groups": [
                [
                    {
                        "function": "drug_identifiers(drug_id)",
                        "lines": 22,
                        "desc": (
                            "Fetches `name`, `display_name`, `brand_name`, `aliases`, "
                            "and `canonical_drug_id` from `drugs`, then fetches "
                            "`alias_name` values from `drug_aliases` joined on "
                            "`canonical_id` (not `drug_id` — the earlier bug that "
                            "caused false-positive MISMATCHes). Returns a set of "
                            "lowercased tokens, each ≥ 3 characters, including "
                            "the raw drug_id with and without hyphens. Used by "
                            "`classify()` to do a simple substring match against "
                            "the CT.gov title + intervention haystack."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Reference collection",
            "note": "collect_refs() drives two code paths — a fast Management API CTE and a PostgREST fallback — to produce the same (drug_id, NCT) worklist either way.",
            "groups": [
                [
                    {
                        "function": "collect_refs(area=None)",
                        "lines": 34,
                        "desc": (
                            "Entry point for Phase 1. Tries the fast path first: if "
                            "`SUPABASE_PAT` is present, delegates to `_refs_sql()` + "
                            "`_run_sql()` for a single-round-trip CTE. If the PAT is "
                            "absent or the Management API call raises, falls back to "
                            "five separate PostgREST GETs (one per source table), "
                            "extracts NCTs via `NCT8` regex, unions into a Python set, "
                            "and returns a deduplicated, sorted list of "
                            "`{drug_id, nct}` dicts. Applies the `--area` filter as a "
                            "sixth GET against `drug_targets` if specified."
                        ),
                    }
                ],
                [
                    {
                        "function": "_refs_sql(area)",
                        "lines": 13,
                        "desc": (
                            "Builds the UNION CTE that collects NCTs from all five "
                            "source tables in one SQL round-trip: `catalysts`, "
                            "`drug_clinical_benchmarks`, `drug_bispecific_landscape`, "
                            "`platform_trials`, and `drugs.source_url` (via "
                            "`regexp_matches`). Optionally joins `drug_targets` to "
                            "filter by area. Returns the SQL string; `_run_sql()` "
                            "executes it."
                        ),
                    },
                    {
                        "function": "_run_sql(sql, pat)",
                        "lines": 10,
                        "desc": (
                            "Posts a raw SQL query to the Supabase Management API "
                            "(`/v1/projects/<project_id>/database/query`) using the "
                            "PAT for authorization. Returns the parsed JSON rows. "
                            "Only called if the PAT is available — the workflow sets "
                            "it via `SUPABASE_PAT` secret."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Classification",
            "note": "Combines ctgov_record() and drug_identifiers() to render the per-NCT verdict.",
            "groups": [
                [
                    {
                        "function": "classify(drug_id, nct)",
                        "lines": 12,
                        "desc": (
                            "Calls `ctgov_record()` and `drug_identifiers()`, then "
                            "applies a two-step decision: if the NCT returned 404 / "
                            "empty → NONEXISTENT; else concat `title + interventions` "
                            "into a haystack and check whether any drug identifier "
                            "token (≥3 chars) appears as a substring — hit → MATCH, "
                            "miss → MISMATCH. Returns a `(verdict, detail, title)` "
                            "tuple consumed by `main()`."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main loop",
            "note": "Parses args, drives the collect → verify → log pipeline, and prints the run summary.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 39,
                        "desc": (
                            "Parses `--area` / `--all`, `--apply` / `--dry-run`, and "
                            "`--sleep`. Calls `collect_refs()` to build the worklist, "
                            "then iterates every `(drug_id, nct)` pair: calls "
                            "`classify()`, increments the MATCH / MISMATCH / "
                            "NONEXISTENT counter, prints the detail for non-MATCHes, "
                            "and (if `--apply`) upserts a `governance_violations` row "
                            "via `_sb()`. Sleeps `--sleep` seconds between CT.gov "
                            "calls. Prints the final MATCH | misattributed | fabricated "
                            "summary, and notes if `--dry-run` suppressed writes."
                        ),
                    }
                ],
            ],
        },
    ],
}
