# RESUME — pick up from another machine

A condensed cookbook. For the full picture read `HANDOFF.md` and `CLAUDE.md` at the project root.

## On a fresh machine

```bash
# 1. Copy the repo (whichever way: git clone, rsync, scp, zip — your choice)

# 2. Install Python 3.12 + Chromium deps
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 3. Sanity check
python -c "import scrapy, trafilatura, yaml; print('ok')"
sqlite3 data/articles.db "SELECT COUNT(*) FROM articles"   # if you copied data/

# 4. Smoke test
scrapy crawl express -a max_total=20 -a events=imran_trial
sqlite3 data/articles.db "SELECT article_type, COUNT(*) FROM articles GROUP BY 1"
```

## Open Claude Code on a fresh machine

The first message Claude sees in any new session in this directory will include `CLAUDE.md` and the auto-memory entries that mirror it. Tell Claude `read HANDOFF.md and tell me where we are`.

## Push to VPS (if not already deployed)

```bash
ssh root@69.55.49.66 'mkdir -p /opt/pk-scraper'

rsync -avz --delete \
  --exclude '.venv' --exclude 'data' --exclude 'exports' \
  --exclude 'httpcache' --exclude '.git' --exclude '__pycache__' \
  --exclude '.claude' --exclude '*.pyc' \
  ./ root@69.55.49.66:/opt/pk-scraper/

ssh root@69.55.49.66 'cd /opt/pk-scraper && docker compose up -d --build'
ssh root@69.55.49.66 'cd /opt/pk-scraper && docker compose logs -f scraper'
```

## Run the open work (opinion/blog/editorial)

```bash
nohup .venv/bin/scrapy crawl express -a max_total=400 \
  > /tmp/express_opinion_test.log 2>&1 &
disown

# Watch:
watch -n 10 "sqlite3 data/articles.db 'SELECT article_type, COUNT(*) FROM articles GROUP BY 1 ORDER BY 2 DESC'"
```

If counts climb for `Opinion` / `Blog` / `Editorial`, the new code is working — push to VPS and run there.

## Pull dataset down

```bash
rsync -avz root@69.55.49.66:/opt/pk-scraper/exports/articles.csv ./
rsync -avz root@69.55.49.66:/opt/pk-scraper/data/articles.db ./
```

## Stop everything

```bash
# Local
pkill -f keep_alive.sh
for pid in $(pgrep -f "[.]venv/bin/scrapy crawl"); do kill -9 "$pid"; done

# VPS
ssh root@69.55.49.66 'cd /opt/pk-scraper && docker compose down'
```

## Final-deliverable refresh

```bash
.venv/bin/python scripts/backfill_authors.py        # fill any missing bylines
.venv/bin/python scripts/backfill_article_type.py   # re-classify from cache
.venv/bin/python scripts/export.py --out exports/articles.csv
.venv/bin/python scripts/report.py
```
