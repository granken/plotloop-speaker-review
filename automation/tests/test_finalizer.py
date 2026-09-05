import json
import os
import tempfile
import unittest
from pathlib import Path

from automation.finalizer import (
    _display_created_at,
    apply_decisions,
    finalize_recording,
    update_work_index,
    write_completion_signal,
    write_review_artifact,
)
from automation.replies import ReplyDecision, ReviewItem


class FinalizerTests(unittest.TestCase):
    def test_plain_txt_speaker_headers_are_replaced(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            raw_transcript = root / "会议-全文.txt"
            raw_summary = root / "会议-总结.txt"
            content = "\ufeffSpeaker 2 00:00:01\n开始。\nSpeaker 2 00:00:07\n继续。\n"
            raw_transcript.write_text(content, encoding="utf-8")
            raw_summary.write_text("会议总结。\n", encoding="utf-8")
            review = {
                "current": {
                    "meeting": "会议",
                    "file_stem": "会议",
                    "note": "",
                    "mappings": [
                        {
                            "label": "Speaker 2",
                            "name": "老周",
                            "action": "replace",
                            "confidence": "high",
                            "note": "直接点名",
                        }
                    ],
                }
            }

            output = finalize_recording(
                "txt-1",
                {"title": "会议", "created_at": "2026-08-29T13:57:45+08:00"},
                review,
                raw_transcript,
                raw_summary,
                raw_transcript,
                raw_summary,
                root,
                existing_outputs={
                    "transcript": str(raw_transcript),
                    "summary": str(raw_summary),
                },
            )

            transcript = Path(output["transcript"]).read_text(encoding="utf-8")
            self.assertIn("\ufeff老周 00:00:01", transcript)
            self.assertIn("老周 00:00:07", transcript)
            self.assertNotIn("Speaker 2 00:00:01", transcript)
            self.assertNotIn("Speaker 2 00:00:07", transcript)
            self.assertEqual(output["replacements"], 2)

    def test_plain_txt_reused_label_is_replaced_by_time_segment(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            transcript_path = root / "大会-全文.txt"
            summary_path = root / "大会-总结.txt"
            transcript_path.write_text(
                "Speaker 1 00:00:16\n第一段。\nSpeaker 1 00:47:50\n第二段。\n",
                encoding="utf-8",
            )
            summary_path.write_text("总结。\n", encoding="utf-8")
            review = {
                "current": {
                    "meeting": "大会",
                    "file_stem": "大会",
                    "note": "",
                    "mappings": [
                        {
                            "label": "Speaker 1",
                            "name": "杨磊",
                            "action": "replace",
                            "confidence": "high",
                            "note": "标签复用",
                            "segments": [
                                {"start": "00:00:16", "end": "00:08:27", "name": "杨磊"},
                                {"start": "00:47:50", "end": "00:55:44", "name": "陈立勇"},
                            ],
                        }
                    ],
                }
            }

            output = finalize_recording(
                "txt-segments",
                {"title": "大会", "created_at": "2026-08-29T13:57:45+08:00"},
                review,
                transcript_path,
                summary_path,
                transcript_path,
                summary_path,
                root,
                existing_outputs={
                    "transcript": str(transcript_path),
                    "summary": str(summary_path),
                },
            )

            transcript = Path(output["transcript"]).read_text(encoding="utf-8")
            self.assertIn("杨磊 00:00:16", transcript)
            self.assertIn("陈立勇 00:47:50", transcript)
            self.assertIn("`00:00:16–00:08:27` → 杨磊", transcript)
            self.assertIn("`00:47:50–00:55:44` → 陈立勇", transcript)
            self.assertEqual(output["replacements"], 2)

    def test_volc_transcript_labels_are_replaced_in_turns_and_details(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            raw_transcript = root / "raw-transcript.md"
            raw_summary = root / "raw-summary.md"
            corrected_transcript = root / "corrected-transcript.md"
            corrected_summary = root / "corrected-summary.md"
            content = (
                "# 火山转写\n\n"
                "## 可读转写\n\n"
                "**说话人 1**：你好\n\n"
                "## 详细时间轴\n\n"
                "### 001 · 00:00:01 - 00:00:03 · 说话人 1\n\n"
                "你好\n"
            )
            raw_transcript.write_text(content, encoding="utf-8")
            corrected_transcript.write_text(content, encoding="utf-8")
            raw_summary.write_text("# 火山转写\n\n结论。\n", encoding="utf-8")
            corrected_summary.write_text("# 火山转写\n\n结论。\n", encoding="utf-8")
            review = {
                "current": {
                    "meeting": "火山转写",
                    "file_stem": "火山转写",
                    "note": "",
                    "mappings": [
                        {
                            "label": "说话人 1",
                            "name": "林夏",
                            "action": "replace",
                            "confidence": "high",
                            "note": "已确认",
                        }
                    ],
                }
            }

            output = finalize_recording(
                "volc-1",
                {"title": "火山转写", "created_at": "2026-08-05T18:44:18+08:00"},
                review,
                corrected_transcript,
                corrected_summary,
                raw_transcript,
                raw_summary,
                root / "target",
            )

            transcript = Path(output["transcript"]).read_text(encoding="utf-8")
            self.assertIn("**林夏**：你好", transcript)
            self.assertIn("### 001 · 00:00:01 - 00:00:03 · 林夏", transcript)
            self.assertEqual(output["replacements"], 2)

    def test_review_block_preserves_yaml_frontmatter_at_file_start(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            raw_transcript = root / "raw-transcript.md"
            raw_summary = root / "raw-summary.md"
            corrected_transcript = root / "corrected-transcript.md"
            corrected_summary = root / "corrected-summary.md"
            content = (
                "---\n"
                "type: 转写\n"
                "date: 2026-08-12\n"
                "---\n\n"
                "# 带元数据的会议\n\n"
                "**说话人 1**：你好\n"
            )
            for path in (raw_transcript, corrected_transcript, raw_summary, corrected_summary):
                path.write_text(content, encoding="utf-8")
            review = {
                "current": {
                    "meeting": "带元数据的会议",
                    "file_stem": "带元数据的会议",
                    "note": "已确认。",
                    "mappings": [
                        {
                            "label": "说话人 1",
                            "name": "林夏",
                            "action": "replace",
                            "confidence": "high",
                            "note": "直接点名。",
                        }
                    ],
                }
            }

            output = finalize_recording(
                "frontmatter-1",
                {"title": "带元数据的会议", "created_at": "2026-08-12T10:00:00+08:00"},
                review,
                corrected_transcript,
                corrected_summary,
                raw_transcript,
                raw_summary,
                root / "target",
            )

            transcript = Path(output["transcript"]).read_text(encoding="utf-8")
            self.assertTrue(transcript.startswith("---\ntype: 转写\n"))
            self.assertLess(transcript.index("# 带元数据的会议"), transcript.index("说话人识别（已确认）"))

    def test_confirmed_writeback_preserves_timestamp_and_updates_index(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            raw_transcript = root / "raw-transcript.md"
            raw_summary = root / "raw-summary.md"
            corrected_transcript = root / "corrected-transcript.md"
            corrected_summary = root / "corrected-summary.md"
            content = "# 演示会议\n\n## 转写\n\n- [00:01] Speaker 0: 你好\n"
            raw_transcript.write_text(content, encoding="utf-8")
            corrected_transcript.write_text(content, encoding="utf-8")
            raw_summary.write_text("# 演示会议\n\n结论。\n", encoding="utf-8")
            corrected_summary.write_text("# 演示会议\n\n结论。\n", encoding="utf-8")
            timestamp = 1_700_000_000
            os.utime(raw_transcript, (timestamp, timestamp))
            os.utime(raw_summary, (timestamp + 1, timestamp + 1))
            review = {
                "type": "speaker-review",
                "version": 2,
                "generated_at": "2026-08-04T10:00:00+08:00",
                "current": {
                    "meeting": "演示会议",
                    "date": "2026-08-04",
                    "time": "10:00:00",
                    "file_stem": "演示会议",
                    "note": "特别一句：明确下一步。",
                    "mappings": [
                        {
                            "label": "Speaker 0",
                            "name": "候选甲",
                            "action": "keep",
                            "confidence": "low",
                            "note": "待确认",
                        }
                    ],
                },
                "batch": [],
            }
            item = ReviewItem(1, "r1", "演示会议", "Speaker 0", "候选甲", "keep", "low", "")
            confirmed = apply_decisions(
                review,
                [item],
                {1: ReplyDecision(1, "replace", "确认姓名")},
            )
            self.assertEqual(confirmed["current"]["mappings"][0]["confidence"], "high")
            self.assertEqual(
                confirmed["current"]["mappings"][0]["note"],
                "待确认 用户确认修改为确认姓名。",
            )
            target = root / "target"
            output = finalize_recording(
                "r1",
                {"title": "演示会议", "created_at": "2026-08-04T10:00:00+08:00", "privacy": "work"},
                confirmed,
                corrected_transcript,
                corrected_summary,
                raw_transcript,
                raw_summary,
                target,
            )
            transcript = Path(output["transcript"])
            self.assertIn("确认姓名: 你好", transcript.read_text(encoding="utf-8"))
            self.assertIn("说话人识别（已确认）", transcript.read_text(encoding="utf-8"))
            self.assertEqual(int(transcript.stat().st_mtime), timestamp)
            index = target / "录音索引.md"
            index.write_text(
                "# 索引\n\n## 近期新增重点\n\n| 时间 | 主要会议题 | 核心参会人（可识别） | 资料 |\n|---|---|---|---|\n",
                encoding="utf-8",
            )
            self.assertTrue(update_work_index(index, output))
            self.assertFalse(update_work_index(index, output))
            updated = dict(output, speakers=["修正姓名"])
            self.assertTrue(update_work_index(index, updated))
            self.assertIn("修正姓名", index.read_text(encoding="utf-8"))
            artifact = write_review_artifact(target, "SR-TEST", [confirmed])
            signal = write_completion_signal(target, "SR-TEST", [output], artifact)
            payload = json.loads(signal.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ready_for_downstream")

    def test_accepting_existing_keep_preserves_evidence_and_confidence(self):
        review = {
            "current": {
                "mappings": [
                    {
                        "label": "说话人 2",
                        "name": "测试同学",
                        "action": "keep",
                        "confidence": "medium",
                        "note": "只有职责证据，尚无实名证据。",
                    }
                ]
            }
        }
        item = ReviewItem(
            1, "r1", "演示会议", "说话人 2", "测试同学", "keep", "medium", ""
        )
        confirmed = apply_decisions(
            review,
            [item],
            {1: ReplyDecision(1, "keep")},
        )
        mapping = confirmed["current"]["mappings"][0]
        self.assertEqual(mapping["confidence"], "medium")
        self.assertEqual(mapping["note"], "只有职责证据，尚无实名证据。")

    def test_index_rows_are_inserted_in_descending_recording_time(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            index = root / "录音索引.md"
            index.write_text(
                "# 索引\n\n## 近期新增重点\n\n"
                "| 时间 | 主要会议题 | 核心参会人（可识别） | 资料 |\n"
                "|---|---|---|---|\n",
                encoding="utf-8",
            )
            later = {
                "recording_id": "later",
                "created_at": "2026-08-04T18:01:09+08:00",
                "meeting": "较晚会议",
                "speakers": ["甲"],
                "transcript": str(root / "较晚会议_转写.md"),
                "summary": str(root / "较晚会议_总结.md"),
            }
            earlier = {
                "recording_id": "earlier",
                "created_at": "2026-08-04T17:12:30+08:00",
                "meeting": "较早会议",
                "speakers": ["乙"],
                "transcript": str(root / "较早会议_转写.md"),
                "summary": str(root / "较早会议_总结.md"),
            }

            self.assertTrue(update_work_index(index, later))
            self.assertTrue(update_work_index(index, earlier))

            text = index.read_text(encoding="utf-8")
            self.assertLess(text.index("较晚会议"), text.index("较早会议"))

    def test_utc_recording_time_is_rendered_in_the_configured_timezone(self):
        source = "2026-08-04T09:12:30.123456789Z"
        self.assertEqual(_display_created_at(source), "2026-08-04 17:12:30")


if __name__ == "__main__":
    unittest.main()
