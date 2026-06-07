# data/ — Static Dashboard Layer

All files in this folder are **served by GitHub Pages** and fetched directly
by `index.html` at runtime. Do not put script-generated artifacts here.

## Files

### Manually curated competitive data
Competitive pipeline/monospecific/readout JSON for each area tab in the dashboard.
Edit these directly when competitive intelligence changes.

| Pattern | Purpose |
|---|---|
| `tl1a_*.json` | TL1A competitive area |
| `tslp_*.json` | TSLP area |
| `il4ra_tslp_*.json` | IL-4Rα × TSLP bispecific area |
| `il4ra_ox40l_*.json` | IL-4Rα × OX40L area |
| `igf1r_tshr_*.json` | IGF1R × TSHR area |
| `fcrn_*.json` | FcRn area |
| `ace_*.json` | ACE area |

### Ailux asset data
| File | Purpose |
|---|---|
| `asset_profiles.json` | Ailux asset detail panels |
| `asset_docs.json` | Asset document links |

### Script-generated (committed intentionally — dashboard reads these)
| File | Written by | When |
|---|---|---|
| `navigator_lookup.json` | `scripts/build_navigator_lookup.py` | On demand / weekend sprint |
| `indication_priority_scores.json` | `scripts/seed_indication_priorities.py` | On demand |

## What does NOT belong here
Script-generated artifacts (training data, drift reports, prompt improvements).
Those go in `output/` which is gitignored. See `output/.gitkeep` for the folder.
