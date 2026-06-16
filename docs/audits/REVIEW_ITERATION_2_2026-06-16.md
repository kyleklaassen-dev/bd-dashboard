# Meridian Platform — Autonomous Review Pass (Iteration 2)

> **Run:** overnight 2026-06-16 (~02:45 UTC) · **Mode:** READ-ONLY (no service key locally; DB writes flagged, not made).
> **Scope:** post-re-enable backend HEALTH check. Earlier tonight the 15 recurring Claude-API
> workflows were re-enabled (disabled since 2026-06-06) and a Meridian Research run was dispatched.
> This pass verifies the pipeline is genuinely moving (not silently failing) and that fresh content
> is being produced.
> **Sources:** GitHub Actions API (`kyleklaassen-dev/bd-dashboard`, `main`), `raw.githubusercontent`,
> and anon/publishable reads against `https://tghntyofptvfhmtchwcv.supabase.co/rest/v1`.

---

## 0. Headline

- **Workflow health: GREEN.** Across all non-`pages` runs since the 2026-06-15 re-enable, there is
  **zero genuine workflow failure.** Every completed Claude-API and free-API workflow concluded
  `success`. The only non-success is **one benign `cancelled`** (Patent Sweep dispatch) — it
  completed its core write step and was cut at a late keyless step; not a systemic fault.
- **Engine is MOVING again.** Live DB writes are landing **tonight**: `drugs.updated_at` max =
  **2026-06-16T02:41Z**, `entity_edges` + `company_patents` written at **01:27Z**. The platform is
  not failing-before-write.
- **Fresh Issue: NOT YET — and that is expected, not a fault.** `meridian_today.html` is still the
  **2026-06-06** Issue. Tonight's **Meridian Research run is still `in_progress`** (step 5, 210-min
  timeout, started 01:27Z). The Writer sits at the END of the nightly chain
  (Research -> Source Verify -> Content Verify -> Score -> Writer) and has not fired yet. It will be
  triggered when the chain completes, with a **10:30 UTC fallback cron** as a safety net.
- **All 15 re-enabled workflows confirmed `state=active`** (54 workflows total, all active).
- **GitHub-fixable items applied this pass: none required.** No broken YAML, no bad path, no missing
  secret in CI. The one open dependency is owner/credential-side (see section 5).

---

## 1. Workflow health since the re-enable

Queried `GET /actions/runs?per_page=100` (pages 1-2, `created>=2026-06-14/15`) and the per-workflow
run histories for the nightly chain. Filtered out the high-volume `pages build and deployment`
noise (these are GitHub Pages CDN deploys, all `success`/benign `cancelled` superseded builds).

### 1a. Non-`pages` runs since 2026-06-15 — conclusions

| Conclusion | Count | Notes |
|---|---|---|
| `success` | ~27 | all scheduled + dispatched Claude-API and free-API jobs |
| `in_progress` | 1 | **Meridian Research** (id 27587814826), dispatched 01:27Z |
| `cancelled` | 1 | **Meridian Patent Sweep** (id 27587691194) — benign, see 1c |
| `failure` | **0** | — |

Representative successes tonight (workflow_dispatch, 01:12-01:28Z window — the re-enable smoke test):
Meridian API Harvest (Daily), Meridian Efficacy & NCT Verification, Meridian Abstract Fetcher,
Meridian Orange/Purple Book Refresh (x4). Scheduled jobs through 2026-06-15 (Signal Monitor,
Pipeline Health Monitor, Stock Price Refresh, Completeness Scoring, Daily Ranking Snapshots,
Verify Competitor Edges, Materialize Structural Edges, Morning Summary, Validation Tests, etc.)
all `success`.

### 1b. Meridian Research (the critical path) — current state

Run `27587814826`, event `workflow_dispatch`, started `2026-06-16T01:27:35Z`:

```
job: research  status: in_progress
  1 Set up job          OK success
  2 Checkout            OK success
  3 Set up Python       OK success
  4 Install dependencies OK success
  5 Run research pipeline ... in_progress   <- currently here
  9 Post Set up Python  . pending
 10 Post Checkout       . pending
```

