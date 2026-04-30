from articles_scraper.spiders.idsweep_base import BaseIDSweepSpider


class DawnIDSweepSpider(BaseIDSweepSpider):
    """Iterate Dawn article IDs. Recent (April 2026) IDs ≈ 1995000.
    Approximate ID-to-year mapping: 2024 ≈ 1700000-1900000, 2025 ≈ 1900000-1970000."""

    name = "dawn_ids"
    source_id = "dawn"
    candidate_url_template = "https://www.dawn.com/news/{id}/"
    id_min = 1700000
    id_max = 1995000
    id_stride = 5  # sample every 5th ID — about 60K fetches
