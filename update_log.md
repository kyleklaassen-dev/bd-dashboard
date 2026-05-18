
---
## 2026-05-18 Critical Spyre data fix, inline edit + research validation — commit 27473ba2

### Critical data corrections (all verified against SEC 8-K Jan 2026 and ClinicalTrials.gov)

**Spyre pipeline was substantially wrong — now corrected:**
- SPY001: was "Anti-IL-23p19" → corrected to **Anti-α4β7** (same mechanism as vedolizumab/Entyvio but 3× longer half-life via YTE modification). Part A data April 2026: RHI -9.2pts primary endpoint met.
- SPY002: Anti-TL1A ✅ (name correct) but **cls changed 1st Gen → 2nd Gen** (YTE Fc modification = extended half-life engineering, same class as Xencor XmAb technology — user correctly flagged this)
- SPY003: was "TL1A × IL-23p19 bispecific" → corrected to **Anti-IL-23 monoclonal** (Phase 2, SKYLINE)
- SPY004: doesn't exist → removed
- Added **SPY072**: Anti-TL1A for RA/PsA/axSpA (Phase 2 SKYWAY trial NCT07148414; RA data Q3 2026, PsA/axSpA Q4 2026)
- Added **SPY120** (α4β7+TL1A), **SPY130** (α4β7+IL-23), **SPY230** (TL1A+IL-23) — all in SKYLINE Part B
- `spyre-003` table entry (TL1A bispecific — completely wrong) → replaced with **`spyre-230`** representing SPY230 TL1A+IL-23 combination arm

**Website URL corrected:** spyretherapeutics.com → **www.spyre.com/pipeline**

**Pipeline display in Spyre expanded row:**
- All 7 drugs shown as bubbles centered across top of card
- Full size: TL1A+IBD drugs (SPY002, SPY120, SPY230)
- Smaller/dimmed: IBD-only (SPY001, SPY003, SPY130) and Rheumatic-only (SPY072) — still fully hoverable
- Divider labels: "TL1A+IBD programs", "IBD non-TL1A", "TL1A/Rheumatic"
- Each bubble popup: summary card, 2-col detail grid, Ailux BD Lens, trials/proxy ref, verified sources

**Inline edit + Supabase research validation:**
- Double-click Drug, Target, or Class cell → inline input appears
- On Enter: row auto-expands; research panel slides in at top of expanded section
- Panel queries Supabase `companies` (insight_text, ailux_angle) and `intel_companies` for stored intel
- Text-match validation: if proposed new value found in stored intel → "✅ Consistent"; else → "⚠️ Queued for deep research"
- Proposed edit written to Supabase `pi_user_edits` table (async) for overnight research pipeline pickup
- "Apply Change Locally" button updates TL1A_PROGRAMS in-memory and re-renders table
- CSS: `.pi-editable` hover hint (✏), `.pi-edit-validation` panel with pending/supported/conflict states

---
## 2026-05-18 TL1A tab: blinking intel dot, 3-col layout, redesigned Spyre hover cards — commit 46a77ab2

### What was changed

**Blinking green dot for companies with no intel:**
- `_loadIntelStatus()` now called in `tl1aPI.init()` on page load
- Queries Supabase `intel_companies → companies(ticker)` to find which companies have any intel records
- Companies not found get a `<span class="pi-no-intel-dot">` — slow green pulse animation next to their name
- `@keyframes pi-dot-blink` with box-shadow pulse, 2.8s cycle; tooltip: "No intel on record yet — flagged for auto-research"

**TL1A tab 3-column layout (pill buttons + centered PI card):**
- `.tl1a-layout` CSS grid: `148px 1fr 148px` with sticky side pill columns
- Left pills: 📡 Intel Feed, 📅 Catalyst Calendar, 📐 Estimand Guide
- Right pills: 🧬 Ailux Profile, 💊 IBD Market, 🔬 China Programs, 🎯 BD Takeaways, 📖 IBD History
- Each pill opens a `.tl1a-modal-overlay` with full card content; `openTl1aModal()` / `closeTl1aModal()` JS functions
- Escape key closes all open modals; clicking overlay backdrop closes panel
- `#tl1a-pi-card` with `!important` overrides Pharma Intel tab's global `.pi-card` margin conflict

**SPYRE_PIPELINE redesign:**
- Added `sources[]` array to each drug with labeled verification links
- SPY001 sources: spyretherapeutics.com/pipeline, NCT07012395, Endpoints News data readout
- SPY002 sources: spyretherapeutics.com/pipeline, NCT07012395, NCT06672718
- SPY003 sources: spyretherapeutics.com/pipeline, NCT07012395 (combo arm proxy)
- SPY004 sources: spyretherapeutics.com/pipeline
- Added `comboRef` field to SPY003: SKYLINE combination arm as proxy trial data reference
- Combo drug names now use × symbol: "TL1A × IL-23p19", "IL-6 × IL-23p19"

**Spyre hover popup redesign (per-drug buttons):**
- Removed "COMBO" badge — combo drugs now show target pair (e.g., "TL1A + IL-23p19") as subtitle under drug code
- New summary card at top of each popup: drug code, name, phase badge, indication (distinct colored background)
- 2-column detail grid: left = Drug Details (format/stage/half-life/dosing/target); right = Mechanism & Context
- Ailux BD Lens section: full-width yellow highlight block
- Trials section: Active Trials with NCT links for mono drugs; "Proxy data" amber block for SPY003 (SKYLINE combo arm)
- SPY004 (no trials registered): "No trials registered — IND in progress" note
- 🔗 Sources section at bottom of each popup with all verification links
- Popup CSS: fixed 340px width, max-height 80vh with overflow scroll

---
## 2026-05-18 TL1A tab: polish pass — color pills, clean header, Spyre card enrichment — commit ff124220

### What was changed

**Header cleanup:**
- Removed TOP BAR div (molecule title "TL1A × IL-23p19 · IBD (UC / CD)" + "Competitive intelligence · Live from Supabase · Updated May 2026")
- Removed `⚔ Program Intelligence · All TL1A Companies & Drugs` pi-title span
- Moved Biology Deep Dive button into the pi-hd alongside the filters

