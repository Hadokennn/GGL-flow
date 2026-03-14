"""API for GGL (Graph Guided Learning) operations."""

import logging

from fastapi import APIRouter, HTTPException
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


_ggl_states: dict[str, dict] = {}


def _get_thread_state(thread_id: str) -> ThreadState | None:
    """Get thread state from checkpointer.

    Args:
        thread_id: The thread ID.

    Returns:
        ThreadState from checkpointer, or None if thread not found.

    Raises:
        HTTPException: 404 if thread not found.
    """
    checkpointer = get_checkpointer()
    config = {"configurable": {"thread_id": thread_id}}

    checkpoint = checkpointer.get(config)
    if checkpoint is None:
        return None

    return checkpoint.metadata.get("thread_state") if checkpoint.metadata else None


def _get_ggl_state_from_storage(thread_id: str) -> dict | None:
    """Get GGL state for a thread (in-memory for Phase 1).

    Args:
        thread_id: The thread ID.

    Returns:
        GGL state dict if exists.
    """
    return _ggl_states.get(thread_id)


def _set_ggl_state_to_storage(thread_id: str, state: dict) -> None:
    """Set GGL state for a thread (in-memory for Phase 1).

    Args:
        thread_id: The thread ID.
        state: The GGL state to set.
    """
    _ggl_states[thread_id] = state


def _check_ggl_permission(thread_id: str) -> None:
    """Check if thread has GGL enabled.

    Args:
        thread_id: The thread ID.

    Raises:
        HTTPException: 403 if thread is not a GGL thread.
    """
    thread_state = _get_thread_state(thread_id)

    if thread_state is None:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")

    agent_variant = thread_state.get("agent_variant")

    if agent_variant != "ggl":
        raise HTTPException(
            status_code=403,
            detail="GGL operations are only available for threads with agent_variant='ggl'",
        )


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
    _check_ggl_permission(thread_id)

    ggl_state = _get_ggl_state_from_storage(thread_id)

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
    _check_ggl_permission(thread_id)

    ggl_state = _get_ggl_state_from_storage(thread_id) or {}

    topic_graph = ggl_state.get("topic_graph")
    if topic_graph:
        nodes = topic_graph.get("nodes", [])
        node_ids = [n["id"] for n in nodes]
        if request.node_id not in node_ids:
            raise HTTPException(status_code=404, detail=f"Node '{request.node_id}' not found in graph")

    ggl_state["active_node_id"] = request.node_id
    _set_ggl_state_to_storage(thread_id, ggl_state)

    return ActiveNodeResponse(
        active_node_id=request.node_id,
        topic_graph_version=ggl_state.get("topic_graph_version"),
    )
