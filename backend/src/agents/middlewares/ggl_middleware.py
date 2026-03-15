import logging
from typing import NotRequired

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from src.agents.thread_state import GGLState
from src.ggl.intent import IntentType, classify_intent

logger = logging.getLogger(__name__)

# Spec §2.3: Context budget limits.
_MAX_NEIGHBORS = 12
_MAX_PATH_NODES = 8


class GGLMiddlewareState(AgentState):
    ggl: NotRequired[GGLState | None]
    agent_variant: NotRequired[str | None]


class GGLMiddleware(AgentMiddleware[GGLMiddlewareState]):
    def __init__(self):
        self.intent_timeout_ms = 800

    def _get_neighbors(self, ggl_state: GGLState, node_id: str) -> list[dict]:
        """Return first-degree neighbor nodes of node_id from topic_graph edges."""
        topic_graph = ggl_state.get("topic_graph") or {}
        nodes = {n["id"]: n for n in (topic_graph.get("nodes") or []) if isinstance(n, dict) and n.get("id")}
        edges = topic_graph.get("edges") or []
        neighbor_ids: list[str] = []
        for edge in edges:
            if not (isinstance(edge, (list, tuple)) and len(edge) >= 2):
                continue
            a, b = str(edge[0]), str(edge[1])
            if a == node_id and b not in neighbor_ids:
                neighbor_ids.append(b)
            elif b == node_id and a not in neighbor_ids:
                neighbor_ids.append(a)
        result = []
        for nid in neighbor_ids[:_MAX_NEIGHBORS]:
            node = nodes.get(nid)
            if node:
                result.append({"id": nid, "label": node.get("label"), "state": node.get("state")})
        return result

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

        active_node_id = ggl_state.get("active_node_id")
        topic_graph = ggl_state.get("topic_graph") or {}
        knowledge_cards = ggl_state.get("knowledge_cards") or {}
        nodes = topic_graph.get("nodes") or []

        context_parts: list[str] = []

        # --- Stats (global summary) ---
        total = len(nodes)
        mastered_count = sum(1 for n in nodes if n.get("state") == "mastered")
        context_parts.append(f"stats: {{\"total\": {total}, \"mastered\": {mastered_count}}}")

        # --- Active node ---
        active_node_data = None
        if active_node_id:
            for node in nodes:
                if node.get("id") == active_node_id:
                    active_node_data = node
                    break

        if active_node_data:
            card_summary = None
            if active_node_id in knowledge_cards:
                card = knowledge_cards[active_node_id]
                card_summary = (card.get("summary") or "")[:600] or None

            active_block = {
                "id": active_node_id,
                "label": active_node_data.get("label"),
                "state": active_node_data.get("state"),
            }
            if card_summary:
                active_block["summary"] = card_summary  # type: ignore[assignment]
            context_parts.append(f"active_node: {active_block}")

            # --- First-degree neighbors (spec §2.3) ---
            neighbors = self._get_neighbors(ggl_state, active_node_id)
            if neighbors:
                context_parts.append(f"neighbors: {neighbors}")
        else:
            context_parts.append("active_node: null")

        # --- Current path summary (spec §2.3) ---
        current_path = ggl_state.get("current_path") or []
        path_limited = current_path[:_MAX_PATH_NODES]
        if path_limited:
            node_labels = {n.get("id"): n.get("label") for n in nodes if isinstance(n, dict)}
            path_labels = [node_labels.get(nid, nid) for nid in path_limited]
            context_parts.append(f"path_summary: \"{' -> '.join(str(lbl) for lbl in path_labels)}\"")

        # --- Intent ---
        if intent is not None:
            context_parts.append(f"intent: \"{intent.value}\"")
            if intent == IntentType.DIGRESSION:
                context_parts.append("hint: \"用户提问可能偏离当前学习主题，请适当处理。\"")
            elif intent == IntentType.REVIEW:
                context_parts.append("hint: \"用户想要复习已学内容。\"")
            elif intent == IntentType.MASTERED:
                context_parts.append("hint: \"用户表示已掌握某个知识点。\"")

        body = "\n".join(context_parts)
        wrapped = f"<ggl_context>\n{body}\n</ggl_context>"
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
            "related_topics": related_topics[:_MAX_NEIGHBORS],
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
        logger.info("GGL intent classification result: %s", intent)

        return self._build_context_message(state, intent)

    def after_model(
        self,
        state: GGLMiddlewareState,
        runtime: Runtime,
    ) -> dict | None:
        """Spec §2.3 after_model: parse tool results and update state.ggl.

        Tool state updates from update_graph_node / create_graph_node /
        link_to_existing_node are already applied via Command(update={...})
        inside the tools themselves (LangGraph merges them via ggl_reducer).
        Here we perform housekeeping: update current_path when active_node_id
        changes after a tool call.
        """
        agent_variant = state.get("agent_variant") or runtime.context.get("agent_variant")
        if agent_variant != "ggl":
            return None

        ggl_state = state.get("ggl")
        if not ggl_state:
            return None

        active_node_id = ggl_state.get("active_node_id")
        current_path = list(ggl_state.get("current_path") or [])

        if active_node_id and active_node_id not in current_path:
            current_path.append(active_node_id)
            logger.debug("GGL after_model: appending %s to current_path", active_node_id)
            return {"ggl": {"current_path": current_path}}

        return None