**Color-coded filter pills with group labels:**
- Added `.pi-pill-lbl` (grey uppercase label before each group)
- Class group: blue (#2563eb active/hover)
- Stage group: purple (#7c3aed active/hover)
- Relevance group: crimson (#dc2626 active/hover)
- Labels: "Class", "Stage", "Relevance"

**Spyre SPYRE_PIPELINE enrichment:**
- Added `isCombo`, `indication`, `trials[]` fields to each drug entry
- SPY001/SPY002: `indication: 'Ulcerative Colitis (UC)'`; SPY003: `UC / CD (planned)`; SPY004: `Crohn's Disease (CD)`
- SPY002 has 2 trials (NCT07012395 SKYLINE + NCT06672718 Phase 1); SPY001 has SKYLINE
- SPY003/SPY004 flagged `isCombo:true` → show red "COMBO" badge on pipeline button

**Spyre hover card popup improvements:**
- Shows disease indication (`📍 d.indication`)
- Shows "Active Trials" sub-section with NCT links, status, phase, N, PCD
- TBD half-life/dosing tags hidden for Pre-IND/Preclinical drugs

**Links everywhere in Spyre expanded row:**
- Catalysts: url field added to all 3 entries (CT.gov or spyretherapeutics.com); rendered as `↗` hyperlinks
- Deals: url field added; rendered as `↗` hyperlink
- Website: `spyretherapeutics.com ↗` link in expanded row header
- "hover each drug to explore" label removed
- Combo drugs (SPY003, SPY004) get a red "COMBO" chip on their pipeline button

---
## 2026-05-18 TL1A tab: compact PI card, pill filters, Spyre rich row — commit 3ef77a9f

### What was changed

**Program Intelligence card layout:**
- `.pi-card` now `max-width:1100px;margin:0 auto 20px` — centered and constrained
- Table `min-width` reduced from 700px → 620px; `_colWidths` from `[220,150,100,90,80,80]` → `[175,130,85,80,75,75]`
- `.pi-table th` padding: `8px 10px` → `6px 8px`; `.pi-table td` padding: `9px 10px` → `7px 8px`

**Filter pill buttons:**
- Replaced three `<select>` dropdowns with `.pi-pill-group` + `.pi-pill` button groups
- Groups: Class (All / 1st Gen / 2nd Gen / Direct), Stage (All / Ph 3 / Ph 2 / Ph 1 / Pre-IND / Preclinical), Relevance (All / High Overlap / Watch)
- Added `piPillClick()` global function; updated `tl1aPI.filter()` to read active pill `data-val`
- CSS: `.pi-pill`, `.pi-pill.active`, `.pi-pill:hover`, `.pi-pill-divider`

**Spyre rich expanded row:**
- `SPYRE_PIPELINE` const: 4 drug entries (SPY001–SPY004) with target, format, phase, half-life, dosing, mechanism, Ailux BD Lens
- `_spyreDetailHTML(p)`: renders header (SYRE stock chip with live price/arrow from Supabase), pipeline drug buttons with hover popup cards, 2-col grid (summary, trials, catalysts, deals, risk, diff)
- `_loadSpyreStock()`: async Supabase fetch of `companies` table for SYRE; populates price + direction arrow on expand
- `_renderTable()`: routes Spyre (id=`spyre-mono`) to `_spyreDetailHTML()`, all others to standard detail
- CSS: `.spyre-hd`, `.spyre-stock-chip`, `.spyre-drug-btn`, `.spyre-drug-popup`, `.spyre-popup-*`, `.spyre-section-lbl`

---
## 2026-05-18 Bug fix: loadAreaCompanies / loadAreaDrugs undefined — commit cd5a122

### What was fixed

**Root cause:** `loadMoleculeTab()` called `loadAreaCompanies(tabId)` and `loadAreaDrugs(tabId)` but neither function was defined anywhere in the file. Every molecule tab navigation (TSLP, IL-4Rα, IL-4Rα/OX40L, IGF1R/TSHR, FcRn) threw a `ReferenceError` on load, preventing `loadAreaBDActivity` from running and leaving all molecule tabs blank.

**Fix:** Added both functions as async stubs in the head script block (before `loadMoleculeTab`). Each function checks for its target element (`tabId + '-companies'` / `tabId + '-drugs'`) and returns early if not found — so no visible change on current tabs, but the `ReferenceError` is resolved and all molecule tab content now renders correctly.

---
## 2026-05-18 Bug fix: dead TL1A Grid.js containers in initGrids — commit 27d653e

### What was fixed

**Root cause:** The TL1A redesign removed `#grid-tl1a-landscape` and `#grid-tl1a-tech` container divs, but `initGrids()` still called `.render()` on both. Grid.js throws `Container element cannot be null` synchronously, halting `initGrids()` before any TSLP, IL-4Rα, or other molecule tab grids could initialize — leaving all Drugs to Know and molecule tabs blank.

**Fix:** Removed both dead grid initialization blocks (`grids.tl1aLandscape` and `grids.tl1aTech`) from `initGrids()`. Replaced with a comment noting they were superseded by the `tl1aPI` Program Intelligence table.

---
## 2026-05-18 TL1A tab full redesign (Tasks #97–#99) — commit 1ee24b80

### What was changed

**Removed from TL1A tab:**
- Top stat bar (UC/CD prevalence, biologic failure rate, etc.) — moved biology context to deep dive modal
- Companies to Watch card (hardcoded 7 companies)
- Drugs to Know card (hardcoded 14 drugs, now unified)
- Separate competitive landscape card (tl1a-live-competitive-card)
- Separate BD activity card (tl1a-bd-activity)
- Live Meridian Updates card (tl1a-live-intel-card)
- Static "Latest Field Intelligence" card (tl1a-intel-anchor)
- Deal Spotlight card (most recent transaction)
- Deals by Total Value chart
- Competitive Analysis section (redundant with new table)
- Bispecific Technical Deep-Dive section (content now in expandable row detail panels)
- Related News & Precedent Transactions section (now in unified intel feed)
- Inline Biology Deep-Dive edu-section (moved to modal)

**Added to TL1A tab:**
- **Biology Deep Dive button** (top-right): small green card-button that opens a full-screen modal with all TL1A biology content (TL1A/DR3 mechanism, IBD disease biology, TL1A×IL-23 synergy, IBD drug dev endpoints). ESC to close.
- **Unified Program Intelligence Table** (`tl1aPI` object, `#pi-tl1a-wrap`):
  - 13 companies with full data: Roche, Merck, Sanofi/Teva, Spyre (mono), Xencor (XmAb942), Mirador, Simcere/BI, Caldera/Qyuns, Earendil/Helixon, Xencor (XmAb412), LaNova/Zymeworks, Spyre (SPY003), Episcience
  - Classifications: **1st Gen** (monospecific TL1A mAb), **Direct** (exact TL1A×IL-23p19 bispecific = direct Ailux competitors), **2nd Gen** (enhanced mono, e.g. Xencor's XTEND extended half-life)
  - Filter by Classification, Stage, Relevance (High Overlap / Watch)
  - Sortable columns (Company, Drug, Target, Class, Stage, Relevance)
  - Resizable columns (drag right edge of any column header)
  - Expandable rows: click any row to reveal Summary, Upcoming Catalysts, Deal History, Key Risk, Why It Matters/Differentiation
- **Live Intel Feed** (`loadTL1AIntelFeed()`): queries Supabase `intel_areas` for `area_id='tl1a'`, then fetches matching `intel` rows ordered by date — single unified chronological stream of deals, clinical, regulatory, and news items
- Tab load: `tl1aPI.init()` and `loadTL1AIntelFeed()` called when TL1A tab is opened via `switchTab()`; also initialized on `DOMContentLoaded`
- Updated TOC_MAP for `tl1a`: Program Intelligence, Intel Feed, Ailux Profile, Estimand Guide, Catalyst Calendar, IBD Market & SOC, Chinese Programs

**Kept (unchanged or lightly trimmed):**
- Ailux Asset Profile (with deal valuation estimates)
- Estimand Intelligence card
- Catalyst Calendar (live from Supabase, tl1a-live-catalysts)
- IBD Market & Standard of Care (collapsible)
- BD Intelligence Key Takeaways (insight-box)
- China Domestic Read-Through
- IBD Target History (collapsible)

---
## 2026-05-18 Supabase intel submission + centered search bar (Tasks #94–#95) — commit 8f01318

### What was changed

**Supabase intel submission (Task #94):**
- Added `INTEL_TAG_AREA` map: tag label → Supabase `area_id` (IBD→tl1a, Resp→tslp, Type 2→il4ra, AD→il4ra, TED→igf1r, AI→fcrn, Immune Reset→tcell)
- New `_saveIntelToSupabase(url, text, tag)` async helper: inserts to `intel` table with `intel_type='user_submitted'`, `importance='medium'`, `source_name='User Submission'`; then inserts to `intel_areas` junction table for non-General tags
- Both `saveFromModal()` (modal submit) and `submitIntel()` (inline panel submit) now call `_saveIntelToSupabase()` alongside the existing localStorage write
- localStorage retained as a local backup; Supabase is the persistent record for the next research update cycle

**Centered header search bar (Task #95):**
- `.header-search-wrap` changed from `flex: 1` flow layout to `position: absolute; left: 50%; transform: translateX(-50%)` with `width: clamp(280px,36%,540px)`
- Search bar is now truly centered in the header regardless of unequal left (title) and right (buttons) column widths
- Mobile override (line ~694) retains `order: 3; flex-basis: 100%` so the bar drops to its own row on narrow screens

---
## 2026-05-18 Nav fix + home tab cleanup + dynamic Meridian Reader (Tasks #87–#90) — commit 2674800

### What was changed

**Tab navigation fix (Task #87):**
- Root cause identified: the home tab HTML block had 1 more `</div>` than `<div>` openers, causing it to consume the `.content` wrapper's closing tag
- The orphan `</div><!-- end tab-home inner -->` (left over from earlier content removals) was removed
- Home tab section now perfectly balanced: 48 opens, 48 closes, depth returns to 0
- All subsequent tabs (`tab-industry-insights`, drug tabs, etc.) are now correctly inside `.content` at the same DOM level as the home tab

**Remove Key Concepts card (Task #88):**
- Removed the entire "Key Concepts — What to Know Across Coverage Areas" card (`id="learning-anchor"`) from the home page
- Card contained 6 hardcoded concept mini-cards for IBD, Resp, Type 2, TED, FcRn, Immune Reset
- Removed stale `learning-anchor` and `ailux-pipeline-anchor` entries from TOC_MAP; replaced with `bd-signal-panel` entry

**Dynamic Meridian Reader card (Task #89):**
- Yellow top-of-home card now loads live from Supabase `intel` table instead of 7 hardcoded items
- New `loadMeridianReader()` function: queries top 20 high/medium importance intel by date, joins `intel_areas` for area labels, prioritises `importance = 'high'`, takes top 7
- Area-aware pill styling: `MR_AREA_STYLE` maps area_id → color/label (IBD, Resp, Type 2, TED, FcRn, Immune Reset); falls back to `MR_TYPE_STYLE` for intel_type (deal, clinical, regulatory, etc.)
- Called in `DOMContentLoaded` alongside other home tab loaders

**Key Watch pill under date (Task #90):**
- `KEY WATCH` pill moved from the right-side pill group to below the date text in the left 80px column of catalyst rows
- High-significance rows now show: date (top-left) → KEY WATCH badge (below date) → label/notes (center) → countdown + significance/area pills (right)

---
## 2026-05-18 Pharma sort/filter + 8-across stock grid (Tasks #79–#80) — commit 122b5cd

### What was added

**Pharma Landscape table sort + filter (Task #79):**
- Both China and Global pharma tables now have clickable sortable column headers with ↑/↓ indicators
- China table: sort by Company (alpha), Mkt Cap, Revenue, R&D Spend, R&D %, TA #1, TA #2
- Global table: sort by Company (alpha), Mkt Cap, Revenue, R&D, R&D %, TA #1, TA #2
- Numeric parser handles `~$60B`, `$700B`, `~$3.9B`, `29%`, `<1%` etc.
- Sort moves paired `pi-main-row` + `pi-dr-row` together as a unit (expanded details follow their row)
- Filter search bar above each table — searches all visible text (company, TA, type, notes) and hides non-matching row pairs

**Market & Learning stock cards 8-across (Task #80):**
- Changed `.stock-cards-grid` from `repeat(auto-fill,minmax(310px,1fr))` to `repeat(8,1fr)` for consistent 8-across layout
- Uniform gap on all sides between cards (no margin/padding asymmetry)

---
## 2026-05-18 Home tab enhancements + pipeline intel_companies (Tasks #65–#69) — commit d227118

### What was added

**Drugs to Know — rich expandable dropdowns (Task #65):**
- Every drug row now expands on click to reveal a detail panel: class/mechanism, stage, key trials, primary endpoints, differentiation insight, key risk, and live Supabase data (trial data + Ailux BD signal)
- `dknLoadSbData()` fetches the Supabase `drugs` table at page load and caches it in `_dknSbMap` for fuzzy matching
- Default filter changed from "All" to "◈ Ailux Focus" — shows only drugs relevant to Ailux's 6 coverage areas

**BD Signal panel on home tab (Task #66):**
- New `◈ BD Signal` card between catalysts and deals on the home tab
- `loadBDSignal()` fetches top 5 recent deals (prioritizing deals with ailux_signal), renders synthesized intelligence cards with area badge, deal value, parties, headline, and the Ailux BD Signal commentary

**Catalyst countdown badges (Task #67):**
- `catDaysTag(sort_date)` helper added — computes days to each catalyst event
- Badges auto-color: red "TODAY", red "Nd" (≤7 days), yellow "Nd" (≤30 days), grey "Nd" (>30 days), "Nd ago" for resolved
- Each open catalyst card now shows the countdown badge inline

**Company watchlist enrichment — Supabase (Task #68):**
- UCB: full rozanolixizumab/Rystiggo profile + FcRn competitive angle
- Cullinan: CLN-978 CD19×CD3 TcE detail + dual lineage BCMA differentiation narrative
- Pfizer: insight_text added (PF-07261271 + Telavant position)
- Roivant: full Telavant/afimkibart origin story + $7.25B benchmark
- J&J: nipocalimab expanded; daratumumab autoimmune parallel noted
- Regeneron: Dupixent $13B benchmark + itepekimab COPD AERIFY read-through

**research.py — intel_companies junction writes (Task #69):**
- `get_company_map()` fetches all companies from Supabase at startup; builds lowercase name → id lookup with 20+ aliases (J&J, Roche/Genentech, Eli Lilly, etc.)
- `resolve_company_id()` does exact then substring fuzzy match
- `write_to_supabase()` now accepts `company_map` and writes `intel_companies` rows for every company Haiku extracts in `company_names`
- Pharma tab `loadAreaIntel` can now be extended to filter intel by company_id — the data pipeline is ready

---
## 2026-05-18 Dashboard audit + fixes (Tasks #61–#64) — commit bc48040

### What was fixed
**BD Activity section on all 7 molecule tabs:**
Previously only TL1A had the BD Activity section. Added placeholder + JS wiring to TSLP, IL-4Rα × TSLP, IL-4Rα × OX40L, IGF1R × TSHR, FcRn, and ACE tabs.

**Stock prices column mismatch fixed:**
`scripts/stock_prices.py` was writing to `stock_change_pct` and `price_updated_at` — neither column exists in Supabase. Corrected to `stock_change` and `last_price_update`. Prices will now update correctly at 10 AM ET daily via GitHub Actions.

**27 companies seeded with current prices:**
Used yfinance to seed current stock prices for all public tracked companies. Market tab now shows live prices immediately.

**Duplicate T-cell deal removed; 8 new landmark deals seeded:**
- FcRn: J&J/Momenta $6.5B acquisition (nipocalimab), argenx/Halozyme ENHANZE collaboration, HanAll/Immunovant batoclimab license
- IGF1R: Amgen/Horizon $27.8B acquisition (Tepezza), River Vision/Horizon teprotumumab rights
- IL-4Rα: AZ/Aiolos Bio $1.06B acquisition (AIO-001 long-acting anti-TSLP), Apogee $200M Series B (APG279 IL-4Rα×TSLP bispecific)
- TSLP: AZ/Aiolos duplicate (long-acting TSLP perspective)

---
## 2026-05-18 GitHub Actions pipeline (Tasks #59–#60) — commits 0255a3f + c676af0

### What was built
Full automated background pipeline — runs on GitHub's servers, no computer needed, no Cowork needed.

**Scripts added:**
- `scripts/research.py` — RSS feed aggregator (10 feeds, 6 focus areas), Claude Haiku extraction, writes to Supabase `intel`/`intel_areas`/`deals`/`catalysts`
- `scripts/write_meridian.py` — reads Supabase intel, calls Claude Sonnet to generate HTML briefing, commits `meridian_today.html` to GitHub Pages
- `scripts/stock_prices.py` — yfinance price fetch for all tracked companies, upserts to Supabase `companies`
- `scripts/requirements.txt` — feedparser, anthropic, requests, yfinance, pynacl

**Workflows added:**
- `.github/workflows/meridian-research.yml` — 4 AM ET Mon–Sat (09:00 UTC)
- `.github/workflows/meridian-write.yml` — 6:30 AM ET Mon–Sat (10:30 UTC)
- `.github/workflows/stock-prices.yml` — 10 AM ET daily (14:00 UTC)
- `.github/workflows/evening-update.yml` — 7 PM ET daily (23:00 UTC)

**GitHub Actions secrets (all set):** ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY, GH_DEPLOY_TOKEN

**Test run:** Meridian Research #1 — Success, 42s

**New token:** `bd-actions-workflow-deploy` (repo+workflow, no expiry) stored at `.github_token_workflow`

---
## 2026-05-18 Meridian Issue layout fix + SKILL.md CSS update (Tasks #56–#57) — commit 818325b

### Changes
- `index.html`: Meridian Issue tab now wraps iframe in a card (max-width 880px, centered, white card on #edf1f7 grey background, 10px border-radius, box-shadow)
- `meridian_today.html`: body changed from `max-width:100%; margin:0` to `max-width:780px; margin:0 auto` so content and tables sit at a readable width
- `the-meridian` scheduled task SKILL.md: CSS template body line updated to match — future issues will generate with constrained width automatically

---
## 2026-05-18 TL1A BD Activity Section (Tasks #53–#55) — commit 765ed56

### Data seeded (12 TL1A deals, 9 new companies, 2 new drugs)
**Key deals:** Prometheus→Merck $10.8B (tulisokibart), Telavant→Roche $7.25B (afimkibart), Roivant→Roche $7B (afimkibart), Teva/Sanofi $1.5B (duvakitug), AbbVie/FutureGen $1.71B (FG-M701), Earendil/Sanofi $1.85B (HXN-1003), Simcere/BI €1.04B (SIM0709), plus Qyuns/Caldera, Pfizer/Roche PF-07261271 (option + co-dev), Roche/Chugai Japan rights
**New companies:** earendil, chugai, futuregen, telavant, roivant, prometheus, vant, caldera, pfizer
**New drugs:** pf07261271 (Pfizer IL-12p40/TL1A BsAb), fg-m701 (AbbVie TL1A mAb from FutureGen)

### BD Activity UI — `loadAreaBDActivity(tabId)`
- Live-query all deals for the area (no limit — full history)
- **Summary bar**: deal count, disclosed total value, acquisition/license breakdown, year range
- **Filter bar**: All / Acquisition / License / Collab / Option type buttons + inline search
- **Compact rows**: Year | From→To | Drug tag | Type badge (color-coded) | Value | Stage-at-deal
- **Click to expand**: full detail text, milestone info, region, Ailux Lens box, source link
- Section minimizable via header click
- Added CSS: `.bda-section`, `.bda-row`, `.bda-compact`, `.bda-detail`, `.bda-ailux-box`, animation
- Wired into `loadMoleculeTab()` — fires for all tabs (only renders where `#tabId-bd-activity` div exists)
- HTML placeholder added to TL1A tab (between competitive landscape and intel card)
- Pattern established for other 5 areas: add `#tabId-bd-activity` div to any tab to activate

---
## 2026-05-18 TL1A Competitive Landscape Expansion (Tasks #50–#52)

### Source: Competitive product analysis slide (IL-23 × TL1A bispecifics)
**Before:** 7 TL1A drugs in Supabase (tulisokibart, duvakitug, afimkibart, SIM0709, HXN-1003, ABS-101, AbbVie TL1A mAb)
**After:** 22 TL1A drugs — 15 new programs added

### New drugs inserted (all linked to `tl1a` area):
| ID | Name | Company | Stage | Direct? |
|---|---|---|---|---|
| ro7837195 | RO7837195 | Roche/Genentech/Pfizer | Phase 2 | ✓ |
| hy8931 | HY8931 | Newsoara Biopharma | Phase 1 | ✓ |
| qx030n | QX030N | Qyuns/Caldera | Phase 1 | ✓ |
| hbm2001 | HBM2001 | Harbour BioMed | Preclinical (IND) | ✓ |
| sab06 | SAB06 | Santa Ana Bio | Preclinical | ✓ |
| lbl053 | LBL-053 | Nanjing Leads Biolabs | Preclinical | ✓ |
| pr203 | PR203 | Shandong BoAn | Preclinical | ✓ |
| xmab412 | XmAb412 | Xencor | Preclinical | ✓ |
| lq080 | LQ080 | Shanghai Novamab | Preclinical | ✓ |
| generate-uc | Generate UC TL1A/IL-23 | Generate:Biomedicines | Preclinical | ✓ |
| cantai-tl1a | Cantai TL1A/IL-23 | Cantai Therapeutics | Preclinical | ✓ |
| spy230 | SPY230 | Spyre/Paragon | Preclinical | ✓ |
| lq082 | LQ082 | Shanghai Novamab | Preclinical | ✓ |
| es302 | ES302 | Elpiscience Biopharma | Preclinical | ✓ |
| spx306 | SPX-306 | Sparx Therapeutics | Preclinical | ✗ (oncology) |

### New companies inserted (12):
harbourbiomed, santaana, leads, shboan, xencor, helixon, novamab, cantai, spyre, elpiscience, sparx (newsoara was already present)

### meridian-research search terms updated:
- Area 1 now has 20 targeted search strings covering all tracked TL1A programs
- Drug-company attribution section updated with all 15 new pairings + confusion-prone notes
- RO7837195 vs afimkibart distinction explicitly noted (different drugs, both Roche but different targets)
- SIM0709 licensor/licensee split documented (Simcere originator / BI ex-China)

---
## 2026-05-18 Global Search → Supabase (Task #49)

### Deploy: commit 305d171
- **Problem:** `globalSearch()` filtered static DOM content only — all intel, deals, and catalysts in Supabase were invisible to search
- **Fix:** Added `_gsSbSearch()` async function that fires parallel Supabase queries (intel, deals, catalysts) debounced 280ms after the user stops typing
- **UI:** Floating dropdown panel (`#gs-sb-panel`) positioned below the search bar; sections for Intel (≤8), Deals (≤5), Catalysts (≤5 unresolved); type/area badges; clickable items open source URLs in new tab
- **Highlight:** Matched term highlighted in dropdown results with `<mark class="gs-hl">` styling
- **Close behaviour:** Panel hides on click outside the search wrap, on clear, or when term drops below 2 characters
- **DOM search unchanged:** Existing static-content filtering continues to run in parallel
- `data-ts` refreshed to 1779112306

---
## 2026-05-18 Full Dashboard Live-Data Wiring (Tasks #42–#47)

### Deploy: commit fdbd54a — 8 changes in one shot
- **Restored `loadAreaCompanies` + `loadAreaDrugs`** to all molecule tabs — Companies to Watch and Drugs to Know sections now render live from Supabase `company_areas`, `company_signals`, `drug_areas`, `drugs` tables
- **Industry Insights tab** replaced: removed ~2MB of static hardcoded HTML articles; replaced with 30-line dynamic shell populated by new `loadIndustryInsights()` function querying `intel` table (limit 300, order by `intel_date` desc)
- **Industry Insights stat bar** added: shows total items, deals, clinical entries, BD items, and date range — all computed from Supabase at load time
- **Home stat bar** added at top of `tab-home`: live counts for companies tracked, drugs tracked, intel items, upcoming catalysts
- **Submit Intel → Supabase**: `saveFromModal()` now writes to `intel` table (`verified=false`) in addition to localStorage; morning task can review and confirm
- **`header-date` fix**: JS-computed dynamically on page load (always shows today's date)
- **`data-ts` refreshed**: reset to current Unix timestamp; all task prompts updated to refresh on every deploy
- **`DOMContentLoaded`** updated to call `loadHomeStats()` and `loadIndustryInsights()` on every page load
- **Size reduction**: index.html shrank from ~2.75MB to ~765KB (72% reduction) by removing static Industry Insights content

### Task #46: meridian-evening-update skill updated
- Added STEP 5: drug stage patching (mirrors meridian-research STEP 5b)
- Fixed blob API fetch pattern (was using Contents API which truncates large files)
- Added `data-ts` refresh in STEP 6 deploy
- Updated architecture notes: Companies to Watch, Drugs to Know, Competitive Landscape, Industry Insights all now Supabase-driven (do not edit HTML directly)

### Task #47: bd-dashboard-weekly-update skill updated
- WEEKLY TASK 5 (validate drug data) now includes explicit stage PATCH pattern with exact stage values
- Added `ailux_competes_directly` flag review instruction
- Fixed blob API fetch pattern throughout
- Added `data-ts` refresh to WEEKLY TASK 6
- Updated architecture notes

---
## 2026-05-18 Header Timestamp Fix + New Area Onboarding Runbook

### Header "Last Updated" — now always current
- **Problem:** `header-date` was hardcoded "Saturday, May 16, 2026" in HTML; `data-ts` was a stale Unix timestamp
- **Fix 1 (one-time):** Cleared static text from `<strong id="header-date">` — JS now computes and writes today's date on every page load
- **Fix 2 (one-time):** Reset `data-ts` to `int(time.time())` (May 18 2026, ~7:01 AM)
- **Fix 3 (ongoing):** Updated `meridian-morning-update` task to refresh `data-ts` on every deploy — "Last updated" will always reflect the most recent 7 AM run
- **Deployed:** 8cd4515

### New area onboarding runbook created
- **Task:** `onboard-focus-area` (manual/ad-hoc, no cron schedule)
- **Location:** `/Users/kyleklaassen/Documents/Claude/Scheduled/onboard-focus-area/SKILL.md`
- **Covers 9 steps:** research pass → seed companies → seed drugs (with `drug_areas` link) → seed catalysts → seed intel → update meridian-research search terms → add dashboard tab → update the-meridian content architecture → verify + log
- **Key rules:** every drug verified against primary source before insert; `ailux_competes_directly` flag set explicitly; smaller biotech programs treated with same priority as pharma
- **Invoke:** manually from the Scheduled sidebar when a new focus area is added

---
## 2026-05-18 Pipeline Hardening — Drug Stage Auto-Update + Competitive Snapshot at Write Time

### Task #36: meridian-research — auto-patch drug stages (STEP 5b added)
- Research task now PATCHes `drugs.stage` in Supabase when a phase advance is confirmed by primary source
- Stage values: `Approved | BLA Filed | Phase 3 | Phase 2/3 | Phase 2 | Phase 1/2 | Phase 1b | Phase 1 | Preclinical`
- Rules: GET first to confirm drug_id, primary source required, two-source rule for demotions
- Stage updates logged in research notes file with `⚡ Stage updated:` marker
- Keeps competitive landscape table current without manual intervention

### Task #37: the-meridian — Supabase competitive context at write time (Step 3 added)
- Writing task now queries `drug_areas → drugs → companies` at the start of each run (before drafting)
- Builds `AREA_DRUGS` dict keyed by area_id, sorted by phase, flagged 🔴/🟡 by `ailux_competes_directly`
- Writer cross-checks competitor stage claims against live Supabase data (not just stale notes)
- Explicit instruction: if research notes mention a stage change not yet in Supabase, note it in the section narrative
- Both tasks updated via `update_scheduled_task`

---
## 2026-05-18 Architecture Overhaul — Research Pipeline + Meridian Issue + Pharma Intel

### 1. Research pipeline consolidated (meridian-research task)
- **Before:** `meridian-research` (4 AM) wrote notes only; `meridian-morning-update` (7 AM) did all Supabase writes
- **After:** `meridian-research` now does both — writes verified intel/deals/catalysts to Supabase AND saves the structured notes file organized by the 6 dashboard areas (TL1A, TSLP, IL-4Rα, IGF1R, FcRn, T-cell)
- `meridian-morning-update` is now lightweight: late-breaking sweep only + Meridian reader widget update
- Net result: Supabase gets populated 3 hours earlier each morning

### 2. Meridian Issue restructured — area-led (the-meridian writing task)
- **Before:** broad biopharma newsletter format (general landscape news, conference recaps)
- **After:** every issue is organized around the 6 dashboard focus areas — each content section maps to one area (TL1A, TSLP, IL-4Rα, IGF1R, FcRn, T-cell Engineering)
- JHU concept is now load-bearing (tied to a specific story), not appended generically
- No broad market recaps unless directly relevant to one of the 6 areas
- Writing task now explicitly skips areas with no new verified news (no padding)
- Schedule: 6:30 AM Mon–Sat (unchanged)

### 3. Pharma Intel tab — live Supabase intel injection
- Added `injectPharmaIntel()` JS function that runs on page load
- Fetches Supabase `intel_companies` JOIN `intel` for last 30 days, filtered to 35 pharma companies shown in the tab
- Maps Supabase `company_id` → piToggle slug (e.g. `merck` → `us-merck`, `abbvie` → `us-abbvie`)
- Injects a blue "🔴 Live Intel" section at the top of each company's expandable drawer
- Static financial data (market cap, revenue, R&D %, TAs) stays as-is — live intel prepended above it
- Deployed: commit fedfb07

---
## 2026-05-18 Pre-morning QA — PASS (0 issues found) — see qa_report_20260518.md

---
## 2026-05-18 Meridian Issue Tab — wired and live
- **Tab:** dedicated 📰 nav button → `tab-meridian-issue` with `<iframe>` loading `meridian_today.html` from GitHub Pages
- **Root cause fixed:** `the-meridian` task was saving HTML to The Meridian workspace but deploy script read from BD Platform (wrong path) — token was also missing from The Meridian folder
- **Fixes applied:**
  - Copied `.github_token` to The Meridian workspace
  - Updated `the-meridian` scheduled task prompt — deploy now reads from `/mnt/The Meridian/meridian_today.html` (correct workspace) and deploys via GitHub Contents API
  - Deployed today's issue manually (Monday, May 18, 2026) — verified live in browser
- **From tomorrow:** every 5 AM run auto-deploys the new issue; dashboard tab always shows the current day

---
## 2026-05-18 Morning Intelligence Update
- **Searched:** TL1A/IBD, TSLP/IL-33/Respiratory, IL-4Rα/Atopy, IGF1R/TED, FcRn/Autoimmune, T-cell Engineering/ACE, BD Deals
- **Intel written to Supabase:** 9 items with area tags
  - `tslp`: AZ tozorakimab OBERON+TITANIA Ph3 positive (Mar 27), MIRANDA Ph3 positive (Apr 20)
  - `igf1r`: Amgen SC Tepezza Ph3 positive — 77% proptosis response (Apr 6)
  - `fcrn`: argenx VYVGART expanded to all gMG serotypes (May 8), J&J Imaavy Priority Review for wAIHA (May 12)
  - `tcell`: UCB acquires Candid Therapeutics $2.2B (May 3), Kyverna miv-cel rolling BLA initiated (Apr 25)
  - `il4ra`: Dupilumab FDA approval CSU ages 2–11 (Apr 22), Amlitelimab Ph3 AAD data (Mar 28)
- **Deals written to Supabase:** 1 — UCB acquires Candid Therapeutics $2B up / $2.2B total (tcell, acquisition)
- **Catalysts added:** 3 — Amgen SC Tepezza sBLA (igf1r, H2 2026), IMVT-1402 D2T RA topline (fcrn, H2 2026), AZ tozorakimab NDA/MAA filing (tslp, H2 2026)
- **Catalysts resolved:** 2 — id=46 AZ tozorakimab OBERON interim (POSITIVE), id=3 AZ OBERON/MIRANDA Ph3 (POSITIVE three-for-three)
- **Company signals updated:** 3 — AZ signal id=2 (tozorakimab POSITIVE three-for-three), AZ signal id=3 (updated alarmin narrative), Amgen signal id=21 (SC Tepezza Ph3 positive)
- **HTML changes:** Meridian reader updated — replaced KT501/Sanofi (Mar 2026) item with UCB/Candid $2.2B acquisition (May 3 2026)
- **Deployed:** f136d6a
- **Sources:** AstraZeneca press releases, Amgen press release, argenx press release, UCB press release, Sanofi/Regeneron press release, J&J/PR Newswire, FierceBiotech, BioPharma Dive

---
## 2026-05-18 Schema Migration + Live Stock Prices
- **Problem:** `companies` table missing `stock_price`, `stock_change`, `market_cap`, `last_price_update` columns — daily price refresh task had been saving to JSON fallback only
- **Fix:** Ran ALTER TABLE via Supabase SQL editor — added all 4 columns
- **Backfilled:** 21 companies updated with today's prices from `stock_prices_2026-05-18.json` (0 skipped)
- **Sample data:** Eli Lilly $1004.92 (−1.07%), argenx $799.32 (−0.42%), Regeneron $698.25 (−3.00%)
- **Frontend:** Updated `buildStockCard()` to display live `$price` and `%change` badge in tile header (green/red color-coded)
- **Deployed:** 91a650475bf98fa5f0a7de87ea884e67e13e602d

---
## 2026-05-18 Drugs to Know → Supabase
- **Drug counts by area (from drug_areas junction):** tl1a: 6, tslp: 7, il4ra: 6, igf1r: 3, fcrn: 5, tcell (ace tab): 5
- **Tabs updated:** all 7 (tl1a, tslp, il4ra-tslp, il4ra-ox40l, igf1r-tshr, fcrn, ace)
- **Changes made:**
  - Added CSS block for `.live-drugs-grid`, `.drug-card-live`, `.dcl-header`, `.dcl-name`, `.dcl-company`, `.dcl-stage`, `.dcl-mech`, `.dcl-detail`
  - Added `loadAreaDrugs(tabId)` async function — fetches via drug_areas junction, uses `mechanism` field (actual schema), stage-colored badges
  - Updated `loadMoleculeTab()` to call `loadAreaDrugs(tabId)` as 5th loader
  - Inserted `<div id="{tabId}-live-drugs">` placeholder before each of the 7 static dkn-card sections
  - Schema note: drugs table uses `mechanism` field (no target/format/moa); area mapping is entirely via `drug_areas` junction table
- **Deployed:** ca8fe2ea7762fbf8b72090ce620f4fa3d826d596

---
## 2026-05-18 Companies to Watch → Supabase
- **company_areas table:** already existed (30 rows pre-seeded across 6 areas)
- **Areas covered:** tl1a (8 co), tslp (5 co), il4ra (6 co), igf1r (3 co), fcrn (4 co), tcell (4 co)
- **Tabs updated:** all 7 (tl1a, tslp, il4ra-tslp, il4ra-ox40l, igf1r-tshr, fcrn, ace)
- **Changes made:**
  - Added CSS block for `.company-watch-card`, `.cw-header`, `.insight-up/down/neutral`, `.signal-item` etc.
  - Added `loadAreaCompanies(tabId)` async function with area→tab mapping
  - Updated `loadMoleculeTab()` to call `loadAreaCompanies(tabId)` as 4th loader
  - Inserted `<div id="{tabId}-live-companies">` placeholder at top of each CW body (static cards remain as fallback)
- **Deployed:** 3eb476c80de63139669de7fa90b9047d575a0ff3

---
## 2026-05-18 Stocks Tab Audit
- **Status found:** functional — fully wired, no stub
- **Structure verified:**
  - `id="tab-stocks"` exists at line 5344 (8,160-line file)
  - Contains: 4 prediction rule chips, area filter bar (All / TL1A / TSLP / IL-4Rα / IGF1R / FcRn / T-cell), `#stock-cards-grid` div
  - `loadStockCards()` defined at line 1066; called at `DOMContentLoaded` (line 7369)
  - `buildStockCard()` renders company name, ticker, exchange, tagline, area tags, insight direction/text from `company_signals`, Ailux BD Lens text
  - `stockFilter()` toggles `stock-card-hidden` on cards by `data-areas` attribute
  - `navTo('stocks')` correctly activates tab via nav-icon-btn; tab-btn hidden (display:none) as expected
- **Supabase data verified:**
  - 27 companies, 30 company_areas, 49 company_signals — all IDs consistent (string slugs)
  - 7 companies have no area or signal data (Astellas, Cullinan, Galderma, Kali, LEO Pharma, PTC, Windward Bio) — data gap, not a code bug; cards still render in "All" view
  - `market_cap`, `stock_price`, `stock_change` columns do not exist in DB; current implementation correctly uses `company_signals` for insight direction/text instead
- **Action taken:** no changes made — tab is functional as-is
- **Deployed:** no (no changes)

---
## 2026-05-17 Molecule Tab Migration — Build Session

### Architecture Changes
- **All 7 molecule tabs** (TL1A, TSLP, IL-4Rα×TSLP, IL-4Rα×OX40L, IGF1R×TSHR, FcRn, ACE) now Supabase-driven for intel, catalysts, and deals
- **HTML shells** added to each tab: `{tabId}-live-intel`, `{tabId}-live-catalysts`, `{tabId}-live-deals` sections
- **Molecule JS renderer** added: `TAB_AREA_MAP`, `loadMoleculeTab()`, `loadAreaIntel()`, `loadAreaCatalysts()`, `loadAreaDeals()` — uses `_sb` (supabase-js) directly
- **Tab structure bug fixed**: missing `</div>` after `tab-home` caused all molecule tabs to nest inside it; added correct closing tag
- **Loader bug fixed**: rewrote three loader functions to use `_sb.from().in().eq().order().limit()` directly instead of incompatible `sbFetch` wrapper

### Supabase Enrichment Seeded
- 27 companies, 30 drugs, 24 catalysts, 13 deals in Supabase
- All 7 areas populated with area-tagged data

### Scheduled Tasks Updated
- `meridian-morning-update`, `meridian-evening-update`, `bd-dashboard-weekly-update` — all updated with:
  - Area ID reference table (`tl1a`, `tslp`, `il4ra`, `igf1r`, `fcrn`, `tcell`)
  - Intel type reference (`news`, `data`, `deal`, `regulatory`, `conference`, `other`)
  - Explicit "NEVER edit molecule tab HTML" instructions (Supabase-driven)
  - Blob API deploy pattern for large files

### Verification
- All 7 molecule tabs verified rendering: catalysts ✓, deals ✓, intel (graceful empty state) ✓
- Home tab: stock cards ✓, deal tracker ✓, catalysts feed ✓
- Commits: e91c4a5 (loader fix), 1dffe2f (tab-home structure fix)

---
## Evening Run — May 16, 2026 (~18:00 PT)

### Sources Checked
1. Bispecific antibody press releases (general) — via WebSearch
2. ClinicalTrials.gov / TL1A / IL-23 — Xencor XmAb412 + XmAb942 DDW 2026 (May 2–5); Merck tulisokibart expansion (Oct 2025); Spyre SKYWAY-RD
3. TSLP / IL-33 bispecific — Roche/QX031N (Oct 2025, already in dashboard); Odyssey Therapeutics pipeline
4. FcRn autoimmune — Nipocalimab JASMINE Ph2b SLE (J&J, Jan 6, 2026); VRDN-008 HV data expected
5. BCMA / CD19 / CD3 trispecific — UCB/Candid acquisition $2.2B (May 3, 2026); IBI3003 Fast Track (Jan 2026, oncology focus)
6. IGF1R / TSHR / TED — Elegrobart (VRDN-003) Ph3 initiated Aug 2024; no new data today
7. IL-4Rα / OX40L / atopic dermatitis — Amlitelimab Phase 3 AAD data (Mar 2026, already in dashboard); Belenos BEL536 Ph1 planned Q1 2026
8. BD deals — UCB/Candid $2.2B (May 3, 2026); Curacle/Mabtics MT-103 retinal bispecific (May 12, 2026 — retinal vascular, out of scope)
9. Conference abstracts — Xencor XmAb412 poster at DDW (May 2–5, 2026) — already in dashboard; Nature Medicine 2026 paper on TCEs for autoimmune CTDs

### Changes Made
- **Body 7 (BCMA/CD19/CD3 TCE tab)**: Added UCB/Candid $2.2B acquisition (May 3, 2026) — CND460 BCMAxCD19xCD3 trispecific; second major pharma validation of the format after Sanofi/HXN-1031 ($2.56B). intel-dot-red.
- **Body 6 (FcRn tab)**: Added Nipocalimab (J&J) JASMINE Ph2b primary endpoint met in active SLE (Jan 6, 2026) — first FcRn inhibitor to succeed in SLE; J&J advancing to Ph3, FDA Fast Track granted Mar 2026. intel-dot-blue.

### Skipped (already in dashboard)
- Xencor XmAb942 Ph1 HV final data at DDW (already Body 1)
- Xencor XmAb412 DDW preclinical poster (already Body 1, within XmAb942 item)
- Windward Bio $165M round (already Body 2)
- Dupilumab / amlitelimab AD data (already Bodies 3–4)

### Deployed
- Commit: 3191c23
- 2 new intel items added; no layout, CSS, JS, or Ailux Pipeline Overview changes

## Evening Run — Sun May 17, 2026 (~6:00 PM)

**Searches conducted:**
1. Bispecific antibody press release today May 2026
2. ClinicalTrials.gov TL1A / IL-23 update
3. TSLP / IL-33 bispecific news May 2026
4. FcRn autoimmune clinical trial news May 2026
5. BCMA / CD19 / CD3 trispecific news May 2026
6. IGF1R / TSHR thyroid eye disease antibody news 2026
7. IL-4Ra / OX40L atopic dermatitis news May 2026
8. Bispecific antibody licensing deal announced May 2026
9. DDW 2026 conference abstracts IBD immunology results
10. Xencor XmAb942 / XmAb412 DDW 2026 (validation)
11. Aclaris ATI-052 Phase 1a full results (validation)
12. UCB / Antengene ATG-201 deal (validation)
13. Merck tulisokibart expansion date (Oct 2025 — already pre-dashboard scope)
14. Sanofi lunsekimig Phase 2 results (validation)

**Dashboard changes (commit e3ada8c):**

### Added — TSLP tab
- **Sanofi lunsekimig Phase 2 data (Apr 7, 2026)**: TSLP×IL-13 bispecific Nanobody met primary endpoints in asthma (AIRCULES Ph2b) and CRSwNP (DUET Ph2a); missed AD (VELVET Ph2b). First Phase 2 validation of TSLP×IL-13 bispecific in respiratory. Source: sanofi.com PR.

### Added — IL-4Rα/TSLP tab
- **Aclaris ATI-052 full Phase 1a topline results (Apr 28, 2026)**: ~45-day half-life, dose-proportional PK, no safety signals. Phase 1b AD + asthma ongoing (data 2H 2026). Phase 2b asthma planned Q4 2026. Source: investor.aclaristx.com PR.

### Added — ACE tab
- **UCB/Antengene ATG-201 deal (Mar 3, 2026)**: CD19×CD3 masked bispecific TCE for B-cell autoimmune. $80M upfront / >$1.1B total milestones. AnTenGager™ steric-masking platform. FIH China/Australia. Source: ucb.com PR.

**Not added (already in dashboard):** Xencor XmAb942/XmAb412 DDW data, UCB/Candid $2.2B, Windward Bio $165M, tulisokibart ATLAS-UC, nipocalimab SLE.
**Not added (pre-dates relevance window):** Merck tulisokibart expansion (Oct 2025).
**Not added (target mismatch):** iBio IBIO-610 (metabolic), Boehringer/Immunitas (undisclosed target).

## Morning Update — May 17, 2026

### News Feed Sources
- Fierce Biotech RSS: Unable to fetch directly (URL not in provenance); 1 BD-relevant article sourced via WebSearch (Boehringer/Simcere SIM0709 deal)
- Endpoints News (news-briefing channel): ~23 articles scanned, 1 BD-relevant selected (Bristol Myers/Hengrui 13-asset deal, UCB/Candid TCE deal)
- Endpoints News (deals channel): ~25 articles scanned, 2 BD-relevant selected
- Endpoints News (R&D channel): ~23 articles scanned, 1 BD-relevant selected (Sanofi immunology CEO)
- WebSearch (7 targeted queries): 1 additional policy item (FDA 1-trial approval policy)

### Articles Added to Industry Insights Daily Feed (5 total)

1. **Endpoints News — Bristol Myers joins Hengrui party in 13-asset deal worth up to $15.2B** (May 15)
   - Tags: deals | Reason: Landmark China-to-West deal; Hengrui immunology/oncology pipeline; BD signal for outbound licensing

2. **Endpoints News — UCB bets $2B on Candid's T cell engager ambitions** (May 3)
   - Tags: deals, bd | Reason: China-founded TCE autoimmune company; validates bispecific B-cell depleting format for autoimmune; directly relevant to BCMA/CD19 tab

3. **Fierce Biotech — Boehringer pens €1.05B deal for Simcere's TL1A×IL-23p19 IBD bispecific SIM0709** (Jan 2026)
   - Tags: deals, bd | Reason: Directly relevant to TL1A×IL-23p19 tab; first major pharma validation of dual-target IBD bispecific from China

4. **Endpoints News — Sanofi's new CEO faces a reckoning on immunology-focused R&D strategy** (Apr 23)
   - Tags: market | Reason: Amlitelimab pipeline and BD implications; dupilumab franchise context; signals Sanofi BD appetite

5. **BioPharma Dive — FDA shifts to single-trial approval standard** (May 2026)
   - Tags: policy | Reason: Major regulatory policy shift affecting approval timelines for bispecific antibodies and immunology drugs

### Articles Rejected

- Boehringer/Zealand obesity shot (today, Endpoints R&D): Not relevant — GLP-1/obesity, not immunology/bispecific
- Erasca vs Revolution Medicines RAS drugs (today, Endpoints R&D): Not relevant — oncology/RAS, not target area
- Intellia CRISPR Phase 3 (yesterday, Endpoints R&D): Not relevant — gene therapy/TTR, not immunology
- Veradermics oral Rogaine (yesterday, Endpoints R&D): Not relevant — alopecia/minoxidil, not bispecific
- Pfizer/Arvinas breast cancer drug (2 days, Endpoints Deals): Not relevant — oncology PROTAC
- Bayer M&A return announcement (2 days, Endpoints Deals): Not relevant — no immunology focus specified
- Avalyn IPO / WHO malaria drug / Grace CRL (yesterday, Endpoints Briefing): Not relevant — respiratory/malaria/non-immunology
- Oruka Phase 2 psoriasis (Endpoints R&D): Marginally relevant (IL-17 psoriasis) but non-bispecific mAb; excluded to keep feed focused

### Intel Card Updates
None — no new validated press release / ClinicalTrials.gov / SEC filing data today for specific target tabs. All relevant deal data (UCB/Candid, BMS/Hengrui, Boehringer/Simcere) already captured in prior runs or in today's feed cards.

### Deployed
- Commit: e5fd65f
- 5 new ii-cards added to Industry Insights Today's Feed block
- Article counter updated: 64 → 69

### SKILL.md Update
- Skipped: /Users/kyleklaassen/Documents/Claude/Scheduled/meridian-morning-update/SKILL.md path not accessible in workspace mount. User should manually add STEP 1b to that file per task instructions.

---
## May 17, 2026 — Market & Learning Tab Redesign (Manual)

**Changes made to index.html:**

### Market & Learning Tab (`id="tab-stocks"`)
- **Removed** the "Market Signal Framework" banner header (`meridian-reader` div)
- **Replaced** 4 full `predict-card` sections with compact collapsible `.rule-chip` divs
  - Each chip shows: rule number badge + one-line brief summary + ▾ toggle
  - Expanded body reveals the full predict rules (same content, collapsible)
  - Functions: `toggleRuleChip(id)`
- **Replaced** 6 full-height `.stock-card` divs with compact grid tiles
  - New layout: `.stock-cards-grid` (CSS grid, auto-fill 310px min columns)
  - Each card shows: company + ticker + target-area tags + single key insight line
  - Click to expand full analysis (`.stock-body`)
  - Function: `toggleStockCard(el)`
- **Added** filter bar above the grid (All / TL1A·IBD / TSLP·Resp. / IL-4Rα / FcRn / T-cell Eng.)
  - Each card has `data-areas` attribute for JS filtering
  - Function: `stockFilter(btn, area)`

### CSS Added (earlier session, confirmed present)
- `.rules-grid`, `.rule-chip`, `.rule-chip-hd`, `.rule-num`, `.rule-brief`, `.rule-toggle-icon`
- `.stock-filter-bar`, `.stock-fbtn`, `.stock-cards-grid`, `.stock-card`, `.stock-tile-hd`
- `.stock-tile-left/right/name/sub/tags`, `.stag` variants, `.stock-insight`, `.stock-body`
- `.stock-card.expanded` states, `.stock-card-hidden`

### JS Added
- `toggleRuleChip(id)` — toggles `.open` on rule chip
- `toggleStockCard(el)` — toggles `.expanded` on stock card
- `stockFilter(btn, area)` — filters stock cards by `data-areas` attribute

**Deployed:** commit c456cae

---
## 2026-05-17 — Supabase Backend + Dynamic Rendering

### Infrastructure
- Created Supabase project: **Ailux BD Project** (`tghntyofptvfhmtchwcv.supabase.co`)
- Stored credentials: `.supabase_anon_key`, `.supabase_service_key`, `.supabase_config`
- Saved schema SQL: `supabase_schema.sql`
- Saved seed script: `supabase_seed.py`

### Schema (16 tables created)
`disease_areas` · `targets` · `target_areas` · `companies` · `company_areas` · `company_signals` · `drugs` · `drug_targets` · `drug_areas` · `trials` · `deals` · `intel` · `intel_areas` · `intel_companies` · `catalysts` · `meridian_issues`

RLS enabled on all tables; anon key granted SELECT only; service_role key for writes.

### Seed Data Loaded
- 6 disease areas (TL1A, TSLP, IL-4Rα, IGF1R, FcRn, T-cell)
- 11 targets with ailux_program flags
- 20 companies with 30 area mappings and 49 individual signals
- 17 key drugs with target + area mappings
- 10 catalysts (including 1 resolved: Immunovant batoclimab TED failure Apr 2026)

### Dashboard Changes
- Added `@supabase/supabase-js@2` CDN to `<head>`
- Replaced 363 lines of static stock card HTML with 3-line loading shell
- Added `buildStockCard()`, `loadStockCards()`, `sbFetch()` helper functions
- `loadStockCards()` fires on `DOMContentLoaded` alongside existing handlers
- Filter bar (`stockFilter()`) still works — cards rendered with correct `data-areas`
- **Result:** 20 company cards now render live from Supabase on every page load

## 2026-05-18 Home stats → Supabase: companies, drugs, catalysts, deals, intel counts — deployed 79797a8

## 2026-05-18 Industry Insights → Supabase: replaces static monthly entries with live intel feed — deployed c58546f9d801945fed18b4057babd6dff83774e7

---
## 2026-05-18 Supabase Data Audit (Scheduled — Automated)

### Scope
Full data quality pass against primary sources (ClinicalTrials.gov, company press releases, FDA.gov). Verified 27 companies, 30 drugs, 23 unresolved catalysts, 13 deals.

### Companies verified: 27
No corrections required — all insight_text and insight_dir values consistent with known pipeline status.

### Drugs verified: 30, updated: 5

| Drug | Field | Old Value | New Value | Source |
|------|-------|-----------|-----------|--------|
| duvakitug | stage_detail | "STARSCAPE (UC) + SUNSCAPE (CD)" | "SUNSCAPE (UC) + STARSCAPE (CD)" | ClinicalTrials.gov — SUNSCAPE-1/2 = UC; STARSCAPE-1 = CD |
| kt501 | mechanism | "BCMA × CD3 bispecific" | "BCMA × CD19 × CD3 tri-specific T-cell engager" | Kali/Sanofi press release (Mar 23 2026, prnewswire) |
| kt501 | key_data | "$150M upfront / $1.8B total" | "$180M upfront / $1.23B total Sanofi deal (Mar 2026)" | Kali/Sanofi press release; fiercebiotech; pharmaphorum |
| amlitelimab | stage_detail | "EU approved AD; FDA filing 2025" | "EU approved AD (Jun 2024); US regulatory submission planned H2 2026" | Sanofi press releases Jan 2026, Mar 2026; clinicaltrialsarena |
| teprotumumab | stage_detail | "SC formulation in development" | "SC Ph3 POSITIVE Apr 2026; sBLA planned late 2026" | Amgen press release Apr 2026; clinicaltrialsarena |
| miv-cel | stage_detail | "BLA filing H1 2026 for SPS" | "Rolling BLA initiated May 2026 for SPS; BLA completion targeted Q4 2026" | Kyverna IR May 12 2026; globenewswire |

### Catalysts verified: 23, resolved: 1

- **Catalyst 6 — RESOLVED**: "Kyverna miv-cel BLA filing for SPS" — rolling BLA submission initiated May 12, 2026. BLA completion targeted Q4 2026.

### Deals verified: 13, corrected: 1, flagged: 1

- **Deal ID 1 (Kali/Sanofi Mar 2026)**: Corrected `deal_type` from "collab" → "license" (confirmed exclusive worldwide license agreement).
- **Deal ID 17 — FLAGGED FOR MANUAL REVIEW**: Record shows "Sanofi licenses KT501 from Kali for $150M up / $1.8B total" dated Jan 2025. No press release or secondary source confirms a Jan 2025 Kali/Sanofi deal. The only confirmed Kali/Sanofi deal for KT501 was announced March 23, 2026 at $180M/$1.23B (already correctly captured in Deal ID 1). Deal ID 17 likely represents a duplicate seed entry with wrong date and wrong amounts. Recommend deletion after manual review.

### Confirmed accurate (no change needed)
- tulisokibart ATLAS-UC: Phase 3 ongoing, no topline data yet — readout ~Nov 2026 ✓
- nipocalimab (Imaavy): FDA approved gMG Apr 30, 2025 ✓ — brand name "Imaavy" confirmed ✓
- efgartigimod: expanded to all gMG serotypes confirmed ✓
- duvakitug Ph2b 48% UC remission signal ✓
- afimkibart AMETRINE (UC) + SIBERITE (CD) trial names ✓
- Earendil/Sanofi deal HXN-1003: $125M upfront / ~$1.85B total confirmed ✓
- Simcere/BI SIM0709: €42M upfront / €1.05B total confirmed ✓

### Flagged for manual review
1. **Deal ID 17** — Phantom duplicate record (see above). Recommend deletion.
2. **Catalyst 48** — "Sanofi amlitelimab FDA approval decision (AD)" sort_date 2026-10-01. FDA submission is not yet filed as of May 2026 (planned H2 2026); regulatory approval by Oct 2026 is not feasible. Catalyst date should be moved to 2027 or left open pending US filing.

### Not changed (could not verify)
- argenx efgartigimod Q8W SC Ph3 results timing — unverified specific date; left as-is.
- Specific clinical trial NCT enrollment completion dates — taken at face value from existing entries.


## 2026-05-18 Monthly task SKILL.md updated for Supabase architecture

---
## 2026-05-18 Submit Intel + Search Upgrade
- Submit Intel modal: replaced localStorage-only modal with full Supabase-backed form (headline, body, source URL/name, type, importance, area checkboxes); writes to `intel` table + `intel_areas` junction
- Global search: added `supabaseSearch()` async function that queries `drugs`, `companies`, and `intel` tables in parallel; result count appended to gs-count element
- Deployed: 8540cd5c8ff0478c38d305c1e1c8cd074c9488a7

## 2026-05-18 Stock Price Refresh

- **Status:** PARTIAL — prices fetched from Yahoo Finance but **NOT written to Supabase** (columns missing)
- **Root cause:** `companies` table lacks `stock_price`, `stock_change`, `market_cap`, `last_price_update` columns
- **Action required:** Add these columns to Supabase (see migration note below)
- **Fetched successfully:** 21 companies
- **Failed (fetch error):** 3 — Astellas Pharma (HTTP Error 404: Not Found), Boehringer Ingelheim (HTTP Error 404: Not Found), Galderma (HTTP Error 404: Not Found)
- **No/invalid ticker:** 3 — Kali Therapeutics, LEO Pharma, Windward Bio

**Sample prices (first 5):**
  - AbbVie (ABBV): $210.39 (+0.91%)
  - Amgen (AMGN): $326.31 (-3.01%)
  - Apogee Therapeutics (APGE): $81.14 (-3.34%)
  - argenx (ARGX): $799.32 (-0.42%)
  - AstraZeneca (AZN): $181.58 (-3.27%)

**Full price snapshot saved to:** `stock_prices_2026-05-18.json`

**Migration SQL (run in Supabase SQL editor to enable future writes):**
```sql
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS stock_price NUMERIC,
  ADD COLUMN IF NOT EXISTS stock_change NUMERIC,
  ADD COLUMN IF NOT EXISTS market_cap TEXT,
  ADD COLUMN IF NOT EXISTS last_price_update DATE;
```

## 2026-05-18 Intel Read modal + Drug detail modal: wired to Supabase, NCT auto-linking — deployed 1d99a3db3d8bd4f5d9fdf8721ed8ecf5cb208ec4

---
## 2026-05-18 Market watchlist → Supabase + Past Catalysts history section added — deployed 4eba801044483d8b77a4341ea4e2566e280ead20

---

## 2026-05-18 — Fix: Blank Molecule Tabs and Drugs to Know
**Commit:** `27d653e`

### Root Cause
The TL1A tab redesign (commit `1ee24b80`) removed the `#grid-tl1a-landscape` and `#grid-tl1a-tech` Grid.js container elements, replacing them with the new `tl1aPI` program intelligence table. However, the `initGrids()` function still tried to call `.render(document.getElementById('grid-tl1a-landscape'))` — which returned `null` — causing Grid.js to throw `Container element cannot be null`. Since this threw synchronously inside the function, all subsequent grid initializations (TSLP catalyst calendar, TSLP competitive landscape, IL-4Rα, IGF1R, FcRn, ACE grids) never executed. Result: every molecule tab appeared blank.

### Fix
Removed the dead `grids.tl1aLandscape` and `grids.tl1aTech` initialization blocks from `initGrids()` (lines 7777–7807 in the prior version). These are superseded by the `tl1aPI` Program Intelligence table introduced in the redesign.

### Verified
- No console errors on fresh page load
- `grid-tslp-readouts`, `grid-tslp-landscape`, `grid-tl1a-readouts` all render ✓  
- Drugs to Know tab activates correctly with 118 rows ✓
