from __future__ import annotations

import re
from typing import Any


def extract_topics_from_messages(messages: list[Any], candidate_topics: list[str] | None = None) -> list[str]:
    """Extract candidate topic labels from recent messages.

    For Phase 4 we keep extraction deterministic and lightweight:
    - Prefer topic labels already in graph (candidate_topics) when they appear in text.
    - Fallback to simple noun-like spans (CJK/ASCII words with length >= 2).
    """
    text = " ".join(str(m) for m in messages if m is not None)
    extracted: list[str] = []

    if candidate_topics:
        for topic in candidate_topics:
            label = topic.strip()
            if label and label in text:
                extracted.append(label)

    if extracted:
        return extracted

    # Basic fallback tokenizer for mixed Chinese/English content.
    tokens = re.findall(r"[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9_\-]{1,30}", text)
    seen: set[str] = set()
    for token in tokens:
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        extracted.append(token)
        if len(extracted) >= 12:
            break
    return extracted

