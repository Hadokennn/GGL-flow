"""Shared checkpoint utilities for updating LangGraph state from outside the graph."""

import logging
from typing import Any

from langgraph.checkpoint.base import copy_checkpoint, create_checkpoint

from src.agents.checkpointer.provider import get_checkpointer

logger = logging.getLogger(__name__)


def get_checkpoint_tuple(thread_id: str):
    """Get checkpoint tuple for a thread."""
    checkpointer = get_checkpointer()
    return checkpointer.get_tuple({"configurable": {"thread_id": thread_id}})


def persist_partial_state(thread_id: str, partial_state: dict[str, Any]) -> None:
    """Persist partial ThreadState fields as a new checkpoint.

    Args:
        thread_id: The thread ID.
        partial_state: Partial state dict to merge into the checkpoint.

    Raises:
        ValueError: If the thread is not found.
    """
    checkpoint_tuple = get_checkpoint_tuple(thread_id)
    if checkpoint_tuple is None:
        raise ValueError(f"Thread '{thread_id}' not found")

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
    logger.debug("Persisted partial state for thread %s: keys=%s", thread_id, list(partial_state))
