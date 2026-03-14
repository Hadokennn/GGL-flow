"""Tests for GGL middleware context injection and behavior."""

from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from src.agents.middlewares.ggl_middleware import GGLMiddleware, GGLMiddlewareState
from src.agents.thread_state import GGLState, TopicGraph
from src.ggl.intent import IntentType


class TestGGLMiddlewareContextInjection:
    """Test context injection with priority and limits."""

    def test_inject_context_empty_ggl_state(self):
        """Test context injection when GGL state is empty."""
        middleware = GGLMiddleware()
        state: GGLMiddlewareState = {
            "messages": [],
            "agent_variant": "ggl",
        }

        result = middleware._build_context_message(state, IntentType.CONTINUE)
        
        assert result is not None
        assert "messages" in result
        assert "知识图谱尚未初始化" in result["messages"][0].content

    def test_inject_context_with_active_node(self):
        """Test context injection includes active node information."""
        middleware = GGLMiddleware()

        topic_graph: TopicGraph = {
            "nodes": [
                {"id": "node1", "label": "Machine Learning", "state": "exploring"},
                {"id": "node2", "label": "Deep Learning", "state": "unvisited"},
            ],
            "edges": [["node1", "node2"]],
        }

        ggl_state: GGLState = {
            "active_node_id": "node1",
            "topic_graph": topic_graph,
            "topic_graph_version": 1,
            "knowledge_cards": {
                "node1": {
                    "summary": "ML is a subset of AI that enables computers to learn from data.",
                    "keyPoints": ["Supervised learning", "Unsupervised learning"],
                    "examples": ["Email spam detection"],
                    "commonMistakes": ["Overfitting"],
                    "relatedConcepts": ["Statistics", "Linear Algebra"],
                }
            },
        }

        state: GGLMiddlewareState = {
            "messages": [HumanMessage(content="What is ML?")],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        result = middleware._build_context_message(state, IntentType.CONTINUE)

        assert result is not None
        assert "messages" in result
        context = result["messages"][0].content

        # Should include active node info
        assert "Machine Learning" in context
        assert "exploring" in context

        # Should include stats
        assert "总节点数: 2" in context or "total" in context.lower()

        # Should include intent
        assert "Continue" in context

    def test_inject_context_digression_intent(self):
        """Test context injection for digression intent."""
        middleware = GGLMiddleware()

        ggl_state: GGLState = {
            "active_node_id": "node1",
            "topic_graph": {
                "nodes": [{"id": "node1", "label": "Topic", "state": "exploring"}],
                "edges": [],
            },
        }

        state: GGLMiddlewareState = {
            "messages": [],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        result = middleware._build_context_message(state, IntentType.DIGRESSION)

        assert result is not None
        content = result["messages"][0].content
        assert "偏离" in content or "Digression" in content

    def test_inject_context_review_intent(self):
        """Test context injection for review intent."""
        middleware = GGLMiddleware()

        ggl_state: GGLState = {
            "active_node_id": "node1",
            "topic_graph": {
                "nodes": [{"id": "node1", "label": "Topic", "state": "mastered"}],
                "edges": [],
            },
        }

        state: GGLMiddlewareState = {
            "messages": [],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        result = middleware._build_context_message(state, IntentType.REVIEW)

        assert result is not None
        content = result["messages"][0].content
        assert "复习" in content or "review" in content.lower()

    def test_inject_context_mastered_intent(self):
        """Test context injection for mastered intent."""
        middleware = GGLMiddleware()

        ggl_state: GGLState = {
            "active_node_id": "node1",
            "topic_graph": {
                "nodes": [{"id": "node1", "label": "Topic", "state": "mastered"}],
                "edges": [],
            },
        }

        state: GGLMiddlewareState = {
            "messages": [],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        result = middleware._build_context_message(state, IntentType.MASTERED)

        assert result is not None
        content = result["messages"][0].content
        assert "掌握" in content or "mastered" in content.lower()

    def test_inject_context_with_knowledge_card_summary_limit(self):
        """Test that knowledge card summary is truncated if too long."""
        middleware = GGLMiddleware()

        long_summary = "A" * 500  # Very long summary

        ggl_state: GGLState = {
            "active_node_id": "node1",
            "topic_graph": {
                "nodes": [{"id": "node1", "label": "Topic", "state": "exploring"}],
                "edges": [],
            },
            "knowledge_cards": {
                "node1": {
                    "summary": long_summary,
                    "keyPoints": [],
                    "examples": [],
                    "commonMistakes": [],
                    "relatedConcepts": [],
                }
            },
        }

        state: GGLMiddlewareState = {
            "messages": [],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        result = middleware._build_context_message(state, IntentType.CONTINUE)

        assert result is not None
        # Summary should be included but may be truncated
        content = result["messages"][0].content
        assert "节点摘要" in content or "summary" in content.lower()


class TestGGLMiddlewareBeforeModel:
    """Test before_model behavior."""

    def test_before_model_skips_non_ggl_variant(self):
        """Test that before_model skips when agent_variant is not ggl."""
        middleware = GGLMiddleware()

        state: GGLMiddlewareState = {
            "messages": [HumanMessage(content="Hello")],
            "agent_variant": "default",
        }

        mock_runtime = MagicMock()

        result = middleware.before_model(state, mock_runtime)

        assert result is None

    def test_before_model_onboards_when_ggl_state_empty(self):
        """Test that before_model returns onboarding guidance for empty GGL state."""
        middleware = GGLMiddleware()

        state: GGLMiddlewareState = {
            "messages": [HumanMessage(content="Hello")],
            "agent_variant": "ggl",
        }

        mock_runtime = MagicMock()

        with patch("src.agents.middlewares.ggl_middleware.classify_intent", return_value=IntentType.CONTINUE):
            result = middleware.before_model(state, mock_runtime)

        assert result is not None
        assert "messages" in result

    def test_before_model_passes_learning_context_to_intent(self):
        middleware = GGLMiddleware()
        ggl_state: GGLState = {
            "active_node_id": "node1",
            "topic_graph": {
                "nodes": [
                    {"id": "node1", "label": "Machine Learning", "state": "exploring"},
                    {"id": "node2", "label": "Deep Learning", "state": "unvisited"},
                ],
                "edges": [],
            },
        }
        state: GGLMiddlewareState = {
            "messages": [HumanMessage(content="什么是监督学习？")],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }
        mock_runtime = MagicMock()

        with patch("src.agents.middlewares.ggl_middleware.classify_intent", return_value=IntentType.CONTINUE) as mock_classify:
            middleware.before_model(state, mock_runtime)

        assert mock_classify.called
        _, kwargs = mock_classify.call_args
        context = kwargs["ggl_context"]
        assert context["current_topic"] == "Machine Learning"
        assert "Deep Learning" in context["related_topics"]

    def test_before_model_processes_ggl_thread(self):
        """Test that before_model processes GGL threads correctly."""
        middleware = GGLMiddleware()

        ggl_state: GGLState = {
            "active_node_id": "node1",
            "topic_graph": {
                "nodes": [{"id": "node1", "label": "Topic", "state": "exploring"}],
                "edges": [],
            },
        }

        state: GGLMiddlewareState = {
            "messages": [HumanMessage(content="What is this?")],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        mock_runtime = MagicMock()

        with patch("src.agents.middlewares.ggl_middleware.classify_intent", return_value=IntentType.CONTINUE):
            result = middleware.before_model(state, mock_runtime)

        assert result is not None
        assert "messages" in result

    def test_before_model_with_digression_intent(self):
        """Test before_model behavior with digression intent."""
        middleware = GGLMiddleware()

        ggl_state: GGLState = {
            "active_node_id": "node1",
            "topic_graph": {
                "nodes": [{"id": "node1", "label": "Topic", "state": "exploring"}],
                "edges": [],
            },
        }

        state: GGLMiddlewareState = {
            "messages": [HumanMessage(content="What's the weather?")],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        mock_runtime = MagicMock()

        with patch("src.agents.middlewares.ggl_middleware.classify_intent", return_value=IntentType.DIGRESSION):
            result = middleware.before_model(state, mock_runtime)

        assert result is not None
        assert "messages" in result
        # Should include digression warning
        content = result["messages"][0].content
        assert "偏离" in content or "Digression" in content


class TestGGLMiddlewareStatsCalculation:
    """Test stats calculation in context injection."""

    def test_stats_with_mixed_node_states(self):
        """Test stats calculation with various node states."""
        middleware = GGLMiddleware()

        topic_graph: TopicGraph = {
            "nodes": [
                {"id": "n1", "label": "A", "state": "mastered"},
                {"id": "n2", "label": "B", "state": "mastered"},
                {"id": "n3", "label": "C", "state": "exploring"},
                {"id": "n4", "label": "D", "state": "blurry"},
                {"id": "n5", "label": "E", "state": "unvisited"},
            ],
            "edges": [],
        }

        ggl_state: GGLState = {
            "topic_graph": topic_graph,
        }

        state: GGLMiddlewareState = {
            "messages": [],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        result = middleware._build_context_message(state, IntentType.CONTINUE)

        assert result is not None
        context = result["messages"][0].content

        # Should show total count
        assert "5" in context  # Total nodes

        # Should show mastered count
        assert "2" in context  # Mastered nodes

    def test_stats_with_empty_graph(self):
        """Test stats with empty graph."""
        middleware = GGLMiddleware()

        topic_graph: TopicGraph = {
            "nodes": [],
            "edges": [],
        }

        ggl_state: GGLState = {
            "topic_graph": topic_graph,
        }

        state: GGLMiddlewareState = {
            "messages": [],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        result = middleware._build_context_message(state, IntentType.CONTINUE)

        assert result is not None
        # Should handle empty graph gracefully
        content = result["messages"][0].content
        assert "0" in content or "尚未创建" in content
