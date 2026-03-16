"""API for thread operations."""

import asyncio
import logging
import shutil

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agents.checkpointer.provider import get_checkpointer
from src.config.paths import get_paths
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


def _delete_thread_sync(thread_id: str) -> None:
    """Delete thread checkpoints and thread directory (sync, run in thread pool)."""
    cp = get_checkpointer()
    if hasattr(cp, "delete_thread"):
        cp.delete_thread(thread_id)
        logger.info("Deleted checkpoints for thread %s", thread_id)
    thread_dir = get_paths().thread_dir(thread_id)
    if thread_dir.exists():
        shutil.rmtree(thread_dir)
        logger.info("Deleted thread dir %s", thread_dir)


@router.delete(
    "/{thread_id}",
    status_code=204,
    summary="Delete Thread",
    description="Delete thread checkpoints and associated files (uploads, outputs).",
)
async def delete_thread(thread_id: str) -> None:
    """Delete a thread and all its data.

    Removes:
    - LangGraph checkpoints (including knowledge-map in ggl channel)
    - Thread directory (uploads, outputs, workspace)

    Args:
        thread_id: The thread ID to delete.

    Raises:
        HTTPException: 404 if thread not found.
    """
    thread_state = _get_thread_state(thread_id)
    if thread_state is None:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")

    await asyncio.to_thread(_delete_thread_sync, thread_id)
