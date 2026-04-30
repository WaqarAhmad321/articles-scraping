from articles_scraper.spiders.cdx_base import BaseCDXSpider


class AryCDXSpider(BaseCDXSpider):
    name = "ary_cdx"
    source_id = "ary"
    cdx_patterns = ["arynews.tv/*"]
    article_url_pattern = r"arynews\.tv/[a-z0-9][a-z0-9-]+/?$"

    custom_settings = {
        "USER_AGENT": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
