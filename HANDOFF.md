# Pakistan News Scraper — HANDOFF

> **For: future-you, or another Claude Code session.** Read this first. It captures what we're building, where we are, what's running, what's not, and what to do next.

Last updated: **2026-04-30 (post Express opinion-tag test)**

---

## 1. The goal

Build a structured dataset of **Pakistani political reportage in Urdu** from 2024-01-01 onward. Output is a SQLite table + CSV with this schema:

| column | description |
|---|---|
| `article_id` | `ART` + 8 hex chars of `sha1(url)` |
| `headline` | title |
| `full_text` | trafilatura-extracted body |
| `source` | display name |
| `author` | byline (or `NULL`) |
| `date_published` | ISO `YYYY-MM-DD` |
| `url` | canonical |
| `category` | one of 18 tracked political events |
| `article_type` | `News Report` / `Opinion` / `Blog` / `Editorial` |
| `language` | `Urdu` (English is filtered out by pipeline) |
| `word_count` | whitespace-tokenised |

The user wants the dataset:
- **Urdu-only** — `URDU_ONLY=true` is the default in `articles_scraper/settings.py`. The pipeline drops English-detected articles before SQLite write.
- **Political topics only** — `config/events.yaml` lists 18 events. Each spider's `parse_article` runs `relevance.match_event()` and drops anything that doesn't match a tracked event keyword set.
- **Date-bounded** — `DATE_FROM=2024-01-01`, `DATE_TO=2026-12-31` (set on each base-spider class). Anything older is dropped.
- **Diverse `article_type`** — recently expanded to include opinion/column/blog/editorial sections (see § 4 below).

---

## 2. Where we are right now

**Local DB:** `data/articles.db` — **9,135 articles, all Urdu, all 18 categories represented.**

| source | count |
|---|---|
| Express News | 4,410 |
| BBC Urdu | 2,506 |
| ARY News (Urdu) | 2,129 |
| Dawn News (Urdu) | 89 |
| Abb Takk News | 1 |

`article_type` breakdown: News Report 9,127 · Opinion 6 · Blog 2 · Editorial 0.

**Author coverage: 99.98%** (9,133 of 9,135 — only 2 Express stragglers genuinely have no byline). BBC Urdu's 2,506 authors were backfilled from JSON-LD via `scripts/backfill_authors.py`.

**Latest exports:**
- `exports/articles.csv` — 57 MB, 9,135 rows
- `exports/report.html` — editorial-style HTML report

**Nothing is running.** Local keep_alive killed; VPS container stopped.

---

## 3. Architecture in one screen

```
        ┌───────────────────────────────────────────┐
        │  config/events.yaml      (18 topics)      │
        │  config/sources.yaml     (per-source cfg) │
        └──────────────┬────────────────────────────┘
                       │ (read at spider __init__)
        ┌──────────────▼────────────────────────────────────────────┐
        │  Spiders (each chooses one discovery strategy)            │
        │                                                           │
        │  BaseSitemapSpider   → express_sitemap, bbc_urdu, abbtakk │
        │  BaseSectionSpider   → dawnnews, ary_urdu, ary, geo, dawn │
        │  BaseTagListSpider   → express                            │
        │  BaseIDSweepSpider   → dawn_ids, geo_ids                  │
        │  BaseCDXSpider       → *_cdx (Wayback Machine, off)       │
        └──────────────┬────────────────────────────────────────────┘
                       │ yield ArticleItem(...)
        ┌──────────────▼─────────────────────────────────────┐
        │  Pipeline (articles_scraper/pipelines.py)          │
        │   1. CleanTextPipeline    — strip whitespace       │
        │   2. RequiredFieldsPipeline                        │
        │   3. LanguagePipeline     — detect Urdu vs English │
        │   4. UrduOnlyPipeline     — drop if not Urdu       │
        │   5. WordCountPipeline                             │
        │   6. ArticleTypePipeline  — News/Opinion/Blog/Edit │
        │   7. ArticleIdPipeline    — sha1(url)              │
        │   8. SQLitePipeline       — INSERT OR IGNORE       │
        └────────────────────────────────────────────────────┘
```

