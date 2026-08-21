from __future__ import annotations

import html
from typing import Any, Dict, Iterable, List, Sequence

from .replies import ReviewItem


MAX_MEETINGS_PER_CARD = 4


def _escape(value: object) -> str:
    return html.escape(str(value or ""), quote=False)


def _truncate(value: object, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _is_focus(mapping: Dict[str, Any]) -> bool:
    return mapping.get("confidence") != "high" or mapping.get("action") != "replace"


def _action_label(action: object) -> str:
    return {
        "replace": "智能替换",
        "keep": "保留标签",
        "ignore": "忽略发言",
    }.get(str(action), str(action or "待确认"))


def _confidence_tag(confidence: object) -> str:
    value = str(confidence or "low")
    label = {"high": "高", "medium": "中", "low": "低"}.get(value, value)
    color = {"high": "blue", "medium": "violet", "low": "neutral"}.get(
        value, "neutral"
    )
    return f"<text_tag color='{color}'>{_escape(label)}置信</text_tag>"


def _mapping_markdown(item: ReviewItem, mapping: Dict[str, Any]) -> str:
    focus = " <text_tag color='violet'>重点确认</text_tag>" if _is_focus(mapping) else ""
    action = _escape(_action_label(mapping.get("action")))
    evidence = _escape(_truncate(mapping.get("note", ""), 240))
    lines = [
        f"<number_tag>{item.number}</number_tag> **{_escape(mapping.get('label'))}** → "
        f"**{_escape(mapping.get('name'))}** {_confidence_tag(mapping.get('confidence'))}{focus}",
        f"<font color='grey'>处理：{action}</font>",
    ]
    if evidence:
        lines.append(f"> <font color='grey'>依据：{evidence}</font>")
    return "\n".join(lines)


def _review_entries(
    reviews: Sequence[Dict[str, object]], items: Sequence[ReviewItem]
) -> List[Dict[str, Any]]:
    item_lookup = {(item.recording_id, item.label): item for item in items}
    entries: List[Dict[str, Any]] = []
    for index, review_entry in enumerate(reviews):
        recording_id = str(review_entry["recording_id"])
        review = review_entry["review"]
        current = review["current"]
        mappings = list(current.get("mappings", []))
        mapped_items = []
        for mapping in mappings:
            key = (recording_id, str(mapping.get("label", "")))
            item = item_lookup.get(key)
            if item is None:
                raise ValueError(f"missing review item for {recording_id} {key[1]}")
            mapped_items.append((item, mapping))
        entries.append(
            {
                "index": index,
                "recording_id": recording_id,
                "current": current,
                "mapped_items": mapped_items,
                "focus_count": sum(1 for mapping in mappings if _is_focus(mapping)),
            }
        )
    return sorted(entries, key=lambda entry: (-entry["focus_count"], entry["index"]))


def _meeting_panel(entry: Dict[str, Any], expanded: bool) -> Dict[str, Any]:
    current = entry["current"]
    date_time = f"{current.get('date', '')} {current.get('time', '')}".strip()
    focus_count = int(entry["focus_count"])
    focus_text = f" · 重点 {focus_count}" if focus_count else ""
    title = _truncate(
        f"{current.get('meeting', '未命名会议')} · {date_time}{focus_text}", 120
    )
    summary = _escape(_truncate(current.get("note", ""), 420))
    mapping_blocks = [
        _mapping_markdown(item, mapping) for item, mapping in entry["mapped_items"]
    ]
    content = []
    if summary:
        content.extend([f"**一句话总结**\n{summary}", ""])
    content.append("\n\n".join(mapping_blocks))
    return {
        "tag": "collapsible_panel",
        "element_id": f"meeting{entry['index'] + 1}",
        "expanded": expanded,
        "background_color": "blue-50" if expanded else "grey-50",
        "border": {
            "color": "blue-100" if expanded else "grey-200",
            "corner_radius": "6px",
        },
        "padding": "8px",
        "vertical_spacing": "8px",
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "width": "fill",
            "icon_position": "right",
        },
        "elements": [
            {
                "tag": "markdown",
                "content": "\n".join(content),
                "text_size": "normal",
            }
        ],
    }


def build_review_cards(
    batch_id: str,
    reviews: Iterable[Dict[str, object]],
    items: Iterable[ReviewItem],
    max_meetings_per_card: int = MAX_MEETINGS_PER_CARD,
) -> List[Dict[str, Any]]:
    review_list = list(reviews)
    item_list = list(items)
    if not review_list:
        raise ValueError("cannot build a review card without meetings")
    if max_meetings_per_card < 1:
        raise ValueError("max_meetings_per_card must be positive")

    entries = _review_entries(review_list, item_list)
    total_focus = sum(int(entry["focus_count"]) for entry in entries)
    chunks = [
        entries[index : index + max_meetings_per_card]
        for index in range(0, len(entries), max_meetings_per_card)
    ]
    cards: List[Dict[str, Any]] = []
    for chunk_index, chunk in enumerate(chunks):
        part = f" · {chunk_index + 1}/{len(chunks)}" if len(chunks) > 1 else ""
        focus_copy = (
            f"**优先确认 {total_focus} 项** · 共 {len(entries)} 场 / {len(item_list)} 项"
            if total_focus
            else f"**本批次均为高置信建议** · 共 {len(entries)} 场 / {len(item_list)} 项"
        )
        overview = {
            "tag": "markdown",
            "element_id": f"overview{chunk_index + 1}",
            "content": (
                focus_copy
                + "\n<font color='grey'>直接回复：全对；2=林夏；3留；4忽略。"
                "多条指令可写在一行。</font>"
            ),
            "text_size": "normal",
        }
        panels = [
            _meeting_panel(
                entry,
                expanded=(panel_index == 0 and int(entry["focus_count"]) > 0),
            )
            for panel_index, entry in enumerate(chunk)
        ]
        cards.append(
            {
                "schema": "2.0",
                "config": {
                    "update_multi": True,
                    "width_mode": "default",
                    "enable_forward": False,
                    "summary": {
                        "content": f"说话人确认 {batch_id}：{len(entries)} 场待确认"
                    },
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"说话人确认{part}",
                    },
                    "subtitle": {
                        "tag": "plain_text",
                        "content": batch_id,
                    },
                    "template": "blue",
                    "icon": {
                        "tag": "standard_icon",
                        "token": "notice_colorful",
                    },
                    "text_tag_list": [
                        {
                            "tag": "text_tag",
                            "text": {"tag": "plain_text", "content": "待确认"},
                            "color": "blue",
                        },
                        {
                            "tag": "text_tag",
                            "text": {
                                "tag": "plain_text",
                                "content": f"重点 {total_focus}",
                            },
                            "color": "violet",
                        },
                    ],
                },
                "body": {
                    "direction": "vertical",
                    "padding": "12px 12px 20px 12px",
                    "vertical_spacing": "8px",
                    "elements": [overview, *panels],
                },
            }
        )
    return cards
