"""Sitemap-driven discovery + relevance filtering.

Flow per source:
  1. Fetch the configured sitemap_index URLs.
  2. Each <sitemap><loc> in the index is a sub-sitemap; if the index entry has
     a <lastmod> outside the configured date window, skip it.
  3. For each in-range sub-sitemap, fetch it and walk its <url> entries.
     Each <url> may carry its own <lastmod>; date-filter against the global
     window AND drop anything not matching the source's article URL pattern.
  4. Fetch the article. Run trafilatura + per-source selectors for headline,
     author, date. Run relevance matcher (events.yaml) against headline+body.
  5. If matched, yield an ArticleItem with category=matched event.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import scrapy
import yaml
from scrapy.http import Request, Response

from articles_scraper.extractors import extract
from articles_scraper.items import ArticleItem
from articles_scraper.relevance import EventDef, load_events, match_event, url_could_be_relevant
from articles_scraper.utils.article_type import classify_article_type
from articles_scraper.utils.dates import in_range, parse_date

log = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def load_yaml(name: str):
    with open(CONFIG_DIR / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


_DATE_HEAD = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def _is_index(xml_text: str) -> bool:
    return "<sitemapindex" in xml_text or "<sitemap>" in xml_text


def _parse_sitemap(xml_text: str) -> list[tuple[str, str | None]]:
    """Return list of (loc, lastmod-or-None). Works for both index and urlset."""
    out: list[tuple[str, str | None]] = []
    # Find each <url> or <sitemap> block; extract <loc> and (optional) <lastmod>
    # We're loose with namespaces — these sites all use the standard schema.
    pat = re.compile(
        r"<(?:url|sitemap)>(.*?)</(?:url|sitemap)>",
        re.DOTALL,
    )
    for block in pat.findall(xml_text):
        m_loc = re.search(r"<loc>([^<]+)</loc>", block)
        if not m_loc:
            continue
        loc = m_loc.group(1).strip()
        m_lm = re.search(r"<lastmod>([^<]+)</lastmod>", block)
        lastmod = m_lm.group(1).strip() if m_lm else None
        out.append((loc, lastmod))
    return out


def _lastmod_in_range(lastmod: str | None, date_from: str | None, date_to: str | None) -> bool:
    if not lastmod:
        return True  # no lastmod → can't reject; let article-level filter decide
    m = _DATE_HEAD.match(lastmod)
    if not m:
        return True
    iso = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return in_range(iso, date_from, date_to)


class BaseSitemapSpider(scrapy.Spider):
    """Subclasses set:
      - source_id (required): key in config/sources.yaml
      - DATE_FROM / DATE_TO: project-wide date window
      - article_url_pattern: regex; URL must match to be considered an article
    """

    source_id: str = ""

    DATE_FROM = "2024-01-01"
    DATE_TO = "2026-12-31"

    # Per-source: regex an article URL must match (compiled in __init__).
    # Example: r"/story/\d+/" for Express.
    article_url_pattern: str = r"."  # default: anything

    DEFAULT_MAX_ARTICLES_TOTAL = 5000

    custom_settings = {
        # Sitemaps + RSS aren't disallowed by the sources we use; keeping ROBOTSTXT_OBEY
        # but sitemap fetches need User-Agent overrides occasionally.
    }

    def __init__(self, max_total: int | None = None, events: str | None = None, *a, **kw):
        super().__init__(*a, **kw)
        sources = load_yaml("sources.yaml")
        if self.source_id not in sources:
            raise ValueError(f"Source {self.source_id!r} not in sources.yaml")
        self.cfg = sources[self.source_id]
        self.allowed_domains = list(self.cfg.get("allowed_domains", []))

        all_events = load_yaml("events.yaml")
        if events:
            wanted = set(events.split(","))
            all_events = [e for e in all_events if e["id"] in wanted]
        self.events: list[EventDef] = load_events(all_events)

        self.max_total = int(max_total) if max_total else self.DEFAULT_MAX_ARTICLES_TOTAL
        self._yielded = 0
        self._seen_urls: set[str] = set()

        self._article_re = re.compile(self.article_url_pattern)

    # ----- discovery: walk sitemap index → sub-sitemaps → article URLs -----
    def _meta(self, **extra) -> dict:
        meta = dict(extra)
        if self.cfg.get("render") == "playwright":
            meta["playwright"] = True
            meta["playwright_page_goto_kwargs"] = {"wait_until": "domcontentloaded"}
        return meta

    def start_requests(self) -> Iterable[Request]:
        sitemap_urls = self.cfg.get("sitemaps", [])
        if not sitemap_urls:
            log.error("%s: no sitemaps configured", self.source_id)
            return
        for url in sitemap_urls:
            yield Request(
                url,
                callback=self.parse_sitemap,
                meta=self._meta(depth=0),
                dont_filter=True,
            )

    def parse_sitemap(self, response: Response):
        if self._yielded >= self.max_total:
            return
        depth = response.meta.get("depth", 0)
        text = response.text
        is_index = _is_index(text)
        entries = _parse_sitemap(text)
        log.info(
            "%s: sitemap %s — %d entries (%s, depth=%d)",
            self.source_id, response.url, len(entries),
            "INDEX" if is_index else "urlset",
            depth,
        )
        for loc, lastmod in entries:
            if is_index:
                # filter sub-sitemaps by lastmod against the global window
                if not _lastmod_in_range(lastmod, self.DATE_FROM, self.DATE_TO):
                    continue
                yield Request(
                    loc,
                    callback=self.parse_sitemap,
                    meta=self._meta(depth=depth + 1),
                    dont_filter=True,
                )
            else:
                # article URL
                if loc in self._seen_urls:
                    continue
                if not self._article_re.search(loc):
                    continue
                if not _lastmod_in_range(lastmod, self.DATE_FROM, self.DATE_TO):
                    continue
                # Subclass can opt out of URL-slug pre-filter (e.g. for Urdu
                # transliterated slugs where the filter is too aggressive).
                if not getattr(self, "skip_slug_filter", False):
                    if not url_could_be_relevant(loc, self.events):
                        continue
                self._seen_urls.add(loc)
                yield Request(
                    loc,
                    callback=self.parse_article,
                    meta=self._meta(sitemap_lastmod=lastmod),
                    priority=10,
                )

    # ----- article processing -----
    def parse_article(self, response: Response):
        if self._yielded >= self.max_total:
            return

        ext = extract(response, self.cfg.get("selectors", {}))

        # Fall back to sitemap lastmod for date if extraction failed
        date_iso = ext.date_published or parse_date(response.meta.get("sitemap_lastmod"))

        if not ext.full_text or len(ext.full_text) < 200:
            return
        if not ext.headline:
            return
        if not date_iso:
            return
        if not in_range(date_iso, self.DATE_FROM, self.DATE_TO):
            return

        ev = match_event(ext.headline, ext.full_text, self.events)
        if ev is None:
            return  # not relevant to any tracked event

        # Per-event date window also applies (some events are narrower than the global one)
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
            article_type=classify_article_type(response.url, ext.section),
            language=None,
            word_count=None,
        )
        self._yielded += 1
        yield item
