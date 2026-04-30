from articles_scraper.utils.article_type import classify_article_type


def test_news_default():
    assert classify_article_type("https://www.dawn.com/news/123/some-slug") == "News Report"


def test_opinion_from_url():
    assert classify_article_type("https://www.dawn.com/news/opinion/whatever") == "Opinion"


def test_blog_from_url():
    assert classify_article_type("https://www.dawn.com/blogs/123/title") == "Blog"


def test_editorial_from_url():
    assert classify_article_type("https://www.dawn.com/news/editorial/title") == "Editorial"


def test_section_hint_overrides():
    assert classify_article_type("https://example.com/article/1", section="Editorial") == "Editorial"
