import unittest
from datetime import date

from core.dates import normalize_deadline, parse_deadline

# Saturday
TODAY = date(2026, 11, 21)


class ParseDeadlineTests(unittest.TestCase):

    def check(self, text, expected):
        self.assertEqual(parse_deadline(text, TODAY), expected, text)

    def test_calendar_formats(self):
        self.check("2026-12-05", date(2026, 12, 5))
        self.check("05-12-2026", date(2026, 12, 5))
        self.check("05/12/2026", date(2026, 12, 5))
        self.check("December 5, 2026", date(2026, 12, 5))
        self.check("2026-12-05T10:30:00Z", date(2026, 12, 5))

    def test_month_and_day_only_use_current_year(self):
        self.check("November 24", date(2026, 11, 24))
        self.check("by December 5th", date(2026, 12, 5))
        self.check("5 Dec", date(2026, 12, 5))

    def test_relative_words(self):
        self.check("today", TODAY)
        self.check("tomorrow", date(2026, 11, 22))
        self.check("in 3 days", date(2026, 11, 24))
        self.check("in 2 weeks", date(2026, 12, 5))

    def test_weekdays(self):
        self.check("Friday", date(2026, 11, 27))
        self.check("by Monday", date(2026, 11, 23))
        self.check("next Saturday", date(2026, 11, 28))
        self.check("end of week", date(2026, 11, 27))

    def test_unusable_values(self):
        for text in (None, "", "null", "TBD", "soon", "sometime later"):
            self.assertIsNone(parse_deadline(text, TODAY), text)


class NormalizeDeadlineTests(unittest.TestCase):

    def test_understood_text_becomes_iso(self):
        self.assertEqual(
            normalize_deadline("November 24", TODAY), "2026-11-24"
        )

    def test_unknown_text_is_kept(self):
        self.assertEqual(
            normalize_deadline("after the holidays", TODAY),
            "after the holidays"
        )

    def test_placeholder_words_become_none(self):
        self.assertIsNone(normalize_deadline("null", TODAY))
        self.assertIsNone(normalize_deadline("  ", TODAY))


if __name__ == "__main__":
    unittest.main()
