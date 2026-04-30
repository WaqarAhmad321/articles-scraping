from articles_scraper.spiders.cdx_base import BaseCDXSpider


class DawnCDXSpider(BaseCDXSpider):
    name = "dawn_cdx"
    source_id = "dawn"
    cdx_patterns = ["dawn.com/news/*", "dawn.com/blogs/*"]
    article_url_pattern = r"dawn\.com/(news|blogs)/\d+/"
