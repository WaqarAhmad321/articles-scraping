from __future__ import annotations

import logging
from typing import Iterable

import scrapy
from scrapy.http import Request, Response

from articles_scraper.spiders.section_base import BaseSectionSpider

log = logging.getLogger(__name__)


class DawnSpider(BaseSectionSpider):
    """Dawn discovery is hybrid:
       1) RSS feeds (server-rendered XML, fast, gives ~30 latest per topic)
       2) Section pages via Playwright (slower, but pages back into 2024)
    """

    name = "dawn"
    source_id = "dawn"
    article_url_pattern = r"/news/\d+/|/blogs/\d+/"

    RSS_FEEDS = [
        "https://www.dawn.com/feeds/home",
        "https://www.dawn.com/feeds/pakistan",
        "https://www.dawn.com/feeds/world",
        "https://www.dawn.com/feeds/opinion",
        "https://www.dawn.com/feeds/business",
        "https://www.dawn.com/feeds/newspaper",
        "https://www.dawn.com/feed/national",
    ]

    def start_requests(self) -> Iterable[Request]:
        # 1. Hit RSS feeds first (no JS, immediate yield).
        for feed in self.RSS_FEEDS:
            yield Request(feed, callback=self.parse_rss, dont_filter=True)
        # 2. Then walk section pages with Playwright (handled by base).
        yield from super().start_requests()

    def parse_rss(self, response: Response):
        # Dawn's RSS uses Atom-ish <link>https://...</link> tags. Article pages
        # are server-rendered HTML — DO NOT pass playwright meta here.
        for url in response.xpath("//link/text()").getall():
            url = url.strip()
            if not url or "/news/" not in url:
                continue
            if url in self._seen_urls:
                continue
            self._seen_urls.add(url)
            yield Request(url, callback=self.parse_article, priority=20)

    def _section_url(self, section: str, page: int) -> str:
        if page == 1:
            return f"https://www.dawn.com/{section}"
        return f"https://www.dawn.com/{section}?page={page}"
