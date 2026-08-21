from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .analyzer import AnalysisError, CodexAnalyzer
from .cards import build_review_cards
from .config import AppConfig
from .finalizer import (
    apply_decisions,
    finalize_recording,
    update_work_index,
    write_completion_signal,
    write_review_artifact,
)
from .hotwords import HotwordCorrector
from .lark import LarkClient, LarkError, message_text, sender_open_id
from .models import SourceRecording
from .replies import (
    ParsedReply,
    ReplyDecision,
    ReviewItem,
    build_review_message,
    looks_like_reply,
    parse_reply,
)
from .schedule import decide
from .state import StateStore
from .yoooclaw import YoooClawClient, source_fingerprints, stage_recording


TERMINAL_JOB_STATUSES = {"baseline_ignored", "finalized"}


def _now_iso(now: datetime) -> str:
    return now.astimezone().isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _parse_time(value: str, fallback: datetime) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return fallback
    if parsed.tzinfo is None and fallback.tzinfo is not None:
        parsed = parsed.replace(tzinfo=fallback.tzinfo)
    return parsed


def _review_item_from_dict(payload: Dict[str, Any]) -> ReviewItem:
    return ReviewItem(
        number=int(payload["number"]),
        recording_id=str(payload["recording_id"]),
        meeting=str(payload["meeting"]),
        label=str(payload["label"]),
        proposed_name=str(payload["proposed_name"]),
        proposed_action=str(payload["proposed_action"]),
        proposed_confidence=str(payload["proposed_confidence"]),
        note=str(payload.get("note", "")),
    )


