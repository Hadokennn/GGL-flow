from __future__ import annotations

from typing import Any

MAX_SUMMARY_CHARS = 600
MAX_KEYPOINTS = 8
MAX_EXAMPLES = 5
MAX_MISTAKES = 5
MAX_RELATED = 8


def _truncate(text: str, limit: int) -> str:
    value = text.strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _unique_keep_order(items: list[str], limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
        if len(out) >= limit:
            break
    return out


def build_knowledge_card(topic_label: str, recent_messages: list[str]) -> dict[str, Any]:
    """Build a deterministic knowledge card from recent conversation text."""
    joined = "\n".join(msg.strip() for msg in recent_messages if msg.strip())
    lines = [line.strip("-* ").strip() for line in joined.splitlines() if line.strip()]

    summary_base = joined if joined else f"围绕 {topic_label} 的知识梳理。"
    summary = _truncate(summary_base, MAX_SUMMARY_CHARS)

    keypoints = _unique_keep_order(lines, MAX_KEYPOINTS)
    examples = _unique_keep_order([line for line in lines if "例如" in line or "example" in line.lower()], MAX_EXAMPLES)
    mistakes = _unique_keep_order([line for line in lines if "误区" in line or "错误" in line], MAX_MISTAKES)
    related = _unique_keep_order([topic_label], MAX_RELATED)

    if not keypoints:
        keypoints = [f"{topic_label} 的核心概念待进一步补充。"]

    return {
        "summary": summary,
        "keyPoints": keypoints,
        "examples": examples,
        "commonMistakes": mistakes,
        "relatedConcepts": related,
    }

