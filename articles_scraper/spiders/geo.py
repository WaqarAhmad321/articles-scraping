"""Geo News — section walker plus on-site search by event keyword."""
from __future__ import annotations

from typing import Iterable
from urllib.parse import quote_plus

import yaml
from scrapy.http import Request

from articles_scraper.spiders.section_base import BaseSectionSpider, CONFIG_DIR


class GeoSpider(BaseSectionSpider):
    name = "geo"
    source_id = "geo"
    article_url_pattern = r"/latest/\d+-"
    skip_slug_filter = True

    custom_settings = {
        "USER_AGENT": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "DOWNLOAD_DELAY": 2.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

    def _section_url(self, section: str, page: int) -> str:
        if page == 1:
            return f"https://www.geo.tv/{section}"
        return f"https://www.geo.tv/{section}/page/{page}"

    def _search_queries(self) -> list[str]:
        with open(CONFIG_DIR / "events.yaml") as f:
            events = yaml.safe_load(f)
        queries: list[str] = []
        for ev in events:
            queries.extend(ev.get("keywords_en", [])[:3])
        return queries

    def start_requests(self) -> Iterable[Request]:
        # Search-based discovery (Geo's WP-style ?s=query)
        for q in self._search_queries():
            for page in range(1, 6):
                if page == 1:
                    url = f"https://www.geo.tv/?s={quote_plus(q)}"
                else:
                    url = f"https://www.geo.tv/page/{page}/?s={quote_plus(q)}"
                yield Request(url, callback=self.parse_listing,
                              meta=self._meta(section=f"search:{q}", page=page),
                              dont_filter=True)
        # Section walker
        yield from super().start_requests()
