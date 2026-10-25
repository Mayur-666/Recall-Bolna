from datetime import date

from app.services.dates import humanize, parse_relative_range

TODAY = date(2026, 10, 25)  # a Sunday


def test_last_week_range():
    assert parse_relative_range("What did we decide last week?", TODAY) == (
        date(2026, 10, 12),
        date(2026, 10, 18),
    )


def test_this_week_range():
    assert parse_relative_range("anything this week", TODAY) == (date(2026, 10, 19), TODAY)


def test_yesterday_and_today():
    assert parse_relative_range("what happened yesterday", TODAY) == (date(2026, 10, 24), date(2026, 10, 24))
    assert parse_relative_range("Today's call", TODAY) == (TODAY, TODAY)


def test_n_days_ago_allows_one_day_slack():
    assert parse_relative_range("the meeting 3 days ago", TODAY) == (date(2026, 10, 21), date(2026, 10, 23))


def test_last_month():
    assert parse_relative_range("last month", TODAY) == (date(2026, 9, 1), date(2026, 9, 30))


def test_last_weekday():
    assert parse_relative_range("what did we say last Tuesday", TODAY) == (
        date(2026, 10, 20),
        date(2026, 10, 20),
    )


def test_no_relative_phrase_none():
    assert parse_relative_range("What did Priya say about WebSockets?", TODAY) is None


def test_humanize_variants():
    assert humanize(TODAY, TODAY) == "today"
    assert humanize(date(2026, 10, 24), TODAY) == "yesterday"
    assert humanize(date(2026, 10, 22), TODAY) == "3 days ago, on Thursday"
    assert humanize(date(2026, 10, 12), TODAY) == "on Monday, 12 October"
    assert humanize(date(2025, 12, 1), TODAY) == "on 1 December 2025"