Inside each spider's `parse_article`:
```
extract(response, selectors)        # trafilatura body + meta/JSON-LD fallbacks
   ↓
require headline + body ≥ 200 chars + date in [DATE_FROM, DATE_TO]
   ↓
relevance.match_event(headline, body, events)   # drop if no political match
   ↓
classify_article_type(url, section)             # recently improved (see § 4)
   ↓
yield ArticleItem(...)
```

---

## 4. Open work — opinion / blog / editorial coverage

We just finished plumbing this through, but **never finished a full crawl with the new code.**

### What's already done (committed)
- `articles_scraper/utils/article_type.py` — classifier now recognises Urdu markers (`کالم`, `اداریہ`, `بلاگ`, `رائے`, `نقطہ نظر`) in addition to English.
- `articles_scraper/extractors.py` — `extract()` now also reads JSON-LD `articleSection` and returns it as `Extracted.section`.
- All three spider bases now pass `_listing_section` (the originating tag/category) through `request.meta` and feed it to `classify_article_type()` — this is critical because individual article HTML rarely tags itself as Opinion.
- `config/sources.yaml` — Express, DawnNews, ARY-Urdu now include their opinion/column/editorial section paths:
  - **Express tag_pages**: `opinion`, `opinion/blog`, `blog`, `editorial`, `category/opinion`, `category/editorial`, `category/blogs`
  - **DawnNews section_pages**: `opinions`, `opinions/columnist`, `opinions/editorial`, `opinions/features`
  - **ARY-Urdu section_pages**: `category/urdu-blogs`, `category/blog`, `category/blogs`
- `scripts/backfill_article_type.py` — re-classifies existing rows from cached responses (already run; only 2 reclassifications because old data was all from news sections).

### What's left
1. **Run a focused local test** (Express opinion tags, ~10 min) to verify the classifier produces real Opinion / Blog / Editorial counts. The previous attempt was killed mid-way before producing many items.
2. **If local looks healthy → push to VPS and run there.** See § 5 for VPS commands.

### How to resume the test
```bash
cd /home/waqardev/Work/client-projects/articles-scraping
# kills any leftover, runs Express against opinion/blog/editorial tags only:
nohup .venv/bin/scrapy crawl express -a max_total=400 \
  > /tmp/express_opinion_test.log 2>&1 &
disown
# watch:
sqlite3 data/articles.db "SELECT article_type, COUNT(*) FROM articles GROUP BY 1"
```
Expect to see Opinion / Blog / Editorial counts climb (they were 6 / 2 / 0 before).

---

## 5. VPS deployment — current state

**VPS:** `root@69.55.49.66` (DigitalOcean droplet, Ubuntu 24.04).
**Project path:** `/opt/pk-scraper/`
**Current container:** STOPPED. Was running fine before user asked us to stop.

### Files on the VPS (rsynced)
The full project tree is at `/opt/pk-scraper/` minus:
- `.venv` (image installs deps globally)
- `data/`, `exports/`, `httpcache/` (Docker volumes hold these)
- `.git`, `__pycache__`, `.claude`

### How to start/stop the VPS scraper

```bash
# Push current code (run from your laptop):
rsync -avz --delete \
  --exclude '.venv' --exclude 'data' --exclude 'exports' \
  --exclude 'httpcache' --exclude '.git' --exclude '__pycache__' \
  --exclude '.claude' --exclude '*.pyc' \
  ./ root@69.55.49.66:/opt/pk-scraper/

# Start (rebuild image + launch container):
ssh root@69.55.49.66 'cd /opt/pk-scraper && docker compose up -d --build'

# Watch logs:
ssh root@69.55.49.66 'cd /opt/pk-scraper && docker compose logs -f scraper'

# Quick status:
ssh root@69.55.49.66 'docker exec pk-scraper sqlite3 data/articles.db \
    "SELECT source, COUNT(*) FROM articles GROUP BY 1; SELECT article_type, COUNT(*) FROM articles GROUP BY 1"'

# Pull the dataset down:
rsync -avz root@69.55.49.66:/opt/pk-scraper/exports/articles.csv ./
rsync -avz root@69.55.49.66:/opt/pk-scraper/data/articles.db ./

# Stop:
ssh root@69.55.49.66 'cd /opt/pk-scraper && docker compose down'
```

