# index.html — Decomposition Plan

> ## ✅ STATUS 2026-06-18 — Stages 2, 3, 4 effectively DONE. index.html **34,847 → 7,124 lines (−79.6%)**.
> All JavaScript and all top-level CSS are externalized; index.html is now the HTML shell + `<script src>` /
> `<link>` tags + small inline glue. Extracted under `assets/`:
> - **JS (16 modules, `assets/js/`):** `core.js` (shared Supabase layer/globals) · `app.js` (loadData + all
>   rendering + BRIDGE template, 13.5k lines) · the 14 tab/feature modules (reads, home_preview, changes_feed,
>   saved_views, ontology_explorer, ontology_audit, audit, intel2, program_board, dkn, discovery_queue,
>   company_database, pi_toggle, pharma_intel).
> - **CSS (12 files, `assets/css/style_01..12.css`):** each `<style>` block → a `<link>` at the **same document
>   position** (exact cascade preservation, not concatenated).
> Every extraction was byte-identical relocation, verified via the Claude Code preview tools (HTTP 200 +
> tab render + globals/computed-styles intact + 0 console errors). Merged in PRs #6–#12.
> **Remaining (optional):** small inline glue scripts (10–50 lines each in the messy mid-file region) and the
> in-JS `<style>` string now inside `app.js` — low value, leave unless a reason arises.

> **Goal:** Make the 4.4 MB monolithic `index.html` smaller and more maintainable
> **without breaking the live GitHub Pages site.** Staged by risk; the safest, highest-value
> step (image extraction) is **already done** (see §3 / Stage 0).
>
> **Companion:** `INDEX_HTML_MAP.md` (the navigable structure map). Read it first.
> **Serving model:** GitHub Pages project page, base path `/bd-dashboard/`, `.nojekyll` present,
> no build step. The file is hand-edited and PUT via the GitHub Contents API.

---

## Feasibility assessment (the three questions)

### (a) Is the CSS one contiguous `<style>` block? → **NO. Fragmented. DO NOT extract.**
There are **13 real `<style>` blocks** (plus one CSS string literal *inside* JavaScript at
lines 23601–23619). The main stylesheet (lines 67–2651) is large but is followed by 12 more
per-tab/per-component blocks scattered across the file (see Map §2). Extracting CSS would
require concatenating 13 sources, preserving cascade order, and re-testing every tab's
styling — which **cannot be verified headlessly** and risks visual regressions. **Deferred to
a supervised session.** (If ever attempted: concatenate in document order into `styles.css`,
`<link>` it in `<head>`, and visually diff every tab against the live site before/after.)

### (b) Large embedded base64 data-URIs? → **YES, and they have been extracted. ✅**
26 base64 JPEGs (Industry-Insights tab) totaled **~1.89 MB = 44 % of the file**. They were
static `<img src="data:…">` tags — the lowest-risk possible target. **Done in Stage 0 below.**

### (c) Which `<script>` blocks are self-contained vs interdependent?
- **Interdependent / shared core (DO NOT move yet):** `<script>` #1 (lines 2986–5420). This
  defines the global namespace everything relies on — `_sb`, `SUPABASE_URL`, `SUPABASE_ANON`,
  `switchTab`/`switchTabTo`, `TAB_REGISTRY`, `registerTab`, `TAB_AREA(_MAP)`, and ~430 global
  `loadX()` functions called from inline `onclick=` handlers throughout the static HTML.
- **Mostly self-contained / namespaced (eventual extraction candidates):** the tail modules —
  Ontology Explorer IIFE (`#oex-main-script`, 28927–30743), `intel2` (31141–31395),
  Program Board (31398–31549), Ontology Audit (31551–32878), Audit (32883–34173),
  Saved Views (34189–34303), Changes Feed (34305–34602), Home Preview (34604–34751),
  Reads (34754–34844). These are IIFE-wrapped / namespaced and registered through
  `TAB_REGISTRY`, so each fails in isolation.
- **The blocker for JS extraction:** hundreds of inline `onclick="globalFn(...)"` handlers in
  the static markup bind to functions in the global scope. Moving JS to an external file is
  fine *as long as it is a classic `<script src>` (not `type=module`)* so globals stay global —
  but verifying that *every* handler still resolves requires running the page, which is **not
  safe to do headless**. **Deferred to a supervised session.**

---

## Stage 0 — Extract embedded images  ✅ DONE (2026-06-15)

**What:** Moved all 26 Industry-Insights JPEGs out of the HTML into `/assets/ii-01.jpg …
ii-26.jpg` and replaced each `data:image/jpeg;base64,…` with `src="assets/ii-NN.jpg"`.

