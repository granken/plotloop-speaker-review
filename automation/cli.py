from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from .confirmed import ConfirmedPayloadProcessor
from .config import AppConfig, ConfigError, DEFAULT_CONFIG_PATH
from .worker import RecordingWorker


def _print(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plotloop-recordings", description="Local-first recording review automation"
    )
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG_PATH), help="Path to local JSON config"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight", help="Check paths and external CLIs")
    baseline = subparsers.add_parser("baseline", help="Mark current recordings as already handled")
    baseline.add_argument("--yes", action="store_true", help="Confirm baseline creation")
    run = subparsers.add_parser("run", help="Run one scheduled heartbeat")
    run.add_argument("--force", action="store_true", help="Ignore schedule and enabled flag")
    subparsers.add_parser("status", help="Show local state summary")
    reply = subparsers.add_parser("apply-reply", help="Apply a review reply manually")
    reply.add_argument("--batch", required=True)
    reply.add_argument("--text", required=True)
    classify = subparsers.add_parser(
        "classify", help="Resolve an uncertain work/private destination"
    )
    classify.add_argument("--recording", required=True)
    classify.add_argument("--as", dest="classification", choices=["work", "private"], required=True)
    finalize_json = subparsers.add_parser(
        "finalize-json", help="Finalize one confirmed speaker-review JSON without a model"
    )
    finalize_json.add_argument("--file", required=True)
    subparsers.add_parser(
        "process-confirmed", help="Finalize every queued JSON in work_target/confirmed"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = AppConfig.load(Path(args.config))
        worker = RecordingWorker(config)
        if args.command == "preflight":
            payload = worker.preflight()
        elif args.command == "baseline":
            if not args.yes:
                payload = {
                    "ok": False,
                    "error": "baseline needs --yes because it suppresses all current recordings",
                }
            else:
                payload = worker.baseline()
        elif args.command == "run":
            payload = worker.run_once(force=args.force)
        elif args.command == "status":
            payload = worker.status()
        elif args.command == "apply-reply":
            payload = worker.apply_manual_reply(args.batch, args.text)
        elif args.command == "classify":
            payload = worker.set_privacy(args.recording, args.classification)
        elif args.command == "finalize-json":
            payload = ConfirmedPayloadProcessor(config).process_file(Path(args.file))
        elif args.command == "process-confirmed":
            payload = ConfirmedPayloadProcessor(config).process_pending()
        else:
            parser.error(f"unknown command: {args.command}")
            return 2
        _print(payload)
        return 0 if payload.get("ok", True) else 1
    except (ConfigError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        _print({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
