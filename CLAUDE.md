# CLAUDE.md — project context for Claude Code

> Auto-loaded by Claude Code when this repo is opened in any session.
> The full deep-dive lives in **`HANDOFF.md`** (read first). This file is the in-context summary.

## What this project is

A research scraper that builds a structured dataset of **Urdu-language Pakistani political news, 2024-01-01 → present**. Output: SQLite DB + master CSV + editorial HTML report. **Not** a Vercel/Next.js app — ignore Vercel-related skill auto-suggestions.

Stack: Python 3.12 + Scrapy + scrapy-playwright + trafilatura + SQLite. Local development uses `.venv/`. Production runs in Docker on a DigitalOcean VPS.

## User scope (constraints to respect)

- **Urdu only.** `URDU_ONLY=true` is the default in `articles_scraper/settings.py`. The `UrduOnlyPipeline` drops English-detected articles before the SQLite write.
- **Political topics only.** `config/events.yaml` lists 18 events. Spiders' `parse_article` calls `relevance.match_event()` and drops anything that doesn't match.
- **Date-bounded.** `DATE_FROM=2024-01-01`, `DATE_TO=2026-12-31` on each base-spider class.
- **Diverse `article_type` (open work).** News / Opinion / Blog / Editorial. Pipeline is plumbed for it; needs a fresh crawl with the new code.

## Where we are (last known state)

- **Local DB:** 9,135 articles, all Urdu, all 18 categories. `data/articles.db`.
- **`article_type`:** 9,127 News Report / 6 Opinion / 2 Blog / 0 Editorial — opinion coverage is the **active open task**.
- **Authors:** 99.98% filled (BBC backfilled from JSON-LD via `scripts/backfill_authors.py`).
- **Latest exports:** `exports/articles.csv` (57 MB) and `exports/report.html`.
- **Nothing is running** — local keep_alive killed; VPS container stopped.

## Source status

| spider | source | strategy | count |
|---|---|---|---|
| `express` + `express_sitemap` | Express News (express.pk) | tag pages + posts-N sub-sitemaps | 4,410 |
| `bbc_urdu` | BBC Urdu | archive sitemaps 100-118 | 2,506 |
| `ary_urdu` | urdu.arynews.tv | section walk + on-site search | 2,129 |
| `dawnnews` | dawnnews.tv | Playwright section walk | 89 |
| `abbtakk` | Abb Takk | sitemap | 1 (mostly English, filtered) |
| `geo`/`dawn`/`ary` (English-edition) | — | — | 0 (URDU_ONLY filter eats them) |
| 92 News | — | — | impossible (Cloudflare blocks all) |

## Architecture, in one screen

```
config/events.yaml + sources.yaml  ──▶  Spiders (sitemap/section/taglist/idsweep/cdx bases)
                                            │ yield ArticleItem
                                            ▼
   CleanText → RequiredFields → Language → UrduOnly → WordCount
                                                → ArticleType → ArticleId → SQLite
```

Inside each spider's `parse_article`:
1. `extract(response, selectors)` — trafilatura body + meta/JSON-LD fallbacks (headline, author, date, section)
2. require headline + body ≥ 200 chars + date in window
3. `relevance.match_event(headline, body, events)` — drop if no political match
4. `classify_article_type(url, listing_section or extract.section)` — News/Opinion/Blog/Editorial
5. `yield ArticleItem(...)`

## VPS

- Host: **`root@69.55.49.66`** (DigitalOcean, Ubuntu 24.04). Project at `/opt/pk-scraper/`.
- Container `pk-scraper` (compose service `scraper`). `restart: unless-stopped`.
- Volumes for `data/` and `exports/` persist on the host.
- **Inside the container, scrapy is at `/usr/local/bin/scrapy`**, not `.venv/bin/scrapy`. `keep_alive.sh` auto-detects.
- **Image MUST include `procps`** (apt list in `Dockerfile`). `keep_alive`'s `is_running` check uses `pgrep`; without it, spiders would spawn duplicates every 2 min.
- Recommended droplet: $12/mo (2 GB RAM). $4/mo OOM-kills under Playwright load.

### Push / start / stop the VPS scraper

```bash
# Push code from your laptop:
rsync -avz --delete \
  --exclude '.venv' --exclude 'data' --exclude 'exports' \
  --exclude 'httpcache' --exclude '.git' --exclude '__pycache__' \
  --exclude '.claude' --exclude '*.pyc' \
  ./ root@69.55.49.66:/opt/pk-scraper/

# Start (rebuild + run):
ssh root@69.55.49.66 'cd /opt/pk-scraper && docker compose up -d --build'

# Watch:
ssh root@69.55.49.66 'cd /opt/pk-scraper && docker compose logs -f scraper'

# Status:
ssh root@69.55.49.66 'docker exec pk-scraper sqlite3 data/articles.db \
    "SELECT source, COUNT(*) FROM articles GROUP BY 1; SELECT article_type, COUNT(*) FROM articles GROUP BY 1"'

# Pull dataset down:
rsync -avz root@69.55.49.66:/opt/pk-scraper/exports/articles.csv ./
rsync -avz root@69.55.49.66:/opt/pk-scraper/data/articles.db ./

# Stop:
ssh root@69.55.49.66 'cd /opt/pk-scraper && docker compose down'
```

