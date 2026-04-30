from __future__ import annotations

import re
from datetime import date, datetime

from dateutil import parser as dateparser

_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def parse_date(value: str | None) -> str | None:
    """Parse a heterogeneous date string into ISO YYYY-MM-DD, or None."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None

    m = _ISO_RE.search(value)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    try:
        dt = dateparser.parse(value, dayfirst=False, fuzzy=True)
    except (ValueError, OverflowError):
        return None
    return dt.date().isoformat()


def in_range(iso_date: str | None, start: str | None, end: str | None) -> bool:
    if not iso_date:
        return False
    try:
        d = date.fromisoformat(iso_date)
    except ValueError:
        return False
    if start and d < date.fromisoformat(start):
        return False
    if end and d > date.fromisoformat(end):
        return False
    return True