Setup + dependency install succeeded — **no startup/secret failure**. The pipeline (RSS -> filter ->
dedup -> full-text -> LLM extract -> Supabase; then CT.gov poller + EDGAR 8-K sweep) is executing.
Timeout is 210 min, so it has ample runway. **Last successful Research run before tonight was
2026-06-06** — confirming the 9-day gap from the disable, now being closed.

### 1c. The one `cancelled` run — diagnosed, benign

Patent Sweep `27587691194` (workflow_dispatch, 01:24Z) reached:
steps 1-7 `success` (incl. **"Write company_patents (cache-only)" OK** — which is why 116 new
`company_patents` rows landed at 01:27Z), then step 8 "Resolve patent families (SureChEMBL,
keyless)" was `cancelled`, and the **service-key cleanup step still ran (OK)**. This is a manual/
superseded cancel during the re-enable testing, on a **keyless free-API** workflow — no Claude
spend, no data loss, no secret leak. **No action needed.**

---

## 2. Fresh content — was a new Issue generated tonight?

**No new Issue yet — by design, because the chain hasn't completed.**

- `index.html` serves the current Issue as **`meridian_today.html`** (confirmed via the served-file
  scan; sibling pages: `Meridian_Live.html`, `meridian_atlas.html`, `meridian_ask.html`, etc.).
- `meridian_today.html` last **content** commit: `ed6cefc8` —
  *"Meridian issue 2026-06-06 — add reader feedback widget [auto]"* (2026-06-06T17:52Z). The two
  later commits (`444a2535`, `e33db542`, 2026-06-07) were **security key migrations**, not content.
- The Writer (`meridian-write.yml`) is **event-driven**: `workflow_run` on
  *"Compute Landscape Dependency Scores"* completing (the tail of the nightly chain), plus a
  **`schedule: cron "30 10 * * *"`** (10:30 UTC) fallback. `write_meridian.py` writes **one Issue
  per day** and skips if today's already exists.
- Because tonight's **Research is still `in_progress`**, the downstream chain (and thus the Writer)
  has not been reached. **Expectation:** once Research succeeds, the chain should produce a fresh
  `meridian_today.html` for 2026-06-16; if the chain stalls, the 10:30 UTC Writer fallback covers it.

**Verdict:** Issue is currently **stale (2026-06-06)** but a fresh one is **pended, not failed.**
Re-check after ~10:30 UTC.

---

## 3. Scheduled vs dispatch — re-enabled workflows are active

`GET /actions/workflows` -> **54 workflows, ALL `state=active`.** The 15 Claude-API recurring
workflows are confirmed active. Cron cadence (UTC) so the owner knows when fresh content lands:

| Workflow | Cron (UTC) | Cadence |
|---|---|---|
| Meridian Research | `0 6 * * *` | daily 06:00 (2 AM ET) |
| Meridian Writer | `30 10 * * *` | daily 10:30 fallback (event-driven primary) |
| Narrative Generation | `0 10 * * 0` | Sundays 10:00 |
| Patient Briefs | `0 7 * * 0` | Sundays 07:00 |
| Landscape Briefings | `30 9 * * 0` | Sundays 09:30 |
| BD Recommender | `0 9 * * 0` | Sundays 09:00 |
| Content Verifier | `30 8 * * 2,5` | Tue + Fri 08:30 |
| Source Verifier | `0 8 * * 1,4` | Mon + Thu 08:00 (full sweep) |
| Evidence Collectors | `0 15 * * 6` | Saturdays 15:00 |
| Intelligence Pipeline (company-enrichment) | `0 4 * * *` / `10 4 * * *` | daily 04:00 / 04:10 |
| Validation Research Pass | `0 7 * * 0` | Sundays 07:00 |

(Free-API harvesters — API Harvest Daily, Abstract Fetcher, Efficacy Verification, etc. — are also
active per the daily-cadence retune logged 2026-06-15.)

**Note for the owner:** the daily 06:00 UTC Research cron means the next *automatic* nightly cycle
should run on schedule tomorrow; tonight's was a manual dispatch and is the one currently running.

---

## 4. Accuracy sweep — is data actually being written?

Anon `count=exact` + `max(timestamp)` on high-value tables. **The engine is writing today and
tonight:**

