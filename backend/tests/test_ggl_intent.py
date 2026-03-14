"""Tests for GGL intent classification module."""

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from src.ggl.intent import (
    IntentType,
    _get_message_hash,
    _intent_cache,
    classify_intent,
)


def setup_function():
    _intent_cache.clear()


class TestIntentClassification:
    """Test intent classification functionality."""

    def test_get_message_hash_consistency(self):
        """Test that message hash is consistent for same input."""
        msg = "Hello, world!"
        hash1 = _get_message_hash(msg)
        hash2 = _get_message_hash(msg)
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hex length

    def test_get_message_hash_different_inputs(self):
        """Test that different messages produce different hashes."""
        hash1 = _get_message_hash("Hello")
        hash2 = _get_message_hash("World")
        assert hash1 != hash2

    def test_classify_intent_empty_messages(self):
        """Test that empty messages return Continue."""
        result = classify_intent([])
        assert result == IntentType.CONTINUE

    def test_classify_intent_no_user_message(self):
        """Test that messages without user input return Continue."""
        messages = [AIMessage(content="Hello!")]
        result = classify_intent(messages)
        assert result == IntentType.CONTINUE

    def test_classify_intent_with_human_message(self):
        """Test classification with deterministic mocked LLM response."""
        messages = [HumanMessage(content="What is machine learning?")]
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content='{"intent":"Continue","reason":"test"}')
        result = classify_intent(
            messages,
            llm=mock_llm,
            ggl_context={
                "current_topic": "Machine Learning",
                "related_topics": ["Supervised Learning", "Deep Learning"],
            },
        )
        assert result == IntentType.CONTINUE
        called_prompt = mock_llm.invoke.call_args.args[0]
        assert "当前学习主题: Machine Learning" in called_prompt
        assert "相关知识点: Supervised Learning、Deep Learning" in called_prompt


class TestIntentFallback:
    """Test intent classification fallback behavior."""

    def test_classify_intent_llm_creation_failure(self):
        """Test fallback when LLM creation fails."""
        messages = [HumanMessage(content="Test message")]

        with patch("src.ggl.intent.create_chat_model", side_effect=Exception("Config error")):
            result = classify_intent(messages)
            assert result == IntentType.CONTINUE

    def test_classify_intent_with_complex_message_content(self):
        """Test handling of complex message content (list format)."""
        messages = [
            HumanMessage(content=[{"type": "text", "text": "What is AI?"}])
        ]
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content='{"intent":"Continue","reason":"test"}')
        result = classify_intent(messages, llm=mock_llm)
        assert result == IntentType.CONTINUE

    def test_classify_intent_cache_is_context_sensitive(self):
        """Same message with different learning context should not share cache entry."""
        messages = [HumanMessage(content="什么是监督学习？")]
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            MagicMock(content='{"intent":"Continue","reason":"topic related"}'),
            MagicMock(content='{"intent":"Digression","reason":"topic mismatch"}'),
        ]

        intent_a = classify_intent(
            messages,
            llm=mock_llm,
            ggl_context={"current_topic": "机器学习", "related_topics": ["监督学习"]},
        )
        intent_b = classify_intent(
            messages,
            llm=mock_llm,
            ggl_context={"current_topic": "线性代数", "related_topics": ["矩阵"]},
        )

        assert intent_a == IntentType.CONTINUE
        assert intent_b == IntentType.DIGRESSION
        assert mock_llm.invoke.call_count == 2


class TestIntentType:
    """Test IntentType enum."""

    def test_intent_type_values(self):
        """Test that IntentType has correct values."""
        assert IntentType.CONTINUE.value == "Continue"
        assert IntentType.DIGRESSION.value == "Digression"
        assert IntentType.REVIEW.value == "Review"
        assert IntentType.MASTERED.value == "Mastered"

    def test_intent_type_comparison(self):
        """Test IntentType comparison."""
        assert IntentType.CONTINUE == IntentType.CONTINUE
        assert IntentType.CONTINUE != IntentType.DIGRESSION
