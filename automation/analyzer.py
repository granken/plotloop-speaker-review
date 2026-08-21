from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .config import AnalysisConfig
from .timeutils import DEFAULT_TIMEZONE, parse_display_datetime


class AnalysisError(RuntimeError):
    pass


class CodexAnalyzer:
    def __init__(
        self,
        config: AnalysisConfig,
        project_root: Path,
        timezone: str = DEFAULT_TIMEZONE,
    ):
        self.config = config
        self.project_root = project_root
        self.timezone = timezone
        self.schema_path = Path(__file__).parent / "schemas" / "analysis-result-v1.schema.json"

    def _prompt(
        self,
        recording: Dict[str, Any],
        transcript: str,
        summary: str,
        roster: str,
        confirmed_history: Iterable[Dict[str, Any]],
    ) -> str:
        history = json.dumps(list(confirmed_history), ensure_ascii=False, indent=2)
        metadata = json.dumps(recording, ensure_ascii=False, indent=2)
        return f"""你是会议文字稿的说话人校对分析器。只输出符合所给 JSON Schema 的 JSON。

目标：
1. 识别每个原始说话人标签最可能对应的人名或角色。
2. 判断材料应进入 work、private，还是证据不足的 uncertain；uncertain 必须暂停，不能猜目录。
3. 在 note 末尾给出“特别一句：...”作为这场会议最值得专题总结的一句话。

判断规则：
- 优先级：本场直接点名/自报姓名 > 会议职责与历史连续性 > 语言风格。不得仅凭语气把人写死。
- high 只用于直接证据，或多条独立证据形成的稳定职责链；否则使用 medium/low。
- label 必须原样使用逐字稿里的标签，例如 Speaker 0、speakerId 1、讲话人 2。
- 能确认真实姓名时 action=replace；只能确认角色或证据不足时 action=keep；环境音、导航、多人串并标签用 ignore。
- name 不得凭空创造；可使用清晰角色名，如“客户方/产品同学”。
- current 只放本场会议，batch 必须是空数组。
- date/time 优先取元数据；没有就留空字符串。
- 工作、人事、客户、招聘等内容属于 work；纯私人生活属于 private；两者混合或不确定属于 uncertain。
- 不复述手机号、地址、账号等不必要的个人信息。

录音元数据：
{metadata}

脱敏花名册与别名参考：
{roster}

最近已确认映射（仅作连续性参考，不能替代本场证据）：
{history}

YoooClaw 总结：
{summary}

逐字稿：
{transcript}
"""

    def analyze(
        self,
        recording: Dict[str, Any],
        transcript_path: Path,
        summary_path: Path,
        roster_path: Path,
        confirmed_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not self.config.enabled:
            raise AnalysisError("analysis is disabled")
        transcript = transcript_path.read_text(encoding="utf-8")
        summary = summary_path.read_text(encoding="utf-8")
        roster = roster_path.read_text(encoding="utf-8")
        prompt = self._prompt(
            recording,
            transcript,
            summary,
            roster,
            confirmed_history[-self.config.recent_confirmed_limit :],
        )

        with tempfile.TemporaryDirectory(prefix="plotloop-analysis-") as temp_dir:
            output_path = Path(temp_dir) / "result.json"
            command = [
                self.config.command,
                "exec",
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--output-schema",
                str(self.schema_path),
                "--output-last-message",
                str(output_path),
                "-C",
                str(self.project_root),
                "-",
            ]
            result = subprocess.run(
                command,
                input=prompt,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
            )
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip()
                raise AnalysisError(f"Codex analysis failed: {detail[-2000:]}")
            if not output_path.exists():
                raise AnalysisError("Codex did not produce an analysis result")
            try:
                payload = json.loads(output_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise AnalysisError("Codex analysis result is not valid JSON") from exc

        self._validate_result(payload)
        self._normalize_review_metadata(payload, recording, self.timezone)
        return payload

    @staticmethod
    def _normalize_review_metadata(
        payload: Dict[str, Any],
        recording: Dict[str, Any],
        timezone: str = DEFAULT_TIMEZONE,
    ) -> None:
        current = payload["review"]["current"]
        title = str(recording.get("title", "")).strip()
        if title:
            current["meeting"] = title
            current["file_stem"] = title

        created_at = str(recording.get("created_at", "")).strip()
        if not created_at:
            return
        try:
            created = parse_display_datetime(created_at, timezone)
        except ValueError:
            return
        current["date"] = created.strftime("%Y-%m-%d")
        current["time"] = created.strftime("%H:%M:%S")

    @staticmethod
    def _validate_result(payload: Dict[str, Any]) -> None:
        if payload.get("type") != "speaker-review-analysis" or payload.get("version") != 1:
            raise AnalysisError("unexpected analysis envelope")
        privacy = payload.get("privacy", {})
        if privacy.get("classification") not in {"work", "private", "uncertain"}:
            raise AnalysisError("invalid privacy classification")
        review = payload.get("review", {})
        current = review.get("current", {})
        mappings = current.get("mappings", [])
        if review.get("type") != "speaker-review" or review.get("version") != 2:
            raise AnalysisError("invalid speaker-review payload")
        if not mappings:
            raise AnalysisError("speaker-review has no mappings")
        labels = [item.get("label") for item in mappings]
        if len(labels) != len(set(labels)):
            raise AnalysisError("speaker-review contains duplicate labels")
        if not review.get("generated_at"):
            review["generated_at"] = datetime.now().astimezone().isoformat()
