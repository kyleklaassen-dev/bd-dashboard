# Meridian Session Protocol

Every session — autonomous or with Kyle — follows this exact sequence.  
Non-negotiable. The protocol is what prevents drift.

---

## SESSION START (Claude does this before any other action)

### Step 1 — Read PRIORITY.md
Open `PRIORITY.md`. Identify the `## ▶ DOING NOW` item. That is the session's task.  
If DOING NOW is ambiguous or blocked, surface the blocker to Kyle immediately. Do not invent work.

### Step 2 — Read NEXT_SESSION.md (if it exists)
Check for `NEXT_SESSION.md` in the workspace root. If present:
- Read it fully
- Confirm the task matches PRIORITY.md DOING NOW
- Note any open issues or known gaps from the previous session

### Step 3 — Check validation queue
Run or query: `drug_validation_results WHERE status IN ('fail','warning','needs_review')`  
Note failures. Do not proceed with new enrichment if P1 validation failures exist.

### Step 4 — Check governance violations
Query: `governance_violations WHERE resolved = false`  
Note any outstanding violations. Flag to Kyle if count > 0.

### Step 5 — State the plan (2 sentences max)
Before touching any file or table, write:
> "Doing: [specific task from PRIORITY.md]. Done when: [acceptance criteria]."

Wait for Kyle's go-ahead in live sessions. In autonomous sessions, proceed after stating the plan.

---

## WRITTEN PLAN RULE (for any code or schema change)

Before touching `index.html`, any Python script, or any database schema, produce:

```
PLAN
-----
What changes: [specific files or tables]
Why it matters: [how this serves the North Star]
Affected areas: [tabs, queries, consumers]
Expected output: [what you will see when it works]
Rollback: [git revert / SQL revert steps]
Acceptance tests: [3–5 "must appear / must not appear / must stay" assertions]
```

In live sessions: get Kyle's approval before building.  
In autonomous sessions: write the plan to NEXT_SESSION.md, then proceed.

---

## DECISION RULE (architectural or strategic choices)

Present 3 options. Rank by: value delivered × implementation risk × sessions required.  
Recommend one. Wait for approval.

Do NOT decide alone on: data model changes, tab structure, governance rules, sequence changes.  
DO decide alone on: implementation details within an approved plan, code quality, error handling.

---

## NO-OVERWRITE RULE

- Never delete working code without deprecation comment first: `// DEPRECATED: removing [date] — [reason]`
- New features go behind flags until validated
- Preserve existing tab behavior when modifying shared components
- If removing a database table or column: parallel-write period required, then 2-week monitor, then DROP

---

## MULTI-AGENT COORDINATION

When more than one agent is active (e.g., a second autonomous agent running enrichment overnight), both agents read and write to the same shared files. To prevent overwrites:

**Rule 1 — Append, don't overwrite NEXT_SESSION.md mid-task.**  
Only overwrite NEXT_SESSION.md at true session end. Mid-task notes go to `AGENT_LOG.md` (append-only).

**Rule 2 — Sign every write to shared files.**  
Any agent updating PRIORITY.md or NEXT_SESSION.md must prepend: `<!-- updated: [ISO timestamp] agent: [session-id or "cowork"|"autonomous"] -->`  
If the file already has a timestamp newer than 5 minutes ago from a different agent, read the current state before writing — do not blindly overwrite.

**Rule 3 — PRIORITY.md queue changes need Kyle.**  
Agents may update the COMPLETED table and the DOING NOW item (marking done, pulling in next). Agents must NOT reorder the queue or add/remove HORIZON items — that requires Kyle's approval.

**Rule 4 — AGENT_LOG.md is the safe scratch space.**  
Write in-progress notes, discoveries, and partial results to `/Users/kyleklaassen/Documents/Claude/Projects/BD Platform/AGENT_LOG.md` (append with timestamp + agent). This file is never overwritten, only appended.

