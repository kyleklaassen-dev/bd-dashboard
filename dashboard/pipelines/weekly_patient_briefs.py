"""
Static description of the Meridian Patient Briefs pipeline
(.github/workflows/weekly-patient-briefs.yml).

Documents what generate_patient_briefs.py does — iterating all indications in
indication_patient_intelligence and invoking patient_narrative.py for each to
generate a cited Patient Brief + Meridian Patient Analysis.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "patient_briefs",
    "workflow_name": "Meridian Patient Briefs",
    "workflow_file": ".github/workflows/weekly-patient-briefs.yml",
    "schedule": "Sundays 07:00 UTC (3 AM ET) — after the narrative refresh",
    "entrypoint": "scripts/narrative/generate_patient_briefs.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Weekly batch driver that regenerates the Meridian Patient Brief and "
        "Meridian Patient Analysis for every indication in `indication_patient_intelligence`. "
        "For each indication the driver invokes `scripts/patient_narrative.py` as a "
        "subprocess with `--section both`, which generates two narrative sections using "
        "the shared narrative provenance and gap-detection machinery. Unsourced patient "
        "facts surface in the evidence collection queue so the evidence collector can "
        "source them in a future run. The workflow runs `--all` by default; `--indications` "
        "accepts a comma-separated subset for partial regeneration via manual dispatch."
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
        label="generate_patient_briefs.py\n(entrypoint — main())",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    ipi_in [
        label="Supabase\nindication_patient_intelligence\n(read here — indication_name list)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_loop {
        label="Per-indication loop"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        patient_narrative [label="scripts/patient_narrative.py\n--indication <name> --section both\n(one subprocess per indication)"]
    }

    entity_narratives [
        label="Supabase\nentity_narratives\n(written by patient_narrative.py\nindication/ sections)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    stdout [
        label="stdout\nper-indication section count\ntotal sections written",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> ipi_in [label="  ng.get(indication_patient_intelligence)\n  (--all path)", style="bold", color="#c9890a", fontcolor="#c9890a"]
    ipi_in -> patient_narrative [label="  one subprocess\n  per indication"]
    patient_narrative -> entity_narratives [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    patient_narrative -> stdout [style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        ipi_in [label="Supabase\nindication_patient_intelligence\n(indication_name list)", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
        claude_in [label="Claude API\n(ai.client — via patient_narrative.py)\nPatient Brief + Meridian Patient Analysis", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Patient\nBriefs",
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

        narratives_out [label="Supabase\nentity_narratives\n(indication/ — patient_brief + patient_analysis sections)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nsection counts per indication", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    ipi_in -> pipeline
    claude_in -> pipeline
    pipeline -> narratives_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "indication_patient_intelligence",
                "kind": "Supabase table",
                "via": "ng.get('indication_patient_intelligence?select=indication_name')",
                "desc": (
                    "Fetches the full list of `indication_name` values from the "
                    "North Star patient intelligence table. Deduplicated into a sorted "
                    "set to form the worklist. Used only in the `--all` path; the "
                    "`--indications` path parses the comma-separated CLI argument instead."
                ),
                "scope": "One query, only in the `--all` path.",
            },
            {
                "name": "indication_patient_intelligence + evidence tables (via patient_narrative.py)",
                "kind": "Supabase tables (multiple, via sub-script)",
                "via": "subprocess.run(['scripts/patient_narrative.py', '--indication', name, '--section', 'both'])",
                "desc": (
                    "`patient_narrative.py` reads indication-specific patient intelligence "
                    "data, existing evidence sources, and any prior narrative sections. "
                    "It uses the same provenance and gap-detection machinery as the drug "
                    "narrative layer, so unsourced patient facts are flagged for the "
                    "evidence collector."
                ),
                "scope": "One subprocess per indication.",
            },
        ],
        "cleaning": (
            "**The driver is a thin subprocess orchestrator with no data logic.** "
            "It fetches the indication list, loops, and counts `'wrote indication/'` "
            "occurrences in each subprocess's stdout as a proxy for success. It does "
            "not parse or validate the narrative content — that logic lives in "
            "`patient_narrative.py`. A zero-sections result for an indication is "
            "reported in the stdout summary but does not abort the loop."
        ),
        "writes": [
            {
                "name": "entity_narratives",
                "kind": "Supabase table (via patient_narrative.py)",
                "via": "scripts/patient_narrative.py --section both (subprocess)",
                "desc": (
                    "Each `patient_narrative.py` invocation writes up to two narrative "
                    "sections to `entity_narratives` — a Patient Brief (the cited, "
                    "patient-facing summary) and a Meridian Patient Analysis (strategic "
                    "interpretation for the BD committee). Both sections are stored under "
                    "the `indication/` entity namespace."
                ),
                "scope": (
                    "Up to 2 rows per indication per run. Sections written by "
                    "`patient_narrative.py` are counted in stdout as "
                    "'wrote indication/<name>/<section>' lines."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Subprocess runner helper",
            "note": "run() wraps the per-indication subprocess call and extracts the section count from stdout.",
            "groups": [
                [
                    {
                        "function": "run(name)",
                        "lines": 8,
                        "desc": (
                            "Invokes `[sys.executable, 'scripts/patient_narrative.py', "
                            "'--indication', name, '--section', 'both']` with `cwd` set to "
                            "the parent of `narrative/`. Counts `'wrote indication/'` "
                            "occurrences in stdout as the sections-written proxy. Prints "
                            "the indication name (truncated to 40 chars), section count, "
                            "and last stdout line. Returns the section count."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main loop",
            "note": "main() parses args, builds the indication list, and runs the per-indication loop.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 16,
                        "desc": (
                            "Parses `--all` / `--indications` (mutually exclusive, one "
                            "required). In `--all` mode, fetches `indication_name` values "
                            "from `indication_patient_intelligence` via `ng.get()`. In "
                            "`--indications` mode, splits the comma-separated argument. "
                            "Prints the indication count, then calls `run(name)` for each "
                            "indication, accumulating the total sections written. Prints "
                            "the final 'done: N sections written across M indications' "
                            "summary."
                        ),
                    }
                ],
            ],
        },
    ],
}