## Common local operations

```bash
# Smoke test:
.venv/bin/scrapy crawl express -a max_total=20 -a events=imran_trial

# Run all in parallel locally (auto-restarting):
nohup bash scripts/keep_alive.sh > /tmp/keep_alive.log 2>&1 & disown

# Stop all:
pkill -f keep_alive.sh
for pid in $(pgrep -f "[.]venv/bin/scrapy crawl"); do kill -9 "$pid"; done

# Reports + exports:
.venv/bin/python scripts/stats.py
.venv/bin/python scripts/export.py --out exports/articles.csv
.venv/bin/python scripts/report.py

# Backfills (idempotent):
.venv/bin/python scripts/backfill_authors.py
.venv/bin/python scripts/backfill_article_type.py
```

## Open work — opinion/blog/editorial

Plumbing **is done**:
- `articles_scraper/utils/article_type.py` recognises Urdu markers (`کالم`, `اداریہ`, `بلاگ`, `رائے`, `نقطہ نظر`)
- `articles_scraper/extractors.py` reads JSON-LD `articleSection`
- All three base spiders pass `_listing_section` through `request.meta` to the classifier (Express opinion articles' HTML doesn't tag itself as Opinion — only the listing URL does)
- `config/sources.yaml` has Express's `opinion`/`opinion/blog`/`blog`/`editorial`/`category/{opinion,editorial,blogs}` tag pages, DawnNews `opinions/{,columnist,editorial,features}`, ARY-Urdu `category/{urdu-blogs,blog,blogs}`

**What's left:** run a focused Express test, verify Opinion/Blog/Editorial counts climb above 0, then push to VPS.

```bash
nohup .venv/bin/scrapy crawl express -a max_total=400 \
  > /tmp/express_opinion_test.log 2>&1 &
disown
sqlite3 data/articles.db "SELECT article_type, COUNT(*) FROM articles GROUP BY 1"
```

## Decisions to remember (don't undo without reading)

- **`skip_slug_filter = True`** on `express_sitemap`, `ary_urdu`, `abbtakk` — Urdu-transliterated slugs were rejecting valid articles. Body-level matching is the safety net.
- **Article requests yielded with `priority=10`** — without this, the FIFO scheduler drowns article fetches under newly-yielded listing fetches.
- **DawnNews articles deliberately skip Playwright** even though listings use it. Article pages are server-rendered; the `playwright=True` meta is only on listing requests.
- **CDX (Wayback) spiders are dead weight kept in tree** — IA times out on broad URL queries. Don't burn time on them.
- **Article-type classifier needs the listing's section, not the article HTML.** Express opinion articles' JSON-LD doesn't tag them as Opinion — only the listing URL (`/opinion`, `/editorial`) tells us. Spiders propagate via `meta["_listing_section"]`.
- **`scripts/keep_alive.sh`'s `is_running` regex** uses `[s]crapy crawl <name> ` (note the trailing space and `[s]` trick) so pgrep doesn't match its own argv. Don't simplify.
- **Docker image needs `procps` package.** Without it, `pgrep` is missing and `is_running` always returns false → duplicate spider spawns every 2 min.

## Files to read first (in order)

1. `CLAUDE.md` (this file) — high-level
2. `HANDOFF.md` — full deep-dive, decisions, resume checklist
3. `VPS_DEPLOY.md` — operate the VPS deployment
4. `articles_scraper/settings.py` — Scrapy config + `URDU_ONLY` toggle
5. `articles_scraper/pipelines.py` — pipeline order + `UrduOnlyPipeline`
6. `articles_scraper/spiders/section_base.py` — typical spider lifecycle
7. `config/events.yaml`, `config/sources.yaml` — what we track + how

## Resume checklist

When you sit down to work on this:

1. Read this file, then `HANDOFF.md`.
2. Confirm DB state: `sqlite3 data/articles.db "SELECT source, COUNT(*), article_type FROM articles GROUP BY 1, 3"`.
3. Run the Express opinion-tag test. Verify Opinion/Blog/Editorial counts grow above 0.
4. If the local test looks healthy → push to VPS (`rsync` + `docker compose up -d --build`) and let `keep_alive` run there.
5. To finalize: stop the scraper, run both backfill scripts, regenerate `exports/articles.csv` and `exports/report.html`.