**Rule 5 — One writer per file/table per session (added 2026-06-08, the overlap fix).**  
The damage from running several sessions at once is two concurrent edits to the SAME `index.html` (one deploy silently overwrites the other) or two writers on the same Supabase table. To prevent it:
- **`index.html` has a single owner at a time.** Before editing it, a session claims it by appending a line to `AGENT_LOG.md`: `LOCK index.html <ISO-time> <session-id>`. Release with `UNLOCK index.html …` at deploy. If an unreleased lock newer than ~30 min exists from another session, do NOT edit index.html — coordinate or wait.
- **Deploy = read-before-write.** The Git Data API deploy must fetch the current remote blob SHA immediately before PUT (the `deploy.py` helper already does). Never deploy a copy of index.html that was read at the start of a long session — re-pull, re-apply your diff, then push, so you don't clobber another session's commit.
- **Parallel agents must own disjoint files/tables.** When spawning multiple build agents in one session, give each a non-overlapping scope (different table, different migration number, different page). Two agents must never write the same table or the same HTML file.
- **Migrations are numbered, never reused.** Check the highest `migrations/vNNN_*.sql` before creating one; bump by one. Two sessions picking the same vNNN is the table-level version of the index.html clobber.
- **Prefer one focused session over many concurrent ones.** Concurrency only pays off for genuinely independent data pulls (the API ingestion agents). UI work on `index.html` should be serial.

**Cache reality (not a bug to fix — a constraint to plan around).**  
GitHub Pages serves HTML through a CDN with a ~10-minute edge TTL, and the Pages *build* itself must finish first (watch `pages/builds/latest` → `built`). So after any deploy, the live site can show the OLD page for several minutes even on a hard refresh — this is server-side, not the browser. Verify a deploy via `curl` against `raw.githubusercontent.com/.../main/<file>` (instant) rather than the Pages URL, and tell Kyle a change may take a few minutes to appear. Embedded iframes (Live/Atlas tabs) carry a per-session `?cb=` buster so they don't compound the cache with their own stale copy.

---

## SESSION END (Claude does this before closing)

### Step 1 — Run acceptance tests
For every change made this session, verify the acceptance tests written in the plan.  
Report: passed / failed / skipped.

### Step 2 — Update PRIORITY.md
- Move completed item to `## COMPLETED` table with date and commit SHA
- Promote next queue item to `## ▶ DOING NOW`
- Add any newly discovered items to HORIZON

### Step 3 — Write NEXT_SESSION.md
Overwrite the file with:

```markdown
# Next Session — [date]

## Completed this session
- [item]: [commit SHA]

## Open issues / known gaps
- [anything that didn't work, partial completions, follow-up needed]

## Validation status
- [deployed but not yet verified / fully validated / 28/28 passing]

## Next task (one sentence)
[Exact task, matching PRIORITY.md DOING NOW]

## Decisions needed from Kyle (if any)
- [only if something requires his input before work can proceed]
```

### Step 4 — Deploy
Commit and push if any dashboard changes were made.  
Record commit SHA in NEXT_SESSION.md.

---

## KYLE'S ROLE

Kyle approves:
- Priority sequence changes
- Architectural decisions (data model, tab structure, governance)
- Strategic direction (what Meridian should answer, which areas to prioritize)

Kyle does not need to approve:
- Implementation details within an agreed plan
- Code quality choices
- Minor enrichment runs that don't change schema

---

## CORRECTION SIGNALS

If Kyle says any of the following, stop and recalibrate:
- "That's not what I meant" → re-read PRIORITY.md, restate the plan
- "We've done this before" → check COMPLETED table, check memory files
- "Why are we doing this?" → re-anchor to North Star before continuing
- "What happened to X?" → read NEXT_SESSION.md, check COMPLETED table

---

## DAILY PIPELINE (GitHub Actions — runs without Cowork)

- **2:00 AM ET** — `research.py` → RSS scan + intel extraction → Supabase intel table
- **6:30 AM ET (Mon–Sat)** — `write_meridian.py` → reads intel → generates meridian_today.html → deploys to GitHub Pages
- **Nightly** — `company_enrichment.py` → company profile enrichment
- **Daily** — `signal_monitor.py` + `stock_prices.py`

If Meridian article is missing: check GitHub Actions run history (not Cowork).
