# VPS deployment

Self-restarting Docker setup for running the scraper continuously on a VPS.

## What it does

When started, the container runs `scripts/keep_alive.sh`, which:
- Launches all eight spiders in parallel (Urdu-only mode is on by default).
- Re-launches any spider that crashes or exits, until each source's target is met.
- Exports `exports/articles.csv` every 15 minutes (a fresh snapshot you can `rsync` down whenever you like).
- Survives VPS reboots via Docker's `restart: unless-stopped`.

Targets (per source) are set to a high cap so the scrape keeps producing for hours:
- Express News · 10,000
- BBC Urdu · 5,000
- Abb Takk · 3,000
- ARY Urdu · 3,000
- Dawn News (Urdu) · 3,000
- ARY / Geo / Dawn (English-edition fallbacks) · 500 each

`URDU_ONLY=true` is set in the Dockerfile so any English-detected article is dropped at the pipeline stage — only Urdu rows make it into the database.

## Requirements on the VPS

Anything that runs Docker — Ubuntu 22.04+, Debian 12, etc. ~2 GB RAM and ~5 GB disk are plenty.

```bash
# One-time, on the VPS:
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
```

## Deploy in three commands

From your local machine:

```bash
# 1. Copy the repo to the VPS (rsync skips the venv/data/cache via .dockerignore)
rsync -avz --exclude '.venv' --exclude 'data' --exclude 'httpcache' \
      ./ root@YOUR_VPS_IP:/opt/pk-scraper/

# 2. ssh in and start it
ssh root@YOUR_VPS_IP 'cd /opt/pk-scraper && docker compose up -d --build'

# 3. Watch the logs
ssh root@YOUR_VPS_IP 'docker logs -f pk-scraper'
```

That's it. The scraper now runs 24/7, restarts on crashes, and survives VPS reboots.

## Pulling the dataset down

The CSV is refreshed every 15 minutes inside `/opt/pk-scraper/exports/articles.csv` on the VPS. Pull it whenever:

```bash
rsync -avz root@YOUR_VPS_IP:/opt/pk-scraper/exports/articles.csv ./
rsync -avz root@YOUR_VPS_IP:/opt/pk-scraper/data/articles.db ./    # optional full DB
```

For the HTML report:

```bash
ssh root@YOUR_VPS_IP 'cd /opt/pk-scraper && docker compose exec scraper python scripts/report.py'
rsync -avz root@YOUR_VPS_IP:/opt/pk-scraper/exports/report.html ./
```

## Operating

```bash
# Status
docker compose ps
docker compose logs --tail=50 scraper

# Stop / start / restart
docker compose stop
docker compose start
docker compose restart

# Run a one-off command inside the container (e.g. ad-hoc stats)
docker compose exec scraper python scripts/stats.py
docker compose exec scraper python scripts/export.py --out exports/snapshot.csv

# Update after editing config/events.yaml or config/sources.yaml
docker compose down
rsync -avz ./ root@YOUR_VPS_IP:/opt/pk-scraper/
docker compose up -d --build
```

## Disk / database

The SQLite DB lives on the host at `/opt/pk-scraper/data/articles.db` and grows roughly **5 KB per article**. At 30,000 articles you're around 150 MB — trivial for any VPS. The HTTP cache (`httpcache/`) can grow larger; clear it with `docker compose exec scraper rm -rf httpcache/*` if needed.

## Resource caps

The compose file limits the container to **1.5 GB RAM and 1.5 CPU cores** so it won't starve other workloads. Tune in `docker-compose.yml` if your VPS has more headroom.

## When to stop the scraper

Once each source has plateaued (visible in `docker compose logs`), the keep-alive loop will keep relaunching exhausted spiders that produce zero new rows. That's harmless — just network noise — but you can stop the container at that point:

```bash
docker compose stop
```

The DB and CSV remain available on disk for download.
