from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .replies import ReplyDecision, ReviewItem
from .timeutils import DEFAULT_TIMEZONE, parse_display_datetime


INVALID_FILENAME_RE = re.compile(r"[\x00/:]")


def safe_stem(value: str) -> str:
    cleaned = INVALID_FILENAME_RE.sub("_", value).strip().strip(".")
    return cleaned or "未命名会议"


def _atomic_write(path: Path, content: str, source_timestamp: Path | None = None) -> None:
    source_times: tuple[int, int] | None = None
    if source_timestamp and source_timestamp.exists():
        stat = source_timestamp.stat()
        source_times = (stat.st_atime_ns, stat.st_mtime_ns)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            if content and not content.endswith("\n"):
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        if source_times:
            os.utime(path, ns=source_times)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _review_block(meeting: Dict[str, Any]) -> str:
    lines = [
        "<!-- plotloop-speaker-review:start -->",
        "> [!info] 说话人识别（已确认）",
    ]
    for mapping in meeting.get("mappings", []):
        segments = mapping.get("segments") or []
        if segments:
            for segment in segments:
                lines.append(
                    f"> - `{mapping.get('label', '')}` "
                    f"`{segment.get('start', '')}–{segment.get('end', '')}` → "
                    f"{segment.get('name', '')}（按时段已写回，{mapping.get('confidence', '')}）"
                )
            continue
        suffix = {
            "replace": "已写回",
            "keep": "保留原标签",
            "ignore": "不参与说话人写回",
        }.get(mapping.get("action"), str(mapping.get("action", "")))
        lines.append(
            f"> - `{mapping.get('label', '')}` → {mapping.get('name', '')}"
            f"（{suffix}，{mapping.get('confidence', '')}）"
        )
    if meeting.get("note"):
        lines.append(f"> - {meeting['note']}")
    lines.append("<!-- plotloop-speaker-review:end -->")
    return "\n".join(lines)


def _insert_review_block(text: str, meeting: Dict[str, Any]) -> str:
    block = _review_block(meeting)
    marker_re = re.compile(
        r"<!-- plotloop-speaker-review:start -->[\s\S]*?<!-- plotloop-speaker-review:end -->"
    )
    if marker_re.search(text):
        return marker_re.sub(block, text, count=1)
    lines = text.splitlines()
    title_index = 0
    if lines and lines[0].strip() == "---":
        try:
            frontmatter_end = lines.index("---", 1)
        except ValueError:
            frontmatter_end = -1
        if frontmatter_end >= 0:
            title_index = frontmatter_end + 1
            while title_index < len(lines) and not lines[title_index].strip():
                title_index += 1
    if title_index < len(lines) and lines[title_index].startswith("# "):
        return (
            "\n".join(
                [*lines[: title_index + 1], "", block, "", *lines[title_index + 1 :]]
            ).rstrip()
            + "\n"
        )
    if title_index > 0:
        return (
            "\n".join([*lines[:title_index], block, "", *lines[title_index:]]).rstrip()
            + "\n"
        )
    return f"{block}\n\n{text}".rstrip() + "\n"


def _remove_legacy_speaker_notes(text: str) -> str:
    lines = text.splitlines()
    cleaned = [line for line in lines if not re.match(r"^>\s*说话人（.*工作台确认.*", line)]
    return "\n".join(cleaned).rstrip() + "\n"


def _append_confirmation_note(note: Any, confirmation: str) -> str:
    original = str(note or "").strip()
    if not original:
        return confirmation
    if confirmation in original:
        return original
    return f"{original} {confirmation}"


