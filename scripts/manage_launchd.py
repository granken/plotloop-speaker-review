#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from automation.config import AppConfig, DEFAULT_CONFIG_PATH


LABEL = "com.plotloop.speaker-review"


def render(config_path: Path) -> Path:
    config = AppConfig.load(config_path)
    template = (
        config.project_root
        / "automation"
        / "launchd"
        / "com.plotloop.speaker-review.plist.template"
    ).read_text(encoding="utf-8")
    command_dirs = {
        str(Path(config.lark.command).parent),
        str(Path(config.analysis.command).parent),
        str(Path(config.yoooclaw_command).parent),
        str(Path(config.hotwords_command).parent),
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    }
    runtime_path = ":".join(sorted(command_dirs))
    content = (
        template.replace("__PYTHON__", "/usr/bin/python3")
        .replace("__CONFIG__", str(config_path.resolve()))
        .replace("__PROJECT_ROOT__", str(config.project_root))
        .replace("__STATE_DIR__", str(config.state_dir))
        .replace("__HOME__", str(Path.home()))
        .replace("__PATH__", runtime_path)
    )
    destination = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Install or remove the Plotloop launchd job")
    parser.add_argument("action", choices=["render", "install", "uninstall", "status"])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    args = parser.parse_args()
    config_path = Path(args.config).expanduser().resolve()
    destination = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    domain = f"gui/{subprocess.check_output(['id', '-u'], text=True).strip()}"
    if args.action == "render":
        print(render(config_path))
    elif args.action == "install":
        path = render(config_path)
        subprocess.run(["launchctl", "bootout", domain, str(path)], check=False)
        subprocess.run(["launchctl", "bootstrap", domain, str(path)], check=True)
        subprocess.run(["launchctl", "enable", f"{domain}/{LABEL}"], check=True)
        print(f"installed: {path}")
    elif args.action == "uninstall":
        subprocess.run(["launchctl", "bootout", domain, str(destination)], check=False)
        print(f"unloaded: {destination}")
    else:
        subprocess.run(["launchctl", "print", f"{domain}/{LABEL}"], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
