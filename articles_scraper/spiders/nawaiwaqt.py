"""Nawa-i-Waqt (nawaiwaqt.com.pk) — Urdu daily, op-ed / editorials harvest.

Walks 5 sections that all expose article:section="رائے" on individual posts:
  /columns /editorials /adarate-mazameen /mazamine /letters

Pagination is JS-driven; section_pages_max=1 in sources.yaml.
"""
from __future__ import annotations

from articles_scraper.spiders.section_base import BaseSectionSpider


class NawaiwaqtSpider(BaseSectionSpider):
    name = "nawaiwaqt"
    source_id = "nawaiwaqt"
    article_url_pattern = r"nawaiwaqt\.com\.pk/\d{2}-[A-Za-z]+-\d{4}/\d+"
    skip_slug_filter = True  # date-based URLs have no event slug

    custom_settings = {
        "USER_AGENT": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _section_url(self, section: str, page: int) -> str:
        return f"https://www.nawaiwaqt.com.pk/{section}"
