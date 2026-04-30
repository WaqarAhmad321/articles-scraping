"""Wayback Machine CDX-driven discovery for historical content.

The Internet Archive's CDX server has indexed every URL ever crawled across
the entire web, with timestamps. For sources whose own pagination doesn't go
back far enough (Dawn, Geo, Express, ARY), we ask CDX:

    "every dawn.com/news/* URL captured between 2023-01-01 and 2024-12-31"

CDX returns the *original* URLs (with crawl dates), which we then fetch live
from the source — no need to actually go through the Wayback proxy.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

import scrapy
import yaml
from scrapy.http import Request, Response

from articles_scraper.extractors import extract
from articles_scraper.items import ArticleItem
from articles_scraper.relevance import EventDef, load_events, match_event, url_could_be_relevant
from articles_scraper.utils.dates import in_range

log = logging.getLogger(__name__)
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def load_yaml(name: str):
    with open(CONFIG_DIR / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class BaseCDXSpider(scrapy.Spider):
    """Subclasses set:
      - source_id (sources.yaml key)
      - cdx_patterns: list of URL patterns for CDX (e.g. ["dawn.com/news/*"])
      - article_url_pattern: regex an article URL must match
    """

    source_id: str = ""
    cdx_patterns: list[str] = []
    DATE_FROM = "2023-01-01"
    DATE_TO = "2026-12-31"
    article_url_pattern: str = r"."

    DEFAULT_MAX_TOTAL = 5000
    CDX_LIMIT = 50000  # max URLs per CDX query

    custom_settings = {
        # CDX itself isn't bandwidth-heavy; the article fetches dominate.
        # Keep autothrottle on so we don't pound the source.
    }

    def __init__(self, max_total: int | None = None, events: str | None = None, *a, **kw):
        super().__init__(*a, **kw)
        sources = load_yaml("sources.yaml")
        self.cfg = sources[self.source_id]
        self.allowed_domains = list(self.cfg.get("allowed_domains", [])) + ["web.archive.org"]
        all_events = load_yaml("events.yaml")
        if events:
            wanted = set(events.split(","))
            all_events = [e for e in all_events if e["id"] in wanted]
        self.events: list[EventDef] = load_events(all_events)
        self.max_total = int(max_total) if max_total else self.DEFAULT_MAX_TOTAL
        self._yielded = 0
        self._seen_urls: set[str] = set()
        self._article_re = re.compile(self.article_url_pattern)

    def start_requests(self) -> Iterable[Request]:
        date_from_compact = self.DATE_FROM.replace("-", "")
        date_to_compact = self.DATE_TO.replace("-", "")
        for pat in self.cdx_patterns:
            cdx_url = (
                "https://web.archive.org/cdx/search/cdx"
                f"?url={quote(pat)}"
                f"&from={date_from_compact}"
                f"&to={date_to_compact}"
                "&output=json"
                "&filter=statuscode:200"
                "&filter=mimetype:text/html"
                "&collapse=urlkey"  # dedupe by canonical URL
                f"&limit={self.CDX_LIMIT}"
            )
            yield Request(cdx_url, callback=self.parse_cdx,
                          meta={"cdx_pattern": pat}, dont_filter=True)

    def parse_cdx(self, response: Response):
        """CDX returns: [[fields], [urlkey, timestamp, original, mime, status, digest, length], ...]"""
        if self._yielded >= self.max_total:
            return
        try:
            rows = json.loads(response.text)
        except Exception as e:
            log.error("%s: CDX parse failed for %s: %s", self.source_id, response.url, e)
            return
        if not rows or len(rows) < 2:
            log.info("%s: CDX returned 0 rows for %s", self.source_id, response.meta["cdx_pattern"])
            return
        header = rows[0]
        try:
            url_idx = header.index("original")
            ts_idx = header.index("timestamp")
        except ValueError:
            url_idx, ts_idx = 2, 1
        log.info("%s: CDX %s → %d rows",
                 self.source_id, response.meta["cdx_pattern"], len(rows) - 1)

        for row in rows[1:]:
            if self._yielded >= self.max_total:
                return
            try:
                orig_url = row[url_idx]
                ts = row[ts_idx]  # YYYYMMDDhhmmss
            except IndexError:
                continue
            iso = f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}"
            if not in_range(iso, self.DATE_FROM, self.DATE_TO):
                continue
            if not self._article_re.search(orig_url):
                continue
            if not url_could_be_relevant(orig_url, self.events):
                continue
            if orig_url in self._seen_urls:
                continue
            self._seen_urls.add(orig_url)
            # Fetch the LIVE article from the source (not from Wayback proxy).
            yield Request(orig_url, callback=self.parse_article,
                          meta={"cdx_capture": iso}, priority=10)

    def parse_article(self, response: Response):
        if self._yielded >= self.max_total:
            return
        ext = extract(response, self.cfg.get("selectors", {}))
        if not ext.full_text or len(ext.full_text) < 200:
            return
        if not ext.headline:
            return
        date_iso = ext.date_published or response.meta.get("cdx_capture")
        if not date_iso:
            return
        if not in_range(date_iso, self.DATE_FROM, self.DATE_TO):
            return
        ev = match_event(ext.headline, ext.full_text, self.events)
        if ev is None:
            return
        if not in_range(date_iso, ev.date_from, ev.date_to):
            return

        item = ArticleItem(
            headline=ext.headline,
            full_text=ext.full_text,
            source=self.cfg["display_name"],
            author=ext.author,
            date_published=date_iso,
            url=response.url,
            category=ev.category,
            article_type=None,
            language=None,
            word_count=None,
        )
        self._yielded += 1
        yield item