### Important VPS-specific notes
- **Inside the container scrapy lives at `/usr/local/bin/scrapy`**, not `.venv/bin/scrapy`. `scripts/keep_alive.sh` auto-detects which to use — don't hardcode.
- **Container needs `procps` package** (for `pgrep`). It's installed via `Dockerfile` apt list. Without it, `keep_alive`'s `is_running` check would always return false and spawn duplicate spiders forever.
- **Resource cap:** 1.5 GB RAM, 1.5 CPU in `docker-compose.yml`. Recommend the **DigitalOcean $12/mo plan** (2 GB RAM); $4 plan OOM-kills under Playwright load.

### What `keep_alive.sh` actually does
- Every 2 min it checks `data/articles.db` for each spider's row count.
- If a spider is below its target AND no live process is running for it → it relaunches the spider.
- Every 15 min it runs `scripts/export.py` to refresh `exports/articles.csv`.
- Survives container restarts (`restart: unless-stopped` in compose).

Spider list and per-spider targets are at the top of `scripts/keep_alive.sh` in the `SPIDERS` array.

---

## 6. Source-by-source notes

| Source | Status | Discovery | Notes |
|---|---|---|---|
| **Express News** | strong (4,410) | tag pages + sub-sitemaps | Urdu edition. `skip_slug_filter=True` because slugs are Urdu transliterations. Just added opinion/blog/editorial tags — needs a fresh run to fill those. |
| **BBC Urdu** | strong (2,506) | archive sitemaps (100-118) | All Urdu by definition. Politer settings (4s delay, single concurrent, browser UA) — they refuse connections under load. Authors live in JSON-LD only — backfill done. |
| **ARY News (Urdu)** | mid (2,129) | `urdu.arynews.tv` section walk + on-site search | Mostly responding well. Browser UA required. |
| **Dawn News (Urdu)** | weak (89) | `dawnnews.tv` section walk via Playwright | JS-heavy site. Just added opinion sections — needs a fresh run. |
| **Abb Takk** | broken (1) | sitemap | Most content is English; URDU_ONLY drops it. Keep around for the rare Urdu piece. |
| **92 News** | impossible (0) | — | Cloudflare-blocks all programmatic access including RSS. No path. |
| **Geo (English)** | filtered (0) | — | Returns English only; URDU_ONLY drops everything. |
| **Dawn (English)** | filtered (0) | — | Same — URDU_ONLY filter eats it. Kept in keep_alive list as cheap insurance for any rare Urdu piece. |
| **ARY (English)** | filtered (0) | — | Same. |

---

## 7. Files to know

```
articles_scraper/
├── settings.py             — Scrapy settings (incl. URDU_ONLY toggle)
├── pipelines.py            — UrduOnlyPipeline + 7 others
├── extractors.py           — trafilatura + meta/JSON-LD fallbacks (headline, author, date, section)
├── relevance.py            — match_event() + url_could_be_relevant()
├── utils/
│   ├── article_type.py     — News/Opinion/Blog/Editorial classifier (EN + UR markers)
│   ├── article_id.py       — sha1-based stable IDs
│   ├── language.py         — Unicode-script ratio (Urdu vs English)
│   └── dates.py
└── spiders/
    ├── sitemap_base.py     — BaseSitemapSpider
    ├── section_base.py     — BaseSectionSpider (passes _listing_section through meta)
    ├── taglist_base.py     — BaseTagListSpider
    ├── idsweep_base.py     — BaseIDSweepSpider
    ├── cdx_base.py         — BaseCDXSpider (Wayback CDX; not in active rotation)
    ├── express.py + express_sitemap.py
    ├── bbc_urdu.py
    ├── abbtakk.py
    ├── dawn.py + dawn_ids.py + dawnnews.py
    ├── ary.py + ary_urdu.py
    └── geo.py + geo_ids.py + ninetytwo.py

config/
├── events.yaml             — 18 political topics × bilingual keywords
└── sources.yaml            — per-source: discovery method, URL patterns, render mode, selectors

scripts/
├── keep_alive.sh           — self-healing parallel runner (used in Docker too)
├── export.py               — DB → CSV/JSONL (--source, --category, --language filters)
├── stats.py                — coverage matrix
├── report.py               — editorial-style HTML report
├── backfill_authors.py     — re-extract authors from cached HTML
└── backfill_article_type.py — re-classify article_type from cache

Dockerfile                  — Python 3.12 + Chromium + procps
docker-compose.yml          — restart:unless-stopped, 1.5GB cap, persistent volumes
VPS_DEPLOY.md               — deploy/operate playbook
HANDOFF.md                  — this file
```

