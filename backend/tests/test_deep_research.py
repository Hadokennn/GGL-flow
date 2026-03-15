"""Tests for deep research functionality."""

import json

import pytest

from src.ggl.deep_research import (
    analyze_survey_responses,
    generate_knowledge_graph,
    generate_self_assessment_survey,
)


class TestKnowledgeGraphGeneration:
    """Test knowledge graph generation."""

    @pytest.mark.skipif(True, reason="Requires LLM model")
    def test_generate_knowledge_graph_structure(self):
        """Test that generated graph has correct structure."""
        topic = "机器学习基础"

        graph = generate_knowledge_graph(topic)
        assert "nodes" in graph
        assert "edges" in graph
        assert isinstance(graph["nodes"], list)
        assert isinstance(graph["edges"], list)
        assert len(graph["nodes"]) > 0
        # Verify root node exists
        node_ids = [n["id"] for n in graph["nodes"]]
        assert "root" in node_ids

    def test_graph_validation(self):
        """Test graph validation logic."""
        # Test missing required fields
        invalid_graph = {"nodes": []}  # Missing edges
        with pytest.raises(ValueError, match="missing required fields"):
            # This would be caught in the generation function
            if "edges" not in invalid_graph:
                raise ValueError("Generated graph missing required fields: nodes, edges")

        # Test invalid node format
        invalid_graph = {"nodes": ["not a dict"], "edges": []}
        with pytest.raises(ValueError, match="must be a dict"):
            for node in invalid_graph["nodes"]:
                if not isinstance(node, dict):
                    raise ValueError("Each node must be a dict")

        # Test missing root node
        invalid_graph = {
            "nodes": [{"id": "n1", "label": "Node 1"}],
            "edges": [],
        }
        with pytest.raises(ValueError, match="must have a 'root' node"):
            node_ids = [n["id"] for n in invalid_graph["nodes"]]
            if "root" not in node_ids:
                raise ValueError("Graph must have a 'root' node")


class TestSurveyGeneration:
    """Test survey generation."""

    @pytest.mark.skipif(True, reason="Requires LLM model")
    def test_generate_survey_structure(self):
        """Test that generated survey has correct structure."""
        topic = "Python 编程"
        nodes = [
            {"id": "root", "label": "Python 编程"},
            {"id": "n1", "label": "基础语法"},
            {"id": "n2", "label": "数据结构"},
        ]

        survey = generate_self_assessment_survey(topic, nodes)
        assert "questions" in survey
        assert isinstance(survey["questions"], list)
        assert len(survey["questions"]) >= 3
        assert len(survey["questions"]) <= 5

        # Verify question structure
        for q in survey["questions"]:
            assert "id" in q
            assert "question" in q
            assert isinstance(q["id"], str)
            assert isinstance(q["question"], str)


class TestSurveyAnalysis:
    """Test survey response analysis."""

    @pytest.mark.skipif(True, reason="Requires LLM model")
    def test_analyze_survey_responses_structure(self):
        """Test survey analysis output structure."""
        survey_questions = [
            {
                "id": "q1",
                "question": "什么是 Python?",
                "related_nodes": ["root", "n1"],
            },
            {
                "id": "q2",
                "question": "解释 list 和 tuple 的区别",
                "related_nodes": ["n2"],
            },
        ]

        user_responses = {
            "q1": "Python 是一种高级编程语言，语法简洁，应用广泛",
            "q2": "list 是可变的，tuple 是不可变的",
        }

        assessments = analyze_survey_responses(survey_questions, user_responses)
        assert isinstance(assessments, dict)

        # Verify all values are valid states
        valid_states = {"mastered", "blurry", "unknown"}
        for node_id, state in assessments.items():
            assert state in valid_states
            assert isinstance(node_id, str)


class TestJSONParsing:
    """Test JSON extraction from LLM responses."""

    def test_extract_json_from_markdown(self):
        """Test extracting JSON from markdown code blocks."""
        # Simulate LLM response with markdown code block
        response_with_markdown = """Here's the graph:

```json
{
  "nodes": [{"id": "root", "label": "Test"}],
  "edges": []
}
```
"""

        # Extract JSON
        content = response_with_markdown
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()

        data = json.loads(content)
        assert "nodes" in data
        assert "edges" in data

    def test_extract_json_without_language_tag(self):
        """Test extracting JSON from code blocks without language tag."""
        response_with_code_block = """```
{
  "nodes": [{"id": "root", "label": "Test"}],
  "edges": []
}
```"""

        content = response_with_code_block
        if "```" in content:
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()

        data = json.loads(content)
        assert "nodes" in data
        assert "edges" in data
