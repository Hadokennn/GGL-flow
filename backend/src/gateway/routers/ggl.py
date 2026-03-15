"""API for GGL (Graph Guided Learning) operations."""

import logging

from fastapi import APIRouter, HTTPException
from langgraph.checkpoint.base import copy_checkpoint, create_checkpoint
from pydantic import BaseModel, Field

from src.agents.checkpointer.provider import get_checkpointer
from src.agents.thread_state import ThreadState
from src.ggl.deep_research import (
    analyze_survey_responses,
    generate_knowledge_graph,
    generate_self_assessment_survey,
)

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


class KnowledgeCardResponse(BaseModel):
    node_id: str = Field(..., description="Node ID")
    knowledge_card: dict = Field(..., description="Knowledge card payload")


class InitGraphRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="Learning topic")
    expected_version: int | None = Field(default=None, description="Optional expected graph version for optimistic concurrency")
    use_llm: bool = Field(default=True, description="Use LLM to generate graph (True) or use hardcoded template (False)")
    model_name: str | None = Field(default=None, description="LLM model name for graph generation")


class InitGraphResponse(BaseModel):
    topic_graph: dict = Field(..., description="Initialized topic graph")
    topic_graph_version: int = Field(..., description="Current topic graph version")
    survey: dict | None = Field(default=None, description="Self-assessment survey questions")


class SurveyItem(BaseModel):
    node_id: str = Field(..., description="Node ID")
    state: str = Field(..., description="Node state after survey")


class SurveyRequest(BaseModel):
    assessments: list[SurveyItem] = Field(default_factory=list)
    expected_version: int | None = Field(default=None, description="Expected current graph version for optimistic concurrency")


class SurveyAnswersRequest(BaseModel):
    """Request body for submitting survey answers."""

    responses: dict[str, str] = Field(..., description="User responses to survey questions {question_id: answer_text}")
    expected_version: int | None = Field(default=None, description="Expected current graph version")


class SurveyAnswersResponse(BaseModel):
    """Response after analyzing survey answers."""

    topic_graph: dict = Field(..., description="Updated topic graph with assessed node states")
    topic_graph_version: int = Field(..., description="Updated topic graph version")
    assessments: dict[str, str] = Field(..., description="Node assessments {node_id: state}")


class SurveyResponse(BaseModel):
    topic_graph: dict = Field(..., description="Updated topic graph")
    topic_graph_version: int = Field(..., description="Updated topic graph version")


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


def _build_initial_topic_graph(topic: str, use_llm: bool = True, model_name: str | None = None) -> tuple[dict, dict | None]:
    """
    Build initial topic graph.

    Args:
        topic: Learning topic
        use_llm: Use LLM to generate graph (True) or use hardcoded template (False)
        model_name: LLM model name for generation

    Returns:
        Tuple of (topic_graph, survey_data)
        - topic_graph: Graph structure with nodes and edges
        - survey_data: Survey questions (None if use_llm=False)

    Raises:
        ValueError: If LLM generation fails
    """
    if not use_llm:
        # 旧的硬编码逻辑（保留作为后备方案）
        seed = topic.strip()
        subtopics = [
            f"{seed} - 核心概念",
            f"{seed} - 关键术语",
            f"{seed} - 基础原理",
            f"{seed} - 常见误区",
            f"{seed} - 典型实践",
            f"{seed} - 进阶方向",
        ]
        nodes = [{"id": "root", "label": seed, "state": "exploring"}]
        edges: list[list[str]] = []
        for i, label in enumerate(subtopics, start=1):
            node_id = f"n{i}"
            nodes.append({"id": node_id, "label": label, "state": "unvisited"})
            edges.append(["root", node_id])
        return {"nodes": nodes, "edges": edges}, None

    # 使用 LLM 生成知识图谱
    try:
        logger.info(f"Generating knowledge graph for topic '{topic}' using LLM")
        graph_data = generate_knowledge_graph(topic, model_name)

        # 转换为 GGL 格式（添加 state 字段）
        nodes = []
        for node in graph_data["nodes"]:
            ggl_node = {
                "id": node["id"],
                "label": node["label"],
                "state": "exploring" if node["id"] == "root" else "unvisited",
            }
            # 保留额外字段（如 layer）
            for key in node:
                if key not in ["id", "label", "state"]:
                    ggl_node[key] = node[key]
            nodes.append(ggl_node)

        topic_graph = {"nodes": nodes, "edges": graph_data["edges"]}

        # 生成自评问卷
        logger.info("Generating self-assessment survey")
        survey_data = generate_self_assessment_survey(topic, nodes, model_name)

        return topic_graph, survey_data

    except Exception as e:
        logger.error(f"LLM graph generation failed: {e}, falling back to hardcoded template")
        # 失败时回退到硬编码逻辑
        return _build_initial_topic_graph(topic, use_llm=False, model_name=None)


