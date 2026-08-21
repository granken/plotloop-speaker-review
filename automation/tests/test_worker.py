import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from automation.config import AnalysisConfig, AppConfig, LarkConfig
from automation.lark import LarkError
from automation.models import SourceRecording
from automation.state import empty_state
from automation.worker import RecordingWorker


class FakeYoooClaw:
    def __init__(self, recording):
        self.recording = recording

    def discover(self):
        return [self.recording]


class FakeHotwords:
    def process_files(self, source_paths, destination_dir):
        destination_dir.mkdir(parents=True, exist_ok=True)
        files = {}
        for source in source_paths:
            target = destination_dir / source.name
            shutil.copy2(source, target)
            files[source.name] = str(target)
        report = destination_dir / "hotword-report.json"
        report.write_text("[]\n", encoding="utf-8")
        return {"files": files, "report": [], "report_path": str(report)}


class FakeAnalyzer:
    def analyze(self, metadata, transcript_path, summary_path, roster_path, history):
        return {
            "type": "speaker-review-analysis",
            "version": 1,
            "privacy": {"classification": "work", "confidence": "high", "note": "工作会议"},
            "review": {
                "type": "speaker-review",
                "version": 2,
                "generated_at": "2026-08-04T10:00:00+08:00",
                "current": {
                    "meeting": "测试会议",
                    "date": "2026-08-04",
                    "time": "10:00:00",
                    "file_stem": "测试会议",
                    "note": "特别一句：测试闭环。",
                    "mappings": [
                        {
                            "label": "Speaker 0",
                            "name": "测试用户",
                            "action": "replace",
                            "confidence": "high",
                            "note": "直接点名",
                        }
                    ],
                },
                "batch": [],
            },
        }


class FakeFallbackLark:
    def __init__(self):
        self.cards = []
        self.texts = []

    def send_card(self, card, idempotency_key):
        self.cards.append((card, idempotency_key))
        raise LarkError("card unavailable")

    def send_text(self, text, idempotency_key):
        self.texts.append((text, idempotency_key))
        return {"message_id": "om_fallback"}


class WorkerTests(unittest.TestCase):
    def test_active_batch_falls_back_to_text_when_card_send_fails(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            roster = root / "roster.md"
            roster.write_text("测试用户\n", encoding="utf-8")
            for name in ("source", "work", "private"):
                (root / name).mkdir()
            config = AppConfig(
                enabled=True,
                mode="active",
                source_root=root / "source",
                work_target=root / "work",
                private_target=root / "private",
                state_dir=root / "state",
                roster_path=roster,
                yoooclaw_command="unused",
                hotwords_command="unused",
                project_root=root,
                analysis=AnalysisConfig(command="unused"),
                lark=LarkConfig(enabled=True, dry_run=False, chat_id="oc_test"),
            )
            analysis_path = root / "analysis.json"
            analysis_path.write_text(
                json.dumps(FakeAnalyzer().analyze({}, root, root, roster, []), ensure_ascii=False),
                encoding="utf-8",
            )
            job = {
                "recording_id": "r1",
                "title": "测试会议",
                "created_at": "2026-08-06T10:00:00+08:00",
                "analysis_path": str(analysis_path),
                "privacy": "work",
                "status": "analyzed",
            }
            state = empty_state()
            state["jobs"]["r1"] = job
            worker = RecordingWorker(config)
            worker.lark = FakeFallbackLark()

            batch_id = worker._create_batch(
                state,
                [job],
                datetime.fromisoformat("2026-08-06T10:00:00+08:00"),
                local_only=False,
            )
            batch = state["batches"][batch_id]
            self.assertEqual(batch["dispatch_mode"], "text_fallback")
            self.assertEqual(batch["dispatch_message_ids"], ["om_fallback"])
            self.assertEqual(len(worker.lark.cards), 1)
            self.assertEqual(len(worker.lark.texts), 1)

    def test_shadow_batch_and_manual_reply_end_to_end(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            source = root / "source"
            source.mkdir()
            audio = source / "recording.ogg"
            transcript = source / "transcript.md"
            summary = source / "summary.md"
            data = source / "data.json"
            audio.write_bytes(b"audio")
            transcript.write_text("# 测试会议\n\n- [00:01] Speaker 0: 开始\n", encoding="utf-8")
            summary.write_text("# 测试会议\n\n总结\n", encoding="utf-8")
            data.write_text(
                json.dumps({"normalized": {"segments": [{"speakerId": 0, "startMs": 1, "text": "开始"}]}}),
                encoding="utf-8",
            )
            roster = root / "roster.md"
            roster.write_text("测试用户\n", encoding="utf-8")
            work = root / "work"
            private = root / "private"
            work.mkdir()
            private.mkdir()
            (work / "录音索引.md").write_text(
                "# 索引\n\n## 近期新增重点\n\n| 时间 | 主要会议题 | 核心参会人（可识别） | 资料 |\n|---|---|---|---|\n",
                encoding="utf-8",
            )
            config = AppConfig(
                enabled=True,
                mode="shadow",
                source_root=source,
                work_target=work,
                private_target=private,
                state_dir=root / "state",
                roster_path=roster,
                yoooclaw_command="unused",
                hotwords_command="unused",
                project_root=root,
                analysis=AnalysisConfig(command="unused"),
                lark=LarkConfig(enabled=False),
            )
            recording = SourceRecording(
                recording_id="r1",
                title="测试会议",
                created_at="2026-08-04T10:00:00+08:00",
                updated_at="2026-08-04T10:01:00+08:00",
                audio_path=audio,
                transcript_path=transcript,
                summary_path=summary,
                transcript_data_path=data,
                status="transcribed",
            )
            worker = RecordingWorker(config)
            worker.yoooclaw = FakeYoooClaw(recording)
            worker.hotwords = FakeHotwords()
            worker.analyzer = FakeAnalyzer()
            first = worker.run_once(force=True, now=datetime.fromisoformat("2026-08-04T10:00:00+08:00"))
            self.assertEqual(first["analyzed"], 0)
            second = worker.run_once(force=True, now=datetime.fromisoformat("2026-08-04T10:05:00+08:00"))
            self.assertEqual(second["analyzed"], 1)
            self.assertEqual(len(second["batches_created"]), 1)
            batch_id = second["batches_created"][0]
            result = worker.apply_manual_reply(batch_id, "全对")
            self.assertTrue(result["ok"])
            output = Path(result["outputs"][0]["transcript"])
            self.assertIn("测试用户: 开始", output.read_text(encoding="utf-8"))
            status = worker.status()
            self.assertEqual(status["jobs"]["finalized"], 1)
            self.assertEqual(status["batches"]["completed"], 1)


if __name__ == "__main__":
    unittest.main()
