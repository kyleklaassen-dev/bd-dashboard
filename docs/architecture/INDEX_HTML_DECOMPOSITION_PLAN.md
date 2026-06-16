# index.html — Decomposition Plan

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
Move the IIFE/namespaced tail scripts (§(c) above) into individual files under `/src/` and
load them with classic `<script src>` tags **after** the core block, preserving order.
- Keep them **non-module** so any globals they expose stay global.
- Extract **one module per commit**; after each, open the live site and exercise that tab.
- Highest-value first (largest): Audit (~1,290 lines), Ontology Audit (~1,330), Ontology
  Explorer (~1,820). Lowest-risk first: Reads, Saved Views, Changes Feed (small, isolated).

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