| Table | rows since 2026-06-15 | most-recent timestamp | read |
|---|---|---|---|
| `drugs` (`updated_at`) | 67 | **2026-06-16T02:41Z** | writing **right now** |
| `entity_edges` (`created_at`) | 139 | **2026-06-16T01:27Z** | tonight |
| `company_patents` (`created_at`) | 116 | **2026-06-16T01:27Z** | tonight (Patent Sweep step 7) |
| `intel_facts` (`created_at`) | 2 | 2026-06-15T21:20Z | pre-dispatch (research output) |
| `drug_sources` (`created_at`) | 2 | 2026-06-15T21:20Z | pre-dispatch |
| `research_reads` (`created_at`) | 2 | 2026-06-15T21:20Z | pre-dispatch |
| `drug_efficacy_endpoints` | 0 | 2026-06-10T22:56Z | cadence (verification cron) |
| `news_articles` | 0 | **2026-06-07T01:41Z** | **stale — see below** |
| `drug_validation_results` | 0 | (no today rows) | cadence |

**Reading:** structural/edge/patent/drugs writes are live tonight -> the engine is unblocked and
moving. The **LLM-extraction outputs** (`intel_facts`, `drug_sources`, `research_reads`) last landed
at **21:20Z (yesterday's pipeline)** and have **not yet been refreshed by tonight's Research run
because that run is still in_progress.** Expect these to advance once Research step 5 completes.

> **Correction to the night's premise:** DB writes are **not** blocked in CI. `meridian-research.yml`
> reads `SUPABASE_SERVICE_KEY` from **repo secrets** (`secrets.SUPABASE_SERVICE_KEY`), and
> the runner clearly wrote tonight (02:41Z). The "no service key" constraint applies only to **this
> local review pass**, not to GitHub Actions. Good news: the pipeline can complete the write path.

---

## 5. Findings classified

### (A) GitHub-fixable now — applied this pass
- **None.** No broken workflow YAML, bad path, or CI-side missing secret was found. All 54 workflows
  active; the nightly chain is wired correctly (Research -> ... -> Score -> Writer, with Writer fallback).
  Nothing to safely change without risking the in-flight run.

### (B) Needs credentials / owner / time — flag only
1. **Fresh Issue is pended on the in-flight Research run.** Re-verify `meridian_today.html` shows a
   **2026-06-16** date after the chain completes (or after the 10:30 UTC Writer fallback). If it is
   still 2026-06-06 past ~11:00 UTC, investigate the Research run's outcome and the
   Score -> Writer `workflow_run` linkage.
2. **`news_articles` stale since 2026-06-07.** Homepage News (`fetch-homepage-news.yml`) is
   `workflow_run`-triggered off Research completing, plus a 07:30 UTC fallback. It hasn't refreshed
   because Research hasn't completed since 2026-06-06. Should self-heal once tonight's Research
   finishes; if not, the 07:30 UTC fallback or a manual dispatch will refill it. **Owner watch item.**
3. **API spend now live again.** The 15 Claude-API workflows are active and the daily 06:00 UTC
   Research cron will incur Anthropic spend each night (routed through the tier router — EXTRACT/JUDGE
   = Haiku, ENRICH = Sonnet, REASON/VERIFY = Fable). No credit/rate-limit error was observed tonight,
   but this is the cost-driver to monitor now that the pause is lifted.

### (C) Informational
- The high run-count of `pages build and deployment` (many `cancelled`) is normal CDN-deploy churn
  (concurrent superseded builds), not workflow failures.
- Patent Sweep's `cancelled` (1c) is benign; its core write succeeded and the service-key cleanup ran.
- `drug_efficacy_endpoints` / `drug_validation_results` showing 0 today is expected cadence (weekly /
  scheduled verification), not a fault.

---

## 6. One-line verdict

**Backend re-enable is HEALTHY: 0 workflow failures, all 54 workflows active, and live DB writes are
landing tonight (drugs 02:41Z, edges/patents 01:27Z). The nightly Research run is still in_progress;
the fresh 2026-06-16 Issue is correctly pended on the chain, not failed — re-check after ~10:30 UTC.
No GitHub-fixable defect found; the only watch items are owner/credential-side (Issue completion,
news refresh chaining, and resumed Claude-API spend).**