def _assert_version(expected_version: int | None, current_version: int | None) -> None:
    if expected_version is None:
        return
    current = current_version or 0
    if expected_version != current:
        raise HTTPException(
            status_code=409,
            detail={"message": "topic_graph_version conflict", "current_version": current},
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


@router.get(
    "/{thread_id}/ggl/knowledge-card/{node_id}",
    response_model=KnowledgeCardResponse,
    summary="Get Knowledge Card",
    description="Get knowledge card for a specific node in a GGL thread.",
)
async def get_knowledge_card(thread_id: str, node_id: str) -> KnowledgeCardResponse:
    thread_state = _check_ggl_permission(thread_id)
    ggl_state = thread_state.get("ggl") or {}
    cards = ggl_state.get("knowledge_cards") or {}
    card = cards.get(node_id)
    if not isinstance(card, dict):
        raise HTTPException(status_code=404, detail=f"Knowledge card for node '{node_id}' not found")
    return KnowledgeCardResponse(node_id=node_id, knowledge_card=card)


@router.post(
    "/{thread_id}/ggl/init",
    response_model=InitGraphResponse,
    summary="Initialize topic graph",
    description="Initialize a topic graph for GGL thread from a topic name. Optionally uses LLM for intelligent graph generation.",
)
async def init_ggl_graph(thread_id: str, request: InitGraphRequest) -> InitGraphResponse:
    thread_state = _check_ggl_permission(thread_id)
    ggl_state = dict(thread_state.get("ggl") or {})
    current_version = ggl_state.get("topic_graph_version") or 0
    _assert_version(request.expected_version, current_version)

    try:
        topic_graph, survey_data = _build_initial_topic_graph(
            request.topic, use_llm=request.use_llm, model_name=request.model_name
        )
    except Exception as e:
        logger.error(f"Failed to build topic graph: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate topic graph: {str(e)}")

    next_version = current_version + 1
    ggl_state.update(
        {
            "topic_graph": topic_graph,
            "topic_graph_version": next_version,
            "active_node_id": "root",
            "current_path": ["root"],
            "digression_stack": [],
        }
    )

    # 存储问卷数据（如果有）
    if survey_data:
        ggl_state["survey_data"] = survey_data

    _persist_partial_state(thread_id, {"ggl": ggl_state})
    return InitGraphResponse(topic_graph=topic_graph, topic_graph_version=next_version, survey=survey_data)


@router.post(
    "/{thread_id}/ggl/survey",
    response_model=SurveyResponse,
    summary="Apply survey results",
    description="Update node states according to survey/self-assessment.",
)
async def survey_ggl_graph(thread_id: str, request: SurveyRequest) -> SurveyResponse:
    thread_state = _check_ggl_permission(thread_id)
    ggl_state = dict(thread_state.get("ggl") or {})
    topic_graph = ggl_state.get("topic_graph")
    if not isinstance(topic_graph, dict):
        raise HTTPException(status_code=400, detail="topic_graph is empty, initialize first")

    current_version = ggl_state.get("topic_graph_version") or 0
    _assert_version(request.expected_version, current_version)

    nodes = topic_graph.get("nodes") or []
    index_by_id = {str(node.get("id")): idx for idx, node in enumerate(nodes) if isinstance(node, dict)}
    allowed_states = {"unvisited", "exploring", "mastered", "blurry", "unknown"}

    for item in request.assessments:
        if item.node_id not in index_by_id:
            raise HTTPException(status_code=404, detail=f"Node '{item.node_id}' not found in graph")
        if item.state not in allowed_states:
            raise HTTPException(status_code=400, detail=f"Invalid state '{item.state}'")
        nodes[index_by_id[item.node_id]]["state"] = item.state

    topic_graph["nodes"] = nodes
    next_version = current_version + 1
    ggl_state.update(
        {
            "topic_graph": topic_graph,
            "topic_graph_version": next_version,
        }
    )
    _persist_partial_state(thread_id, {"ggl": ggl_state})
    return SurveyResponse(topic_graph=topic_graph, topic_graph_version=next_version)


@router.post(
    "/{thread_id}/ggl/survey-answers",
    response_model=SurveyAnswersResponse,
    summary="Submit survey answers",
    description="Submit answers to self-assessment survey and automatically update node states based on LLM analysis.",
)
async def submit_survey_answers(thread_id: str, request: SurveyAnswersRequest) -> SurveyAnswersResponse:
    """
    Analyze user's survey answers and update node states.

    This endpoint:
    1. Retrieves the survey questions from ggl_state
    2. Analyzes user responses using LLM
    3. Updates node states based on the analysis
    4. Returns the updated graph
    """
    thread_state = _check_ggl_permission(thread_id)
    ggl_state = dict(thread_state.get("ggl") or {})

    # 获取 survey 数据
    survey_data = ggl_state.get("survey_data")
    if not survey_data or "questions" not in survey_data:
        raise HTTPException(status_code=400, detail="No survey data found. Initialize graph with use_llm=True first.")

    # 获取 topic_graph
    topic_graph = ggl_state.get("topic_graph")
    if not isinstance(topic_graph, dict):
        raise HTTPException(status_code=400, detail="topic_graph is empty, initialize first")

    current_version = ggl_state.get("topic_graph_version") or 0
    _assert_version(request.expected_version, current_version)

    try:
        # 使用 LLM 分析回答
        logger.info(f"Analyzing survey responses for thread {thread_id}")
        node_assessments = analyze_survey_responses(survey_data["questions"], request.responses)

        # 更新节点状态
        nodes = topic_graph.get("nodes") or []
        index_by_id = {str(node.get("id")): idx for idx, node in enumerate(nodes) if isinstance(node, dict)}

        for node_id, state in node_assessments.items():
            if node_id in index_by_id:
                nodes[index_by_id[node_id]]["state"] = state
                logger.info(f"Updated node {node_id} to state {state}")

        topic_graph["nodes"] = nodes
        next_version = current_version + 1

        ggl_state.update(
            {
                "topic_graph": topic_graph,
                "topic_graph_version": next_version,
            }
        )

        _persist_partial_state(thread_id, {"ggl": ggl_state})

        return SurveyAnswersResponse(
            topic_graph=topic_graph, topic_graph_version=next_version, assessments=node_assessments
        )

    except Exception as e:
        logger.error(f"Failed to analyze survey responses: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze survey responses: {str(e)}")
