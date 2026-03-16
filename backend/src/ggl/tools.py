"""Tools for GGL (Graph Guided Learning) state management."""

from __future__ import annotations

import logging
from typing import Annotated

from langchain.tools import InjectedToolCallId, ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langgraph.typing import ContextT

# Direct import of thread_state module (NOT through src.agents.__init__ to avoid
# circular imports since src.agents.__init__ imports lead_agent which imports this file)
from src.agents.thread_state import GGLState, KnowledgeCard, ThreadState, TopicGraph, TopicNode

logger = logging.getLogger(__name__)


@tool("update_ggl_graph", parse_docstring=True)
def update_ggl_graph_tool(
    runtime: ToolRuntime[ContextT, "ThreadState"],
    tool_call_id: Annotated[str, InjectedToolCallId],
    nodes: list[dict],
    edges: list[list[str]],
    active_node_id: str | None = None,
    current_path: list[str] | None = None,
) -> Command:
    """Update the GGL knowledge graph in the current thread state.

    Use this tool to write the topic graph into the thread state so the
    frontend renders the Knowledge Map in real time.

    Call this tool AFTER finishing all research subagents and determining
    the knowledge nodes and their relationships.

    Args:
        nodes: List of topic nodes, each with keys: id (unique slug), label (display name),
               state (one of unvisited/exploring/mastered/blurry/unknown).
        edges: Directed edges as [source_id, target_id] pairs representing
               prerequisite relationships (source should be learned before target).
        active_node_id: The node ID to start learning from first.
                        Should be the entry point of the learning path.
        current_path: Ordered list of node IDs representing the recommended
                      learning sequence from start to end.
    """
    # Lazy import to avoid circular dependency at module level
    from src.agents.thread_state import GGLState, TopicGraph, TopicNode  # noqa: PLC0415

    if not nodes:
        return Command(
            update={"messages": [ToolMessage("Error: nodes list cannot be empty", tool_call_id=tool_call_id)]},
        )

    valid_states = {"unvisited", "exploring", "mastered", "blurry", "unknown"}
    validated_nodes: list[TopicNode] = []
    for n in nodes:
        if not isinstance(n, dict) or not n.get("id") or not n.get("label"):
            return Command(
                update={"messages": [ToolMessage(f"Error: each node must have 'id' and 'label', got: {n}", tool_call_id=tool_call_id)]},
            )
        node_state = n.get("state", "unvisited")
        if node_state not in valid_states:
            node_state = "unvisited"
        validated_nodes.append(
            TopicNode(id=str(n["id"]), label=str(n["label"]), state=node_state)
        )

    node_ids = {n["id"] for n in validated_nodes}
    validated_edges: list[list[str]] = []
    for edge in edges:
        if isinstance(edge, (list, tuple)) and len(edge) == 2:
            src, tgt = str(edge[0]), str(edge[1])
            if src in node_ids and tgt in node_ids:
                validated_edges.append([src, tgt])
            else:
                logger.warning(f"Skipping edge with unknown node(s): {edge}")

    topic_graph = TopicGraph(nodes=validated_nodes, edges=validated_edges)

    resolved_active = (
        active_node_id
        if active_node_id and active_node_id in node_ids
        else validated_nodes[0]["id"]
    )

    current_ggl: GGLState | None = runtime.state.get("ggl") if runtime else None
    current_version = 0
    if current_ggl and isinstance(current_ggl.get("topic_graph_version"), int):
        current_version = current_ggl["topic_graph_version"]

    # Detect newly mastered nodes (not mastered before, mastered now) for knowledge card generation.
    prev_mastered: set[str] = set()
    if current_ggl:
        prev_nodes = (current_ggl.get("topic_graph") or {}).get("nodes") or []
        prev_mastered = {n["id"] for n in prev_nodes if n.get("state") == "mastered"}
    existing_cards: set[str] = set((current_ggl or {}).get("knowledge_cards") or {})
    newly_mastered = [
        n["id"] for n in validated_nodes
        if n["state"] == "mastered" and n["id"] not in prev_mastered and n["id"] not in existing_cards
    ]

    new_ggl_state = GGLState(
        topic_graph=topic_graph,
        topic_graph_version=current_version + 1,
        active_node_id=resolved_active,
        current_path=current_path or [n["id"] for n in validated_nodes],
        pending_card_node_ids=newly_mastered if newly_mastered else None,
    )

    summary = (
        f"知识图谱已写入：{len(validated_nodes)} 个节点，"
        f"{len(validated_edges)} 条连接，起始节点：{resolved_active}"
    )
    if newly_mastered:
        summary += f"；新掌握节点待生成知识卡：{newly_mastered}"
    logger.info(summary)

    return Command(
        update={
            "ggl": new_ggl_state,
            "messages": [ToolMessage(summary, tool_call_id=tool_call_id)],
        },
    )
