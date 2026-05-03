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
        # Section walker only — search loop disabled because keyword search
        # returns mostly news, not opinion/column/blog articles. Opinion
        # harvesting relies entirely on the curated section_pages list.
        yield from super().start_requests()
