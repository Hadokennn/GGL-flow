import logging
from typing import NotRequired

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from src.agents.knowledge_card.queue import get_knowledge_card_queue
from src.agents.thread_state import GGLState
from src.ggl.intent import IntentType, IntentResult, classify_intent

logger = logging.getLogger(__name__)

# TODO: path inital. Path to the GGL init skill file injected into LLM prompt
_GGL_INIT_SKILL_PATH = "/mnt/skills/public/ggl-init/SKILL.md"

# Marker in init message — used to detect if we've already injected (avoid duplicate on every LLM call)
_INIT_MARKER = "知识图谱尚未初始化"
_CONTEXT_MARKER = "__ggl_ctx__"

# Short confirmations that imply "user mastered current node" when active node is exploring.
# classify_intent often returns Continue due to "保守判断"; this heuristic ensures MASTERED branch is reached.
_MASTERED_CONFIRMATIONS = frozenset({"好", "1", "2", "ok", "继续", "懂了", "明白", "嗯", "可以", "行", "收到"})


class GGLMiddlewareState(AgentState):
    ggl: NotRequired[GGLState | None]
    agent_variant: NotRequired[str | None]


class GGLMiddleware(AgentMiddleware[GGLMiddlewareState]):
    def __init__(self):
        self.intent_timeout_ms = 10000

    def _has_init_been_injected(self, messages: list) -> bool:
        """Check if init instruction was already injected (avoid duplicate on every LLM call)."""
        for msg in messages:
            if getattr(msg, "name", None) == "ggl_context":
                content = getattr(msg, "content", "") or ""
                if isinstance(content, str) and _INIT_MARKER in content:
                    return True
        return False

    def _extract_last_user_message(self, messages: list) -> str:
        """Extract the last user message (HumanMessage, not ggl_context)."""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                content = getattr(msg, "text", "")
                if isinstance(content, str):
                    return content.strip()
                return ""
        return ""

    def _heuristic_mastered(
        self,
        last_user_msg: str,
        ggl_state: GGLState | None,
    ) -> bool:
        """True if last message is a short confirmation and active node is exploring."""
        if not ggl_state or not last_user_msg:
            return False
        topic_graph = ggl_state.get("topic_graph")
        active_id = ggl_state.get("active_node_id")
        if not topic_graph or not active_id:
            return False
        nodes = topic_graph.get("nodes") or []
        active_node = next((n for n in nodes if n.get("id") == active_id), None)
        if not active_node or active_node.get("state") != "exploring":
            return False
        normalized = last_user_msg.strip().lower()
        return normalized in _MASTERED_CONFIRMATIONS

    def _has_context_been_injected(self, messages: list) -> bool:
        """Check if ggl_context was already injected for the current user turn.

        Only run classify_intent when the last message is a HumanMessage (start of turn).
        Once we've injected ggl_context after the last user message, skip until next user message.
        """
        last_user_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if isinstance(msg, HumanMessage) and getattr(msg, "name", None) != "ggl_context":
                last_user_idx = i
                break
        for msg in messages[last_user_idx + 1 :]:
            if getattr(msg, "name", None) == "ggl_context":
                content = getattr(msg, "content", "") or ""
                if isinstance(content, str) and _CONTEXT_MARKER in content:
                    return True
        return False

    def _build_init_message(self) -> dict:
        """Inject mandatory init instruction when topic_graph is absent (first message)."""
        content = (
            "当前会话为 GGL 学习模式，知识图谱尚未初始化。\n\n"
            "**你的首要任务是初始化知识图谱，必须严格按以下步骤执行：**\n\n"
            f"1. 立即使用 `read_file` 工具读取 GGL 初始化 Skill：`{_GGL_INIT_SKILL_PATH}`\n"
            "2. 按照 Skill 中的流程，使用 `task` 工具启动 3 个并行 subagent 进行深度研究\n"
            "3. 综合 subagent 的研究结果，用 `write_file` 将调研报告写入 `/mnt/user-data/outputs`，并用 `present_files` 加入 artifacts\n"
            "4. 调用 `update_ggl_graph` 工具将图谱写入 state\n"
            "5. 向用户展示图谱概览和推荐学习路径\n\n"
            "**禁止跳过 subagent 并行研究直接生成图谱。**\n"
            "**必须调用 update_ggl_graph 工具才能让图谱出现在前端。**\n"
        )
        return {"messages": [HumanMessage(name="ggl_context", content=content)]}

    def _build_context_message(
        self,
        state: GGLMiddlewareState,
        intent_result: IntentResult,
    ) -> dict | None:
        ggl_state = state.get("ggl")
        active_node = ggl_state.get("active_node_id") if ggl_state else None
        topic_graph = ggl_state.get("topic_graph") if ggl_state else None
        knowledge_cards = (ggl_state.get("knowledge_cards") or {}) if ggl_state else {}

        context_parts: list[str] = []
        context_parts.append("当前学习主题图谱状态：")

        if topic_graph:
            nodes = topic_graph.get("nodes", [])
            context_parts.append(f"- 总节点数: {len(nodes)}")
            mastered_count = sum(1 for n in nodes if n.get("state") == "mastered")
            context_parts.append(f"- 已掌握: {mastered_count}")
        else:
            context_parts.append("- 尚未创建图谱")

        if active_node and topic_graph:
            active_node_data = None
            for node in topic_graph.get("nodes", []):
                if node.get("id") == active_node:
                    active_node_data = node
                    break

            if active_node_data:
                context_parts.append(
                    f"\n当前学习节点: {active_node_data.get('label')} (状态: {active_node_data.get('state')})"
                )
                if knowledge_cards and active_node in knowledge_cards:
                    card = knowledge_cards[active_node]
                    if card.get("summary"):
                        context_parts.append(f"\n节点摘要: {card['summary'][:200]}")
        intent = intent_result.intent
        if intent is not None:
            context_parts.append(f"\n当前意图: {intent.value}")

        if intent == IntentType.DIGRESSION:
            context_parts.append("\n注意: 用户提问可能偏离了当前学习主题，请适当处理。")
        elif intent == IntentType.REVIEW:
            context_parts.append("\n注意: 用户想要复习已学内容。")
        elif intent == IntentType.MASTERED:
            context_parts.append("\n注意: 用户已掌握当前节点，请调用 `update_ggl_graph` 将该节点状态改为 mastered 并推进到下一节点。")
        elif intent == IntentType.JUMP:
            context_parts.append(f"\n注意: 用户想要跳转到另一个主题{intent_result.next_node_id}，请调用 `update_ggl_graph` 将该节点状态改为 exploring，再开始讲解。")
        elif (
            active_node_data
            and active_node_data.get("state") == "unvisited"
        ):
            context_parts.append(
                "\n注意: 用户手动跳转到了未学习的节点，请先调用 `update_ggl_graph` 将该节点状态改为 exploring，再开始讲解。"
            )

        wrapped = "<ggl_context>\n" + _CONTEXT_MARKER + "\n" + "\n".join(context_parts) + "\n</ggl_context>"
        return {"messages": [HumanMessage(name="ggl_context", content=wrapped)]}

    def _build_intent_context(self, ggl_state: GGLState | None) -> dict[str, object]:
        if not ggl_state:
            return {}

        topic_graph = ggl_state.get("topic_graph") or {}
        nodes = topic_graph.get("nodes", [])
        active_node_id = ggl_state.get("active_node_id")

        current_topic = None
        related_topics: list[str] = []
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                label = str(node.get("label") or "").strip()
                node_id = node.get("id")
                if not label:
                    continue
                related_topics.append(label)
                if active_node_id and node_id == active_node_id:
                    current_topic = label

        return {
            "current_topic": current_topic,
            "related_topics": related_topics[:12],
        }

    def before_model(
        self,
        state: GGLMiddlewareState,
        runtime: Runtime,
    ) -> dict | None:
        agent_variant = state.get("agent_variant") or runtime.context.get("agent_variant")
        if agent_variant != "ggl":
            return None

        if runtime.context.get("synthetic") is True:
            logger.debug("Skip GGL context injection for synthetic continuation")
            return None

        ggl_state = state.get("ggl")
        if not ggl_state or not ggl_state.get("topic_graph"):
            messages = state.get("messages", [])
            if self._has_init_been_injected(messages):
                logger.debug("GGL init already injected — skip to avoid duplicate on every LLM call")
                return None
            logger.info("GGL topic_graph absent — injecting mandatory init instruction (once)")
            return self._build_init_message()

        messages = state.get("messages", [])
        if self._has_context_been_injected(messages):
            logger.debug("GGL context already injected this turn — skip")
            return None

        last_user_msg = self._extract_last_user_message(messages)

        # Heuristic: short confirmation + exploring node → MASTERED (classify_intent often returns Continue)
        if self._heuristic_mastered(last_user_msg, ggl_state):
            logger.info("GGL heuristic: short confirmation + exploring → MASTERED")
            intent = IntentType.MASTERED
        else:
            intent_context = self._build_intent_context(ggl_state)
            user_messages = [
                m for m in messages
                if isinstance(m, HumanMessage) and getattr(m, "name", None) != "ggl_context"
            ]
            intent_result = classify_intent(user_messages, timeout_ms=self.intent_timeout_ms, ggl_context=intent_context)
            logger.info(f"GGL intent classification result: {intent_result}")
            return self._build_context_message(state, intent_result)
        return None

    def after_agent(
        self,
        state: GGLMiddlewareState,
        runtime: Runtime,
    ) -> dict | None:
        """Enqueue background knowledge card generation for newly mastered nodes."""
        agent_variant = state.get("agent_variant") or runtime.context.get("agent_variant")
        if agent_variant != "ggl":
            return None

        ggl_state = state.get("ggl")
        pending = (ggl_state or {}).get("pending_card_node_ids") or []
        if not pending:
            return None

        thread_id = runtime.context.get("thread_id")
        if not thread_id:
            logger.warning("GGLMiddleware.after_agent: no thread_id in context, skip card queue")
            return None

        topic_graph = (ggl_state or {}).get("topic_graph") or {}
        nodes_by_id = {n["id"]: n for n in (topic_graph.get("nodes") or [])}
        messages = state.get("messages", [])

        queue = get_knowledge_card_queue()
        for node_id in pending:
            node_label = (nodes_by_id.get(node_id) or {}).get("label") or node_id
            queue.add(
                thread_id=thread_id,
                node_id=node_id,
                node_label=node_label,
                messages=messages,
            )

        logger.info("GGL: enqueued %d knowledge card tasks, clearing pending", len(pending))
        return {"ggl": {"pending_card_node_ids": []}}
