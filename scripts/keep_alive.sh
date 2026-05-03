#!/usr/bin/env bash
# Self-healing scrape loop. Designed to run unattended.
#
# Every CHECK_INTERVAL seconds:
#   - For each (spider_name, source_name, target) row, check the DB count.
#   - If count < target AND that spider isn't currently running, relaunch it.
#   - Always-on guard: also relaunches if it crashed.
#
# Stop with:  pkill -f scripts/keep_alive.sh

set -u

cd "$(dirname "$0")/.."

CHECK_INTERVAL=120         # seconds between checks
LOG_DIR=/tmp
DB=data/articles.db

# spider_name | source_name (in DB) | target | max_total per launch
# Urdu-only mode: every spider here yields Urdu articles only.
# Each row: spider_name | source_name | target | max_total_per_launch
# Spiders run in parallel (different domains, no contention).
SPIDERS=(
  # Opinion / Blog / Editorial harvest. Each source's config restricts its
  # crawl to opinion-section listings only. With OPINION_ONLY=true active,
  # OpinionOnlyPipeline drops anything that still classifies as News Report
  # so only Opinion/Blog/Editorial rows accumulate in the DB.
  "express|Express News|10000|10000"
  "ary_urdu|ARY News (Urdu)|5000|5000"
  "dawnnews|Dawn News (Urdu)|5000|5000"
  "humsub|Humsub|10000|10000"
  "nawaiwaqt|Nawa-i-Waqt|5000|5000"
  "naya_daur|Naya Daur Urdu|3000|5000"
)

count_for_source() {
  sqlite3 "$DB" "SELECT COUNT(*) FROM articles WHERE source='$1'" 2>/dev/null || echo 0
}

# Pick whichever scrapy/python binaries are available. Local dev uses a venv;
# the Docker image installs scrapy globally and has no .venv.
if [ -x ".venv/bin/scrapy" ]; then
  SCRAPY_BIN=".venv/bin/scrapy"
  PYTHON_BIN=".venv/bin/python"
elif command -v scrapy > /dev/null 2>&1; then
  SCRAPY_BIN="$(command -v scrapy)"
  PYTHON_BIN="$(command -v python3 || command -v python)"
else
  echo "FATAL: scrapy binary not found (tried .venv/bin/scrapy and PATH)"
  exit 1
fi
echo "$(date +'%H:%M:%S') keep_alive: using $SCRAPY_BIN ($PYTHON_BIN)"

is_running() {
  # Match the python process running this scrapy spider. The `[s]` trick
  # prevents pgrep from finding its own argv in the process table.
  pgrep -f "[s]crapy crawl $1 " > /dev/null 2>&1
}

launch() {
  local spider=$1 max_total=$2
  echo "$(date +'%H:%M:%S') keep_alive: launching $spider (max_total=$max_total)"
  nohup "$SCRAPY_BIN" crawl "$spider" -a max_total="$max_total" \
    > "$LOG_DIR/${spider}_keep.log" 2>&1 &
  disown
}

EXPORT_INTERVAL=900   # 15 minutes
LAST_EXPORT=0

mkdir -p exports

while true; do
  NOW=$(date +%s)
  echo "$(date +'%H:%M:%S') keep_alive: checking all sources"
  TOTAL=$(sqlite3 "$DB" "SELECT COUNT(*) FROM articles" 2>/dev/null || echo 0)
  echo "  total articles: $TOTAL"
  for row in "${SPIDERS[@]}"; do
    IFS='|' read -r spider source target max_total <<< "$row"
    n=$(count_for_source "$source")
    if [ "$n" -ge "$target" ]; then
      echo "  ✓ $source = $n / $target — done"
      continue
    fi
    if is_running "$spider"; then
      echo "  · $source = $n / $target — running"
      continue
    fi
    launch "$spider" "$max_total"
  done

  # Periodic export so the user wakes up to a fresh CSV regardless of state
  if [ $((NOW - LAST_EXPORT)) -gt $EXPORT_INTERVAL ]; then
    echo "  exporting CSV snapshot..."
    "$PYTHON_BIN" scripts/export.py --out exports/articles.csv > /dev/null 2>&1 \
      && echo "    ✓ exports/articles.csv" \
      || echo "    ✗ export failed"
    LAST_EXPORT=$NOW
  fi

  sleep "$CHECK_INTERVAL"
done
