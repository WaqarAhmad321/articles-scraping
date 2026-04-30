from articles_scraper.spiders.idsweep_base import BaseIDSweepSpider


class GeoIDSweepSpider(BaseIDSweepSpider):
    """Iterate Geo article IDs at /latest/<id>-<slug>. Recent ≈ 661800.
    Geo's CDN refuses connections after rapid bursts — keep the rate low."""

    name = "geo_ids"
    source_id = "geo"
    candidate_url_template = "https://www.geo.tv/latest/{id}-"
    id_min = 540000   # ~ early 2024
    id_max = 665000
    id_stride = 7   # sample every 7th — still ~18K candidates

    custom_settings = {
        "USER_AGENT": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        # Aggressive throttling — Geo CDN starts refusing connections under load.
        "DOWNLOAD_DELAY": 5.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 60.0,
        "RETRY_TIMES": 2,
    }
