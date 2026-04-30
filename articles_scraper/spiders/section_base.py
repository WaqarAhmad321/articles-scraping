"""Section-archive walker for sources without usable sitemaps.

Walks /<section>?page=1..N (or equivalent) listing pages, collects article
URLs, then runs the same article-fetch + relevance-match flow as the
sitemap spider. Subclasses can override `_section_url(section, page)` for
sites that use a different pagination scheme.
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


class BaseSectionSpider(scrapy.Spider):
    source_id: str = ""
    DATE_FROM = "2024-01-01"
    DATE_TO = "2026-12-31"
    article_url_pattern: str = r"."

    DEFAULT_MAX_TOTAL = 5000

    def __init__(self, max_total: int | None = None, events: str | None = None, *a, **kw):
        super().__init__(*a, **kw)
        sources = load_yaml("sources.yaml")
        if self.source_id not in sources:
            raise ValueError(f"Source {self.source_id!r} not in sources.yaml")
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
            # `domcontentloaded` returns once HTML is parsed (~1-3s) instead of
            # waiting for every ad/analytics resource (which can take 60s+).
            meta["playwright_page_goto_kwargs"] = {"wait_until": "domcontentloaded"}
        return meta

    def _section_url(self, section: str, page: int) -> str:
        # Default scheme: /section/?page=N (Dawn) or /<section>/page/N (WordPress)
        # Subclasses override for other schemes.
        if page == 1:
            return f"{self.base_url}/{section}"
        return f"{self.base_url}/{section}?page={page}"

    def start_requests(self) -> Iterable[Request]:
        sections = self.cfg.get("section_pages", [])
        max_pages = int(self.cfg.get("section_pages_max", 30))
        for section in sections:
            for page in range(1, max_pages + 1):
                url = self._section_url(section, page)
                yield Request(
                    url,
                    callback=self.parse_listing,
                    meta=self._meta(section=section, page=page),
                    dont_filter=True,
                )

    def parse_listing(self, response: Response):
        if self._yielded >= self.max_total:
            return
        # Collect candidate article hrefs from anywhere on the page; filter via regex.
        hrefs = set()
        for h in response.css("a::attr(href)").getall():
            if not h:
                continue
            absu = urljoin(response.url, h)
            if urlparse(absu).netloc.endswith(tuple(self.allowed_domains)) and self._article_re.search(absu):
                clean = absu.split("#")[0]
                # Subclasses can opt-out of slug pre-filter (helpful for sites
                # whose article slugs aren't English-aligned with our keywords)
                if getattr(self, "skip_slug_filter", False) or url_could_be_relevant(clean, self.events):
                    hrefs.add(clean)

        section = response.meta.get("section")
        page = response.meta.get("page")
        log.info("%s: listing %s p%d → %d candidate articles",
                 self.source_id, section, page, len(hrefs))

        for url in hrefs:
            if url in self._seen_urls:
                continue
            self._seen_urls.add(url)
            # Article pages are server-rendered HTML even on JS-heavy listing
            # sites — skip Playwright for articles to avoid 30s navigation
            # timeouts and reduce browser load.
            yield Request(
                url,
                callback=self.parse_article,
                priority=10,
                meta={"_listing_section": response.meta.get("section")},
            )
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
