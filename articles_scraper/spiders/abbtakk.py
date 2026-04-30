from articles_scraper.spiders.sitemap_base import BaseSitemapSpider


class AbbTakkSpider(BaseSitemapSpider):
    name = "abbtakk"
    source_id = "abbtakk"
    # Abb Takk articles are slug-based: /<slug>/  Avoid hitting category/tag pages.
    article_url_pattern = r"abbtakk\.tv/[a-z0-9-]+/?$"

    def _looks_like_article(self, url: str) -> bool:
        # Belt-and-suspenders: filter out obvious non-articles
        bad = ("/category/", "/tag/", "/author/", "/sitemap", "/wp-")
        return not any(b in url for b in bad)
