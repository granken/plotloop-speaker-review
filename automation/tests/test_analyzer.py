import unittest
from datetime import datetime

from automation.analyzer import CodexAnalyzer


class AnalyzerTests(unittest.TestCase):
    def test_recording_metadata_overrides_model_naming_fields(self):
        payload = {
            "review": {
                "current": {
                    "meeting": "模型改写的标题",
                    "date": "2026-08-03",
                    "time": "00:00:00",
                    "file_stem": "2026-08-04_171230_模型前缀",
                }
            }
        }
        recording = {
            "title": "产品增长链路与付费转化策略分析",
            "created_at": "2026-08-04T17:12:30+08:00",
        }

        CodexAnalyzer._normalize_review_metadata(payload, recording)

        current = payload["review"]["current"]
        self.assertEqual(current["meeting"], recording["title"])
        self.assertEqual(current["file_stem"], recording["title"])
        self.assertEqual(current["date"], "2026-08-04")
        self.assertEqual(current["time"], "17:12:30")

    def test_utc_metadata_is_normalized_to_the_local_timezone(self):
        payload = {
            "review": {
                "current": {
                    "meeting": "测试会议",
                    "date": "",
                    "time": "",
                    "file_stem": "测试会议",
                }
            }
        }
        recording = {
            "title": "测试会议",
            "created_at": "2026-08-04T09:12:30Z",
        }

        CodexAnalyzer._normalize_review_metadata(payload, recording)

        expected = datetime.fromisoformat("2026-08-04T09:12:30+00:00").astimezone()
        current = payload["review"]["current"]
        self.assertEqual(current["date"], expected.strftime("%Y-%m-%d"))
        self.assertEqual(current["time"], expected.strftime("%H:%M:%S"))


if __name__ == "__main__":
    unittest.main()
