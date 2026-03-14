"""API for thread operations."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.gateway.routers.ggl import _get_thread_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/threads", tags=["threads"])


class ThreadInfoResponse(BaseModel):
    """Response model for thread info."""

    thread_id: str = Field(..., description="Thread ID")
    agent_variant: str | None = Field(default=None, description="Agent variant (default, ggl, etc.)")


@router.get(
    "/{thread_id}/info",
    response_model=ThreadInfoResponse,
    summary="Get Thread Info",
    description="Get basic thread information including agent variant.",
)
async def get_thread_info(thread_id: str) -> ThreadInfoResponse:
    """Get thread info.

    Args:
        thread_id: The thread ID.

    Returns:
        Thread info including agent_variant.

    Raises:
        HTTPException: 404 if thread not found.
    """
    thread_state = _get_thread_state(thread_id)
    if thread_state is None:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")

    return ThreadInfoResponse(
        thread_id=thread_id,
        agent_variant=thread_state.get("agent_variant"),
    )
