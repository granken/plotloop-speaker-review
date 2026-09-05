from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class ReviewItem:
    number: int
    recording_id: str
    meeting: str
    label: str
    proposed_name: str
    proposed_action: str
    proposed_confidence: str
    note: str


@dataclass(frozen=True)
class ReplyDecision:
    number: int
    action: str
    name: Optional[str] = None


@dataclass(frozen=True)
class ParsedReply:
    decisions: Dict[int, ReplyDecision]
    complete: bool
    error: Optional[str] = None


CHANGE_RE = re.compile(r"^(\d+)\s*(?:=|改成|改为|改)\s*(\S.+?|\S)$")
ACCEPT_RE = re.compile(r"^(\d+)\s*(?:对|确认|接受)$")
KEEP_RE = re.compile(r"^(\d+)\s*(?:留|保留)$")
IGNORE_RE = re.compile(r"^(\d+)\s*(?:忽略|不要|环境音)$")
PENDING_RE = re.compile(r"^(\d+)\s*(?:待核|不确定|待确认)$")
EMBEDDED_DIRECTIVE_RE = re.compile(
    r"\s+\d+\s*(?:=|改成|改为|改|对|确认|接受|留|保留|忽略|不要|环境音|待核|不确定|待确认)"
)


def looks_like_reply(text: str) -> bool:
    normalized = text.strip()
    if normalized in {"全对", "全部确认", "都对", "全部对"}:
        return True
    return bool(
        re.match(
            r"^\d+\s*(?:=|改成|改为|改|对|确认|接受|留|保留|忽略|不要|环境音|待核|不确定|待确认)",
            normalized,
        )
    )


def build_review_message(batch_id: str, reviews: Iterable[Dict[str, object]]) -> tuple[str, List[ReviewItem]]:
    lines = [
        f"【说话人确认 {batch_id}】",
        "直接回复：全对；2=林夏；3留；4忽略。可组合成一行。",
    ]
    items: List[ReviewItem] = []
    number = 1
    for review_entry in reviews:
        recording_id = str(review_entry["recording_id"])
        review = review_entry["review"]
        current = review["current"]
        lines.append("")
        lines.append(
            f"{current['meeting']}｜{current.get('date', '')} {current.get('time', '')}".rstrip()
        )
        if current.get("note"):
            lines.append(str(current["note"]))
        for mapping in current.get("mappings", []):
            item = ReviewItem(
                number=number,
                recording_id=recording_id,
                meeting=str(current["meeting"]),
                label=str(mapping["label"]),
                proposed_name=str(mapping["name"]),
                proposed_action=str(mapping["action"]),
                proposed_confidence=str(mapping["confidence"]),
                note=str(mapping.get("note", "")),
            )
            items.append(item)
            lines.append(
                f"{number}. {item.label} → {item.proposed_name}"
                f"（{item.proposed_confidence}，{item.proposed_action}）"
            )
            if item.note:
                lines.append(f"   依据：{item.note}")
            number += 1
    lines.extend(["", f"批次号：{batch_id}"])
    return "\n".join(lines), items


def parse_reply(text: str, items: Iterable[ReviewItem]) -> ParsedReply:
    item_list = list(items)
    valid = {item.number for item in item_list}
    item_by_number = {item.number: item for item in item_list}
    normalized = text.strip().replace("，", ";").replace(",", ";").replace("；", ";")
    normalized = re.sub(rf"【?说话人确认\s+[A-Za-z0-9_-]+】?", "", normalized).strip()
    if normalized in {"全对", "全部确认", "都对", "全部对"}:
        decisions = {
            item.number: ReplyDecision(
                number=item.number,
                action=item.proposed_action,
                name=item.proposed_name,
            )
            for item in item_list
        }
        return ParsedReply(decisions=decisions, complete=True)

    decisions: Dict[int, ReplyDecision] = {}
    tokens = [token.strip() for token in re.split(r"[;\n]+", normalized) if token.strip()]
    if not tokens:
        return ParsedReply(decisions={}, complete=False, error="回复为空")

    for token in tokens:
        match = CHANGE_RE.match(token)
        if match:
            number, name = int(match.group(1)), match.group(2).strip()
            if EMBEDDED_DIRECTIVE_RE.search(name):
                return ParsedReply(
                    decisions={},
                    complete=False,
                    error="检测到多条粘连指令，请用分号、逗号或换行分隔",
                )
            decision = ReplyDecision(number=number, action="replace", name=name)
        elif (match := ACCEPT_RE.match(token)):
            number = int(match.group(1))
            item = item_by_number.get(number)
            if item is None:
                return ParsedReply(decisions={}, complete=False, error=f"不存在编号 {number}")
            decision = ReplyDecision(number=number, action=item.proposed_action, name=item.proposed_name)
        elif (match := KEEP_RE.match(token)):
            number = int(match.group(1))
            decision = ReplyDecision(number=number, action="keep")
        elif (match := IGNORE_RE.match(token)):
            number = int(match.group(1))
            decision = ReplyDecision(number=number, action="ignore")
        elif (match := PENDING_RE.match(token)):
            number = int(match.group(1))
            decision = ReplyDecision(number=number, action="pending")
        else:
            return ParsedReply(
                decisions={}, complete=False, error=f"无法识别：{token}"
            )
        if number not in valid:
            return ParsedReply(decisions={}, complete=False, error=f"不存在编号 {number}")
        if number in decisions:
            return ParsedReply(decisions={}, complete=False, error=f"编号 {number} 重复")
        decisions[number] = decision

    return ParsedReply(
        decisions=decisions,
        complete=valid.issubset(decisions.keys())
        and all(item.action != "pending" for item in decisions.values()),
    )
