"""
Static description of the Backfill Company BD Angles pipeline
(.github/workflows/manual-backfill-bd-angle.yml).

Documents what backfill_bd_angle.py does — filling company_profiles.bd_angle
for all NULL rows using Claude Sonnet with key_risk, why_it_matters, and drug
context as inputs.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "backfill_bd_angle",
    "workflow_name": "Backfill Company BD Angles",
    "workflow_file": ".github/workflows/manual-backfill-bd-angle.yml",
    "schedule": "Manual dispatch only — no cron schedule",
    "entrypoint": "scripts/enrichment/backfill_bd_angle.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Manual one-shot backfill that fills `company_profiles.bd_angle` for rows "
        "where the field is NULL. Designed to be run once to clear the initial "
        "backlog (up to 78 missing profiles when originally written), then "
        "maintained going forward by the full company enrichment pipeline. "
        "For each NULL profile, the script fetches the company's drugs in that area "
        "from `drug_competitive_scores` and `drugs`, then calls Claude Sonnet with a "
        "structured prompt that includes the Ailux context, the company's `key_risk` "
        "and `why_it_matters` fields, and the drug list. Claude returns a 2–4 "
        "sentence `bd_angle` paragraph describing the primary BD opportunity or "
        "strategic consideration for Ailux relative to that company×area combination. "
        "The result is patched onto the `company_profiles` row with a 1.5-second "
        "inter-call sleep to respect API rate limits."
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
        label="backfill_bd_angle.py\n(entrypoint — main())",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    profiles_in [
        label="Supabase\ncompany_profiles\n(read here — bd_angle is.null)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_loop {
        label="Per-profile loop (up to --limit rows)"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        get_drugs [label="get_company_drugs()\nfetch from drug_competitive_scores + drugs"]
        gen_angle [label="generate_bd_angle()\nClaude Sonnet call\n2-4 sentence bd_angle"]
        patch [label="_db.sb_patch()\ncompany_profiles.bd_angle"]
    }

    dcs_in [
        label="Supabase\ndrug_competitive_scores + drugs\n(read per company×area)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    claude_api [
        label="Claude Sonnet\n(ai.client.run_text)\nbd_angle per profile",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    profiles_out [
        label="Supabase\ncompany_profiles\n(bd_angle patched — NULL rows only)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    stdout [
        label="stdout\nper-profile progress\nfinal success count",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> profiles_in [label="  sb_get(bd_angle is.null)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    profiles_in -> get_drugs
    get_drugs -> dcs_in [style="bold", color="#c9890a", fontcolor="#c9890a"]
    dcs_in -> get_drugs
    get_drugs -> gen_angle
    gen_angle -> claude_api [label="  run_text()", style="bold", color="#c9890a", fontcolor="#c9890a"]
    claude_api -> gen_angle
    gen_angle -> patch
    patch -> profiles_out [label="  sb_patch (not dry_run)", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    patch -> stdout [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        sb_in [label="Supabase\ncompany_profiles (NULL bd_angle rows)\ndrug_competitive_scores + drugs", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        claude_in [label="Claude Sonnet\n(Anthropic API)\nbd_angle paragraph per profile", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Backfill\nBD Angles",
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

        profiles_out [label="Supabase\ncompany_profiles.bd_angle\n(patched for NULL rows)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nper-profile progress + final count", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    claude_in -> pipeline
    pipeline -> profiles_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "company_profiles",
                "kind": "Supabase table",
                "via": "_db.sb_get('company_profiles', {'bd_angle': 'is.null', ...})",
                "desc": (
                    "Fetches all `company_profiles` rows where `bd_angle IS NULL`, "
                    "ordered by `area_id, company_id`, up to `--limit` rows (default 100). "
                    "The `--area` filter adds `area_id=eq.<area>` to restrict to one area. "
                    "Fetches `company_id`, `area_id`, `key_risk`, and `why_it_matters` — "
                    "the fields used in the Claude prompt."
                ),
                "scope": "One query per run. Bounded by `--limit`.",
            },
            {
                "name": "drug_competitive_scores",
                "kind": "Supabase table",
                "via": "get_company_drugs() → _db.sb_get('drug_competitive_scores', {'context_id': 'eq.<area>'})",
                "desc": (
                    "Fetches `drug_id` values for drugs scored in the target area, "
                    "up to 20. Used to identify which drugs are relevant for the "
                    "area — a bridge between the area and the company's drug set. "
                    "Note: this query uses `context_id` (the area) rather than "
                    "`company_id`, so it returns drugs from all companies in the area."
                ),
                "scope": "One query per profile.",
            },
            {
                "name": "drugs",
                "kind": "Supabase table",
                "via": "get_company_drugs() → _db.sb_get('drugs', {'company_id': 'eq.<company>'})",
                "desc": (
                    "Fetches the company's drug records filtered by `company_id`, "
                    "up to 15 rows. Returns `id`, `name`, `stage`, `target`, "
                    "`mechanism`, `overlap`, and `indication_short` for the prompt's "
                    "drug block. Note: the company filter is applied after the area "
                    "drug_ids fetch, so only the company's own drugs appear."
                ),
                "scope": "One query per profile.",
            },
            {
                "name": "Claude Sonnet (Anthropic API)",
                "kind": "External API",
                "via": "generate_bd_angle() → ai_client.run_text(_BD_ANGLE_CFG, prompt)",
                "desc": (
                    "One call per profile. The prompt includes: Ailux context block, "
                    "company ID, area label, up to 8 drug lines (name/stage/target/overlap/"
                    "indication), `key_risk` (truncated to 300 chars), and "
                    "`why_it_matters` (truncated to 300 chars). Response is expected to "
                    "be plain prose — responses starting with `{` or shorter than 30 "
                    "characters are rejected and the profile is skipped. `max_tokens=300`."
                ),
                "scope": (
                    "One API call per profile, with 1.5s sleep between calls. "
                    "Up to `--limit` calls per run (default 100)."
                ),
            },
        ],
        "cleaning": (
            "**Only NULL rows are targeted, and the write is a PATCH (not a full update).** "
            "The `bd_angle IS NULL` filter in the initial query ensures already-populated "
            "profiles are never re-processed. The Claude response is validated with two "
            "guards: it must not start with `{` (rejecting accidental JSON output) and "
            "must be at least 30 characters (rejecting empty or trivially short responses). "
            "Failed profiles log a '✗ no output generated' message but don't abort the "
            "loop — the run continues with the next profile and the skipped row remains "
            "NULL for the next run. The PATCH only touches `bd_angle` and `updated_at`; "
            "no other fields are modified."
        ),
        "writes": [
            {
                "name": "company_profiles.bd_angle",
                "kind": "Supabase table",
                "via": "_db.sb_patch('company_profiles', {'bd_angle': ..., 'updated_at': NOW}, {'company_id': ..., 'area_id': ...})",
                "desc": (
                    "Patches `bd_angle` and `updated_at` on each successfully generated "
                    "profile row. The PATCH key is the composite `(company_id, area_id)` — "
                    "both are required to uniquely identify a `company_profiles` row."
                ),
                "scope": (
                    "One PATCH per successfully generated profile. Skipped profiles "
                    "(Claude error or validation rejection) receive no write."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Drug context fetch",
            "note": "get_company_drugs() provides the drug list for the Claude prompt.",
            "groups": [
                [
                    {
                        "function": "get_company_drugs(company_id, area_id)",
                        "lines": 14,
                        "desc": (
                            "Queries `drug_competitive_scores` for drug_ids in the area "
                            "(up to 20), then queries `drugs` filtered by `company_id` "
                            "(up to 15). Returns the drug records. Note: the area filter "
                            "is applied to `drug_competitive_scores.context_id`, not to "
                            "the company's drugs directly — this means drugs from all "
                            "companies in the area are fetched first, then filtered by "
                            "company_id in the second query."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "BD angle generation",
            "note": "generate_bd_angle() builds the prompt and calls Claude Sonnet.",
            "groups": [
                [
                    {
                        "function": "generate_bd_angle(company_id, area_id, profile, drugs)",
                        "lines": 46,
                        "desc": (
                            "Builds the prompt with: Ailux context, company ID, area label "
                            "(from `AREA_LABELS` dict, fallback to area_id), up to 8 drug "
                            "lines, `key_risk[:300]`, and `why_it_matters[:300]`. Calls "
                            "`ai_client.run_text()` with `model=claude-sonnet-4-6` and "
                            "`max_tokens=300`. Strips the response and applies two "
                            "validation guards. Returns the text or `None` on failure."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main loop",
            "note": "main() orchestrates the fetch, per-profile loop, and summary.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 52,
                        "desc": (
                            "Parses `--limit`, `--dry-run`, `--area`. Fetches NULL profiles "
                            "with optional area filter. For each: calls `get_company_drugs()`, "
                            "calls `generate_bd_angle()`, prints the first 120 chars of the "
                            "result. Unless `--dry-run`: calls `_db.sb_patch()` and logs "
                            "success/failure. Sleeps 1.5s between profiles. Prints the final "
                            "'Done: N/M bd_angles written' summary."
                        ),
                    }
                ],
            ],
        },
    ],
}
