"""Background queue for knowledge card generation."""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeCardTask:
    thread_id: str
    node_id: str
    node_label: str
    messages: list[Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class KnowledgeCardQueue:
    """Immediate background queue for knowledge card generation.

    Each task spawns a dedicated daemon thread. Duplicate (thread_id, node_id)
    tasks that arrive while processing is in progress are silently dropped.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._processing: set[str] = set()

    def add(
        self,
        thread_id: str,
        node_id: str,
        node_label: str,
        messages: list[Any],
    ) -> None:
        key = f"{thread_id}:{node_id}"
        with self._lock:
            if key in self._processing:
                logger.debug("Knowledge card already in-flight for %s, skip", key)
                return
            self._processing.add(key)

        task = KnowledgeCardTask(
            thread_id=thread_id,
            node_id=node_id,
            node_label=node_label,
            messages=list(messages),
        )
        t = threading.Thread(target=self._process, args=(task,), daemon=True)
        t.start()
        logger.info("Knowledge card task enqueued: %s / %s", thread_id, node_id)

    def _process(self, task: KnowledgeCardTask) -> None:
        from src.agents.knowledge_card.processor import KnowledgeCardProcessor  # noqa: PLC0415

        key = f"{task.thread_id}:{task.node_id}"
        try:
            processor = KnowledgeCardProcessor()
            processor.generate(
                thread_id=task.thread_id,
                node_id=task.node_id,
                node_label=task.node_label,
                messages=task.messages,
            )
        except Exception as e:
            logger.error("Knowledge card task failed for %s: %s", key, e)
        finally:
            with self._lock:
                self._processing.discard(key)

    @property
    def in_flight_count(self) -> int:
        with self._lock:
            return len(self._processing)


_kc_queue: KnowledgeCardQueue | None = None
_kc_lock = threading.Lock()


def get_knowledge_card_queue() -> KnowledgeCardQueue:
    global _kc_queue
    with _kc_lock:
        if _kc_queue is None:
            _kc_queue = KnowledgeCardQueue()
        return _kc_queue
