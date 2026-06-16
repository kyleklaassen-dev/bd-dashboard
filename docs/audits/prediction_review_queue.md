# Prediction Review Queue (Tier-2)

**Generated:** 2026-06-15 by `scripts/score_foresight.py`

These judgment calls are past their resolution window and still `open`.
For each: set `status` (correct / incorrect / partially_correct / expired),
fill `outcome_text` + `outcome_date` (+ `outcome_value_usd` for deals),
set `reasons_held` (did the rationale survive?), and add a source URL.
Do this in Supabase or via a follow-up script — never let the loop guess.

| id | type | due | confidence | statement |
|----|------|-----|-----------|-----------|
