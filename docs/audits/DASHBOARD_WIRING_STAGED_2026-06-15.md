# Dashboard Wiring — Staged Edit (not yet deployed)

**Date:** 2026-06-15 · **Author:** Claude (cowork) · **File:** `index.html` (local only)
**Status:** STAGED — validated locally, NOT deployed (GitHub token expired). One-line deploy command at the bottom, to run once the token is restored.
**Source of work:** `docs/audits/CONNECTIVITY_GAP_AUDIT_2026-06-15.md` (items #1–#6, #8, plus the narrative-trust relink).

---

## What was added

ONE new self-contained, additive, namespaced tab — **📡 Intelligence** (`intel2`) — that surfaces the highest-value backend tables the connectivity audit found NO live surface reads, plus a relink of the stranded narrative-trust block. No existing function was modified or renamed. All new CSS classes/IDs use the `intel2-` prefix. All JS is wrapped in an IIFE and registered via the existing `TAB_REGISTRY`. Errors are isolated (try/catch in the loader + `registerTab`'s own try/catch).

### Tab
- **Tab id:** `intel2`
- **Visible nav icon (the REAL nav):** `<button id="nav-icon-intel2" onclick="navTo('intel2')">📡 Intelligence</button>` in the `.nav-icon-btn` icon bar.
- **Hidden `.tab-btn`** added for `switchTab` compatibility (matches the existing pattern for reads/atlas/etc.).
- **`NAV_ICON_MAP`** entry added: `'intel2': 'nav-icon-intel2'`.

### Sections (sub-nav inside the tab)
| Section | Backend table(s) | What it shows |
|---|---|---|
| 💡 Strategic Insights | `strategic_insights` (532) | Derived cross-table insights grouped by `insight_type`, with `detail`/`metric`/`confidence`. |
| 🧬 Genetic Validation | `target_disease_assoc` (1,537) + `target_genetics` (117) | Open Targets target→disease ranked by `genetic_association_score`; gnomAD LoF intolerance (o/e). **Duplicate-name trap resolved:** uses the richer `target_disease_assoc` (1,537), NOT the thinner queried `target_disease_associations` (600). Documented inline in the subhead. |
| 🧪 Trial-Design Quality | `trial_design_quality` (1,398) | Trials by `quality_score`/`quality_tier`, randomized/controlled flags, enrollment, `why_stopped`. Links each `nct_id` to ClinicalTrials.gov. (Note: `quality_tier` includes values like `single_arm`/`high`; the tier-color helper falls back to a neutral pill for unrecognized values.) |
| 📊 Conference Signals | `conference_abstract_signals` (451) | Late-breaker flag, readout phase, `result_direction`, `signal_score`. **Trap resolved:** uses the derived *signal* table, not the raw `conference_abstracts` titles already shown elsewhere. |
| 🇪🇺 EU Approvals | `eu_approvals` (47) | EMA dates, MAH, biosimilar flag, EU-vs-US lag (days). |
| 🏭 Manufacturing | `manufacturing_sites` (51) | `is_supplies_candidate` BD list + all sites + in-house flag. |
| 🔗 Narrative Trust | `narrative_provenance` (4,137) + `narrative_claim_triangulation` (195) | **RELINKED** from the retired `changes-feed` tab. Per-narrative claim→source provenance + independence/triangulation counts. Same tables/key the live `homeprev` tab already reads, now given a standalone surface. |

All counts verified via REST `count=exact` on 2026-06-15.

---

## Security / convention compliance
- **Reads only via the existing anon/publishable key:** the IIFE uses the in-page `SUPABASE_URL` + `SUPABASE_ANON` constants (the publishable key, `sb_publishable_3GLfZ7b9Tjp9RFRcc4YZew_ov-fY7dI`). NO `service_role`/`sb_secret`/JWT key appears anywhere in the additions (only mention of "service_role" in the new code is a comment stating it is NOT used).
- **Additive:** no existing function modified/renamed; new tab registered via `registerTab`, never by editing `switchTab`.
- **Namespaced:** every new class/id uses `intel2-` / `tab-intel2` / `nav-icon-intel2`. Confirmed zero collisions via grep before editing.
- **Error-isolated:** loader wrapped in try/catch (renders an inline error message inside the tab on failure); `switchTab` already wraps `onEnter` in try/catch.
- **Pagination:** the two large narrative tables are read via a paginated `QALL()` helper (1000-row pages, hard cap 20k) so the default 1000-row limit can't silently truncate. The other tables are <1,537 rows and use a single capped page (`limit=1000`, ordered) — none exceed one page.

---

## Edit locations (line numbers in the edited `index.html`)
- **~5821** — visible nav icon button `nav-icon-intel2` (after the Reads icon).
- **~5840** — hidden `.tab-btn` for `intel2` (after the Reads hidden button).
- **~25760** — `NAV_ICON_MAP` entry `'intel2': 'nav-icon-intel2'`.
- **~31064–31135** — `<style>` (intel2- CSS) + `<div class="tab-pane" id="tab-intel2">` markup (inserted right after the retired `tab-changes-feed` pane).
- **~31137–31306** — the `<script>` IIFE (renderers, loader `intel2Init`, section nav, `registerTab('intel2', …)`).

---

## Validation results
- **`node --check`** on the extracted IIFE (`/tmp/intel2_check.js`, 168 lines): **PASS — zero syntax errors.**
- **ID/class collision check (grep before edit):** `intel2`, `nav-icon-intel2`, `tab-intel2`, `registerTab('intel2'` all had **0** prior occurrences; **1** of each after edit.
- **No service_role/secret key in additions:** grep confirms `sb_secret` = 0 file-wide; the only `service_role` string is the disclaiming comment; no hardcoded `sb_*` key in the intel2 block (uses `SUPABASE_ANON`).
- **DIV balance** of the new pane: 6 open / 6 close.
- **Schema/column validity:** every `select=` column list was live-tested against the REST API (service key, server-side only) and returned real rows — all columns exist. The anon-key RLS read path is proven by the existing live `homeprev` tab reading the same `narrative_provenance` / `narrative_claim_triangulation` tables with the same publishable key.
- **Pre-deploy manual check recommended:** open the tab in a browser, click through all 7 sub-sections, and confirm the network calls 200 (per the reorg plan's screenshot-review discipline).

---

## Deploy command (run once the GitHub token is restored)

git is broken on the mounted folder, so deploy `index.html` via the GitHub Contents API to `kyleklaassen-dev/bd-dashboard` (branch `main`). One-liner (uses the existing `.github_token`; recipe per `docs/archive/CLAUDE_full_2026-06-09.md`):

```bash
cd "/Users/.../BD Platform" && \
SHA=$(curl -s -H "Authorization: token $(cat .github_token)" \
  "https://api.github.com/repos/kyleklaassen-dev/bd-dashboard/contents/index.html?ref=main" | python3 -c "import sys,json;print(json.load(sys.stdin)['sha'])") && \
python3 -c "import base64,json,subprocess; \
body=json.dumps({'message':'Add 📡 Intelligence tab (intel2): surface hidden backend tables + relink narrative trust','content':base64.b64encode(open('index.html','rb').read()).decode(),'sha':'$SHA','branch':'main'}); \
open('/tmp/intel2_deploy.json','w').write(body)" && \
curl -s -X PUT -H "Authorization: token $(cat .github_token)" \
  -H "Content-Type: application/json" \
  --data @/tmp/intel2_deploy.json \
  "https://api.github.com/repos/kyleklaassen-dev/bd-dashboard/contents/index.html"
```

After PUT: GitHub Pages CDN has ~10-min TTL + build lag — verify via `raw.githubusercontent.com/kyleklaassen-dev/bd-dashboard/main/index.html` (grep for `nav-icon-intel2`) before assuming it's live.
