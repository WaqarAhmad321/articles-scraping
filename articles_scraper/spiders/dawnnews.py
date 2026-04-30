"""Dawn News TV (dawnnews.tv) — Dawn's Urdu news platform."""
from articles_scraper.spiders.section_base import BaseSectionSpider


class DawnNewsSpider(BaseSectionSpider):
    name = "dawnnews"
    source_id = "dawnnews"
    article_url_pattern = r"dawnnews\.tv/news/\d+/"
    skip_slug_filter = True

    custom_settings = {
        "USER_AGENT": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _section_url(self, section: str, page: int) -> str:
        if page == 1:
            return f"https://www.dawnnews.tv/{section}"
        return f"https://www.dawnnews.tv/{section}?page={page}"
