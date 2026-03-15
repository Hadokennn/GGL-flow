from __future__ import annotations

import json
import uuid
from typing import Annotated, Any

from langchain.tools import InjectedToolCallId, ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langgraph.typing import ContextT

from src.agents.thread_state import ThreadState
from src.ggl.graph.extraction import extract_topics_from_messages
from src.ggl.graph.summarization import build_knowledge_card

# Spec §2.2.1: Legal state transitions table.
_VALID_TRANSITIONS: set[tuple[str, str]] = {
    ("unvisited", "exploring"),
    ("exploring", "mastered"),
    ("exploring", "blurry"),
    ("exploring", "unknown"),
    ("blurry", "mastered"),
    ("blurry", "exploring"),
    ("blurry", "unknown"),
    ("mastered", "exploring"),
    ("mastered", "blurry"),
    ("unknown", "exploring"),
}


def _messages_to_text(messages: list[Any], limit: int = 8) -> list[str]:
    out: list[str] = []
    for msg in messages[-limit:]:
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
            out.append(" ".join(parts).strip())
        else:
            out.append(str(content).strip())
    return [x for x in out if x]


def _get_topic_node(ggl_state: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    graph = ggl_state.get("topic_graph") or {}
    nodes = graph.get("nodes") or []
    for node in nodes:
        if isinstance(node, dict) and node.get("id") == node_id:
            return node
    return None


def _clone_graph(ggl_state: dict[str, Any]) -> dict[str, Any]:
    """Deep-ish copy of topic_graph (each node dict is new)."""
    graph = ggl_state.get("topic_graph") or {}
    nodes = [dict(n) for n in (graph.get("nodes") or []) if isinstance(n, dict)]
    edges = list(graph.get("edges") or [])
    return {"nodes": nodes, "edges": edges}


@tool("update_graph_node", parse_docstring=False)
def update_graph_node(
    runtime: ToolRuntime[ContextT, ThreadState],
    node_id: str,
    new_state: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Update the state of a node in the topic graph.

    Validates the transition against the NodeState machine before applying.

    Args:
        node_id: The ID of the node to update.
        new_state: Target state. One of: unvisited, exploring, mastered, blurry, unknown.
    """
    state = runtime.state or {}
    ggl_state = dict(state.get("ggl") or {})
    node = _get_topic_node(ggl_state, node_id)
    if node is None:
        return Command(
            update={"messages": [ToolMessage(f"Error: node '{node_id}' not found in topic graph", tool_call_id=tool_call_id)]},
        )

    current_state = node.get("state", "unvisited")
    if new_state == current_state:
        payload = json.dumps({"node_id": node_id, "state": new_state, "status": "no_change"}, ensure_ascii=False)
        return Command(update={"messages": [ToolMessage(payload, tool_call_id=tool_call_id)]})

    if (current_state, new_state) not in _VALID_TRANSITIONS:
        valid_targets = ", ".join(t for f, t in _VALID_TRANSITIONS if f == current_state)
        error_msg = (
            f"Error: illegal state transition '{current_state}' -> '{new_state}' for node '{node_id}'. "
            f"Valid targets from '{current_state}': {valid_targets}"
        )
        return Command(update={"messages": [ToolMessage(error_msg, tool_call_id=tool_call_id)]})

    new_graph = _clone_graph(ggl_state)
    for n in new_graph["nodes"]:
        if n.get("id") == node_id:
            n["state"] = new_state
            break

    payload = json.dumps(
        {"node_id": node_id, "old_state": current_state, "new_state": new_state, "status": "ok"},
        ensure_ascii=False,
    )
    return Command(
        update={
            "ggl": {**ggl_state, "topic_graph": new_graph},
            "messages": [ToolMessage(payload, tool_call_id=tool_call_id)],
        },
    )


@tool("create_graph_node", parse_docstring=False)
def create_graph_node(
    runtime: ToolRuntime[ContextT, ThreadState],
    label: str,
    parent_node_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Create a new node in the topic graph and link it to a parent node.

    Used when a Digression introduces a new related sub-topic worth tracking.

    Args:
        label: Human-readable label for the new node.
        parent_node_id: ID of the parent node to link this new node to.
    """
    state = runtime.state or {}
    ggl_state = dict(state.get("ggl") or {})
    if not ggl_state.get("topic_graph"):
        return Command(update={"messages": [ToolMessage("Error: topic graph is empty", tool_call_id=tool_call_id)]})

    parent = _get_topic_node(ggl_state, parent_node_id)
    if parent is None:
        return Command(
            update={"messages": [ToolMessage(f"Error: parent node '{parent_node_id}' not found", tool_call_id=tool_call_id)]},
        )

    new_node_id = f"node_{uuid.uuid4().hex[:8]}"
    new_graph = _clone_graph(ggl_state)
    new_graph["nodes"].append({"id": new_node_id, "label": label, "state": "unvisited"})
    new_graph["edges"].append([parent_node_id, new_node_id])

    digression_stack = list(ggl_state.get("digression_stack") or [])
    active_node_id = ggl_state.get("active_node_id")
    if active_node_id:
        digression_stack.append(active_node_id)

    version = (ggl_state.get("topic_graph_version") or 0) + 1
    updated_ggl = {
        **ggl_state,
        "topic_graph": new_graph,
        "topic_graph_version": version,
        "active_node_id": new_node_id,
        "digression_stack": digression_stack,
    }
    payload = json.dumps(
        {"node_id": new_node_id, "label": label, "parent_node_id": parent_node_id, "status": "ok"},
        ensure_ascii=False,
    )
    return Command(
        update={
            "ggl": updated_ggl,
            "messages": [ToolMessage(payload, tool_call_id=tool_call_id)],
        },
    )


@tool("link_to_existing_node", parse_docstring=False)
def link_to_existing_node(
    runtime: ToolRuntime[ContextT, ThreadState],
    node_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Switch active node to an existing graph node and push current to digression stack.

    Used when a Digression question maps to a node already in the graph.

    Args:
        node_id: ID of the existing node to switch focus to.
    """
    state = runtime.state or {}
    ggl_state = dict(state.get("ggl") or {})
    node = _get_topic_node(ggl_state, node_id)
    if node is None:
        return Command(
            update={"messages": [ToolMessage(f"Error: node '{node_id}' not found in topic graph", tool_call_id=tool_call_id)]},
        )

    digression_stack = list(ggl_state.get("digression_stack") or [])
    active_node_id = ggl_state.get("active_node_id")
    if active_node_id and active_node_id != node_id:
        digression_stack.append(active_node_id)

    updated_ggl = {
        **ggl_state,
        "active_node_id": node_id,
        "digression_stack": digression_stack,
    }
    payload = json.dumps({"node_id": node_id, "label": node.get("label"), "status": "ok"}, ensure_ascii=False)
    return Command(
        update={
            "ggl": updated_ggl,
            "messages": [ToolMessage(payload, tool_call_id=tool_call_id)],
        },
    )


@tool("get_current_path", parse_docstring=False)
def get_current_path(
    runtime: ToolRuntime[ContextT, ThreadState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Get the current learning path and suggest the next recommended node."""
    state = runtime.state or {}
    ggl_state = state.get("ggl") or {}
    current_path = ggl_state.get("current_path") or []
    active_node_id = ggl_state.get("active_node_id")
    graph = ggl_state.get("topic_graph") or {}
    nodes = graph.get("nodes") or []

    node_labels = {n.get("id"): n.get("label") for n in nodes if isinstance(n, dict)}
    path_labels = [node_labels.get(nid, nid) for nid in current_path]

    priority = ["exploring", "blurry", "unknown", "unvisited", "mastered"]
    rank = {name: idx for idx, name in enumerate(priority)}
    sorted_nodes = sorted(
        [n for n in nodes if n.get("id") != active_node_id],
        key=lambda n: rank.get(n.get("state", "mastered"), 999),
    )
    next_node = sorted_nodes[0] if sorted_nodes else None

    payload = {
        "current_path": current_path,
        "path_labels": path_labels,
        "active_node_id": active_node_id,
        "next_suggested_node": (
            {"id": next_node.get("id"), "label": next_node.get("label"), "state": next_node.get("state")}
            if next_node
            else None
        ),
    }
    return Command(update={"messages": [ToolMessage(json.dumps(payload, ensure_ascii=False), tool_call_id=tool_call_id)]})


@tool("extract_knowledge_card", parse_docstring=False)
def extract_knowledge_card(
    runtime: ToolRuntime[ContextT, ThreadState],
    node_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Extract a knowledge card for a node from recent conversation.

    Args:
        node_id: Graph node id to attach the knowledge card to.
    """
    state = runtime.state or {}
    ggl_state = state.get("ggl") or {}
    node = _get_topic_node(ggl_state, node_id)
    if node is None:
        return Command(
            update={"messages": [ToolMessage(f"Error: node '{node_id}' not found in topic graph", tool_call_id=tool_call_id)]},
        )

    recent_text = _messages_to_text(state.get("messages") or [])
    topic_label = str(node.get("label") or node_id)
    card = build_knowledge_card(topic_label=topic_label, recent_messages=recent_text)
    update = {"ggl": {"knowledge_cards": {node_id: card}}}
    return Command(
        update={
            **update,
            "messages": [ToolMessage(json.dumps({"node_id": node_id, "status": "ok"}, ensure_ascii=False), tool_call_id=tool_call_id)],
        },
    )


@tool("suggest_next_node", parse_docstring=False)
def suggest_next_node(
    runtime: ToolRuntime[ContextT, ThreadState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Suggest next node to learn based on current graph state."""
    state = runtime.state or {}
    ggl_state = state.get("ggl") or {}
    graph = ggl_state.get("topic_graph") or {}
    nodes = graph.get("nodes") or []
    if not nodes:
        return Command(update={"messages": [ToolMessage("Error: topic graph is empty", tool_call_id=tool_call_id)]})

    priority = ["exploring", "blurry", "unknown", "unvisited", "mastered"]
    rank = {name: idx for idx, name in enumerate(priority)}
    sorted_nodes = sorted(nodes, key=lambda n: rank.get(n.get("state", "mastered"), 999))
    chosen = sorted_nodes[0]

    payload = {
        "node_id": chosen.get("id"),
        "label": chosen.get("label"),
        "state": chosen.get("state"),
        "reason": "priority_by_state",
        "candidates": extract_topics_from_messages(
            _messages_to_text(state.get("messages") or []),
            [str(n.get("label", "")).strip() for n in nodes if isinstance(n, dict)],
        ),
    }
    return Command(update={"messages": [ToolMessage(json.dumps(payload, ensure_ascii=False), tool_call_id=tool_call_id)]})


GGL_TOOLS = [
    update_graph_node,
    create_graph_node,
    link_to_existing_node,
    get_current_path,
    extract_knowledge_card,
    suggest_next_node,
]