---

## 8. Common operations

```bash
# Smoke test one source × one event:
.venv/bin/scrapy crawl express -a max_total=20 -a events=imran_trial

# Run one source autonomously (used by keep_alive):
.venv/bin/scrapy crawl bbc_urdu -a max_total=5000

# Coverage report:
.venv/bin/python scripts/stats.py

# Refresh exports:
.venv/bin/python scripts/export.py --out exports/articles.csv
.venv/bin/python scripts/report.py

# Per-source CSV:
.venv/bin/python scripts/export.py --out exports/express.csv --source "Express News"
.venv/bin/python scripts/export.py --out exports/gaza.jsonl --category "Gaza Conflict Coverage"

# Backfills (idempotent — safe to re-run):
.venv/bin/python scripts/backfill_authors.py --source "BBC Urdu"
.venv/bin/python scripts/backfill_article_type.py

# Run all spiders in parallel locally (auto-restarting):
nohup bash scripts/keep_alive.sh > /tmp/keep_alive.log 2>&1 & disown

# Stop all spiders + keep_alive:
pkill -f keep_alive.sh
for pid in $(pgrep -f "[.]venv/bin/scrapy crawl"); do kill -9 "$pid"; done
```

---

## 9. Decisions & rationale (why things look the way they do)

- **Urdu-only is a pipeline toggle, not a per-source thing.** Cleaner: any source can theoretically yield Urdu, the pipeline decides.
- **`skip_slug_filter` flag on spiders for Express + ARY-Urdu** — their URL slugs are Urdu transliterations (e.g. `pakstan-myn-asmart-fwn-ky-frwkht`), so the English slug-keyword pre-filter rejected too many real articles. Body-level matching takes over for them.
- **`_listing_section` meta-passing** — added because individual article pages (especially Express, ARY-Urdu) don't carry section info in their HTML or JSON-LD. The spider knows which listing it crawled from, so we propagate that downstream.
- **Article requests yielded with `priority=10`** — the FIFO scheduler would otherwise drown article fetches under newly-yielded listing fetches.
- **WAL mode + 30s timeout on SQLite** — needed when 8 spiders write concurrently from inside one container.
- **Scrapy CSS `meta[property=...]::attr(content)` works for og:title** — important fallback because Dawn renders `<h1>` via JS (server HTML has only meta).
- **CDX (Wayback) approach was abandoned** — IA's CDX server times out on broad wildcard queries. Spiders left in-tree but not in the keep_alive rotation.

---

## 10. Known issues / gotchas

- `scripts/keep_alive.sh`'s `is_running` check uses `pgrep -f "[s]crapy crawl <name> "` (note the space). Removing the space causes it to match its own argv. Don't change the format without understanding why.
- The Docker image base is `python:3.12-slim-bookworm`. **Must include `procps`** in apt installs — keep_alive depends on `pgrep`.
- DawnNews uses Playwright for listings; **article fetches deliberately skip Playwright** (server-rendered) — see `BaseSectionSpider.parse_listing` where article requests are yielded without the `playwright=True` meta.
- Geo and ARY (English) are kept in keep_alive's spider list deliberately — they cost ~nothing and occasionally surface a stray Urdu piece. They contribute 0 only because the pipeline filter is doing its job.

---

## 11. Resume checklist (next session)

1. Read this file. Confirm where the DB stands (`sqlite3 data/articles.db "SELECT source, COUNT(*), article_type FROM articles GROUP BY 1, 3"`).
2. Run a focused Express opinion-tag test (§ 4 above). Verify Opinion/Blog/Editorial counts climb above 0.
3. If healthy, push to VPS (§ 5) and run there with `keep_alive` in background.
4. Pull final CSV and regenerate `report.html` periodically.
5. To finalize: stop scraper, run `scripts/backfill_authors.py` and `scripts/backfill_article_type.py` once more, regenerate exports, hand back.
