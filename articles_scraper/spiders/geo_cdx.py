from articles_scraper.spiders.cdx_base import BaseCDXSpider


class GeoCDXSpider(BaseCDXSpider):
    name = "geo_cdx"
    source_id = "geo"
    cdx_patterns = ["geo.tv/latest/*"]
    article_url_pattern = r"geo\.tv/latest/\d+-"

    custom_settings = {
        "USER_AGENT": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
