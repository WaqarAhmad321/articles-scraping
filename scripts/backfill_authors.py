"""Backfill missing authors by re-reading cached HTML and parsing JSON-LD.

Many BBC Urdu (and a handful of Express) articles landed without an author
because the original byline selectors targeted HTML attributes that the sites
have since migrated to JSON-LD. This script rescues those by walking each
article URL, finding its cached HTML, and extracting the author via the
upgraded extractor.

Run after pipelines.py / extractors.py has been updated:
    python scripts/backfill_authors.py
"""
from __future__ import annotations

import argparse
import gzip
import json
import pickle
import re
import sqlite3
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "articles.db"
DEFAULT_CACHE = ROOT / "httpcache"

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Same JSON-LD-author logic as articles_scraper/extractors.py — we keep it
# self-contained so this script doesn't depend on Scrapy's response object.
_JSONLD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def author_from_jsonld(html_text: str) -> str | None:
    for raw in _JSONLD_RE.findall(html_text):
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


def author_from_meta(html_text: str) -> str | None:
    for pat in (
        r'<meta[^>]+name="author"[^>]+content="([^"]+)"',
        r'<meta[^>]+property="article:author"[^>]+content="([^"]+)"',
    ):
        m = re.search(pat, html_text)
        if m:
            return m.group(1).strip()
    return None


def find_cached_body(cache_root: Path, url: str) -> str | None:
    """Walk every cached entry, find the one whose URL matches, and return its body."""
    for meta_path in cache_root.rglob("pickled_meta"):
        try:
            with meta_path.open("rb") as f:
                meta = pickle.load(f)
        except Exception:
            continue
        if not isinstance(meta, dict):
            continue
        if meta.get("url") == url or meta.get("response_url") == url:
            body_path = meta_path.with_name("response_body")
            if not body_path.exists():
                return None
            raw = body_path.read_bytes()
            try:
                return gzip.decompress(raw).decode("utf-8", "replace")
            except OSError:
                return raw.decode("utf-8", "replace")
    return None


def build_cache_index(cache_root: Path) -> dict[str, Path]:
    """Build a one-shot map of url -> body file path. Much faster than rglob per article."""
    index: dict[str, Path] = {}
    for meta_path in cache_root.rglob("pickled_meta"):
        try:
            with meta_path.open("rb") as f:
                meta = pickle.load(f)
        except Exception:
            continue
        if not isinstance(meta, dict):
            continue
        url = meta.get("url") or meta.get("response_url")
        if url:
            body_path = meta_path.with_name("response_body")
            if body_path.exists():
                index[url] = body_path
    return index


def fetch_live(url: str) -> str | None:
    try:
        req = Request(url, headers={"User-Agent": UA})
        with urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"    fetch failed: {e}", file=sys.stderr)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--cache", default=str(DEFAULT_CACHE))
    ap.add_argument("--source", default=None,
                    help="filter to one source (e.g. 'BBC Urdu')")
    ap.add_argument("--fetch-missing", action="store_true",
                    help="fall back to a live HTTP fetch when the URL isn't in the cache")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    where = "(author IS NULL OR author = '')"
    params: list = []
    if args.source:
        where += " AND source = ?"
        params.append(args.source)
    rows = conn.execute(
        f"SELECT url, source FROM articles WHERE {where}", params
    ).fetchall()
    print(f"  {len(rows)} articles need author backfill")

    print("  building cache index...")
    cache_index = build_cache_index(Path(args.cache))
    print(f"  cache contains {len(cache_index)} unique URLs")

    fixed = 0
    cache_hits = 0
    live_fetches = 0
    not_found_in_cache = 0
    no_author_extractable = 0

    for i, row in enumerate(rows):
        url = row["url"]
        body = None
        if url in cache_index:
            cache_hits += 1
            try:
                raw = cache_index[url].read_bytes()
                try:
                    body = gzip.decompress(raw).decode("utf-8", "replace")
                except OSError:
                    body = raw.decode("utf-8", "replace")
            except Exception as e:
                print(f"    {i+1}/{len(rows)}: cache read failed for {url}: {e}",
                      file=sys.stderr)
        elif args.fetch_missing:
            live_fetches += 1
            body = fetch_live(url)
        else:
            not_found_in_cache += 1

        if not body:
            continue

        author = author_from_jsonld(body) or author_from_meta(body)
        if not author:
            no_author_extractable += 1
            continue

        if not args.dry_run:
            conn.execute(
                "UPDATE articles SET author = ? WHERE url = ?",
                (author, url),
            )
        fixed += 1
        if (i + 1) % 200 == 0:
            print(f"    progress: {i+1}/{len(rows)} processed, {fixed} authors set")
            if not args.dry_run:
                conn.commit()

    if not args.dry_run:
        conn.commit()

    print()
    print(f"  cache hits         : {cache_hits}")
    print(f"  live fetches       : {live_fetches}")
    print(f"  not in cache       : {not_found_in_cache}")
    print(f"  no author in body  : {no_author_extractable}")
    print(f"  authors filled     : {fixed}{' (DRY RUN)' if args.dry_run else ''}")

    print()
    print("  current state:")
    for src, total, has, missing in conn.execute(
        "SELECT source, COUNT(*),"
        "       SUM(CASE WHEN author IS NOT NULL AND author != '' THEN 1 ELSE 0 END),"
        "       SUM(CASE WHEN author IS NULL OR author = '' THEN 1 ELSE 0 END)"
        " FROM articles GROUP BY 1 ORDER BY 2 DESC"
    ):
        print(f"    {src:<20}  total={total:>5}  has={has:>5}  missing={missing:>4}")

    conn.close()


if __name__ == "__main__":
    main()
