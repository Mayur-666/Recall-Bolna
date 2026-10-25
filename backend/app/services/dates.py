"""Relative-date parsing for questions and spoken-friendly date phrases for answers.

Weeks start on Monday. "N days ago" allows one day of slack either side because
people round when they speak.
"""

import calendar
import re
from datetime import date, timedelta

_WEEKDAYS = [d.lower() for d in calendar.day_name]
_N_DAYS = re.compile(r"\b(\d{1,2})\s+days?\s+ago\b")
_LAST_WEEKDAY = re.compile(r"\blast\s+(" + "|".join(_WEEKDAYS) + r")\b")


def parse_relative_range(text: str, today: date) -> tuple[date, date] | None:
    t = text.lower()
    week_start = today - timedelta(days=today.weekday())

    if m := _N_DAYS.search(t):
        n = int(m.group(1))
        return today - timedelta(days=n + 1), today - timedelta(days=max(n - 1, 0))
    if m := _LAST_WEEKDAY.search(t):
        target = _WEEKDAYS.index(m.group(1))
        back = (today.weekday() - target) % 7 or 7
        day = today - timedelta(days=back)
        return day, day
    if re.search(r"\byesterday\b", t):
        day = today - timedelta(days=1)
        return day, day
    if re.search(r"\btoday\b|\btoday's\b", t):
        return today, today
    if re.search(r"\blast\s+week\b", t):
        return week_start - timedelta(days=7), week_start - timedelta(days=1)
    if re.search(r"\bthis\s+week\b", t):
        return week_start, today
    if re.search(r"\blast\s+month\b", t):
        last_of_prev = today.replace(day=1) - timedelta(days=1)
        return last_of_prev.replace(day=1), last_of_prev
    if re.search(r"\bthis\s+month\b", t):
        return today.replace(day=1), today
    return None


def humanize(d: date, today: date) -> str:
    delta = (today - d).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "yesterday"
    if 2 <= delta <= 6:
        return f"{delta} days ago, on {d:%A}"
    if d.year != today.year:
        return f"on {d.day} {d:%B %Y}"
    if 7 <= delta <= 13:
        return f"on {d:%A}, {d.day} {d:%B}"
    if delta < 0:
        return f"on {d.day} {d:%B}" + ("" if d.year == today.year else f" {d.year}")
    return f"on {d:%A}, {d.day} {d:%B}" if delta <= 30 else f"on {d.day} {d:%B}"


def today_local() -> date:
    """Today's date in the app's configured timezone (relative dates are spoken in local time)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.core.config import get_settings

    return datetime.now(ZoneInfo(get_settings().APP_TIMEZONE)).date()
