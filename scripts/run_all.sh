#!/usr/bin/env bash
# Run every spider in sequence. Articles accumulate in data/articles.db.
set -euo pipefail
cd "$(dirname "$0")/.."

for spider in dawn bbc_urdu express ninetytwo abbtakk geo ary; do
  echo "=== $spider ==="
  scrapy crawl "$spider" "$@"
done

echo
python scripts/stats.py
