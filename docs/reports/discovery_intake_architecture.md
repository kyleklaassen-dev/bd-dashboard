# Discovery Intake Architecture
_Meridian BD Platform — v1.0 — May 2026_

---

## The Core Problem

The system was **target-centric**: discovery searched for "anti-TL1A antibodies" and missed J&J's DUET/VEGA (IL-23+TNF combo, Phase 3 UC/CD) — a critical IBD competitor that never touches TL1A.

The fix has two parts:
1. **Broaden search scope** — think indication-first, not mechanism-first
2. **Gate insertion** — discovered candidates must be reviewed before entering the dashboard

This document defines the full intake pipeline.

---

## Six-Step Discovery Intake Workflow

```
Discover → Classify → Score → Route → Review → Promote
```

### Step 1 — Discover

Live web search (Claude Haiku + search tools) scans for:

| Entity Type     | Example                                          |
|-----------------|--------------------------------------------------|
| `company`       | J&J with VEGA/DUET in UC/CD                      |
| `molecule`      | XPF005 (Ailux internal), mirikizumab (Eli Lilly) |
| `trial`         | NCT05435560 — DUET Phase 3                       |
| `deal`          | Sanofi/Teva co-promotion of duvakitug            |
| `catalyst`      | PCD: risankizumab UC approval Q3 2026            |
| `article`       | NEJM VEGA results publication                    |
| `evidence_item` | ECCO abstract: tezepelumab CRSwNP data           |
| `poster`        | DDW 2026: TEV-48574 Phase 2 interim              |

**Scope rule:** Search indication-first, not mechanism-first. For TL1A/IBD, the search context explicitly includes IL-23 inhibitors, IL-23+TNF combos, JAKs with active UC/CD trials, and integrins — not just TL1A antibodies.

---

### Step 2 — Classify

Each discovered item is assigned:

| Field              | Values                                                |
|--------------------|-------------------------------------------------------|
| `entity_type`      | company / molecule / trial / deal / catalyst / article / evidence_item / poster |
| `area_id`          | tl1a / tslp / il4ra / fcrn / igf1r / tcell           |
| `overlap`          | Direct / Adjacent / Same-Space / Watch                |
| `competition_layer`| 1 = Direct Mechanism / 2 = Clinical Competition / 3 = Strategic Threat |
| `company_id_suggested` | Slug derived from company name (e.g. `jnj`)       |
| `drug_name`        | Generic name or code name                             |
| `suggested_dest`   | Where this belongs if approved (see Routing section)  |

**Competition Layer definitions:**

- **Layer 1 — Direct Mechanism:** Same target or drug class as the lead Ailux asset. Example: anti-TL1A antibodies competing with TEV-48574.
- **Layer 2 — Direct Clinical Competition:** Different mechanism but same indication + patient population. Example: J&J risankizumab in UC, targeting biologic-naive and bio-experienced CD/UC patients.
- **Layer 3 — Strategic Threat:** Adjacent indication, platform breadth, or major deal activity that could redirect capital or pipeline priority. Example: AbbVie ABBV-157 (IL-23×TL1A bispecific) as a future combo threat.

---

### Step 2.5 — Relationship Classification (v10)

For every discovered entity, the system must classify **how it relates to Ailux's competitive landscape** — not just that it's relevant.

| Field | Values |
|-------|--------|
| `relationship_type` | `peer_competitor` / `direct_competitor` / `adjacent_competitor` / `licensor` / `licensee` / `partner` / `co_developer` / `parent_subsidiary` / `asset_owner` / `unknown` |
| `relationship_confidence` | `confirmed` / `inferred` / `suggested` |
| `why_discovered` | Free text: what search query or criteria matched this entity |

