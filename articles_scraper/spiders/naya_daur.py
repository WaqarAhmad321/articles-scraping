"""Naya Daur Urdu (urdu.nayadaur.tv) — politics + analysis harvest.

Only /politics is statically accessible. Individual articles tagged
article:section="تجزیہ" (analysis) get classified as Opinion; all others
fall to News Report and get filtered out by OpinionOnlyPipeline.
"""
from __future__ import annotations

from articles_scraper.spiders.section_base import BaseSectionSpider


class NayaDaurSpider(BaseSectionSpider):
    name = "naya_daur"
    source_id = "naya_daur"
    article_url_pattern = r"urdu\.nayadaur\.tv/\d{2}-[A-Za-z]+-\d{4}/\d+"
    skip_slug_filter = True  # date-based URLs have no event slug

    custom_settings = {
        "USER_AGENT": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _section_url(self, section: str, page: int) -> str:
        return f"https://urdu.nayadaur.tv/{section}"
