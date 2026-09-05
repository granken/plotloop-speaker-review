import json
import os
import tempfile
import unittest
from pathlib import Path

from automation.config import AppConfig
from automation.confirmed import (
    ConfirmedPayloadError,
    ConfirmedPayloadProcessor,
    validate_confirmed_payload,
)


class ConfirmedPayloadTests(unittest.TestCase):
    def _config(self, root: Path) -> AppConfig:
        source = root / "source"
        work = root / "work"
        private = root / "private"
        state = root / "state"
        for path in (source, work, private, state):
            path.mkdir(parents=True, exist_ok=True)
        roster = root / "roster.md"
        roster.write_text("# 花名册\n", encoding="utf-8")
        return AppConfig(
            enabled=False,
            mode="shadow",
            source_root=source,
            work_target=work,
            private_target=private,
            state_dir=state,
            roster_path=roster,
            yoooclaw_command="yoooclaw",
            hotwords_command="yc-hotwords",
            project_root=root,
        )

    @staticmethod
    def _payload():
        meeting = {
            "meeting": "官网讨论",
            "date": "2026-08-26",
            "time": "20:40:33",
            "file_stem": "官网讨论",
            "note": "已人工确认。",
            "mappings": [
                {
                    "label": "Speaker 0",
                    "name": "林青",
                    "action": "replace",
                    "confidence": "high",
                    "note": "用户确认。",
                },
                {
                    "label": "Speaker 1",
                    "name": "顾川",
                    "action": "replace",
                    "confidence": "high",
                    "note": "用户确认。",
                },
            ],
        }
        return {
            "type": "speaker-review",
            "version": 2,
            "generated_at": "2026-08-27T00:00:00+08:00",
            "current": meeting,
            "batch": [meeting],
        }

    def test_processor_finalizes_without_model_and_preserves_source_time(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            config = self._config(root)
            work = config.work_target
            transcript = work / "官网讨论_转写.md"
            summary = work / "官网讨论_总结.md"
            transcript.write_text(
                "# 官网讨论\n\n"
                "> 说话人（2026-08-26 工作台确认）：待人工确认\n\n"
                "## 转写\n\n"
                "- [00:01] Speaker 0: 开始。\n"
                "- [00:02] Speaker 1: 收到。\n",
                encoding="utf-8",
            )
            summary.write_text("# 官网讨论\n\n结论。\n", encoding="utf-8")
            source_time = 1_700_000_000
            os.utime(transcript, (source_time, source_time))
            os.utime(summary, (source_time + 1, source_time + 1))
            (work / "录音索引.md").write_text(
                "# 索引\n\n## 近期新增重点\n\n"
                "| 时间 | 主要会议题 | 核心参会人（可识别） | 资料 |\n"
                "|---|---|---|---|\n",
                encoding="utf-8",
            )
            (work / "录音同步台账.json").write_text(
                json.dumps(
                    {
                        "recordings": [
                            {
                                "uuid": "recording-1",
                                "name": "官网讨论",
                                "created_at": "2026-08-26T12:40:33.582999305Z",
                                "speakers_confirmed": None,
                                "files": ["官网讨论_转写.md", "官网讨论_总结.md"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            confirmed = work / "confirmed" / "speaker-review-test.json"
            confirmed.parent.mkdir(parents=True)
            confirmed.write_text(
                json.dumps(self._payload(), ensure_ascii=False), encoding="utf-8"
            )

            result = ConfirmedPayloadProcessor(config).process_file(confirmed)

            updated = transcript.read_text(encoding="utf-8")
            self.assertIn("林青: 开始", updated)
            self.assertIn("顾川: 收到", updated)
            self.assertNotIn("待人工确认", updated)
            self.assertEqual(int(transcript.stat().st_mtime), source_time)
            self.assertEqual(int(summary.stat().st_mtime), source_time + 1)
            self.assertEqual(result["outputs"][0]["replacements"], 2)
            self.assertTrue(Path(result["processed_file"]).exists())
            self.assertFalse(confirmed.exists())
            index = (work / "录音索引.md").read_text(encoding="utf-8")
            self.assertIn("2026-08-26 20:40:33", index)
            ledger = json.loads((work / "录音同步台账.json").read_text(encoding="utf-8"))
            self.assertTrue(ledger["recordings"][0]["speakers_confirmed"])
            roster = json.loads((config.state_dir / "roster.json").read_text(encoding="utf-8"))
            self.assertEqual(roster["names"], ["林青", "顾川"])

    def test_unresolved_replace_name_is_rejected(self):
        payload = self._payload()
        payload["batch"][0]["mappings"][0]["name"] = "待确认"
        with self.assertRaises(ConfirmedPayloadError):
            validate_confirmed_payload(payload)

    def test_source_paths_support_plain_txt_pairs(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            config = self._config(root)
            transcript = config.work_target / "大会-全文.txt"
            summary = config.work_target / "大会-总结.txt"
            transcript.write_text("Speaker 1 00:00:01\n你好。\n", encoding="utf-8")
            summary.write_text("总结。\n", encoding="utf-8")

            resolved = ConfirmedPayloadProcessor(config)._source_paths(
                {"meeting": "大会", "file_stem": "大会"}, None
            )

            self.assertEqual(resolved, (transcript, summary))


if __name__ == "__main__":
    unittest.main()