**Default behavior (enforced in prompt and script):**
- If no explicit licensing or partnership deal is found → `relationship_type = 'peer_competitor'`, `relationship_confidence = 'inferred'`
- `licensor` or `licensee` requires `relationship_confidence = 'confirmed'` — i.e., a press release, SEC filing, or official announcement citing the agreement. The script will downgrade unconfirmed licensor/licensee claims to `peer_competitor/inferred` automatically.
- `confirmed` = explicitly stated in a primary source (press release, CT.gov, SEC filing, IR page)
- `inferred` = logically deduced (same target/indication, same geography, overlapping pipeline)
- `suggested` = speculative association requiring human verification

**Canonical example — Akeso Biopharma in IL-4Rα:**

```
Company: Akeso Biopharma
Molecule: AK120 (anti-IL-4Rα antibody, Phase 3, atopic dermatitis)
relationship_type: peer_competitor
relationship_confidence: confirmed
why_discovered: IL-4Rα antibody in atopic dermatitis Phase 3 — same target and
                indication as Stapokibart; Chinese innovative biologics peer
```

Akeso and Hengenix Biotech are **peer competitors** to Keymed Biosciences — both developing IL-4Rα antibodies for the same indications. They have no licensing or ownership relationship to Stapokibart (CM310). The discovery system correctly surfaces them as Layer 2 competitors; the relationship classification layer prevents the system from implying a structural deal where none exists.

**Reviewer workflow in the UI:**
1. Open the detail panel for a discovered entity
2. See: `Relationship Classification: Peer Competitor (inferred)` with the `why_discovered` text
3. If the classification is wrong, override via the dropdown (e.g., change to `licensor` if a deal was announced)
4. Click Approve — the override is persisted to `discovery_queue.relationship_type` before promotion

**Migration required (v10):** Run `scripts/migrations/v10_relationship_fields.sql` in the Supabase SQL editor before the next enrichment run.

---

### Step 3 — Relevance Scoring

Each candidate receives a **relevance_score (1–10)** with a written rationale.

| Score | Definition                                                              | Action                          |
|-------|-------------------------------------------------------------------------|---------------------------------|
| 9–10  | Critical — Direct Mechanism or major late-stage Clinical Competition    | Priority review, flag in queue  |
| 7–8   | Important — Layer 2/3 with Phase 2+ data in same patient population     | Standard review queue           |
| 5–6   | Watch — early stage, emerging mechanism, or adjacent indication         | Low-priority review             |
| 1–4   | Low relevance — very early, different patient population, non-competitive| Auto-archive (recorded, no alert)|

**Scoring factors:**
- Same patient population (+3)
- Same indication / label (+2)
- Target overlap or mechanism adjacency (+2)
- Clinical stage (Phase 3 = +2, Phase 2 = +1, Phase 1 = 0, Pre-IND = -1)
- Deal/financing significance (>$500M = +1)
- Catalyst timing (within 12 months = +1)
- Company strategic strength (large cap with BD track record = +1)
- Ailux strategic relevance (directly competitive with TEV-48574 or Ailux pipeline = +2)

---

### Step 4 — Route to Correct Destination

`suggested_dest` tells the reviewer where the item belongs if approved:

| Destination         | Meaning                                                     |
|---------------------|-------------------------------------------------------------|
| `new_company`       | Create company row + company_areas + initial drug row       |
| `molecule_update`   | Patch an existing drug row (new data on known molecule)     |
| `trial_update`      | Update trial record (new results, phase change, enrollment) |
| `deal_update`       | Add to deals/partnerships table                             |
| `catalyst_update`   | Update or add catalyst for an existing company              |
| `evidence_update`   | Add to evidence table for an existing molecule              |
| `research_queue`    | Flag for manual research (incomplete data, needs follow-up) |

---

### Step 5 — Review Queue

All candidates with relevance_score ≥ 5 enter `discovery_queue` with `status='pending'`. Candidates with relevance_score < 5 are inserted with `status='archived'` (recorded but not surfaced).

Each queue item displays:

