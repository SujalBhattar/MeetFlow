"""Deadline parsing shared by reminders, digests, Trello and the extractor.

Understands ISO dates, day-first dates, "November 24", "Dec 5th",
"Friday", "next Monday", "tomorrow" and "in 3 days".
Relative words are resolved against `today` (pass the meeting date to
resolve them against the meeting instead).
"""

import re
from datetime import date, datetime, timedelta

ABSOLUTE_FORMATS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%b %d %Y",
    "%d %B %Y",
    "%d %b %Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d-%m-%Y %H:%M",
)

# Used after commas and ordinal suffixes (1st, 2nd, 5th) are removed.
MONTH_DAY_FORMATS = (
    "%B %d %Y",
    "%b %d %Y",
    "%d %B %Y",
    "%d %b %Y",
    "%B %d",
    "%b %d",
    "%d %B",
    "%d %b",
)

WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

EMPTY_VALUES = {
    "", "null", "none", "n/a", "na", "unknown", "tbd",
    "not specified", "unspecified",
}


def parse_deadline(value, today=None):
    """Return a `date`, or None if the text cannot be understood."""

    if value is None:
        return None

    today = today or date.today()
    text = str(value).strip()

    if text.lower() in EMPTY_VALUES:
        return None

    # 1. Exact calendar formats.
    for fmt in ABSOLUTE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    # 2. ISO timestamps, including a trailing "Z".
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass

    # 3. Casual wording.
    cleaned = text.lower()
    cleaned = re.sub(r"^(?:due by|due|by|on|before|until)\s+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned.strip(" .!"))

    relative = _parse_relative(cleaned, today)

    if relative:
        return relative

    # 4. "December 5th", "5 Dec", "Dec 5, 2026" (year defaults to today's).
    day_text = re.sub(r"(\d)(?:st|nd|rd|th)\b", r"\1", cleaned)
    day_text = re.sub(r"\s+", " ", day_text.replace(",", " ")).strip()

    for fmt in MONTH_DAY_FORMATS:
        try:
            parsed = datetime.strptime(day_text, fmt)
        except ValueError:
            continue

        if "%Y" in fmt:
            return parsed.date()

        try:
            return parsed.date().replace(year=today.year)
        except ValueError:
            return None

    return None


def _parse_relative(text, today):

    if text in ("today", "tonight", "eod", "end of day", "end of today"):
        return today

    if text == "tomorrow":
        return today + timedelta(days=1)

    if text == "day after tomorrow":
        return today + timedelta(days=2)

    if text in ("end of week", "end of the week", "eow"):
        return _upcoming_weekday(today, 4, strictly_after=False)

    match = re.fullmatch(r"in (\d+) (day|days|week|weeks)", text)

    if match:
        amount = int(match.group(1))
        unit_days = 7 if match.group(2).startswith("week") else 1
        return today + timedelta(days=amount * unit_days)

    match = re.fullmatch(r"(?:(this|next) )?([a-z]+)", text)

    if match and match.group(2) in WEEKDAYS:
        return _upcoming_weekday(
            today,
            WEEKDAYS[match.group(2)],
            strictly_after=(match.group(1) == "next")
        )

    return None


def _upcoming_weekday(today, weekday, strictly_after):

    days_ahead = (weekday - today.weekday()) % 7

    if strictly_after and days_ahead == 0:
        days_ahead = 7

    return today + timedelta(days=days_ahead)


def normalize_deadline(value, today=None):
    """Turn a spoken deadline into "YYYY-MM-DD" when possible.

    Text that cannot be understood is kept as-is so no information is
    lost. Empty-ish values such as "null" or "TBD" become None.
    """

    if value is None:
        return None

    text = str(value).strip()

    if text.lower() in EMPTY_VALUES:
        return None

    parsed = parse_deadline(text, today)

    return parsed.isoformat() if parsed else text