def _replace_labels(text: str, mappings: Iterable[Dict[str, Any]]) -> Tuple[str, int]:
    replacement_count = 0
    result = text
    for mapping in mappings:
        if mapping.get("action") != "replace":
            continue
        label = str(mapping.get("label", "")).strip()
        name = str(mapping.get("name", "")).strip()
        if not label or not name:
            continue
        timeline_pattern = re.compile(
            rf"(?m)^(?P<prefix>\s*-\s+\[[0-9:]+\]\s+){re.escape(label)}(?P<suffix>\s*:)"
        )
        result, count = timeline_pattern.subn(rf"\g<prefix>{name}\g<suffix>", result)
        replacement_count += count

        volc_turn_pattern = re.compile(
            rf"(?m)^(?P<prefix>\s*\*\*){re.escape(label)}(?P<suffix>\*\*[：:])"
        )
        result, count = volc_turn_pattern.subn(rf"\g<prefix>{name}\g<suffix>", result)
        replacement_count += count

        volc_detail_pattern = re.compile(
            rf"(?m)^(?P<prefix>\s*###\s+\d+\s+·\s+[^\n]+?\s+·\s+)"
            rf"{re.escape(label)}(?P<suffix>\s*)$"
        )
        result, count = volc_detail_pattern.subn(rf"\g<prefix>{name}\g<suffix>", result)
        replacement_count += count

        segments = mapping.get("segments") or []
        plain_header_pattern = re.compile(
            rf"(?m)^(?P<prefix>\ufeff?){re.escape(label)}\s+"
            rf"(?P<timestamp>\d{{2}}:\d{{2}}:\d{{2}})(?P<suffix>\s*)$"
        )
        if segments:
            def replace_segment(match: re.Match[str]) -> str:
                timestamp = match.group("timestamp")
                segment = next(
                    (
                        value
                        for value in segments
                        if str(value.get("start", "")) <= timestamp
                        <= str(value.get("end", ""))
                    ),
                    None,
                )
                if not segment:
                    return match.group(0)
                return (
                    f"{match.group('prefix')}{segment.get('name', '')} "
                    f"{timestamp}{match.group('suffix')}"
                )

            result, count = plain_header_pattern.subn(replace_segment, result)
        else:
            result, count = plain_header_pattern.subn(
                rf"\g<prefix>{name} \g<timestamp>\g<suffix>", result
            )
        replacement_count += count
    return result, replacement_count


def apply_decisions(
    review: Dict[str, Any],
    items: Iterable[ReviewItem],
    decisions: Dict[int, ReplyDecision],
) -> Dict[str, Any]:
    payload = json.loads(json.dumps(review, ensure_ascii=False))
    current = payload["current"]
    by_label = {mapping["label"]: mapping for mapping in current["mappings"]}
    for item in items:
        decision = decisions[item.number]
        mapping = by_label[item.label]
        original_action = mapping.get("action")
        original_name = mapping.get("name")
        mapping["action"] = decision.action
        if decision.action == "replace":
            mapping["name"] = decision.name or item.proposed_name
            if mapping["name"] != original_name:
                mapping["confidence"] = "high"
                mapping["note"] = _append_confirmation_note(
                    mapping.get("note"), f"用户确认修改为{mapping['name']}。"
                )
        elif decision.action in {"keep", "ignore"}:
            if decision.action != original_action:
                mapping["confidence"] = "high"
                mapping["note"] = _append_confirmation_note(
                    mapping.get("note"), "用户确认修改为该处理方式。"
                )
    payload["confirmed_at"] = datetime.now().astimezone().isoformat()
    return payload


def _unique_output_paths(
    target_dir: Path,
    title: str,
    created_at: str,
    existing_outputs: Dict[str, str],
    timezone: str = DEFAULT_TIMEZONE,
) -> Tuple[Path, Path]:
    if existing_outputs.get("transcript") and existing_outputs.get("summary"):
        return Path(existing_outputs["transcript"]), Path(existing_outputs["summary"])
    stem = safe_stem(title)
    transcript = target_dir / f"{stem}_转写.md"
    summary = target_dir / f"{stem}_总结.md"
    if not transcript.exists() and not summary.exists():
        return transcript, summary
    suffix = ""
    if created_at:
        try:
            suffix = parse_display_datetime(created_at, timezone).strftime("_%H%M%S")
        except ValueError:
            suffix = ""
    suffix = suffix or "_同名"
    return target_dir / f"{stem}{suffix}_转写.md", target_dir / f"{stem}{suffix}_总结.md"


def _display_created_at(value: Any, timezone: str = DEFAULT_TIMEZONE) -> str:
    created_at = str(value or "").strip()
    if not created_at:
        return ""
    try:
        created = parse_display_datetime(created_at, timezone)
    except ValueError:
        return created_at.replace("T", " ").replace("Z", "")[:19]
    return created.strftime("%Y-%m-%d %H:%M:%S")


