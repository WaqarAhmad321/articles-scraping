import scrapy


class ArticleItem(scrapy.Item):
    article_id = scrapy.Field()
    headline = scrapy.Field()
    full_text = scrapy.Field()
    source = scrapy.Field()
    author = scrapy.Field()
    date_published = scrapy.Field()
    url = scrapy.Field()
    category = scrapy.Field()
    article_type = scrapy.Field()
    language = scrapy.Field()
    word_count = scrapy.Field()
