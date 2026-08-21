import unittest
from datetime import datetime

from automation.config import ScheduleConfig
from automation.schedule import decide, full_scan_interval


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.config = ScheduleConfig()

    def test_weekday_active_is_five_minutes(self):
        now = datetime.fromisoformat("2026-08-04T10:00:00+08:00")
        self.assertEqual(full_scan_interval(now, self.config), 5)

    def test_weekday_quiet_is_thirty_minutes(self):
        now = datetime.fromisoformat("2026-08-04T23:00:00+08:00")
        self.assertEqual(full_scan_interval(now, self.config), 30)

    def test_weekend_day_and_night(self):
        day = datetime.fromisoformat("2026-08-08T10:00:00+08:00")
        night = datetime.fromisoformat("2026-08-08T23:00:00+08:00")
        self.assertEqual(full_scan_interval(day, self.config), 30)
        self.assertEqual(full_scan_interval(night, self.config), 60)

    def test_awaiting_reply_keeps_fast_poll_for_six_hours(self):
        now = datetime.fromisoformat("2026-08-08T23:00:00+08:00")
        batches = [
            {
                "status": "awaiting_review",
                "dispatched_at": "2026-08-08T20:00:00+08:00",
            }
        ]
        decision = decide({}, batches, now, self.config)
        self.assertEqual(decision.full_scan_interval_minutes, 60)
        self.assertEqual(decision.reply_poll_interval_minutes, 5)


if __name__ == "__main__":
    unittest.main()
