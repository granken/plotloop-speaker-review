from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterable, List


def normalize_names(values: Iterable[object]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        name = str(value or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


class LearnedRosterStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> List[str]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        values = payload.get("names", []) if isinstance(payload, dict) else payload
        return normalize_names(values if isinstance(values, list) else [])

    def add(self, values: Iterable[object]) -> dict:
        current = self.load()
        merged = normalize_names([*current, *values])
        added = [name for name in merged if name not in set(current)]
        if added:
            self._write(merged)
        return {"names": merged, "added": added}

    def _write(self, names: List[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "names": names}, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
