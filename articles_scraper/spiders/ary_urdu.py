"""ARY News Urdu edition (urdu.arynews.tv) — section walker + on-site search."""
from __future__ import annotations

from typing import Iterable
from urllib.parse import quote_plus

import yaml
from scrapy.http import Request

from articles_scraper.spiders.section_base import BaseSectionSpider, CONFIG_DIR


class AryUrduSpider(BaseSectionSpider):
    name = "ary_urdu"
    source_id = "ary_urdu"
    article_url_pattern = r"urdu\.arynews\.tv/[a-z0-9][a-z0-9-]+/?$"
    skip_slug_filter = True

    custom_settings = {
        "USER_AGENT": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
    }

    def _section_url(self, section: str, page: int) -> str:
        if page == 1:
            return f"https://urdu.arynews.tv/{section}/"
        return f"https://urdu.arynews.tv/{section}/page/{page}/"

    def _search_queries(self) -> list[str]:
        with open(CONFIG_DIR / "events.yaml") as f:
            events = yaml.safe_load(f)
        queries: list[str] = []
        for ev in events:
            queries.extend(ev.get("keywords_ur", [])[:3])
            queries.extend(ev.get("keywords_en", [])[:2])
        return queries

    def start_requests(self) -> Iterable[Request]:
        # On-site search by Urdu keywords first
        for q in self._search_queries():
            for page in range(1, 6):
                if page == 1:
                    url = f"https://urdu.arynews.tv/?s={quote_plus(q)}"
                else:
                    url = f"https://urdu.arynews.tv/page/{page}/?s={quote_plus(q)}"
                yield Request(url, callback=self.parse_listing,
                              meta=self._meta(section=f"search:{q}", page=page),
                              dont_filter=True)
        # Section walker
        yield from super().start_requests()
