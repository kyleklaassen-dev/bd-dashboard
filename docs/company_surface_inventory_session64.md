# Company Surface Inventory — Session 64
**Date:** 2026-05-26  
**Audit scope:** index.html — all company information rendering surfaces  
**Purpose:** WS-E classification required before canonical company card consolidation

---

## Summary

Three distinct company information surfaces identified. One is canonical. One is a parallel surface with its own tab system. One is a dead legacy DOM shell.

---

## Surface A — Canonical Entity Modal (`openCompanySlideOver`)
**Classification: CANONICAL — all new company intelligence should go here**

| Property | Value |
|---|---|
| HTML element | `#entity-modal-overlay` → `.entity-modal-card` |
| CSS | Lines 1136–1163 (`.entity-modal-*`) |
| JS function | `openCompanySlideOver(companyId, companyName, sourceTabId, ...)` at line 9693 |
| Close function | `closeCoSlideOver()` at line 9952 → calls `closeEntityModal()` |
| HTML location | Lines 3732–3752 |

### Data fetched
- `company_profiles` — profile for current area (stage 1)
- `catalysts` — filtered by company + area
- `deals` — all company deals
- `companies` — id, name, ticker, hq_city, hq_country, company_type, ta_focus
- `company_areas` — area membership
- `ownership_edges` — rendered in drug rows (CONTROLLED_BY)
- `news_articles` — Recent Coverage section

### Called from
| Location | Line | Context |
|---|---|---|
| Area tab company row click | 9689 | All six biological area PI tables |
| Drugs Know tab company cell | 7373 | `onclick` on company name cell |
| Drug modal company link | 10625 | Company name link inside `_cemDrugBody` |
| Pharma Intelligence row | 17522 | `openCompanySlideOver('..., 'pharma-intel')` |
| Intel signal feed | 16846 | Signal panel company button |
| Intel/news feed button | 17450 | News article company button |

### Missing (per integration audit)
- `parent_company_id` hierarchy (UCB → Candid not shown)
- `companies.ailux_angle` — field exists, not surfaced
- Full portfolio view across all drugs (area-filtered only)
- `drug_competitive_scores` competitive context per company

### Verdict
**This is the canonical surface.** Do not build company intelligence anywhere else. All future company intelligence features belong here.

---

## Surface B — Dead Legacy DOM Shell (`#co-slideover`)
**Classification: DEAD LEGACY — safe to remove**

| Property | Value |
|---|---|
| HTML element | `#co-slideover-overlay`, `#co-slideover` |
| CSS | Lines 1291–1300 (`.co-slideover-*`) |
| JS writes to it | **None** |
| HTML location | Lines 3757–3766 |

### Evidence of deadness
- `#co-slideover-body`, `#co-slideover-title`, `#co-slideover-sub` are defined in HTML but never referenced by any JavaScript `getElementById` or `querySelector` call
- `closeCoSlideOver()` at line 9952 calls `closeEntityModal()` — it does NOT touch `#co-slideover`
- No function calls `document.getElementById('co-slideover')` to write content into it
- The element has been superseded by the entity-modal system (Surface A)

### Removal plan
1. Remove HTML lines 3757–3766 (`co-slideover-overlay` + `co-slideover` DOM nodes)
2. Remove CSS lines 1291–1300 (`.co-slideover*` class definitions)
3. Keep `closeCoSlideOver()` function — it delegates to `closeEntityModal()` and some callers may still reference it

**Risk:** Zero. Nothing reads from or writes to these elements at runtime.  
**Session:** Can be done any session as a cleanup task.

---

## Surface C — Company Database Panel (`openCOPanel` / `#co-panel`)
**Classification: PARALLEL SURFACE — redirect to canonical card (multi-session refactor)**

| Property | Value |
|---|---|
| HTML element | `#co-overlay`, `#co-panel` |
| CSS | Lines 7538–7548 (`.co-panel-*`) |
| JS namespace | IIFE at lines 17718–17836 |
| Public API | `window.openCOPanel(companyId, piRow)` |
| Close function | `window.closeCOPanel()` |
| HTML location | Lines 17713–17716 |

### Called from
| Location | Line | Context |
|---|---|---|
| Pharma Landscape "⎘ Profile" button | 18155–18156 | Button injected via `_injectButtons()` |
| URL hash routing (`#/company/{id}`) | 18166–18169 | `window.location.hash` on page load |

### Features this surface has that Surface A does not
- **URL-addressable routing** — `#/company/{company_id}` deep links open this panel
- **Tab system** — own tab rendering via `renderCOPanelTab()`
- **PI row context** — receives `piRow` argument for area-specific context from PI tables
- **`PI_SLUG_TO_ID` map** — maps Pharma Landscape row IDs to company_ids

### Data fetched
Similar to Surface A: companies, company_areas, drugs, catalysts, deals, company_profiles. Different query structure, different rendering templates.

### Consolidation path
This is a non-trivial refactor. Recommended approach:
1. **Phase 1 (thin launcher):** Redirect `openCOPanel` to call `openCompanySlideOver` with the same companyId. Loses the tab system and URL routing but eliminates duplication immediately.
2. **Phase 2 (preserve routing):** Add hash routing support to `openCompanySlideOver` / entity-modal system so `#/company/{id}` deep links still work after redirect.
3. **Phase 3 (remove):** Once routing is in entity-modal, remove the `#co-panel` IIFE, CSS, and DOM shell.

**Do not build new company intelligence into this surface.** The "⎘ Profile" button in Pharma Landscape should eventually open the canonical card.  
**Session estimate:** Phase 1 = 1 session. Phase 2–3 = 1–2 additional sessions.

---

## Surface D — Inline Company Card (`.cw-company-card`)
**Classification: INLINE LIST COMPONENT — not a standalone surface, no action needed**

| Property | Value |
|---|---|
| CSS | Lines 1838–1849 (`.cw-company-card`, `.cw-co-hd`, `.cw-co-body`) |
| Role | Expandable company row in company list/widget view |

This is not a company intelligence modal — it is a row component within a list. Not in scope for consolidation. No new fields to route anywhere.

---

## Action Summary

| Surface | Action | Session |
|---|---|---|
| A — entity-modal (canonical) | Add missing fields: `ailux_angle`, `parent_company_id`, full portfolio view | Sprint 3+ |
| B — `#co-slideover` (dead) | Remove HTML + CSS | Any cleanup session |
| C — `#co-panel` (parallel) | Phase 1: redirect `openCOPanel` → `openCompanySlideOver` | Session 66+ |
| D — `.cw-company-card` (inline) | No action | — |

### Immediate rules
1. All new company intelligence → Surface A only
2. Do not add features to `#co-panel` (Surface C)
3. Do not restore `#co-slideover` (Surface B)

---

## `company.ailux_angle` — Current Status

`companies.ailux_angle` exists in the database and IS rendered in one location:  
Line ~9800 in `openCompanySlideOver` body — "Ailux BD Lens" blue callout box.  
It IS in the canonical surface. Confirmed present per integration audit. No gap here.

## `parent_company_id` — Current Status

`parent_company_id` field: **NOT rendered in any company surface** (confirmed by audit at line 235 of integration_audit). The UCB → Candid hierarchy is invisible in the UI. This is a Surface A addition for Sprint 3.

---

*Session 64 — 2026-05-26. No code modified. Inventory only.*
