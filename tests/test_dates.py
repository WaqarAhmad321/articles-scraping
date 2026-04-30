from articles_scraper.utils.dates import in_range, parse_date


def test_iso():
    assert parse_date("2024-02-10") == "2024-02-10"


def test_human_readable():
    assert parse_date("February 10, 2024") == "2024-02-10"


def test_with_time():
    assert parse_date("2024-02-10T08:30:00+05:00") == "2024-02-10"


def test_garbage():
    assert parse_date("") is None
    assert parse_date(None) is None


def test_in_range():
    assert in_range("2024-02-10", "2024-01-01", "2024-12-31") is True
    assert in_range("2022-12-31", "2024-01-01", "2024-12-31") is False
    assert in_range("2025-01-01", "2024-01-01", "2024-12-31") is False
    assert in_range(None, "2024-01-01", "2024-12-31") is False