class RecordingWorker:
    def __init__(self, config: AppConfig):
        self.config = config
        self.state_store = StateStore(config.state_dir)
        self.yoooclaw = YoooClawClient(config.yoooclaw_command, config.source_root)
        self.hotwords = HotwordCorrector(config.hotwords_command)
        self.analyzer = CodexAnalyzer(config.analysis, config.project_root)
        self.lark = LarkClient(config.lark)

    def preflight(self) -> Dict[str, Any]:
        problems = self.config.validate_runtime()
        recordings = []
        if not problems:
            try:
                recordings = self.yoooclaw.discover()
            except Exception as exc:  # surfaced as a preflight problem
                problems.append(f"YoooClaw discovery failed: {exc}")
        return {
            "ok": not problems,
            "mode": self.config.mode,
            "enabled": self.config.enabled,
            "recording_count": len(recordings),
            "source_root": str(self.config.source_root),
            "work_target": str(self.config.work_target),
            "private_target": str(self.config.private_target),
            "state_dir": str(self.config.state_dir),
            "lark_enabled": self.config.lark.enabled,
            "lark_dry_run": self.config.lark.dry_run,
            "problems": problems,
        }

    def baseline(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now().astimezone()
        recordings = self.yoooclaw.discover()
        with self.state_store.locked() as state:
            for recording in recordings:
                state["jobs"][recording.recording_id] = {
                    "recording_id": recording.recording_id,
                    "title": recording.title,
                    "created_at": recording.created_at,
                    "status": "baseline_ignored",
                    "baselined_at": _now_iso(now),
                }
            state["runtime"]["baseline_at"] = _now_iso(now)
        return {"baselined": len(recordings), "at": _now_iso(now)}

    def run_once(self, force: bool = False, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now().astimezone()
        if not self.config.enabled and not force:
            return {"ok": False, "skipped": "automation is disabled"}
        self.config.ensure_directories()
        with self.state_store.locked() as state:
            schedule = decide(
                state["runtime"], state["batches"].values(), now, self.config.schedule
            )
            result: Dict[str, Any] = {
                "ok": True,
                "at": _now_iso(now),
                "schedule": {
                    "full_scan_due": schedule.full_scan_due,
                    "reply_poll_due": schedule.reply_poll_due,
                    "full_scan_interval_minutes": schedule.full_scan_interval_minutes,
                    "reply_poll_interval_minutes": schedule.reply_poll_interval_minutes,
                },
                "discovered": 0,
                "analyzed": 0,
                "batches_created": [],
                "finalized": [],
                "alerts": [],
                "errors": [],
            }
            if force or schedule.full_scan_due:
                scan_result = self._scan(state, now)
                for key in ("discovered", "analyzed"):
                    result[key] = scan_result[key]
                result["alerts"].extend(scan_result["alerts"])
                result["errors"].extend(scan_result["errors"])
                result["batches_created"].extend(self._create_batches(state, now))
                if result["alerts"]:
                    self._dispatch_alert_summary(
                        result["alerts"], state, now, result["errors"]
                    )
                state["runtime"]["last_full_scan_at"] = _now_iso(now)
            if force or schedule.reply_poll_due:
                reply_result = self._poll_replies(state, now)
                result["finalized"].extend(reply_result["finalized"])
                result["errors"].extend(reply_result["errors"])
                state["runtime"]["last_reply_poll_at"] = _now_iso(now)
            state["runtime"]["last_run_at"] = _now_iso(now)
            return result

    def _real_lark_enabled(self) -> bool:
        return bool(
            self.config.mode == "active"
            and self.config.lark.enabled
            and not self.config.lark.dry_run
        )

    def _dispatch_alert_summary(
        self,
        alerts: List[str],
        state: Dict[str, Any],
        now: datetime,
        errors: List[str],
    ) -> None:
        if not self._real_lark_enabled():
            return
        text = (
            f"【录音处理告警】有 {len(alerts)} 条录音落库超过 "
            f"{self.config.missing_artifact_alert_minutes} 分钟，但转写或总结仍不完整。"
            "请检查 YoooClaw 转写额度和任务状态。为避免泄露，告警不包含录音标题。"
        )
        try:
            self.lark.send_text(text, f"plotloop-alert-{now:%Y%m%d%H%M}")
            state["runtime"]["last_alert_dispatched_at"] = _now_iso(now)
        except LarkError as exc:
            errors.append(f"Lark alert failed: {exc}")

    def _scan(self, state: Dict[str, Any], now: datetime) -> Dict[str, Any]:
        result = {"discovered": 0, "analyzed": 0, "alerts": [], "errors": []}
        try:
            recordings = self.yoooclaw.discover()
        except Exception as exc:
            result["errors"].append(f"discovery failed: {exc}")
            return result
        result["discovered"] = len(recordings)
        for recording in recordings:
            job = state["jobs"].setdefault(
                recording.recording_id,
                {
                    "recording_id": recording.recording_id,
                    "first_seen_at": _now_iso(now),
                    "status": "discovered",
                    "stable_scans": 0,
                },
            )
            if job.get("status") in TERMINAL_JOB_STATUSES:
                continue
            job.update(
                {
                    "title": recording.title,
                    "created_at": recording.created_at,
                    "updated_at": recording.updated_at,
                    "source_status": recording.status,
                    "last_seen_at": _now_iso(now),
                }
            )
            if not recording.has_required_artifacts:
                job["status"] = "waiting_transcription"
                first_seen = _parse_time(job["first_seen_at"], now)
                age = now - first_seen
                if (
                    age >= timedelta(minutes=self.config.missing_artifact_alert_minutes)
                    and not job.get("missing_artifact_alerted_at")
                ):
                    alert = (
                        f"录音 {recording.recording_id}（{recording.title}）已落库 "
                        f"{int(age.total_seconds() // 60)} 分钟，但转写或总结仍不完整。"
                    )
                    result["alerts"].append(alert)
                    job["missing_artifact_alerted_at"] = _now_iso(now)
                continue
            try:
                fingerprints = source_fingerprints(recording)
                if fingerprints == job.get("source_fingerprints"):
                    job["stable_scans"] = int(job.get("stable_scans", 0)) + 1
                else:
                    job["source_fingerprints"] = fingerprints
                    job["stable_scans"] = 1
                if job["stable_scans"] < self.config.stability_scans:
                    job["status"] = "stabilizing"
                    continue
                if job.get("analysis_path"):
                    continue
                self._stage_and_analyze(state, job, recording, now)
                result["analyzed"] += 1
            except (OSError, RuntimeError, AnalysisError) as exc:
                job["status"] = "error"
                job["last_error"] = str(exc)
                job["last_error_at"] = _now_iso(now)
                result["errors"].append(f"{recording.recording_id}: {exc}")
        return result

    def _stage_and_analyze(
        self,
        state: Dict[str, Any],
        job: Dict[str, Any],
        recording: SourceRecording,
        now: datetime,
    ) -> None:
        staged = stage_recording(recording, self.config.state_dir / "staging")
        job["staged_files"] = staged
        job["status"] = "staged"
        corrected_dir = self.config.state_dir / "staging" / recording.recording_id / "corrected"
        hotword_result = self.hotwords.process_files(
            [Path(staged["transcript"]), Path(staged["summary"])], corrected_dir
        )
        job["corrected_files"] = hotword_result["files"]
        job["hotword_report_path"] = hotword_result["report_path"]
        transcript_name = Path(staged["transcript"]).name
        summary_name = Path(staged["summary"]).name
        labels = self._speaker_labels(staged.get("transcript_data"))
        metadata = {
            "recording_id": recording.recording_id,
            "title": recording.title,
            "created_at": recording.created_at,
            "updated_at": recording.updated_at,
            "speaker_labels": labels,
        }
        analysis = self.analyzer.analyze(
            metadata,
            Path(hotword_result["files"][transcript_name]),
            Path(hotword_result["files"][summary_name]),
            self.config.roster_path,
            state["confirmed_history"],
        )
        analysis_path = self.config.state_dir / "staging" / recording.recording_id / "analysis.json"
        _write_json(analysis_path, analysis)
        job["analysis_path"] = str(analysis_path)
        job["privacy"] = analysis["privacy"]["classification"]
        job["privacy_confidence"] = analysis["privacy"]["confidence"]
        job["analyzed_at"] = _now_iso(now)
        job["status"] = (
            "privacy_review_required"
            if job["privacy"] == "uncertain"
            else "analyzed"
        )

    @staticmethod
    def _speaker_labels(path_value: Optional[str]) -> List[str]:
        if not path_value:
            return []
        try:
            payload = json.loads(Path(path_value).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        segments = payload.get("normalized", {}).get("segments", [])
        labels = []
        for segment in segments if isinstance(segments, list) else []:
            speaker_id = segment.get("speakerId") if isinstance(segment, dict) else None
            if speaker_id is None:
                continue
            label = f"speakerId {speaker_id}"
            if label not in labels:
                labels.append(label)
        return labels

    def _next_batch_id(self, state: Dict[str, Any], now: datetime, suffix: str = "") -> str:
        base = f"SR-{now:%Y%m%d-%H%M%S}{suffix}"
        candidate = base
        index = 2
        while candidate in state["batches"]:
            candidate = f"{base}-{index}"
            index += 1
        return candidate

    def _create_batches(self, state: Dict[str, Any], now: datetime) -> List[str]:
        candidates = [
            job
            for job in state["jobs"].values()
            if job.get("status") in {"analyzed", "privacy_review_required"}
            and not job.get("batch_id")
        ]
        if not candidates:
            return []
        dispatchable: List[Dict[str, Any]] = []
        local_only: List[Dict[str, Any]] = []
        for job in candidates:
            privacy = job.get("privacy")
            if privacy == "uncertain":
                continue
            if privacy == "work" or (
                privacy == "private" and self.config.lark.allow_private_content
            ):
                dispatchable.append(job)
            else:
                local_only.append(job)
        created: List[str] = []
        if dispatchable:
            created.append(self._create_batch(state, dispatchable, now, local_only=False))
        if local_only:
            created.append(self._create_batch(state, local_only, now, local_only=True))
        return created

    def _create_batch(
        self,
        state: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        now: datetime,
        local_only: bool,
    ) -> str:
        batch_id = self._next_batch_id(state, now, "-LOCAL" if local_only else "")
        reviews = []
        review_payloads = []
        for job in jobs:
            analysis = json.loads(Path(job["analysis_path"]).read_text(encoding="utf-8"))
            review = analysis["review"]
            reviews.append({"recording_id": job["recording_id"], "review": review})
            review_payloads.append(review["current"])
        message, items = build_review_message(batch_id, reviews)
        cards = build_review_cards(batch_id, reviews, items)
        batch_dir = self.config.state_dir / "batches" / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)
        message_path = batch_dir / "message.txt"
        message_path.write_text(message + "\n", encoding="utf-8")
        card_paths = []
        for index, card in enumerate(cards, start=1):
            card_path = batch_dir / f"card-{index}.json"
            _write_json(card_path, card)
            card_paths.append(str(card_path))
        speaker_review = {
            "type": "speaker-review",
            "version": 2,
            "generated_at": _now_iso(now),
            "current": review_payloads[-1],
            "batch": review_payloads,
        }
        review_path = batch_dir / "speaker-review.json"
        _write_json(review_path, speaker_review)
        batch = {
            "batch_id": batch_id,
            "created_at": _now_iso(now),
            "recording_ids": [job["recording_id"] for job in jobs],
            "items": [asdict(item) for item in items],
            "decisions": {},
            "message_path": str(message_path),
            "card_paths": card_paths,
            "review_path": str(review_path),
            "local_only": local_only,
        }
        can_send = not local_only and self._real_lark_enabled()
        if can_send:
            responses = []
            try:
                for index, card in enumerate(cards, start=1):
                    responses.append(
                        self.lark.send_card(card, f"plotloop-{batch_id}-card-{index}")
                    )
                batch["dispatch_mode"] = "card"
            except LarkError as exc:
                batch["card_send_error"] = str(exc)
                responses.append(
                    self.lark.send_text(message, f"plotloop-{batch_id}-text-fallback")
                )
                batch["dispatch_mode"] = "text_fallback"
            message_ids = [
                str(
                    response.get("message_id")
                    or response.get("message", {}).get("message_id")
                    or ""
                )
                for response in responses
            ]
            batch["dispatch_responses"] = responses
            batch["dispatch_response"] = responses[-1]
            batch["dispatch_message_ids"] = list(filter(None, message_ids))
            batch["dispatch_message_id"] = batch["dispatch_message_ids"][-1]
            batch["dispatched_at"] = _now_iso(now)
            batch["status"] = "awaiting_review"
        else:
            batch["status"] = "local_review" if local_only else "shadow_ready"
        state["batches"][batch_id] = batch
        for job in jobs:
            job["batch_id"] = batch_id
            job["status"] = batch["status"]
        return batch_id

    def _poll_replies(self, state: Dict[str, Any], now: datetime) -> Dict[str, Any]:
        result = {"finalized": [], "errors": []}
        waiting = [
            batch for batch in state["batches"].values() if batch.get("status") == "awaiting_review"
        ]
        if not waiting or not self.config.lark.enabled:
            return result
        try:
            messages = self.lark.recent_messages(now)
        except LarkError as exc:
            result["errors"].append(f"Lark polling failed: {exc}")
            return result
        processed = set(state["processed_message_ids"])
        dispatched_message_ids = {
            message_id
            for batch in waiting
            for message_id in (
                list(batch.get("dispatch_message_ids", []))
                + [batch.get("dispatch_message_id", "")]
            )
            if message_id
        }
        for message in messages:
            message_id = str(message.get("message_id", ""))
            if not message_id or message_id in processed:
                continue
            if message_id in dispatched_message_ids:
                processed.add(message_id)
                continue
            if self.config.lark.sender_open_id and sender_open_id(message) != self.config.lark.sender_open_id:
                continue
            text = message_text(message).strip()
            matched = [batch for batch in waiting if batch["batch_id"] in text]
            if not matched and len(waiting) == 1 and looks_like_reply(text):
                matched = waiting
            if len(matched) != 1:
                continue
            batch = matched[0]
            cleaned = text.replace(batch["batch_id"], "").strip(" \n：:")
            parsed = self._parse_batch_reply(batch, cleaned)
            processed.add(message_id)
            if parsed.error:
                batch.setdefault("reply_errors", []).append(
                    {"message_id": message_id, "text": text, "error": parsed.error}
                )
                continue
            self._merge_decisions(batch, parsed)
            if self._batch_decisions_complete(batch):
                try:
                    outputs = self._finalize_batch(state, batch, now)
                    result["finalized"].extend(outputs)
                except Exception as exc:
                    batch["status"] = "finalize_error"
                    batch["last_error"] = str(exc)
                    result["errors"].append(f"{batch['batch_id']}: {exc}")
                    continue
                if self._real_lark_enabled():
                    try:
                        self.lark.send_text(
                            f"【录音处理完成 {batch['batch_id']}】已确认并归档 {len(outputs)} 场会议。",
                            f"plotloop-complete-{batch['batch_id']}",
                        )
                    except LarkError as exc:
                        result["errors"].append(
                            f"{batch['batch_id']} completion notice failed: {exc}"
                        )
        state["processed_message_ids"] = list(processed)[-1000:]
        return result

    @staticmethod
    def _parse_batch_reply(batch: Dict[str, Any], text: str) -> ParsedReply:
        items = [_review_item_from_dict(item) for item in batch["items"]]
        return parse_reply(text, items)

    @staticmethod
    def _merge_decisions(batch: Dict[str, Any], parsed: ParsedReply) -> None:
        for number, decision in parsed.decisions.items():
            batch["decisions"][str(number)] = {
                "number": number,
                "action": decision.action,
                "name": decision.name,
            }

    @staticmethod
    def _batch_decisions_complete(batch: Dict[str, Any]) -> bool:
        expected = {str(item["number"]) for item in batch["items"]}
        actual = set(batch["decisions"])
        return expected == actual and all(
            decision.get("action") != "pending" for decision in batch["decisions"].values()
        )

    def apply_manual_reply(
        self, batch_id: str, text: str, now: Optional[datetime] = None
    ) -> Dict[str, Any]:
        now = now or datetime.now().astimezone()
        with self.state_store.locked() as state:
            batch = state["batches"].get(batch_id)
            if not batch:
                raise RuntimeError(f"batch not found: {batch_id}")
            if batch.get("status") == "completed":
                return {"batch_id": batch_id, "already_completed": True}
            parsed = self._parse_batch_reply(batch, text)
            if parsed.error:
                return {"batch_id": batch_id, "ok": False, "error": parsed.error}
            self._merge_decisions(batch, parsed)
            if not self._batch_decisions_complete(batch):
                return {
                    "batch_id": batch_id,
                    "ok": True,
                    "waiting_for": sorted(
                        {item["number"] for item in batch["items"]}
                        - {int(value) for value in batch["decisions"]}
                    ),
                }
            outputs = self._finalize_batch(state, batch, now)
            return {"batch_id": batch_id, "ok": True, "outputs": outputs}

    def set_privacy(self, recording_id: str, classification: str) -> Dict[str, Any]:
        if classification not in {"work", "private"}:
            raise RuntimeError("classification must be work or private")
        with self.state_store.locked() as state:
            job = state["jobs"].get(recording_id)
            if not job:
                raise RuntimeError(f"recording not found: {recording_id}")
            if job.get("status") == "finalized":
                raise RuntimeError("cannot change privacy after finalization")
            job["privacy"] = classification
            job["privacy_confidence"] = "high"
            job["privacy_confirmed_at"] = datetime.now().astimezone().isoformat()
            if not job.get("batch_id"):
                job["status"] = "analyzed"
            return {
                "recording_id": recording_id,
                "privacy": classification,
                "status": job["status"],
            }

    def _finalize_batch(
        self, state: Dict[str, Any], batch: Dict[str, Any], now: datetime
    ) -> List[Dict[str, Any]]:
        all_items = [_review_item_from_dict(item) for item in batch["items"]]
        decisions = {
            int(number): ReplyDecision(
                number=int(number), action=value["action"], name=value.get("name")
            )
            for number, value in batch["decisions"].items()
        }
        outputs: List[Dict[str, Any]] = []
        confirmed_by_target: Dict[str, List[Dict[str, Any]]] = {}
        for recording_id in batch["recording_ids"]:
            job = state["jobs"][recording_id]
            privacy = job.get("privacy")
            if privacy not in {"work", "private"}:
                raise RuntimeError(
                    f"{recording_id} privacy is {privacy}; choose work/private before finalizing"
                )
            analysis = json.loads(Path(job["analysis_path"]).read_text(encoding="utf-8"))
            job_items = [item for item in all_items if item.recording_id == recording_id]
            confirmed_review = apply_decisions(analysis["review"], job_items, decisions)
            confirmed_path = Path(job["analysis_path"]).with_name("confirmed-review.json")
            _write_json(confirmed_path, confirmed_review)
            staged = job["staged_files"]
            corrected = job["corrected_files"]
            transcript_name = Path(staged["transcript"]).name
            summary_name = Path(staged["summary"]).name
            target = self.config.work_target if privacy == "work" else self.config.private_target
            metadata = {
                "title": job["title"],
                "created_at": job.get("created_at", ""),
                "privacy": privacy,
            }
            output = finalize_recording(
                recording_id=recording_id,
                metadata=metadata,
                review=confirmed_review,
                corrected_transcript=Path(corrected[transcript_name]),
                corrected_summary=Path(corrected[summary_name]),
                raw_transcript=Path(staged["transcript"]),
                raw_summary=Path(staged["summary"]),
                target_dir=target,
                existing_outputs=job.get("outputs", {}),
            )
            outputs.append(output)
            job["outputs"] = {
                "transcript": output["transcript"], "summary": output["summary"]
            }
            job["confirmed_review_path"] = str(confirmed_path)
            job["status"] = "finalized"
            job["finalized_at"] = _now_iso(now)
            confirmed_by_target.setdefault(str(target), []).append(confirmed_review)
            if privacy == "work":
                update_work_index(self.config.work_target / "录音索引.md", output)
            for mapping in confirmed_review["current"]["mappings"]:
                state["confirmed_history"].append(
                    {
                        "recording_id": recording_id,
                        "meeting": confirmed_review["current"]["meeting"],
                        "label": mapping["label"],
                        "name": mapping["name"],
                        "action": mapping["action"],
                        "confirmed_at": _now_iso(now),
                    }
                )
        state["confirmed_history"] = state["confirmed_history"][-500:]
        for target_value, reviews in confirmed_by_target.items():
            target = Path(target_value)
            target_outputs = [output for output in outputs if str(Path(output["transcript"]).parent) == target_value]
            artifact = write_review_artifact(target, batch["batch_id"], reviews)
            signal = write_completion_signal(target, batch["batch_id"], target_outputs, artifact)
            batch.setdefault("review_artifacts", []).append(str(artifact))
            batch.setdefault("completion_signals", []).append(str(signal))
        batch["status"] = "completed"
        batch["completed_at"] = _now_iso(now)
        batch["outputs"] = outputs
        return outputs

    def status(self) -> Dict[str, Any]:
        state = self.state_store.load()
        job_counts: Dict[str, int] = {}
        for job in state["jobs"].values():
            status = str(job.get("status", "unknown"))
            job_counts[status] = job_counts.get(status, 0) + 1
        batch_counts: Dict[str, int] = {}
        for batch in state["batches"].values():
            status = str(batch.get("status", "unknown"))
            batch_counts[status] = batch_counts.get(status, 0) + 1
        return {
            "runtime": state["runtime"],
            "jobs": job_counts,
            "batches": batch_counts,
            "latest_batches": list(state["batches"].keys())[-10:],
        }
