# China NMPA/CDE Sponsor-Sweep — `china_trials` monitor

**Purpose.** Catch the moment a China-developed TL1A/IL-23 competitor registers a clinical
trial in China. These assets are invisible to ClinicalTrials.gov, WHO ICTRP search is broken
upstream, and ChiCTR is mostly academic. Company drug trials live on the **NMPA/CDE platform**
(`chinadrugtrials.org.cn`). Chinese firms register under their own internal codes (e.g. Qyuns =
`QX###N`, not the Western `QX030N`), so we sweep by **sponsor (申请人)** and match.

## CRITICAL CONSTRAINT — collection cannot be a plain GitHub Action
The CDE site sits behind an **anti-bot WAF** (it sets `FSSBBIl1UgzbN7N80S/T` cookies and serves
a JS-challenge shell with **zero trial rows** to any non-browser client). Verified 2026-06-15:
- The search is a server-side form POST to `clinicaltrials.searchlist.dhtml` (fields incl.
  `appliers` = sponsor, `keywords`, `drugs_name`, `currentpage`).
- A plain `GET`+cookie-jar+`POST` from a server (sandbox/CI) returns the 25 KB challenge shell,
  **no CTR rows** — the WAF challenge must be executed by a real browser.

**Consequence:** the COLLECT step requires a real browser (Claude-in-Chrome). It cannot run as a
headless GitHub Action over plain HTTP, and we will **not** build WAF/anti-bot evasion. Only the
PROCESS step (matching + writing) is GitHub-native.

## What IS in GitHub (the automatable half)
- `scripts/integrations/cde_sponsor_sweep.py` — deterministic matcher + `china_trials` writer.
- `data/china_sponsors.json` — sponsor (申请人) terms + asset code/indication profiles.
Both deployed to `kyleklaassen-dev/bd-dashboard`. Tested end-to-end (synthetic QX030N row:
written, idempotent, removed).

## Procedure
**1. COLLECT (real browser — the one non-headless step).** For each company in
`data/china_sponsors.json` with a `cn` term: open
`https://www.chinadrugtrials.org.cn/clinicaltrials.searchlist.dhtml`, click **二级查询**, type the
`cn` term into **申请人**, search, page through, and capture each row (登记号/试验状态/药物名称/适应症/
试验通俗题目), tagged with `company_id`, into a JSON list:
```json
[{"company_id":"qyuns","ctr":"CTR20260219","status":"进行中 尚未招募",
  "drug_name":"QX030N注射液","indication":"...","title":"..."}]
```

**2. PROCESS (deterministic, repo script).**
```bash
python3 scripts/integrations/cde_sponsor_sweep.py --ingest rows.json --dry-run   # preview
python3 scripts/integrations/cde_sponsor_sweep.py --ingest rows.json             # write
```
Env: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`.

## Matching (resolve-or-skip — never fabricates)
- **CODE match → auto-written**: row drug name/title contains an asset code/alias (normalized:
  lowercased, CN dosage suffix 注射液/片… and hyphens stripped).
- **HEURISTIC → review only, NOT written**: same sponsor + indication keyword (克罗恩 / 溃疡性结
  肠炎 / 炎症性肠 …) overlap. Catches a trial filed under a *different internal code*; confirm by hand.
- Else skipped. Idempotent (`on_conflict=trial_id`).

## Config maintenance (`data/china_sponsors.json`)
- `companies[]`: `company_id`, `en`, `cn[]`. Still need CN 申请人 name: **newsoara, shboan, santaana**.
- `assets[]`: `drug_id`, `company_id`, `codes[]`, `target`, `indication_kw[]`.

## Status 2026-06-15
0 of the 15 tracked assets are currently registered on CDE (most preclinical/pre-IND; even Ph1
QX030N absent — Qyuns has QX001S/002N/004N/005N/006N/008N/013N/027N/029N, no QX030N). `china_trials`
is legitimately empty; the monitor flags the first filing when it appears.
