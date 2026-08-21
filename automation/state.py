from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterator


STATE_VERSION = 1


def empty_state() -> Dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "runtime": {},
        "jobs": {},
        "batches": {},
        "processed_message_ids": [],
        "confirmed_history": [],
    }


class StateStore:
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.path = state_dir / "state.json"
        self.lock_path = state_dir / "worker.lock"

    @contextmanager
    def locked(self, blocking: bool = False) -> Iterator[Dict[str, Any]]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock_file:
            flags = fcntl.LOCK_EX
            if not blocking:
                flags |= fcntl.LOCK_NB
            try:
                fcntl.flock(lock_file.fileno(), flags)
            except BlockingIOError as exc:
                raise RuntimeError("another worker is already running") from exc
            state = self.load()
            original = deepcopy(state)
            try:
                yield state
                if state != original:
                    self.save(state)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return empty_state()
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"state file is unreadable: {self.path}: {exc}") from exc
        if state.get("version") != STATE_VERSION:
            raise RuntimeError(
                f"unsupported state version: {state.get('version')}, expected {STATE_VERSION}"
            )
        defaults = empty_state()
        for key, value in defaults.items():
            state.setdefault(key, value)
        return state

    def save(self, state: Dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix="state.", suffix=".tmp", dir=str(self.state_dir)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
