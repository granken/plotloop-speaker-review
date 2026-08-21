from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


PROTECTED_RE = re.compile(r"(```[\s\S]*?```|`[^`\n]+`|https?://[^\s)>]+)", re.MULTILINE)


@dataclass(frozen=True)
class Correction:
    source: str
    target: str
    count: int


class HotwordCorrector:
    def __init__(self, command: str):
        self.command = command

    def load_corrections(self) -> Dict[str, str]:
        result = subprocess.run(
            [self.command, "corrections"],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "cannot load hotword corrections")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("hotword command returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("hotword corrections must be a JSON object")
        return {str(key): str(value) for key, value in payload.items() if key and value}

    @staticmethod
    def apply(text: str, corrections: Dict[str, str]) -> Tuple[str, List[Correction]]:
        ordered = sorted(corrections.items(), key=lambda item: len(item[0]), reverse=True)
        counts: Dict[Tuple[str, str], int] = {}
        pieces: List[str] = []
        cursor = 0

        def replace_plain(value: str) -> str:
            for source, target in ordered:
                occurrences = value.count(source)
                if occurrences:
                    value = value.replace(source, target)
                    key = (source, target)
                    counts[key] = counts.get(key, 0) + occurrences
            return value

        for match in PROTECTED_RE.finditer(text):
            pieces.append(replace_plain(text[cursor : match.start()]))
            pieces.append(match.group(0))
            cursor = match.end()
        pieces.append(replace_plain(text[cursor:]))

        report = [
            Correction(source=source, target=target, count=count)
            for (source, target), count in sorted(counts.items())
        ]
        return "".join(pieces), report

    def process_files(
        self, source_paths: Iterable[Path], destination_dir: Path
    ) -> Dict[str, object]:
        corrections = self.load_corrections()
        destination_dir.mkdir(parents=True, exist_ok=True)
        files: Dict[str, str] = {}
        combined: Dict[Tuple[str, str], int] = {}
        for source in source_paths:
            text = source.read_text(encoding="utf-8")
            corrected, report = self.apply(text, corrections)
            target = destination_dir / source.name
            target.write_text(corrected, encoding="utf-8")
            files[source.name] = str(target)
            for item in report:
                key = (item.source, item.target)
                combined[key] = combined.get(key, 0) + item.count
        report_payload = [
            {"source": source, "target": target, "count": count}
            for (source, target), count in sorted(combined.items())
        ]
        report_path = destination_dir / "hotword-report.json"
        report_path.write_text(
            json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {"files": files, "report": report_payload, "report_path": str(report_path)}
