# Meridian — BD & Competitive-Intelligence Platform

Meridian is a competitive-intelligence and business-development (BD) platform built
around **Ailux's TL1A×IL-23p19 bispecific antibody program for inflammatory bowel
disease (IBD)**. It tracks the competitive landscape (targets, drugs, companies,
trials, deals, catalysts) as a governed knowledge graph and surfaces it through a
live dashboard so a BD/strategy team can answer, quickly and with citations:

- Who else is developing in this mechanism / indication, and at what stage?
- What just changed (catalysts, readouts, deals) and why does it matter to Ailux?
- Where is the whitespace, and which assets are worth a conversation?

It is designed as **"trusted intelligence, not more AI summaries"**: every fact in
the database is expected to carry a real source row, and the read layer is built on
an explicit ontology rather than free-text generation.

> **Live dashboard:** GitHub Pages site served from the `kyleklaassen-dev/bd-dashboard`
> repo (`index.html`). The GitHub Pages CDN has roughly a 10-minute TTL, so a freshly
> deployed change may take a few minutes to appear; verify against
> `raw.githubusercontent.com` if in doubt.

---

## Quickstart

### Prerequisites
- **Python 3.11+** (a local `.venv/` is used; pipelines are plain Python scripts).
- A **Supabase** project (Postgres + RLS). Project ref: `tghntyofptvfhmtchwcv`.
- Credentials, supplied via local dotfiles (never committed — see **Security**):
  - `.env` (copy from `.env.example`)
  - `.supabase_anon_key`, `.supabase_service_key`, `.supabase_config`
  - `.anthropic_api_key` (for LLM pipelines)
  - `.github_token_workflow` (for deploys via the GitHub Contents/Git Data API; the plain `.github_token` is dead)

### Run the dashboard locally
The dashboard is a single static file. Open `index.html` in a browser, or serve it:

```bash
python -m http.server 8000   # then open http://localhost:8000/index.html
```

The client talks to Supabase using the **publishable/anon key** (safe client-side,
protected by Row-Level Security). No service key is ever embedded in the client.

### Deploy
The repo deploys from a single protected `main` branch. A clean local clone can
`git push` to `main`; agent/automation contexts that lack a working git checkout
deploy through the **GitHub Contents API** (or the Git Data API for batch changes)
using a token (recipe in `docs/archive/CLAUDE_full_2026-06-09.md`).
After deploy, allow for the GitHub Pages CDN TTL (~10 min) before verifying against
`raw.githubusercontent.com`.

### Run the tests
The writer/regression suites are read-only and must stay green:

```bash
python tests/database/test_drug_writer.py    # read-only; must pass
```

---

## Architecture (at a glance)

```
external sources → ingestion → identity / ontology → enrichment
        → knowledge graph (entity_edges) → products → Supabase → frontend
```

- **Backend:** Supabase (Postgres). The browser uses the anon key + RLS read
  policies; the **service key lives only in CI secrets** (GitHub Actions), never in
  the client or the repo.
- **Pipelines:** Python scripts (research → intel extraction → enrichment →
  write) orchestrated by GitHub Actions. Many LLM-backed workflows are
  intentionally **disabled for cost** and run on demand.
- **Frontend:** `index.html` (the large single-file dashboard, a Phase-4 split
  target) plus a set of focused `meridian_*.html` product views, all on GitHub Pages.
- **Governance:** core tables (`drugs`, `companies`, `entity_edges`, `catalysts`)
  are written only through their **single Writer** (`src/database/drug_writer.py`,
  others in progress). Every fact requires a source row. See the governance docs.

A fuller diagram and component map live in `docs/architecture/repo_maps.md` and the
canonical spec in `ARCHITECTURE.md`.

---

## Repository map

| Path | Purpose |
|------|---------|
| `index.html` | The deployed dashboard (single-file; Phase-4 split target). |
| `Meridian_Live.html`, `meridian_*.html`, `intelligence.html`, `predictions.html`, `aib_view.html` | Focused product views (ask, atlas, brief, today, coverage, predictions, intelligence, etc.). The main dashboard also carries a **📡 Intelligence** tab that surfaces 11 backend datasets (genetic validation, trial-design quality, conference signals, EU approvals, manufacturing, narrative trust, etc.). |
| `ARCHITECTURE.md` | Canonical platform-architecture specification. |
| `CLAUDE.md` | AI agent operating instructions (governance, hard rules, key paths). |
| `src/` | Production layer: the governed single-writer pattern. `src/database/` (shared client + drug/company/catalyst/edge writers) is live; identity, ingestion, ontology, enrichment, and scoring are the staged directories code graduates into. |
| `scripts/` | Active pipelines (the bulk of the code). Subdirs: `scripts/maintenance/` (dedupe/audit/link tools), `scripts/integrations/` (external-API sync), `scripts/migrations/` (script-side migration helpers). |
| `tests/` | Writer and regression test suites. |
| `migrations/` | ~60 numbered SQL migrations (the schema's source of truth). `PROPOSED_*.sql` = staged for review (await owner approval before applying). |
| `data/` | Tracked dashboard input files. Generated caches/logs are gitignored. |
| `config/` | Configuration (e.g. the weekend autonomous-sprint phase config). |
| `docs/` | All documentation. Subdirs: `architecture/`, `database/`, `audits/`, `reports/`, `decisions/`, `frameworks/`, `sops/`, `archive/`. The docs root keeps only the read-first/governance files (constitution, decisions, STABILIZATION_PLAN) and a few script-referenced docs. |
| `.github/workflows/` | GitHub Actions pipelines (many disabled for cost; see project notes). |

**Where to look first:** `src/` for the production/governed code, `scripts/` for the
data pipelines, `migrations/` for the schema, and `docs/` for everything else.
The real code mass currently lives in `scripts/`; `src/` is the layer code
graduates into as it becomes a governed, production writer.

---

## Governance & source-of-truth docs

Read these before changing data, schema, or governed code:

- `docs/STABILIZATION_PLAN.md` — current phase, what's in progress, success criteria. **Read first.**
- `docs/constitution.md` — what counts as truth, the source hierarchy, what needs approval.
- `docs/database/governance_table.md` — per-table owner / sole-writer / validation.
- `docs/architecture/drug_lifecycle.md` — how a drug record flows through the system.
- `docs/architecture/repo_maps.md` — intended repository layout and component map.
- `docs/decisions.md` — architecture decision records (why things are the way they are).
- `PRIORITY.md`, `NEXT_SESSION.md`, `SESSION_PROTOCOL.md` — current task, handoff, and session ritual.

---

## Security

- **Secrets are never committed.** They live in CI (GitHub Secrets) and in local
  dotfiles only. The `.gitignore` blocks `.env`, all `.supabase_*` / `.github_token*`
  / `.anthropic_api_key` dotfiles, and catch-all patterns (`*.key`, `*.pem`,
  `*_secret*`, `*service_role*`).
- **The client uses the Supabase publishable/anon key behind RLS** — the service
  role key is CI-only.
- A previously exposed service-role key (removed from the client) still needs
  rotation in Supabase as an open security item (see project security notes).

---

## Status

The platform is in a **stabilization sprint**: no new features until single-writer
enforcement and the related Phases 1–3 are green (see `docs/STABILIZATION_PLAN.md`).
Treat `drugs` / `companies` / `entity_edges` / `catalysts` as write-through-the-Writer
only, and ensure every fact has a source.
