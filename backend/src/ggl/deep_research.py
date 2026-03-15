"""Deep research tool for generating knowledge graphs using LLM."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from src.models.factory import create_chat_model

logger = logging.getLogger(__name__)


GRAPH_GENERATION_PROMPT = """你是一位资深的教学设计专家，擅长将知识主题分解为结构化的学习路径。

用户想学习的主题是：「{topic}」

请为这个主题设计一个完整的知识图谱，包含 8-12 个核心知识节点。

## 设计要求：

1. **节点设计**：
   - 每个节点代表一个可以独立学习和掌握的知识点
   - 节点粒度适中：不要太大（如"全部内容"）也不要太小（如"一个术语"）
   - 标签清晰简洁（5-15 个字）

2. **关系设计**：
   - 前置关系：学习 B 之前必须先掌握 A
   - 并行关系：A 和 B 可以同时学习，互不依赖
   - 进阶关系：掌握 A 后可以深入学习 B

3. **图谱结构**：
   - 必须有一个根节点（root），代表主题本身
   - 建议采用分层结构：基础层 → 核心层 → 进阶层
   - 避免过于复杂的依赖关系，确保学习路径清晰

## 输出格式（JSON）：

{{
  "nodes": [
    {{"id": "root", "label": "{topic}", "layer": "root"}},
    {{"id": "basic_1", "label": "基础概念", "layer": "basic"}},
    {{"id": "core_1", "label": "核心原理", "layer": "core"}},
    {{"id": "advanced_1", "label": "进阶应用", "layer": "advanced"}}
  ],
  "edges": [
    ["root", "basic_1"],
    ["basic_1", "core_1"],
    ["core_1", "advanced_1"]
  ],
  "metadata": {{
    "total_nodes": 10,
    "estimated_hours": 20,
    "difficulty": "intermediate",
    "description": "简要描述这个学习路径的特点"
  }}
}}

注意：
- nodes 数组中 id 必须唯一
- edges 数组中每个元素是 [source_id, target_id]
- layer 可以是：root, basic, core, advanced
- 只输出 JSON，不要额外的解释文字
"""


SURVEY_GENERATION_PROMPT = """你是一位资深的教育评估专家，擅长设计诊断性评估问题。

学习主题：「{topic}」

知识图谱节点：
{nodes_summary}

请为这个主题设计 3-5 个开放式自评问题，用于评估学习者对该主题的掌握程度。

## 问题设计要求：

1. **覆盖核心节点**：问题应该涵盖图谱中的关键知识点
2. **区分度高**：能够区分"完全不懂"、"模糊理解"和"深入掌握"三个层次
3. **开放式提问**：避免是非题，鼓励学习者展开描述
4. **场景化**：尽可能结合实际应用场景

## 输出格式（JSON）：

{{
  "questions": [
    {{
      "id": "q1",
      "question": "请简要解释一下XXX的核心概念",
      "related_nodes": ["node_1", "node_2"],
      "evaluation_hints": {{
        "mastered": "能清晰准确地解释概念，并举出恰当例子",
        "blurry": "能说出大概意思，但理解不够深入或有混淆",
        "unknown": "完全不了解或无法解释"
      }}
    }}
  ]
}}

