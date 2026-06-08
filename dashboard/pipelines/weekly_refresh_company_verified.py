"""
Static description of the Meridian Company Freshness Refresh pipeline
(.github/workflows/weekly-refresh-company-verified.yml).

Documents what refresh_company_verified.py does — applying three verification
tiers to set last_verified on stale/null company records without touching any
curated fields, then running company_validator.py for a health score summary.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "company_freshness_refresh",
    "workflow_name": "Company Freshness Refresh",
    "workflow_file": ".github/workflows/weekly-refresh-company-verified.yml",
    "schedule": "Sundays 06:00 UTC (2 AM ET) — off-peak, before the BD scoring window",
    "entrypoint": "scripts/sync/refresh_company_verified.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Weekly freshness maintenance job that sets `last_verified` on company records "
        "that are null or older than 90 days, without touching any curated fields. "
        "Three tiers are applied per company in order: "
        "(1) **Tier 1 — enrichment_pipeline_bootstrap**: if `last_enriched_at` is within "
        "90 days, `last_verified` is set to that date — the enrichment pipeline explicitly "
        "reviewed the company's data; "
        "(2) **Tier 2 — reference_entity_auto_verify**: if the company has a "
        "`coverage_status` of reference, planned, or orphan (static attribution entities), "
        "`last_verified` is set to today; "
        "(3) **Tier 3 — skip (needs_manual_review)**: active companies with no recent "
        "enrichment are not touched — a `drug_validation_results` flag is written instead. "
        "After the refresh, `company_validator.py --summary --scores` runs as a "
        "`continue-on-error` step to print the company health score distribution. "
        "Protected fields are enforced in `_patch_company()` — the script will never "
        "modify `company_type`, `geography`, `status`, `name`, or any other curated field."
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
        label="refresh_company_verified.py\n(entrypoint — main())",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    companies_in [
        label="Supabase\ncompanies\n(read here — stale/null or all)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_tiers {
        label="Per-company: determine_action() — three tiers in order"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        t0 [label="Is last_verified current?\n(within 90 days)\n→ skip_current"]
        t1 [label="Tier 1: last_enriched_at within 90 days?\n→ UPDATE last_verified = last_enriched_at\nmethod: enrichment_pipeline_bootstrap"]
        t2 [label="Tier 2: coverage_status in\nreference / planned / orphan?\n→ UPDATE last_verified = today\nmethod: reference_entity_auto_verify"]
        t3 [label="Tier 3: active, no recent enrichment\n→ skip_needs_review\n(writes drug_validation_results flag)"]
    }

    companies_out [
        label="Supabase\ncompanies\n(last_verified patched — Tier 1 + 2 only)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    dvr_out [
        label="Supabase\ndrug_validation_results\n(one row per Tier 1/2/3 company\ncheck_type: freshness_refreshed or _needs_review)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    log_file [
        label="logs/company_refresh_<ts>.jsonl\n(one JSON line per actioned company)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    validator [
        label="company_validator.py\n--summary --scores\n(post-refresh health report)",
        fillcolor="#dbe9fb",
        color="#5b8def",
        fontcolor="#111827"
    ]

    stdout [
        label="stdout\nper-company action table\nrefresh summary + validator output",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> companies_in [label="  _get('companies')", style="bold", color="#c9890a", fontcolor="#c9890a"]
    companies_in -> t0
    t0 -> t1 [label="  stale or null"]
    t0 -> stdout [label="  skip_current"]
    t1 -> companies_out [label="  _patch_company(last_verified)\n  (not dry_run)", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    t1 -> dvr_out [label="  freshness_refreshed", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    t1 -> t2 [label="  no recent\n  last_enriched_at"]
    t2 -> companies_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    t2 -> dvr_out [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    t2 -> t3 [label="  not reference entity"]
    t3 -> dvr_out [label="  needs_review flag", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    t1 -> log_file [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    t2 -> log_file [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    t3 -> log_file [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    entry -> validator [label="  (workflow step — after refresh)"]
    validator -> stdout
    t3 -> stdout
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

        sb_in [label="Supabase\ncompanies\n(all or filtered by id)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Company\nFreshness\nRefresh",
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

        companies_out [label="Supabase\ncompanies\n(last_verified + updated_at patched)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        dvr_out [label="Supabase\ndrug_validation_results\n(freshness_refreshed or _needs_review)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        log_out [label="logs/company_refresh_*.jsonl\n(per-company JSONL log)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\naction table + summary", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    pipeline -> companies_out
    pipeline -> dvr_out
    pipeline -> log_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "companies",
                "kind": "Supabase table",
                "via": "_get('companies', {'limit': 1000}) or {'id': 'eq.<company>'}",
                "desc": (
                    "The full company list (up to 1000 rows) for scheduled runs, or a "
                    "single-company fetch when `--company` is specified. Each row provides "
                    "`id`, `name`, `coverage_status`, `last_verified`, and `last_enriched_at` "
                    "— the four fields `determine_action()` inspects. The script does NOT "
                    "filter to stale/null in the query; `determine_action()` applies the "
                    "staleness check in Python so that `--all` (force-process current "
                    "companies) still works."
                ),
                "scope": "One query per run.",
            },
        ],
        "cleaning": (
            "**The protection boundary is enforced at write time, not query time.** "
            "`_patch_company()` strips any key in `PROTECTED_FIELDS` before issuing the "
            "PATCH, so a logic error upstream that accidentally includes `name` or "
            "`status` in the payload is silently discarded. The script only ever writes "
            "`last_verified` and `updated_at` — both are explicitly included in every "
            "PATCH call and both are non-protected. The `determine_action()` decision "
            "tree is deterministic and stateless: same company fields → same action, "
            "every time, so re-runs are idempotent (already-fresh companies are "
            "skip_current; already-flagged Tier 3 companies get a new "
            "`drug_validation_results` upsert but no company row change). "
            "`--dry-run` suppresses all DB writes and JSONL logging."
        ),
        "writes": [
            {
                "name": "companies (last_verified)",
                "kind": "Supabase table",
                "via": "_patch_company(cid, {'last_verified': ..., 'updated_at': ...})",
                "desc": (
                    "Patches exactly two fields — `last_verified` and `updated_at` — on "
                    "each Tier 1 or Tier 2 company. `_patch_company()` enforces the "
                    "protected-field list as a final guard. Tier 3 companies are never "
                    "patched."
                ),
                "scope": (
                    "At most one PATCH per company per run. Typically a small subset of "
                    "the full company list — only null or stale records are targeted "
                    "unless `--all` is passed."
                ),
            },
            {
                "name": "drug_validation_results",
                "kind": "Supabase table",
                "via": "_write_validation() → _db.sb_upsert('drug_validation_results', row)",
                "desc": (
                    "One row per actioned company (Tier 1, 2, and 3). Tier 1/2 rows "
                    "have `check_type='company_freshness_refreshed'` and "
                    "`check_status='pass'`. Tier 3 rows have "
                    "`check_type='company_freshness_needs_review'` and "
                    "`check_status='needs_review'`. The `drug_id` column is reused "
                    "to store `company_id` (the table predates the company coverage work). "
                    "The `details` column carries the full decision context as JSON."
                ),
                "scope": (
                    "One upsert per actioned company. The upsert key is not explicitly "
                    "specified — each run may create new rows for the same company if "
                    "the check_type changes between runs."
                ),
            },
            {
                "name": "logs/company_refresh_<ts>.jsonl",
                "kind": "Local file",
                "via": "json.dumps(log_entry) appended line-by-line",
                "desc": (
                    "One JSON object per line for every company that was actioned or "
                    "flagged (skip_current is only logged when `--all` is active). "
                    "Each entry records: `company_id`, `company_name`, `coverage_status`, "
                    "`previous_last_verified`, `last_enriched_at`, `action`, "
                    "`new_last_verified`, `method`, `source`, `reason`, `timestamp`, "
                    "`dry_run`. The timestamp is embedded in the filename."
                ),
                "scope": "One file per run, written to `scripts/logs/`.",
            },
        ],
    },
    "phases": [
        {
            "label": "Helpers",
            "note": "Five utility functions used throughout the script.",
            "groups": [
                [
                    {
                        "function": "_get(path, params)",
                        "lines": 2,
                        "desc": "Thin wrapper over `_db.sb_get()` with an empty-dict default.",
                    },
                    {
                        "function": "_patch_company(company_id, payload)",
                        "lines": 5,
                        "desc": (
                            "Strips any key in `PROTECTED_FIELDS` from the payload before "
                            "issuing `_db.sb_patch()`. Returns False if nothing safe remains. "
                            "The protected-field guard is the last line of defense."
                        ),
                    },
                    {
                        "function": "_write_validation(company_id, check_type, severity, details)",
                        "lines": 10,
                        "desc": (
                            "Assembles and upserts a `drug_validation_results` row with the "
                            "check type, status, severity, and JSON details. Called for every "
                            "Tier 1, 2, and 3 action."
                        ),
                    },
                    {
                        "function": "_parse_date(s)",
                        "lines": 10,
                        "desc": (
                            "Parses an ISO 8601 string (with or without timezone) to a "
                            "`date` object, returning `None` on failure. Used to normalize "
                            "`last_verified` and `last_enriched_at` before comparison."
                        ),
                    },
                    {
                        "function": "_days_ago(d)",
                        "lines": 4,
                        "desc": "Returns `(today - d).days` or `None` if `d` is None.",
                    },
                    {
                        "function": "_ensure_log_dir()",
                        "lines": 4,
                        "desc": "Creates `scripts/logs/` if it doesn't exist; returns the Path.",
                    },
                ],
            ],
        },
        {
            "label": "Tier decision engine",
            "note": "determine_action() is the core logic — stateless, deterministic, called once per company.",
            "groups": [
                [
                    {
                        "function": "determine_action(company)",
                        "lines": 58,
                        "desc": (
                            "Evaluates one company dict through the three-tier decision tree. "
                            "First checks if `last_verified` is current (within 90 days) → "
                            "`skip_current`. Then Tier 1: if `last_enriched_at` is within "
                            "90 days → `update` with `method='enrichment_pipeline_bootstrap'`. "
                            "Then Tier 2: if `coverage_status` in {reference, planned, orphan} "
                            "→ `update` with `method='reference_entity_auto_verify'` and "
                            "`new_last_verified=TODAY`. Finally Tier 3: "
                            "→ `skip_needs_review` with the human-readable skip_reason. "
                            "Returns a dict with `action`, `new_last_verified`, `method`, "
                            "`source`, `reason`, and `skip_reason`."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main loop",
            "note": "main() orchestrates the load, per-company decision loop, DB writes, logging, and summary.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 114,
                        "desc": (
                            "Parses `--dry-run`, `--company`, `--all`. Loads companies "
                            "(full table or single-ID). Opens the JSONL log file path. "
                            "Iterates companies sorted by name: calls `determine_action()`, "
                            "prints the per-company action line. For `update` actions: "
                            "calls `_patch_company()` and `_write_validation("
                            "'company_freshness_refreshed')`. For `skip_needs_review`: "
                            "calls `_write_validation('company_freshness_needs_review')`. "
                            "Appends the log entry for every non-skip_current company. "
                            "Prints the refresh summary table (updated / skipped-current / "
                            "needs-review / errors counts) and lists companies needing "
                            "manual review."
                        ),
                    }
                ],
            ],
        },
    ],
}
