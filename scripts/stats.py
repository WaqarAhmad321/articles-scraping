"""Print a coverage report: articles per (category × source) and per language."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "articles.db"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=str(DEFAULT_DB))
    args = p.parse_args()

    conn = sqlite3.connect(args.db)

    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    print(f"\n  Total articles: {total}\n")

    print("  By source:")
    for src, n in conn.execute(
        "SELECT source, COUNT(*) FROM articles GROUP BY source ORDER BY 2 DESC"
    ):
        print(f"    {n:>6}  {src}")

    print("\n  By category:")
    for cat, n in conn.execute(
        "SELECT category, COUNT(*) FROM articles GROUP BY category ORDER BY 2 DESC"
    ):
        print(f"    {n:>6}  {cat}")

    print("\n  By language:")
    for lang, n in conn.execute(
        "SELECT language, COUNT(*) FROM articles GROUP BY language ORDER BY 2 DESC"
    ):
        print(f"    {n:>6}  {lang}")

    print("\n  By article_type:")
    for at, n in conn.execute(
        "SELECT article_type, COUNT(*) FROM articles GROUP BY article_type ORDER BY 2 DESC"
    ):
        print(f"    {n:>6}  {at}")

    print("\n  Date range:")
    row = conn.execute("SELECT MIN(date_published), MAX(date_published) FROM articles").fetchone()
    print(f"    {row[0]}  →  {row[1]}")

    print("\n  Coverage matrix (source × category):")
    sources = [r[0] for r in conn.execute("SELECT DISTINCT source FROM articles ORDER BY 1")]
    cats = [r[0] for r in conn.execute("SELECT DISTINCT category FROM articles ORDER BY 1")]

    if sources and cats:
        cat_w = max(len(c) for c in cats)
        col_w = max(8, max(len(s.split()[0]) for s in sources))
        # Header
        print("    " + " " * cat_w + "  " + "  ".join(s[:col_w].ljust(col_w) for s in sources) + "  TOTAL")
        for cat in cats:
            row_cells = [cat.ljust(cat_w)]
            row_total = 0
            for src in sources:
                n = conn.execute(
                    "SELECT COUNT(*) FROM articles WHERE category=? AND source=?",
                    (cat, src),
                ).fetchone()[0]
                row_cells.append(str(n).rjust(col_w))
                row_total += n
            row_cells.append(str(row_total).rjust(6))
            print("    " + "  ".join(row_cells))

    print("\n  Top 10 authors:")
    for author, n in conn.execute(
        "SELECT author, COUNT(*) FROM articles WHERE author IS NOT NULL GROUP BY author ORDER BY 2 DESC LIMIT 10"
    ):
        print(f"    {n:>4}  {author}")

    conn.close()


if __name__ == "__main__":
    main()