| Field                | Example                                                        |
|----------------------|----------------------------------------------------------------|
| `company_name`       | Janssen (J&J)                                                  |
| `drug_name`          | Guselkumab + Golimumab (DUET combo)                            |
| `area_id`            | tl1a                                                           |
| `competition_layer`  | 2                                                              |
| `overlap`            | Adjacent                                                       |
| `relevance_score`    | 9                                                              |
| `relevance_rationale`| Phase 3 UC/CD combo targeting same biologic-naive patients     |
| `reason`             | DUET/VEGA studies are the most advanced IL-23+TNF combo in IBD |
| `suggested_dest`     | new_company                                                    |
| `confidence_score`   | 95                                                             |
| `source_url`         | clinicaltrials.gov/NCT...                                      |

**Reviewer actions (status transitions):**

| Action     | Status          | Effect                                          |
|------------|-----------------|--------------------------------------------------|
| Approve    | `approved`      | Triggers promotion to production tables          |
| Reject     | `rejected`      | Records rejection reason; entity not created     |
| Watch      | `watch`         | Parks item for later review without promoting    |
| Enrich     | stays `pending` | Flags item for deeper Step 5 enrichment first    |
| Merge      | `approved`      | Merges into existing entity (company/drug)       |

---

### Step 6 — Promote to Production

After approval, the promotion step:
1. Creates `companies` row (if `suggested_dest = new_company`)
2. Creates `company_areas` links (area_id + indication_group)
3. Creates `drugs` row if a molecule was identified
4. Creates `drug_areas` links
5. Sets `created_company_id` and `created_drug_id` on the queue row
6. Marks `status = 'approved'`, `reviewed_at = now()`

Promotion is currently **manual** — Kyle approves from the queue and then triggers enrichment for the new entity. Automated promotion (for relevance 9–10 items with confidence ≥ 90) can be added later.

---

## Update Tracking

For every accepted entity, the system tracks what changed and when:

| Field             | Purpose                                                   |
|-------------------|-----------------------------------------------------------|
| `discovered_at`   | When first found by Step 1                                |
| `last_updated_at` | Last time this entity was re-evaluated                    |
| `change_log`      | Human-readable diff: "Stage advanced Phase 2 → Phase 3"  |
| `relevance_score` | Re-computed on each discovery run                         |
| `reviewed_at`     | When approved/rejected                                    |
| `reviewed_by`     | Who approved (currently 'kyle' / 'system')                |

---

## Preventing the Two Failure Modes

| Failure Mode                              | Fix                                                        |
|-------------------------------------------|------------------------------------------------------------|
| Missing important competitors (J&J DUET)  | Indication-first search scope + Layer 2 competition layer  |
| Flooding platform with noise              | Relevance scoring gate + review queue before promotion     |

**The invariant:** Nothing reaches the Meridian dashboard without either (a) being an existing entity enriched by the pipeline, or (b) passing through discovery_queue with a human approval.

---

## Current Implementation Status

| Component                                  | Status         |
|--------------------------------------------|----------------|
| `discovery_queue` table (Supabase)         | ✅ Live         |
| Step 1 → discovery_queue (not production)  | ✅ Deployed     |
| Relevance score + competition_layer in prompt | ✅ Deployed  |
| Indication-first AREA_LABELS_MAP           | ✅ Deployed     |
| Promotion workflow (approval → production) | 🔲 TODO        |
| Review queue UI in Meridian dashboard      | 🔲 TODO        |
| Notification workflow (high-priority alert)| 🔲 TODO        |
| Update/change_log tracking                 | 🔲 TODO        |

---

## Next Priorities

1. **Review queue UI** — simple Meridian tab showing pending items, sortable by relevance_score and competition_layer, with Approve/Reject/Watch actions
2. **Promotion script** — `approve_discovery_item(id)` function that creates the production rows from a queue entry
3. **Nightly re-scoring** — re-run relevance scoring on existing queue items when new landscape data is available
4. **Notification** — email/Slack alert for relevance 9–10 items found by nightly run
