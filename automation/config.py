from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from .timeutils import DEFAULT_TIMEZONE, get_timezone


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "plotloop-speaker-review" / "config.json"
DEFAULT_STATE_DIR = Path.home() / ".local" / "share" / "plotloop-speaker-review"


class ConfigError(RuntimeError):
    pass


def _expand(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def _command(value: str) -> str:
    expanded = os.path.expandvars(os.path.expanduser(value))
    resolved = shutil.which(expanded)
    return resolved or expanded


@dataclass(frozen=True)
class ScheduleConfig:
    heartbeat_minutes: int = 5
    weekday_active_minutes: int = 5
    weekday_quiet_minutes: int = 30
    weekend_active_minutes: int = 30
    weekend_quiet_minutes: int = 60
    active_start: str = "09:30"
    active_end: str = "22:00"
    reply_fast_minutes: int = 5
    reply_fast_hours: int = 6


@dataclass(frozen=True)
class LarkConfig:
    enabled: bool = False
    dry_run: bool = True
    chat_id: str = ""
    identity: str = "user"
    sender_open_id: str = ""
    command: str = "lark-cli"
    allow_private_content: bool = False


@dataclass(frozen=True)
class AnalysisConfig:
    enabled: bool = True
    command: str = "codex"
    timeout_seconds: int = 600
    recent_confirmed_limit: int = 30


@dataclass(frozen=True)
class AppConfig:
    enabled: bool
    mode: str
    source_root: Path
    work_target: Path
    private_target: Path
    state_dir: Path
    roster_path: Path
    yoooclaw_command: str
    hotwords_command: str
    project_root: Path
    timezone: str = DEFAULT_TIMEZONE
    stability_scans: int = 2
    missing_artifact_alert_minutes: int = 30
    work_keywords: List[str] = field(default_factory=list)
    private_keywords: List[str] = field(default_factory=list)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    lark: LarkConfig = field(default_factory=LarkConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)

    @classmethod
    def load(cls, path: Path | str = DEFAULT_CONFIG_PATH) -> "AppConfig":
        config_path = _expand(str(path))
        if not config_path.exists():
            raise ConfigError(
                f"Config not found: {config_path}. Copy automation/config.example.json first."
            )
        try:
            raw: Dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"Cannot read config {config_path}: {exc}") from exc

        required = ["source_root", "work_target", "private_target", "roster_path"]
        missing = [key for key in required if not raw.get(key)]
        if missing:
            raise ConfigError(f"Missing config fields: {', '.join(missing)}")

        schedule = ScheduleConfig(**raw.get("schedule", {}))
        lark_raw = raw.get("lark", {})
        lark = LarkConfig(
            **{**lark_raw, "command": _command(lark_raw.get("command", "lark-cli"))}
        )
        analysis_raw = raw.get("analysis", {})
        analysis = AnalysisConfig(
            **{
                **analysis_raw,
                "command": _command(analysis_raw.get("command", "codex")),
            }
        )

        project_root = _expand(
            raw.get("project_root", str(Path(__file__).resolve().parents[1]))
        )
        state_dir = _expand(raw.get("state_dir", str(DEFAULT_STATE_DIR)))
        mode = raw.get("mode", "shadow")
        if mode not in {"shadow", "active"}:
            raise ConfigError("mode must be 'shadow' or 'active'")

        return cls(
            enabled=bool(raw.get("enabled", False)),
            mode=mode,
            source_root=_expand(raw["source_root"]),
            work_target=_expand(raw["work_target"]),
            private_target=_expand(raw["private_target"]),
            state_dir=state_dir,
            roster_path=_expand(raw["roster_path"]),
            yoooclaw_command=_command(raw.get("yoooclaw_command", "yoooclaw")),
            hotwords_command=_command(raw.get("hotwords_command", "yc-hotwords")),
            project_root=project_root,
            timezone=str(raw.get("timezone", DEFAULT_TIMEZONE)),
            stability_scans=int(raw.get("stability_scans", 2)),
            missing_artifact_alert_minutes=int(
                raw.get("missing_artifact_alert_minutes", 30)
            ),
            work_keywords=list(raw.get("work_keywords", [])),
            private_keywords=list(raw.get("private_keywords", [])),
            schedule=schedule,
            lark=lark,
            analysis=analysis,
        )

    def ensure_directories(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "staging").mkdir(parents=True, exist_ok=True)
        (self.state_dir / "batches").mkdir(parents=True, exist_ok=True)
        (self.state_dir / "signals").mkdir(parents=True, exist_ok=True)

    def validate_runtime(self) -> List[str]:
        problems: List[str] = []
        for label, path in (
            ("source_root", self.source_root),
            ("work_target", self.work_target),
            ("private_target", self.private_target),
            ("roster_path", self.roster_path),
        ):
            if not path.exists():
                problems.append(f"{label} does not exist: {path}")
        for label, command in (
            ("yoooclaw_command", self.yoooclaw_command),
            ("hotwords_command", self.hotwords_command),
            ("analysis.command", self.analysis.command),
            ("lark.command", self.lark.command),
        ):
            if not Path(command).exists() and shutil.which(command) is None:
                problems.append(f"{label} is not executable: {command}")
        if self.stability_scans < 2:
            problems.append("stability_scans must be at least 2")
        try:
            get_timezone(self.timezone)
        except ValueError as exc:
            problems.append(str(exc))
        return problems
