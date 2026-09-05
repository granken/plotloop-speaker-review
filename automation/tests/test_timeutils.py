import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from automation.timeutils import get_timezone, parse_display_datetime, DEFAULT_TIMEZONE

class TimeUtilsTests(unittest.TestCase):
    def test_get_timezone_valid(self):
        tz = get_timezone("UTC")
        self.assertIsInstance(tz, ZoneInfo)
        self.assertEqual(str(tz), "UTC")

        tz_default = get_timezone()
        self.assertEqual(str(tz_default), DEFAULT_TIMEZONE)

    def test_get_timezone_invalid(self):
        with self.assertRaises(ValueError) as ctx:
            get_timezone("Invalid/Timezone")
        self.assertIn("unknown timezone: Invalid/Timezone", str(ctx.exception))

    def test_parse_display_datetime_naive(self):
        dt = parse_display_datetime("2023-01-01T12:00:00")
        self.assertIsNone(dt.tzinfo)
        self.assertEqual(dt, datetime(2023, 1, 1, 12, 0, 0))

    def test_parse_display_datetime_with_z(self):
        dt = parse_display_datetime("2023-01-01T12:00:00Z")
        self.assertIsNotNone(dt.tzinfo)
        # Should be converted to DEFAULT_TIMEZONE
        self.assertEqual(str(dt.tzinfo), DEFAULT_TIMEZONE)

        # We can also check explicit timezone conversion
        dt_explicit = parse_display_datetime("2023-01-01T12:00:00Z", timezone="UTC")
        self.assertEqual(dt_explicit.hour, 12)
        self.assertEqual(str(dt_explicit.tzinfo), "UTC")

    def test_parse_display_datetime_with_offset(self):
        dt = parse_display_datetime("2023-01-01T08:00:00-04:00", timezone="UTC")
        self.assertEqual(dt.hour, 12)
        self.assertEqual(str(dt.tzinfo), "UTC")

    def test_parse_display_datetime_explicit_timezone(self):
        # 12:00:00 UTC to America/New_York
        dt = parse_display_datetime("2023-01-01T12:00:00Z", timezone="America/New_York")
        self.assertEqual(dt.hour, 7)
        self.assertEqual(str(dt.tzinfo), "America/New_York")

if __name__ == "__main__":
    unittest.main()
