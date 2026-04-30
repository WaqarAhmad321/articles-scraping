"""Match article text against event keyword sets to assign a category.

Strategy: case-insensitive substring match. Title carries more weight than
body (a hit in title is enough; in body we require a slightly stronger match).
First event whose keywords match wins (events.yaml ordering = priority).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EventDef:
    id: str
    category: str
    date_from: str | None
    date_to: str | None
    keywords: tuple[str, ...]      # combined EN + UR, lowercased — for body match
    slug_keywords: tuple[str, ...] # short tokens for URL prefilter, lowercased


def load_events(events_yaml: list[dict]) -> list[EventDef]:
    out = []
    for e in events_yaml:
        kws = [k.lower() for k in (e.get("keywords_en", []) + e.get("keywords_ur", [])) if k]
        slugs = [s.lower() for s in (e.get("slug_keywords") or []) if s]
        out.append(
            EventDef(
                id=e["id"],
                category=e["category"],
                date_from=str(e.get("date_from")) if e.get("date_from") else None,
                date_to=str(e.get("date_to")) if e.get("date_to") else None,
                keywords=tuple(kws),
                slug_keywords=tuple(slugs),
            )
        )
    return out


def url_could_be_relevant(url: str, events: list[EventDef]) -> bool:
    """Cheap prefilter: does the URL path contain any event's slug keyword?

    Returns True (pass-through) if:
      - no event has slug_keywords, OR
      - the URL appears to use opaque hash-style slugs (no hyphens between
        letters in the last path segment), since we can't slug-match those.
    """
    has_any_slugs = any(ev.slug_keywords for ev in events)
    if not has_any_slugs:
        return True
    # If the last meaningful path segment doesn't have a hyphenated slug,
    # we can't slug-match it (e.g. BBC's /urdu/articles/c4gx7gj8vxeo).
    # Pass it through and let the body-level matcher decide.
    last_segment = url.rstrip("/").rsplit("/", 1)[-1].lower()
    if "-" not in last_segment:
        return True
    u = url.lower()
    for ev in events:
        for kw in ev.slug_keywords:
            if kw in u:
                return True
    return False


def match_event(headline: str, body: str, events: list[EventDef]) -> EventDef | None:
    h = (headline or "").lower()
    b_head = (body or "").lower()[:2000]
    for ev in events:
        for kw in ev.keywords:
            if kw in h:
                return ev
        for kw in ev.keywords:
            if kw in b_head:
                return ev
    return None
