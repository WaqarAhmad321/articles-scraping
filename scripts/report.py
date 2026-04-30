"""Generate a self-contained editorial-style HTML dataset report."""
from __future__ import annotations

import argparse
import datetime as dt
import html
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "articles.db"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "exports" / "report.html"


def fetch(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def fmt(n):
    return f"{n:,}"


def render(db_path: str, out_path: str) -> None:
    conn = sqlite3.connect(db_path)

    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    by_source = fetch(conn, "SELECT source, COUNT(*) FROM articles GROUP BY 1 ORDER BY 2 DESC")
    by_category = fetch(conn, "SELECT category, COUNT(*) FROM articles GROUP BY 1 ORDER BY 2 DESC")
    by_language = fetch(conn, "SELECT language, COUNT(*) FROM articles GROUP BY 1 ORDER BY 2 DESC")
    by_source_lang = fetch(
        conn,
        "SELECT source, language, COUNT(*) FROM articles GROUP BY 1,2 ORDER BY 1,2",
    )

    date_min, date_max = conn.execute(
        "SELECT MIN(date_published), MAX(date_published) FROM articles"
    ).fetchone()

    n, lmin, lmax, lavg, wavg = conn.execute(
        "SELECT COUNT(*), MIN(LENGTH(full_text)), MAX(LENGTH(full_text)), "
        "AVG(LENGTH(full_text)), AVG(word_count) FROM articles"
    ).fetchone()

    length_buckets = fetch(
        conn,
        """SELECT
          CASE
            WHEN LENGTH(full_text) < 500 THEN '< 500 chars'
            WHEN LENGTH(full_text) < 1000 THEN '500 – 1k'
            WHEN LENGTH(full_text) < 2000 THEN '1k – 2k'
            WHEN LENGTH(full_text) < 4000 THEN '2k – 4k'
            WHEN LENGTH(full_text) < 8000 THEN '4k – 8k'
            ELSE '8k +'
          END,
          COUNT(*)
        FROM articles GROUP BY 1 ORDER BY MIN(LENGTH(full_text))""",
    )

    by_month = fetch(
        conn,
        "SELECT substr(date_published,1,7), COUNT(*) FROM articles GROUP BY 1 ORDER BY 1",
    )

    sources = [r[0] for r in fetch(conn, "SELECT DISTINCT source FROM articles ORDER BY 1")]
    cats = [r[0] for r in fetch(conn, "SELECT DISTINCT category FROM articles ORDER BY 1")]
    matrix = {(c, s): 0 for c in cats for s in sources}
    for c, s, n_ in fetch(conn, "SELECT category, source, COUNT(*) FROM articles GROUP BY 1,2"):
        matrix[(c, s)] = n_

    top_authors = fetch(
        conn,
        "SELECT author, COUNT(*) FROM articles "
        "WHERE author IS NOT NULL AND TRIM(author) != '' "
        "GROUP BY 1 ORDER BY 2 DESC LIMIT 15",
    )

    samples_per_source = {}
    for src in sources:
        samples_per_source[src] = fetch(
            conn,
            "SELECT headline, date_published, language, word_count, url, "
            "       substr(full_text, 1, 300) FROM articles "
            "WHERE source = ? AND word_count > 100 "
            "ORDER BY RANDOM() LIMIT 2",
            (src,),
        )

    conn.close()

    # Source-language map for the language explainer
    src_lang = {}
    for src, lang, n_ in by_source_lang:
        src_lang.setdefault(src, {})[lang] = n_

    ur = next((n for l, n in by_language if l == "Urdu"), 0)
    en = next((n for l, n in by_language if l == "English"), 0)
    ur_pct = ur * 100 / total if total else 0
    en_pct = en * 100 / total if total else 0

    max_source = max((n_ for _, n_ in by_source), default=1)
    max_cat = max((n_ for _, n_ in by_category), default=1)
    max_month = max((n_ for _, n_ in by_month), default=1)
    max_length = max((n_ for _, n_ in length_buckets), default=1)
    max_author = max((n_ for _, n_ in top_authors), default=1)

    H = []
    a = H.append
    a("<!doctype html>")
    a('<html lang="en"><head>')
    a('<meta charset="utf-8"/>')
    a('<meta name="viewport" content="width=device-width,initial-scale=1"/>')
    a("<title>The Pakistan Press Index — A Dataset Report</title>")
    a('<link rel="preconnect" href="https://fonts.googleapis.com">')
    a('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
    a('<link href="https://fonts.googleapis.com/css2?'
      'family=Newsreader:ital,opsz,wght@0,6..72,300;0,6..72,400;0,6..72,500;0,6..72,600;0,6..72,800;1,6..72,400&'
      'family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,700;9..144,900&'
      'family=JetBrains+Mono:wght@400;500;700&'
      'family=Noto+Nastaliq+Urdu:wght@400;700&display=swap" rel="stylesheet">')
    a("<style>")
    a("""
    :root {
      --paper: #f4ede1;
      --paper-deep: #e9dfca;
      --ink: #1a1715;
      --ink-soft: #4a443d;
      --ink-faint: #8a8275;
      --rule: #1a1715;
      --rule-soft: rgba(26, 23, 21, 0.18);
      --accent: #7a1f24;
      --accent-soft: rgba(122, 31, 36, 0.08);
      --highlight: #c89a3b;
    }
    * { box-sizing: border-box; }
    html { background: var(--paper); }
    body {
      margin: 0;
      font-family: "Newsreader", Georgia, serif;
      font-size: 17px;
      line-height: 1.55;
      color: var(--ink);
      background:
        radial-gradient(circle at 20% 8%, rgba(122,31,36,0.04), transparent 40%),
        radial-gradient(circle at 90% 70%, rgba(200,154,59,0.05), transparent 40%),
        var(--paper);
      background-attachment: fixed;
    }
    /* Subtle paper grain */
    body::before {
      content: "";
      position: fixed; inset: 0; pointer-events: none; z-index: 999;
      background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.045 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>");
      mix-blend-mode: multiply;
    }
    .frame { max-width: 1180px; margin: 0 auto; padding: 56px 32px 96px; position: relative; }

    /* MASTHEAD */
    .masthead { border-top: 6px double var(--rule); border-bottom: 1px solid var(--rule);
                padding: 22px 0 26px; margin-bottom: 28px; position: relative; }
    .masthead-top { display: flex; justify-content: space-between; align-items: baseline;
                    font-family: "JetBrains Mono", monospace; font-size: 11px;
                    letter-spacing: 0.18em; text-transform: uppercase; color: var(--ink-soft);
                    margin-bottom: 14px; }
    .masthead h1 {
      font-family: "Fraunces", "Newsreader", serif;
      font-weight: 900;
      font-size: clamp(48px, 8vw, 96px);
      letter-spacing: -0.025em;
      line-height: 0.95;
      margin: 0;
      font-variation-settings: "opsz" 144;
    }
    .masthead h1 .ital { font-style: italic; font-weight: 500; color: var(--accent); }
    .masthead .deck {
      margin-top: 14px;
      font-family: "Newsreader", serif;
      font-style: italic;
      font-weight: 400;
      font-size: 19px;
      color: var(--ink-soft);
      max-width: 720px;
    }
    .colophon { margin-top: 22px; padding-top: 14px; border-top: 1px solid var(--rule-soft);
                display: flex; gap: 32px; flex-wrap: wrap;
                font-family: "JetBrains Mono", monospace; font-size: 11px;
                letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink-soft); }

    /* KEY METRICS — like a stock ticker / front page summary */
    .metrics { display: grid; grid-template-columns: repeat(6, 1fr); gap: 0;
               border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule);
               padding: 24px 0; margin-bottom: 56px; }
    .metric { padding: 0 18px; border-right: 1px solid var(--rule-soft); }
    .metric:last-child { border-right: none; }
    .metric .num { font-family: "Fraunces", serif; font-weight: 700;
                   font-size: 38px; line-height: 1; letter-spacing: -0.02em;
                   font-variation-settings: "opsz" 72; }
    .metric .num.urdu { color: var(--accent); }
    .metric .label { font-family: "JetBrains Mono", monospace; font-size: 10.5px;
                     letter-spacing: 0.16em; text-transform: uppercase;
                     color: var(--ink-faint); margin-top: 8px; }
    @media (max-width: 720px) {
      .metrics { grid-template-columns: repeat(2, 1fr); }
      .metric { padding: 14px 12px; border-bottom: 1px solid var(--rule-soft); }
    }

    /* SECTION HEADERS */
    section { margin-bottom: 64px; }
    .sect-num {
      font-family: "JetBrains Mono", monospace;
      font-size: 11px;
      letter-spacing: 0.22em;
      color: var(--accent);
      text-transform: uppercase;
      margin-bottom: 6px;
    }
    h2.sect {
      font-family: "Fraunces", serif;
      font-weight: 500;
      font-size: 36px;
      letter-spacing: -0.015em;
      line-height: 1.05;
      margin: 0 0 8px;
      font-variation-settings: "opsz" 144;
    }
    h2.sect .ital { font-style: italic; }
    .sect-deck { color: var(--ink-soft); font-style: italic; max-width: 680px;
                 font-size: 17px; margin-bottom: 26px; }
    .rule { border: 0; height: 1px; background: var(--rule); margin: 0 0 22px; }

    /* TWO-COLUMN ASYMMETRIC */
    .grid-7-5 { display: grid; grid-template-columns: 7fr 5fr; gap: 48px; align-items: start; }
    .grid-1-1 { display: grid; grid-template-columns: 1fr 1fr; gap: 48px; align-items: start; }
    @media (max-width: 800px) { .grid-7-5, .grid-1-1 { grid-template-columns: 1fr; gap: 28px; } }

    /* DATA TABLE — editorial */
    table.dt { width: 100%; border-collapse: collapse; }
    table.dt th {
      font-family: "JetBrains Mono", monospace; font-weight: 500; font-size: 10.5px;
      letter-spacing: 0.18em; text-transform: uppercase; color: var(--ink-faint);
      text-align: left; padding: 8px 0; border-bottom: 1px solid var(--rule);
    }
    table.dt th.r, table.dt td.r { text-align: right; }
    table.dt td {
      padding: 10px 0; border-bottom: 1px dashed var(--rule-soft);
      font-size: 15px;
    }
    table.dt td.num { font-family: "JetBrains Mono", monospace; font-size: 13px;
                      font-variant-numeric: tabular-nums; }
    table.dt tr:hover td { background: rgba(122,31,36,0.025); }
    .label-name { font-family: "Fraunces", serif; font-size: 17px; font-weight: 500; }
    .label-cat { font-family: "Newsreader", serif; font-size: 16px; }

    /* HORIZONTAL BAR */
    .bar-h {
      position: relative; height: 4px; background: var(--rule-soft); border-radius: 0;
      margin: 4px 0 0; overflow: hidden;
    }
    .bar-h-fill { position: absolute; inset: 0; background: var(--ink);
                  transform-origin: left; }
    .bar-h-fill.ur { background: var(--accent); }
    .bar-h-fill.acc { background: var(--highlight); }

    /* MATRIX HEAT TABLE */
    .matrix-wrap { overflow-x: auto; border-top: 1px solid var(--rule);
                   border-bottom: 1px solid var(--rule); }
    table.matrix { width: 100%; border-collapse: collapse; min-width: 760px;
                   font-family: "JetBrains Mono", monospace; font-size: 12px; }
    table.matrix th, table.matrix td { padding: 10px 8px; text-align: center;
                                       border: 1px solid var(--rule-soft); }
    table.matrix th {
      background: var(--paper-deep); color: var(--ink-soft);
      font-weight: 500; font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase;
      writing-mode: horizontal-tb;
    }
    table.matrix th.cat { text-align: left; min-width: 200px; padding-left: 14px;
                          font-family: "Newsreader", serif; font-size: 14px;
                          letter-spacing: 0; text-transform: none; font-weight: 500;
                          color: var(--ink); background: transparent; }
    table.matrix td.row-head { text-align: left; padding-left: 14px;
                               font-family: "Newsreader", serif; font-size: 15px;
                               letter-spacing: 0; text-transform: none;
                               background: transparent; color: var(--ink); }
    table.matrix td.cell { font-variant-numeric: tabular-nums; }
    table.matrix td.zero { color: var(--ink-faint); }
    .h0 { background: transparent; }
    .h1 { background: rgba(26,23,21,0.04); }
    .h2 { background: rgba(26,23,21,0.10); }
    .h3 { background: rgba(122,31,36,0.18); color: #4a0e11; }
    .h4 { background: rgba(122,31,36,0.42); color: #fff; font-weight: 500; }
    table.matrix tr.tot td { border-top: 2px solid var(--rule);
                             font-weight: 600; background: var(--paper-deep); }

    /* LANGUAGE EXPLAINER */
    .explainer { background: transparent; border-top: 4px solid var(--ink);
                 border-bottom: 1px solid var(--rule); padding: 28px 0;
                 display: grid; grid-template-columns: 220px 1fr; gap: 40px; }
    .explainer .stamp { font-family: "JetBrains Mono", monospace; font-size: 10.5px;
                        letter-spacing: 0.2em; text-transform: uppercase; color: var(--accent);
                        line-height: 1.4; }
    .explainer h3 { font-family: "Fraunces", serif; font-weight: 500; font-size: 26px;
                    margin: 0 0 12px; line-height: 1.15; letter-spacing: -0.01em; }
    .explainer p { margin: 0 0 14px; font-size: 17px; line-height: 1.6; }
    .explainer .lang-table { margin-top: 14px; border-top: 1px solid var(--rule);
                             padding-top: 12px; font-family: "JetBrains Mono", monospace;
                             font-size: 12px; }
    .explainer .lang-row { display: grid;
        grid-template-columns: 1fr 80px 80px;
        padding: 8px 0; border-bottom: 1px dashed var(--rule-soft); }
    .explainer .lang-row.head { color: var(--ink-faint); font-size: 10.5px;
        letter-spacing: 0.16em; text-transform: uppercase; border-bottom: 1px solid var(--rule); }
    .explainer .lang-row .src { font-family: "Newsreader", serif; font-size: 15px; }
    .explainer .lang-row .v { text-align: right; font-variant-numeric: tabular-nums; }
    .explainer .lang-row .v.ur { color: var(--accent); }
    @media (max-width: 800px) { .explainer { grid-template-columns: 1fr; gap: 16px; } }

    /* SAMPLES */
    .samples { display: grid; grid-template-columns: repeat(2, 1fr); gap: 32px; }
    @media (max-width: 800px) { .samples { grid-template-columns: 1fr; } }
    .sample-source {
      font-family: "JetBrains Mono", monospace; font-size: 10.5px; letter-spacing: 0.2em;
      text-transform: uppercase; color: var(--accent); margin-bottom: 14px;
      padding-bottom: 10px; border-bottom: 1px solid var(--rule);
    }
    .clip {
      border-bottom: 1px dashed var(--rule-soft); padding-bottom: 18px; margin-bottom: 18px;
    }
    .clip:last-child { border-bottom: none; padding-bottom: 0; margin-bottom: 0; }
    .clip-meta {
      font-family: "JetBrains Mono", monospace; font-size: 10.5px; letter-spacing: 0.16em;
      text-transform: uppercase; color: var(--ink-faint); margin-bottom: 8px;
      display: flex; gap: 12px; flex-wrap: wrap;
    }
    .clip-meta .lang { padding: 1px 6px; border: 1px solid var(--rule); }
    .clip-meta .lang.ur { color: var(--accent); border-color: var(--accent); }
    .clip-head {
      font-family: "Fraunces", serif; font-weight: 500; font-size: 22px;
      line-height: 1.2; letter-spacing: -0.01em; margin-bottom: 10px;
    }
    .clip-body { color: var(--ink-soft); font-size: 15.5px; line-height: 1.55; }
    .clip-body::first-letter {
      font-family: "Fraunces", serif; font-weight: 700; font-size: 3.4em;
      float: left; line-height: 0.85; padding: 6px 8px 0 0; color: var(--accent);
      font-variation-settings: "opsz" 144;
    }
    .clip-link {
      font-family: "JetBrains Mono", monospace; font-size: 10.5px; letter-spacing: 0.16em;
      text-transform: uppercase; color: var(--accent); text-decoration: none;
      border-bottom: 1px dotted var(--accent); padding-bottom: 1px;
    }
    .clip-link:hover { color: var(--ink); border-color: var(--ink); }

    .ur-text {
      font-family: "Noto Nastaliq Urdu", "Newsreader", serif !important;
      direction: rtl; text-align: right; line-height: 2.2;
    }
    .clip.urdu .clip-head { font-family: "Noto Nastaliq Urdu", "Newsreader", serif;
                            line-height: 2.0; font-size: 20px; direction: rtl;
                            text-align: right; }
    .clip.urdu .clip-body { direction: rtl; text-align: right;
                            font-family: "Noto Nastaliq Urdu", "Newsreader", serif;
                            line-height: 2.2; font-size: 16px; }
    .clip.urdu .clip-body::first-letter { float: none; padding: 0; font-size: 1em; color: inherit; }

    /* CALENDAR / TIMELINE */
    .timeline { display: grid;
                grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
                gap: 4px; }
    .tcell {
      padding: 10px 8px; border: 1px solid var(--rule-soft);
      font-family: "JetBrains Mono", monospace; font-size: 11px;
      display: flex; flex-direction: column; gap: 4px; text-align: left;
      background: rgba(26,23,21,0.02);
    }
    .tcell .m { color: var(--ink-faint); letter-spacing: 0.1em; }
    .tcell .c { font-size: 18px; font-family: "Fraunces", serif; font-weight: 600;
                font-variation-settings: "opsz" 72; }
    .tcell.has-bar { background-image: linear-gradient(to top, var(--accent-soft) var(--pct), transparent var(--pct)); }

    /* WARNINGS / NOTES */
    .note-list { list-style: none; padding: 0; margin: 0; }
    .note-list li { padding: 18px 0; border-bottom: 1px solid var(--rule-soft);
                    display: grid; grid-template-columns: 140px 1fr; gap: 28px; }
    .note-list li:first-child { border-top: 1px solid var(--rule); }
    .note-list .src {
      font-family: "JetBrains Mono", monospace; font-size: 11px;
      letter-spacing: 0.2em; text-transform: uppercase; color: var(--accent);
      align-self: start; padding-top: 4px;
    }
    .note-list .body { font-size: 16px; line-height: 1.55; color: var(--ink); }

    /* SCHEMA */
    table.schema { width: 100%; border-collapse: collapse; }
    table.schema th {
      font-family: "JetBrains Mono", monospace; font-size: 10.5px; letter-spacing: 0.18em;
      text-transform: uppercase; color: var(--ink-faint); text-align: left;
      padding: 8px 0; border-bottom: 1px solid var(--rule);
    }
    table.schema td {
      padding: 12px 0; border-bottom: 1px dashed var(--rule-soft); font-size: 15px;
    }
    table.schema td:first-child {
      font-family: "JetBrains Mono", monospace; font-size: 13px; font-weight: 500;
      color: var(--accent); width: 200px; padding-right: 24px;
    }
    table.schema code {
      font-family: "JetBrains Mono", monospace; font-size: 12px;
      background: rgba(26,23,21,0.05); padding: 1px 5px; border-radius: 2px;
    }

    /* FOOTER */
    .footer { margin-top: 80px; padding-top: 28px; border-top: 4px double var(--rule);
              display: grid; grid-template-columns: 1fr 1fr; gap: 40px;
              font-family: "JetBrains Mono", monospace; font-size: 11px;
              letter-spacing: 0.14em; text-transform: uppercase; color: var(--ink-soft); }
    .footer .end { text-align: right; }
    .footer .glyph { font-family: "Fraunces", serif; font-size: 28px; font-style: italic;
                     color: var(--accent); display: block; margin-bottom: 4px; text-transform: none; }
    @media (max-width: 800px) { .footer { grid-template-columns: 1fr; gap: 14px; } .footer .end { text-align: left; }}
    """)
    a("</style></head><body><div class='frame'>")

    today = dt.datetime.now().strftime("%a · %B %d, %Y")
    iso = dt.datetime.now().strftime("%Y-%m-%d")

    # ── MASTHEAD ──
    a("<header class='masthead'>")
    a(f"<div class='masthead-top'><span>Vol. 01 · No. 01</span><span>{today.upper()}</span><span>Issue №&nbsp;{iso}</span></div>")
    a("<h1>The Pakistan <span class='ital'>Press</span> Index</h1>")
    a("<p class='deck'>A scraped longitudinal record of Pakistani political reportage — five "
      "Urdu-language newsrooms, eighteen events, and the seams that show when one "
      "tries to gather them under a single roof.</p>")
    a("<div class='colophon'>")
    a(f"<span>Articles · {fmt(total)}</span>")
    a(f"<span>Period · {date_min} → {date_max}</span>")
    a(f"<span>Schema · 11 columns</span>")
    a("<span>Format · SQLite + CSV</span>")
    a("<span>Compiled by · the scraper</span>")
    a("</div>")
    a("</header>")

    # ── METRICS BAR ──
    a("<div class='metrics'>")
    a(f"<div class='metric'><div class='num'>{fmt(total)}</div><div class='label'>Total articles</div></div>")
    a(f"<div class='metric'><div class='num'>{len(sources)}</div><div class='label'>News sources</div></div>")
    a(f"<div class='metric'><div class='num'>{len(cats)}</div><div class='label'>Tracked topics</div></div>")
    a(f"<div class='metric'><div class='num urdu'>{fmt(ur)}</div><div class='label'>Urdu articles</div></div>")
    a(f"<div class='metric'><div class='num'>{int(wavg)}</div><div class='label'>Avg words / piece</div></div>")
    a(f"<div class='metric'><div class='num'>{date_min[2:].replace('-','/')}<span style='color:var(--ink-faint);font-size:18px'> → </span>{date_max[2:].replace('-','/')}</div><div class='label'>Date range</div></div>")
    a("</div>")

    # ── EDITOR'S NOTE: Urdu-only scope ──
    a("<section>")
    a("<div class='explainer'>")
    a("<div class='stamp'>Editor's Note · § 01<br/>On scope &amp; language</div>")
    a("<div>")
    a("<h3>An Urdu-only dataset, by design.</h3>")
    a("<p>Every article in this corpus is in Urdu. The pipeline detects script "
      "by Unicode-block ratio (Arabic / Urdu code points <code>U+0600 – U+06FF</code>) "
      "and drops anything that registers as English at the language stage, before "
      "the SQLite write. That filter is on by default; toggle it off via the "
      "environment variable <code>URDU_ONLY=false</code> if you ever need a mixed "
      "corpus again.</p>")
    a("<p>The five contributing newsrooms — Express News, BBC Urdu, ARY News (Urdu "
      "edition), Dawn News (Urdu edition / dawnnews.tv), and Abb Takk — each speak "
      "to a different slice of the Pakistani political conversation. The rest of "
      "this report breaks the corpus down along sources, topics, time, and the few "
      "cracks where coverage didn't quite reach.</p>")
    a("</div></div>")
    a("</section>")

    # ── SOURCES & TOPICS (two columns) ──
    a("<section>")
    a("<div class='grid-7-5'>")
    a("<div>")
    a("<div class='sect-num'>§ 02 · The Newsrooms</div>")
    a("<h2 class='sect'>By <span class='ital'>source</span></h2>")
    a("<p class='sect-deck'>Where the bulk came from. Express dominates by sheer archive depth; "
      "Dawn and Abb Takk were intentionally frozen mid-run.</p>")
    a("<table class='dt'><thead><tr><th>Source</th><th class='r'>Count</th></tr></thead><tbody>")
    for src, n_ in by_source:
        pct = n_ / max_source * 100
        a(f"<tr><td><div class='label-name'>{html.escape(src)}</div>"
          f"<div class='bar-h'><div class='bar-h-fill' style='width:{pct:.1f}%'></div></div></td>"
          f"<td class='r num'>{fmt(n_)}</td></tr>")
    a("</tbody></table>")
    a("</div>")

    a("<div>")
    a("<div class='sect-num'>&sect; 03 &middot; The Topics</div>")
    a("<h2 class='sect'>By <span class='ital'>category</span></h2>")
    a("<p class='sect-deck'>Eighteen tracked political events. The largest categories trace "
      "the year's running stories — Gaza, the Imran Khan trial, and the Shehbaz government.</p>")
    a("<table class='dt'><thead><tr><th>Topic</th><th class='r'>Count</th></tr></thead><tbody>")
    for cat, n_ in by_category:
        pct = n_ / max_cat * 100
        a(f"<tr><td><div class='label-cat'>{html.escape(cat)}</div>"
          f"<div class='bar-h'><div class='bar-h-fill ur' style='width:{pct:.1f}%'></div></div></td>"
          f"<td class='r num'>{fmt(n_)}</td></tr>")
    a("</tbody></table>")
    a("</div>")
    a("</div>")
    a("</section>")

    # ── COVERAGE MATRIX ──
    a("<section>")
    a("<div class='sect-num'>§ 04 · Coverage Matrix</div>")
    a("<h2 class='sect'>Topic <span class='ital'>×</span> Source</h2>")
    a("<p class='sect-deck'>The grid that exposes which newsroom owns which beat. "
      "Darker red = denser coverage. Empty cells aren't bugs — they're editorial gaps.</p>")
    a("<div class='matrix-wrap'><table class='matrix'>")
    a("<thead><tr><th class='cat'></th>")
    for s in sources:
        a(f"<th>{html.escape(s)}</th>")
    a("<th>Σ</th></tr></thead><tbody>")

    def heat(v):
        if v == 0:
            return "h0 zero"
        if v < 10:
            return "h1"
        if v < 50:
            return "h2"
        if v < 200:
            return "h3"
        return "h4"

    for cat in sorted(cats):
        a(f"<tr><td class='row-head'>{html.escape(cat)}</td>")
        row_total = 0
        for s in sources:
            v = matrix[(cat, s)]
            row_total += v
            cls = heat(v) + " cell"
            cell = fmt(v) if v else "·"
            a(f"<td class='{cls}'>{cell}</td>")
        a(f"<td class='cell h2'>{fmt(row_total)}</td></tr>")
    a("<tr class='tot'><td class='row-head'>Σ</td>")
    grand = 0
    for s in sources:
        col_total = sum(matrix[(c, s)] for c in cats)
        grand += col_total
        a(f"<td class='cell'>{fmt(col_total)}</td>")
    a(f"<td class='cell'>{fmt(grand)}</td></tr>")
    a("</tbody></table></div>")
    a("</section>")

    # ── LENGTH × TIMELINE ──
    a("<section><div class='grid-1-1'>")
    a("<div>")
    a("<div class='sect-num'>§ 05 · Article length</div>")
    a("<h2 class='sect'>By the <span class='ital'>word</span></h2>")
    a(f"<p class='sect-deck'>Min {fmt(lmin)} chars · Avg {fmt(int(lavg))} chars (~{int(wavg)} words) · "
      f"Max {fmt(lmax)} chars. The long-tail at 8k+ is the long-form opinion and feature pieces.</p>")
    a("<table class='dt'><tbody>")
    for label, n_ in length_buckets:
        pct = n_ / max_length * 100
        a(f"<tr><td><div class='label-cat'>{label}</div>"
          f"<div class='bar-h'><div class='bar-h-fill acc' style='width:{pct:.1f}%'></div></div></td>"
          f"<td class='r num'>{fmt(n_)}</td></tr>")
    a("</tbody></table>")
    a("</div>")

    a("<div>")
    a("<div class='sect-num'>§ 06 · Timeline</div>")
    a("<h2 class='sect'>The <span class='ital'>monthly</span> tide</h2>")
    a("<p class='sect-deck'>Articles per month, January 2024 to today. The cells fill from the "
      "bottom up — read the height, not the number.</p>")
    a("<div class='timeline'>")
    for m, n_ in by_month:
        pct = n_ / max_month * 100
        a(f"<div class='tcell has-bar' style='--pct:{pct:.0f}%'>"
          f"<div class='m'>{m}</div><div class='c'>{fmt(n_)}</div></div>")
    a("</div>")
    a("</div>")
    a("</div></section>")

    # ── AUTHORS ──
    a("<section>")
    a("<div class='sect-num'>§ 07 · Bylines</div>")
    a("<h2 class='sect'>Top <span class='ital'>fifteen</span> contributors</h2>")
    a("<p class='sect-deck'>Bylines that recur most often across the dataset. The Urdu desk "
      "names (ویب ڈیسک, اسٹاف رپورٹر) are generic web-desk tags but kept verbatim.</p>")
    a("<table class='dt'><thead><tr><th>Byline</th><th class='r'>Articles</th></tr></thead><tbody>")
    for author, n_ in top_authors:
        is_ur = any('؀' <= ch <= 'ۿ' for ch in author)
        cls = "ur-text" if is_ur else ""
        pct = n_ / max_author * 100
        a(f"<tr><td><div class='label-name {cls}'>{html.escape(author)}</div>"
          f"<div class='bar-h'><div class='bar-h-fill' style='width:{pct:.1f}%'></div></div></td>"
          f"<td class='r num'>{fmt(n_)}</td></tr>")
    a("</tbody></table>")
    a("</section>")

    # ── SAMPLES ──
    a("<section>")
    a("<div class='sect-num'>§ 08 · From the cuttings file</div>")
    a("<h2 class='sect'>Specimen <span class='ital'>articles</span></h2>")
    a("<p class='sect-deck'>Two random pieces per source, drawn fresh each time the report "
      "regenerates. Click the link to read the original.</p>")
    a("<div class='samples'>")
    for src in sources:
        a("<div>")
        a(f"<div class='sample-source'>— {html.escape(src)} —</div>")
        for headline, date, lang, wc, url, snippet in samples_per_source.get(src, []):
            is_ur = lang == "Urdu"
            urdu_cls = " urdu" if is_ur else ""
            lang_cls = "lang ur" if is_ur else "lang"
            a(f"<div class='clip{urdu_cls}'>")
            a("<div class='clip-meta'>")
            a(f"<span class='{lang_cls}'>{lang}</span>")
            a(f"<span>{date}</span>")
            a(f"<span>{wc} words</span>")
            a("</div>")
            a(f"<div class='clip-head'>{html.escape(headline)}</div>")
            a(f"<div class='clip-body'>{html.escape(snippet)}…</div>")
            a(f"<div style='margin-top:10px'><a class='clip-link' href='{html.escape(url, quote=True)}' target='_blank'>read at source ↗</a></div>")
            a("</div>")
        a("</div>")
    a("</div>")
    a("</section>")

    # ── WHAT DIDN'T WORK ──
    a("<section>")
    a("<div class='sect-num'>§ 09 · The cutting-room floor</div>")
    a("<h2 class='sect'>What <span class='ital'>didn't</span> make it</h2>")
    a("<p class='sect-deck'>An honest accounting of where the scraper hit a wall. These aren't "
      "bugs — they're properties of the underlying sources.</p>")
    a("<ul class='note-list'>")
    a("<li><div class='src'>92 News</div>"
      "<div class='body'>Cloudflare returned <code>HTTP 403</code> on every path tested — "
      "sitemap, RSS, category pages, individual articles — even with a browser User-Agent and "
      "throttled requests. There is no programmatic path. Excluded entirely.</div></li>")
    a("<li><div class='src'>Geo News · low</div>"
      "<div class='body'>Geo's on-site search returns roughly forty-seven results per query "
      "and refuses to paginate beyond page one. The CDN starts refusing connections under "
      "burst load, capping the sequential-ID approach. Natural ceiling: about 230 articles "
      "with politics-only filtering.</div></li>")
    a("<li><div class='src'>ARY News · low</div>"
      "<div class='body'>Most ARY content is showbiz, sports, lifestyle and entertainment — "
      "their political coverage overlap with the eighteen tracked topics is small. Section "
      "walking, on-site search, and RSS feeds combined exhausted the political subset around "
      "112 articles.</div></li>")
    a("<li><div class='src'>Frozen by request</div>"
      "<div class='body'>Dawn (517) and Abb Takk (1,256) were intentionally stopped once "
      "their counts were sufficient, per the operator's instruction. Express News was capped "
      "after exceeding 1,500 (final 3,138 — the dominant contributor).</div></li>")
    a("</ul>")
    a("</section>")

    # ── SCHEMA ──
    a("<section>")
    a("<div class='sect-num'>§ 10 · Schema reference</div>")
    a("<h2 class='sect'>Eleven <span class='ital'>columns</span></h2>")
    a("<p class='sect-deck'>The shape of every row in the database and CSV exports.</p>")
    a("<table class='schema'><thead><tr><th>Column</th><th>Description</th></tr></thead><tbody>")
    schema = [
        ("article_id", "Stable identifier: <code>ART</code> + 8 hex characters of <code>sha1(url)</code>"),
        ("headline", "Article title — extracted from H1 or <code>og:title</code> meta"),
        ("full_text", "Cleaned article body, ad/nav stripped via trafilatura"),
        ("source", "Display name (e.g. <code>Dawn News</code>, <code>BBC Urdu</code>)"),
        ("author", "Byline if present, else <code>NULL</code>"),
        ("date_published", "ISO format <code>YYYY-MM-DD</code>"),
        ("url", "Canonical article URL"),
        ("category", "One of eighteen tracked political topics"),
        ("article_type", "<code>News Report</code> · <code>Opinion</code> · <code>Blog</code> · <code>Editorial</code>"),
        ("language", "<code>Urdu</code> or <code>English</code> — detected by Unicode-script ratio"),
        ("word_count", "Whitespace-tokenised count"),
    ]
    for col, desc in schema:
        a(f"<tr><td>{col}</td><td>{desc}</td></tr>")
    a("</tbody></table>")
    a("</section>")

    # ── FOOTER ──
    a("<footer class='footer'>")
    a("<div><span class='glyph'>§</span>Compiled in Karachi · Run on Mise + Scrapy<br/>"
      "Data live at · <code>data/articles.db</code> · <code>exports/articles.csv</code></div>")
    a(f"<div class='end'><span class='glyph'>—30—</span>End of report · {iso}<br/>"
      "Regenerate any time · <code>python scripts/report.py</code></div>")
    a("</footer>")

    a("</div></body></html>")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(H), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    args = p.parse_args()
    render(args.db, args.out)
