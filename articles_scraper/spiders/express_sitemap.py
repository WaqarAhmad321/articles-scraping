"""Express News via sub-sitemaps. Each sub-sitemap has 5000 URLs with lastmod.
Express slugs are transliterated Urdu, so the URL slug pre-filter rejects too
many real articles. We rely on the body-level relevance match instead."""
from articles_scraper.spiders.sitemap_base import BaseSitemapSpider


class ExpressSitemapSpider(BaseSitemapSpider):
    name = "express_sitemap"
    source_id = "express_sitemap"
    article_url_pattern = r"/story/\d+/"
    skip_slug_filter = True  # Urdu transliteration won't match English slug keywords
