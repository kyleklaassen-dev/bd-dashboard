# BD Analyst Playbook
**Ailux BD Platform — Daily Operating Guide**
*Last updated: 2026-05-19*

---

## What the Platform Does

The platform is a self-aware intelligence graph for 6 disease areas (TL1A, TSLP, IL-4Rα, FcRn, IGF1R, T-cell). Each night it pulls trial data from ClinicalTrials.gov, enriches company profiles via Claude, scores every tracked entity for research completeness, and surfaces the most urgent gaps. You work the queue; the pipeline fills the gaps.

---

## The Research Queue

### Where to find it
Home tab → **Research Queue** panel (purple border, top of page).

### What the numbers mean

| Field | What it tells you |
|---|---|
| **Priority score** | Urgency rank (0–200+). Calculated from completeness score, strategic importance, recency of triggers, and AI signal strength. Higher = more urgent. |
| **Completeness tier** | `thin` (<40 points) = major gaps; `partial` (40–69) = meaningful but incomplete; `strong` (≥70) = well-documented |
| **Next best action** | The single most impactful thing to do for this entity right now |

### Priority score thresholds
- **≥100** (red): High urgency — act this week
- **70–99** (amber): Moderate urgency — act this month
- **<70** (grey): Low urgency — monitor passively

### Status workflow
Each entity has a status button. Click to cycle:

`○ Pending` → `● In Progress` → `✓ Done` → `○ Pending`

- **Pending**: Not yet actioned
- **In Progress**: You're actively researching this entity
- **Done**: Research gap addressed; score will update on next pipeline run
- Use **Hide done** checkbox to declutter the view

---

## What Each Next Best Action Means

| Next Best Action | What to do |
|---|---|
| **Add strategic positioning** | Fill in `vs_ailux` field in company_profiles — what's the BD angle for Ailux vs this competitor? |
| **Add trial data** | Check ClinicalTrials.gov manually for this drug; trial may be too new for the nightly sync |
| **Generate catalysts** | Trigger manual enrichment for this area; or add a catalyst manually via the Catalysts feed |
| **Add drug mapping** | A company is tracked but its drug program hasn't been linked — check `drugs` table for this entity |
| **Add company profile** | New entity discovered but no profile yet — trigger `company_enrichment.py --area <area> --company <id>` |
| **Run full enrichment** | Multiple stages missing — trigger a full pipeline run for this area |
| **Review deal activity** | Entity has no deals tracked; check press releases / SEC filings for recent BD activity |
| **Verify trial status** | Trial record exists but status is stale — check ClinicalTrials.gov directly |

---

## Triggering Pipeline Runs

### Nightly (automatic)
- **Mon–Sat 04:00 UTC**: TL1A full pipeline + research intelligence audit for all 6 areas
- **Sunday 05:00 UTC**: Full pipeline for all 6 areas (ct_gov + enrichment + intelligence)

### Manual run — single area
1. Go to [GitHub Actions](https://github.com/kyleklaassen-dev/bd-dashboard/actions/workflows/company-enrichment.yml)
2. Click **Run workflow**
3. Set `area` to the disease area (e.g. `tl1a`)
4. Optionally filter to one company with `company` field (e.g. `sanofi`)
5. Use `dry_run = true` to test without writing to Supabase

### Manual run — all areas
Same as above but set `area = all`. Takes ~30–45 minutes.

### Skip trial sync (faster)
Check `skip_trial_sync = true` when trials are already fresh and you only want to re-run enrichment/scoring.

---

## Overriding a Status

Override `assigned_status` manually when:

- **Pipeline flagged something already resolved**: Mark `done` immediately — don't wait for a rescore
- **You've deprioritized an entity**: Mark `done` to remove from active view, even if score is still `thin`
- **You're about to work on something not yet in the queue**: Mark `in_progress` manually; the queue will catch up after the next pipeline run

The pipeline **does not reset** `assigned_status` — it only updates scores, tiers, and next_best_action. Your status decisions persist until you change them.

---

## Identity Layer Health Panel

Home tab → **Identity Layer Health** panel (teal border, below Research Queue).

| Stat | What it means | Target |
|---|---|---|
| **Canonical Coverage %** | % of drug records resolved to a canonical ID | 100% |
| **Active Canonicals** | Distinct real drug programs tracked | Growing |
| **Fuzzy Pending** | Name variants that scored ≥85% similar but weren't auto-merged — need human review | 0 |
| **Resolver Errors** | Failed identity resolution attempts not yet retried | 0 |

### If Fuzzy Pending > 0
Run this query in Supabase SQL editor to see what needs review:
```sql
SELECT related_id AS input_name, canonical_id AS near_match,
       new_value->>'fuzzy_ratio' AS ratio, performed_at
FROM identity_audit_log
WHERE operation = 'flag_review'
ORDER BY performed_at DESC;
```
Then manually update `drugs.canonical_drug_id` to merge, or leave separate if they're truly different programs.

### If Resolver Errors > 0
```bash
python scripts/identity_resolution.py --retry-errors
```

---

## Quick Reference — Key Scripts

| Script | Purpose | Common usage |
|---|---|---|
| `ct_gov_sync.py` | Pull trial records from ClinicalTrials.gov | `--area tl1a` |
| `company_enrichment.py` | Entity discovery, catalyst gen, enrichment, deal intel | `--area tl1a --company spyre` |
| `research_intelligence.py` | Score all entities, update research_queue | `--area all` |
| `identity_resolution.py` | Resolve a drug name or retry failed resolutions | `--name "tulisokibart"` or `--retry-errors` |
| `identity_health_check.py` | Read-only health report on identity layer | (no args) |

---

## What "Production-Ready" Means Here

The platform is your daily research tool, not a public product. It is ready when:
- The nightly pipeline runs without failures
- The research queue reflects your actual knowledge gaps
- The identity health panel stays green

It is **not** a source of truth for investor-facing work — always verify key data points (trial status, deal terms) from primary sources before using in BD materials.
