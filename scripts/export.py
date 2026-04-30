"""Export scraped articles from SQLite to CSV or JSONL.

Usage:
  python scripts/export.py --out exports/articles.csv
  python scripts/export.py --out exports/gaza.jsonl --category "Gaza Conflict Coverage"
  python scripts/export.py --out exports/dawn.csv --source "Dawn News"
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path

COLUMNS = [
    "article_id", "headline", "full_text", "source", "author",
    "date_published", "url", "category", "article_type", "language", "word_count",
]

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "articles.db"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--out", required=True)
    p.add_argument("--category")
    p.add_argument("--source")
    p.add_argument("--language")
    args = p.parse_args()

    where, params = [], []
    for col, val in (("category", args.category), ("source", args.source), ("language", args.language)):
        if val:
            where.append(f"{col} = ?")
            params.append(val)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        f"SELECT {', '.join(COLUMNS)} FROM articles {where_sql} ORDER BY date_published DESC",
        params,
    )

    n = 0
    if out.suffix.lower() == ".jsonl":
        with out.open("w", encoding="utf-8") as f:
            for row in cur:
                f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
                n += 1
    else:
        with out.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            for row in cur:
                w.writerow(dict(row))
                n += 1

    conn.close()
    print(f"wrote {n} rows -> {out}")


if __name__ == "__main__":
    main()