def finalize_recording(
    recording_id: str,
    metadata: Dict[str, Any],
    review: Dict[str, Any],
    corrected_transcript: Path,
    corrected_summary: Path,
    raw_transcript: Path,
    raw_summary: Path,
    target_dir: Path,
    existing_outputs: Dict[str, str] | None = None,
    timezone: str = DEFAULT_TIMEZONE,
) -> Dict[str, Any]:
    current = review["current"]
    transcript_text = corrected_transcript.read_text(encoding="utf-8")
    summary_text = corrected_summary.read_text(encoding="utf-8")
    transcript_text = _remove_legacy_speaker_notes(transcript_text)
    summary_text = _remove_legacy_speaker_notes(summary_text)
    transcript_text, replacements = _replace_labels(transcript_text, current["mappings"])
    transcript_text = _insert_review_block(transcript_text, current)
    summary_text = _insert_review_block(summary_text, current)
    transcript_path, summary_path = _unique_output_paths(
        target_dir,
        str(current.get("file_stem") or current.get("meeting") or metadata.get("title")),
        str(metadata.get("created_at", "")),
        existing_outputs or {},
        timezone,
    )
    _atomic_write(transcript_path, transcript_text, raw_transcript)
    _atomic_write(summary_path, summary_text, raw_summary)
    return {
        "recording_id": recording_id,
        "meeting": current.get("meeting", ""),
        "created_at": metadata.get("created_at", ""),
        "privacy": metadata.get("privacy", ""),
        "transcript": str(transcript_path),
        "summary": str(summary_path),
        "replacements": replacements,
        "speakers": [
            name
            for mapping in current.get("mappings", [])
            if mapping.get("action") != "ignore"
            for name in (
                [segment.get("name", "") for segment in mapping.get("segments", [])]
                or [mapping.get("name", "")]
            )
        ],
        "note": current.get("note", ""),
    }


def update_work_index(
    index_path: Path,
    output: Dict[str, Any],
    timezone: str = DEFAULT_TIMEZONE,
) -> bool:
    if not index_path.exists():
        return False
    recording_id = output["recording_id"]
    marker = f"<!-- plotloop:{recording_id} -->"
    text = index_path.read_text(encoding="utf-8")
    created = _display_created_at(output.get("created_at", ""), timezone)
    speakers = "、".join(dict.fromkeys(filter(None, output.get("speakers", [])))) or "待确认"
    transcript_name = Path(output["transcript"]).name
    summary_name = Path(output["summary"]).name
    row = (
        f"| {created}（自动归档） | {output.get('meeting', '')} | {speakers} | "
        f"[总结](<{summary_name}>) / [转写](<{transcript_name}>) | {marker}\n"
    )
    if marker in text:
        lines = text.splitlines()
        index = next(index for index, line in enumerate(lines) if marker in line)
        if lines[index] == row.rstrip("\n"):
            return False
        lines[index] = row.rstrip("\n")
        _atomic_write(index_path, "\n".join(lines) + "\n")
        return True
    header = "## 近期新增重点"
    table_rule = "|---|---|---|---|"
    start = text.find(header)
    rule = text.find(table_rule, start)
    if start < 0 or rule < 0:
        text = text.rstrip() + f"\n\n{header}\n\n| 时间 | 主要会议题 | 核心参会人（可识别） | 资料 |\n{table_rule}\n{row}"
    else:
        lines = text.splitlines()
        rule_line = next(
            index
            for index, line in enumerate(lines)
            if index >= text[:rule].count("\n") and line.strip() == table_rule
        )
        insert_line = rule_line + 1
        timestamp_re = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
        while insert_line < len(lines) and lines[insert_line].lstrip().startswith("|"):
            match = timestamp_re.match(lines[insert_line])
            if match and match.group(1) < created:
                break
            insert_line += 1
        lines.insert(insert_line, row.rstrip("\n"))
        text = "\n".join(lines) + "\n"
    _atomic_write(index_path, text)
    return True


def write_review_artifact(target_dir: Path, batch_id: str, reviews: List[Dict[str, Any]]) -> Path:
    now = datetime.now().astimezone()
    path = target_dir / f"说话人核对_{now:%Y-%m-%d}_{safe_stem(batch_id)}_已确认.md"
    lines = [
        "---",
        "type: speaker-review-confirmed",
        f"date: {now:%Y-%m-%d}",
        f"batch: {batch_id}",
        "status: 已确认",
        "---",
        "",
        f"# 说话人核对 {batch_id}",
        "",
    ]
    for review in reviews:
        current = review["current"]
        lines.extend([f"## {current['meeting']}", "", _review_block(current), ""])
    _atomic_write(path, "\n".join(lines))
    return path


def write_completion_signal(
    target_dir: Path, batch_id: str, outputs: List[Dict[str, Any]], review_artifact: Path
) -> Path:
    path = target_dir / "说话人处理完成信号.json"
    payload = {
        "type": "speaker-processing-signal",
        "version": 1,
        "status": "ready_for_downstream",
        "batch_id": batch_id,
        "completed_at": datetime.now().astimezone().isoformat(),
        "review_artifact": str(review_artifact),
        "outputs": outputs,
        "next_action": "读取确认稿与本批次总结，继续专题提炼、工作台归档或其他下游处理。",
    }
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path
