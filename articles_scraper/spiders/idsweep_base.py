"""Sequential-ID URL sweep — for sources whose articles live at predictable
numeric URL paths (e.g. Dawn `/news/<id>/<slug>`, Geo `/latest/<id>-<slug>`).

Iterates a numeric ID range, fetches each candidate URL (server redirects to
the canonical /<id>/<slug> form), then runs the standard extraction +
relevance pipeline. URL slug pre-filter skips slugs that don't contain any
event keyword, dramatically cutting the fetch volume.

Sites publish IDs in roughly chronological order, so an ID range maps
approximately onto a date range.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable

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


class BaseIDSweepSpider(scrapy.Spider):
    """Subclasses set:
      - source_id (sources.yaml key)
      - id_min / id_max (numeric range, inclusive)
      - id_stride (sample every Nth ID; 1 = every ID)
      - candidate_url_template (e.g. "https://www.dawn.com/news/{id}/")
    """

    source_id: str = ""
    DATE_FROM = "2024-01-01"
    DATE_TO = "2026-12-31"
    id_min: int = 0
    id_max: int = 0
    id_stride: int = 1
    candidate_url_template: str = ""
    DEFAULT_MAX_TOTAL = 5000

    def __init__(self, max_total: int | None = None, events: str | None = None,
                 id_min: int | None = None, id_max: int | None = None, id_stride: int | None = None,
                 *a, **kw):
        super().__init__(*a, **kw)
        sources = load_yaml("sources.yaml")
        self.cfg = sources[self.source_id]
        self.allowed_domains = list(self.cfg.get("allowed_domains", []))
        all_events = load_yaml("events.yaml")
        if events:
            wanted = set(events.split(","))
            all_events = [e for e in all_events if e["id"] in wanted]
        self.events: list[EventDef] = load_events(all_events)
        self.max_total = int(max_total) if max_total else self.DEFAULT_MAX_TOTAL
        if id_min:
            self.id_min = int(id_min)
        if id_max:
            self.id_max = int(id_max)
        if id_stride:
            self.id_stride = int(id_stride)
        self._yielded = 0

    def start_requests(self) -> Iterable[Request]:
        # Iterate IDs in REVERSE order (newest first) — the server redirects
        # /news/<id>/ to /news/<id>/<slug>, after which we run extraction.
        for i in range(self.id_max, self.id_min - 1, -self.id_stride):
            url = self.candidate_url_template.format(id=i)
            yield Request(url, callback=self.parse_article, priority=10,
                          dont_filter=True)

    def parse_article(self, response: Response):
        if self._yielded >= self.max_total:
            return
        # The slug-keyword pre-filter applies after redirect (response.url has the slug)
        if not url_could_be_relevant(response.url, self.events):
            return

        ext = extract(response, self.cfg.get("selectors", {}))
        if not ext.full_text or len(ext.full_text) < 200:
            return
        if not ext.headline:
            return
        date_iso = ext.date_published
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