**Why it was safe:**
- Each was a static `<div class="ii-img"><img src="data:…">` tag (no JS/CSS dependency).
- **Byte-level integrity proof:** the new HTML + the extracted files reconstruct the original
  file *byte-for-byte* — the only change is where the image bytes live.
- Relative path `assets/ii-NN.jpg` resolves to `/bd-dashboard/assets/ii-NN.jpg` on Pages
  (index.html is at repo root), matching the upload location.

**Procedure used (the safe-deploy recipe — reuse for any future edit):**
1. Backed up the live file (`index_s3.bak`, sha `601b6db6`).
2. Uploaded all 26 asset files **first**; verified each returns HTTP 200 + valid JPEG magic
   bytes on `raw.githubusercontent`.
3. Re-fetched index.html sha to confirm no concurrent edit, then PUT the new index.html.
4. Verified the deployed file: size 2,488,075 B, well-formed (`<!DOCTYPE>`…`</html>`),
   markers present (`tab-intel2`, `tab-industry-insights`, `SUPABASE_ANON`, `switchTab`,
   `registerTab`×25), 0 base64 data-URIs, 26 `assets/ii-` refs, byte-identical to intended.

**Result:** **4,421,381 B → 2,488,075 B (−1.89 MB, −43.7 %)**, no behavior change.

> ⚠️ **Caveat:** verification was headless (file integrity + asset reachability + well-formedness).
> The image *rendering* could not be visually confirmed. A human should glance at the
> Industry Insights tab on the live site to confirm thumbnails display. Rollback = restore
> `index_s3.bak` (the pre-change 4.4 MB file) via Contents API PUT with the then-current sha.

---

## Stage 1 — (Optional, low risk) move CDN libs / add caching headers
No code change required; documented for completeness. The three CDN deps (gridjs CSS+JS,
supabase-js) are already external. No action recommended.

## Stage 2 — Extract the tail self-contained modules (MEDIUM risk · supervised)
Move the IIFE/namespaced tail scripts (§(c) above) into individual files under `assets/js/`
(same root-relative scheme as the Stage-0 images; resolves to `/bd-dashboard/assets/js/…` on
Pages) and load them with classic `<script src>` tags **after** the core block, preserving order.
- Keep them **non-module** so any globals they expose stay global.
- Extract **one module per commit**; after each, open the live site and exercise that tab.
- Highest-value first (largest): Audit (~1,290 lines), Ontology Audit (~1,330), Ontology
  Explorer (~1,820). Lowest-risk first: Reads, Saved Views, Changes Feed (small, isolated).

### ✅ Refreshed tail-module map (current line numbers, 2026-06-17)
The original Map line numbers had drifted. Verified `<script>…</script>` spans in the tail
(all inline, no `src=`), with the `registerTab` id each one owns:

| Module | Lines (current) | Size | registerTab id |
|---|---|---|---|
| Ontology Explorer (`#oex-main-script`) | 28927–30743 | 1,817 | (IIFE; registered elsewhere) |
| intel2 (📡 Intelligence) | 31141–31395 | 255 | `intel2` |
| Program Board | 31398–31549 | 152 | (registers `program-board`) |
| Ontology Audit | 31551–32878 | 1,328 | `ontology` |
| Audit | 32883–34173 | 1,291 | (registers `audit`) |
| ~~Saved Views~~ | ~~34189–34303~~ | ~~115~~ | ✅ **EXTRACTED 2026-06-18 → `assets/js/saved_views.js`** |
| ~~Changes Feed~~ | ~~34305–34602~~ | ~~298~~ | ✅ **EXTRACTED 2026-06-18 → `assets/js/changes_feed.js`** |
| ~~Home Preview~~ | ~~34604–34751~~ | ~~148~~ | ✅ **EXTRACTED 2026-06-18 → `assets/js/home_preview.js`** |
| ~~Reads~~ | ~~34754–34844~~ | ~~91~~ | ✅ **EXTRACTED 2026-06-18 → `assets/js/reads.js`** |

> **Stage-2 progress (2026-06-18):** the 4 small tail modules (Reads, Home Preview, Changes Feed,
> Saved Views) are all extracted to `assets/js/*.js` — index.html **34,847 → 34,199 lines** (−648).
> Each verified via the preview loop (byte-integrity reconstruction + `node --check` + HTTP 200 +
> tab renders + exposed globals defined + 0 console errors). **Next Stage-2 targets** (larger,
> still IIFE/registered — re-grep boundaries first): Audit (`audit`, ~1,291), Ontology Audit
> (`ontology`, ~1,328), Ontology Explorer (~1,817), Program Board, intel2. CSS (Stage 3) and the
> shared core script #1 (Stage 4, HIGHEST risk) remain after the tab modules.

