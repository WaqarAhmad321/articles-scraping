from articles_scraper.utils.article_id import make_article_id


def test_deterministic():
    url = "https://www.dawn.com/news/1820000/some-slug"
    assert make_article_id(url) == make_article_id(url)


def test_format():
    aid = make_article_id("https://example.com/x")
    assert aid.startswith("ART")
    assert len(aid) == 11
    assert aid[3:].isalnum()


def test_distinct():
    a = make_article_id("https://example.com/a")
    b = make_article_id("https://example.com/b")
    assert a != b
