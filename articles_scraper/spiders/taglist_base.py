"""Tag-page-based discovery for sources that have topic landing pages.

For Express, https://www.express.pk/<tag-slug> returns a paginated listing of
stories tagged with that topic. Higher-precision than walking sub-sitemaps
when the tag set is curated for the events we care about.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import scrapy
import yaml
from scrapy.http import Request, Response

from articles_scraper.extractors import extract
from articles_scraper.items import ArticleItem
from articles_scraper.relevance import EventDef, load_events, match_event, url_could_be_relevant
from articles_scraper.utils.article_type import classify_article_type
from articles_scraper.utils.dates import in_range, parse_date

log = logging.getLogger(__name__)
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def load_yaml(name: str):
    with open(CONFIG_DIR / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class BaseTagListSpider(scrapy.Spider):
    """Subclasses provide:
      - source_id (key in sources.yaml)
      - tag_pages (list of relative tag URLs)
      - article_url_pattern (regex for the source's article URLs)
      - _tag_page_url(tag, page) → full URL with pagination
    """

    source_id: str = ""
    DATE_FROM = "2024-01-01"
    DATE_TO = "2026-12-31"
    article_url_pattern: str = r"."
    tag_pages_per_tag: int = 50  # how many pagination pages to walk per tag
    DEFAULT_MAX_TOTAL = 5000

    def __init__(self, max_total: int | None = None, events: str | None = None, *a, **kw):
        super().__init__(*a, **kw)
        sources = load_yaml("sources.yaml")
        self.cfg = sources[self.source_id]
        self.allowed_domains = list(self.cfg.get("allowed_domains", []))
        all_events = load_yaml("events.yaml")
        if events:
            wanted = set(events.split(","))
            all_events = [e for e in all_events if e["id"] in wanted]
        self.events: list[EventDef] = load_events(all_events)
        self.max_total = int(max_total) if max_total else self.DEFAULT_MAX_TOTAL
        self._yielded = 0
        self._seen_urls: set[str] = set()
        self._article_re = re.compile(self.article_url_pattern)
        self.base_url = f"https://{self.allowed_domains[0]}"

    def _meta(self, **extra) -> dict:
        meta = dict(extra)
        if self.cfg.get("render") == "playwright":
            meta["playwright"] = True
            meta["playwright_page_goto_kwargs"] = {"wait_until": "domcontentloaded"}
        return meta

    def _tag_page_url(self, tag: str, page: int) -> str:
        if page == 1:
            return f"{self.base_url}/{tag}"
        return f"{self.base_url}/{tag}?page={page}"

    def start_requests(self) -> Iterable[Request]:
        tags = self.cfg.get("tag_pages", [])
        for tag in tags:
            for page in range(1, self.tag_pages_per_tag + 1):
                yield Request(
                    self._tag_page_url(tag, page),
                    callback=self.parse_tag_page,
                    meta=self._meta(tag=tag, page=page),
                    dont_filter=True,
                )

    def parse_tag_page(self, response: Response):
        if self._yielded >= self.max_total:
            return
        hrefs = set()
        for h in response.css("a::attr(href)").getall():
            if not h:
                continue
            absu = urljoin(response.url, h).split("#")[0]
            if not urlparse(absu).netloc.endswith(tuple(self.allowed_domains)):
                continue
            if self._article_re.search(absu):
                hrefs.add(absu)
        log.info("%s: tag '%s' p%d → %d candidate articles",
                 self.source_id, response.meta.get("tag"), response.meta.get("page"), len(hrefs))

        for url in hrefs:
            if url in self._seen_urls:
                continue
            self._seen_urls.add(url)
            # priority>0 → jumps the FIFO queue ahead of newly enqueued tag pages.
            # Article pages don't need Playwright even when listing pages do.
            # Pass the tag down so the article-type classifier can see whether
            # this article was harvested from /opinion, /editorial, /blog, etc.
            yield Request(url, callback=self.parse_article, priority=10,
                          meta={"_listing_section": response.meta.get("tag")})
            if self._yielded >= self.max_total:
                return

    def parse_article(self, response: Response):
        if self._yielded >= self.max_total:
            return
        ext = extract(response, self.cfg.get("selectors", {}))
        if not ext.full_text or len(ext.full_text) < 200:
            return
        if not ext.headline:
            return
        date_iso = ext.date_published
        if not date_iso:
            return
        if not in_range(date_iso, self.DATE_FROM, self.DATE_TO):
            return
        ev = match_event(ext.headline, ext.full_text, self.events)
        if ev is None:
            return
        if not in_range(date_iso, ev.date_from, ev.date_to):
            return

        item = ArticleItem(
            headline=ext.headline,
            full_text=ext.full_text,
            source=self.cfg["display_name"],
            author=ext.author,
            date_published=date_iso,
            url=response.url,
            category=ev.category,
            article_type=classify_article_type(
                response.url,
                response.meta.get("_listing_section") or ext.section,
            ),
            language=None,
            word_count=None,
        )
        self._yielded += 1
        yield item
