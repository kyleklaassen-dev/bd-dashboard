# Submit Intel Pipeline Audit — Session 65
**Date:** 2026-05-26  
**Purpose:** Trace the full submit intel flow from user submission to displayed intelligence. Identify gaps, delays, and manual bottlenecks.

---

## Pipeline Overview

```
User (Submit Intel form)
  → submitted_intel (status='new')
      → review_submitted_intel.py [every 6h]
          → status='analyzed' or 'needs_review'
              → Kyle reviews in Submitted Intel tab
                  → "✅ Send to Queue" → discovery_queue (status='pending')
                  → "❌ Reject" → submitted_intel (status='rejected')
                  → "💬 Needs Review" → submitted_intel (status='needs_review')
                      → discovery_queue → company_enrichment.py
                          → catalysts / deals / intel (via enrichment pipeline)
```

There are **two human decision points** and **two automated processing steps** in this pipeline. The total latency from submission to display can range from 6 hours (automated) to multiple days (if Kyle doesn't review).

---

## Step 1: User Submission

**Trigger:** Kyle clicks "Submit Intel" in the dashboard.

**Form fields:**
- Source URL (optional)
- Submitted text / notes (optional)
- Submitter name

**Database write:** `submitted_intel` with `status='new'`  
**Code:** `index.html` L15434–15443  

```javascript
const payload = {
  submitted_by:     name,
  source_url:       url || null,
  submitted_text:   text || null,
  status:           'new',
  raw_payload_json: { url, text, name, submitted_at: new Date().toISOString() }
};
await _sb.from('submitted_intel').insert([payload]);
```

**Current queue:** 9 rows with `status='new'` submitted 2026-05-26.

---

## Step 2: Automated Review — review_submitted_intel.py

**Trigger:** `review_submitted_intel.yml` runs every 6h (00:00, 06:00, 12:00, 18:00 UTC).

**Processing steps per row:**
1. Validates source URL (HTTP HEAD check) → sets `source_validation_status`
2. Fetches page text if URL is accessible (best-effort HTML scrape)
3. Calls Claude (claude-opus-4-6) with URL + submitted text → extracts:
   - `extracted_title`
   - `extracted_summary`
   - `extracted_key_facts_json`
   - `extracted_entities_json` (companies, drugs, areas, targets)
   - `proposed_actions_json` (suggested DB writes with rationale)
   - `confidence_level`
4. Matches extracted entities against `companies` and `drugs` tables
5. Checks for duplicates (same URL, similar title, similar event)
6. Sets `analyzed_at` + updates status:
   - `'analyzed'` — high confidence, proposed actions ready for review
   - `'needs_review'` — low confidence, entity match failure, or duplicate concern

**Latency:** 0–6 hours from submission to analysis (depends on when the cron fires).  
**Cost:** claude-opus-4-6 is called once per row. For the 9 current rows, this costs ~9 × ~$0.03 = ~$0.27.

**What Kyle sees after this step:**
In the Submitted Intel tab, each row now shows: Claude Summary, Extracted Entities, Proposed Actions. These give enough context to approve or reject without reading the original source.

---

## Step 3: Manual Review — Submitted Intel Tab

**Access:** Dashboard → Submitted Intel tab (nav icon top right)  
**Code:** `index.html` L15478–15663

**UI elements per row:**
- Claude Summary (from `extracted_summary`)
- Extracted entities (from `extracted_entities_json`)
- Proposed actions (from `proposed_actions_json`) — what enrichment would write if approved
- Source URL (clickable)
- Status badge + confidence level

**Action buttons:**

| Button | Action | DB write |
|---|---|---|
| ✅ Send to Queue | Inserts to `discovery_queue`, sets `status='imported'` | Two writes (discovery_queue + submitted_intel) |
| ❌ Reject | Sets `status='rejected'` | One write |
| 💬 Needs Review | Sets `status='needs_review'` | One write |

**Current bottleneck:** This step requires Kyle's manual attention. The pipeline stops here until he reviews. With 9 submissions today and a busy schedule, items may sit in 'analyzed' for days.

---

## Step 4: Automated Processing — company_enrichment.py via discovery_queue

**Trigger:** "Send to Queue" writes to `discovery_queue` with `status='pending'`. `company_enrichment.py` drains this queue during its scheduled runs.

**What company_enrichment.py does with a queued item:**
- Looks up `company_name`, `drug_name`, `area_id`, `target` from the queue row
- Runs enrichment pipeline for the relevant context
- May produce: new `catalysts` rows, new `deals` rows, new `intel` rows, updated drug fields
- Sets `discovery_queue.status='completed'` or `'failed'`

**From the queue row structure (L15625–15638):**
```javascript
const queueRow = {
  company_name:   companies[0] || null,  // first extracted company
  drug_name:      drugs[0]     || null,  // first extracted drug
  area_id:        areas[0]     || null,  // first extracted area
  target:         targets[0]   || null,
  reason:         row.extracted_summary,
  source_url:     row.source_url,
  source:         'submitted_intel',
  status:         'pending',
};
```

**Limitation:** Only the first extracted company, drug, and area are included. Multi-entity submissions (e.g., a partnership article mentioning 3 companies and 2 drugs) are reduced to a single primary entity for enrichment purposes.

**Current queue:** 60 `pending` items in `research_queue` (which likely contains both submitted_intel-originated and system-generated items). Latency to processing depends on how frequently company_enrichment.py runs and its per-item throughput.

---

## Step 5: Display

Once `company_enrichment.py` processes the queue item and writes new `catalysts`, `deals`, or `intel` rows, those records surface through the standard routing paths:

- New `catalysts` → visible in area tab Catalyst Calendar, company card catalysts, homepage
- New `deals` → visible in area tab deals feed, drug card deals section
- New `intel` + `intel_areas` → visible in area tab intel feed, global intel search

**Total end-to-end latency (best case):**
- Submission → analysis: 0–6h (next 6h cron cycle)
- Analysis → manual approval: hours to days (Kyle's review time)
- Approval → display: 0–24h (next company_enrichment.py run)

**Total end-to-end latency (typical):** 1–3 days

---

## Status State Machine

```
new
  → [review_submitted_intel.py]
      → analyzed
      → needs_review
  [Kyle action]
      → imported (→ discovery_queue → enrichment pipeline → display)
      → rejected
      → needs_review (manual flag — no further automation)
```

There is **no automated path from `needs_review` to `imported`**. Items flagged as `needs_review` require a second manual action. If Kyle doesn't return to them, they stay in `needs_review` indefinitely.

---

## Gap Analysis

| Gap | Severity | Description |
|---|---|---|
| Manual review bottleneck | P1 | Pipeline stops at Step 3 until Kyle reviews. 9 items backlogged today. |
| Single-entity queue insertion | P2 | Multi-entity articles only get the first entity enriched. Reduces recall. |
| needs_review dead end | P2 | `needs_review` items have no automation path forward. |
| No SLA visibility | P3 | No dashboard count of "waiting >24h" or "waiting >7d" items. |
| discovery_queue ≠ research_queue | Note | Queue terminology: "discovery_queue" is the insert target (L15640), "research_queue" is the visible table. Verify these are the same table. |

---

## Recommended Improvements

**P1 — Add Submitted Intel badge to daily workflow:**  
At the start of each BD session, check: `submitted_intel WHERE status='analyzed'`. If items are waiting, review them before other work. These represent Kyle's own submitted context — they are the highest-signal inputs in the system.

**P2 — Auto-promote high-confidence items:**  
For rows where `confidence_level='A'` and no duplicate concern is flagged, consider auto-promoting to `discovery_queue` without manual review. This would remove the human gate for clear, high-confidence submissions.

**P3 — Improve queue row completeness:**  
Change `siSendToQueue` to include all extracted entities, not just `[0]`. This requires either passing an array or inserting multiple `discovery_queue` rows for multi-entity submissions.

**P4 — Add needs_review aging alert:**  
Add to the health report: `submitted_intel WHERE status='needs_review' AND created_at < NOW()-7d`. Items in this state for >7 days are likely forgotten.

---

## Current 9 Submissions (2026-05-26)

All 9 rows have `status='new'` and `created_at` of 2026-05-26. They will be analyzed in the next `review_submitted_intel.yml` cycle (runs at 00:00, 06:00, 12:00, 18:00 UTC). After analysis, they will appear in the Submitted Intel tab for Kyle's review.

---

*Session 65 — 2026-05-26. Flow traced from index.html L15434–15663 + review_submitted_intel.py header + Supabase live query.*
