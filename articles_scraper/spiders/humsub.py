"""Humsub (humsub.com.pk) — Urdu opinion / column / blog harvest.

Digital-only Urdu opinion outlet. Two main listings used:
  - /category/columns/  — political/social columnists
  - /category/blog/     — guest blogs

Both paginate WordPress-style at /<section>/page/<N>/.
Article URLs look like https://www.humsub.com.pk/<id>/<slug>/.
"""
from __future__ import annotations

from articles_scraper.spiders.section_base import BaseSectionSpider


class HumsubSpider(BaseSectionSpider):
    name = "humsub"
    source_id = "humsub"
    article_url_pattern = r"humsub\.com\.pk/\d+/[a-zA-Z0-9-]+/?$"
    skip_slug_filter = True  # Humsub slugs are author-name based, not topic

    custom_settings = {
        "USER_AGENT": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _section_url(self, section: str, page: int) -> str:
        if page == 1:
            return f"https://www.humsub.com.pk/{section}/"
        return f"https://www.humsub.com.pk/{section}/page/{page}/"
