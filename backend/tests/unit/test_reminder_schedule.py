"""Reminder dates: occurrences, lead time, Eastern send times, describe()."""

from datetime import date, datetime, time

import pytest

from app.services.reminders.schedule import describe, next_due, occurrence, send_at

pytestmark = pytest.mark.unit

EIGHT = time(8, 0)


class TestOccurrences:
    def test_weekly(self):
        assert occurrence(date(2026, 12, 3), "weekly", 2) == date(2026, 12, 17)

    def test_monthly_keeps_its_day_and_falls_back_to_month_end(self):
        start = date(2027, 1, 31)
        got = [occurrence(start, "monthly", k) for k in range(4)]
        assert got == [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31), date(2027, 4, 30)]

    def test_yearly_leap_day(self):
        assert occurrence(date(2028, 2, 29), "yearly", 1) == date(2029, 2, 28)
        assert occurrence(date(2028, 2, 29), "yearly", 4) == date(2032, 2, 29)

    def test_one_off_has_only_one(self):
        assert occurrence(date(2026, 12, 25), "none", 0) == date(2026, 12, 25)
        assert occurrence(date(2026, 12, 25), "none", 1) is None


class TestSendAt:
    def test_eastern_standard_time(self):
        # 8:00 AM EST = 13:00 UTC; three days before Dec 25
        assert send_at(date(2026, 12, 25), 3, EIGHT) == datetime(2026, 12, 22, 13, 0)

    def test_eastern_daylight_time(self):
        assert send_at(date(2027, 7, 4), 0, EIGHT) == datetime(2027, 7, 4, 12, 0)


class TestNextDue:
    def test_first_occurrence_still_ahead(self):
        now = datetime(2026, 11, 26, 15, 0)  # 10 AM ET on the 26th
        # Monthly on the 25th, 3 days before: the 22nd has passed, so Dec 25.
        assert next_due(date(2026, 1, 25), "monthly", 3, EIGHT, now) == (
            date(2026, 12, 25),
            datetime(2026, 12, 22, 13, 0),
        )

    def test_after_sending_moves_past_that_occurrence(self):
        # Sent the Dec 25 one late (on the 23rd): next is Jan 25, not Dec 25 again.
        now = datetime(2026, 12, 23, 13, 5)
        got = next_due(date(2026, 1, 25), "monthly", 3, EIGHT, now, past_event=date(2026, 12, 25))
        assert got == (date(2027, 1, 25), datetime(2027, 1, 22, 13, 0))

    def test_catching_up_skips_missed_occurrences(self):
        # Down for two weeks over a weekly reminder: next is the first still ahead.
        now = datetime(2026, 12, 20, 12, 0)
        got = next_due(date(2026, 11, 2), "weekly", 0, EIGHT, now, past_event=date(2026, 11, 30))
        assert got == (date(2026, 12, 21), datetime(2026, 12, 21, 13, 0))

    def test_one_off_in_the_past_has_none(self):
        assert next_due(date(2026, 11, 1), "none", 0, EIGHT, datetime(2026, 11, 26)) is None


@pytest.mark.parametrize(
    "start, repeat, lead, text",
    [
        (date(2026, 12, 25), "none", 3, "Once, Fri Dec 25, 2026 · 3 days before · 8:00 AM ET"),
        (date(2026, 12, 3), "weekly", 1, "Every Thursday · 1 day before · 8:00 AM ET"),
        (date(2026, 1, 22), "monthly", 0, "Every month on the 22nd · on the day · 8:00 AM ET"),
        (date(2026, 6, 11), "monthly", 0, "Every month on the 11th · on the day · 8:00 AM ET"),
        (date(2027, 3, 15), "yearly", 30, "Every year on March 15 · 30 days before · 8:00 AM ET"),
    ],
)
def test_describe(start, repeat, lead, text):
    assert describe(start, repeat, lead, EIGHT) == text
