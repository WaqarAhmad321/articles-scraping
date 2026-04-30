# Pakistan News Scraper — Articles, Blogs & Opinions

Builds a structured dataset of Pakistani political news articles. Covers 17 events from January 2024 onwards (the 8 originally requested plus 9 expansion political topics) across 6 sources: **Dawn News, BBC Urdu, Express News, Geo News, ARY News, Abb Takk News**. (92 News blocks all programmatic access at the Cloudflare layer; no data captured.)

## Output schema

Each row in `data/articles.db` (table `articles`) and in CSV/JSONL exports has:

| column | description |
|---|---|
| `article_id` | `ART` + 8 hex chars of `sha1(url)` (stable across runs) |
| `headline` | Article title |
| `full_text` | Body text (cleaned) |
| `source` | Display name of the source |
| `author` | Byline if present, otherwise `NULL` |
| `date_published` | ISO `YYYY-MM-DD` |
| `url` | Canonical article URL |
| `category` | One of the tracked political events |
| `article_type` | `News Report` / `Opinion` / `Blog` / `Editorial` |
| `language` | `Urdu` or `English` (Unicode-script-ratio detection) |
| `word_count` | Whitespace-tokenised count |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium    # only needed for sources that use Playwright
cp .env.example .env           # set SCRAPER_CONTACT_EMAIL for the User-Agent
```

## Configure

- **`config/events.yaml`** — atomic Urdu+English keywords + URL-slug pre-filter tokens for each tracked event.
- **`config/sources.yaml`** — per-source: discovery method (sitemap / section / tag / RSS / ID-sweep), URL patterns, render mode, CSS selectors.

## Run

Smoke-test:

```bash
scrapy crawl abbtakk -a max_total=20 -a events=imran_trial
```

Run a single source:

```bash
scrapy crawl abbtakk -a max_total=2000
```

Run everything:

```bash
./scripts/run_all.sh
```

Spider arguments:

| arg | default | meaning |
|---|---|---|
| `events` | (all) | comma-separated event ids from `events.yaml` |
| `max_total` | 5000 | hard cap on items yielded by this run |

## Inspect

```bash
python scripts/stats.py
```

Produces a coverage matrix of source × category, plus per-language and top-author breakdowns.

## Export

```bash
python scripts/export.py --out exports/articles.csv
python scripts/export.py --out exports/gaza.jsonl --category "Gaza Conflict Coverage"
python scripts/export.py --out exports/dawn.csv --source "Dawn News"
```

## Tests

```bash
pytest tests/
```

## Architecture

The codebase has multiple discovery strategies because no single one works for every source. Each source uses whichever ones are usable:

| Strategy | Spider | Used by | When |
|---|---|---|---|
| **Sitemap walking** | `BaseSitemapSpider` | `abbtakk`, `bbc_urdu`, `express_sitemap` | Source has a per-article sitemap with `<lastmod>` and the date span we care about |
| **Section page walking** | `BaseSectionSpider` | `dawn`, `geo`, `ary`, `ninetytwo` | Source has paginated category/section pages that list articles |
| **Tag page walking** | `BaseTagListSpider` | `express` | Source exposes `/<tag-slug>` pages for topic-targeted listings |
| **RSS feed** | `DawnSpider`, `NinetyTwoSpider` | `dawn`, `ninetytwo` | Source publishes RSS — fast for recent content |
| **Sequential ID sweep** | `BaseIDSweepSpider` | `dawn_ids`, `geo_ids` | Article URLs use sequential numeric IDs (`/news/<id>/`); stride-sample the range |
| **CDX (Wayback)** | `BaseCDXSpider` | `dawn_cdx`, `express_cdx`, `geo_cdx`, `ary_cdx` | Historical content not reachable via the source's own discovery — ask Internet Archive's CDX index for known archived URLs |

After discovery, every spider funnels through the same article pipeline:

```
fetch → trafilatura body extraction
       → og:title / JSON-LD headline fallback (handles Dawn's JS-rendered h1)
       → meta[article:published_time] / JSON-LD datePublished fallback
       → relevance.match_event() against headline + first 2KB body
       → date_in_range filter
       → CleanText → Language → WordCount → ArticleType → ArticleId → SQLite
```

`relevance.match_event()` is case-insensitive substring matching against atomic Urdu+English keywords in `events.yaml`. URL-level pre-filter (`url_could_be_relevant`) skips obvious non-matches; opaque hash-style URLs (e.g. BBC's `/urdu/articles/c4gx7gj8vxeo`) pass through to the body match.

## Politeness & reliability

- `ROBOTSTXT_OBEY = True` — rejects any path the site disallows
- `AUTOTHROTTLE_ENABLED = True`, `DOWNLOAD_DELAY = 1.5s` baseline, randomized
- BBC: politer settings (4s delay, single concurrent request, browser UA)
- ARY/Geo: browser User-Agent (Cloudflare serves a different page to non-browser UAs)
- Article requests get `priority=10` so they jump ahead of newly-enqueued listings (otherwise the FIFO queue chokes on listing pages)
- HTTP cache enabled — re-runs reuse cached responses
- SQLite WAL mode — multiple spiders write concurrently without lock contention

## Known limits

- **92 News** — Cloudflare blocks all programmatic access. No data captured.
- **Geo News** — Geo's CDN refuses connections after ~200 fetches per session, capping yield via ID-sweep. Section walker works but only paginates ~6 months back.
- **Express News** — Tag pages mix recent + 2020-2022 articles, so most yield is from the sitemap-walker (`express_sitemap`).
- **BBC Urdu ToS** — BBC's `robots.txt` parser allows access (no Disallow directives), but their terms-of-use prose discourages scraping. Included here under the user's "any approach" mandate; remove the `bbc_urdu` config entry to exclude.
- **Date range** — Filter is 2024-01-01 → 2026-12-31, matching the user's "from 2024 to today" spec.
