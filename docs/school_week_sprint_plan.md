# School Week Sprint Plan — Week of June 1, 2026

**Status:** Autonomous. No action needed from Kyle while in school.
**Monitoring:** Check GitHub Actions tab and morning briefing (8 AM daily).

---

## What the Pipeline Will Do This Week

### Monday Night (9 PM ET)
Target: **Company profiles for 69 unenriched companies**
- Run company_enrichment.py for TL1A, FcRn, IBD areas
- These 69 companies show in the dashboard but have no BD angle, platform summary, or risk profile
- After Monday: profiles filled for all companies in top 3 areas

### Tuesday Night (9 PM ET)
Target: **53% mechanism_detail gap + 33% source_url gap**
- 92 drugs missing mechanism_detail — explains HOW each drug works
- 57 drugs missing source_url — required for sourcing compliance
- Run molecule_enrichment.py + CT.gov sync for each area

### Wednesday Night (9 PM ET)
Target: **100Q intelligence for 20 Next Gen bispecifics**
- 159 drugs have zero 100-question intelligence
- Priority: next-gen bispecifics competing with ALX001
- Each drug gets answers to 100 questions across 8 domains

### Thursday Night (9 PM ET)
Target: **Company profiles pass 2 + validation expansion**
- Fill atopy, TSLP, IL-4Rα area company profiles
- Run validation tests and write results to DB
- Catch any enrichment regressions from earlier in the week

### Friday Night (9 PM ET)
Target: **Full scoring sweep + ranking update**
- Re-run competitive scoring with all new data from the week
- Update next_gen_rankings snapshots
- Compute coverage scores — track how much we've improved
- Full validation suite run

---

## Database Gaps Targeted

| Gap | Before | Target After Week |
|-----|--------|------------------|
| mechanism_detail | 92 missing (53%) | <20 missing |
| source_url | 57 missing (33%) | <15 missing |
| Company profiles | 69 with none | All covered |
| bd_angle | 78 missing | <20 missing |
| 100Q intelligence | 159 without any | Top 20 Next Gen covered |
| Coverage score | Unknown | Computed for all |

---

## What Kyle Returns To (Saturday)

1. Open the dashboard — competitive cards will have mechanism detail, BD angles, risk summaries
2. Check PRIORITY.md — pipeline will have updated progress
3. Review the next_gen_rankings history — see how scores shifted during the week
4. Read the morning briefing — Saturday 8 AM summary of the week's work
5. Apply v43 migration if not already done (next_gen_rankings table)

---

## If Something Fails

Each step has `continue-on-error: true` — pipeline won't halt on partial failures.
Check GitHub Actions tab: https://github.com/kyleklaassen-dev/bd-dashboard/actions
