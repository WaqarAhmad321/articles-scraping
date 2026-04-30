"""ARY News — combine RSS + section walking + on-site search by event keyword."""
from __future__ import annotations

from typing import Iterable
from urllib.parse import quote_plus

import yaml
from scrapy.http import Request, Response

from articles_scraper.spiders.section_base import BaseSectionSpider, CONFIG_DIR


class ArySpider(BaseSectionSpider):
    name = "ary"
    source_id = "ary"
    article_url_pattern = r"arynews\.tv/[a-z0-9][a-z0-9-]+/?$"
    skip_slug_filter = True  # ARY articles vary widely; let body match decide

    custom_settings = {
        "USER_AGENT": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_TIMEOUT": 30,
    }

    RSS_FEEDS = [
        "https://arynews.tv/feed/",
        "https://arynews.tv/category/pakistan/feed/",
        "https://arynews.tv/category/business/feed/",
        "https://arynews.tv/category/world/feed/",
        "https://arynews.tv/category/regional/feed/",
        "https://arynews.tv/category/middle-east/feed/",
    ]

    def _section_url(self, section: str, page: int) -> str:
        if page == 1:
            return f"https://arynews.tv/{section}/"
        return f"https://arynews.tv/{section}/page/{page}/"

    def _search_queries(self) -> list[str]:
        # Use event keywords as on-site search queries; ARY's `?s=` returns
        # a paginated topic page that's usually very different from the
        # categorical pagination, exposing more political articles.
        with open(CONFIG_DIR / "events.yaml") as f:
            events = yaml.safe_load(f)
        queries: list[str] = []
        for ev in events:
            queries.extend(ev.get("keywords_en", [])[:3])
        return queries

    def start_requests(self) -> Iterable[Request]:
        # 1. RSS first (fast, recent)
        for feed in self.RSS_FEEDS:
            yield Request(feed, callback=self.parse_rss, dont_filter=True)
        # 2. On-site search per event keyword
        for q in self._search_queries():
            for page in range(1, 6):  # 5 pages per query
                if page == 1:
                    url = f"https://arynews.tv/?s={quote_plus(q)}"
                else:
                    url = f"https://arynews.tv/page/{page}/?s={quote_plus(q)}"
                yield Request(url, callback=self.parse_listing,
                              meta=self._meta(section=f"search:{q}", page=page),
                              dont_filter=True)
        # 3. Section walker (existing)
        yield from super().start_requests()

    def parse_rss(self, response: Response):
        for url in response.xpath("//link/text()").getall():
            url = url.strip()
            if not url or "arynews.tv" not in url:
                continue
            if not self._article_re.search(url):
                continue
            if url in self._seen_urls:
                continue
            self._seen_urls.add(url)
            yield Request(url, callback=self.parse_article, priority=20)
