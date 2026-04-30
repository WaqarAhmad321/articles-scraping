"""Re-classify the article_type column on existing rows using the upgraded
classifier (which now also reads JSON-LD `articleSection` from cached HTML).

Walks `httpcache/<source>/*/*/response_body`, decodes each blob, looks up the
matching url via `pickled_meta`, extracts the section, and re-classifies.

Run:  python scripts/backfill_article_type.py
"""
from __future__ import annotations

import argparse
import gzip
import json
import pickle
import re
import sqlite3
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT / "data" / "articles.db"
DEFAULT_CACHE = PROJECT / "httpcache"

import sys
sys.path.insert(0, str(PROJECT))
from articles_scraper.utils.article_type import classify_article_type


_JSONLD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def jsonld_section(html: str) -> str | None:
    for raw in _JSONLD_RE.findall(html):
        try:
            data = json.loads(raw)
        except Exception:
            continue
        nodes = data if isinstance(data, list) else [data]
        graph = []
        for c in nodes:
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
                f = sec[0]
                if isinstance(f, str) and f.strip():
                    return f.strip()
    return None


def build_cache_index(cache_dir: Path) -> dict[str, Path]:
    """Return {url: response_body_path}."""
    out: dict[str, Path] = {}
    for meta_path in cache_dir.glob("*/*/*/pickled_meta"):
        try:
            with meta_path.open("rb") as f:
                m = pickle.load(f)
        except Exception:
            continue
        if not isinstance(m, dict):
            continue
        url = m.get("url") or m.get("response_url")
        if not url:
            continue
        body_path = meta_path.parent / "response_body"
        if body_path.exists():
            out[url] = body_path
    return out


def read_body(p: Path) -> str | None:
    try:
        raw = p.read_bytes()
    except Exception:
        return None
    try:
        return gzip.decompress(raw).decode("utf-8", "replace")
    except Exception:
        return raw.decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--cache", default=str(DEFAULT_CACHE))
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    print("  building cache index...")
    cache_idx = build_cache_index(Path(args.cache))
    print(f"  {len(cache_idx)} cached responses")

    print("  scanning DB...")
    rows = conn.execute("SELECT article_id, url, article_type FROM articles").fetchall()
    print(f"  {len(rows)} articles in DB")

    counters = {"unchanged": 0, "updated": 0, "no_cache": 0}
    new_type_counts: dict[str, int] = {}
    cur = conn.cursor()

    for i, row in enumerate(rows, 1):
        url = row["url"]
        body_path = cache_idx.get(url)
        section = None
        if body_path:
            html = read_body(body_path)
            if html:
                section = jsonld_section(html)
        else:
            counters["no_cache"] += 1

        new_type = classify_article_type(url, section)
        if new_type != row["article_type"]:
            cur.execute(
                "UPDATE articles SET article_type = ? WHERE article_id = ?",
                (new_type, row["article_id"]),
            )
            counters["updated"] += 1
        else:
            counters["unchanged"] += 1
        new_type_counts[new_type] = new_type_counts.get(new_type, 0) + 1

        if i % 1000 == 0:
            print(f"    {i}/{len(rows)} processed...")
            conn.commit()

    conn.commit()
    print()
    for k, v in counters.items():
        print(f"  {k}: {v}")
    print()
    print("  new article_type distribution:")
    for k, v in sorted(new_type_counts.items(), key=lambda x: -x[1]):
        print(f"    {v:>6}  {k}")


if __name__ == "__main__":
    main()
