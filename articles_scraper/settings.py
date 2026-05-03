import os
from pathlib import Path

BOT_NAME = "articles_scraper"

SPIDER_MODULES = ["articles_scraper.spiders"]
NEWSPIDER_MODULE = "articles_scraper.spiders"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = os.getenv("SCRAPER_DB_PATH", str(DATA_DIR / "articles.db"))
CONTACT_EMAIL = os.getenv("SCRAPER_CONTACT_EMAIL", "research@example.com")

USER_AGENT = (
    f"articles-scraping-research/0.1 (+contact: {CONTACT_EMAIL})"
)

ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 4
DOWNLOAD_DELAY = 1.5
RANDOMIZE_DOWNLOAD_DELAY = True
DOWNLOAD_TIMEOUT = 30

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 30.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 500, 502, 503, 504, 522, 524, 408]

HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 60 * 60 * 24 * 7
HTTPCACHE_DIR = str(PROJECT_ROOT / "httpcache")
HTTPCACHE_IGNORE_HTTP_CODES = [301, 302, 401, 403, 404, 500, 502, 503, 504]

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

LOG_LEVEL = "INFO"

# Toggle: when True, drop any article whose detected language != "Urdu".
URDU_ONLY = os.getenv("URDU_ONLY", "true").lower() not in ("0", "false", "no")

# Toggle: when True, drop article_type == "News Report" so the DB only
# accumulates Opinion / Blog / Editorial. Default off — local dev keeps news.
OPINION_ONLY = os.getenv("OPINION_ONLY", "false").lower() not in ("0", "false", "no")

ITEM_PIPELINES = {
    "articles_scraper.pipelines.CleanTextPipeline": 100,
    "articles_scraper.pipelines.RequiredFieldsPipeline": 150,
    "articles_scraper.pipelines.LanguagePipeline": 200,
    "articles_scraper.pipelines.UrduOnlyPipeline": 250,
    "articles_scraper.pipelines.WordCountPipeline": 300,
    "articles_scraper.pipelines.ArticleTypePipeline": 400,
    "articles_scraper.pipelines.OpinionOnlyPipeline": 450,
    "articles_scraper.pipelines.ArticleIdPipeline": 500,
    "articles_scraper.pipelines.SQLitePipeline": 900,
}

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {"headless": True}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60_000
# "load" waits for ALL subresources (ads, analytics) — too slow for news sites.
# "domcontentloaded" fires once HTML is parsed, which is enough to extract links.
PLAYWRIGHT_PAGE_GOTO_KWARGS = {"wait_until": "domcontentloaded"}
