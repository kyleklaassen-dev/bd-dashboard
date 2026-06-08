"""
Static description of the Meridian Validation Research Pass pipeline
(.github/workflows/weekly-validation-research.yml).

Documents the four-step validation workflow: validation_research.py (registry
search for stage_trial_match warnings), conflict_detector.py (cross-table
contradiction detection), inline NCT discovery check, and inline warning summary.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "validation_research",
    "workflow_name": "Validation Research Pass",
    "workflow_file": ".github/workflows/weekly-validation-research.yml",
    "schedule": "Sundays 07:00 UTC (3 AM ET) — after the nightly sync has run",
    "entrypoint": "scripts/validation/validation_research.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Weekly four-step data quality sweep that investigates and escalates all "
        "unresolved validation warnings in the catalog. "
        "**Step 1 — `validation_research.py`**: fetches every drug with an unresolved "
        "`stage_trial_match` warning, searches CT.gov (v2 API) and ANZCTR by drug name "
        "and aliases, and either flips the warning to `pass` (trials found) or confirms "
        "the gap (searched, nothing found). Writes search results to `trial_registries` "
        "and updates `drug_validation_results` and `drugs.validation_summary`. "
        "Structural warnings (`field_consistency`, `brand_name`) that require human "
        "judgment are escalated from `warning` to `needs_review`. "
        "**Step 2 — `conflict_detector.py`**: runs after the registry research so newly "
        "resolved drugs are reflected; detects cross-table contradictions between "
        "`drugs` and `drug_targets` (target_consistency), `drug_indications` "
        "(indication_consistency), and `companies` / `company_aliases` "
        "(company_resolution). Writes `needs_review` rows to `drug_validation_results`. "
        "**Step 3 — inline NCT discovery check**: queries `trial_registries` for "
        "rows updated today with `search_status=found` — these are newly discovered "
        "NCT IDs that need to be added to `NCT_SEED_MAP` in `ct_gov_sync.py`. "
        "**Step 4 — inline warning summary**: prints all remaining unresolved "
        "warning/fail/needs_review rows from `drug_validation_results` for the run log."
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

    step1 [
        label="Step 1: validation_research.py\n(registry search for stage_trial_match warnings)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    step2 [
        label="Step 2: conflict_detector.py\n(cross-table contradiction detection)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    step3 [
        label="Step 3: inline NCT discovery check\n(newly found trial_registries rows)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    step4 [
        label="Step 4: inline warning summary\n(remaining unresolved issues)",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    supabase_in [
        label="Supabase\ndrug_validation_results · drugs\ndrug_aliases · drug_targets\ndrug_indications · indications\ncompanies · company_aliases\ntrial_registries\n(read by both scripts)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    ctgov_api [
        label="ClinicalTrials.gov v2 API\n(GET /studies per drug name+aliases)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    anzctr_api [
        label="ANZCTR\n(HTML search per drug name)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    trial_reg_out [
        label="Supabase\ntrial_registries\n(search_status + trial_count\n+ last_searched_at + verified_by)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    dvr_out [
        label="Supabase\ndrug_validation_results\n(stage_trial_match: pass or confirmed gap\nfield_consistency/brand_name: needs_review\nconflict checks: needs_review)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    drugs_out [
        label="Supabase\ndrugs.validation_summary\n(refreshed per resolved drug)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    stdout [
        label="stdout\nnewly found NCT IDs (Step 3)\nremaining issues summary (Step 4)",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    supabase_in -> step1 [label="  reads warnings + drug records", style="bold", color="#c9890a", fontcolor="#c9890a"]
    ctgov_api -> step1 [label="  per drug name+alias", style="bold", color="#c9890a", fontcolor="#c9890a"]
    anzctr_api -> step1 [label="  per drug name", style="bold", color="#c9890a", fontcolor="#c9890a"]
    step1 -> trial_reg_out [label="  upsert search results", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    step1 -> dvr_out [label="  flip pass/confirmed/needs_review", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    step1 -> drugs_out [label="  refresh validation_summary", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    step1 -> step2 [label="  (after registry pass)"]
    supabase_in -> step2 [style="bold", color="#c9890a", fontcolor="#c9890a"]
    step2 -> dvr_out [label="  conflict rows needs_review", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    step2 -> step3
    supabase_in -> step3 [style="bold", color="#c9890a", fontcolor="#c9890a"]
    step3 -> stdout [label="  newly found NCTs", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    step3 -> step4
    supabase_in -> step4 [style="bold", color="#c9890a", fontcolor="#c9890a"]
    step4 -> stdout [label="  remaining issues", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        sb_in [label="Supabase\ndrug_validation_results · drugs · drug_aliases\ndrug_targets · drug_indications · indications\ncompanies · company_aliases · trial_registries", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        ctgov_in [label="ClinicalTrials.gov v2 API\n(per drug name+aliases)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        anzctr_in [label="ANZCTR\n(HTML per drug name)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Validation\nResearch\nPass",
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

        tr_out [label="Supabase\ntrial_registries\n(search results per drug)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        dvr_out [label="Supabase\ndrug_validation_results\n(pass / confirmed gap / needs_review)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        drugs_out [label="Supabase\ndrugs.validation_summary\n(refreshed JSONB per drug)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nnewly found NCTs + issue summary", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    ctgov_in -> pipeline
    anzctr_in -> pipeline
    pipeline -> tr_out
    pipeline -> dvr_out
    pipeline -> drugs_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "drug_validation_results",
                "kind": "Supabase table",
                "via": "sb_get('drug_validation_results', {'check_status': 'in.(warning,pending)', 'check_type': 'eq.stage_trial_match'})",
                "desc": (
                    "The worklist for the registry research pass. Fetches all rows with "
                    "`check_status` in `(warning, pending)` and `check_type=stage_trial_match`. "
                    "Also queried to fetch all checks for a drug during `validation_summary` "
                    "refresh, and queried by the inline summary step for remaining unresolved "
                    "issues (warning/fail/needs_review, up to 100 rows)."
                ),
                "scope": "Multiple queries across all four workflow steps.",
            },
            {
                "name": "drugs",
                "kind": "Supabase table",
                "via": "sb_get('drugs', {'id': 'in.(<ids>)', 'select': 'id,name,aliases,indication_short,stage'})",
                "desc": (
                    "Full drug records for each flagged drug_id — `name`, `aliases`, "
                    "`indication_short`, and `stage` — to build the search terms for "
                    "CT.gov and ANZCTR. Also read by `conflict_detector.py` for "
                    "target, indication, and company_display fields."
                ),
                "scope": "One batched IN query per run for the flagged drug set.",
            },
            {
                "name": "drug_targets · drug_indications · indications · companies · company_aliases",
                "kind": "Supabase tables",
                "via": "conflict_detector.py — sb_get() for each source table",
                "desc": (
                    "Read by `conflict_detector.py` to build the comparison sets for "
                    "three conflict checks: `drug_targets` for target_consistency, "
                    "`drug_indications` + `indications` for indication_consistency, "
                    "and `companies` + `company_aliases` for company_resolution."
                ),
                "scope": "Full table reads (up to 2000 rows each) in `conflict_detector.py`.",
            },
            {
                "name": "ClinicalTrials.gov v2 API",
                "kind": "External API",
                "via": "search_ctgov() → requests.get(CT_GOV_BASE + '/studies', params={...})",
                "desc": (
                    "Searched per search term (drug name + each alias) with a 0.5-second "
                    "sleep between terms. Results are hard-gated: a study is only accepted "
                    "if the drug name or alias appears in the trial title or intervention "
                    "list — terms of ≤5 chars after hyphen-splitting are skipped to avoid "
                    "false positives. Returns NCT IDs, titles, phases, statuses, and sponsors."
                ),
                "scope": (
                    "One GET per search term per drug. Rate-limited by 0.5s inter-term "
                    "sleep and 2.0s inter-drug sleep. The 30-minute CI timeout provides "
                    "headroom for large warning lists."
                ),
            },
            {
                "name": "ANZCTR (Australian New Zealand Clinical Trials Registry)",
                "kind": "External API (HTML)",
                "via": "search_anzctr() → requests.get(ANZCTR_BASE, params={'searchTxt': name})",
                "desc": (
                    "HTML search for each drug name. ANZCTR has no JSON API — "
                    "`search_anzctr()` parses ACTRN14-digit IDs from the HTML via regex. "
                    "Returns ACTRN IDs and constructed URLs."
                ),
                "scope": "One GET per drug, with a 1.0-second sleep before the call.",
            },
            {
                "name": "trial_registries (NCT discovery check)",
                "kind": "Supabase table",
                "via": "inline Python in workflow Step 3 → requests.get('/rest/v1/trial_registries', ...)",
                "desc": (
                    "Inline Step 3 queries `trial_registries` for rows updated today "
                    "with `registry_name=ct_gov`, `search_status=found`, and "
                    "`verified_by=validation_research` — these are the newly discovered "
                    "NCT IDs from the just-completed registry search pass."
                ),
                "scope": "One query in inline Step 3, filtered to today's timestamp.",
            },
        ],
        "cleaning": (
            "**The registry search has a hard relevance gate before any write.** "
            "`search_ctgov()` only accepts a study if the drug name or at least one "
            "alias appears as a substring in the CT.gov trial title or intervention list. "
            "Short tokens (≤5 chars after hyphen-splitting) are excluded to prevent "
            "common abbreviations from matching unrelated trials. Aliases that are '—' "
            "or blank are dropped before the search. The ANZCTR search is less precise "
            "(HTML regex for ACTRN numbers) — it's a discovery signal, not a verified "
            "match. `conflict_detector.py` applies the 'no table is assumed correct' "
            "principle: every detected conflict is written as `needs_review` with both "
            "values recorded in `details` JSONB, never auto-resolved. Structural "
            "warnings (`field_consistency`, `brand_name`) are escalated from `warning` "
            "to `needs_review` only — the status change signals that a human or model "
            "session needs to evaluate them, without implying they are errors."
        ),
        "writes": [
            {
                "name": "trial_registries",
                "kind": "Supabase table",
                "via": "sb_upsert('trial_registries', rows, on_conflict='drug_id,registry_name')",
                "desc": (
                    "Two rows per drug per run (one for `ct_gov`, one for `anzctr`), "
                    "upserted on `(drug_id, registry_name)`. Fields written: "
                    "`search_status` (found/not_found), `trial_count`, "
                    "`last_searched_at`, `verified_by='validation_research'`, "
                    "and `notes` (trial count or 'Searched; no matching trials found'). "
                    "Even not-found results are written so the next run knows this drug "
                    "was already searched on this date."
                ),
                "scope": "2 rows per drug in the flagged worklist.",
            },
            {
                "name": "drug_validation_results",
                "kind": "Supabase table",
                "via": "sb_upsert('drug_validation_results', row, on_conflict='drug_id,check_type')",
                "desc": (
                    "Three types of writes: "
                    "(1) `stage_trial_match` rows: `check_status` flipped to `pass` "
                    "(if found) or left as `warning` with `confidence='supported'` "
                    "(confirmed searched, not found). "
                    "(2) `field_consistency` / `brand_name` rows: `check_status` "
                    "escalated from `warning` to `needs_review`. "
                    "(3) Conflict rows from `conflict_detector.py`: new "
                    "`needs_review` rows for target_consistency, indication_consistency, "
                    "and company_resolution conflicts, with full conflict detail in "
                    "`details` JSONB. All upserts key on `(drug_id, check_type)`."
                ),
                "scope": (
                    "One upsert per drug per check_type per run. Conflict checks "
                    "produce one row per unique conflict found in `conflict_detector.py`."
                ),
            },
            {
                "name": "drugs.validation_summary",
                "kind": "Supabase table (JSONB column patch)",
                "via": "sb_patch('drugs', {'validation_summary': {...}}, {'id': 'eq.<drug_id>'})",
                "desc": (
                    "After each drug is resolved, `validation_summary` (a JSONB column) "
                    "is refreshed with the current check_type → check_status map, an "
                    "overall status (`fail` > `warning` > `pass`), and "
                    "`last_validated_at` timestamp. This keeps the dashboard's "
                    "per-drug quality indicator current without a separate aggregation job."
                ),
                "scope": "One PATCH per resolved drug.",
            },
        ],
    },
    "phases": [
        {
            "label": "Step 1 — validation_research.py helpers",
            "note": "Logging, Supabase wrappers, and the two external registry search functions.",
            "groups": [
                [
                    {
                        "function": "log(msg, indent)",
                        "lines": 4,
                        "desc": "Timestamped print with optional indent. Used throughout the script.",
                    },
                    {
                        "function": "sb_get(table, params)",
                        "lines": 2,
                        "desc": "Wraps `_db.sb_get()` with `limit=2000`.",
                    },
                    {
                        "function": "sb_upsert(table, records, on_conflict)",
                        "lines": 6,
                        "desc": "Wraps `_db.sb_upsert()`, normalizing a single dict to a list.",
                    },
                ],
                [
                    {
                        "function": "search_ctgov(drug_name, aliases, indication)",
                        "lines": 63,
                        "desc": (
                            "Builds a search_terms list from drug_name + aliases (deduped, "
                            "blanks and dashes dropped). For each term, GETs "
                            "`/api/v2/studies` with active/completed status filter, "
                            "pageSize=20. Applies the hard relevance gate: only keeps "
                            "studies where a search term (or a 5+-char word from it) "
                            "appears in `briefTitle + interventions`. Returns a deduped "
                            "list of `{nct_id, title, phase, status, sponsor}` dicts. "
                            "Sleeps 0.5s between terms."
                        ),
                    },
                    {
                        "function": "search_anzctr(drug_name)",
                        "lines": 29,
                        "desc": (
                            "GETs ANZCTR's HTML search page for `drug_name`. Extracts "
                            "ACTRN14-digit IDs via regex. Returns a list of "
                            "`{actrn_id, url}` dicts. No relevance gate — any ACTRN "
                            "in the page counts. Catches all exceptions gracefully."
                        ),
                    },
                ],
            ],
        },
        {
            "label": "Step 1 — resolve_drug and escalate_structural_warnings",
            "note": "The two core business logic functions called from run().",
            "groups": [
                [
                    {
                        "function": "resolve_drug(drug, dry_run)",
                        "lines": 88,
                        "desc": (
                            "Orchestrates the registry search for one drug: calls "
                            "`search_ctgov()` then (with 1s sleep) `search_anzctr()`. "
                            "Unless `--dry-run`: upserts two `trial_registries` rows "
                            "(ct_gov + anzctr search results); upserts a "
                            "`drug_validation_results` row with the new check_status; "
                            "re-fetches all checks for the drug and refreshes "
                            "`drugs.validation_summary`. Returns the result dict with "
                            "`resolved` flag and `new_nct_ids` list."
                        ),
                    },
                    {
                        "function": "escalate_structural_warnings(dry_run)",
                        "lines": 26,
                        "desc": (
                            "Fetches all `drug_validation_results` rows where "
                            "`check_type in (field_consistency, brand_name)` and "
                            "`check_status=warning`. For each, upserts with "
                            "`check_status='needs_review'` and a human-readable note. "
                            "Called at the end of `run()` after the registry search pass."
                        ),
                    },
                ],
            ],
        },
        {
            "label": "Step 1 — main run() function",
            "note": "Orchestrates the full validation research pass for one invocation.",
            "groups": [
                [
                    {
                        "function": "run(drug_filter, dry_run)",
                        "lines": 60,
                        "desc": (
                            "Fetches unresolved `stage_trial_match` warnings. Applies "
                            "`--drug` filter if specified. Fetches full drug records for "
                            "the filtered set. Iterates each drug calling `resolve_drug()` "
                            "with 2.0s inter-drug sleep, counting resolved vs still_missing. "
                            "Calls `escalate_structural_warnings()`. Prints the resolved / "
                            "still_missing / new_nct_ids summary."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Step 2 — conflict_detector.py",
            "note": "Separate script; runs after Step 1 so newly resolved drugs are reflected.",
            "groups": [
                [
                    {
                        "function": "conflict_detector.py (full script, 939 lines)",
                        "lines": 939,
                        "desc": (
                            "Detects three classes of cross-table contradictions: "
                            "(1) **target_consistency** — `drugs.target` (free-text) vs "
                            "`drug_targets.target_id` (structured); only flags drugs that "
                            "already have `drug_targets` rows. "
                            "(2) **indication_consistency** — `drugs.indication_short` vs "
                            "`drug_indications` + `indications` (structured); same coverage-gap "
                            "carve-out. "
                            "(3) **company_resolution** — `drugs.company_display` vs "
                            "`companies` + `company_aliases`; acquired-asset aware. "
                            "All conflicts are written as `needs_review` to "
                            "`drug_validation_results` with both values in `details` JSONB "
                            "and severity (high/medium/low). Never auto-corrects any field. "
                            "Prints a formatted priority queue sorted by severity and confidence."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Steps 3 and 4 — inline workflow scripts",
            "note": "Two inline Python blocks in the YAML workflow; they run after both scripts complete.",
            "groups": [
                [
                    {
                        "function": "Step 3: NCT discovery check (inline)",
                        "lines": 20,
                        "desc": (
                            "Queries `trial_registries` for rows updated today with "
                            "`registry_name=ct_gov`, `search_status=found`, and "
                            "`verified_by=validation_research`. If any rows exist, prints "
                            "the drug IDs, trial counts, and a 'ACTION REQUIRED: add to "
                            "NCT_SEED_MAP' prompt for the next `ct_gov_sync.py` run."
                        ),
                    },
                    {
                        "function": "Step 4: warning summary (inline)",
                        "lines": 20,
                        "desc": (
                            "Queries `drug_validation_results` for all remaining "
                            "`check_status in (warning, fail, needs_review)`, ordered by "
                            "severity descending then drug_id, limit 100. Prints a "
                            "formatted list or 'All validation checks passing' if none remain."
                        ),
                    },
                ],
            ],
        },
    ],
}
