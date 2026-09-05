from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .config import AppConfig
from .finalizer import (
    finalize_recording,
    update_work_index,
    write_completion_signal,
    write_review_artifact,
)
from .roster import LearnedRosterStore
from .state import StateStore
from .timeutils import get_timezone


ALLOWED_ACTIONS = {"replace", "keep", "ignore"}
UNRESOLVED_NAME_RE = re.compile(r"待核|待确认|无法确认|未知说话人")


class ConfirmedPayloadError(RuntimeError):
    pass


def validate_confirmed_payload(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ConfirmedPayloadError("payload must be an object")
    if payload.get("type") != "speaker-review" or payload.get("version") != 2:
        raise ConfirmedPayloadError("payload must be speaker-review v2")
    batch = payload.get("batch")
    if not isinstance(batch, list) or not batch:
        raise ConfirmedPayloadError("payload batch must be non-empty")
    for meeting_index, meeting in enumerate(batch, start=1):
        if not isinstance(meeting, dict) or not str(meeting.get("meeting", "")).strip():
            raise ConfirmedPayloadError(f"meeting {meeting_index} has no title")
        mappings = meeting.get("mappings")
        if not isinstance(mappings, list) or not mappings:
            raise ConfirmedPayloadError(f"meeting {meeting_index} has no mappings")
        labels = set()
        for mapping_index, mapping in enumerate(mappings, start=1):
            if not isinstance(mapping, dict):
                raise ConfirmedPayloadError(
                    f"meeting {meeting_index} mapping {mapping_index} is invalid"
                )
            label = str(mapping.get("label", "")).strip()
            action = str(mapping.get("action", "")).strip()
            name = str(mapping.get("name", "")).strip()
            if not label or label in labels:
                raise ConfirmedPayloadError(
                    f"meeting {meeting_index} has a missing or duplicate label"
                )
            labels.add(label)
            if action not in ALLOWED_ACTIONS:
                raise ConfirmedPayloadError(
                    f"meeting {meeting_index} mapping {label} has invalid action"
                )
            if action == "replace" and (not name or UNRESOLVED_NAME_RE.search(name)):
                raise ConfirmedPayloadError(
                    f"meeting {meeting_index} mapping {label} has no confirmed name"
                )
            segments = mapping.get("segments") or []
            if segments and action != "replace":
                raise ConfirmedPayloadError(
                    f"meeting {meeting_index} mapping {label} has segments without replace"
                )
            for segment in segments:
                if not isinstance(segment, dict) or not all(
                    str(segment.get(key, "")).strip()
                    for key in ("start", "end", "name")
                ):
                    raise ConfirmedPayloadError(
                        f"meeting {meeting_index} mapping {label} has invalid segments"
                    )
    return batch


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _label_patterns(label: str) -> Iterable[re.Pattern[str]]:
    escaped = re.escape(label)
    return (
        re.compile(rf"(?m)^\s*-\s+\[[0-9:]+\]\s+{escaped}\s*:"),
        re.compile(rf"(?m)^\s*\*\*{escaped}\*\*[：:]"),
        re.compile(rf"(?m)^\s*###\s+\d+\s+·\s+[^\n]+?\s+·\s+{escaped}\s*$"),
        re.compile(rf"(?m)^\ufeff?{escaped}\s+\d{{2}}:\d{{2}}:\d{{2}}\s*$"),
    )


def _name_patterns(name: str) -> Iterable[re.Pattern[str]]:
    escaped = re.escape(name)
    return (
        re.compile(rf"(?m)^\s*-\s+\[[0-9:]+\]\s+{escaped}\s*:"),
        re.compile(rf"(?m)^\s*\*\*{escaped}\*\*[：:]"),
        re.compile(rf"(?m)^\s*###\s+\d+\s+·\s+[^\n]+?\s+·\s+{escaped}\s*$"),
        re.compile(rf"(?m)^\ufeff?{escaped}\s+\d{{2}}:\d{{2}}:\d{{2}}\s*$"),
    )


class ConfirmedPayloadProcessor:
    def __init__(self, config: AppConfig):
        self.config = config
        self.target = config.work_target
        self.ledger_path = self.target / "录音同步台账.json"
        self.roster = LearnedRosterStore(config.state_dir / "roster.json")
        self.state_store = StateStore(config.state_dir)

    def process_pending(self) -> Dict[str, Any]:
        confirmed_dir = self.target / "confirmed"
        files = sorted(confirmed_dir.glob("*.json")) if confirmed_dir.exists() else []
        results = []
        errors = []
        for path in files:
            try:
                results.append(self.process_file(path))
            except (ConfirmedPayloadError, OSError, json.JSONDecodeError) as exc:
                errors.append({"file": str(path), "error": str(exc)})
        return {"ok": not errors, "processed": results, "errors": errors}

    def process_file(self, path: Path) -> Dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        meetings = validate_confirmed_payload(payload)
        ledger = self._load_ledger()
        outputs: List[Dict[str, Any]] = []
        reviews: List[Dict[str, Any]] = []
        history: List[Dict[str, Any]] = []
        learned_names: List[str] = []
        confirmation_date = datetime.now(get_timezone(self.config.timezone)).date().isoformat()

        for meeting in meetings:
            entry = self._find_ledger_entry(ledger, meeting)
            transcript, summary = self._source_paths(meeting, entry)
            review = {
                "type": "speaker-review",
                "version": 2,
                "generated_at": payload.get("generated_at", ""),
                "confirmed_at": datetime.now(get_timezone(self.config.timezone)).isoformat(),
                "current": meeting,
                "batch": [meeting],
            }
            recording_id, created_at = self._recording_identity(meeting, entry)
            output = finalize_recording(
                recording_id=recording_id,
                metadata={
                    "title": meeting["meeting"],
                    "created_at": created_at,
                    "privacy": "work",
                },
                review=review,
                corrected_transcript=transcript,
                corrected_summary=summary,
                raw_transcript=transcript,
                raw_summary=summary,
                target_dir=self.target,
                existing_outputs={"transcript": str(transcript), "summary": str(summary)},
                timezone=self.config.timezone,
            )
            output["new_replacements"] = output["replacements"]
            output["replacements"] = self._audit_and_count(output, meeting)
            update_work_index(
                self.target / "录音索引.md", output, self.config.timezone
            )
            if entry is not None:
                entry["speakers_confirmed"] = confirmation_date
            for mapping in meeting["mappings"]:
                history.append(
                    {
                        "recording_id": recording_id,
                        "meeting": meeting["meeting"],
                        "label": mapping["label"],
                        "name": mapping.get("name", ""),
                        "action": mapping["action"],
                        "confirmed_at": review["confirmed_at"],
                    }
                )
                if mapping["action"] == "replace":
                    learned_names.append(str(mapping.get("name", "")).strip())
                    learned_names.extend(
                        str(segment.get("name", "")).strip()
                        for segment in mapping.get("segments", [])
                    )
            outputs.append(output)
            reviews.append(review)

        if ledger is not None:
            _atomic_json(self.ledger_path, ledger)
        roster_result = self.roster.add(learned_names)
        self._append_history(history)
        batch_id = self._batch_id(payload, path)
        artifact = write_review_artifact(self.target, batch_id, reviews)
        signal = write_completion_signal(self.target, batch_id, outputs, artifact)
        processed = self._archive(path)
        return {
            "batch_id": batch_id,
            "outputs": outputs,
            "review_artifact": str(artifact),
            "completion_signal": str(signal),
            "processed_file": str(processed),
            "roster_added": roster_result["added"],
        }

    def _load_ledger(self) -> Dict[str, Any] | None:
        if not self.ledger_path.exists():
            return None
        payload = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("recordings"), list):
            raise ConfirmedPayloadError("recording ledger is invalid")
        return payload

    @staticmethod
    def _find_ledger_entry(
        ledger: Dict[str, Any] | None, meeting: Dict[str, Any]
    ) -> Dict[str, Any] | None:
        if ledger is None:
            return None
        title = str(meeting.get("meeting", "")).strip()
        stem = str(meeting.get("file_stem") or title).strip()
        matches = [
            entry
            for entry in ledger["recordings"]
            if entry.get("name") == title
            or any(str(value).startswith(stem + "_") for value in entry.get("files", []))
        ]
        if len(matches) > 1:
            raise ConfirmedPayloadError(f"multiple ledger entries match {title}")
        return matches[0] if matches else None

    def _source_paths(
        self, meeting: Dict[str, Any], entry: Dict[str, Any] | None
    ) -> Tuple[Path, Path]:
        filenames = list(entry.get("files", [])) if entry else []
        transcript_name = next(
            (name for name in filenames if "转写" in name or "全文" in name), ""
        )
        summary_name = next((name for name in filenames if "总结" in name), "")
        stem = str(meeting.get("file_stem") or meeting["meeting"]).strip()

        def first_existing(names: Iterable[str]) -> Path:
            candidates = [self.target / name for name in names if name]
            return next((path for path in candidates if path.exists()), candidates[0])

        transcript = first_existing(
            [
                transcript_name,
                f"{stem}_转写.md",
                f"{stem}-全文.txt",
                f"{stem}_全文.txt",
                f"{stem}-转写.txt",
            ]
        )
        summary = first_existing(
            [
                summary_name,
                f"{stem}_总结.md",
                f"{stem}-总结.txt",
                f"{stem}_总结.txt",
            ]
        )
        missing = [str(value) for value in (transcript, summary) if not value.exists()]
        if missing:
            raise ConfirmedPayloadError("missing writeback files: " + ", ".join(missing))
        return transcript, summary

    def _recording_identity(
        self, meeting: Dict[str, Any], entry: Dict[str, Any] | None
    ) -> Tuple[str, str]:
        if entry:
            return str(entry.get("uuid") or ""), str(entry.get("created_at") or "")
        date = str(meeting.get("date") or "").strip()
        time = str(meeting.get("time") or "00:00:00").strip()
        created = datetime.fromisoformat(f"{date}T{time}").replace(
            tzinfo=get_timezone(self.config.timezone)
        )
        digest = hashlib.sha1(
            f"{meeting['meeting']}|{created.isoformat()}".encode("utf-8")
        ).hexdigest()[:12].upper()
        return f"LOCAL-{digest}", created.isoformat()

    @staticmethod
    def _audit_and_count(output: Dict[str, Any], meeting: Dict[str, Any]) -> int:
        transcript_path = Path(output["transcript"])
        summary_path = Path(output["summary"])
        transcript = transcript_path.read_text(encoding="utf-8")
        summary = summary_path.read_text(encoding="utf-8")
        if transcript.count("<!-- plotloop-speaker-review:start -->") != 1:
            raise ConfirmedPayloadError(f"invalid review block: {transcript_path}")
        if summary.count("<!-- plotloop-speaker-review:start -->") != 1:
            raise ConfirmedPayloadError(f"invalid review block: {summary_path}")
        if re.search(r"(?m)^>\s*说话人（.*待人工确认", transcript):
            raise ConfirmedPayloadError(f"legacy pending marker remains: {transcript_path}")
        total = 0
        for mapping in meeting["mappings"]:
            if mapping["action"] != "replace":
                continue
            label = str(mapping["label"])
            if any(pattern.search(transcript) for pattern in _label_patterns(label)):
                raise ConfirmedPayloadError(
                    f"speaker label remains after writeback: {meeting['meeting']} / {label}"
                )
            name = str(mapping.get("name", ""))
            names = [name, *[
                str(segment.get("name", ""))
                for segment in mapping.get("segments", [])
            ]]
            total += sum(
                len(pattern.findall(transcript))
                for value in dict.fromkeys(filter(None, names))
                for pattern in _name_patterns(value)
            )
        return total

    def _append_history(self, values: List[Dict[str, Any]]) -> None:
        if not values:
            return
        with self.state_store.locked(blocking=True) as state:
            state["confirmed_history"].extend(values)
            state["confirmed_history"] = state["confirmed_history"][-500:]

    @staticmethod
    def _batch_id(payload: Dict[str, Any], path: Path) -> str:
        explicit = str(payload.get("batch_id") or "").strip()
        if explicit:
            return explicit
        stem = path.stem.removeprefix("speaker-review-")
        return "SR-" + stem.upper()

    def _archive(self, path: Path) -> Path:
        confirmed_dir = (self.target / "confirmed").resolve()
        if path.resolve().parent != confirmed_dir:
            return path
        processed = confirmed_dir / "processed" / path.name
        processed.parent.mkdir(parents=True, exist_ok=True)
        os.replace(path, processed)
        return processed
