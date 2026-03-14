"""API for GGL (Graph Guided Learning) operations."""

import logging

from fastapi import APIRouter, HTTPException
from langgraph.checkpoint.base import copy_checkpoint, create_checkpoint
from pydantic import BaseModel, Field

from src.agents.checkpointer.provider import get_checkpointer
from src.agents.thread_state import ThreadState

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/threads", tags=["ggl"])


class GGLGraphResponse(BaseModel):
    """Response model for GGL graph."""

    active_node_id: str | None = Field(default=None, description="Currently active node ID")
    topic_graph: dict | None = Field(default=None, description="Topic graph structure")
    topic_graph_version: int | None = Field(default=None, description="Graph version for conflict detection")
    digression_stack: list | None = Field(default=None, description="Stack of digression paths")
    current_path: list[str] | None = Field(default=None, description="Current learning path")
    knowledge_cards: dict | None = Field(default=None, description="Knowledge cards by node ID")


class ActiveNodeUpdate(BaseModel):
    """Request body for updating active node."""

    node_id: str = Field(..., description="Node ID to set as active")


class ActiveNodeResponse(BaseModel):
    """Response after updating active node."""

    active_node_id: str = Field(..., description="Updated active node ID")
    topic_graph_version: int | None = Field(default=None, description="Current graph version")


def _get_checkpoint_tuple(thread_id: str):
    checkpointer = get_checkpointer()
    return checkpointer.get_tuple({"configurable": {"thread_id": thread_id}})


def _get_thread_state(thread_id: str) -> ThreadState | None:
    """Get thread state from checkpointer.

    Args:
        thread_id: The thread ID.

    Returns:
        ThreadState from checkpointer, or None if thread not found.

    Raises:
        HTTPException: 404 if thread not found.
    """
    checkpoint_tuple = _get_checkpoint_tuple(thread_id)
    if checkpoint_tuple is None:
        return None
    channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
    return channel_values if isinstance(channel_values, dict) else {}


def _persist_partial_state(thread_id: str, partial_state: dict) -> None:
    """Persist partial ThreadState fields through checkpointer as a new checkpoint."""
    checkpoint_tuple = _get_checkpoint_tuple(thread_id)
    if checkpoint_tuple is None:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")

    base_checkpoint = copy_checkpoint(checkpoint_tuple.checkpoint)
    merged_values = dict(base_checkpoint.get("channel_values", {}))
    merged_values.update(partial_state)
    base_checkpoint["channel_values"] = merged_values

    base_metadata = dict(checkpoint_tuple.metadata or {})
    prev_step = base_metadata.get("step")
    step = prev_step + 1 if isinstance(prev_step, int) else 1
    new_checkpoint = create_checkpoint(base_checkpoint, channels=None, step=step)
    new_metadata = {
        **base_metadata,
        "source": "update",
        "step": step,
        "writes": partial_state,
    }

    checkpointer = get_checkpointer()
    checkpointer.put(
        checkpoint_tuple.config,
        new_checkpoint,
        new_metadata,
        {},
    )


def _check_ggl_permission(thread_id: str, thread_state: ThreadState | None = None) -> ThreadState:
    """Check if thread has GGL enabled.

    Args:
        thread_id: The thread ID.

    Raises:
        HTTPException: 403 if thread is not a GGL thread.
    """
    state = thread_state or _get_thread_state(thread_id)

    if state is None:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")

    agent_variant = state.get("agent_variant") or "default"

    if agent_variant != "ggl":
        raise HTTPException(
            status_code=403,
            detail="GGL operations are only available for threads with agent_variant='ggl'",
        )
    return state


@router.get(
    "/{thread_id}/ggl/graph",
    response_model=GGLGraphResponse,
    summary="Get GGL Graph",
    description="Get the current topic graph for a GGL thread.",
)
async def get_ggl_graph(thread_id: str) -> GGLGraphResponse:
    """Get GGL graph for a thread.

    Args:
        thread_id: The thread ID.

    Returns:
        GGL graph data.

    Raises:
        HTTPException: 403 if thread is not a GGL thread.
    """
    thread_state = _check_ggl_permission(thread_id)
    ggl_state = thread_state.get("ggl")

    if ggl_state is None:
        return GGLGraphResponse()

    return GGLGraphResponse(
        active_node_id=ggl_state.get("active_node_id"),
        topic_graph=ggl_state.get("topic_graph"),
        topic_graph_version=ggl_state.get("topic_graph_version"),
        digression_stack=ggl_state.get("digression_stack"),
        current_path=ggl_state.get("current_path"),
        knowledge_cards=ggl_state.get("knowledge_cards"),
    )


@router.put(
    "/{thread_id}/ggl/active-node",
    response_model=ActiveNodeResponse,
    summary="Set Active Node",
    description="Set the active node in the topic graph (double-click in Canvas).",
)
async def set_active_node(thread_id: str, request: ActiveNodeUpdate) -> ActiveNodeResponse:
    """Set active node for a GGL thread.

    Args:
        thread_id: The thread ID.
        request: The node ID to set as active.

    Returns:
        Updated active node info.

    Raises:
        HTTPException: 403 if thread is not a GGL thread, 404 if node not found.
    """
    thread_state = _check_ggl_permission(thread_id)
    ggl_state = dict(thread_state.get("ggl") or {})

    topic_graph = ggl_state.get("topic_graph")
    if topic_graph:
        nodes = topic_graph.get("nodes", [])
        node_ids = [n["id"] for n in nodes]
        if request.node_id not in node_ids:
            raise HTTPException(status_code=404, detail=f"Node '{request.node_id}' not found in graph")

    ggl_state["active_node_id"] = request.node_id
    _persist_partial_state(thread_id, {"ggl": ggl_state})

    return ActiveNodeResponse(
        active_node_id=request.node_id,
        topic_graph_version=ggl_state.get("topic_graph_version"),
    )
