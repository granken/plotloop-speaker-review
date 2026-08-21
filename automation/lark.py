from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List

from .config import LarkConfig


class LarkError(RuntimeError):
    pass


class LarkClient:
    def __init__(self, config: LarkConfig):
        self.config = config

    def _run_json(self, args: List[str], timeout: int = 120) -> Dict[str, Any]:
        result = subprocess.run(
            [self.config.command, *args, "--format", "json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise LarkError(result.stderr.strip() or result.stdout.strip())
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise LarkError("lark-cli returned invalid JSON") from exc
        if payload.get("ok") is False:
            raise LarkError(str(payload.get("error") or payload))
        return payload

    @staticmethod
    def _data(payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload.get("data")
        return data if isinstance(data, dict) else payload

    def send_text(self, text: str, idempotency_key: str) -> Dict[str, Any]:
        if not self.config.enabled:
            raise LarkError("Lark sending is disabled")
        args = [
            "im",
            "+messages-send",
            "--as",
            self.config.identity,
            "--chat-id",
            self.config.chat_id,
            "--text",
            text,
            "--idempotency-key",
            idempotency_key,
        ]
        if self.config.dry_run:
            args.append("--dry-run")
        return self._data(self._run_json(args))

    def send_card(self, card: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
        if not self.config.enabled:
            raise LarkError("Lark sending is disabled")
        args = [
            "im",
            "+messages-send",
            "--as",
            self.config.identity,
            "--chat-id",
            self.config.chat_id,
            "--msg-type",
            "interactive",
            "--content",
            json.dumps(card, ensure_ascii=False, separators=(",", ":")),
            "--idempotency-key",
            idempotency_key,
        ]
        if self.config.dry_run:
            args.append("--dry-run")
        return self._data(self._run_json(args))

    def list_messages(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        if not self.config.enabled:
            return []
        args = [
            "im",
            "+chat-messages-list",
            "--as",
            self.config.identity,
            "--chat-id",
            self.config.chat_id,
            "--start",
            start.strftime("%Y-%m-%d %H:%M:%S"),
            "--end",
            end.strftime("%Y-%m-%d %H:%M:%S"),
            "--order",
            "asc",
            "--page-size",
            "50",
            "--no-reactions",
        ]
        data = self._data(self._run_json(args))
        messages = data.get("messages", [])
        flattened: List[Dict[str, Any]] = []
        for message in messages if isinstance(messages, list) else []:
            if isinstance(message, dict):
                flattened.append(message)
                replies = message.get("thread_replies", [])
                if isinstance(replies, list):
                    flattened.extend(reply for reply in replies if isinstance(reply, dict))
        return flattened

    def recent_messages(self, now: datetime, hours: int = 24) -> List[Dict[str, Any]]:
        return self.list_messages(now - timedelta(hours=hours), now + timedelta(minutes=1))


def message_text(message: Dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, dict):
        return str(content.get("text") or content.get("content") or "")
    if not isinstance(content, str):
        return ""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return content
    if isinstance(parsed, dict):
        return str(parsed.get("text") or parsed.get("content") or "")
    return content


def sender_open_id(message: Dict[str, Any]) -> str:
    sender = message.get("sender", {})
    if not isinstance(sender, dict):
        return ""
    sender_id = sender.get("id")
    if isinstance(sender_id, dict):
        return str(sender_id.get("open_id") or sender_id.get("id") or "")
    return str(sender.get("open_id") or sender_id or "")
