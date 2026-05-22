#!/bin/bash
# ============================================================
# TL1A Full Enrichment Runner
# Runs company_enrichment.py for all TL1A companies in priority order.
# Usage: ./run_tl1a_enrichment.sh [--dry-run]
# Logs to: logs/tl1a_enrichment_YYYYMMDD.log
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$WORKSPACE/logs"
mkdir -p "$LOG_DIR"

LOG="$LOG_DIR/tl1a_enrichment_$(date +%Y%m%d_%H%M).log"
DRY_RUN="${1:-}"

# Load credentials
export ANTHROPIC_API_KEY=$(cat "$WORKSPACE/.anthropic_api_key" | tr -d '\n')
export SUPABASE_URL="https://tghntyofptvfhmtchwcv.supabase.co"
export SUPABASE_SERVICE_KEY=$(cat "$WORKSPACE/.supabase_service_key" | tr -d '\n')

echo "TL1A Enrichment Runner — $(date)" | tee "$LOG"
echo "Log: $LOG" | tee -a "$LOG"
echo "" | tee -a "$LOG"

# Priority order: lowest completeness first, then alphabetical
COMPANIES=(
  "jnj"
  "celgene"
  "roivant"
  "xencor-942"
  "xencor-412"
  "prometheus"
  "teva"
  "spyre"
  "roche"
  "abbvie"
  "sanofi"
  "earendil"
  "episcience"
  "lilly"
  "simcere"
  "merck"
  "caldera"
  "boehringer"
  "xencor"
  "lanova"
  "gossamerbio"
  "pfizer"
  "absci"
  "mirador"
  "takeda"
)

TOTAL=${#COMPANIES[@]}
DONE=0; FAILED=0

for company in "${COMPANIES[@]}"; do
  echo "[$((DONE+1))/$TOTAL] Enriching: $company — $(date +%H:%M:%S)" | tee -a "$LOG"

  if python3 "$SCRIPT_DIR/company_enrichment.py" \
      --area tl1a \
      --company "$company" \
      $DRY_RUN >> "$LOG" 2>&1; then
    echo "  ✅ $company — done" | tee -a "$LOG"
    DONE=$((DONE+1))
  else
    echo "  ❌ $company — FAILED (see log)" | tee -a "$LOG"
    FAILED=$((FAILED+1))
  fi

  # Brief pause between companies to avoid rate limits
  sleep 5
done

echo "" | tee -a "$LOG"
echo "=== ENRICHMENT COMPLETE: $DONE succeeded, $FAILED failed ===" | tee -a "$LOG"
echo "Finished: $(date)" | tee -a "$LOG"
