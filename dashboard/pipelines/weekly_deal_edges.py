"""
Static description of the Meridian Materialize Deal Edges pipeline
(.github/workflows/weekly-deal-edges.yml).

Documents what materialize_deal_edges.py does — mirroring company_partnerships,
asset_transfer_history, and deals into entity_relationships as licensor_licensee,
co_developer, and parent_subsidiary edges.
This is descriptive only — it does not import or execute the pipeline.
"""

PIPELINE = {
    "key": "deal_edges",
    "workflow_name": "Materialize Deal Edges",
    "workflow_file": ".github/workflows/weekly-deal-edges.yml",
    "schedule": "Sundays 10:00 UTC (6 AM ET) — after BD Recommender, before landscape briefing",
    "entrypoint": "scripts/graph/materialize_deal_edges.py",
    "unit_key": "function",
    "unit_section_title": "Function-by-function, in order",
    "summary": (
        "Weekly graph maintenance job that keeps the `entity_relationships` table "
        "current with the BD-bearing relationship layer. The table was historically "
        "rich in competitive edges (`direct_competitor`) but thin on deal structure — "
        "licensing, co-development, and acquisition chains never got mirrored from "
        "the three source-of-truth tables. This pipeline fixes that by reading "
        "`company_partnerships`, `asset_transfer_history`, and `deals` in priority "
        "order and inserting any edge (source_id, target_id, relationship_type) not "
        "already present. The deduplication check makes the run fully idempotent — "
        "re-running on the same data is a no-op. Confidence scores and "
        "`verification_needed` flags are set based on whether the source row has a "
        "verified flag or source URL."
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
        label="materialize_deal_edges.py\n(entrypoint — main())",
        fillcolor="#bcd4f6",
        color="#3567b5",
        fontcolor="#111827"
    ]

    supabase_in [
        label="Supabase\ncompanies · entity_relationships\ncompany_partnerships\nasset_transfer_history · deals\n(read here — dedup + sources)",
        shape=cylinder,
        fillcolor="#ffe4b8",
        color="#c9890a",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    subgraph cluster_sources {
        label="Three source tables — processed in priority order"
        style="dashed"
        color="#9aa7b5"
        pencolor="#9aa7b5"
        fontname="Helvetica"
        fontsize=11
        fontcolor="#e8ecf2"

        cp [label="1. company_partnerships\n→ licensor_licensee / co_developer\n   / parent_subsidiary\n   conf: high if verified, else inferred"]
        ath [label="2. asset_transfer_history\n→ licensor_licensee / parent_subsidiary\n   conf: high if verified, else inferred"]
        deals [label="3. deals\n→ licensor_licensee / parent_subsidiary\n   / co_developer\n   (name-resolved, conservative)"]
    }

    dedup [
        label="Dedup check\nexisting set from entity_relationships\n+ seen set (in-flight)\nskip if (src, tgt, rt) already present"
    ]

    entity_rel [
        label="Supabase\nentity_relationships\n(insert new edges only)",
        shape=cylinder,
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11,
        margin="0.22,0.14"
    ]

    stdout [
        label="stdout\nedges added count\ninsert ok/failed",
        fillcolor="#d2f2dc",
        color="#2f9e63",
        fontcolor="#111827",
        fontsize=11
    ]

    entry -> supabase_in [label="  reads all sources + existing edges", style="bold", color="#c9890a", fontcolor="#c9890a"]
    supabase_in -> cp
    supabase_in -> ath
    supabase_in -> deals
    cp -> dedup
    ath -> dedup
    deals -> dedup
    dedup -> entity_rel [label="  sb_insert (new only, --dry-run skips)", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
    dedup -> stdout [label="  count + result", style="bold", color="#2f9e63", fontcolor="#2f9e63"]
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

        sb_in [label="Supabase\ncompanies · entity_relationships\ncompany_partnerships\nasset_transfer_history · deals", fillcolor="#fde9c8", color="#d99a3b", fontcolor="#111827"]
    }

    pipeline [
        label="Materialize\nDeal Edges",
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

        er_out [label="Supabase\nentity_relationships\n(new licensor_licensee / co_developer\n/ parent_subsidiary edges)", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
        stdout_out [label="stdout\nedges added + insert result", fillcolor="#d2f2dc", color="#2f9e63", fontcolor="#111827"]
    }

    sb_in -> pipeline
    pipeline -> er_out
    pipeline -> stdout_out
}
""",
    "io": {
        "reads": [
            {
                "name": "companies",
                "kind": "Supabase table",
                "via": "g('companies', {'select': 'id,name'})",
                "desc": (
                    "Full company list — id and name only. Used to build two structures: "
                    "`valid` (a set of known company IDs for existence checks) and "
                    "`name2id` (a lowercased name-to-id dict for name-based resolution "
                    "in the deals source). The `add()` helper silently skips any edge "
                    "whose source or target is not in `valid`."
                ),
                "scope": "Single query with `limit=5000`.",
            },
            {
                "name": "entity_relationships",
                "kind": "Supabase table",
                "via": "g('entity_relationships', {'select': 'source_id,target_id,relationship_type,source_type'})",
                "desc": (
                    "Existing company-type edges, used to build the `existing` set for "
                    "deduplication. Only rows with `source_type='company'` are loaded — "
                    "drug-level edges are filtered out in Python. The check is "
                    "`(source_id, target_id, relationship_type) in existing`."
                ),
                "scope": "Single query with `limit=5000`.",
            },
            {
                "name": "company_partnerships",
                "kind": "Supabase table",
                "via": "g('company_partnerships', {'select': '...'})",
                "desc": (
                    "Primary source for deal edges. `partnership_type` / `deal_type` "
                    "drives the relationship_type mapping: `licensed_in` → licensor_licensee "
                    "(partner as licensor), `licensed_out` → licensor_licensee (lead as "
                    "licensor), `co_developed` / `collaboration` → co_developer, "
                    "`acquisition` → parent_subsidiary. Verified partnerships get "
                    "`confidence='high'` and score 0.9; unverified get `confidence='inferred'` "
                    "and score 0.65."
                ),
                "scope": "Single query with `limit=5000`.",
            },
            {
                "name": "asset_transfer_history",
                "kind": "Supabase table",
                "via": "g('asset_transfer_history', {'select': '...'})",
                "desc": (
                    "Licensing chain history. `transfer_type` containing 'acqui' maps to "
                    "`parent_subsidiary`; all others map to `licensor_licensee`. "
                    "Uses `from_entity_id` / `to_entity_id` directly (no name resolution "
                    "needed). Verified rows get confidence 0.85; unverified 0.6."
                ),
                "scope": "Single query with `limit=5000`.",
            },
            {
                "name": "deals",
                "kind": "Supabase table",
                "via": "g('deals', {'select': '...'})",
                "desc": (
                    "Conservative third source. Only structural deal types are mapped: "
                    "`licensing` / `license` → licensor_licensee, `acquisition` → "
                    "parent_subsidiary, `collaboration` / `co-development` → co_developer. "
                    "Deal parties are resolved to company IDs via `name2id` lookups on "
                    "`from_company` / `to_company`, with a fallback to `company_id` for "
                    "`from_company`. Rows where either party can't be resolved are skipped. "
                    "All deal-sourced edges get `confidence='inferred'`, score 0.6, and "
                    "`verification_needed=True`."
                ),
                "scope": "Single query with `limit=5000`.",
            },
        ],
        "cleaning": (
            "**Deduplication is two-layered: against existing DB rows and within the "
            "current batch.** The `existing` set is loaded from the full `entity_relationships` "
            "table at startup. The `seen` set accumulates edges added during the current run. "
            "The `add()` helper checks both before appending. `add()` also silently drops: "
            "self-loops (`src == tgt`), rows with null source or target, and edges to/from "
            "unknown company IDs. The result is that the run is fully idempotent — "
            "re-running on unchanged data inserts 0 rows. The `--dry-run` flag "
            "(workflow dispatch input) prints the count without issuing any INSERT."
        ),
        "writes": [
            {
                "name": "entity_relationships",
                "kind": "Supabase table",
                "via": "_db.sb_insert('entity_relationships', rows)",
                "desc": (
                    "Batch INSERT of all new edges. Each row includes `source_id`, "
                    "`source_type='company'`, `target_id`, `target_type='company'`, "
                    "`relationship_type` (licensor_licensee / co_developer / "
                    "parent_subsidiary), `confidence`, `confidence_score`, "
                    "`source_url`, `inference_method='database_join'`, `evidence` "
                    "(single-item list), `notes`, `verification_needed`, "
                    "`is_current=True`, and `inferred_at` (UTC timestamp)."
                ),
                "scope": (
                    "Only rows not already in `existing` or `seen`. In a typical weekly "
                    "run with no new deals, this is 0 rows. When new partnerships or "
                    "deals land, it's the delta since the last run."
                ),
            },
        ],
    },
    "phases": [
        {
            "label": "Module-level helpers",
            "note": "One helper and the main() function — no class structure.",
            "groups": [
                [
                    {
                        "function": "g(t, params)",
                        "lines": 2,
                        "desc": (
                            "Thin wrapper around `_db.sb_get()` that always sets "
                            "`limit=5000` to ensure full table reads without pagination "
                            "hitting the default PostgREST ceiling."
                        ),
                    }
                ],
            ],
        },
        {
            "label": "Main loop",
            "note": "All logic lives in main(): load, dedup, source pass, insert.",
            "groups": [
                [
                    {
                        "function": "main()",
                        "lines": 75,
                        "desc": (
                            "1. Reads `companies` to build `valid` (id set) and `name2id` "
                            "(name lookup). "
                            "2. Reads existing `entity_relationships` company edges into the "
                            "`existing` dedup set. "
                            "3. Defines the inner `add()` helper (validates both IDs, checks "
                            "`existing` and `seen`, appends the edge row). "
                            "4. Iterates `company_partnerships` — maps `partnership_type` / "
                            "`deal_type` to relationship_type, calls `add()` for each valid pair. "
                            "5. Iterates `asset_transfer_history` — maps `transfer_type`, "
                            "calls `add()`. "
                            "6. Iterates `deals` — filters to structural deal types, resolves "
                            "company IDs via name, flips src/tgt for acquisition direction, "
                            "calls `add()`. "
                            "7. Prints count. If rows and not DRY, calls `_db.sb_insert()` "
                            "and prints result. Returns 0 on success, 1 on insert failure."
                        ),
                    }
                ],
            ],
        },
    ],
}
