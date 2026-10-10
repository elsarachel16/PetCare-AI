"""Date parsing and reminder helpers (no external dependencies)."""
import re
from datetime import date, timedelta
from typing import Optional

_MONTH_NAMES = (
    "january|february|march|april|june|july|august|september|october|november|december|"
    "jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec"
)
_MONTH_NUM = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _future(month: int, day: int, today: date) -> Optional[date]:
    try:
        d = date(today.year, month, day)
        if d < today:
            d = date(today.year + 1, month, day)
        return d
    except ValueError:
        return None


def parse_date(text: str, today: Optional[date] = None) -> Optional[date]:
    """Find a date in free text: '20 October', 'Oct 20th', '2026-10-20', 'tomorrow', 'next friday', 'in 2 weeks'."""
    today = today or date.today()
    low = text.lower()

    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", low)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    m = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_NAMES})\b", low)
    if m:
        return _future(_MONTH_NUM[m.group(2)[:3]], int(m.group(1)), today)

    m = re.search(rf"\b({_MONTH_NAMES})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", low)
    if m:
        return _future(_MONTH_NUM[m.group(1)[:3]], int(m.group(2)), today)

    if re.search(r"\btomorrow\b", low):
        return today + timedelta(days=1)

    m = re.search(r"\bin\s+(\d+)\s+(day|week)s?\b", low)
    if m:
        return today + timedelta(days=int(m.group(1)) * (7 if m.group(2) == "week" else 1))

    m = re.search(r"\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", low)
    if m:
        target = _WEEKDAYS.index(m.group(1))
        delta = (target - today.weekday()) % 7 or 7
        return today + timedelta(days=delta)

    if re.search(r"\bnext week\b", low):
        return today + timedelta(days=7)
    return None


def parse_interval_weeks(text: str) -> Optional[int]:
    """'every 4 weeks' -> 4, 'every month' -> 4, 'weekly' -> 1, 'every other week' -> 2."""
    low = text.lower()
    m = re.search(r"every\s+(\d+)\s*(week|wk|month)s?", low)
    if m:
        n = int(m.group(1))
        return n * 4 if m.group(2) == "month" else n
    if re.search(r"every other week|fortnight", low):
        return 2
    if re.search(r"every week|weekly", low):
        return 1
    if re.search(r"every month|monthly", low):
        return 4
    return None


def next_due(due: date, repeat_weeks: int, today: Optional[date] = None) -> date:
    """Advance a repeating reminder to its next occurrence after today."""
    today = today or date.today()
    step = timedelta(weeks=max(1, repeat_weeks))
    nxt = due + step
    while nxt <= today:
        nxt += step
    return nxt
