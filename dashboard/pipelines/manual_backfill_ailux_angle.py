"""
Static description of the Backfill ailux_angle — Watch Tier pipeline
(.github/workflows/manual-backfill-ailux-angle-watch.yml).

Documents what backfill_ailux_angle_watch.py does — a 3-mode pipeline
(dry_run → preview → commit) for backfilling drugs.ailux_angle by target tier.

NOTE: The entrypoint script (enrichment/backfill_ailux_angle_watch.py) is
referenced in the workflow YAML but does not currently exist in the repository.
This documentation is derived from the workflow inputs, the field_backfill_preview
staging pattern, and the ailux_angle field semantics.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "backfill_ailux_angle",
    "workflow_name": "Backfill ailux_angle — Watch Tier",
    "workflow_file": ".github/workflows/manual-backfill-ailux-angle-watch.yml",
    "schedule": "Manual dispatch only — no cron schedule",
    "entrypoint": "enrichment/backfill_ailux_angle_watch.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Manual backfill pipeline that populates `drugs.ailux_angle` for drugs "
        "currently missing that field. The pipeline uses a safe 3-mode pattern "
        "that requires explicit human sign-off before any data lands in production: "
        "**`dry_run`** — generates `ailux_angle` text for up to `max_drugs` drugs "
        "per tier and writes a preview artifact to `docs/ailux_angle_*.json`, but "
        "makes zero DB writes; "
        "**`preview`** — generates text and writes it to the `field_backfill_preview` "
        "staging table alongside the `run_id`, enabling human review before commit; "
        "**`commit`** — reads approved rows from `field_backfill_preview` matching "
        "the specified `run_id_override` and patches `drugs.ailux_angle`. "
        "Drugs are segmented into tiers by target/mechanism: Tier 1a "
        "(immunology-primary: FcRn, IL-4Rα, TSLP, IL-33, BAFF, TNF, JAK, OX40, "
        "complement), Tier 1b (oncology-adjacent with autoimmune signal: CD20, BCMA, "
        "FcγRIIb), and Tier 2 (oncology-only, metabolic, remainder). "
        "An `all` tier processes all three in one pass. "
        "**Note: `enrichment/backfill_ailux_angle_watch.py` does not currently exist "
        "in the repository** — this documentation is derived from the workflow YAML "
        "inputs and the `field_backfill_preview` staging pattern."
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

    dispatch [
        label="Manual workflow_dispatch\nmode (dry_run/preview/commit)\ntier (1a/1b/2/all) + max_drugs\nrun_id_override (commit mode)",
        fillcolor="#fde9c8",
        color="#d99a3b",
        fontcolor="#111827"
    ]

    entry [
        label="enrichment/backfill_ailux_angle_watch.py\n(entrypoint — missing from repo)",
        fillcolor="#f6dada",
        color="#c2554f",
        fontcolor="#111827"
    ]

    drugs_in [
        label="Supabase\ndrugs\n(read here — ailux_angle null, by tier)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    claude_api [
        label="Claude API\n(generate ailux_angle per drug)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_modes {
        label="Mode-dependent output path"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        dry_run [label="dry_run mode\n→ artifact only\n(zero DB writes)"]
        preview [label="preview mode\n→ field_backfill_preview\n(staging, not drugs)"]
        commit [label="commit mode\n→ read field_backfill_preview\n(approved rows by run_id)\n→ patch drugs.ailux_angle"]
    }

    fbp [
        label="Supabase\nfield_backfill_preview\n(staging table — preview mode writes\ncommit mode reads)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    drugs_out [
        label="Supabase\ndrugs.ailux_angle\n(patched — commit mode only)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    artifact [
        label="GitHub Actions artifact\ndocs/ailux_angle_*.json\n(30-day retention, all modes)",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    dispatch -> entry
    entry -> drugs_in [label="  reads NULL ailux_angle by tier", style="bold", color="#c9890a", fontcolor="#c9890a"]
    drugs_in -> claude_api [label="  per drug (up to max_drugs)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    claude_api -> dry_run [label="  dry_run mode"]
    claude_api -> preview [label="  preview mode"]
    commit -> fbp [label="  reads approved rows\n  by run_id_override", style="bold", color="#c9890a", fontcolor="#c9890a"]
    preview -> fbp [label="  writes staging rows", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    commit -> drugs_out [label="  sb_patch", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    dry_run -> artifact [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    preview -> artifact [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    commit -> artifact [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        drugs_in [label="Supabase\ndrugs\n(ailux_angle null, by tier)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        fbp_in [label="Supabase\nfield_backfill_preview\n(commit mode — approved rows by run_id)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        claude_in [label="Claude API\n(ailux_angle text per drug)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Backfill\nailux_angle",
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

        fbp_out [label="Supabase\nfield_backfill_preview\n(preview mode — staging rows)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        drugs_out [label="Supabase\ndrugs.ailux_angle\n(commit mode only)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        artifact_out [label="GitHub Actions artifact\ndocs/ailux_angle_*.json\n(30-day retention, all modes)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    drugs_in -> pipeline
    fbp_in -> pipeline
    claude_in -> pipeline
    pipeline -> fbp_out
    pipeline -> drugs_out
    pipeline -> artifact_out
}
""",
    "io": {
        "reads": [
            {
                "name": "drugs",
                "kind": "Supabase table",
                "via": "backfill_ailux_angle_watch.py (inferred from workflow YAML and field semantics)",
                "desc": (
                    "Drugs with `ailux_angle IS NULL`, filtered to the target tier by "
                    "mechanism or target field (Tier 1a: immunology-primary targets; "
                    "Tier 1b: oncology-adjacent with autoimmune signal; Tier 2: "
                    "oncology-only and remainder). Limited to `max_drugs` rows per run "
                    "(default 30, safety cap)."
                ),
                "scope": "One query per run (or per tier if `tier=all`).",
            },
            {
                "name": "field_backfill_preview",
                "kind": "Supabase table",
                "via": "backfill_ailux_angle_watch.py — commit mode reads approved rows by run_id",
                "desc": (
                    "In `commit` mode, the script reads rows from `field_backfill_preview` "
                    "matching the `run_id_override` parameter. These are the rows that "
                    "were staged in a previous `preview` run and approved by the analyst. "
                    "Only approved rows are patched to `drugs.ailux_angle`."
                ),
                "scope": "Read once in commit mode, filtered by run_id.",
            },
            {
                "name": "Claude API (Anthropic)",
                "kind": "External API",
                "via": "backfill_ailux_angle_watch.py (dry_run and preview modes)",
                "desc": (
                    "Called to generate `ailux_angle` text for each drug in dry_run and "
                    "preview modes. The prompt likely includes drug name, target, mechanism, "
                    "stage, and Ailux context to produce a specific BD angle paragraph. "
                    "Not called in commit mode (text is already staged in `field_backfill_preview`)."
                ),
                "scope": "One call per drug, up to `max_drugs` per run.",
            },
        ],
        "cleaning": (
            "**The 3-mode pattern is the safety mechanism.** No `ailux_angle` text "
            "ever lands in `drugs` without passing through two checkpoints: generation "
            "(dry_run or preview), then explicit human approval (commit with the matching "
            "`run_id`). The `run_id_override` requirement in commit mode prevents stale "
            "or mismatched staging rows from being committed — you must supply the exact "
            "run_id from the preview step. The `max_drugs` cap (default 30) limits blast "
            "radius per run so the analyst can review the artifact before processing the "
            "full backlog. The output artifact (`docs/ailux_angle_*.json`) is uploaded "
            "in all three modes so the generated text is always visible in the Actions "
            "run history regardless of whether a DB write occurred."
        ),
        "writes": [
            {
                "name": "field_backfill_preview",
                "kind": "Supabase table",
                "via": "backfill_ailux_angle_watch.py — preview mode",
                "desc": (
                    "In `preview` mode, generated `ailux_angle` text is written to "
                    "`field_backfill_preview` as staging rows tagged with the `run_id`. "
                    "Each row contains the drug_id, field name, generated value, and "
                    "provenance metadata. This is the human review checkpoint — the "
                    "analyst inspects the artifact and the staging table before running "
                    "`commit` mode."
                ),
                "scope": "One row per drug per preview run, up to `max_drugs`.",
            },
            {
                "name": "drugs.ailux_angle",
                "kind": "Supabase table",
                "via": "backfill_ailux_angle_watch.py — commit mode → sb_patch()",
                "desc": (
                    "In `commit` mode, approved rows from `field_backfill_preview` are "
                    "patched to `drugs.ailux_angle`. Only rows matching the "
                    "`run_id_override` are written — this scopes the commit to a specific "
                    "reviewed preview batch."
                ),
                "scope": (
                    "One PATCH per approved drug in the matched preview batch. "
                    "Zero writes in dry_run and preview modes."
                ),
            },
            {
                "name": "docs/ailux_angle_*.json (GitHub Actions artifact)",
                "kind": "CI artifact upload",
                "via": "actions/upload-artifact@v4 (workflow step, not the script)",
                "desc": (
                    "The script writes JSON output to `docs/ailux_angle_*.json`. The "
                    "workflow uploads this as a named artifact "
                    "(`ailux-angle-<mode>-tier<tier>-<run_number>`) with 30-day retention. "
                    "Available in all three modes — even dry_run produces a downloadable "
                    "artifact for review."
                ),
                "scope": "One artifact per run.",
            },
        ],
    },
    "phases": [
        {
            "label": "Script not present",
            "note": (
                "enrichment/backfill_ailux_angle_watch.py does not currently exist in the "
                "repository. The phases below are inferred from the workflow YAML, the "
                "field_backfill_preview staging pattern used by other backfill scripts, "
                "and the ailux_angle field semantics."
            ),
            "groups": [
                [
                    {
                        "function": "dry_run mode",
                        "lines": None,
                        "desc": (
                            "Reads drugs with null `ailux_angle` filtered by tier (up to "
                            "`max_drugs`). Calls Claude API to generate text for each. "
                            "Writes the generated text to `docs/ailux_angle_*.json` for "
                            "artifact upload. Makes zero DB writes. Designed for initial "
                            "review — run first to see what the model produces before "
                            "staging anything."
                        ),
                    },
                    {
                        "function": "preview mode",
                        "lines": None,
                        "desc": (
                            "Same generation loop as dry_run, but writes the results to "
                            "`field_backfill_preview` as staging rows tagged with the "
                            "current `run_id`. The analyst reviews the staging table "
                            "and artifact, approves rows, then triggers commit mode with "
                            "the matching `run_id_override`."
                        ),
                    },
                    {
                        "function": "commit mode",
                        "lines": None,
                        "desc": (
                            "Reads approved rows from `field_backfill_preview` matching "
                            "`run_id_override`. Patches each approved drug's `ailux_angle` "
                            "in the `drugs` table. Does not call Claude — uses the already-"
                            "staged text from the preview pass."
                        ),
                    },
                ],
            ],
        },
    ],
}
