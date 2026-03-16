from typing import Annotated, Literal, NotRequired, TypedDict

from langchain.agents import AgentState


class SandboxState(TypedDict):
    sandbox_id: NotRequired[str | None]


class ThreadDataState(TypedDict):
    workspace_path: NotRequired[str | None]
    uploads_path: NotRequired[str | None]
    outputs_path: NotRequired[str | None]


class ViewedImageData(TypedDict):
    base64: str
    mime_type: str


NodeState = Literal["unvisited", "exploring", "mastered", "blurry", "unknown"]


class TopicNode(TypedDict):
    id: str
    label: str
    state: NodeState


class TopicGraph(TypedDict):
    nodes: list[TopicNode]
    edges: list[list[str]]


class KnowledgeCard(TypedDict):
    summary: str
    keyPoints: list[str]
    examples: list[str]
    commonMistakes: list[str]
    relatedConcepts: list[str]


class GGLState(TypedDict):
    active_node_id: NotRequired[str | None]
    topic_graph: NotRequired[TopicGraph | None]
    topic_graph_version: NotRequired[int | None]
    digression_stack: NotRequired[list | None]
    current_path: NotRequired[list[str] | None]
    knowledge_cards: NotRequired[dict[str, KnowledgeCard] | None]
    # Node IDs whose knowledge card is pending background generation.
    # Set by update_ggl_graph when a node is newly marked mastered.
    # Cleared by GGLMiddleware.after_agent after enqueuing background tasks.
    pending_card_node_ids: NotRequired[list[str] | None]
    # Node IDs for which a knowledge card has been successfully generated.
    # Used by the frontend to show the card preview icon on mastered nodes.
    knowledge_card_node_ids: NotRequired[list[str] | None]


def merge_artifacts(existing: list[str] | None, new: list[str] | None) -> list[str]:
    """Reducer for artifacts list - merges and deduplicates artifacts."""
    if existing is None:
        return new or []
    if new is None:
        return existing
    return list(dict.fromkeys(existing + new))


def merge_viewed_images(existing: dict[str, ViewedImageData] | None, new: dict[str, ViewedImageData] | None) -> dict[str, ViewedImageData]:
    """Reducer for viewed_images dict - merges image dictionaries.

    Special case: If new is an empty dict {}, it clears the existing images.
    This allows middlewares to clear the viewed_images state after processing.
    """
    if existing is None:
        return new or {}
    if new is None:
        return existing
    if len(new) == 0:
        return {}
    return {**existing, **new}


def agent_variant_reducer(current: str | None, update: str | None) -> str | None:
    """Reducer for agent_variant - once set, cannot be changed."""
    if current is not None:
        return current
    return update


def ggl_reducer(current: GGLState | None, update: GGLState | None) -> GGLState | None:
    """Reducer for GGL state.

    - knowledge_cards: deep-merged (new cards added, existing preserved)
    - pending_card_node_ids: empty list [] clears the field (signals "all done")
    - other fields: replaced when not None
    """
    if update is None:
        return current
    if current is None:
        return update
    merged = dict(current)
    for k, v in update.items():
        if k == "knowledge_cards":
            if isinstance(v, dict):
                prev = merged.get("knowledge_cards") or {}
                merged["knowledge_cards"] = {**prev, **v}
            continue
        if k == "pending_card_node_ids":
            # Empty list explicitly clears; None means "no change"
            if v is not None:
                merged["pending_card_node_ids"] = v if v else None
            continue
        if k == "knowledge_card_node_ids":
            # Append-only merge; None means "no change"
            if isinstance(v, list):
                prev = merged.get("knowledge_card_node_ids") or []
                merged["knowledge_card_node_ids"] = list(dict.fromkeys(prev + v))
            continue
        if v is None:
            continue
        merged[k] = v
    return merged


class ThreadState(AgentState):
    sandbox: NotRequired[SandboxState | None]
    thread_data: NotRequired[ThreadDataState | None]
    title: NotRequired[str | None]
    artifacts: Annotated[list[str], merge_artifacts]
    todos: NotRequired[list | None]
    uploaded_files: NotRequired[list[dict] | None]
    viewed_images: Annotated[dict[str, ViewedImageData], merge_viewed_images]
    agent_variant: Annotated[str | None, agent_variant_reducer]
    ggl: Annotated[GGLState | None, ggl_reducer]
