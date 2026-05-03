from __future__ import annotations

import json
import re
from dataclasses import dataclass

import trafilatura
from scrapy.http import Response

from articles_scraper.utils.dates import parse_date

_JSONLD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def _meta_published_time(response: Response) -> str | None:
    for sel in (
        'meta[property="article:published_time"]::attr(content)',
        'meta[property="og:article:published_time"]::attr(content)',
        'meta[name="article:published_time"]::attr(content)',
        'meta[name="pubdate"]::attr(content)',
        'meta[itemprop="datePublished"]::attr(content)',
    ):
        v = response.css(sel).get()
        if v:
            return v.strip()
    return None


def _jsonld_published(response: Response) -> str | None:
    for raw in _JSONLD_RE.findall(response.text):
        try:
            data = json.loads(raw)
        except Exception:
            continue
        # JSON-LD can be a single object, an array, or have a @graph
        candidates = data if isinstance(data, list) else [data]
        graph = []
        for c in candidates:
            if isinstance(c, dict):
                if "@graph" in c and isinstance(c["@graph"], list):
                    graph.extend(c["@graph"])
                else:
                    graph.append(c)
        for node in graph:
            if not isinstance(node, dict):
                continue
            for key in ("datePublished", "dateCreated"):
                if isinstance(node.get(key), str):
                    return node[key]
    return None


def _meta_author(response: Response) -> str | None:
    for sel in (
        'meta[name="author"]::attr(content)',
        'meta[property="article:author"]::attr(content)',
    ):
        v = response.css(sel).get()
        if v and v.strip():
            return v.strip()
    # JSON-LD fallback. BBC Urdu (and many modern publishers) only expose the
    # author inside <script type="application/ld+json"> rather than HTML markup.
    for raw in _JSONLD_RE.findall(response.text):
        try:
            data = json.loads(raw)
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        graph = []
        for c in candidates:
            if isinstance(c, dict):
                if "@graph" in c and isinstance(c["@graph"], list):
                    graph.extend(c["@graph"])
                else:
                    graph.append(c)
        for node in graph:
            if not isinstance(node, dict):
                continue
            author = node.get("author")
            # author can be a dict, a list of dicts, or a plain string
            if isinstance(author, dict) and isinstance(author.get("name"), str):
                return author["name"].strip()
            if isinstance(author, list) and author:
                first = author[0]
                if isinstance(first, dict) and isinstance(first.get("name"), str):
                    return first["name"].strip()
                if isinstance(first, str):
                    return first.strip()
            if isinstance(author, str):
                return author.strip()
    return None


def _jsonld_section(response: Response) -> str | None:
    """Read article-section info — used to classify article_type as
    Opinion/Blog/Editorial. Tries (in order):
      1. <meta property="article:section">  (Nawaiwaqt, Naya Daur use رائے/تجزیہ)
      2. JSON-LD `articleSection` (Express, ARY-Urdu, BBC Urdu use کالم/اداریہ/بلاگ)
    """
    meta_sec = response.css('meta[property="article:section"]::attr(content)').get()
    if meta_sec and meta_sec.strip():
        return meta_sec.strip()
    for raw in _JSONLD_RE.findall(response.text):
        try:
            data = json.loads(raw)
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        graph = []
        for c in candidates:
            if isinstance(c, dict):
                if "@graph" in c and isinstance(c["@graph"], list):
                    graph.extend(c["@graph"])
                else:
                    graph.append(c)
        for node in graph:
            if not isinstance(node, dict):
                continue
            sec = node.get("articleSection")
            if isinstance(sec, str) and sec.strip():
                return sec.strip()
            if isinstance(sec, list) and sec:
                first = sec[0]
                if isinstance(first, str) and first.strip():
                    return first.strip()
    return None


def _meta_headline(response: Response) -> str | None:
    """Headline fallback: og:title / twitter:title / JSON-LD headline.
    Dawn (and many SPA-style sites) render h1 via JS so server HTML has only meta."""
    for sel in (
        'meta[property="og:title"]::attr(content)',
        'meta[name="twitter:title"]::attr(content)',
        'meta[itemprop="headline"]::attr(content)',
    ):
        v = response.css(sel).get()
        if v and v.strip():
            return v.strip()
    for raw in _JSONLD_RE.findall(response.text):
        try:
            data = json.loads(raw)
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        graph = []
        for c in candidates:
            if isinstance(c, dict):
                if "@graph" in c and isinstance(c["@graph"], list):
                    graph.extend(c["@graph"])
                else:
                    graph.append(c)
        for node in graph:
            if isinstance(node, dict) and isinstance(node.get("headline"), str):
                return node["headline"].strip()
    return None


@dataclass
class Extracted:
    headline: str | None
    full_text: str | None
    author: str | None
    date_published: str | None  # ISO YYYY-MM-DD or None
    section: str | None = None  # JSON-LD articleSection / breadcrumb hint


def _first(response: Response, selectors_csv: str) -> str | None:
    """Try each comma-separated CSS selector in order; return the first non-empty match."""
    if not selectors_csv:
        return None
    for sel in [s.strip() for s in selectors_csv.split(",") if s.strip()]:
        value = response.css(sel).get()
        if value and value.strip():
            return value.strip()
    return None


def extract(response: Response, selectors: dict) -> Extracted:
    """Combine site-specific CSS selectors (for metadata) with trafilatura (for body)."""
    headline = _first(response, selectors.get("headline", ""))
    author = _first(response, selectors.get("author", ""))
    raw_date = _first(response, selectors.get("date", ""))

    # Global fallbacks — hit virtually every modern news site.
    if not raw_date:
        raw_date = _meta_published_time(response) or _jsonld_published(response)
    if not author:
        author = _meta_author(response)
    if not headline:
        headline = _meta_headline(response)

    body = trafilatura.extract(
        response.text,
        url=response.url,
        favor_recall=True,
        include_comments=False,
        include_tables=False,
        no_fallback=False,
    )

    if not headline:
        headline = _first(response, "h1::text")
    if not body:
        # Last-ditch fallback: concatenate all <p> text within likely article containers.
        paragraphs = response.css(
            "article p::text, .story__content p::text, .entry-content p::text, "
            ".article-body p::text, main p::text"
        ).getall()
        if paragraphs:
            body = "\n".join(p.strip() for p in paragraphs if p.strip())

    return Extracted(
        headline=headline,
        full_text=body,
        author=author,
        date_published=parse_date(raw_date),
        section=_jsonld_section(response),
    )
