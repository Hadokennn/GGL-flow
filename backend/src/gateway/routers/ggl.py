"""API for GGL (Graph Guided Learning) operations."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agents.thread_state import ThreadState
from src.gateway.checkpoint_utils import get_checkpoint_tuple

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


def _get_thread_state(thread_id: str) -> ThreadState | None:
    checkpoint_tuple = get_checkpoint_tuple(thread_id)
    if checkpoint_tuple is None:
        return None
    channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
    return channel_values if isinstance(channel_values, dict) else {}


def _check_ggl_permission(thread_id: str, thread_state: ThreadState | None = None) -> ThreadState:
    """Check if thread has GGL enabled.

    Args:
        thread_id: The thread ID.

    Raises:
        HTTPException: 403 if thread is not a GGL thread.
    """
    state = thread_state or _get_thread_state(thread_id)  # type: ignore[assignment]

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
