# Meridian — Session Handoff (live as of 2026-06-16)

Pick up here. Read `PRIORITY.md`, `NEXT_SESSION.md`, `CLAUDE.md`, and the memory index first. Full context: `docs/audits/OVERNIGHT_SUMMARY_2026-06-16.md`, `REVIEW_ITERATION_1/2_2026-06-16.md`.

## Access & conventions
- Repo `kyleklaassen-dev/bd-dashboard`, branch `main` = single source of truth (protected: no force-push/deletion). Working folder = the `bd-dashboard` clone (old `BD Platform` folder retired).
- GitHub: use `.github_token_workflow` (the plain `.github_token` is DEAD). repo+workflow scope.
- git is unreliable through the Cowork mount (FUSE deadlocks) → deploy via the GitHub API: fetch live file raw + sha, edit, PUT with sha, verify on raw.githubusercontent. Kyle runs `git pull` locally to sync.
- Supabase: ref `tghntyofptvfhmtchwcv`, REST `https://tghntyofptvfhmtchwcv.supabase.co/rest/v1`. `.supabase_service_key` (writes), `.supabase_anon_key` (client reads), `.supabase_pat` (Management API/DDL — curl not urllib). CI also holds these as repo secrets (one `SUPABASE_SERVICE_KEY` feeds all 48 workflows).

## State (done)
- Stages 0,1,2,3,5 complete. Engine: 15 workflows re-enabled, all active/healthy.
- Stage 0: production git foundation (one protected main, clean clone, hardened .gitignore). Local IS now synced to main (Kyle pulled 2026-06-16).
- Stage 1: governance 86→41, validation 43→35 (0 hard fails).
- Stage 2: 📡 Intelligence tab = 11 datasets, verified live, no dark panels.
- Stage 3: images extracted to /assets (index.html 4.4MB→2.49MB); structure map + decomposition plan in docs/architecture/.
- Stage 5: update_log trimmed, docs/ organized, README + planning docs refreshed.
- Model: Meridian Writer switched Sonnet→Opus (`claude-opus-4-8`). Confirmed working: fresh Issue dated June 16 2026 generated on Opus and is live. Research timeout 210→350, Writer timeout 15→30. (Fable is down and was never in the live pipeline anyway — live scripts use hardcoded model strings; no router deployed.)
- Health pill bug fixed (was counting skipped/cancelled as failing).

## Next actions
1. Service-role key rotation is KYLE'S to do (security boundary — do not perform it yourself). After he rotates: update GitHub secret `SUPABASE_SERVICE_KEY` (his step), then verify by dispatching a cheap workflow (e.g. completeness-scoring) and confirming it writes.
2. STAGE 4 (enforcement) — pending: apply `migrations/PROPOSED_drugwriter_enforcement.sql` + `PROPOSED_company_catalyst_enforcement.sql` in WARN mode first (via the `apply-migration` workflow, which has the service key), watch the live pipelines, then escalate to EXCEPTION. Lifts the stabilization freeze.
3. STAGE 1 residual DB-write fixes (via DrugWriter `src/database/drug_writer.py`, with sources — see `docs/audits/REVIEW_ITERATION_1_2026-06-16.md` §B): modality mismatches apg777 + apg279; duplicate molecule pairs ati-045≡bosakitug and xmab5871≡obexelimab; graph fixes (orphan `cld-423` + 3 edges where a company is mistyped subject_type='drug'); 8 stale approved-drug stages; 58 drugs missing drug_sources.
4. Continue review→fix iterations (accuracy + connectivity), building on each pass.

## Governance / safety (non-negotiable)
- Single-writer: write core tables only via DrugWriter/CompanyWriter/CatalystWriter/EdgeWriter. Every fact needs a source in `drug_sources`. Deletes/merges/stage-flips need Kyle's approval. Never put a service_role key in the client.
- Do NOT rotate secrets or enter API keys into fields — Kyle's to do; you may map consumers + verify after.
