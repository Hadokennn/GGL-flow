import logging
from typing import NotRequired

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from src.agents.thread_state import GGLState
from src.ggl.intent import IntentType, classify_intent

logger = logging.getLogger(__name__)


class GGLMiddlewareState(AgentState):
    ggl: NotRequired[GGLState | None]
    agent_variant: NotRequired[str | None]


class GGLMiddleware(AgentMiddleware[GGLMiddlewareState]):
    def __init__(self):
        self.intent_timeout_ms = 800

    def _build_context_message(
        self,
        state: GGLMiddlewareState,
        intent: IntentType | None,
    ) -> dict | None:
        ggl_state = state.get("ggl")
        if not ggl_state or not ggl_state.get("topic_graph"):
            content = (
                "<ggl_context>\n"
                "当前会话为 GGL 学习模式，但知识图谱尚未初始化。\n"
                "请优先引导用户明确学习主题，并进入图谱初始化流程。\n"
                "</ggl_context>"
            )
            return {"messages": [HumanMessage(name="ggl_context", content=content)]}

        active_node = ggl_state.get("active_node_id")
        topic_graph = ggl_state.get("topic_graph")
        knowledge_cards = ggl_state.get("knowledge_cards", {})

        context_parts: list[str] = []
        context_parts.append("当前学习主题图谱状态：")

        if topic_graph:
            nodes = topic_graph.get("nodes", [])
            context_parts.append(f"- 总节点数: {len(nodes)}")

            mastered_count = sum(
                1 for n in nodes if n.get("state") == "mastered"
            )
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
                context_parts.append(f"\n当前学习节点: {active_node_data.get('label')} (状态: {active_node_data.get('state')})")

                if knowledge_cards and active_node in knowledge_cards:
                    card = knowledge_cards[active_node]
                    if card.get("summary"):
                        context_parts.append(f"\n节点摘要: {card['summary'][:200]}")

        if intent is not None:
            context_parts.append(f"\n当前意图: {intent.value}")

        if intent == IntentType.DIGRESSION:
            context_parts.append("\n注意: 用户提问可能偏离了当前学习主题，请适当处理。")
        elif intent == IntentType.REVIEW:
            context_parts.append("\n注意: 用户想要复习已学内容。")
        elif intent == IntentType.MASTERED:
            context_parts.append("\n注意: 用户表示已掌握某个知识点。")

        wrapped = "<ggl_context>\n" + "\n".join(context_parts) + "\n</ggl_context>"
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

        # Cap related topics to avoid ballooning intent prompt.
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

        # Synthetic continuation should not affect intent classification.
        if runtime.context.get("synthetic") is True:
            logger.debug("Skip GGL context injection for synthetic continuation")
            return None

        ggl_state = state.get("ggl")
        if not ggl_state or not ggl_state.get("topic_graph"):
            logger.debug("GGL state is empty, injecting onboarding guidance")
            return self._build_context_message(state, intent=None)

        messages = state.get("messages", [])
        intent_context = self._build_intent_context(ggl_state)

        intent = classify_intent(
            messages,
            timeout_ms=self.intent_timeout_ms,
            ggl_context=intent_context,
        )
        logger.info(f"GGL intent classification result: {intent}")

        context_update = self._build_context_message(state, intent)
        return context_update
