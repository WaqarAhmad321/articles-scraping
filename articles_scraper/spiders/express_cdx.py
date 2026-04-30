from articles_scraper.spiders.cdx_base import BaseCDXSpider


class ExpressCDXSpider(BaseCDXSpider):
    name = "express_cdx"
    source_id = "express"
    cdx_patterns = ["express.pk/story/*"]
    article_url_pattern = r"express\.pk/story/\d+/"
