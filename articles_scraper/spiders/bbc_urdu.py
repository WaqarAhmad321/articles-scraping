from articles_scraper.spiders.sitemap_base import BaseSitemapSpider


class BBCUrduSpider(BaseSitemapSpider):
    name = "bbc_urdu"
    source_id = "bbc_urdu"
    article_url_pattern = r"/urdu/(articles/|pakistan-|world-|regional-|sport-|science-|entertainment-)"

    # BBC will start refusing connections under load. Throttle aggressively
    # and use a browser-style User-Agent — they accept that better than ours.
    custom_settings = {
        "DOWNLOAD_DELAY": 4.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 60.0,
        "USER_AGENT": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
