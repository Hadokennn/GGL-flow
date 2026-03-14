"""Integration tests for GGL end-to-end behavior."""

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from src.agents.middlewares.ggl_middleware import GGLMiddleware
from src.agents.thread_state import GGLState
from src.ggl.intent import IntentType


class TestGGLEndToEnd:
    """End-to-end integration tests for GGL."""

    def test_continue_intent_flow(self):
        """Test complete flow with Continue intent."""
        middleware = GGLMiddleware()

        ggl_state: GGLState = {
            "active_node_id": "ml_basics",
            "topic_graph": {
                "nodes": [
                    {"id": "ml_basics", "label": "机器学习基础", "state": "exploring"},
                    {"id": "supervised", "label": "监督学习", "state": "unvisited"},
                ],
                "edges": [["ml_basics", "supervised"]],
            },
            "knowledge_cards": {
                "ml_basics": {
                    "summary": "机器学习是AI的一个分支",
                    "keyPoints": ["数据驱动", "模型训练"],
                    "examples": [],
                    "commonMistakes": [],
                    "relatedConcepts": [],
                }
            },
        }

        state = {
            "messages": [
                HumanMessage(content="什么是监督学习？"),
            ],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        mock_runtime = MagicMock()

        # Mock intent classification to return Continue
        with patch("src.agents.middlewares.ggl_middleware.classify_intent", return_value=IntentType.CONTINUE):
            result = middleware.before_model(state, mock_runtime)

        assert result is not None
        assert "messages" in result
        context = result["messages"][0].content

        # Should include active node
        assert "机器学习基础" in context

        # Should indicate Continue intent
        assert "Continue" in context

    def test_digression_intent_flow(self):
        """Test complete flow with Digression intent."""
        middleware = GGLMiddleware()

        ggl_state: GGLState = {
            "active_node_id": "math_linear_algebra",
            "topic_graph": {
                "nodes": [
                    {"id": "math_linear_algebra", "label": "线性代数", "state": "exploring"},
                ],
                "edges": [],
            },
        }

        state = {
            "messages": [
                HumanMessage(content="今天天气怎么样？"),  # Off-topic question
            ],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        mock_runtime = MagicMock()

        with patch("src.agents.middlewares.ggl_middleware.classify_intent", return_value=IntentType.DIGRESSION):
            result = middleware.before_model(state, mock_runtime)

        assert result is not None
        context = result["messages"][0].content

        # Should include digression warning
        assert "偏离" in context or "Digression" in context

    def test_review_intent_flow(self):
        """Test complete flow with Review intent."""
        middleware = GGLMiddleware()

        ggl_state: GGLState = {
            "active_node_id": "calculus",
            "topic_graph": {
                "nodes": [
                    {"id": "calculus", "label": "微积分", "state": "mastered"},
                    {"id": "derivatives", "label": "导数", "state": "mastered"},
                ],
                "edges": [["calculus", "derivatives"]],
            },
        }

        state = {
            "messages": [
                HumanMessage(content="帮我复习一下导数的内容"),
            ],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        mock_runtime = MagicMock()

        with patch("src.agents.middlewares.ggl_middleware.classify_intent", return_value=IntentType.REVIEW):
            result = middleware.before_model(state, mock_runtime)

        assert result is not None
        context = result["messages"][0].content

        # Should include review indication
        assert "复习" in context or "Review" in context

    def test_mastered_intent_flow(self):
        """Test complete flow with Mastered intent."""
        middleware = GGLMiddleware()

        ggl_state: GGLState = {
            "active_node_id": "python_basics",
            "topic_graph": {
                "nodes": [
                    {"id": "python_basics", "label": "Python基础", "state": "exploring"},
                ],
                "edges": [],
            },
        }

        state = {
            "messages": [
                HumanMessage(content="我已经掌握了Python基础"),
            ],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        mock_runtime = MagicMock()

        with patch("src.agents.middlewares.ggl_middleware.classify_intent", return_value=IntentType.MASTERED):
            result = middleware.before_model(state, mock_runtime)

        assert result is not None
        context = result["messages"][0].content

        # Should include mastered indication
        assert "掌握" in context or "Mastered" in context


class TestGGLWithConversationHistory:
    """Test GGL behavior with conversation history."""

    def test_multi_turn_conversation(self):
        """Test GGL with multi-turn conversation."""
        middleware = GGLMiddleware()

        ggl_state: GGLState = {
            "active_node_id": "topic1",
            "topic_graph": {
                "nodes": [
                    {"id": "topic1", "label": "主题1", "state": "exploring"},
                ],
                "edges": [],
            },
        }

        # Simulate conversation with multiple turns
        state = {
            "messages": [
                HumanMessage(content="开始学习"),
                AIMessage(content="好的，让我们开始学习"),
                HumanMessage(content="继续深入"),
                AIMessage(content="好的"),
                HumanMessage(content="现在讲下一个主题"),
            ],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        mock_runtime = MagicMock()

        with patch("src.agents.middlewares.ggl_middleware.classify_intent", return_value=IntentType.CONTINUE):
            result = middleware.before_model(state, mock_runtime)

        assert result is not None
        assert "messages" in result


class TestGGLPerformance:
    """Performance tests for GGL middleware."""

    def test_before_model_latency_under_threshold(self):
        """Test that before_model completes within acceptable time."""
        import time

        middleware = GGLMiddleware()

        ggl_state: GGLState = {
            "active_node_id": "test",
            "topic_graph": {
                "nodes": [{"id": "test", "label": "Test", "state": "exploring"}],
                "edges": [],
            },
        }

        state = {
            "messages": [HumanMessage(content="Test")],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        mock_runtime = MagicMock()

        with patch("src.agents.middlewares.ggl_middleware.classify_intent", return_value=IntentType.CONTINUE):
            start = time.time()
            result = middleware.before_model(state, mock_runtime)
            elapsed = time.time() - start

        assert result is not None
        # Should complete quickly (intent classification is mocked)
        assert elapsed < 0.1  # 100ms threshold for mocked test

    def test_context_injection_with_large_graph(self):
        """Test context injection performance with large graph."""
        import time

        middleware = GGLMiddleware()

        # Create a large graph (100 nodes)
        nodes = [
            {"id": f"node{i}", "label": f"Node {i}", "state": "exploring" if i < 50 else "unvisited"}
            for i in range(100)
        ]

        ggl_state: GGLState = {
            "active_node_id": "node0",
            "topic_graph": {
                "nodes": nodes,
                "edges": [[f"node{i}", f"node{i+1}"] for i in range(99)],
            },
        }

        state = {
            "messages": [],
            "agent_variant": "ggl",
            "ggl": ggl_state,
        }

        start = time.time()
        result = middleware._build_context_message(state, IntentType.CONTINUE)
        elapsed = time.time() - start

        assert result is not None
        # Should still be fast even with large graph
        assert elapsed < 0.1  # 100ms threshold

        # Should include stats
        assert "100" in result["messages"][0].content  # Total nodes
