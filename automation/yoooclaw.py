from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .models import SourceRecording, fingerprint


class YoooClawError(RuntimeError):
    pass


class YoooClawClient:
    def __init__(self, command: str, source_root: Path):
        self.command = command
        self.source_root = source_root.resolve()

    def _json(self, args: Iterable[str]) -> Dict[str, Any]:
        command = [self.command, *args, "--format", "json"]
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise YoooClawError(result.stderr.strip() or result.stdout.strip())
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise YoooClawError("YoooClaw returned invalid JSON") from exc
        if payload.get("ok") is False:
            raise YoooClawError(str(payload.get("error") or payload))
        return payload

    def list_recordings(self) -> List[Dict[str, Any]]:
        payload = self._json(["recording", "list"])
        return list(payload.get("recordings", []))

    def recording_status(self, recording_id: str) -> Dict[str, Any]:
        payload = self._json(["recording", "status", recording_id])
        data = payload.get("recording") or payload.get("data") or payload
        if not isinstance(data, dict):
            raise YoooClawError(f"unexpected status response for {recording_id}")
        return data

    def _source_path(self, value: Optional[str]) -> Optional[Path]:
        if not value:
            return None
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = self.source_root / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.source_root)
        except ValueError as exc:
            raise YoooClawError(f"source path escaped source root: {resolved}") from exc
        return resolved

    def discover(self) -> List[SourceRecording]:
        listed = {item["id"]: item for item in self.list_recordings() if item.get("id")}
        audio_dir = self.source_root / "audio"
        audio_ids = {path.stem for path in audio_dir.glob("*.ogg")}
        recording_ids = sorted(set(listed) | audio_ids)
        recordings: List[SourceRecording] = []

        for recording_id in recording_ids:
            try:
                status = self.recording_status(recording_id)
            except YoooClawError:
                status = listed.get(recording_id, {})
            audio_path = self._source_path(status.get("audioFile"))
            if audio_path is None:
                audio_path = (audio_dir / f"{recording_id}.ogg").resolve()
            if not audio_path.exists():
                continue
            recordings.append(
                SourceRecording(
                    recording_id=recording_id,
                    title=str(status.get("title") or status.get("name") or recording_id),
                    created_at=str(
                        status.get("created_at")
                        or status.get("ingestedAt")
                        or listed.get(recording_id, {}).get("created_at")
                        or ""
                    ),
                    updated_at=str(
                        status.get("updatedAt")
                        or status.get("updated_at")
                        or listed.get(recording_id, {}).get("updated_at")
                        or ""
                    ),
                    audio_path=audio_path,
                    transcript_path=self._source_path(status.get("transcriptFile")),
                    summary_path=self._source_path(status.get("summaryFile")),
                    transcript_data_path=self._source_path(
                        status.get("transcriptDataFile")
                    ),
                    status=str(status.get("status") or "unknown"),
                )
            )
        return recordings


def source_fingerprints(recording: SourceRecording) -> Dict[str, Dict[str, Any]]:
    return {
        name: fingerprint(path)
        for name, path in recording.source_paths().items()
        if path.exists()
    }


def stage_recording(recording: SourceRecording, staging_root: Path) -> Dict[str, str]:
    destination = staging_root / recording.recording_id / "raw"
    destination.mkdir(parents=True, exist_ok=True)
    staged: Dict[str, str] = {}
    for name, source in recording.source_paths().items():
        if not source.exists():
            continue
        suffix = source.suffix or ".dat"
        target = destination / f"{name}{suffix}"
        shutil.copy2(source, target)
        staged[name] = str(target)
    return staged
