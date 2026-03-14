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
    """Reducer for GGL state - deep merges knowledge_cards, replaces other fields."""
    if update is None:
        return current
    if current is None:
        return update
    merged = dict(current)
    for k, v in update.items():
        if v is None:
            continue
        if k == "knowledge_cards" and isinstance(v, dict):
            prev = merged.get("knowledge_cards") or {}
            merged["knowledge_cards"] = {**prev, **v}
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