> **Line-map note:** after the Reads extraction the file is **34,757 lines** (was 34,847); the Reads
> block is now the one-line `<script src="assets/js/reads.js"></script>` at **line 34754**. The rows
> above (Ontology Explorer … Home Preview) are unaffected — Reads was the file's last script. Re-grep
> before the next Stage-2 target (suggested next: **Home Preview** 34604–34751, or **Changes Feed**).

### Ready-to-run recipe — first extraction: **Reads** (lines 34754–34844) ✅ DONE
This recipe was executed and verified on 2026-06-18 (see the Headless-verification update below).
Validated as the safest possible JS target: fully `(function(){…})()` IIFE; reads `SUPABASE_URL`/
`SUPABASE_ANON`/`registerTab` only through `typeof`-guarded fallbacks; exposes only `window.__readsFilter`
/`window.__readsRender` (created at runtime, referenced by its own rendered HTML — not by static markup);
it is the **last `<script>` in the file**, so load order is trivially preserved. Blast radius = the Reads
tab only (a load failure can't touch the other 24 tabs).

Steps (supervised, follows the Safe-deploy invariant below):
1. Copy the IIFE body (lines 34755–34843, i.e. everything **between** the `<script>`/`</script>` tags)
   verbatim into `assets/js/reads.js`. `node --check assets/js/reads.js` must pass.
2. Replace index.html lines 34754–34844 with a single line: `<script src="assets/js/reads.js"></script>`.
3. **Byte-integrity proof:** reads.js + the new one-line tag must reconstruct the original block
   (the only change is where the bytes live — same proof the Stage-0 image extraction used).
4. Commit reads.js + index.html together (one atomic change → GitHub Pages deploys both at once, so
   the `<script src>` never references a not-yet-deployed file). For a manual API deploy, upload
   `assets/js/reads.js` **first** (verify HTTP 200 on raw), then PUT index.html.
5. **Browser-verify:** load the dashboard, open the Reads tab, confirm cards render and the
   category/target filter chips work; check the console for new errors.
6. Rollback = restore the pre-change index.html (the inline version is self-contained).

> **✅ Headless-verification finding UPDATED (2026-06-18) — it CAN be done headless now.** The
> 2026-06-17 note below was wrong-in-hindsight (it concluded the 2.5 MB dashboard "could not reliably
> load" in headless preview). With the Claude Code **preview tools** (`preview_start` on the
> `dashboard-static` launch config + `preview_eval`/`preview_console_logs`/`preview_network`), the
> full dashboard loads to `readyState:complete` and the Reads IIFE executes. The Reads extraction was
> verified end-to-end this way: byte-integrity reconstruction PASS, `node --check` OK, `reads.js`
> served HTTP 200, the Reads panel rendered **byte-identically** (same checksum before/after), the
> populated tab showed "13 reads" with working CATEGORY/TARGET filter chips (filter→14.7k chars,
> reset→restored exactly), and **zero console errors**. **Implication for future Stage-2 targets:**
> this verification loop is repeatable and no longer needs a human in the loop for the render check —
> extract, `preview_eval` a before/after checksum of the tab panel + a filter round-trip, confirm no
> new console errors. (A human glance at the deployed site is still nice-to-have, not a gate.)
>
> > _Original 2026-06-17 finding (kept for the record, now superseded): a local static server +
> > headless preview "could not reliably load the 2.5 MB dashboard" (landed on a chrome-error page)._

## Stage 3 — Extract the CSS (HIGHER risk · supervised, only if desired)
Only after a human is watching. Concatenate the 13 `<style>` blocks **in document order**
into `styles.css`, `<link>` from `<head>`, leave the in-JS `<style>` string (23601) in place.
Visually diff **every** tab before/after. Abort on any visual difference.

## Stage 4 — Extract the shared core (`<script>` #1) (HIGHEST risk · supervised, last)
Only after Stages 2–3 are stable. Move 2986–5420 to `/src/core.js` as a classic script loaded
right after supabase-js. The risk is the hundreds of inline `onclick` handlers — every one must
still resolve. Requires full click-through QA on the live site. **Do not attempt unattended.**

---

## Safe-deploy invariant (applies to all stages)
1. Back up the current live file before any PUT.
2. Upload dependencies (assets/js/css) **before** the file that references them.
3. Re-fetch sha immediately before the PUT (abort if it changed → concurrent edit).
4. After PUT, verify on `raw`/Contents-API-raw: size delta as expected, well-formed,
   key markers present, byte-identical to intended.
5. If verification is at all off → **restore the backup immediately.**
