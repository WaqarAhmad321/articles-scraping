from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem

from articles_scraper.utils.article_id import make_article_id
from articles_scraper.utils.article_type import classify_article_type
from articles_scraper.utils.language import detect_language
from articles_scraper.utils.wordcount import word_count

log = logging.getLogger(__name__)

_WS = re.compile(r"\s+")


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return _WS.sub(" ", text.replace("\xa0", " ")).strip()


class CleanTextPipeline:
    def process_item(self, item, spider):
        a = ItemAdapter(item)
        a["headline"] = _clean(a.get("headline"))
        a["full_text"] = _clean(a.get("full_text"))
        if a.get("author"):
            a["author"] = _clean(a["author"])
        return item


class RequiredFieldsPipeline:
    REQUIRED = ("headline", "full_text", "url", "source", "category", "date_published")

    def process_item(self, item, spider):
        a = ItemAdapter(item)
        missing = [f for f in self.REQUIRED if not a.get(f)]
        if missing:
            raise DropItem(f"Missing required fields {missing} for {a.get('url')!r}")
        if len(a["full_text"]) < 200:
            raise DropItem(f"Article body too short ({len(a['full_text'])} chars): {a.get('url')!r}")
        return item


class LanguagePipeline:
    def process_item(self, item, spider):
        a = ItemAdapter(item)
        if not a.get("language"):
            a["language"] = detect_language(a["full_text"])
        return item


class UrduOnlyPipeline:
    """Drop English-detected articles. Active when settings.URDU_ONLY=True."""

    def __init__(self, urdu_only: bool):
        self.urdu_only = urdu_only

    @classmethod
    def from_crawler(cls, crawler):
        return cls(urdu_only=crawler.settings.getbool("URDU_ONLY", False))

    def process_item(self, item, spider):
        if not self.urdu_only:
            return item
        a = ItemAdapter(item)
        if a.get("language") != "Urdu":
            raise DropItem(f"non-urdu article dropped (lang={a.get('language')!r}): {a.get('url')!r}")
        return item


class WordCountPipeline:
    def process_item(self, item, spider):
        a = ItemAdapter(item)
        a["word_count"] = word_count(a["full_text"])
        return item


class ArticleTypePipeline:
    def process_item(self, item, spider):
        a = ItemAdapter(item)
        if not a.get("article_type"):
            a["article_type"] = classify_article_type(a["url"])
        return item


class OpinionOnlyPipeline:
    """Drop News Report items. Active when settings.OPINION_ONLY=True."""

    def __init__(self, opinion_only: bool):
        self.opinion_only = opinion_only

    @classmethod
    def from_crawler(cls, crawler):
        return cls(opinion_only=crawler.settings.getbool("OPINION_ONLY", False))

    def process_item(self, item, spider):
        if not self.opinion_only:
            return item
        a = ItemAdapter(item)
        if a.get("article_type") == "News Report":
            raise DropItem(f"news-report dropped (OPINION_ONLY): {a.get('url')!r}")
        return item


class ArticleIdPipeline:
    def process_item(self, item, spider):
        a = ItemAdapter(item)
        a["article_id"] = make_article_id(a["url"])
        return item


SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
  article_id     TEXT PRIMARY KEY,
  headline       TEXT NOT NULL,
  full_text      TEXT NOT NULL,
  source         TEXT NOT NULL,
  author         TEXT,
  date_published TEXT NOT NULL,
  url            TEXT NOT NULL UNIQUE,
  category       TEXT NOT NULL,
  article_type   TEXT NOT NULL,
  language       TEXT NOT NULL,
  word_count     INTEGER NOT NULL,
  scraped_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_category ON articles(category);
CREATE INDEX IF NOT EXISTS idx_source   ON articles(source);
CREATE INDEX IF NOT EXISTS idx_date     ON articles(date_published);
"""


class SQLitePipeline:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(db_path=crawler.settings.get("DB_PATH"))

    def open_spider(self, spider):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # timeout=30s lets concurrent spiders queue up rather than fail on lock
        self.conn = sqlite3.connect(self.db_path, timeout=30)
        # WAL allows readers to coexist with one writer; multiple spider
        # processes still serialize writes, but with much less contention.
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close_spider(self, spider):
        if self.conn is not None:
            self.conn.close()

    def process_item(self, item, spider):
        a = ItemAdapter(item)
        try:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO articles
                  (article_id, headline, full_text, source, author,
                   date_published, url, category, article_type, language, word_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    a["article_id"],
                    a["headline"],
                    a["full_text"],
                    a["source"],
                    a.get("author"),
                    a["date_published"],
                    a["url"],
                    a["category"],
                    a["article_type"],
                    a["language"],
                    a["word_count"],
                ),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            log.error("SQLite insert failed for %s: %s", a.get("url"), e)
        return item
