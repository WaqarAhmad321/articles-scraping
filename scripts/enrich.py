"""Enrich articles.db with derived columns — no scraper re-run required.

Computes everything from data already in the DB plus a single read-only pass
over the HTTP cache for image/tags/full-timestamp fields. Idempotent: safe to
re-run after every crawl.

Adds the following columns:
  - source_domain          urlparse(url).netloc
  - collection_mode        spider's discovery method (sitemap/tag-page/section/...)
  - summary                first ~300 chars of full_text, sentence-aware
  - published_at           full ISO timestamp from cached <meta>/JSON-LD if found
  - body_chars             len(full_text)
  - sentence_count         split on ۔ / .
  - paragraph_count        split on \\n\\n
  - has_urdu               always 1 (URDU_ONLY filter guarantees it)
  - title_hash             sha1(headline)
  - body_hash              sha1(full_text)
  - text_hash              sha1(headline + full_text)
  - extraction_quality     'ok' if headline+body+date all present, else 'partial'
  - scrape_status          'ok' (only inserted rows reach the DB)
  - content_changed        'no' (no historical re-scrape data yet)
  - image_url              og:image from cached HTML, when available
  - image_alt              og:image:alt from cached HTML
  - tags                   news_keywords / articleSection from cached HTML (comma-joined)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import pickle
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "data" / "articles.db"
CACHE_DIR = PROJECT_ROOT / "httpcache"

NEW_COLUMNS = [
    ("source_domain", "TEXT"),
    ("collection_mode", "TEXT"),
    ("summary", "TEXT"),
    ("published_at", "TEXT"),
    ("body_chars", "INTEGER"),
    ("sentence_count", "INTEGER"),
    ("paragraph_count", "INTEGER"),
    ("has_urdu", "INTEGER"),
    ("title_hash", "TEXT"),
    ("body_hash", "TEXT"),
    ("text_hash", "TEXT"),
    ("extraction_quality", "TEXT"),
    ("scrape_status", "TEXT"),
    ("content_changed", "TEXT"),
    ("image_url", "TEXT"),
    ("image_alt", "TEXT"),
    ("tags", "TEXT"),
]

# Each spider's discovery method, mirrored from the codebase. Used to fill
# `collection_mode` based on the source name (since we don't store the spider
# name on items; this mapping is the source of truth).
COLLECTION_MODE = {
    "Express News": "sitemap",            # express_sitemap is the dominant feeder
    "BBC Urdu": "sitemap",                # archive sitemaps
    "ARY News (Urdu)": "section+search",  # urdu.arynews.tv section walker + ?s=
    "Dawn News (Urdu)": "section",        # dawnnews.tv Playwright section walk
    "Abb Takk News": "sitemap",
    "Geo News": "section+search",
    "Dawn News": "section+rss",           # dawn.com (English)
    "ARY News": "section+search",         # arynews.tv (English)
    "92 News": "blocked",
}

_SENTENCE_END = re.compile(r"[۔\.!\?]+")


def add_columns_if_missing(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()}
    for name, sqltype in NEW_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE articles ADD COLUMN {name} {sqltype}")
            print(f"  + added column: {name} {sqltype}")
    conn.commit()


def first_paragraph(body: str, target: int = 300) -> str:
    """Trim body to ~`target` chars, ending on a sentence boundary if possible."""
    if not body:
        return ""
    body = body.strip()
    if len(body) <= target:
        return body
    cut = body[:target]
    # back up to nearest sentence-end
    m = list(_SENTENCE_END.finditer(cut))
    if m and m[-1].end() > target * 0.6:
        return cut[: m[-1].end()].strip()
    # fall back to nearest space
    sp = cut.rfind(" ")
    if sp > target * 0.6:
        return cut[:sp].rstrip() + "…"
    return cut.rstrip() + "…"


def sha1_short(s: str) -> str:
    if not s:
        return ""
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def sentence_count(body: str) -> int:
    if not body:
        return 0
    parts = [p for p in _SENTENCE_END.split(body) if p.strip()]
    return len(parts)


def paragraph_count(body: str) -> int:
    if not body:
        return 0
    return len([p for p in re.split(r"\n\s*\n", body) if p.strip()])


def extraction_quality(headline, full_text, date_published, author) -> str:
    if not headline or not full_text or not date_published:
        return "partial"
    if len(full_text) < 400:
        return "thin"
    if not author:
        return "ok-no-byline"
    return "ok"


# ─────── Cache scan: image_url, image_alt, tags, published_at ───────

_OG_IMAGE = re.compile(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', re.IGNORECASE)
_OG_IMAGE_ALT = re.compile(r'<meta[^>]+property="og:image:alt"[^>]+content="([^"]+)"', re.IGNORECASE)
_NEWS_KEYWORDS = re.compile(r'<meta[^>]+name="news_keywords"[^>]+content="([^"]+)"', re.IGNORECASE)
_KEYWORDS_META = re.compile(r'<meta[^>]+name="keywords"[^>]+content="([^"]+)"', re.IGNORECASE)
_PUBLISHED_TIME = re.compile(r'<meta[^>]+property="article:published_time"[^>]+content="([^"]+)"', re.IGNORECASE)
_JSONLD = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE)


def _read_cached_html(meta_path: Path) -> str | None:
    try:
        body_path = meta_path.parent / "response_body"
        if not body_path.exists():
            return None
        raw = body_path.read_bytes()
        try:
            return gzip.decompress(raw).decode("utf-8", "replace")
        except Exception:
            return raw.decode("utf-8", "replace")
    except Exception:
        return None


def _build_cache_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    for meta in CACHE_DIR.glob("*/*/*/pickled_meta"):
        try:
            with meta.open("rb") as f:
                m = pickle.load(f)
            if isinstance(m, dict):
                u = m.get("url") or m.get("response_url")
                if u and u not in index:
                    index[u] = meta
        except Exception:
            continue
    return index


def _parse_cache_fields(html: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    m = _OG_IMAGE.search(html)
    out["image_url"] = m.group(1).strip() if m else None
    m = _OG_IMAGE_ALT.search(html)
    out["image_alt"] = m.group(1).strip() if m else None
    m = _NEWS_KEYWORDS.search(html) or _KEYWORDS_META.search(html)
    tags = m.group(1).strip() if m else None
    # Augment with JSON-LD articleSection / keywords if news_keywords missing
    sections: list[str] = []
    if tags:
        sections.append(tags)
    for raw in _JSONLD.findall(html):
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
            for k in ("articleSection", "keywords"):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    sections.append(v.strip())
                elif isinstance(v, list):
                    sections.extend(str(x).strip() for x in v if x)
    # Dedupe while preserving order
    seen = set()
    deduped = []
    for s in sections:
        for piece in re.split(r"\s*[,،;]\s*", s):
            piece = piece.strip()
            if piece and piece.lower() not in seen:
                seen.add(piece.lower())
                deduped.append(piece)
    out["tags"] = ", ".join(deduped) if deduped else None

    # full timestamp
    m = _PUBLISHED_TIME.search(html)
    if m:
        out["published_at"] = m.group(1).strip()
    else:
        out["published_at"] = None
        for raw in _JSONLD.findall(html):
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
                if isinstance(node, dict) and isinstance(node.get("datePublished"), str):
                    out["published_at"] = node["datePublished"].strip()
                    break
            if out["published_at"]:
                break
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--no-cache-scan", action="store_true",
                   help="Skip the slow cache scan; only fill cheap fields")
    args = p.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    print(f"DB: {args.db}")
    print("adding columns if missing...")
    add_columns_if_missing(conn)

    rows = conn.execute(
        "SELECT article_id, headline, full_text, source, author, "
        "       date_published, url FROM articles"
    ).fetchall()
    print(f"  {len(rows)} rows in DB")

    cache_idx: dict[str, Path] = {}
    if not args.no_cache_scan:
        print("indexing httpcache (one-time scan)...")
        cache_idx = _build_cache_index()
        print(f"  {len(cache_idx)} cached responses")

    print("computing derived fields + scanning cache for images/tags...")
    cache_hits = 0
    for i, r in enumerate(rows, 1):
        url = r["url"]
        full = r["full_text"] or ""
        headline = r["headline"] or ""

        upd: dict[str, object] = {
            "source_domain": urlparse(url).netloc,
            "collection_mode": COLLECTION_MODE.get(r["source"], "unknown"),
            "summary": first_paragraph(full),
            "body_chars": len(full),
            "sentence_count": sentence_count(full),
            "paragraph_count": paragraph_count(full),
            "has_urdu": 1,
            "title_hash": sha1_short(headline)[:16],
            "body_hash": sha1_short(full)[:16],
            "text_hash": sha1_short(headline + "\n" + full)[:16],
            "extraction_quality": extraction_quality(
                headline, full, r["date_published"], r["author"]
            ),
            "scrape_status": "ok",
            "content_changed": "no",
            # Cache-derived (defaults if no cache hit)
            "image_url": None,
            "image_alt": None,
            "tags": None,
            "published_at": r["date_published"],  # fallback
        }

        if cache_idx:
            meta_path = cache_idx.get(url)
            if meta_path:
                html = _read_cached_html(meta_path)
                if html:
                    fields = _parse_cache_fields(html)
                    if fields.get("image_url"):
                        upd["image_url"] = fields["image_url"]
                    if fields.get("image_alt"):
                        upd["image_alt"] = fields["image_alt"]
                    if fields.get("tags"):
                        upd["tags"] = fields["tags"]
                    if fields.get("published_at"):
                        upd["published_at"] = fields["published_at"]
                    cache_hits += 1

        sets = ", ".join(f"{k} = ?" for k in upd)
        conn.execute(f"UPDATE articles SET {sets} WHERE article_id = ?",
                     list(upd.values()) + [r["article_id"]])

        if i % 1000 == 0:
            conn.commit()
            print(f"    {i}/{len(rows)} rows enriched (cache_hits={cache_hits})")

    conn.commit()
    print(f"\n  total cache_hits: {cache_hits}/{len(rows)}")

    # Show final coverage
    print("\n  filled-column coverage:")
    for col in [
        "source_domain", "collection_mode", "summary", "published_at",
        "body_chars", "sentence_count", "paragraph_count",
        "image_url", "image_alt", "tags",
    ]:
        n = conn.execute(
            f"SELECT COUNT(*) FROM articles WHERE {col} IS NOT NULL AND {col} != ''"
        ).fetchone()[0]
        print(f"    {col:<22} {n}/{len(rows)}")

    conn.close()
    print("\n  done. Re-run scripts/export.py to refresh the CSV.")


if __name__ == "__main__":
    main()
