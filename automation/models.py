from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class SourceRecording:
    recording_id: str
    title: str
    created_at: str
    updated_at: str
    audio_path: Path
    transcript_path: Optional[Path]
    summary_path: Optional[Path]
    transcript_data_path: Optional[Path]
    status: str

    @property
    def has_required_artifacts(self) -> bool:
        return bool(
            self.audio_path.exists()
            and self.transcript_path
            and self.transcript_path.exists()
            and self.summary_path
            and self.summary_path.exists()
        )

    def source_paths(self) -> Dict[str, Path]:
        paths: Dict[str, Path] = {"audio": self.audio_path}
        if self.transcript_path:
            paths["transcript"] = self.transcript_path
        if self.summary_path:
            paths["summary"] = self.summary_path
        if self.transcript_data_path:
            paths["transcript_data"] = self.transcript_data_path
        return paths


def fingerprint(path: Path) -> Dict[str, Any]:
    stat = path.stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
