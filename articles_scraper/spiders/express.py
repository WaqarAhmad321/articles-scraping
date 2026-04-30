from articles_scraper.spiders.taglist_base import BaseTagListSpider


class ExpressSpider(BaseTagListSpider):
    name = "express"
    source_id = "express"
    article_url_pattern = r"/story/\d+/"
    tag_pages_per_tag = 30

    # Express's opinion/blog/editorial sections live at /opinion, /blog,
    # /editorial. Adding them here makes the spider walk those listings the
    # same way it walks /imran-khan, /pti, etc.
    OPINION_TAGS = [
        "opinion",
        "opinion/blog",
        "blog",
        "editorial",
        "category/opinion",
        "category/editorial",
        "category/blogs",
    ]

    def _tag_page_url(self, tag: str, page: int) -> str:
        if page == 1:
            return f"https://www.express.pk/{tag}"
        return f"https://www.express.pk/{tag}?page={page}"
