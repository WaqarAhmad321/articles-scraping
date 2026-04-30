from __future__ import annotations

from typing import Iterable

from scrapy.http import Request, Response

from articles_scraper.spiders.section_base import BaseSectionSpider


class NinetyTwoSpider(BaseSectionSpider):
    """92 News blocks category-page scraping at Cloudflare; we use RSS feeds."""

    name = "ninetytwo"
    source_id = "ninetytwo"
    article_url_pattern = r"/[a-z0-9-]{15,}/?$"

    custom_settings = {
        "USER_AGENT": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def start_requests(self) -> Iterable[Request]:
        for feed in self.cfg.get("rss_feeds", []):
            yield Request(feed, callback=self.parse_rss, dont_filter=True)

    def parse_rss(self, response: Response):
        # WP RSS uses <link>https://...</link>
        for url in response.xpath("//link/text()").getall():
            url = url.strip()
            if not url or "92newshd.tv" not in url:
                continue
            if not self._article_re.search(url):
                continue
            if url in self._seen_urls:
                continue
            self._seen_urls.add(url)
            yield Request(url, callback=self.parse_article, priority=20)
