#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_FILENAMES = {
    ".env",
    "credentials.json",
    "local-review-config.js",
    "local-review-data.js",
}
PRIVATE_PATH_PARTS = (".backup-",)
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".txt",
    ".xml",
    ".yml",
    ".yaml",
}


def candidate_paths() -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    return [PROJECT_ROOT / value.decode() for value in result.stdout.split(b"\0") if value]


def content_issues(path: Path, text: str) -> list[str]:
    issues = []
    mac_home = re.compile("/" + "Users" + r"/[A-Za-z0-9._-]+/")
    internal_recording_path = "360" + "/" + "录音"
    if mac_home.search(text):
        issues.append("contains an absolute macOS home path")
    if internal_recording_path in text:
        issues.append("contains an internal recording directory")
    for field, placeholder in (
        ("chat_id", "YOUR_CHAT_ID"),
        ("sender_open_id", "YOUR_OPEN_ID"),
    ):
        for match in re.finditer(rf'"{field}"\s*:\s*"([^"]*)"', text):
            if match.group(1) not in {"", placeholder}:
                issues.append(f"contains a non-placeholder {field}")
    return issues


def main() -> int:
    problems = []
    for path in candidate_paths():
        relative = path.relative_to(PROJECT_ROOT)
        if path.name in PRIVATE_FILENAMES or any(
            part in str(relative) for part in PRIVATE_PATH_PARTS
        ):
            problems.append(f"{relative}: private or backup filename")
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        problems.extend(f"{relative}: {issue}" for issue in content_issues(path, text))

    if problems:
        print("Public repository check failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("Public repository check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