注意：
- questions 数组包含 3-5 个问题
- related_nodes 关联到图谱中的节点 ID
- evaluation_hints 提供三个层次的判断标准
- 只输出 JSON，不要额外的解释文字
"""


def generate_knowledge_graph(topic: str, model_name: str | None = None) -> dict[str, Any]:
    """
    使用 LLM 生成知识图谱。

    Args:
        topic: 学习主题
        model_name: 使用的模型名称（可选，默认使用配置的默认模型）

    Returns:
        包含 nodes, edges, metadata 的字典

    Raises:
        ValueError: 如果 LLM 返回无效的 JSON 或格式不正确
    """
    try:
        model = create_chat_model(model_name)
        prompt = ChatPromptTemplate.from_template(GRAPH_GENERATION_PROMPT)

        chain = prompt | model
        response = chain.invoke({"topic": topic})

        # 提取内容
        content = response.content if hasattr(response, "content") else str(response)

        # 尝试从 markdown 代码块中提取 JSON
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()
        elif "```" in content:
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()

        # 解析 JSON
        graph_data = json.loads(content)

        # 验证必需字段
        if "nodes" not in graph_data or "edges" not in graph_data:
            raise ValueError("Generated graph missing required fields: nodes, edges")

        # 验证节点格式
        if not isinstance(graph_data["nodes"], list):
            raise ValueError("nodes must be a list")

        for node in graph_data["nodes"]:
            if not isinstance(node, dict):
                raise ValueError("Each node must be a dict")
            if "id" not in node or "label" not in node:
                raise ValueError("Each node must have 'id' and 'label'")

        # 验证边格式
        if not isinstance(graph_data["edges"], list):
            raise ValueError("edges must be a list")

        for edge in graph_data["edges"]:
            if not isinstance(edge, list) or len(edge) != 2:
                raise ValueError("Each edge must be a [source, target] list")

        # 验证根节点存在
        node_ids = [n["id"] for n in graph_data["nodes"]]
        if "root" not in node_ids:
            raise ValueError("Graph must have a 'root' node")

        logger.info(f"Generated knowledge graph for '{topic}' with {len(graph_data['nodes'])} nodes")
        return graph_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Response content: {content[:500]}...")
        raise ValueError(f"LLM returned invalid JSON: {e}") from e
    except Exception as e:
        logger.error(f"Failed to generate knowledge graph: {e}")
        raise


def generate_self_assessment_survey(topic: str, nodes: list[dict], model_name: str | None = None) -> dict[str, Any]:
    """
    根据知识图谱生成自评问卷。

    Args:
        topic: 学习主题
        nodes: 图谱节点列表
        model_name: 使用的模型名称（可选）

    Returns:
        包含 questions 的字典

    Raises:
        ValueError: 如果 LLM 返回无效的 JSON 或格式不正确
    """
    try:
        model = create_chat_model(model_name)
        prompt = ChatPromptTemplate.from_template(SURVEY_GENERATION_PROMPT)

        # 生成节点摘要
        nodes_summary = "\n".join([f"- {node['id']}: {node['label']}" for node in nodes])

        chain = prompt | model
        response = chain.invoke({"topic": topic, "nodes_summary": nodes_summary})

        # 提取内容
        content = response.content if hasattr(response, "content") else str(response)

        # 尝试从 markdown 代码块中提取 JSON
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()
        elif "```" in content:
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()

        # 解析 JSON
        survey_data = json.loads(content)

        # 验证必需字段
        if "questions" not in survey_data:
            raise ValueError("Generated survey missing required field: questions")

        # 验证问题格式
        if not isinstance(survey_data["questions"], list):
            raise ValueError("questions must be a list")

        for question in survey_data["questions"]:
            if not isinstance(question, dict):
                raise ValueError("Each question must be a dict")
            if "id" not in question or "question" not in question:
                raise ValueError("Each question must have 'id' and 'question'")

        logger.info(f"Generated {len(survey_data['questions'])} survey questions for '{topic}'")
        return survey_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Response content: {content[:500]}...")
        raise ValueError(f"LLM returned invalid JSON: {e}") from e
    except Exception as e:
        logger.error(f"Failed to generate survey: {e}")
        raise


def analyze_survey_responses(
    survey_questions: list[dict], user_responses: dict[str, str], model_name: str | None = None
) -> dict[str, str]:
    """
    分析用户的自评回答，判断每个相关节点的掌握程度。

    Args:
        survey_questions: 问卷问题列表
        user_responses: 用户回答字典 {question_id: response_text}
        model_name: 使用的模型名称（可选）

    Returns:
        节点掌握程度字典 {node_id: state}，state 为 "mastered"/"blurry"/"unknown"

    Raises:
        ValueError: 如果 LLM 返回无效的 JSON
    """
    analysis_prompt = """你是一位教育评估专家，请根据学习者的回答判断他们对相关知识点的掌握程度。

问卷问题和用户回答：
{qa_pairs}

评估标准：
- mastered: 回答准确、全面，展示了深入理解
- blurry: 有一定理解但不够深入，存在模糊或错误
- unknown: 完全不了解，无法回答或答非所问

请输出 JSON 格式的评估结果：

{{
  "assessments": [
    {{"node_id": "node_1", "state": "mastered", "reason": "回答准确且有深度"}},
    {{"node_id": "node_2", "state": "blurry", "reason": "理解不够深入"}}
  ]
}}

只输出 JSON，不要额外文字。
"""

    try:
        model = create_chat_model(model_name)

        # 构建问答对
        qa_pairs = []
        for q in survey_questions:
            q_id = q["id"]
            question_text = q["question"]
            user_answer = user_responses.get(q_id, "[未回答]")
            related_nodes = q.get("related_nodes", [])
            qa_pairs.append(
                f"问题 {q_id}: {question_text}\n" f"关联节点: {', '.join(related_nodes)}\n" f"用户回答: {user_answer}\n"
            )

        qa_text = "\n".join(qa_pairs)

        response = model.invoke(analysis_prompt.format(qa_pairs=qa_text))
        content = response.content if hasattr(response, "content") else str(response)

        # 提取 JSON
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()
        elif "```" in content:
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()

        result = json.loads(content)

        # 转换为节点状态字典
        node_states = {}
        for assessment in result.get("assessments", []):
            node_id = assessment.get("node_id")
            state = assessment.get("state")
            if node_id and state in ["mastered", "blurry", "unknown"]:
                node_states[node_id] = state

        logger.info(f"Analyzed {len(user_responses)} responses, assessed {len(node_states)} nodes")
        return node_states

    except Exception as e:
        logger.error(f"Failed to analyze survey responses: {e}")
        raise
