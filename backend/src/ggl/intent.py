import hashlib
import json
import logging
import re
import time
from enum import Enum
from typing import Any

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from src.models.factory import create_chat_model

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    CONTINUE = "Continue"
    DIGRESSION = "Digression"
    REVIEW = "Review"
    MASTERED = "Mastered"


class IntentResult(BaseModel):
    intent: IntentType
    reason: str


INTENT_PROMPT = """你是一个学习助手，负责分析用户消息的意图。

当前学习场景是 Graph Guided Learning (GGL)，用户正在学习一个主题知识图谱。

请分析用户消息的意图并分类：

1. Continue (继续学习): 用户想要继续当前主题的深入学习
2. Digression (偏离主题): 用户提问与当前学习主题无关的内容
3. Review (复习): 用户想要复习已学内容
4. Mastered (已掌握): 用户表示已掌握某个知识点

分析用户最后一条消息，给出意图分类和原因。

{ggl_context_block}

用户消息: {user_message}

请严格返回 JSON（不要 markdown 代码块），格式如下：
{{"intent":"Continue|Digression|Review|Mastered","reason":"..."}}"""


_intent_cache: dict[str, tuple[IntentType, float]] = {}
_CACHE_TTL = 30


def _get_message_hash(message: str) -> str:
    return hashlib.md5(message.encode()).hexdigest()


def _extract_last_user_message(messages: list[Any]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = msg.content
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = str(item.get("text", "")).strip()
                        if text:
                            return text
                return ""
            return str(content).strip()
    return ""


def _parse_intent_from_content(content: str) -> IntentResult | None:
    text = content.strip()
    if not text:
        return None

    # Support models that still wrap JSON with markdown fences.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
        raw_intent = str(parsed.get("intent", "")).strip()
        reason = str(parsed.get("reason", "")).strip() or "parsed_from_json"
        intent = IntentType(raw_intent)
        return IntentResult(intent=intent, reason=reason)
    except Exception:
        # Heuristic fallback when provider doesn't obey JSON instruction.
        lowered = text.lower()
        for intent_type in IntentType:
            if intent_type.value.lower() in lowered:
                return IntentResult(
                    intent=intent_type,
                    reason="heuristic_keyword_match",
                )
    return None


def _build_context_block(ggl_context: dict[str, Any] | None) -> str:
    if not ggl_context:
        return "当前学习上下文：未知（请仅依据用户消息做保守判断，优先 Continue）。"

    current_topic = str(ggl_context.get("current_topic") or "").strip() or "未知"
    related_topics = ggl_context.get("related_topics") or []
    if not isinstance(related_topics, list):
        related_topics = []
    related = "、".join(str(topic).strip() for topic in related_topics if str(topic).strip()) or "无"
    return (
        "当前学习上下文：\n"
        f"- 当前学习主题: {current_topic}\n"
        f"- 相关知识点: {related}"
    )


def _classify_intent_with_llm(llm: Any, user_message: str, ggl_context: dict[str, Any] | None = None) -> IntentResult | None:
    try:
        prompt = INTENT_PROMPT.format(
            user_message=user_message,
            ggl_context_block=_build_context_block(ggl_context),
        )
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        return _parse_intent_from_content(content)
    except Exception as e:
        logger.warning(f"Intent classification failed: {e}")
        return None


def classify_intent(
    messages: list[Any],
    llm: Any = None,
    timeout_ms: int = 800,
    ggl_context: dict[str, Any] | None = None,
) -> IntentType:
    if not messages:
        return IntentType.CONTINUE

    last_user_message = _extract_last_user_message(messages)
    if not last_user_message:
        return IntentType.CONTINUE

    context_key = json.dumps(ggl_context or {}, ensure_ascii=False, sort_keys=True)
    msg_hash = _get_message_hash(f"{last_user_message}|{context_key}")
    if msg_hash in _intent_cache:
        cached_intent, cached_time = _intent_cache[msg_hash]
        if time.time() - cached_time < _CACHE_TTL:
            logger.debug(f"Intent cache hit: {cached_intent}")
            return cached_intent

    if llm is None:
        try:
            llm = create_chat_model(thinking_enabled=False)
        except Exception as e:
            logger.warning(f"Failed to create LLM for intent classification: {e}")
            return IntentType.CONTINUE

    start_ts = time.time()
    try:
        result = _classify_intent_with_llm(llm, last_user_message, ggl_context=ggl_context)
        if result:
            elapsed_ms = (time.time() - start_ts) * 1000
            if elapsed_ms > timeout_ms:
                logger.warning(f"Intent classification timed out logically ({elapsed_ms:.1f}ms > {timeout_ms}ms), fallback Continue")
                return IntentType.CONTINUE
            _intent_cache[msg_hash] = (result.intent, time.time())
            return result.intent
    except Exception as e:
        logger.warning(f"Intent classification error: {e}")

    return IntentType.CONTINUE
