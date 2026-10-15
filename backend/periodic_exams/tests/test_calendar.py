from datetime import date, datetime, timezone

import nepali_datetime
from django.test import SimpleTestCase

from periodic_exams.calendar import CalendarRangeError, KATHMANDU, ad_to_bs, month_length, period_for
from periodic_exams.calendar_data import BS_MONTH_LENGTHS


class CalendarAdapterTests(SimpleTestCase):
    def test_pinned_library_matches_verified_lookup_for_supported_years(self):
        for year in range(2083, 2091):
            for month in range(1, 13):
                first = nepali_datetime.date(year, month, 1).to_datetime_date()
                if month == 12:
                    following = nepali_datetime.date(year + 1, 1, 1).to_datetime_date()
                else:
                    following = nepali_datetime.date(year, month + 1, 1).to_datetime_date()
                self.assertEqual((following - first).days, BS_MONTH_LENGTHS[year][month - 1])
                self.assertEqual(month_length(year, month), BS_MONTH_LENGTHS[year][month - 1])

    def test_fails_closed_outside_supported_range(self):
        with self.assertRaises(CalendarRangeError):
            month_length(2082, 12)
        with self.assertRaises(CalendarRangeError):
            month_length(2091, 1)
        with self.assertRaises(CalendarRangeError):
            ad_to_bs(date(2025, 1, 1))

    def test_monthly_boundary_uses_variable_month_length(self):
        period = period_for('MONTHLY', datetime(2026, 4, 20, tzinfo=timezone.utc))
        self.assertEqual((period.start_bs.year, period.start_bs.month, period.start_bs.day), (2083, 1, 1))
        self.assertEqual((period.end_bs.year, period.end_bs.month, period.end_bs.day), (2083, 1, 31))
        self.assertEqual(period.start_date_ad, date(2026, 4, 14))

    def test_fiscal_quarter_half_year_and_year_boundaries(self):
        q1 = period_for('QUARTERLY', datetime(2026, 8, 1, tzinfo=timezone.utc))
        self.assertEqual((q1.start_bs.year, q1.start_bs.month), (2083, 4))
        self.assertEqual((q1.end_exclusive_bs.year, q1.end_exclusive_bs.month), (2083, 7))
        self.assertEqual(q1.period_number, 1)

        q4 = period_for('QUARTERLY', datetime(2027, 4, 20, tzinfo=timezone.utc))
        self.assertEqual((q4.start_bs.year, q4.start_bs.month), (2084, 1))
        self.assertEqual((q4.end_exclusive_bs.year, q4.end_exclusive_bs.month), (2084, 4))
        self.assertEqual((q4.fiscal_year_start_bs, q4.period_number), (2083, 4))

        h2 = period_for('HALF_YEARLY', datetime(2027, 2, 1, tzinfo=timezone.utc))
        self.assertEqual((h2.start_bs.year, h2.start_bs.month), (2083, 10))
        self.assertEqual((h2.end_exclusive_bs.year, h2.end_exclusive_bs.month), (2084, 4))
        self.assertEqual(h2.period_number, 2)

        year = period_for('YEARLY', datetime(2027, 2, 1, tzinfo=timezone.utc))
        self.assertEqual((year.start_bs.year, year.start_bs.month), (2083, 4))
        self.assertEqual((year.end_exclusive_bs.year, year.end_exclusive_bs.month), (2084, 4))

    def test_kathmandu_midnight_is_previous_utc_day(self):
        before = period_for('MONTHLY', datetime(2026, 7, 16, 18, 14, 59, tzinfo=timezone.utc))
        after = period_for('MONTHLY', datetime(2026, 7, 16, 18, 15, 0, tzinfo=timezone.utc))
        self.assertEqual((before.start_bs.year, before.start_bs.month), (2083, 3))
        self.assertEqual((after.start_bs.year, after.start_bs.month), (2083, 4))
        self.assertEqual(after.starts_at.astimezone(KATHMANDU).hour, 0)
        self.assertEqual(after.starts_at, datetime(2026, 7, 16, 18, 15, tzinfo=timezone.utc))
